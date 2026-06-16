"""
Phase 5 — Analytics: tests for _aggregate_insights() pure function.

No DB or network calls — inputs are SimpleNamespace objects.

Scenarios:
  - latest snapshot wins when multiple snapshots exist for same metric
  - multiple metrics per job
  - multiple jobs (each gets its own metrics)
  - job with no insights → empty metrics dict
  - empty job list
  - job status and platform are preserved in output
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from app.routers.casts import _aggregate_insights

T0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)


def _job(id: str, platform: str, status: str = "done") -> SimpleNamespace:
    return SimpleNamespace(id=id, platform=platform, status=status)


def _ins(job_id: str, metric: str, value: int, fetched_at: datetime) -> SimpleNamespace:
    return SimpleNamespace(job_id=job_id, metric=metric, value=value, fetched_at=fetched_at)


def test_latest_snapshot_wins():
    job = _job("j1", "vk")
    insights = [
        _ins("j1", "views", 100, T0),
        _ins("j1", "views", 200, T1),  # later → should win
        _ins("j1", "views", 150, T0),  # same time as first → should lose
    ]
    result = _aggregate_insights([job], insights)
    assert result[0].metrics["views"] == 200


def test_multiple_metrics_per_job():
    job = _job("j1", "ig")
    insights = [
        _ins("j1", "impressions", 500, T0),
        _ins("j1", "reach", 300, T0),
        _ins("j1", "replies", 5, T0),
    ]
    result = _aggregate_insights([job], insights)
    assert result[0].metrics == {"impressions": 500, "reach": 300, "replies": 5}


def test_multiple_jobs_isolated():
    job_vk = _job("j1", "vk")
    job_ig = _job("j2", "ig")
    insights = [
        _ins("j1", "views", 100, T0),
        _ins("j2", "impressions", 400, T0),
    ]
    result = _aggregate_insights([job_vk, job_ig], insights)
    by_platform = {r.platform: r for r in result}
    assert by_platform["vk"].metrics == {"views": 100}
    assert by_platform["ig"].metrics == {"impressions": 400}


def test_insight_only_for_other_job_does_not_leak():
    job_a = _job("j1", "vk")
    job_b = _job("j2", "tg")
    insights = [_ins("j2", "views_count", 50, T0)]
    result = _aggregate_insights([job_a, job_b], insights)
    by_id = {r.platform: r for r in result}
    assert by_id["vk"].metrics == {}
    assert by_id["tg"].metrics == {"views_count": 50}


def test_job_with_no_insights_returns_empty_metrics():
    job = _job("j1", "tg")
    result = _aggregate_insights([job], [])
    assert result[0].metrics == {}


def test_empty_job_list():
    result = _aggregate_insights([], [_ins("j1", "views", 100, T0)])
    assert result == []


def test_job_fields_preserved():
    job = _job("j1", "vk", status="error")
    result = _aggregate_insights([job], [])
    assert result[0].platform == "vk"
    assert result[0].status == "error"


def test_metric_updated_across_multiple_snapshots():
    job = _job("j1", "ig")
    insights = [
        _ins("j1", "reach", 100, T0),
        _ins("j1", "reach", 200, T1),
        _ins("j1", "reach", 300, T2),
        _ins("j1", "replies", 10, T1),
        _ins("j1", "replies", 8, T0),  # older — should lose
    ]
    result = _aggregate_insights([job], insights)
    assert result[0].metrics["reach"] == 300
    assert result[0].metrics["replies"] == 10


def test_order_of_jobs_preserved_in_output():
    jobs = [_job("j1", "vk"), _job("j2", "tg"), _job("j3", "ig")]
    result = _aggregate_insights(jobs, [])
    assert [r.platform for r in result] == ["vk", "tg", "ig"]
