"""
Dev seed: creates default tenant + stub connected accounts.
Run from backend/: python -m scripts.seed_dev
The app auto-seeds on first startup — this script is for manual reset.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal
from app.models import ConnectedAccount, Tenant
from app.config import settings


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.get(Tenant, settings.DEFAULT_TENANT_ID)
        if existing:
            print(f"Tenant {settings.DEFAULT_TENANT_ID} already exists — skipping.")
            return

        tenant = Tenant(id=settings.DEFAULT_TENANT_ID, name="Default")
        db.add(tenant)

        stubs = [
            ("vk", "@stub_vk"),
            ("tg", "+7 000 000 00 00"),
            ("ig", "@stub_ig"),
            ("fb", "stub_fb"),
            ("wa", "личный номер"),
        ]
        for platform, handle in stubs:
            db.add(
                ConnectedAccount(
                    tenant_id=settings.DEFAULT_TENANT_ID,
                    platform=platform,
                    handle=handle,
                    status="stub",
                )
            )

        await db.commit()
        print(f"Seeded tenant {settings.DEFAULT_TENANT_ID} with {len(stubs)} stub accounts.")


if __name__ == "__main__":
    asyncio.run(main())
