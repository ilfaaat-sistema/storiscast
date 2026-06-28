from fastapi import APIRouter, Header, HTTPException, status
from ..config import settings

router = APIRouter(prefix="/internal", tags=["internal"])


def _check(secret: str):
    if not settings.INTERNAL_SECRET or secret != settings.INTERNAL_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.post("/trigger/publish-worker")
async def trigger_publish_worker(x_internal_secret: str = Header(default="")):
    _check(x_internal_secret)
    from cron.publish_worker import main
    await main()
    return {"ok": True}


@router.post("/trigger/insights-poller")
async def trigger_insights_poller(x_internal_secret: str = Header(default="")):
    _check(x_internal_secret)
    from cron.insights_poller import main
    await main()
    return {"ok": True}
