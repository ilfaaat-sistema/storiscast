from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt
from jwt.exceptions import InvalidTokenError

from .database import get_db
from .models import Tenant
from .config import settings

_bearer = HTTPBearer()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Verify Supabase JWT and return the caller's tenant_id.

    On first login the tenant is auto-provisioned so no separate
    signup endpoint is needed.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    uid: str = payload.get("sub", "")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing sub claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant = await db.scalar(select(Tenant).where(Tenant.owner_uid == uid))
    if tenant is None:
        email = payload.get("email") or uid
        tenant = Tenant(name=email, owner_uid=uid)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

    return tenant.id
