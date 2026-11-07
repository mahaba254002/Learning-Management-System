"""Education levels, assessment scales, strands, co-teaching and staff access.

Levels and scales are chosen per institution at onboarding. Presets in
assessment_scales have no institution; custom scales belong to one."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric,
                        PrimaryKeyConstraint, String, UniqueConstraint, text)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

EDUCATION_LEVELS = ('ECDE', 'LOWER_PRIMARY', 'UPPER_PRIMARY', 'JUNIOR_SCHOOL', 'SENIOR_SCHOOL', 'COLLEGE', 'TVET', 'UNIVERSITY')
SCHOOL_LEVELS = frozenset(EDUCATION_LEVELS[:5])
SCALE_KINDS = ('COMPETENCY', 'LETTER', 'GPA', 'PERCENT')


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AssessmentScale(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = 'assessment_scales'
    __table_args__ = (
        CheckConstraint(_in('kind', SCALE_KINDS), name='ck_assessment_scales_kind'),
        Index('uq_assessment_scales_preset_code', 'code', unique=True,
              postgresql_where=text('institution_id IS NULL'), sqlite_where=text('institution_id IS NULL')),
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('institutions.id'), nullable=True, index=True)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(12))
    copied_from_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('assessment_scales.id'), nullable=True)


class ScaleLevel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = 'scale_levels'
    __table_args__ = (
        UniqueConstraint('scale_id', 'code'), UniqueConstraint('scale_id', 'position'),
        CheckConstraint('min_percent IS NULL OR (min_percent >= 0 AND min_percent <= 100)', name='ck_scale_levels_min'),
        CheckConstraint('max_percent IS NULL OR (max_percent >= 0 AND max_percent <= 100)', name='ck_scale_levels_max'),
    )
    scale_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('assessment_scales.id', ondelete='CASCADE'), index=True)
    code: Mapped[str] = mapped_column(String(20))
    label: Mapped[str] = mapped_column(String(60))
    descriptor: Mapped[str] = mapped_column(String(255), default='')
    min_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    points: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    position: Mapped[int] = mapped_column()


class InstitutionLevel(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'institution_levels'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'level'),
        CheckConstraint(_in('level', EDUCATION_LEVELS), name='ck_institution_levels_level'),
        CheckConstraint("structure IN ('GROUPED','PROGRAMME')", name='ck_institution_levels_structure'),
        CheckConstraint("period_kind IN ('TERM','SEMESTER','BLOCK')", name='ck_institution_levels_period'),
    )
    level: Mapped[str] = mapped_column(String(20))
    structure: Mapped[str] = mapped_column(String(12), default='GROUPED')
    period_kind: Mapped[str] = mapped_column(String(10), default='TERM')
    terminology: Mapped[dict] = mapped_column(JSONType, default=dict, server_default='{}')
    scale_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('assessment_scales.id'), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default='true')


class CurriculumStrand(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """CBE strands and sub-strands of a learning area (catalogue unit). Two levels deep."""
    __tablename__ = 'curriculum_strands'
    __table_args__ = (
        UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'catalogue_id', 'code'),
        ForeignKeyConstraint(['institution_id', 'catalogue_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
        ForeignKeyConstraint(['institution_id', 'parent_id'], ['curriculum_strands.institution_id', 'curriculum_strands.id']),
        CheckConstraint('position >= 1 AND position <= 1000', name='ck_curriculum_strands_position'),
    )
    catalogue_id: Mapped[uuid.UUID] = mapped_column(index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    position: Mapped[int] = mapped_column(default=1)


class OfferingTeacher(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Who teaches an offering. teaching_subjects.teacher_id mirrors the LEAD row."""
    __tablename__ = 'offering_teachers'
    __table_args__ = (
        UniqueConstraint('institution_id', 'subject_id', 'user_id', 'group_name'),
        Index('ix_offering_teachers_institution_user', 'institution_id', 'user_id'),
        Index('uq_offering_teachers_one_lead', 'subject_id', unique=True,
              postgresql_where=text("role = 'LEAD'"), sqlite_where=text("role = 'LEAD'")),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id']),
        CheckConstraint("role IN ('LEAD','ASSISTANT')", name='ck_offering_teachers_role'),
        CheckConstraint('weekly_hours IS NULL OR (weekly_hours > 0 AND weekly_hours <= 168)', name='ck_offering_teachers_hours'),
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    user_id: Mapped[uuid.UUID] = mapped_column()
    role: Mapped[str] = mapped_column(String(10), default='ASSISTANT')
    group_name: Mapped[str] = mapped_column(String(100), default='', server_default='')
    weekly_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)


STAFF_PERMISSIONS = {
    'staff.view': 'View the staff directory',
    'staff_attendance.manage': 'Take and correct staff attendance',
    'students.view': 'View student records',
    'fees.manage': 'View and update student fee status',
    'registrations.approve': 'Approve course registration choices made by students',
}


class StaffPermission(TenantMixin, Base):
    __tablename__ = 'staff_permissions'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'permission'),
        ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
        CheckConstraint(_in('permission', tuple(STAFF_PERMISSIONS)), name='ck_staff_permissions_permission'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True))
    permission: Mapped[str] = mapped_column(String(40))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PasswordSetupToken(UUIDPrimaryKeyMixin, Base):
    """Single-use link for a new account to choose its first password. Only a digest is stored."""
    __tablename__ = 'password_setup_tokens'
    user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
