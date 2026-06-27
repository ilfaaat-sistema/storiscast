from typing import Optional, Protocol, runtime_checkable
from pydantic import BaseModel


class StoryResult(BaseModel):
    ok: bool
    external_id: Optional[str] = None
    error: Optional[str] = None
    manual: bool = False
    retry_later: bool = False  # leave job as queued (limit/flood), not error


@runtime_checkable
class StoryPublisher(Protocol):
    platform: str

    async def publish_story(
        self, account, media: list, caption: Optional[str]
    ) -> StoryResult: ...

    async def fetch_insights(
        self, account, external_id: str
    ) -> dict[str, int]: ...
