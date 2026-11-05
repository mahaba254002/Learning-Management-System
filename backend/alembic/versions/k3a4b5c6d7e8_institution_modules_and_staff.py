"""Institution modules and independent staff management.

Revision ID: k3a4b5c6d7e8
Revises: j2f3a4b5c6d7
"""
from alembic import op
import sqlalchemy as sa

revision = 'k3a4b5c6d7e8'
down_revision = 'j2f3a4b5c6d7'
branch_labels = None
depends_on = None


def common():
    return [sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.add_column('institutions', sa.Column('module_settings', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('users', sa.Column('login_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('staff_members', *common(),
        sa.Column('staff_number', sa.String(40), nullable=False),
        sa.Column('first_name', sa.String(100), nullable=False), sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('category', sa.String(15), nullable=False), sa.Column('job_title', sa.String(120), nullable=False),
        sa.Column('department_id', sa.Uuid()), sa.Column('teacher_user_id', sa.Uuid()),
        sa.Column('email', sa.String(255)), sa.Column('phone', sa.String(50)),
        sa.Column('employment_type', sa.String(15), nullable=False), sa.Column('status', sa.String(10), nullable=False),
        sa.Column('joined_on', sa.Date()),
        sa.UniqueConstraint('institution_id', 'id'), sa.UniqueConstraint('institution_id', 'staff_number'),
        sa.UniqueConstraint('institution_id', 'teacher_user_id'),
        sa.ForeignKeyConstraint(['institution_id', 'department_id'], ['academic_departments.institution_id', 'academic_departments.id']),
        sa.ForeignKeyConstraint(['institution_id', 'teacher_user_id'], ['users.institution_id', 'users.id']),
        sa.CheckConstraint("category IN ('TEACHING','NON_TEACHING')"),
        sa.CheckConstraint("status IN ('ACTIVE','ON_LEAVE','INACTIVE')"),
        sa.CheckConstraint("employment_type IN ('FULL_TIME','PART_TIME','CONTRACT','VOLUNTEER')"),
        sa.CheckConstraint("category = 'TEACHING' OR teacher_user_id IS NULL"))
    op.create_table('staff_course_allocations', *common(),
        sa.Column('staff_id', sa.Uuid(), nullable=False), sa.Column('course_id', sa.Uuid(), nullable=False),
        sa.Column('period', sa.String(100), nullable=False), sa.Column('group_name', sa.String(100), nullable=False),
        sa.Column('weekly_hours', sa.Numeric(5, 2), nullable=False), sa.Column('active', sa.Boolean(), nullable=False),
        sa.UniqueConstraint('institution_id', 'staff_id', 'course_id', 'period', 'group_name'),
        sa.ForeignKeyConstraint(['institution_id', 'staff_id'], ['staff_members.institution_id', 'staff_members.id']),
        sa.ForeignKeyConstraint(['institution_id', 'course_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
        sa.CheckConstraint('weekly_hours > 0 AND weekly_hours <= 168'))
    op.create_table('staff_attendance', *common(),
        sa.Column('staff_id', sa.Uuid(), nullable=False), sa.Column('day', sa.Date(), nullable=False),
        sa.Column('status', sa.String(10), nullable=False), sa.Column('note', sa.String(500), nullable=False),
        sa.UniqueConstraint('institution_id', 'staff_id', 'day'),
        sa.ForeignKeyConstraint(['institution_id', 'staff_id'], ['staff_members.institution_id', 'staff_members.id']),
        sa.CheckConstraint("status IN ('PRESENT','ABSENT','LATE','LEAVE','OFF_DUTY')"))
    for table, columns in [('staff_members', ['institution_id']),
            ('staff_course_allocations', ['institution_id', 'staff_id', 'course_id']),
            ('staff_attendance', ['institution_id', 'staff_id', 'day'])]:
        for column in columns: op.create_index(f'ix_{table}_{column}', table, [column])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM users WHERE login_enabled = false LIMIT 1')).first():
        raise RuntimeError('Login-disabled records exist; refusing to discard access controls.')
    for table in ['staff_attendance', 'staff_course_allocations', 'staff_members']:
        if op.get_bind().execute(sa.text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError('Staff management records exist; refusing to discard history.')
    if op.get_bind().execute(sa.text("SELECT 1 FROM institutions WHERE CAST(module_settings AS TEXT) != '{}' LIMIT 1")).first():
        raise RuntimeError('Institution modules are configured; refusing to discard access settings.')
    op.drop_table('staff_attendance')
    op.drop_table('staff_course_allocations')
    op.drop_table('staff_members')
    op.drop_column('institutions', 'module_settings')
    op.drop_column('users', 'login_enabled')
