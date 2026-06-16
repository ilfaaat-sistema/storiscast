from datetime import datetime
from pydantic import BaseModel


class MediaUploadResponse(BaseModel):
    url: str
    media_type: str  # photo | video


class MediaItem(BaseModel):
    url: str
    media_type: str


class CastCreate(BaseModel):
    caption: str | None = None
    media: list[MediaItem]
    targets: list[str]  # ["vk", "tg", "ig", "wa"]
    scheduled_at: datetime | None = None


class JobOut(BaseModel):
    id: str
    platform: str
    status: str
    external_id: str | None = None
    published_at: datetime | None = None
    last_error: str | None = None

    model_config = {"from_attributes": True}


class CastOut(BaseModel):
    id: str
    caption: str | None
    status: str
    created_at: datetime
    jobs: list[JobOut] = []

    model_config = {"from_attributes": True}


class AccountOut(BaseModel):
    id: str
    platform: str
    handle: str | None
    status: str

    model_config = {"from_attributes": True}


class InsightOut(BaseModel):
    job_id: str
    platform: str
    metric: str
    value: int
    fetched_at: datetime

    model_config = {"from_attributes": True}


class JobInsightOut(BaseModel):
    platform: str
    status: str
    metrics: dict[str, int]


class CastInsightsOut(BaseModel):
    jobs: list[JobInsightOut]


class CastListOut(BaseModel):
    id: str
    caption: str | None
    status: str
    created_at: datetime
    platforms: list[str]


class AuthMeOut(BaseModel):
    tenant_id: str
