"""Add classes, teaching allocations, students, attendance and coursework.

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5f6
"""
from alembic import op
import sqlalchemy as sa

revision = "f2b3c4d5e6a7"
down_revision = "e1a2b3c4d5f6"
branch_labels = None
depends_on = None


def common():
    return [sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def tenant_fk(column, table):
    return sa.ForeignKeyConstraint(["institution_id", column], [f"{table}.institution_id", f"{table}.id"])


def upgrade():
    op.create_unique_constraint("uq_users_institution_id_id", "users", ["institution_id", "id"])
    op.create_table("academic_classes", *common(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("academic_year", sa.String(30), nullable=False),
        sa.Column("supervisor_id", sa.Uuid(), nullable=True),
        sa.UniqueConstraint("institution_id", "id"),
        sa.UniqueConstraint("institution_id", "name", "academic_year"), tenant_fk("supervisor_id", "users"))
    op.create_table("teaching_subjects", *common(),
        sa.Column("class_id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False), sa.UniqueConstraint("institution_id", "id"),
        sa.UniqueConstraint("institution_id", "class_id", "name"), tenant_fk("class_id", "academic_classes"), tenant_fk("teacher_id", "users"))
    op.create_table("students", *common(),
        sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("admission_number", sa.String(60), nullable=False),
        sa.Column("phone", sa.String(50)), sa.UniqueConstraint("institution_id", "id"),
        sa.UniqueConstraint("institution_id", "admission_number"), sa.UniqueConstraint("user_id"), tenant_fk("user_id", "users"))
    op.create_table("class_enrollments", *common(),
        sa.Column("class_id", sa.Uuid(), nullable=False), sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("institution_id", "class_id", "student_id"), tenant_fk("class_id", "academic_classes"), tenant_fk("student_id", "students"))
    op.create_table("coursework", *common(),
        sa.Column("subject_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("max_score", sa.Numeric(8, 2), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False), sa.UniqueConstraint("institution_id", "id"),
        tenant_fk("subject_id", "teaching_subjects"), sa.CheckConstraint("max_score > 0 AND max_score <= 10000"),
        sa.CheckConstraint("kind IN ('ASSIGNMENT', 'COURSEWORK', 'EXAM')"))
    op.create_table("student_scores", *common(),
        sa.Column("coursework_id", sa.Uuid(), nullable=False), sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Numeric(8, 2), nullable=False), sa.Column("feedback", sa.Text(), nullable=False),
        sa.UniqueConstraint("institution_id", "coursework_id", "student_id"), sa.CheckConstraint("score >= 0"),
        tenant_fk("coursework_id", "coursework"), tenant_fk("student_id", "students"))
    op.create_table("student_attendance", *common(),
        sa.Column("class_id", sa.Uuid(), nullable=False), sa.Column("subject_id", sa.Uuid()),
        sa.Column("scope_key", sa.String(36), nullable=False), sa.Column("day", sa.Date(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False), sa.Column("status", sa.String(10), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.UniqueConstraint("institution_id", "class_id", "scope_key", "day", "student_id"),
        sa.CheckConstraint("status IN ('PRESENT', 'ABSENT', 'LATE', 'EXCUSED')"), tenant_fk("class_id", "academic_classes"),
        tenant_fk("subject_id", "teaching_subjects"), tenant_fk("student_id", "students"))
    for table, columns in {
        "academic_classes": [], "teaching_subjects": ["class_id", "teacher_id"], "students": [],
        "class_enrollments": ["class_id", "student_id"], "coursework": ["subject_id"],
        "student_scores": ["coursework_id", "student_id"], "student_attendance": ["class_id", "student_id"],
    }.items():
        for column in ["institution_id", *columns]:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ["student_attendance", "student_scores", "coursework", "class_enrollments", "students", "teaching_subjects", "academic_classes"]:
        op.drop_table(table)
    op.drop_constraint("uq_users_institution_id_id", "users", type_="unique")
