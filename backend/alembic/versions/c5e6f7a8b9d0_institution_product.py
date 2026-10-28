"""Flexible student access, institution settings, result release and subscriptions.

Revision ID: c5e6f7a8b9d0
Revises: b4d5e6f7a8c9
"""
from alembic import op
import sqlalchemy as sa

revision = "c5e6f7a8b9d0"
down_revision = "b4d5e6f7a8c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE institution_type ADD VALUE IF NOT EXISTS 'KINDERGARTEN'")
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=True)
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.add_column("users", sa.Column("student_login_method", sa.String(20), nullable=False, server_default="EMAIL"))
    op.add_column("users", sa.Column("student_login_id", sa.String(60), nullable=True))
    op.create_index("ix_users_student_login_id", "users", ["student_login_id"], unique=True)
    op.create_check_constraint("ck_users_login_method", "users", "student_login_method IN ('EMAIL', 'STUDENT_ID')")
    op.create_check_constraint("ck_users_login_identity", "users", "(student_login_method = 'EMAIL' AND email IS NOT NULL) OR (role = 'STUDENT' AND student_login_method = 'STUDENT_ID' AND student_login_id IS NOT NULL)")
    op.create_check_constraint("ck_users_login_id_upper", "users", "student_login_id IS NULL OR student_login_id = upper(student_login_id)")
    op.add_column("institutions", sa.Column("learning_settings", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("coursework", sa.Column("grades_released", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Preserve visibility of results already published before this migration.
    op.execute("UPDATE coursework SET grades_released = published")
    for name, columns, constraints in [
        ("institution_subscriptions", [sa.Column("monthly_fee", sa.Numeric(12, 2), nullable=False), sa.Column("next_due_date", sa.Date()),
            sa.Column("grace_days", sa.Integer(), nullable=False), sa.Column("enforcement_enabled", sa.Boolean(), nullable=False),
            sa.Column("manually_frozen", sa.Boolean(), nullable=False), sa.Column("support_email", sa.String(255), nullable=False)],
            [sa.UniqueConstraint("institution_id"), sa.CheckConstraint("monthly_fee >= 0"), sa.CheckConstraint("grace_days >= 0 AND grace_days <= 90")]),
        ("subscription_payments", [sa.Column("amount", sa.Numeric(12, 2), nullable=False), sa.Column("reference", sa.String(100), nullable=False),
            sa.Column("paid_on", sa.Date(), nullable=False), sa.Column("previous_due_date", sa.Date()), sa.Column("next_due_date", sa.Date(), nullable=False),
            sa.Column("recorded_by", sa.String(36), nullable=False)], [sa.UniqueConstraint("institution_id", "reference"), sa.CheckConstraint("amount > 0")]),
        ("billing_notices", [sa.Column("notice_key", sa.String(100), nullable=False), sa.Column("sent_at", sa.DateTime(timezone=True))], [sa.UniqueConstraint("institution_id", "notice_key")]),
    ]:
        op.create_table(name, sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            *columns, *constraints)
        op.create_index(f"ix_{name}_institution_id", name, ["institution_id"])


def downgrade():
    # Refuse a destructive downgrade if email-less accounts would be lost.
    if op.get_bind().execute(sa.text("SELECT count(*) FROM users WHERE email IS NULL")).scalar():
        raise RuntimeError("Assign valid unique emails to ID-only accounts before downgrading")
    for name in ["billing_notices", "subscription_payments", "institution_subscriptions"]:
        op.drop_table(name)
    op.drop_column("coursework", "grades_released")
    op.drop_column("institutions", "learning_settings")
    for name in ["ck_users_login_id_upper", "ck_users_login_identity", "ck_users_login_method"]:
        op.drop_constraint(name, "users", type_="check")
    op.drop_index("ix_users_student_login_id", "users")
    op.drop_column("users", "student_login_id")
    op.drop_column("users", "student_login_method")
    op.drop_index("uq_users_email_lower", "users")
    op.alter_column("users", "email", existing_type=sa.String(255), nullable=False)
    # PostgreSQL enum values cannot safely be removed; KINDERGARTEN remains.
