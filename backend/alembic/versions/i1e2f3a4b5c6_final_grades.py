"""Pinned numeric grading policies and approved final results.
Revision ID: i1e2f3a4b5c6
Revises: h0d1e2f3a4b5
"""
from alembic import op
import sqlalchemy as sa
revision='i1e2f3a4b5c6'
down_revision='h0d1e2f3a4b5'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('teaching_subjects',sa.Column('grading_policy',sa.JSON(),nullable=True))
    op.create_table('final_grades',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id'),nullable=False),
        sa.Column('subject_id',sa.Uuid(),nullable=False),sa.Column('student_id',sa.Uuid(),nullable=False),
        sa.Column('scope',sa.String(36),nullable=False),sa.Column('source_digest',sa.String(64),nullable=False),
        sa.Column('result',sa.JSON(),nullable=False),sa.Column('released',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['institution_id','subject_id'],['teaching_subjects.institution_id','teaching_subjects.id']),
        sa.ForeignKeyConstraint(['institution_id','student_id'],['students.institution_id','students.id']),
        sa.UniqueConstraint('institution_id','subject_id','student_id','scope'))
    for name in ['institution_id','subject_id','student_id']:op.create_index('ix_final_grades_'+name,'final_grades',[name])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM final_grades LIMIT 1')).first():raise RuntimeError('Final grades exist; refusing to discard academic history.')
    op.drop_table('final_grades')
    op.drop_column('teaching_subjects','grading_policy')
