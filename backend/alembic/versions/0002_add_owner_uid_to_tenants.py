"""add owner_uid to tenants

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("owner_uid", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_tenants_owner_uid", "tenants", ["owner_uid"])


def downgrade() -> None:
    op.drop_constraint("uq_tenants_owner_uid", "tenants", type_="unique")
    op.drop_column("tenants", "owner_uid")
