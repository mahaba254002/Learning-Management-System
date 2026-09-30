"""Administrative audit events.

Revision ID: b4d5e6f7a8c9
Revises: a3c4d5e6f7b8
"""
from alembic import op
import sqlalchemy as sa

revision = 'b4d5e6f7a8c9'
down_revision = 'a3c4d5e6f7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('audit_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=True),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_id', sa.String(100), nullable=False),
        sa.Column('detail', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_audit_events_institution_id', 'audit_events', ['institution_id'])
    op.create_index('ix_audit_events_actor_id', 'audit_events', ['actor_id'])


def downgrade():
    op.drop_table('audit_events')
