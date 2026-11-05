"""Education levels, assessment scales, faculties, strands, one staff profile, staff accounts and co-teaching.

Revision ID: m5c6d7e8f9a0
Revises: l4b5c6d7e8f9
"""
import json
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'm5c6d7e8f9a0'
down_revision = 'l4b5c6d7e8f9'
branch_labels = None
depends_on = None

LEVEL_TABLES = ['academic_programmes', 'academic_levels', 'academic_catalogue', 'academic_classes']

# Copied from app.services.structure so this migration never changes when the app does.
PRESETS = {
    'CBE_4': ('CBE four levels', 'COMPETENCY', [('EE', 'Exceeding expectations', 80, 4), ('ME', 'Meeting expectations', 50, 3),
                                               ('AE', 'Approaching expectations', 30, 2), ('BE', 'Below expectations', 0, 1)]),
    'CBE_8': ('CBE eight levels', 'COMPETENCY', [('EE1', 'Exceeding expectations 1', 90, 8), ('EE2', 'Exceeding expectations 2', 75, 7),
                                                ('ME1', 'Meeting expectations 1', 58, 6), ('ME2', 'Meeting expectations 2', 41, 5),
                                                ('AE1', 'Approaching expectations 1', 31, 4), ('AE2', 'Approaching expectations 2', 21, 3),
                                                ('BE1', 'Below expectations 1', 11, 2), ('BE2', 'Below expectations 2', 0, 1)]),
    'LETTER_A_E': ('Letter grades A–E', 'LETTER', [('A', 'A', 70, None), ('B', 'B', 60, None), ('C', 'C', 50, None), ('D', 'D', 40, None), ('E', 'E', 0, None)]),
    'GPA_4': ('GPA 4.0', 'GPA', [('A', 'A', 70, 4), ('B', 'B', 60, 3), ('C', 'C', 50, 2), ('D', 'D', 40, 1), ('E', 'E', 0, 0)]),
    'GPA_5': ('GPA 5.0', 'GPA', [('A', 'A', 70, 5), ('B', 'B', 60, 4), ('C', 'C', 50, 3), ('D', 'D', 45, 2), ('E', 'E', 40, 1), ('F', 'F', 0, 0)]),
    'TVET_COMPETENCE': ('TVET competent / not yet competent', 'COMPETENCY', [('C', 'Competent', None, None), ('NYC', 'Not yet competent', None, None)]),
    'PERCENT': ('Percentage only', 'PERCENT', []),
}
TYPE_LEVELS = {'KINDERGARTEN': ['ECDE'], 'PRIMARY_SCHOOL': ['LOWER_PRIMARY', 'UPPER_PRIMARY'], 'HIGH_SCHOOL': ['SENIOR_SCHOOL'],
               'COLLEGE': ['COLLEGE'], 'UNIVERSITY': ['UNIVERSITY'], 'TRAINING_INSTITUTION': ['TVET'], 'OTHER': []}


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def tenant_table(name, *columns):
    op.create_table(name, sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False), *timestamps(), *columns)
    op.create_index(f'ix_{name}_institution_id', name, ['institution_id'])


def guard(bind):
    """Stop before changing anything if the data cannot be carried across."""
    allocations = bind.execute(sa.text('SELECT count(*) FROM staff_course_allocations')).scalar()
    if allocations:
        raise RuntimeError(f'{allocations} staff course allocations exist. Move them to offering teachers by hand before upgrading.')
    duplicate = bind.execute(sa.text(
        'SELECT t.user_id FROM teachers t JOIN staff_members s ON s.teacher_user_id = t.user_id '
        'WHERE s.institution_id <> t.institution_id LIMIT 1')).first()
    if duplicate:
        raise RuntimeError('A teacher is linked to a staff record in another institution.')


