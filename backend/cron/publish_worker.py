"""
Render Cron Job — publish-worker (every 1-2 min).

Picks queued jobs, calls the appropriate adapter, writes status back.
Each run is stateless: reads Postgres, does work, exits.
Run locally: python -m cron.publish_worker  (from backend/)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models import Cast, ConnectedAccount, Job
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


async def _process_job(session, job: Job) -> None:
    if job.status not in ("queued", "scheduled"):
        return

    # WhatsApp has no API — always manual
    if job.platform == "wa":
        job.status = "manual"
        await session.commit()
        return

    # Facebook: piggybacking on Instagram — done only after IG succeeds
    if job.platform == "fb":
        ig_result = await session.scalars(
            select(Job).where(Job.cast_id == job.cast_id, Job.platform == "ig")
        )
        ig_job = ig_result.first()
        if ig_job is None or ig_job.status != "done":
            return  # wait for next cron tick
        job.status = "done"
        job.published_at = datetime.now(timezone.utc)
        await session.commit()
        return

    # Optimistic lock: mark sending before calling adapter (idempotency)
    job.status = "sending"
    job.attempts += 1
    await session.commit()

    account = await session.get(ConnectedAccount, job.account_id)
    cast = await session.get(Cast, job.cast_id)
    if cast:
        await session.refresh(cast, ["media"])

    adapter = ADAPTERS.get(job.platform)
    if adapter is None:
        job.status = "error"
        job.last_error = f"no adapter for {job.platform}"
        await session.commit()
        return

    try:
        result = await adapter.publish_story(account, cast.media if cast else [], cast.caption if cast else None)
        if result.ok:
            job.status = "done"
            job.external_id = result.external_id
            job.published_at = datetime.now(timezone.utc)
        elif result.retry_later:
            # Quota exhausted or FloodWait — leave queued, try next cron tick
            job.status = "queued"
            job.last_error = result.error
        else:
            job.status = "error"
            job.last_error = result.error
    except Exception as exc:
        job.status = "error"
        job.last_error = str(exc)

    await session.commit()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        rows = await session.scalars(
            select(Job)
            .where(Job.status.in_(["queued", "scheduled"]))
            .options(selectinload(Job.cast))
            .order_by(Job.created_at)
            .limit(50)
        )
        for job in rows.all():
            await _process_job(session, job)

    print("publish_worker: done")


if __name__ == "__main__":
    asyncio.run(main())
