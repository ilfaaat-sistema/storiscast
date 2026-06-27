import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    owner_uid: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    accounts: Mapped[List["ConnectedAccount"]] = relationship(back_populates="tenant")
    casts: Mapped[List["Cast"]] = relationship(back_populates="tenant")


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    platform: Mapped[str] = mapped_column(String(50))
    handle: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="connected")
    credentials_enc: Mapped[Optional[str]] = mapped_column(Text)
    meta_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="accounts")
    jobs: Mapped[List["Job"]] = relationship(back_populates="account")


class Cast(Base):
    __tablename__ = "casts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    caption: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    tenant: Mapped["Tenant"] = relationship(back_populates="casts")
    media: Mapped[List["CastMedia"]] = relationship(
        back_populates="cast", order_by="CastMedia.position"
    )
    jobs: Mapped[List["Job"]] = relationship(back_populates="cast")


class CastMedia(Base):
    __tablename__ = "cast_media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cast_id: Mapped[str] = mapped_column(String(36), ForeignKey("casts.id"))
    url: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(20))  # photo | video
    position: Mapped[int] = mapped_column(Integer, default=0)

    cast: Mapped["Cast"] = relationship(back_populates="media")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cast_id: Mapped[str] = mapped_column(String(36), ForeignKey("casts.id"))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("connected_accounts.id"))
    platform: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="queued")
    # queued | sending | done | error | manual | scheduled
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[str]] = mapped_column(String(255))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    cast: Mapped["Cast"] = relationship(back_populates="jobs")
    account: Mapped["ConnectedAccount"] = relationship(back_populates="jobs")
    insights: Mapped[List["Insight"]] = relationship(back_populates="job")


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"))
    platform: Mapped[str] = mapped_column(String(50))
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[int] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    job: Mapped["Job"] = relationship(back_populates="insights")
