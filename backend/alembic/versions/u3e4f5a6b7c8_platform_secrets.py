"""Platform admins' secret questions, and indexes found missing in the readiness review.

Revision ID: u3e4f5a6b7c8
Revises: t2d3e4f5a6b7
"""
from alembic import op
import sqlalchemy as sa

revision = 'u3e4f5a6b7c8'
down_revision = 't2d3e4f5a6b7'
branch_labels = None
depends_on = None

INDEXES = [
    ('ix_audit_events_created', 'audit_events', ['created_at']),
    ('ix_audit_events_institution_action', 'audit_events', ['institution_id', 'action', 'created_at']),
    ('ix_message_deliveries_student', 'message_deliveries', ['institution_id', 'student_id']),
    ('ix_timetable_entries_subject', 'timetable_entries', ['institution_id', 'subject_id']),
    ('ix_stored_files_student', 'stored_files', ['institution_id', 'student_id']),
    ('ix_stored_files_uploader', 'stored_files', ['institution_id', 'uploaded_by', 'created_at']),
    ('ix_quiz_answers_question', 'quiz_answers', ['institution_id', 'question_id']),
    ('ix_quiz_extra_attempts_student', 'quiz_extra_attempts', ['institution_id', 'student_id']),
]


def upgrade():
    op.create_table('platform_secrets',
                    sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('question', sa.String(200), nullable=False), sa.Column('answer_hash', sa.String(255), nullable=False),
                    sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
                    sa.Column('locked_until', sa.DateTime(timezone=True)))
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in INDEXES:
        op.drop_index(name, table_name=table)
    op.drop_table('platform_secrets')
