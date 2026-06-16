import asyncio
import mimetypes
import uuid
from pathlib import Path

from supabase import create_client
from ..config import settings


def _detect_media_type(content_type: str, filename: str) -> str:
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("image/"):
        return "photo"
    ext = Path(filename).suffix.lower()
    if ext in {".mp4", ".mov", ".avi", ".webm"}:
        return "video"
    return "photo"


async def upload_to_storage(
    file_content: bytes, original_filename: str, content_type: str
) -> tuple[str, str]:
    """Upload bytes to Supabase Storage. Returns (public_url, media_type)."""
    ext = Path(original_filename).suffix or mimetypes.guess_extension(content_type) or ""
    storage_path = f"uploads/{uuid.uuid4().hex}{ext}"
    media_type = _detect_media_type(content_type, original_filename)

    def _upload() -> str:
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        bucket.upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return bucket.get_public_url(storage_path)

    public_url: str = await asyncio.to_thread(_upload)
    return public_url, media_type
