from typing import Optional
"""
Instagram Stories adapter.

Publish flow (Graph API, version from IG_GRAPH_API_VERSION env, default v21.0):
  1. GET  /{ig-user-id}/content_publishing_limit?fields=config,quota_usage
     → quota_usage >= config.quota_total → retry_later (job stays queued)
  2. POST /{ig-user-id}/media
     (media_type=STORIES, image_url or video_url, access_token) → creation_id
  3. Video only: poll GET /{creation_id}?fields=status_code until FINISHED (6×5 s)
  4. POST /{ig-user-id}/media_publish (creation_id, access_token) → media_id = external_id

Insights — story metrics expire 24 h after publish, so the poller stops at 23.5 h.
Two separate calls (mixing breakdown with basic metrics can cause API errors):
  Call 1: GET /{media-id}/insights?metric=impressions,reach,replies&period=lifetime
  Call 2: GET /{media-id}/insights?metric=navigation
            &breakdown=story_navigation_action_type&period=lifetime
  Navigation breakdown keys: TAP_FORWARD→taps_forward, TAP_BACK→taps_back,
                              TAP_EXIT→exits, SWIPE_FORWARD→swipe_forward

Ref: https://developers.facebook.com/docs/instagram-platform/content-publishing
     https://developers.facebook.com/docs/instagram-platform/insights/
"""
import asyncio
import json

import httpx
from cryptography.fernet import Fernet

from .base import StoryResult

IG_GRAPH_BASE = "https://graph.facebook.com"
IG_DEFAULT_VERSION = "v21.0"

_BASIC_METRICS = "impressions,reach,replies"
_NAV_METRIC = "navigation"
_NAV_BREAKDOWN = "story_navigation_action_type"
# Map API breakdown dimension values → stored metric names
_NAV_MAP: dict[str, str] = {
    "TAP_FORWARD": "taps_forward",
    "TAP_BACK": "taps_back",
    "TAP_EXIT": "exits",
    "SWIPE_FORWARD": "swipe_forward",
}


