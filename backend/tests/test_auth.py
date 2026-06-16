"""
Phase 6 — auth dependency tests.
JWT verification and tenant auto-provision/lookup.
No real Supabase/DB calls in CI — all mocked.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import jwt as pyjwt

SECRET = "test-supabase-jwt-secret"
UID = "user-uid-test-123"
TENANT_ID = "tenant-id-test-456"


def _make_token(uid=UID, audience="authenticated", expired=False, secret=SECRET):
    now = datetime.now(timezone.utc)
    exp = now - timedelta(seconds=10) if expired else now + timedelta(hours=1)
    return pyjwt.encode(
        {"sub": uid, "aud": audience, "exp": exp, "email": "test@example.com"},
        secret,
        algorithm="HS256",
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_valid_token_existing_tenant():
    """Valid JWT + existing tenant → returns tenant_id without creating a new one."""
    from app.auth import get_current_tenant

    token = _make_token()
    tenant = MagicMock()
    tenant.id = TENANT_ID
    db = AsyncMock()
    db.add = Mock()  # session.add() is synchronous
    db.scalar = AsyncMock(return_value=tenant)

    with patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = SECRET
        result = await get_current_tenant(_creds(token), db)

    assert result == TENANT_ID
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_valid_token_auto_provisions_tenant():
    """Valid JWT + no existing tenant → auto-create tenant and return its id.

    SQLAlchemy assigns the PK default during flush (not at instantiation),
    so we simulate that via a db.refresh side-effect setting tenant.id.
    """
    from app.auth import get_current_tenant

    token = _make_token()
    db = AsyncMock()
    db.add = Mock()  # session.add() is synchronous
    db.scalar = AsyncMock(return_value=None)

    # Simulate SQLAlchemy flush behaviour: refresh populates the generated id
    async def _set_id(obj, **kw):
        obj.id = "auto-provisioned-tenant-id"

    db.refresh = AsyncMock(side_effect=_set_id)

    with patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = SECRET
        result = await get_current_tenant(_creds(token), db)

    db.add.assert_called_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once()
    assert result == "auto-provisioned-tenant-id"


@pytest.mark.asyncio
async def test_invalid_signature_raises_401():
    """JWT signed with wrong secret → 401 Unauthorized."""
    from app.auth import get_current_tenant

    token = _make_token(secret="wrong-secret")
    db = AsyncMock()

    with patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(_creds(token), db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_raises_401():
    """Expired JWT → 401 Unauthorized."""
    from app.auth import get_current_tenant

    token = _make_token(expired=True)
    db = AsyncMock()

    with patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(_creds(token), db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_audience_raises_401():
    """JWT with wrong audience → 401 Unauthorized."""
    from app.auth import get_current_tenant

    token = _make_token(audience="wrong-audience")
    db = AsyncMock()

    with patch("app.auth.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = SECRET
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(_creds(token), db)

    assert exc_info.value.status_code == 401
