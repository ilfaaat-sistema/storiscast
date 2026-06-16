"""
Telegram Stories adapter.

Uses Telethon MTProto user-session (NOT a bot token).
Flow:
  1. Build TelegramClient from StringSession (stateless — suitable for cron).
  2. CanSendStoryRequest: if count_remains == 0, return retry_later so job stays queued.
  3. Download media from Supabase Storage URL via httpx.
  4. Upload via client.upload_file() → InputMediaUploadedPhoto/Document.
  5. SendStoryRequest → extract story_id from UpdateStoryID in the Updates response.
  6. FloodWaitError → retry_later (respect the pause, don't mark as error).

Limits (non-Premium): 3 stories/day, 24 h lifetime, caption ≤ 200 chars.
"""
import httpx
import json
from typing import Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
from telethon.tl.functions.stories import (
    CanSendStoryRequest,
    GetStoriesViewsRequest,
    SendStoryRequest,
)
from telethon.tl.types import (
    DocumentAttributeVideo,
    InputMediaUploadedDocument,
    InputMediaUploadedPhoto,
    InputPeerSelf,
    InputPrivacyValueAllowAll,
    UpdateStoryID,
)
from cryptography.fernet import Fernet

from .base import StoryResult


class TelegramPublisher:
    platform = "tg"

    def __init__(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        session_str: Optional[str] = None,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_str = session_str

    def _get_credentials(self, account) -> tuple:
        if account and getattr(account, "credentials_enc", None):
            try:
                from app.config import settings
                f = Fernet(settings.FERNET_KEY.encode())
                payload = json.loads(f.decrypt(account.credentials_enc.encode()))
                api_id = int(payload["api_id"])
                api_hash = str(payload["api_hash"])
                session_str = str(payload["session_string"])
                if api_id and api_hash and session_str:
                    return api_id, api_hash, session_str
            except Exception:
                pass

        if self._api_id and self._api_hash and self._session_str:
            return self._api_id, self._api_hash, self._session_str

        try:
            from app.config import settings
            if settings.TG_API_ID and settings.TG_API_HASH and settings.TG_SESSION_STRING:
                return settings.TG_API_ID, settings.TG_API_HASH, settings.TG_SESSION_STRING
        except Exception:
            pass

        return None, None, None

    async def publish_story(self, account, media: list, caption: str | None) -> StoryResult:
        if not media:
            return StoryResult(ok=False, error="no media items")

        first = media[0]
        media_url: str = getattr(first, "url", "")
        media_type: str = getattr(first, "media_type", "photo")

        if not media_url:
            return StoryResult(ok=False, error="media url is empty")

        api_id, api_hash, session_str = self._get_credentials(account)
        if not all([api_id, api_hash, session_str]):
            return StoryResult(ok=False, error="Telegram credentials not configured")

        safe_caption = caption[:200] if caption else None

        try:
            async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
                # Check daily quota before attempting to send
                can_send = await client(CanSendStoryRequest(peer=InputPeerSelf()))
                if can_send.count_remains == 0:
                    return StoryResult(
                        ok=False,
                        retry_later=True,
                        error="TG daily story limit reached (3/day), job stays queued",
                    )

                # Download media from Supabase Storage
                async with httpx.AsyncClient(timeout=60.0) as http:
                    resp = await http.get(media_url)
                    resp.raise_for_status()
                    media_bytes = resp.content
                    content_type = (
                        resp.headers.get("content-type", "image/jpeg")
                        .split(";")[0]
                        .strip()
                    )

                filename = "story.mp4" if media_type == "video" else "story.jpg"
                uploaded = await client.upload_file(media_bytes, file_name=filename)

                if media_type == "video":
                    input_media = InputMediaUploadedDocument(
                        file=uploaded,
                        mime_type=content_type or "video/mp4",
                        attributes=[
                            DocumentAttributeVideo(
                                duration=0.0, w=0, h=0, supports_streaming=True
                            )
                        ],
                    )
                else:
                    input_media = InputMediaUploadedPhoto(file=uploaded)

                updates = await client(
                    SendStoryRequest(
                        peer=InputPeerSelf(),
                        media=input_media,
                        privacy_rules=[InputPrivacyValueAllowAll()],
                        caption=safe_caption,
                        period=86400,  # 24-hour lifetime
                    )
                )

                story_id = None
                for upd in getattr(updates, "updates", []):
                    if isinstance(upd, UpdateStoryID):
                        story_id = upd.id
                        break

                if story_id is None:
                    return StoryResult(ok=False, error="story sent but ID not found in updates")

                return StoryResult(ok=True, external_id=str(story_id))

        except FloodWaitError as exc:
            return StoryResult(
                ok=False,
                retry_later=True,
                error=f"FloodWaitError: retry after {exc.seconds}s",
            )
        except Exception as exc:
            return StoryResult(ok=False, error=str(exc))

    async def fetch_insights(self, account, external_id: str) -> dict[str, int]:
        try:
            story_id = int(external_id)
        except (ValueError, TypeError):
            return {}

        api_id, api_hash, session_str = self._get_credentials(account)
        if not all([api_id, api_hash, session_str]):
            return {}

        try:
            async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
                result = await client(
                    GetStoriesViewsRequest(peer=InputPeerSelf(), id=[story_id])
                )
                if not result.views:
                    return {}

                sv = result.views[0]
                metrics: dict[str, int] = {"views": sv.views_count}
                if sv.reactions_count is not None:
                    metrics["reactions_count"] = sv.reactions_count
                if sv.forwards_count is not None:
                    metrics["forwards_count"] = sv.forwards_count
                return metrics
        except Exception:
            return {}
