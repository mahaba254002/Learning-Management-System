"""E-learning: uploaded files, online quizzes, course sections, registration windows and notifications.

Revision ID: s1c2d3e4f5a6
Revises: r0b1c2d3e4f5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 's1c2d3e4f5a6'
down_revision = 'r0b1c2d3e4f5'
branch_labels = None
depends_on = None

OLD_PERMISSIONS = "permission IN ('staff.view', 'staff_attendance.manage', 'students.view', 'fees.manage')"
NEW_PERMISSIONS = "permission IN ('staff.view', 'staff_attendance.manage', 'students.view', 'fees.manage', 'registrations.approve')"
JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def stamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def tenant():
    return sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True)


def upgrade():
    op.create_table('stored_files',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('uploaded_by', sa.Uuid(), nullable=False), sa.Column('purpose', sa.String(12), nullable=False),
                    sa.Column('subject_id', sa.Uuid(), nullable=False, index=True), sa.Column('student_id', sa.Uuid()),
                    sa.Column('filename', sa.String(160), nullable=False), sa.Column('content_type', sa.String(120), nullable=False),
                    sa.Column('size_bytes', sa.Integer(), nullable=False), sa.Column('sha256', sa.String(64), nullable=False),
                    sa.Column('storage_key', sa.String(200), nullable=False), sa.Column('deleted_at', sa.DateTime(timezone=True)),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_stored_files_tenant_id'),
                    sa.UniqueConstraint('storage_key', name='uq_stored_files_key'),
                    sa.ForeignKeyConstraint(['institution_id', 'uploaded_by'], ['users.institution_id', 'users.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.CheckConstraint("purpose IN ('MATERIAL', 'PAPER', 'SUBMISSION')", name='ck_stored_files_purpose'),
                    sa.CheckConstraint('size_bytes > 0 AND size_bytes <= 10485760', name='ck_stored_files_size'),
                    sa.CheckConstraint("(purpose = 'SUBMISSION') = (student_id IS NOT NULL)", name='ck_stored_files_student'))
    op.create_index('ix_stored_files_usage', 'stored_files', ['institution_id', 'deleted_at'])

    op.add_column('course_materials', sa.Column('section', sa.String(120), nullable=False, server_default=''))
    op.add_column('course_materials', sa.Column('file_id', sa.Uuid()))
    op.create_foreign_key('fk_course_materials_file', 'course_materials', 'stored_files', ['institution_id', 'file_id'], ['institution_id', 'id'])

    op.add_column('coursework', sa.Column('delivery', sa.String(10), nullable=False, server_default='STANDARD'))
    op.add_column('coursework', sa.Column('opens_at', sa.DateTime(timezone=True)))
    op.add_column('coursework', sa.Column('section', sa.String(120), nullable=False, server_default=''))
    op.add_column('coursework', sa.Column('paper_file_id', sa.Uuid()))
    op.add_column('coursework', sa.Column('submission_file_types', JSON, nullable=False, server_default='[]'))
    op.create_check_constraint('ck_coursework_delivery', 'coursework', "delivery IN ('STANDARD', 'QUIZ')")
    op.create_foreign_key('fk_coursework_paper_file', 'coursework', 'stored_files', ['institution_id', 'paper_file_id'], ['institution_id', 'id'])

    op.add_column('assignment_submissions', sa.Column('file_id', sa.Uuid()))
    op.create_foreign_key('fk_assignment_submissions_file', 'assignment_submissions', 'stored_files', ['institution_id', 'file_id'], ['institution_id', 'id'])

    op.create_table('quiz_settings',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('coursework_id', sa.Uuid(), nullable=False),
                    sa.Column('time_limit_minutes', sa.Integer()),
                    sa.Column('attempts_allowed', sa.Integer(), nullable=False, server_default='1'),
                    *[sa.Column(name, sa.Boolean(), nullable=False, server_default='false') for name in
                      ('no_going_back', 'shuffle_questions', 'shuffle_options', 'hide_results_until_close', 'log_tab_switches')],
                    sa.UniqueConstraint('institution_id', 'coursework_id', name='uq_quiz_settings_quiz'),
                    sa.ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
                    sa.CheckConstraint('time_limit_minutes IS NULL OR (time_limit_minutes >= 1 AND time_limit_minutes <= 600)', name='ck_quiz_settings_time'),
                    sa.CheckConstraint('attempts_allowed >= 1 AND attempts_allowed <= 10', name='ck_quiz_settings_attempts'))
    op.create_table('quiz_questions',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('coursework_id', sa.Uuid(), nullable=False, index=True), sa.Column('position', sa.Integer(), nullable=False),
                    sa.Column('kind', sa.String(12), nullable=False), sa.Column('prompt', sa.Text(), nullable=False),
                    sa.Column('options', JSON, nullable=False), sa.Column('correct', JSON, nullable=False),
                    sa.Column('points', sa.Numeric(6, 2), nullable=False), sa.Column('time_limit_seconds', sa.Integer()),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_quiz_questions_tenant_id'),
                    sa.ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
                    sa.CheckConstraint("kind IN ('SINGLE', 'MULTIPLE', 'TRUE_FALSE')", name='ck_quiz_questions_kind'),
                    sa.CheckConstraint('points > 0 AND points <= 1000', name='ck_quiz_questions_points'),
                    sa.CheckConstraint('time_limit_seconds IS NULL OR (time_limit_seconds >= 10 AND time_limit_seconds <= 3600)', name='ck_quiz_questions_time'))
    op.create_table('quiz_attempts',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('coursework_id', sa.Uuid(), nullable=False, index=True), sa.Column('student_id', sa.Uuid(), nullable=False, index=True),
                    sa.Column('number', sa.Integer(), nullable=False), sa.Column('status', sa.String(12), nullable=False),
                    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False), sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('submitted_at', sa.DateTime(timezone=True)),
                    sa.Column('auto_submitted', sa.Boolean(), nullable=False, server_default='false'),
                    sa.Column('plan', JSON, nullable=False),
                    sa.Column('sequential', sa.Boolean(), nullable=False, server_default='false'),
                    sa.Column('current_index', sa.Integer(), nullable=False, server_default='0'),
                    sa.Column('current_started_at', sa.DateTime(timezone=True)),
                    sa.Column('score', sa.Numeric(8, 2)), sa.Column('max_score', sa.Numeric(8, 2), nullable=False),
                    sa.Column('tab_switches', sa.Integer(), nullable=False, server_default='0'),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_quiz_attempts_tenant_id'),
                    sa.UniqueConstraint('institution_id', 'coursework_id', 'student_id', 'number', name='uq_quiz_attempts_number'),
                    sa.ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.CheckConstraint("status IN ('IN_PROGRESS', 'SUBMITTED')", name='ck_quiz_attempts_status'),
                    sa.CheckConstraint('number >= 1', name='ck_quiz_attempts_number'))
    op.create_index('uq_quiz_attempts_open', 'quiz_attempts', ['institution_id', 'coursework_id', 'student_id'], unique=True,
                    postgresql_where=sa.text("status = 'IN_PROGRESS'"), sqlite_where=sa.text("status = 'IN_PROGRESS'"))
    op.create_table('quiz_answers',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('attempt_id', sa.Uuid(), nullable=False, index=True), sa.Column('question_id', sa.Uuid(), nullable=False),
                    sa.Column('selected', JSON, nullable=False), sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False),
                    sa.UniqueConstraint('institution_id', 'attempt_id', 'question_id', name='uq_quiz_answers_once'),
                    sa.ForeignKeyConstraint(['institution_id', 'attempt_id'], ['quiz_attempts.institution_id', 'quiz_attempts.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'question_id'], ['quiz_questions.institution_id', 'quiz_questions.id']))
    op.create_table('quiz_extra_attempts',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('coursework_id', sa.Uuid(), nullable=False, index=True), sa.Column('student_id', sa.Uuid(), nullable=False),
                    sa.Column('granted_by', sa.Uuid(), nullable=False), sa.Column('reason', sa.String(300), nullable=False),
                    sa.ForeignKeyConstraint(['institution_id', 'coursework_id'], ['coursework.institution_id', 'coursework.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'granted_by'], ['users.institution_id', 'users.id']))

    op.create_table('registration_windows',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('title', sa.String(120), nullable=False), sa.Column('period_id', sa.Uuid()),
                    sa.Column('opens_at', sa.DateTime(timezone=True), nullable=False), sa.Column('closes_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('min_units', sa.Integer(), nullable=False), sa.Column('max_units', sa.Integer(), nullable=False),
                    sa.Column('min_credits', sa.Numeric(6, 2)), sa.Column('max_credits', sa.Numeric(6, 2)),
                    sa.Column('class_ids', JSON, nullable=False),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_registration_windows_tenant_id'),
                    sa.ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id']),
                    sa.CheckConstraint('closes_at > opens_at', name='ck_registration_windows_dates'),
                    sa.CheckConstraint('min_units >= 0 AND max_units >= min_units AND max_units <= 50', name='ck_registration_windows_units'),
                    sa.CheckConstraint('min_credits IS NULL OR max_credits IS NULL OR max_credits >= min_credits', name='ck_registration_windows_credits'))
    op.add_column('course_registrations', sa.Column('status', sa.String(10), nullable=False, server_default='APPROVED'))
    op.add_column('course_registrations', sa.Column('window_id', sa.Uuid()))
    op.add_column('course_registrations', sa.Column('decided_by', sa.Uuid()))
    op.add_column('course_registrations', sa.Column('decided_at', sa.DateTime(timezone=True)))
    op.add_column('course_registrations', sa.Column('decision_note', sa.String(300), nullable=False, server_default=''))
    op.create_index('ix_course_registrations_window_id', 'course_registrations', ['window_id'])
    op.execute("UPDATE course_registrations SET status = 'DROPPED' WHERE active = false")
    op.create_check_constraint('ck_course_registrations_status', 'course_registrations', "status IN ('APPROVED', 'PENDING', 'REJECTED', 'DROPPED')")
    op.create_foreign_key('fk_course_registrations_window', 'course_registrations', 'registration_windows', ['institution_id', 'window_id'], ['institution_id', 'id'])

    op.drop_constraint('ck_staff_permissions_permission', 'staff_permissions', type_='check')
    op.create_check_constraint('ck_staff_permissions_permission', 'staff_permissions', NEW_PERMISSIONS)

    op.create_table('notifications',
                    sa.Column('id', sa.Uuid(), primary_key=True), tenant(), *stamps(),
                    sa.Column('user_id', sa.Uuid(), nullable=False), sa.Column('ref', sa.String(120), nullable=False),
                    sa.Column('title', sa.String(200), nullable=False), sa.Column('body', sa.String(500), nullable=False),
                    sa.Column('link', sa.String(300), nullable=False), sa.Column('read_at', sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
                    sa.UniqueConstraint('user_id', 'ref', name='uq_notifications_user_ref'))
    op.create_index('ix_notifications_inbox', 'notifications', ['user_id', 'created_at'])


def downgrade():
    op.drop_table('notifications')
    op.execute("DELETE FROM staff_permissions WHERE permission = 'registrations.approve'")
    op.drop_constraint('ck_staff_permissions_permission', 'staff_permissions', type_='check')
    op.create_check_constraint('ck_staff_permissions_permission', 'staff_permissions', OLD_PERMISSIONS)
    op.drop_constraint('fk_course_registrations_window', 'course_registrations', type_='foreignkey')
    op.drop_constraint('ck_course_registrations_status', 'course_registrations', type_='check')
    op.drop_index('ix_course_registrations_window_id', 'course_registrations')
    for name in ('decision_note', 'decided_at', 'decided_by', 'window_id', 'status'):
        op.drop_column('course_registrations', name)
    op.drop_table('registration_windows')
    for table in ('quiz_extra_attempts', 'quiz_answers'):
        op.drop_table(table)
    op.drop_index('uq_quiz_attempts_open', 'quiz_attempts')
    for table in ('quiz_attempts', 'quiz_questions', 'quiz_settings'):
        op.drop_table(table)
    op.drop_constraint('fk_assignment_submissions_file', 'assignment_submissions', type_='foreignkey')
    op.drop_column('assignment_submissions', 'file_id')
    op.drop_constraint('fk_coursework_paper_file', 'coursework', type_='foreignkey')
    op.drop_constraint('ck_coursework_delivery', 'coursework', type_='check')
    for name in ('submission_file_types', 'paper_file_id', 'section', 'opens_at', 'delivery'):
        op.drop_column('coursework', name)
    op.drop_constraint('fk_course_materials_file', 'course_materials', type_='foreignkey')
    op.drop_column('course_materials', 'file_id')
    op.drop_column('course_materials', 'section')
    op.drop_index('ix_stored_files_usage', 'stored_files')
    op.drop_table('stored_files')
