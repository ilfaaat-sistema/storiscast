from typing import Optional
"""
VK Stories adapter.

Upload flow (per VK API v5.199 schema):
  1. stories.getPhotoUploadServer / stories.getVideoUploadServer → upload_url
  2. POST multipart file to upload_url (field name: "file") → {"upload_result": "<hash>"}
  3. stories.save(upload_results_json=<json from step 2>) → story object
     external_id = "{owner_id}_{story_id}"

Insights:
  stories.getStats(owner_id, story_id) → views/replies/shares/likes/…
  stories.getViewers(owner_id, story_id) → count of viewers
"""
import json
import httpx
from cryptography.fernet import Fernet

from .base import StoryResult

VK_API_URL = "https://api.vk.com/method/"
VK_API_VERSION = "5.199"


class VKPublisher:
    platform = "vk"

    def __init__(self, access_token: Optional[str] = None) -> None:
        # Token can come from constructor (tests / env fallback) or account credentials.
        self._env_token = access_token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_token(self, account) -> str:
        if account and account.credentials_enc:
            try:
                from app.config import settings
                f = Fernet(settings.FERNET_KEY.encode())
                payload = json.loads(f.decrypt(account.credentials_enc.encode()))
                token = payload.get("access_token", "")
                if token:
                    return token
            except Exception:
                pass

        if self._env_token:
            return self._env_token

        from app.config import settings
        return settings.VK_ACCESS_TOKEN

    async def _api(self, client: httpx.AsyncClient, method: str, token: str, **params) -> dict:
        params["access_token"] = token
        params["v"] = VK_API_VERSION
        resp = await client.post(f"{VK_API_URL}{method}", data=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            raise RuntimeError(
                f"VK API error {err.get('error_code')}: {err.get('error_msg')}"
            )
        return data["response"]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def publish_story(self, account, media: list, caption: Optional[str]) -> StoryResult:
        if not media:
            return StoryResult(ok=False, error="no media items")

        first = media[0]
        media_url: str = getattr(first, "url", "")
        media_type: str = getattr(first, "media_type", "photo")

        if not media_url:
            return StoryResult(ok=False, error="media url is empty")

        token = self._get_token(account)
        if not token:
            return StoryResult(ok=False, error="VK access token not configured")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Step 1 — get upload URL
                vk_method = (
                    "stories.getVideoUploadServer"
                    if media_type == "video"
                    else "stories.getPhotoUploadServer"
                )
                server = await self._api(client, vk_method, token, add_to_news=1)
                upload_url: str = server["upload_url"]

                # Step 2 — download media from Storage and upload to VK
                media_resp = await client.get(media_url)
                media_resp.raise_for_status()

                content_type = (
                    media_resp.headers.get("content-type", "image/jpeg")
                    .split(";")[0]
                    .strip()
                )
                filename = "story.mp4" if "video" in content_type else "story.jpg"

                upload_resp = await client.post(
                    upload_url,
                    files={"file": (filename, media_resp.content, content_type)},
                )
                upload_resp.raise_for_status()
                upload_data = upload_resp.json()

                # Step 3 — stories.save
                save_result = await self._api(
                    client,
                    "stories.save",
                    token,
                    upload_results_json=json.dumps(upload_data),
                )

            story = save_result["items"][0]
            external_id = f"{story['owner_id']}_{story['id']}"
            return StoryResult(ok=True, external_id=external_id)

        except Exception as exc:
            return StoryResult(ok=False, error=str(exc))

    async def fetch_insights(self, account, external_id: str) -> dict[str, int]:
        try:
            owner_str, story_str = external_id.split("_", 1)
            owner_id = int(owner_str)
            story_id = int(story_str)
        except (ValueError, AttributeError):
            return {}

        token = self._get_token(account)
        if not token:
            return {}

        result: dict[str, int] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            # stories.getStats
            try:
                stats = await self._api(
                    client, "stories.getStats", token,
                    owner_id=owner_id, story_id=story_id,
                )
                for metric in ("views", "replies", "shares", "likes",
                               "subscribers", "answer", "bans", "open_link"):
                    stat = stats.get(metric, {})
                    if isinstance(stat, dict) and stat.get("count") is not None:
                        result[metric] = int(stat["count"])
            except Exception:
                pass

            # stories.getViewers — returns total viewer count
            try:
                viewers = await self._api(
                    client, "stories.getViewers", token,
                    owner_id=owner_id, story_id=story_id,
                    count=0,  # count=0 returns only the total count
                    extended=0,
                )
                result["viewers_count"] = int(viewers.get("count", 0))
            except Exception:
                pass

        return result
