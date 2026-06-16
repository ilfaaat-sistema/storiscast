from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from ..auth import get_current_tenant
from ..schemas import MediaUploadResponse
from ..services.storage import upload_to_storage

router = APIRouter()


@router.post("/media", response_model=MediaUploadResponse)
async def upload_media(
    file: UploadFile = File(...),
    _: str = Depends(get_current_tenant),  # auth required; tenant not used for storage path
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    content_type = file.content_type or "application/octet-stream"
    try:
        url, media_type = await upload_to_storage(content, file.filename or "upload", content_type)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    return MediaUploadResponse(url=url, media_type=media_type)
