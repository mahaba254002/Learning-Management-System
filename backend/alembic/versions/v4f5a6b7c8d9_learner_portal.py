"""Learner portal: last-seen time, recently opened courses, and messages to students.

Revision ID: v4f5a6b7c8d9
Revises: u3e4f5a6b7c8
"""
from alembic import op
import sqlalchemy as sa

revision = 'v4f5a6b7c8d9'
down_revision = 'u3e4f5a6b7c8'
branch_labels = None
depends_on = None


def base():
    return [sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_users_online', 'users', ['institution_id', 'last_seen_at'])

    op.create_table('course_visits', *base(),
                    sa.Column('user_id', sa.Uuid(), nullable=False), sa.Column('subject_id', sa.Uuid(), nullable=False),
                    sa.Column('visited_at', sa.DateTime(timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
                    sa.UniqueConstraint('user_id', 'subject_id', name='uq_course_visits_user_subject'))
    op.create_index('ix_course_visits_recent', 'course_visits', ['institution_id', 'user_id', 'visited_at'])

    op.create_table('student_messages', *base(),
                    sa.Column('sender_id', sa.Uuid(), nullable=False), sa.Column('audience', sa.String(8), nullable=False),
                    sa.Column('class_id', sa.Uuid(), nullable=False), sa.Column('title', sa.String(160), nullable=False),
                    sa.Column('body', sa.Text(), nullable=False),
                    sa.UniqueConstraint('institution_id', 'id'),
                    sa.ForeignKeyConstraint(['institution_id', 'sender_id'], ['users.institution_id', 'users.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
                    sa.CheckConstraint("audience IN ('STUDENT', 'CLASS')", name='ck_student_messages_audience'))
    op.create_index('ix_student_messages_sent', 'student_messages', ['institution_id', 'sender_id', 'created_at'])
    op.create_index('ix_student_messages_recent', 'student_messages', ['institution_id', 'created_at'])
    op.create_index('ix_student_messages_institution_id', 'student_messages', ['institution_id'])

    op.create_table('student_message_recipients', *base(),
                    sa.Column('message_id', sa.Uuid(), nullable=False), sa.Column('user_id', sa.Uuid(), nullable=False),
                    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
                    sa.ForeignKeyConstraint(['institution_id', 'message_id'], ['student_messages.institution_id', 'student_messages.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
                    sa.UniqueConstraint('message_id', 'user_id', name='uq_student_message_recipient'))
    op.create_index('ix_student_message_inbox', 'student_message_recipients', ['institution_id', 'user_id', 'created_at'])
    op.create_index('ix_student_message_recipients_institution_id', 'student_message_recipients', ['institution_id'])
    op.create_index('ix_course_visits_institution_id', 'course_visits', ['institution_id'])


def downgrade():
    op.drop_table('student_message_recipients')
    op.drop_table('student_messages')
    op.drop_table('course_visits')
    op.drop_index('ix_users_online', table_name='users')
    op.drop_column('users', 'last_seen_at')
