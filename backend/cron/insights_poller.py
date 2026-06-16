"""
Render Cron Job — insights-poller (every hour).

For jobs with external_id, calls fetch_insights and saves snapshots.
In Phase 0 stubs return zeroes; real metrics arrive in Phase 1+.
Run locally: python -m cron.insights_poller  (from backend/)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import ConnectedAccount, Insight, Job
from app.adapters.stub import StubPublisher
from app.adapters.vk import VKPublisher
from app.adapters.telegram import TelegramPublisher
from app.adapters.instagram import InstagramPublisher

ADAPTERS: dict = {
    "vk": VKPublisher(),
    "tg": TelegramPublisher(),
    "ig": InstagramPublisher(),
    "fb": StubPublisher("fb"),
    "wa": StubPublisher("wa"),
}

# IG story insights disappear after 24 h — stop polling just before expiry.
_IG_INSIGHTS_TTL = timedelta(hours=23, minutes=30)


async def _poll_job(session, job: Job) -> None:
    # IG story insights expire after 24 h — skip jobs whose window has closed.
    if job.platform == "ig" and job.published_at:
        published = job.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - published > _IG_INSIGHTS_TTL:
            return

    account = await session.get(ConnectedAccount, job.account_id)
    adapter = ADAPTERS.get(job.platform)
    if adapter is None:
        return

    try:
        metrics = await adapter.fetch_insights(account, job.external_id)
    except Exception as exc:
        print(f"insights_poller: error for job {job.id}: {exc}")
        return

    now = datetime.now(timezone.utc)
    for metric, value in metrics.items():
        session.add(
            Insight(
                job_id=job.id,
                platform=job.platform,
                metric=metric,
                value=int(value),
                fetched_at=now,
            )
        )
    await session.commit()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(Job).where(
                Job.status == "done",
                Job.external_id.isnot(None),
            )
        )
        for job in rows.all():
            await _poll_job(session, job)

    print("insights_poller: done")


if __name__ == "__main__":
    asyncio.run(main())
