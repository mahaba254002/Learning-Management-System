"""Student status, guardians, fee status, discipline, announcements and the late-arrival attendance rule.

Revision ID: o7e8f9a0b1c2
Revises: n6d7e8f9a0b1
"""
from alembic import op
import sqlalchemy as sa

revision = 'o7e8f9a0b1c2'
down_revision = 'n6d7e8f9a0b1'
branch_labels = None
depends_on = None

OLD_PERMISSIONS = "permission IN ('staff.view', 'staff_attendance.manage', 'students.view')"
NEW_PERMISSIONS = "permission IN ('staff.view', 'staff_attendance.manage', 'students.view', 'fees.manage')"
TABLES = ('announcements', 'discipline_records', 'student_fee_status', 'student_guardians', 'guardians')


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def tenant(name):
    return [sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True), *timestamps()]


def upgrade():
    op.add_column('students', sa.Column('status', sa.String(12), nullable=False, server_default='ACTIVE'))
    op.add_column('students', sa.Column('left_on', sa.Date()))
    op.add_column('students', sa.Column('status_note', sa.String(300), nullable=False, server_default=''))
    op.create_check_constraint('ck_students_status', 'students', "status IN ('ACTIVE', 'TRANSFERRED', 'GRADUATED', 'WITHDRAWN')")
    op.create_check_constraint('ck_students_left_on', 'students', "(status = 'ACTIVE') = (left_on IS NULL)")

    op.add_column('student_attendance', sa.Column('arrived_at', sa.Time()))
    op.add_column('student_attendance', sa.Column('lesson_end', sa.Time()))
    op.add_column('student_attendance', sa.Column('reason_accepted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('student_attendance', sa.Column('outcome', sa.String(8), nullable=False, server_default='ATTENDED'))
    # Existing records have no arrival times, so late stays attended.
    op.execute("UPDATE student_attendance SET outcome = 'MISSED' WHERE status = 'ABSENT'")
    op.execute("UPDATE student_attendance SET outcome = 'EXCUSED' WHERE status = 'EXCUSED'")
    op.create_check_constraint('ck_student_attendance_outcome', 'student_attendance', "outcome IN ('ATTENDED', 'MISSED', 'EXCUSED')")
    op.create_check_constraint('ck_student_attendance_arrival', 'student_attendance', "status = 'LATE' OR arrived_at IS NULL")
    op.create_index('ix_student_attendance_summary', 'student_attendance', ['institution_id', 'class_id', 'scope_key', 'day'])

    op.drop_constraint('ck_staff_permissions_permission', 'staff_permissions', type_='check')
    op.create_check_constraint('ck_staff_permissions_permission', 'staff_permissions', NEW_PERMISSIONS)

    op.create_table('guardians', *tenant('guardians'),
                    sa.Column('full_name', sa.String(160), nullable=False), sa.Column('phone', sa.String(20), nullable=False),
                    sa.Column('email', sa.String(255)), sa.Column('occupation', sa.String(120), nullable=False, server_default=''),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_guardians_tenant_id'),
                    sa.UniqueConstraint('institution_id', 'phone', name='uq_guardians_phone'))
    op.create_table('student_guardians', *tenant('student_guardians'),
                    sa.Column('student_id', sa.Uuid(), nullable=False, index=True), sa.Column('guardian_id', sa.Uuid(), nullable=False),
                    sa.Column('relationship', sa.String(40), nullable=False),
                    sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
                    sa.UniqueConstraint('institution_id', 'student_id', 'guardian_id', name='uq_student_guardians_pair'),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'guardian_id'], ['guardians.institution_id', 'guardians.id'], ondelete='CASCADE'))
    op.create_index('ix_student_guardians_guardian', 'student_guardians', ['institution_id', 'guardian_id'])

    op.create_table('student_fee_status', *tenant('student_fee_status'),
                    sa.Column('student_id', sa.Uuid(), nullable=False, index=True), sa.Column('period_id', sa.Uuid(), nullable=False),
                    sa.Column('status', sa.String(8), nullable=False), sa.Column('balance', sa.Numeric(12, 2), nullable=False),
                    sa.Column('note', sa.String(300), nullable=False, server_default=''), sa.Column('updated_by', sa.Uuid()),
                    sa.UniqueConstraint('institution_id', 'student_id', 'period_id', name='uq_student_fee_status_term'),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'updated_by'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint("status IN ('PAID', 'PARTIAL', 'UNPAID')", name='ck_student_fee_status_status'),
                    sa.CheckConstraint('balance >= 0', name='ck_student_fee_status_balance'),
                    sa.CheckConstraint("status <> 'PAID' OR balance = 0", name='ck_student_fee_status_paid_zero'))
    op.create_index('ix_student_fee_status_period', 'student_fee_status', ['institution_id', 'period_id', 'status'])

    op.create_table('discipline_records', *tenant('discipline_records'),
                    sa.Column('student_id', sa.Uuid(), nullable=False), sa.Column('occurred_on', sa.Date(), nullable=False),
                    sa.Column('category', sa.String(60), nullable=False), sa.Column('description', sa.Text(), nullable=False),
                    sa.Column('action_taken', sa.Text(), nullable=False, server_default=''), sa.Column('recorded_by', sa.Uuid(), nullable=False),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'recorded_by'], ['users.institution_id', 'users.id']))
    op.create_index('ix_discipline_records_student', 'discipline_records', ['institution_id', 'student_id', 'occurred_on'])

    op.create_table('announcements', *tenant('announcements'),
                    sa.Column('title', sa.String(160), nullable=False), sa.Column('body', sa.Text(), nullable=False),
                    sa.Column('audience', sa.String(10), nullable=False), sa.Column('class_id', sa.Uuid()),
                    sa.Column('expires_on', sa.Date()), sa.Column('created_by', sa.Uuid(), nullable=False),
                    sa.ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint("audience IN ('EVERYONE', 'STAFF', 'STUDENTS', 'CLASS')", name='ck_announcements_audience'),
                    sa.CheckConstraint("(audience = 'CLASS') = (class_id IS NOT NULL)", name='ck_announcements_class'))
    op.create_index('ix_announcements_recent', 'announcements', ['institution_id', 'created_at'])


def downgrade():
    bind = op.get_bind()
    for table in TABLES:
        if bind.execute(sa.text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError(f'{table} holds records. Export them before downgrading.')
    if bind.execute(sa.text("SELECT 1 FROM students WHERE status <> 'ACTIVE' LIMIT 1")).first():
        raise RuntimeError('Some students are marked as having left. Return them to active before downgrading.')
    if bind.execute(sa.text("SELECT 1 FROM staff_permissions WHERE permission = 'fees.manage' LIMIT 1")).first():
        raise RuntimeError('Remove the fees permission from staff before downgrading.')
    for table in TABLES:
        op.drop_table(table)
    op.drop_constraint('ck_staff_permissions_permission', 'staff_permissions', type_='check')
    op.create_check_constraint('ck_staff_permissions_permission', 'staff_permissions', OLD_PERMISSIONS)
    op.drop_index('ix_student_attendance_summary', table_name='student_attendance')
    op.drop_constraint('ck_student_attendance_arrival', 'student_attendance', type_='check')
    op.drop_constraint('ck_student_attendance_outcome', 'student_attendance', type_='check')
    for column in ('outcome', 'reason_accepted', 'lesson_end', 'arrived_at'):
        op.drop_column('student_attendance', column)
    op.drop_constraint('ck_students_left_on', 'students', type_='check')
    op.drop_constraint('ck_students_status', 'students', type_='check')
    for column in ('status_note', 'left_on', 'status'):
        op.drop_column('students', column)
