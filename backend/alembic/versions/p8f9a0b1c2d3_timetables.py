"""Hand-entered timetables: bell schedule, weekly lessons, teacher availability and one-day changes.

Revision ID: p8f9a0b1c2d3
Revises: o7e8f9a0b1c2
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'p8f9a0b1c2d3'
down_revision = 'o7e8f9a0b1c2'
branch_labels = None
depends_on = None

TABLES = ('lesson_changes', 'teacher_unavailability', 'timetable_entries', 'timetable_slots', 'timetable_terms')


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def tenant():
    return [sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def period_fk():
    return sa.ForeignKeyConstraint(['institution_id', 'period_id'], ['academic_periods.institution_id', 'academic_periods.id'], ondelete='CASCADE')


def upgrade():
    op.create_table('timetable_terms', *tenant(),
                    sa.Column('period_id', sa.Uuid(), nullable=False), sa.Column('weekdays', json_type(), nullable=False),
                    sa.Column('published_at', sa.DateTime(timezone=True)),
                    sa.UniqueConstraint('institution_id', 'period_id', name='uq_timetable_terms_period'), period_fk())
    op.create_table('timetable_slots', *tenant(),
                    sa.Column('period_id', sa.Uuid(), nullable=False), sa.Column('label', sa.String(40), nullable=False),
                    sa.Column('start_time', sa.Time(), nullable=False), sa.Column('end_time', sa.Time(), nullable=False),
                    sa.Column('is_break', sa.Boolean(), nullable=False, server_default='false'), sa.Column('weekdays', json_type(), nullable=False),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_timetable_slots_tenant_id'), period_fk(),
                    sa.CheckConstraint('end_time > start_time', name='ck_timetable_slots_times'))
    op.create_index('ix_timetable_slots_period', 'timetable_slots', ['institution_id', 'period_id', 'start_time'])
    op.create_table('timetable_entries', *tenant(),
                    sa.Column('period_id', sa.Uuid(), nullable=False), sa.Column('slot_id', sa.Uuid(), nullable=False),
                    sa.Column('weekday', sa.SmallInteger(), nullable=False), sa.Column('subject_id', sa.Uuid(), nullable=False),
                    sa.Column('class_id', sa.Uuid(), nullable=False), sa.Column('teacher_id', sa.Uuid(), nullable=False),
                    sa.Column('override_reason', sa.String(300)),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_timetable_entries_tenant_id'),
                    sa.UniqueConstraint('institution_id', 'slot_id', 'weekday', 'subject_id', name='uq_timetable_entries_lesson'),
                    period_fk(),
                    sa.ForeignKeyConstraint(['institution_id', 'slot_id'], ['timetable_slots.institution_id', 'timetable_slots.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'subject_id'], ['teaching_subjects.institution_id', 'teaching_subjects.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'teacher_id'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint('weekday BETWEEN 1 AND 7', name='ck_timetable_entries_weekday'))
    op.create_index('ix_timetable_entries_teacher', 'timetable_entries', ['institution_id', 'period_id', 'teacher_id', 'weekday'])
    op.create_index('ix_timetable_entries_class', 'timetable_entries', ['institution_id', 'period_id', 'class_id', 'weekday'])
    op.create_table('teacher_unavailability', *tenant(),
                    sa.Column('period_id', sa.Uuid(), nullable=False), sa.Column('teacher_id', sa.Uuid(), nullable=False),
                    sa.Column('weekday', sa.SmallInteger(), nullable=False), sa.Column('start_time', sa.Time(), nullable=False),
                    sa.Column('end_time', sa.Time(), nullable=False), sa.Column('reason', sa.String(200), nullable=False, server_default=''),
                    period_fk(), sa.ForeignKeyConstraint(['institution_id', 'teacher_id'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint('weekday BETWEEN 1 AND 7', name='ck_teacher_unavailability_weekday'),
                    sa.CheckConstraint('end_time > start_time', name='ck_teacher_unavailability_times'))
    op.create_index('ix_teacher_unavailability_teacher', 'teacher_unavailability', ['institution_id', 'period_id', 'teacher_id', 'weekday'])
    op.create_table('lesson_changes', *tenant(),
                    sa.Column('entry_id', sa.Uuid(), nullable=False), sa.Column('lesson_date', sa.Date(), nullable=False),
                    sa.Column('kind', sa.String(10), nullable=False), sa.Column('substitute_id', sa.Uuid()),
                    sa.Column('new_date', sa.Date()), sa.Column('new_slot_id', sa.Uuid()),
                    sa.Column('note', sa.String(300), nullable=False, server_default=''), sa.Column('override_reason', sa.String(300)),
                    sa.Column('created_by', sa.Uuid(), nullable=False),
                    sa.UniqueConstraint('institution_id', 'entry_id', 'lesson_date', name='uq_lesson_changes_once'),
                    sa.ForeignKeyConstraint(['institution_id', 'entry_id'], ['timetable_entries.institution_id', 'timetable_entries.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'new_slot_id'], ['timetable_slots.institution_id', 'timetable_slots.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'substitute_id'], ['users.institution_id', 'users.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint("kind IN ('CANCELLED', 'MOVED', 'SUBSTITUTE')", name='ck_lesson_changes_kind'),
                    sa.CheckConstraint("(kind = 'SUBSTITUTE') = (substitute_id IS NOT NULL)", name='ck_lesson_changes_substitute'),
                    sa.CheckConstraint("(kind = 'MOVED') = (new_date IS NOT NULL AND new_slot_id IS NOT NULL)", name='ck_lesson_changes_move'))
    op.create_index('ix_lesson_changes_dates', 'lesson_changes', ['institution_id', 'lesson_date'])
    op.create_index('ix_lesson_changes_new_date', 'lesson_changes', ['institution_id', 'new_date'])


def downgrade():
    bind = op.get_bind()
    for table in TABLES:
        if bind.execute(sa.text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError(f'{table} holds records. Export them before downgrading.')
    for table in TABLES:
        op.drop_table(table)
