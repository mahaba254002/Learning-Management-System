"""Tenant-scoped academic catalogue, admissions groups and course registrations."""
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Faculties and schools group departments. Only a DEPARTMENT can have a parent."""
    __tablename__ = 'academic_departments'
    __table_args__ = (UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'code'),
        ForeignKeyConstraint(['institution_id', 'parent_id'], ['academic_departments.institution_id', 'academic_departments.id']),
        CheckConstraint("kind IN ('FACULTY','SCHOOL','DEPARTMENT')", name='ck_academic_departments_kind'),
        CheckConstraint("parent_id IS NULL OR kind = 'DEPARTMENT'", name='ck_academic_departments_parent'))
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(12), default='DEPARTMENT', server_default='DEPARTMENT')
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)


class Programme(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_programmes'
    __table_args__ = (UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'code'),
        ForeignKeyConstraint(['institution_id', 'department_id'], ['academic_departments.institution_id', 'academic_departments.id']),
        ForeignKeyConstraint(['institution_id', 'education_level_id'], ['institution_levels.institution_id', 'institution_levels.id']))
    department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    education_level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    award: Mapped[str | None] = mapped_column(String(100), nullable=True)


class StudyLevel(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_levels'
    __table_args__ = (UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'code'),
        ForeignKeyConstraint(['institution_id', 'programme_id'], ['academic_programmes.institution_id', 'academic_programmes.id']),
        ForeignKeyConstraint(['institution_id', 'education_level_id'], ['institution_levels.institution_id', 'institution_levels.id']),
        CheckConstraint('position >= 1 AND position <= 100'))
    programme_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    education_level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(default=1)


class CatalogueUnit(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'academic_catalogue'
    __table_args__ = (UniqueConstraint('institution_id', 'id'), UniqueConstraint('institution_id', 'code'),
        ForeignKeyConstraint(['institution_id', 'programme_id'], ['academic_programmes.institution_id', 'academic_programmes.id']),
        ForeignKeyConstraint(['institution_id', 'level_id'], ['academic_levels.institution_id', 'academic_levels.id']),
        ForeignKeyConstraint(['institution_id', 'education_level_id'], ['institution_levels.institution_id', 'institution_levels.id']),
        CheckConstraint('credits IS NULL OR (credits >= 0 AND credits <= 1000)'))
    programme_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    education_level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(160))
    credits: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)


class CourseRegistration(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'course_registrations'
    __table_args__ = (UniqueConstraint('institution_id', 'subject_id', 'student_id'),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id']),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        ForeignKeyConstraint(['institution_id', 'window_id'], ['registration_windows.institution_id', 'registration_windows.id'], name='fk_course_registrations_window'),
        CheckConstraint("status IN ('APPROVED', 'PENDING', 'REJECTED', 'DROPPED')", name='ck_course_registrations_status'))
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Student choices made in a registration window wait for approval. Access follows `active`.
    status: Mapped[str] = mapped_column(String(10), default='APPROVED', server_default='APPROVED')
    window_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str] = mapped_column(String(300), default='', server_default='')


class CourseCompletion(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = 'course_completions'
    __table_args__ = (UniqueConstraint('institution_id', 'subject_id', 'student_id'),
        ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id']),
        ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        CheckConstraint("outcome IN ('PASSED', 'FAILED', 'EXEMPT')"), CheckConstraint('credits >= 0 AND credits <= 1000'))
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    outcome: Mapped[str] = mapped_column(String(10))
    credits: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    released: Mapped[bool] = mapped_column(Boolean, default=False)
