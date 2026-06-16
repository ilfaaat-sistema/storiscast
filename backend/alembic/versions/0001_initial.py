"""initial schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("handle", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="connected"),
        sa.Column("credentials_enc", sa.Text, nullable=True),
        sa.Column("meta_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connected_accounts_tenant_platform", "connected_accounts", ["tenant_id", "platform"])

    op.create_table(
        "casts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_casts_tenant_id", "casts", ["tenant_id"])

    op.create_table(
        "cast_media",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cast_id", sa.String(36), sa.ForeignKey("casts.id"), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_cast_media_cast_id", "cast_media", ["cast_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cast_id", sa.String(36), sa.ForeignKey("casts.id"), nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("connected_accounts.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','sending','done','error','manual','scheduled')",
            name="ck_jobs_status",
        ),
    )
    op.create_index("ix_jobs_cast_id", "jobs", ["cast_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("value", sa.Integer, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_insights_job_id", "insights", ["job_id"])


def downgrade() -> None:
    op.drop_table("insights")
    op.drop_table("jobs")
    op.drop_table("cast_media")
    op.drop_table("casts")
    op.drop_table("connected_accounts")
    op.drop_table("tenants")