class InstagramPublisher:
    platform = "ig"

    def __init__(
        self,
        access_token: Optional[str] = None,
        ig_user_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> None:
        self._env_token = access_token
        self._env_user_id = ig_user_id
        self._version = version

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_credentials(self, account) -> tuple[str, str]:
        """Return (access_token, ig_user_id) — account DB creds take priority."""
        if account and getattr(account, "credentials_enc", None):
            try:
                from app.config import settings

                f = Fernet(settings.FERNET_KEY.encode())
                payload = json.loads(f.decrypt(account.credentials_enc.encode()))
                token = payload.get("access_token", "")
                user_id = payload.get("ig_user_id", "")
                if token and user_id:
                    return token, user_id
            except Exception:
                pass

        from app.config import settings

        token = self._env_token or settings.IG_ACCESS_TOKEN
        user_id = self._env_user_id or settings.IG_USER_ID
        return token, user_id

    def _base_url(self) -> str:
        ver = self._version
        if not ver:
            try:
                from app.config import settings

                ver = getattr(settings, "IG_GRAPH_API_VERSION", IG_DEFAULT_VERSION)
            except Exception:
                ver = IG_DEFAULT_VERSION
        return f"{IG_GRAPH_BASE}/{ver or IG_DEFAULT_VERSION}"

    async def _get(
        self, client: httpx.AsyncClient, path: str, token: str, **params
    ) -> dict:
        params["access_token"] = token
        resp = await client.get(
            f"{self._base_url()}{path}", params=params, timeout=30.0
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"IG API error {err.get('code')}: {err.get('message')}"
            )
        return data

    async def _post(
        self, client: httpx.AsyncClient, path: str, token: str, **form_params
    ) -> dict:
        form_params["access_token"] = token
        resp = await client.post(
            f"{self._base_url()}{path}", data=form_params, timeout=60.0
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"IG API error {err.get('code')}: {err.get('message')}"
            )
        return data

    async def _check_quota(
        self, client: httpx.AsyncClient, token: str, user_id: str
    ) -> bool:
        """Returns True if quota allows one more publish; optimistic on any error."""
        try:
            data = await self._get(
                client,
                f"/{user_id}/content_publishing_limit",
                token,
                fields="config,quota_usage",
            )
            items = data.get("data", [])
            if not items:
                return True
            item = items[0]
            usage = item.get("quota_usage", 0)
            total = item.get("config", {}).get("quota_total", 100)
            return int(usage) < int(total)
        except Exception:
            return True  # can't verify → allow optimistically

    async def _wait_for_video_ready(
        self, client: httpx.AsyncClient, token: str, creation_id: str
    ) -> None:
        """Poll status_code until FINISHED; raise on ERROR or 30-second timeout."""
        for _ in range(6):
            data = await self._get(
                client, f"/{creation_id}", token, fields="status_code"
            )
            status = data.get("status_code", "IN_PROGRESS")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise RuntimeError(
                    f"IG video container {creation_id} processing failed (status=ERROR)"
                )
            await asyncio.sleep(5)
        raise RuntimeError(
            f"IG video container {creation_id} not ready after 30 s"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def publish_story(
        self, account, media: list, caption: Optional[str]
    ) -> StoryResult:
        if not media:
            return StoryResult(ok=False, error="no media items")

        first = media[0]
        media_url: str = getattr(first, "url", "")
        media_type: str = getattr(first, "media_type", "photo")

        if not media_url:
            return StoryResult(ok=False, error="media url is empty")

        token, user_id = self._get_credentials(account)
        if not token or not user_id:
            return StoryResult(
                ok=False,
                error="Instagram credentials not configured (IG_ACCESS_TOKEN / IG_USER_ID)",
            )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Step 1 — rate-limit check
                if not await self._check_quota(client, token, user_id):
                    return StoryResult(
                        ok=False,
                        retry_later=True,
                        error="IG publishing quota exhausted — job stays queued",
                    )

                # Step 2 — create media container (media_url must be publicly reachable)
                is_video = media_type == "video"
                url_field = "video_url" if is_video else "image_url"
                container = await self._post(
                    client,
                    f"/{user_id}/media",
                    token,
                    media_type="STORIES",
                    **{url_field: media_url},
                )
                creation_id: str = container["id"]

                # Step 3 — wait for video processing (images are processed instantly)
                if is_video:
                    await self._wait_for_video_ready(client, token, creation_id)

                # Step 4 — publish
                publish = await self._post(
                    client,
                    f"/{user_id}/media_publish",
                    token,
                    creation_id=creation_id,
                )
                media_id: str = publish["id"]

            return StoryResult(ok=True, external_id=media_id)

        except Exception as exc:
            return StoryResult(ok=False, error=str(exc))

    async def fetch_insights(
        self, account, external_id: str
    ) -> dict[str, int]:
        if not external_id:
            return {}

        token, _ = self._get_credentials(account)
        if not token:
            return {}

        result: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Call 1 — basic story metrics (impressions, reach, replies)
            try:
                data = await self._get(
                    client,
                    f"/{external_id}/insights",
                    token,
                    metric=_BASIC_METRICS,
                    period="lifetime",
                )
                for item in data.get("data", []):
                    name = item.get("name")
                    values = item.get("values", [])
                    if name and values:
                        result[name] = int(values[0].get("value", 0))
            except Exception:
                pass

            # Call 2 — navigation breakdown (exits, taps_forward, taps_back, swipe_forward)
            # These are NOT standalone metrics; they come as breakdown values of 'navigation'.
            try:
                nav_data = await self._get(
                    client,
                    f"/{external_id}/insights",
                    token,
                    metric=_NAV_METRIC,
                    breakdown=_NAV_BREAKDOWN,
                    period="lifetime",
                )
                for item in nav_data.get("data", []):
                    if item.get("name") != "navigation":
                        continue
                    total_val = item.get("total_value", {})
                    for bd in total_val.get("breakdowns", []):
                        for res in bd.get("results", []):
                            dims = res.get("dimension_values", [])
                            val = res.get("value", 0)
                            if dims:
                                key = _NAV_MAP.get(dims[0], dims[0].lower())
                                result[key] = int(val)
            except Exception:
                pass

        return result
