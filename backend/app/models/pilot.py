"""Durable sessions and institution academic calendars."""
import uuid
from datetime import date, datetime
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AuthSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = 'auth_sessions'
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    refresh_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remember_me: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class AcademicYear(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_years'
    __table_args__ = (UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'name'),
                      CheckConstraint("status IN ('PLANNED','ACTIVE','CLOSED')"),
                      CheckConstraint('end_date >= start_date'))
    name: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default='PLANNED')


class AcademicPeriod(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_periods'
    __table_args__ = (UniqueConstraint('institution_id', 'id', name='uq_period_tenant_id'), UniqueConstraint('institution_id', 'year_id', 'name'),
                      ForeignKeyConstraint(['institution_id', 'year_id'], ['academic_years.institution_id', 'academic_years.id']),
                      CheckConstraint('end_date >= start_date'))
    year_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(60))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class WorkDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'work_drafts'
    __table_args__ = (UniqueConstraint('actor_id', 'user_id', 'kind', 'resource'),)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    resource: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
