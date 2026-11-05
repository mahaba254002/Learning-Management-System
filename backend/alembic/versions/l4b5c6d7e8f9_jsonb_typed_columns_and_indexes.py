"""Store settings and snapshots as JSONB, type text ID columns and add indexes.

Revision ID: l4b5c6d7e8f9
Revises: k3a4b5c6d7e8
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'l4b5c6d7e8f9'
down_revision = 'k3a4b5c6d7e8'
branch_labels = None
depends_on = None

JSON_COLUMNS = [
    ('institutions', 'learning_settings', "'{}'"),
    ('institutions', 'module_settings', "'{}'"),
    ('institutions', 'academic_configuration', "'{}'"),
    ('invitations', 'submitted_data', None),
    ('academic_documents', 'snapshot', None),
    ('coursework', 'rubric_labels', "'[]'"),
    ('coursework', 'grading_bands', None),
    ('email_failures', 'context', None),
    ('final_grades', 'result', None),
    ('progression_decisions', 'snapshot', None),
    ('teaching_subjects', 'grading_policy', None),
    ('verification_codes', 'payload', None),
    ('work_drafts', 'data', None),
]

INDEXES = [
    ('ix_academic_classes_institution_year', 'academic_classes', ['institution_id', 'academic_year']),
    ('ix_academic_classes_level_id', 'academic_classes', ['level_id']),
    ('ix_academic_classes_programme_id', 'academic_classes', ['programme_id']),
    ('ix_academic_classes_supervisor_id', 'academic_classes', ['supervisor_id']),
    ('ix_academic_documents_class_id', 'academic_documents', ['class_id']),
    ('ix_audit_events_institution_created', 'audit_events', ['institution_id', 'created_at']),
    ('ix_coursework_period_id', 'coursework', ['period_id']),
    ('ix_progression_decisions_target_class_id', 'progression_decisions', ['target_class_id']),
    ('ix_staff_members_department_id', 'staff_members', ['department_id']),
    ('ix_student_attendance_student_day', 'student_attendance', ['institution_id', 'student_id', 'day']),
    ('ix_student_attendance_subject_id', 'student_attendance', ['subject_id']),
    ('ix_teaching_subjects_catalogue_id', 'teaching_subjects', ['catalogue_id']),
    ('ix_teaching_subjects_period_id', 'teaching_subjects', ['period_id']),
]

PAYMENT_RECORDER_FK = 'fk_subscription_payments_recorded_by_users'


def _convert_json(target):
    for table, column, default in JSON_COLUMNS:
        if default:
            op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT')
        op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE {target} USING {column}::{target}')
        if default:
            op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default}::{target}')


def upgrade():
    bind = op.get_bind()
    # Stop before changing anything if existing values cannot be converted.
    bad_recorders = bind.execute(sa.text(
        "SELECT count(*) FROM subscription_payments p WHERE p.recorded_by !~* "
        "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' "
        "OR NOT EXISTS (SELECT 1 FROM users u WHERE u.id::text = lower(p.recorded_by))")).scalar()
    if bad_recorders:
        raise RuntimeError(f'{bad_recorders} payment records name an unknown recorder; fix them before upgrading.')
    bad_percentages = bind.execute(sa.text(
        "SELECT count(*) FROM course_prerequisites WHERE minimum_percentage IS NOT NULL "
        "AND (minimum_percentage !~ '^[0-9]+(\\.[0-9]+)?$' OR minimum_percentage::numeric > 100)")).scalar()
    if bad_percentages:
        raise RuntimeError(f'{bad_percentages} prerequisite percentages are not numbers from 0 to 100.')

    _convert_json('jsonb')

    op.alter_column('subscription_payments', 'recorded_by', type_=postgresql.UUID(as_uuid=True),
                    existing_type=sa.String(36), postgresql_using='lower(recorded_by)::uuid')
    op.create_foreign_key(PAYMENT_RECORDER_FK, 'subscription_payments', 'users', ['recorded_by'], ['id'])
    op.alter_column('course_prerequisites', 'minimum_percentage', type_=sa.Numeric(7, 4),
                    existing_type=sa.String(12), existing_nullable=True,
                    postgresql_using='minimum_percentage::numeric(7,4)')

    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    # Every step converts back without losing data.
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
    op.alter_column('course_prerequisites', 'minimum_percentage', type_=sa.String(12),
                    existing_type=sa.Numeric(7, 4), existing_nullable=True,
                    postgresql_using='minimum_percentage::text')
    op.drop_constraint(PAYMENT_RECORDER_FK, 'subscription_payments', type_='foreignkey')
    op.alter_column('subscription_payments', 'recorded_by', type_=sa.String(36),
                    existing_type=postgresql.UUID(as_uuid=True), postgresql_using='recorded_by::text')
    _convert_json('json')
