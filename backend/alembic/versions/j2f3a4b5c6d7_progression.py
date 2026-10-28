"""Prerequisites and individual progression history.
Revision ID: j2f3a4b5c6d7
Revises: i1e2f3a4b5c6
"""
from alembic import op
import sqlalchemy as sa
revision='j2f3a4b5c6d7'
down_revision='i1e2f3a4b5c6'
branch_labels=None
depends_on=None


def upgrade():
    common=lambda:[sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('institution_id',sa.Uuid(),sa.ForeignKey('institutions.id'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False)]
    op.create_table('course_prerequisites',*common(),sa.Column('course_id',sa.Uuid(),nullable=False),sa.Column('required_id',sa.Uuid(),nullable=False),sa.Column('minimum_percentage',sa.String(12)),
        sa.UniqueConstraint('institution_id','course_id','required_id'),sa.CheckConstraint('course_id != required_id'),
        sa.ForeignKeyConstraint(['institution_id','course_id'],['academic_catalogue.institution_id','academic_catalogue.id']),
        sa.ForeignKeyConstraint(['institution_id','required_id'],['academic_catalogue.institution_id','academic_catalogue.id']))
    op.create_table('progression_decisions',*common(),sa.Column('source_class_id',sa.Uuid(),nullable=False),sa.Column('target_class_id',sa.Uuid()),sa.Column('student_id',sa.Uuid(),nullable=False),sa.Column('decision',sa.String(10),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.UniqueConstraint('institution_id','source_class_id','student_id'),sa.CheckConstraint("decision IN ('ADVANCE','REPEAT','COMPLETE')"),
        sa.ForeignKeyConstraint(['institution_id','source_class_id'],['academic_classes.institution_id','academic_classes.id']),
        sa.ForeignKeyConstraint(['institution_id','target_class_id'],['academic_classes.institution_id','academic_classes.id']),
        sa.ForeignKeyConstraint(['institution_id','student_id'],['students.institution_id','students.id']))
    for table,columns in [('course_prerequisites',['institution_id','course_id','required_id']),('progression_decisions',['institution_id','source_class_id','student_id'])]:
        for column in columns:op.create_index('ix_'+table+'_'+column,table,[column])


def downgrade():
    for table in ['course_prerequisites','progression_decisions']:
        if op.get_bind().execute(sa.text('SELECT 1 FROM '+table+' LIMIT 1')).first():raise RuntimeError('Progression data exists; refusing to discard history.')
    op.drop_table('progression_decisions');op.drop_table('course_prerequisites')
