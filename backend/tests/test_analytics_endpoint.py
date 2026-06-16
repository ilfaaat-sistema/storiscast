"""
Phase 5 — GET /casts/{id}/insights endpoint tests.
DB is mocked — no real Postgres connection required.

Contract verified:
  - Returns { "jobs": [...] } with platform / status / metrics per job.
  - For each (job, metric) only the snapshot with the latest fetched_at is kept.
  - Jobs with no insight rows return metrics: {}.
  - Unknown cast → 404.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.auth import get_current_tenant

CAST_ID = "cast-phase5-test"
TENANT_ID = "test-tenant-analytics"
JOB_VK_ID = "job-vk-p5"
JOB_TG_ID = "job-tg-p5"
JOB_IG_ID = "job-ig-p5"

_BASE_TS = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)


def _cast():
    c = MagicMock()
    c.id = CAST_ID
    c.tenant_id = TENANT_ID
    return c


def _job(jid, platform, status="done"):
    j = MagicMock()
    j.id = jid
    j.platform = platform
    j.status = status
    j.cast_id = CAST_ID
    return j


def _insight(job_id, platform, metric, value, minutes_ago=0):
    i = MagicMock()
    i.job_id = job_id
    i.platform = platform
    i.metric = metric
    i.value = value
    i.fetched_at = _BASE_TS - timedelta(minutes=minutes_ago)
    return i


def _mock_db(cast, jobs, insights):
    db = AsyncMock()
    db.get = AsyncMock(return_value=cast)

    scalars_jobs = MagicMock()
    scalars_jobs.all.return_value = jobs

    scalars_insights = MagicMock()
    scalars_insights.all.return_value = insights

    db.scalars = AsyncMock(side_effect=[scalars_jobs, scalars_insights])
    return db


async def _get(path: str, db) -> tuple[int, dict]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_tenant] = lambda: TENANT_ID
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(path)
        return r.status_code, r.json()
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_tenant, None)


@pytest.mark.asyncio
async def test_latest_snapshot_wins_per_metric():
    """When the same metric has multiple snapshots, the one with max fetched_at is used."""
    cast = _cast()
    jobs = [_job(JOB_VK_ID, "vk")]
    insights = [
        _insight(JOB_VK_ID, "vk", "views", 100, minutes_ago=60),  # older
        _insight(JOB_VK_ID, "vk", "views", 200, minutes_ago=0),   # latest → wins
        _insight(JOB_VK_ID, "vk", "replies", 5, minutes_ago=0),
    ]

    status, data = await _get(f"/casts/{CAST_ID}/insights", _mock_db(cast, jobs, insights))

    assert status == 200
    assert "jobs" in data
    assert len(data["jobs"]) == 1
    vk = data["jobs"][0]
    assert vk["platform"] == "vk"
    assert vk["status"] == "done"
    assert vk["metrics"]["views"] == 200
    assert vk["metrics"]["replies"] == 5


@pytest.mark.asyncio
async def test_job_without_insights_has_empty_metrics():
    """Job with no insight rows in DB returns metrics: {}."""
    cast = _cast()
    jobs = [_job(JOB_VK_ID, "vk", "done"), _job(JOB_TG_ID, "tg", "queued")]
    insights = [_insight(JOB_VK_ID, "vk", "views", 150, minutes_ago=0)]

    status, data = await _get(f"/casts/{CAST_ID}/insights", _mock_db(cast, jobs, insights))

    assert status == 200
    job_map = {j["platform"]: j for j in data["jobs"]}
    assert job_map["tg"]["metrics"] == {}
    assert job_map["vk"]["metrics"]["views"] == 150


@pytest.mark.asyncio
async def test_multiple_platforms_aggregated():
    """VK, TG, and IG each aggregate their own metrics independently."""
    cast = _cast()
    jobs = [
        _job(JOB_VK_ID, "vk", "done"),
        _job(JOB_TG_ID, "tg", "done"),
        _job(JOB_IG_ID, "ig", "done"),
    ]
    insights = [
        _insight(JOB_VK_ID, "vk", "views", 300, minutes_ago=0),
        _insight(JOB_VK_ID, "vk", "replies", 7, minutes_ago=0),
        _insight(JOB_TG_ID, "tg", "views_count", 80, minutes_ago=0),
        _insight(JOB_TG_ID, "tg", "reactions_count", 10, minutes_ago=0),
        _insight(JOB_IG_ID, "ig", "reach", 500, minutes_ago=0),
        _insight(JOB_IG_ID, "ig", "taps_forward", 30, minutes_ago=0),
    ]

    status, data = await _get(f"/casts/{CAST_ID}/insights", _mock_db(cast, jobs, insights))

    assert status == 200
    job_map = {j["platform"]: j for j in data["jobs"]}
    assert job_map["vk"]["metrics"] == {"views": 300, "replies": 7}
    assert job_map["tg"]["metrics"] == {"views_count": 80, "reactions_count": 10}
    assert job_map["ig"]["metrics"] == {"reach": 500, "taps_forward": 30}


@pytest.mark.asyncio
async def test_cast_not_found_returns_404():
    """Unknown cast_id → 404."""
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    status, _ = await _get("/casts/nonexistent-cast/insights", db)
    assert status == 404


@pytest.mark.asyncio
async def test_cast_with_no_jobs_returns_empty_list():
    """Cast exists but has no jobs → jobs: []."""
    cast = _cast()
    db = AsyncMock()
    db.get = AsyncMock(return_value=cast)
    scalars_no_jobs = MagicMock()
    scalars_no_jobs.all.return_value = []
    db.scalars = AsyncMock(return_value=scalars_no_jobs)

    status, data = await _get(f"/casts/{CAST_ID}/insights", db)
    assert status == 200
    assert data == {"jobs": []}
