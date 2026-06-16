from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import AsyncSessionLocal
from .models import Tenant, ConnectedAccount
from .config import settings
from .routers import health, media, accounts, casts, auth as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _seed_default_tenant()
    yield


async def _seed_default_tenant() -> None:
    """Create default tenant + stub accounts on first run (idempotent)."""
    async with AsyncSessionLocal() as db:
        tenant = await db.get(Tenant, settings.DEFAULT_TENANT_ID)
        if tenant:
            return

        tenant = Tenant(id=settings.DEFAULT_TENANT_ID, name="Default")
        db.add(tenant)

        stub_accounts = [
            ("vk", "@stub_vk", "подключить в Phase 1"),
            ("tg", "+7 000 000 00 00", "подключить в Phase 2"),
            ("ig", "@stub_ig", "подключить в Phase 3"),
            ("fb", "stub_fb", "прицепом за Instagram"),
            ("wa", "личный номер", "Status · 24 ч"),
        ]
        for platform, handle, _ in stub_accounts:
            db.add(
                ConnectedAccount(
                    tenant_id=settings.DEFAULT_TENANT_ID,
                    platform=platform,
                    handle=handle,
                    status="stub",
                )
            )

        await db.commit()


app = FastAPI(title="Сторискаст API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth_router.router)
app.include_router(media.router)
app.include_router(accounts.router)
app.include_router(casts.router)
