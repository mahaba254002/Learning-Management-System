"""Teaching allocations are granted by admins, never by a teacher's request body."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class AcademicClass(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "academic_classes"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "name", "academic_year"),
        ForeignKeyConstraint(["institution_id", "supervisor_id"], ["users.institution_id", "users.id"]),
    )
    name: Mapped[str] = mapped_column(String(120))
    academic_year: Mapped[str] = mapped_column(String(30))
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class Subject(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "teaching_subjects"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "class_id", "name"),
        ForeignKeyConstraint(["institution_id", "class_id"], ["academic_classes.institution_id", "academic_classes.id"]),
        ForeignKeyConstraint(["institution_id", "teacher_id"], ["users.institution_id", "users.id"]),
    )
    class_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    teacher_id: Mapped[uuid.UUID] = mapped_column(index=True)


class Student(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("institution_id", "id"),
        UniqueConstraint("institution_id", "admission_number"),
        UniqueConstraint("user_id"),
        ForeignKeyConstraint(["institution_id", "user_id"], ["users.institution_id", "users.id"]),
    )
    user_id: Mapped[uuid.UUID] = mapped_column()
    admission_number: Mapped[str] = mapped_column(String(60))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)


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
        CheckConstraint("max_score > 0 AND max_score <= 10000"),
        CheckConstraint("kind IN ('ASSIGNMENT', 'COURSEWORK', 'EXAM')"),
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="ASSIGNMENT")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_late_submissions: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Score(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "student_scores"
    __table_args__ = (
        UniqueConstraint("institution_id", "coursework_id", "student_id"),
        ForeignKeyConstraint(["institution_id", "coursework_id"], ["coursework.institution_id", "coursework.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        CheckConstraint("score >= 0"),
    )
    coursework_id: Mapped[uuid.UUID] = mapped_column(index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    feedback: Mapped[str] = mapped_column(Text, default="")


class Attendance(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "student_attendance"
    __table_args__ = (
        UniqueConstraint("institution_id", "class_id", "scope_key", "day", "student_id"),
        ForeignKeyConstraint(["institution_id", "class_id"], ["academic_classes.institution_id", "academic_classes.id"]),
        ForeignKeyConstraint(["institution_id", "subject_id"], ["teaching_subjects.institution_id", "teaching_subjects.id"]),
        ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        CheckConstraint("status IN ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED')"),
    )
    class_id: Mapped[uuid.UUID] = mapped_column(index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    # 'class' for the daily class register, otherwise the subject UUID.
    scope_key: Mapped[str] = mapped_column(String(36))
    day: Mapped[date] = mapped_column(Date)
    student_id: Mapped[uuid.UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(String(500), default="")
