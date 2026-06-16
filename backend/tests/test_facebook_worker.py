"""
Phase 4 — Facebook auto-done tests.

Verifies _process_job() FB logic without a real DB or network calls.
session is mocked with AsyncMock; Job-like objects use SimpleNamespace.

Scenarios:
  a) FB-job → done when IG-job is done
  b) FB-job stays queued while IG-job is queued / sending / error
  c) FB-job untouched when no IG-job exists for cast_id
  d) FB-job already done is not re-processed
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from cron.publish_worker import _process_job


def _fb_job(status: str = "queued", cast_id: str = "cast-001") -> SimpleNamespace:
    return SimpleNamespace(
        id="fb-job-1",
        cast_id=cast_id,
        account_id="acc-1",
        platform="fb",
        status=status,
        attempts=0,
        last_error=None,
        external_id=None,
        published_at=None,
    )


def _ig_job(status: str = "done", cast_id: str = "cast-001") -> SimpleNamespace:
    return SimpleNamespace(
        id="ig-job-1",
        cast_id=cast_id,
        platform="ig",
        status=status,
        external_id="987654_111222",
    )


def _mock_session(ig_job_return=None) -> AsyncMock:
    """Async session whose scalars().first() returns ig_job_return."""
    scalar_result = MagicMock()
    scalar_result.first.return_value = ig_job_return
    session = AsyncMock()
    session.scalars.return_value = scalar_result
    return session


# ── a) FB → done after IG done ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fb_done_when_ig_done():
    ig_job = _ig_job(status="done")
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=ig_job)

    await _process_job(session, fb_job)

    assert fb_job.status == "done"
    assert fb_job.published_at is not None
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_fb_published_at_is_utc_aware():
    """published_at must be timezone-aware and fall in the expected window."""
    ig_job = _ig_job(status="done")
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=ig_job)

    before = datetime.now(timezone.utc)
    await _process_job(session, fb_job)
    after = datetime.now(timezone.utc)

    assert fb_job.published_at.tzinfo is not None
    assert before <= fb_job.published_at <= after


@pytest.mark.asyncio
async def test_fb_scheduled_also_auto_done():
    """FB-job in 'scheduled' status is treated same as 'queued' and goes done."""
    ig_job = _ig_job(status="done")
    fb_job = _fb_job(status="scheduled")
    session = _mock_session(ig_job_return=ig_job)

    await _process_job(session, fb_job)

    assert fb_job.status == "done"
    session.commit.assert_called_once()


# ── b) FB stays queued while IG not done ────────────────────────────────────

@pytest.mark.asyncio
async def test_fb_stays_queued_while_ig_queued():
    ig_job = _ig_job(status="queued")
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=ig_job)

    await _process_job(session, fb_job)

    assert fb_job.status == "queued"
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_fb_stays_queued_while_ig_sending():
    ig_job = _ig_job(status="sending")
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=ig_job)

    await _process_job(session, fb_job)

    assert fb_job.status == "queued"
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_fb_stays_queued_while_ig_error():
    """IG errored but might be retried; FB waits rather than fail."""
    ig_job = _ig_job(status="error")
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=ig_job)

    await _process_job(session, fb_job)

    assert fb_job.status == "queued"
    session.commit.assert_not_called()


# ── c) No IG job for this cast_id ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_fb_stays_queued_when_no_ig_job():
    fb_job = _fb_job()
    session = _mock_session(ig_job_return=None)

    await _process_job(session, fb_job)

    assert fb_job.status == "queued"
    session.commit.assert_not_called()


# ── d) FB already done — no re-processing ───────────────────────────────────

@pytest.mark.asyncio
async def test_fb_not_reprocessed_when_already_done():
    fb_job = _fb_job(status="done")
    session = _mock_session()

    await _process_job(session, fb_job)

    assert fb_job.status == "done"
    session.scalars.assert_not_called()
    session.commit.assert_not_called()
