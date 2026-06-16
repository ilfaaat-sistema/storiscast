from fastapi import APIRouter, Depends

from ..auth import get_current_tenant
from ..schemas import AuthMeOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthMeOut)
async def auth_me(tenant_id: str = Depends(get_current_tenant)):
    return AuthMeOut(tenant_id=tenant_id)
