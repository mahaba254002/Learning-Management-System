"""Teaching allocations are granted by admins, never by a teacher's request body."""
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Time, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import JSONType, Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicClass(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "academic_classes"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "name", "academic_year"),
        Index("ix_academic_classes_institution_year", "institution_id", "academic_year"),
        ForeignKeyConstraint(["institution_id", "supervisor_id"], ["users.institution_id", "users.id"]),
        ForeignKeyConstraint(['institution_id', 'programme_id'], ['academic_programmes.institution_id', 'academic_programmes.id']),
        ForeignKeyConstraint(['institution_id', 'level_id'], ['academic_levels.institution_id', 'academic_levels.id']),
        ForeignKeyConstraint(['institution_id', 'education_level_id'], ['institution_levels.institution_id', 'institution_levels.id']),
    )
    name: Mapped[str] = mapped_column(String(120))
    # A class is a study level (Grade 7) plus an optional stream (East).
    stream: Mapped[str] = mapped_column(String(60), default='', server_default='')
    education_level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    academic_year: Mapped[str] = mapped_column(String(30))
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    programme_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    level_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    grading_policy: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    __tablename__ = "teaching_subjects"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "class_id", "name"),
        ForeignKeyConstraint(["institution_id", "class_id"], ["academic_classes.institution_id", "academic_classes.id"]),
        ForeignKeyConstraint(["institution_id", "teacher_id"], ["users.institution_id", "users.id"]),
        ForeignKeyConstraint(['institution_id', 'catalogue_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id']),
        CheckConstraint("registration_mode IN ('COHORT', 'INDIVIDUAL')"),
    )
    class_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True)
    catalogue_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    period_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    registration_mode: Mapped[str] = mapped_column(String(12), default='COHORT', server_default='COHORT')


class Student(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "admission_number"),
        UniqueConstraint("user_id"),
        ForeignKeyConstraint(["institution_id", "user_id"], ["users.institution_id", "users.id"]),
        CheckConstraint("status IN ('ACTIVE', 'TRANSFERRED', 'GRADUATED', 'WITHDRAWN')", name='ck_students_status'),
        CheckConstraint("(status = 'ACTIVE') = (left_on IS NULL)", name='ck_students_left_on'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column()
    admission_number: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Leaving keeps every record; the student just drops out of active lists.
    status: Mapped[str] = mapped_column(String(12), default='ACTIVE', server_default='ACTIVE')
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status_note: Mapped[str] = mapped_column(String(300), default='', server_default='')


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "class_enrollments"
    __table_args__ = (
        UniqueConstraint("institution_id", "class_id", "student_id"),
        ForeignKeyConstraint(["institution_id", "class_id"], ["academic_classes.institution_id", "academic_classes.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
    )
    class_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Coursework(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "coursework"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        ForeignKeyConstraint(["institution_id", "subject_id"], ["teaching_subjects.institution_id", "teaching_subjects.id"]),
        ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], name='fk_coursework_period'),
        ForeignKeyConstraint(['institution_id', 'strand_id'], ['curriculum_strands.institution_id', 'curriculum_strands.id'], name='fk_coursework_strand'),
        CheckConstraint("max_score > 0 AND max_score <= 10000"),
        CheckConstraint("kind IN ('ASSIGNMENT', 'COURSEWORK', 'EXAM')"),
        CheckConstraint("assessment_mode IN ('NUMERIC', 'COMPETENCY')"),
    )
    period_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="ASSIGNMENT")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    grades_released: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    assessment_mode: Mapped[str] = mapped_column(String(12), default='NUMERIC', server_default='NUMERIC')
    rubric_labels: Mapped[list] = mapped_column(JSONType, default=list, server_default='[]')
    grading_bands: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    allow_late_submissions: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    strand_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    # The scale whose bands were copied into grading_bands / rubric_labels.
    scale_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('assessment_scales.id'), nullable=True, index=True)


class Score(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "student_scores"
    __table_args__ = (
        UniqueConstraint("institution_id", "coursework_id", "student_id"),
        ForeignKeyConstraint(["institution_id", "coursework_id"], ["coursework.institution_id", "coursework.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        CheckConstraint("score >= 0"),
        CheckConstraint('(score IS NOT NULL AND competency_label IS NULL) OR (score IS NULL AND competency_label IS NOT NULL)'),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    competency_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default="")


class Attendance(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "student_attendance"
    __table_args__ = (
        UniqueConstraint("institution_id", "class_id", "scope_key", "day", "student_id"),
        Index("ix_student_attendance_student_day", "institution_id", "student_id", "day"),
        ForeignKeyConstraint(["institution_id", "class_id"], ["academic_classes.institution_id", "academic_classes.id"]),
        ForeignKeyConstraint(["institution_id", "subject_id"], ["teaching_subjects.institution_id", "teaching_subjects.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        CheckConstraint("status IN ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED')"),
        CheckConstraint("outcome IN ('ATTENDED', 'MISSED', 'EXCUSED')", name='ck_student_attendance_outcome'),
        CheckConstraint("status = 'LATE' OR arrived_at IS NULL", name='ck_student_attendance_arrival'),
        Index("ix_student_attendance_summary", "institution_id", "class_id", "scope_key", "day"),
    )
    class_id: Mapped[uuid.UUID] = mapped_column(index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    # 'class' for the daily class register, otherwise the subject UUID.
    scope_key: Mapped[str] = mapped_column(String(36))
    day: Mapped[date] = mapped_column(Date)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(500), default="")
    # Late arrivals: the arrival time, and the lesson's end when known.
    arrived_at: Mapped[time | None] = mapped_column(Time, nullable=True)
    lesson_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason_accepted: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false')
    # What the record counts as in percentages, fixed when it is saved.
    outcome: Mapped[str] = mapped_column(String(8), default='ATTENDED', server_default='ATTENDED')
