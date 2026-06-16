from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..auth import get_current_tenant
from ..database import get_db
from ..models import Cast, CastMedia, ConnectedAccount, Job, Insight
from ..schemas import CastCreate, CastOut, InsightOut, JobInsightOut, CastInsightsOut, CastListOut

router = APIRouter()


def _aggregate_insights(jobs: list, all_insights: list) -> list[JobInsightOut]:
    """For each (job_id, metric) keep the snapshot with the latest fetched_at."""
    latest: dict[str, dict[str, tuple]] = {}
    for ins in all_insights:
        bucket = latest.setdefault(ins.job_id, {})
        existing = bucket.get(ins.metric)
        if existing is None or ins.fetched_at > existing[0]:
            bucket[ins.metric] = (ins.fetched_at, ins.value)

    return [
        JobInsightOut(
            platform=job.platform,
            status=job.status,
            metrics={m: v for m, (_, v) in latest.get(job.id, {}).items()},
        )
        for job in jobs
    ]

# Facebook is always added automatically when Instagram is selected
_AUTO_FB_WITH_IG = True


@router.post("/casts", response_model=CastOut, status_code=201)
async def create_cast(
    body: CastCreate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    # Expand targets: ig → also add fb automatically
    targets = list(body.targets)
    if "ig" in targets and "fb" not in targets and _AUTO_FB_WITH_IG:
        targets.append("fb")

    # Find connected accounts for each platform
    result = await db.scalars(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.platform.in_(targets),
        )
    )
    accounts_by_platform = {a.platform: a for a in result.all()}

    missing = [t for t in targets if t not in accounts_by_platform]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"No connected account for platforms: {missing}. Run seed_dev.py.",
        )

    cast = Cast(
        tenant_id=tenant_id,
        caption=body.caption,
        status="queued",
        scheduled_at=body.scheduled_at,
    )
    db.add(cast)
    await db.flush()  # get cast.id

    for i, m in enumerate(body.media):
        db.add(CastMedia(cast_id=cast.id, url=m.url, media_type=m.media_type, position=i))

    for platform in targets:
        account = accounts_by_platform[platform]
        status = "manual" if platform == "wa" else "queued"
        db.add(Job(cast_id=cast.id, account_id=account.id, platform=platform, status=status))

    await db.commit()
    await db.refresh(cast, ["jobs"])
    return cast


@router.get("/casts/{cast_id}", response_model=CastOut)
async def get_cast(
    cast_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Cast)
        .where(
            Cast.id == cast_id,
            Cast.tenant_id == tenant_id,
        )
        .options(selectinload(Cast.jobs))
    )
    cast = result.first()
    if not cast:
        raise HTTPException(status_code=404, detail="Cast not found")
    return cast


@router.get("/casts", response_model=list[CastListOut])
async def list_casts(
    limit: int = 10,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(Cast)
        .where(Cast.tenant_id == tenant_id)
        .options(selectinload(Cast.jobs))
        .order_by(Cast.created_at.desc())
        .limit(min(limit, 50))
    )
    casts = result.all()
    return [
        CastListOut(
            id=c.id,
            caption=c.caption,
            status=c.status,
            created_at=c.created_at,
            platforms=[j.platform for j in c.jobs],
        )
        for c in casts
    ]


@router.get("/casts/{cast_id}/insights", response_model=CastInsightsOut)
async def get_cast_insights(
    cast_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    cast = await db.get(Cast, cast_id)
    if not cast or cast.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Cast not found")

    result = await db.scalars(select(Job).where(Job.cast_id == cast_id))
    jobs = result.all()
    if not jobs:
        return CastInsightsOut(jobs=[])

    job_ids = [j.id for j in jobs]
    ins_result = await db.scalars(
        select(Insight).where(Insight.job_id.in_(job_ids))
    )
    return CastInsightsOut(jobs=_aggregate_insights(list(jobs), list(ins_result.all())))
