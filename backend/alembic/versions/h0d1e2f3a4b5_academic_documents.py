"""Issued report card and transcript snapshots.

Revision ID: h0d1e2f3a4b5
Revises: g9c0d1e2f3b4
"""
from alembic import op
import sqlalchemy as sa

revision = 'h0d1e2f3a4b5'
down_revision = 'g9c0d1e2f3b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('coursework', sa.Column('period_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_coursework_period', 'coursework', 'academic_periods', ['institution_id','period_id'], ['institution_id','id'])
    op.create_table('academic_documents',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
        sa.Column('student_id', sa.Uuid(), nullable=False),
        sa.Column('class_id', sa.Uuid(), nullable=True),
        sa.Column('kind', sa.String(12), nullable=False),
        sa.Column('status', sa.String(10), nullable=False),
        sa.Column('reference', sa.String(50), nullable=False),
        sa.Column('source_digest', sa.String(64), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('issued_by_name', sa.String(250), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
        sa.ForeignKeyConstraint(['institution_id', 'class_id'], ['academic_classes.institution_id', 'academic_classes.id']),
        sa.UniqueConstraint('institution_id', 'reference'),
        sa.UniqueConstraint('institution_id', 'student_id', 'kind', 'source_digest'),
        sa.CheckConstraint("kind IN ('REPORT_CARD', 'TRANSCRIPT')"),
        sa.CheckConstraint("status IN ('ISSUED', 'REVOKED')"))
    op.create_index('ix_academic_documents_institution_id', 'academic_documents', ['institution_id'])
    op.create_index('ix_academic_documents_student_id', 'academic_documents', ['student_id'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM academic_documents LIMIT 1')).first():
        raise RuntimeError('Issued academic documents exist; refusing to discard their history.')
    if op.get_bind().execute(sa.text('SELECT 1 FROM coursework WHERE period_id IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Assessment period assignments exist; refusing to discard history.')
    op.drop_table('academic_documents')
    op.drop_constraint('fk_coursework_period', 'coursework', type_='foreignkey')
    op.drop_column('coursework', 'period_id')
