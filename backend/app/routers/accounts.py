from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_tenant
from ..database import get_db
from ..models import ConnectedAccount
from ..schemas import AccountOut

router = APIRouter()


@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalars(
        select(ConnectedAccount).where(ConnectedAccount.tenant_id == tenant_id)
    )
    return result.all()


@router.post("/accounts/{platform}/connect", response_model=AccountOut)
async def connect_account(
    platform: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Phase-0 stub: marks existing account as connected (no real OAuth yet)."""
    VALID = {"vk", "tg", "ig", "fb", "wa"}
    if platform not in VALID:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    result = await db.scalars(
        select(ConnectedAccount).where(
            ConnectedAccount.tenant_id == tenant_id,
            ConnectedAccount.platform == platform,
        )
    )
    account = result.first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found — run seed_dev.py")

    account.status = "connected"
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_account(
    account_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    account = await db.get(ConnectedAccount, account_id)
    if not account or account.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Account not found")
    account.status = "disconnected"
    await db.commit()
