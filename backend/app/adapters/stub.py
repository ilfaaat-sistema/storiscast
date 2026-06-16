import uuid
from .base import StoryResult


class StubPublisher:
    """Phase-0 stub — always succeeds instantly without hitting any network."""

    def __init__(self, platform: str) -> None:
        self.platform = platform

    async def publish_story(self, account, media: list, caption: str | None) -> StoryResult:
        return StoryResult(ok=True, external_id=f"stub_{uuid.uuid4().hex[:8]}")

    async def fetch_insights(self, account, external_id: str) -> dict[str, int]:
        return {"reach": 0, "impressions": 0}
