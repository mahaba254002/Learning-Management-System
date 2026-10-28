"""Revocable sessions, drafts and academic calendars.

Revision ID: e7a8b9c0d1f2
Revises: d6f7a8b9c0e1
"""
from alembic import op
import sqlalchemy as sa

revision = 'e7a8b9c0d1f2'
down_revision = 'd6f7a8b9c0e1'
branch_labels = depends_on = None


def upgrade():
    op.create_table('auth_sessions', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('refresh_digest', sa.String(64), nullable=False), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('remember_me', sa.Boolean(), nullable=False), sa.Column('revoked', sa.Boolean(), nullable=False))
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_table('work_drafts', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('resource', sa.String(100), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False), sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('actor_id', 'user_id', 'kind', 'resource'))
    for key in ['actor_id', 'user_id']: op.create_index('ix_work_drafts_' + key, 'work_drafts', [key])
    op.create_table('academic_years', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
        sa.Column('name', sa.String(30), nullable=False), sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False), sa.Column('status', sa.String(10), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('institution_id', 'id'), sa.UniqueConstraint('institution_id', 'name'),
        sa.CheckConstraint("status IN ('PLANNED','ACTIVE','CLOSED')"), sa.CheckConstraint('end_date >= start_date'))
    op.create_index('ix_academic_years_institution_id', 'academic_years', ['institution_id'])
    op.create_table('academic_periods', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False),
        sa.Column('year_id', sa.Uuid(), nullable=False), sa.Column('name', sa.String(60), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('institution_id', 'year_id', 'name'), sa.CheckConstraint('end_date >= start_date'),
        sa.ForeignKeyConstraint(['institution_id', 'year_id'], ['academic_years.institution_id', 'academic_years.id']))
    op.create_index('ix_academic_periods_institution_id', 'academic_periods', ['institution_id'])
    op.create_index('ix_academic_periods_year_id', 'academic_periods', ['year_id'])


def downgrade():
    for table in ['academic_periods', 'academic_years', 'work_drafts', 'auth_sessions']: op.drop_table(table)