def upgrade():
    bind = op.get_bind()
    guard(bind)
    now = datetime.now(timezone.utc)

    # Enum values must be committed before any row can use them.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'STAFF'")
        op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'DEACTIVATED'")
        op.execute("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'ARCHIVED'")

    op.add_column('users', sa.Column('temporary_password_expires_at', sa.DateTime(timezone=True), nullable=True))

    # --- Assessment scales ---
    op.create_table('assessment_scales', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=True),
                    sa.Column('code', sa.String(40)), sa.Column('name', sa.String(100), nullable=False),
                    sa.Column('kind', sa.String(12), nullable=False),
                    sa.Column('copied_from_id', sa.Uuid(), sa.ForeignKey('assessment_scales.id')), *timestamps(),
                    sa.CheckConstraint("kind IN ('COMPETENCY', 'LETTER', 'GPA', 'PERCENT')", name='ck_assessment_scales_kind'))
    op.create_index('ix_assessment_scales_institution_id', 'assessment_scales', ['institution_id'])
    op.create_index('uq_assessment_scales_preset_code', 'assessment_scales', ['code'], unique=True,
                    postgresql_where=sa.text('institution_id IS NULL'))
    op.create_table('scale_levels', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('scale_id', sa.Uuid(), sa.ForeignKey('assessment_scales.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('code', sa.String(20), nullable=False), sa.Column('label', sa.String(60), nullable=False),
                    sa.Column('descriptor', sa.String(255), nullable=False),
                    sa.Column('min_percent', sa.Numeric(5, 2)), sa.Column('max_percent', sa.Numeric(5, 2)),
                    sa.Column('points', sa.Numeric(6, 2)), sa.Column('position', sa.Integer(), nullable=False),
                    sa.UniqueConstraint('scale_id', 'code'), sa.UniqueConstraint('scale_id', 'position'),
                    sa.CheckConstraint('min_percent IS NULL OR (min_percent >= 0 AND min_percent <= 100)', name='ck_scale_levels_min'),
                    sa.CheckConstraint('max_percent IS NULL OR (max_percent >= 0 AND max_percent <= 100)', name='ck_scale_levels_max'))
    op.create_index('ix_scale_levels_scale_id', 'scale_levels', ['scale_id'])
    scales = sa.table('assessment_scales', sa.column('id', sa.Uuid()), sa.column('code'), sa.column('name'), sa.column('kind'),
                      sa.column('created_at'), sa.column('updated_at'))
    levels = sa.table('scale_levels', sa.column('id', sa.Uuid()), sa.column('scale_id', sa.Uuid()), sa.column('code'), sa.column('label'),
                      sa.column('descriptor'), sa.column('min_percent'), sa.column('max_percent'), sa.column('points'), sa.column('position'))
    for code, (name, kind, rows) in PRESETS.items():
        scale_id = uuid.uuid4()
        op.bulk_insert(scales, [dict(id=scale_id, code=code, name=name, kind=kind, created_at=now, updated_at=now)])
        upper = 100
        values = []
        for position, (level_code, label, minimum, points) in enumerate(rows, start=1):
            maximum = None
            if minimum is not None:
                maximum, upper = upper, minimum - 0.01
            values.append(dict(id=uuid.uuid4(), scale_id=scale_id, code=level_code, label=label, descriptor='',
                               min_percent=minimum, max_percent=maximum, points=points, position=position))
        if values: op.bulk_insert(levels, values)

    # --- Education levels ---
    tenant_table('institution_levels',
                 sa.Column('level', sa.String(20), nullable=False), sa.Column('structure', sa.String(12), nullable=False),
                 sa.Column('period_kind', sa.String(10), nullable=False),
                 sa.Column('terminology', postgresql.JSONB(), nullable=False, server_default='{}'),
                 sa.Column('scale_id', sa.Uuid(), sa.ForeignKey('assessment_scales.id')),
                 sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
                 sa.UniqueConstraint('institution_id', 'id'), sa.UniqueConstraint('institution_id', 'level'),
                 sa.CheckConstraint("level IN ('ECDE', 'LOWER_PRIMARY', 'UPPER_PRIMARY', 'JUNIOR_SCHOOL', 'SENIOR_SCHOOL', 'COLLEGE', 'TVET', 'UNIVERSITY')", name='ck_institution_levels_level'),
                 sa.CheckConstraint("structure IN ('GROUPED','PROGRAMME')", name='ck_institution_levels_structure'),
                 sa.CheckConstraint("period_kind IN ('TERM','SEMESTER','BLOCK')", name='ck_institution_levels_period'))
    op.create_index('ix_institution_levels_scale_id', 'institution_levels', ['scale_id'])
    institution_levels = sa.table('institution_levels', sa.column('id', sa.Uuid()), sa.column('institution_id', sa.Uuid()),
                                  sa.column('level'), sa.column('structure'), sa.column('period_kind'), sa.column('active'),
                                  sa.column('created_at'), sa.column('updated_at'))
    # Existing institutions get the level their type implies, with no scale, so marking is unchanged.
    single = {}
    for institution_id, kind in bind.execute(sa.text('SELECT id, type::text FROM institutions')).all():
        rows = []
        for level in TYPE_LEVELS.get(kind, []):
            programme = level in {'COLLEGE', 'UNIVERSITY', 'TVET'}
            rows.append(dict(id=uuid.uuid4(), institution_id=institution_id, level=level, active=True, created_at=now, updated_at=now,
                             structure='PROGRAMME' if programme else 'GROUPED',
                             period_kind='SEMESTER' if level in {'COLLEGE', 'UNIVERSITY'} else 'TERM'))
        if rows: op.bulk_insert(institution_levels, rows)
        if len(rows) == 1: single[institution_id] = rows[0]['id']

    for table in LEVEL_TABLES:
        op.add_column(table, sa.Column('education_level_id', sa.Uuid(), nullable=True))
        op.create_foreign_key(f'{table}_institution_id_education_level_id_fkey', table, 'institution_levels',
                              ['institution_id', 'education_level_id'], ['institution_id', 'id'])
        op.create_index(f'ix_{table}_education_level_id', table, ['education_level_id'])
        for institution_id, level_id in single.items():
            bind.execute(sa.text(f'UPDATE {table} SET education_level_id = :level WHERE institution_id = :tenant'),
                         dict(level=level_id, tenant=institution_id))
    op.add_column('academic_classes', sa.Column('stream', sa.String(60), nullable=False, server_default=''))

    # --- Faculties ---
    op.add_column('academic_departments', sa.Column('kind', sa.String(12), nullable=False, server_default='DEPARTMENT'))
    op.add_column('academic_departments', sa.Column('parent_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('academic_departments_institution_id_parent_id_fkey', 'academic_departments', 'academic_departments',
                          ['institution_id', 'parent_id'], ['institution_id', 'id'])
    op.create_index('ix_academic_departments_parent_id', 'academic_departments', ['parent_id'])
    op.create_check_constraint('ck_academic_departments_kind', 'academic_departments', "kind IN ('FACULTY','SCHOOL','DEPARTMENT')")
    op.create_check_constraint('ck_academic_departments_parent', 'academic_departments', "parent_id IS NULL OR kind = 'DEPARTMENT'")

    # --- CBE strands ---
    tenant_table('curriculum_strands',
                 sa.Column('catalogue_id', sa.Uuid(), nullable=False), sa.Column('parent_id', sa.Uuid()),
                 sa.Column('code', sa.String(30), nullable=False), sa.Column('name', sa.String(160), nullable=False),
                 sa.Column('position', sa.Integer(), nullable=False),
                 sa.UniqueConstraint('institution_id', 'id'), sa.UniqueConstraint('institution_id', 'catalogue_id', 'code'),
                 sa.ForeignKeyConstraint(['institution_id', 'catalogue_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
                 sa.ForeignKeyConstraint(['institution_id', 'parent_id'], ['curriculum_strands.institution_id', 'curriculum_strands.id']),
                 sa.CheckConstraint('position >= 1 AND position <= 1000', name='ck_curriculum_strands_position'))
    op.create_index('ix_curriculum_strands_catalogue_id', 'curriculum_strands', ['catalogue_id'])
    op.create_index('ix_curriculum_strands_parent_id', 'curriculum_strands', ['parent_id'])
    op.add_column('coursework', sa.Column('strand_id', sa.Uuid(), nullable=True))
    op.add_column('coursework', sa.Column('scale_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_coursework_strand', 'coursework', 'curriculum_strands', ['institution_id', 'strand_id'], ['institution_id', 'id'])
    op.create_foreign_key('coursework_scale_id_fkey', 'coursework', 'assessment_scales', ['scale_id'], ['id'])
    op.create_index('ix_coursework_strand_id', 'coursework', ['strand_id'])
    op.create_index('ix_coursework_scale_id', 'coursework', ['scale_id'])

    # --- One staff profile ---
    op.alter_column('staff_members', 'teacher_user_id', new_column_name='user_id')
    op.execute('ALTER TABLE staff_members RENAME CONSTRAINT staff_members_institution_id_teacher_user_id_key TO staff_members_institution_id_user_id_key')
    op.execute('ALTER TABLE staff_members RENAME CONSTRAINT staff_members_institution_id_teacher_user_id_fkey TO staff_members_institution_id_user_id_fkey')
    op.drop_constraint('staff_members_check', 'staff_members', type_='check')
    op.add_column('staff_members', sa.Column('gender', sa.String(20)))
    op.add_column('staff_members', sa.Column('date_of_birth', sa.Date()))
    op.add_column('staff_members', sa.Column('qualification', sa.String(255)))
    op.add_column('staff_members', sa.Column('specialization', sa.String(255)))
    op.add_column('staff_members', sa.Column('invitation_id', sa.Uuid(), sa.ForeignKey('invitations.id', name='staff_members_invitation_id_fkey')))
    op.create_check_constraint('ck_staff_members_gender', 'staff_members', "gender IS NULL OR gender IN ('MALE','FEMALE','OTHER','PREFER_NOT_TO_SAY')")
    # Fill details on staff records already linked to a teacher, then create the rest.
    bind.execute(sa.text('''
        UPDATE staff_members s SET gender = t.gender::text, date_of_birth = t.date_of_birth,
               qualification = t.qualification, specialization = t.specialization,
               phone = COALESCE(s.phone, t.phone), invitation_id = t.invited_from
        FROM teachers t WHERE t.user_id = s.user_id AND t.institution_id = s.institution_id'''))
    missing = bind.execute(sa.text('''
        SELECT t.id, t.institution_id, t.user_id, t.gender::text, t.date_of_birth, t.phone, t.qualification, t.specialization,
               t.employment_type::text, t.status::text, t.invited_from, t.created_at, u.first_name, u.last_name, u.email
        FROM teachers t JOIN users u ON u.id = t.user_id
        WHERE NOT EXISTS (SELECT 1 FROM staff_members s WHERE s.user_id = t.user_id AND s.institution_id = t.institution_id)
        ORDER BY t.created_at, t.id''')).all()
    numbers = {}
    for (institution_id, number) in bind.execute(sa.text('SELECT institution_id, staff_number FROM staff_members')).all():
        numbers.setdefault(institution_id, set()).add(number)
    for row in missing:
        taken = numbers.setdefault(row.institution_id, set())
        n = 1
        while f'T{n:04d}' in taken: n += 1
        taken.add(f'T{n:04d}')
        bind.execute(sa.text('''
            INSERT INTO staff_members (id, institution_id, created_at, updated_at, staff_number, first_name, last_name, category,
                job_title, user_id, email, phone, employment_type, status, joined_on, gender, date_of_birth, qualification,
                specialization, invitation_id)
            VALUES (:id, :tenant, :now, :now, :number, :first, :last, 'TEACHING', 'Teacher', :user, :email, :phone, :employment,
                :status, :joined, :gender, :dob, :qualification, :specialization, :invitation)'''),
            dict(id=uuid.uuid4(), tenant=row.institution_id, now=now, number=f'T{n:04d}', first=row.first_name, last=row.last_name,
                 user=row.user_id, email=row.email, phone=row.phone,
                 employment='CONTRACT' if row.employment_type == 'VISITING' else row.employment_type,
                 status={'ACTIVE': 'ACTIVE', 'ON_LEAVE': 'ON_LEAVE'}.get(row.status, 'INACTIVE'),
                 joined=row.created_at.date(), gender=row.gender, dob=row.date_of_birth, qualification=row.qualification,
                 specialization=row.specialization, invitation=row.invited_from))

    # --- Co-teaching ---
    tenant_table('offering_teachers',
                 sa.Column('subject_id', sa.Uuid(), nullable=False), sa.Column('user_id', sa.Uuid(), nullable=False),
                 sa.Column('role', sa.String(10), nullable=False), sa.Column('group_name', sa.String(100), nullable=False, server_default=''),
                 sa.Column('weekly_hours', sa.Numeric(5, 2)),
                 sa.UniqueConstraint('institution_id', 'subject_id', 'user_id', 'group_name'),
                 sa.ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
                 sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id']),
                 sa.CheckConstraint("role IN ('LEAD','ASSISTANT')", name='ck_offering_teachers_role'),
                 sa.CheckConstraint('weekly_hours IS NULL OR (weekly_hours > 0 AND weekly_hours <= 168)', name='ck_offering_teachers_hours'))
    op.create_index('ix_offering_teachers_subject_id', 'offering_teachers', ['subject_id'])
    op.create_index('ix_offering_teachers_institution_user', 'offering_teachers', ['institution_id', 'user_id'])
    op.create_index('uq_offering_teachers_one_lead', 'offering_teachers', ['subject_id'], unique=True, postgresql_where=sa.text("role = 'LEAD'"))
    for subject_id, institution_id, teacher_id in bind.execute(sa.text('SELECT id, institution_id, teacher_id FROM teaching_subjects')).all():
        bind.execute(sa.text('''INSERT INTO offering_teachers (id, institution_id, created_at, updated_at, subject_id, user_id, role, group_name)
                                VALUES (:id, :tenant, :now, :now, :subject, :user, 'LEAD', '')'''),
                     dict(id=uuid.uuid4(), tenant=institution_id, now=now, subject=subject_id, user=teacher_id))
    op.drop_table('staff_course_allocations')

    # --- Staff access ---
    op.create_table('staff_permissions',
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
                    sa.Column('user_id', sa.Uuid(), nullable=False), sa.Column('permission', sa.String(40), nullable=False),
                    sa.Column('granted_by', sa.Uuid(), sa.ForeignKey('users.id')),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('user_id', 'permission'),
                    sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'),
                    sa.CheckConstraint("permission IN ('staff.view', 'staff_attendance.manage', 'students.view')", name='ck_staff_permissions_permission'))
    op.create_index('ix_staff_permissions_institution_id', 'staff_permissions', ['institution_id'])
    op.create_table('password_setup_tokens', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
                    sa.Column('token_digest', sa.String(64), nullable=False, unique=True),
                    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('used_at', sa.DateTime(timezone=True)),
                    sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id')),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_password_setup_tokens_user_id', 'password_setup_tokens', ['user_id'])


def downgrade():
    bind = op.get_bind()
    # The old code has no notion of these, so refuse rather than lose them silently.
    if bind.execute(sa.text("SELECT 1 FROM users WHERE role::text = 'STAFF' OR status::text IN ('DEACTIVATED','ARCHIVED') LIMIT 1")).first():
        raise RuntimeError('Staff accounts or closed accounts exist. Reactivate or remove them before downgrading.')
    if bind.execute(sa.text("SELECT 1 FROM offering_teachers WHERE role = 'ASSISTANT' LIMIT 1")).first():
        raise RuntimeError('Co-teachers exist. Remove them before downgrading; the old version allows one teacher per offering.')
    if bind.execute(sa.text("SELECT 1 FROM staff_members WHERE user_id IS NOT NULL AND category <> 'TEACHING' LIMIT 1")).first():
        raise RuntimeError('Non-teaching staff are linked to accounts. Unlink them before downgrading.')
    # Teachers added after the upgrade need a teachers row for the old code.
    now = datetime.now(timezone.utc)
    for row in bind.execute(sa.text('''
            SELECT s.institution_id, s.user_id, s.gender, s.date_of_birth, s.phone, s.qualification, s.specialization,
                   s.employment_type, s.status, s.invitation_id
            FROM staff_members s JOIN users u ON u.id = s.user_id
            WHERE u.role::text = 'TEACHER' AND NOT EXISTS (SELECT 1 FROM teachers t WHERE t.user_id = s.user_id)''')).all():
        bind.execute(sa.text('''INSERT INTO teachers (id, institution_id, created_at, updated_at, user_id, gender, date_of_birth, phone,
                                    qualification, specialization, employment_type, status, invited_from)
                                VALUES (:id, :tenant, :now, :now, :user, CAST(:gender AS gender), :dob, :phone, :qualification,
                                    :specialization, CAST(:employment AS employment_type), CAST(:status AS teacher_status), :invitation)'''),
                     dict(id=uuid.uuid4(), tenant=row.institution_id, now=now, user=row.user_id, gender=row.gender or 'PREFER_NOT_TO_SAY',
                          dob=row.date_of_birth or datetime(1900, 1, 1).date(), phone=row.phone, qualification=row.qualification or 'Not recorded',
                          specialization=row.specialization, employment=row.employment_type if row.employment_type != 'VOLUNTEER' else 'CONTRACT',
                          status={'ACTIVE': 'ACTIVE', 'ON_LEAVE': 'ON_LEAVE'}.get(row.status, 'TERMINATED'), invitation=row.invitation_id))

    op.drop_index('ix_password_setup_tokens_user_id', table_name='password_setup_tokens')
    op.drop_table('password_setup_tokens')
    op.drop_index('ix_staff_permissions_institution_id', table_name='staff_permissions')
    op.drop_table('staff_permissions')

    op.create_table('staff_course_allocations', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False), *timestamps(),
                    sa.Column('staff_id', sa.Uuid(), nullable=False), sa.Column('course_id', sa.Uuid(), nullable=False),
                    sa.Column('period', sa.String(100), nullable=False), sa.Column('group_name', sa.String(100), nullable=False),
                    sa.Column('weekly_hours', sa.Numeric(5, 2), nullable=False), sa.Column('active', sa.Boolean(), nullable=False),
                    sa.UniqueConstraint('institution_id', 'staff_id', 'course_id', 'period', 'group_name'),
                    sa.ForeignKeyConstraint(['institution_id', 'staff_id'], ['staff_members.institution_id', 'staff_members.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'course_id'], ['academic_catalogue.institution_id', 'academic_catalogue.id']),
                    sa.CheckConstraint('weekly_hours > 0 AND weekly_hours <= 168'))
    for column in ['institution_id', 'staff_id', 'course_id']:
        op.create_index(f'ix_staff_course_allocations_{column}', 'staff_course_allocations', [column])
    op.drop_index('uq_offering_teachers_one_lead', table_name='offering_teachers')
    op.drop_index('ix_offering_teachers_institution_user', table_name='offering_teachers')
    op.drop_index('ix_offering_teachers_subject_id', table_name='offering_teachers')
    op.drop_index('ix_offering_teachers_institution_id', table_name='offering_teachers')
    op.drop_table('offering_teachers')

    op.drop_constraint('ck_staff_members_gender', 'staff_members', type_='check')
    op.drop_constraint('staff_members_invitation_id_fkey', 'staff_members', type_='foreignkey')
    for column in ['invitation_id', 'specialization', 'qualification', 'date_of_birth', 'gender']:
        op.drop_column('staff_members', column)
    op.execute('ALTER TABLE staff_members RENAME CONSTRAINT staff_members_institution_id_user_id_key TO staff_members_institution_id_teacher_user_id_key')
    op.execute('ALTER TABLE staff_members RENAME CONSTRAINT staff_members_institution_id_user_id_fkey TO staff_members_institution_id_teacher_user_id_fkey')
    op.alter_column('staff_members', 'user_id', new_column_name='teacher_user_id')
    op.create_check_constraint('staff_members_check', 'staff_members', "category = 'TEACHING' OR teacher_user_id IS NULL")

    op.drop_index('ix_coursework_scale_id', table_name='coursework')
    op.drop_index('ix_coursework_strand_id', table_name='coursework')
    op.drop_constraint('coursework_scale_id_fkey', 'coursework', type_='foreignkey')
    op.drop_constraint('fk_coursework_strand', 'coursework', type_='foreignkey')
    op.drop_column('coursework', 'scale_id')
    op.drop_column('coursework', 'strand_id')
    op.drop_index('ix_curriculum_strands_parent_id', table_name='curriculum_strands')
    op.drop_index('ix_curriculum_strands_catalogue_id', table_name='curriculum_strands')
    op.drop_index('ix_curriculum_strands_institution_id', table_name='curriculum_strands')
    op.drop_table('curriculum_strands')

    op.drop_constraint('ck_academic_departments_parent', 'academic_departments', type_='check')
    op.drop_constraint('ck_academic_departments_kind', 'academic_departments', type_='check')
    op.drop_index('ix_academic_departments_parent_id', table_name='academic_departments')
    op.drop_constraint('academic_departments_institution_id_parent_id_fkey', 'academic_departments', type_='foreignkey')
    op.drop_column('academic_departments', 'parent_id')
    op.drop_column('academic_departments', 'kind')

    op.drop_column('academic_classes', 'stream')
    for table in reversed(LEVEL_TABLES):
        op.drop_index(f'ix_{table}_education_level_id', table_name=table)
        op.drop_constraint(f'{table}_institution_id_education_level_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'education_level_id')
    op.drop_index('ix_institution_levels_scale_id', table_name='institution_levels')
    op.drop_index('ix_institution_levels_institution_id', table_name='institution_levels')
    op.drop_table('institution_levels')
    op.drop_index('ix_scale_levels_scale_id', table_name='scale_levels')
    op.drop_table('scale_levels')
    op.drop_index('uq_assessment_scales_preset_code', table_name='assessment_scales')
    op.drop_index('ix_assessment_scales_institution_id', table_name='assessment_scales')
    op.drop_table('assessment_scales')
    op.drop_column('users', 'temporary_password_expires_at')
    # Postgres cannot remove enum values; STAFF, DEACTIVATED and ARCHIVED stay defined but unused.
