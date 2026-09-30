"""Course materials and student assignment submissions.

Revision ID: a3c4d5e6f7b8
Revises: f2b3c4d5e6a7
"""
from alembic import op
import sqlalchemy as sa

revision = "a3c4d5e6f7b8"
down_revision = "f2b3c4d5e6a7"
branch_labels = None
depends_on = None


def common():
    return [sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.add_column("coursework", sa.Column("allow_late_submissions", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("course_materials", *common(),
        sa.Column("subject_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False), sa.Column("link_url", sa.String(2000)),
        sa.Column("published", sa.Boolean(), nullable=False), sa.UniqueConstraint("institution_id", "id"),
        sa.ForeignKeyConstraint(["institution_id", "subject_id"], ["teaching_subjects.institution_id", "teaching_subjects.id"]))
    op.create_table("assignment_submissions", *common(),
        sa.Column("coursework_id", sa.Uuid(), nullable=False), sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False), sa.Column("link_url", sa.String(2000)),
        sa.Column("status", sa.String(12), nullable=False), sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("is_late", sa.Boolean(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("institution_id", "id"), sa.UniqueConstraint("institution_id", "coursework_id", "student_id"),
        sa.ForeignKeyConstraint(["institution_id", "coursework_id"], ["coursework.institution_id", "coursework.id"]),
        sa.ForeignKeyConstraint(["institution_id", "student_id"], ["students.institution_id", "students.id"]),
        sa.CheckConstraint("status IN ('DRAFT', 'SUBMITTED')"), sa.CheckConstraint("version > 0"))
    for table, columns in {"course_materials": ["institution_id", "subject_id"], "assignment_submissions": ["institution_id", "coursework_id", "student_id"]}.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    op.drop_table("assignment_submissions")
    op.drop_table("course_materials")
    op.drop_column("coursework", "allow_late_submissions")
