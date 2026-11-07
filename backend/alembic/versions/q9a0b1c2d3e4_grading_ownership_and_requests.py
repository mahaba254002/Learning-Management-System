"""Institutions set their own grading once; later changes are requests the platform approves.

Revision ID: q9a0b1c2d3e4
Revises: p8f9a0b1c2d3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'q9a0b1c2d3e4'
down_revision = 'p8f9a0b1c2d3'
branch_labels = None
depends_on = None


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade():
    op.add_column('institutions', sa.Column('grading_locked_at', sa.DateTime(timezone=True)))
    op.create_table('grading_change_requests',
                    sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('proposed_rules', json_type(), nullable=False), sa.Column('previous_rules', json_type(), nullable=False),
                    sa.Column('reason', sa.String(1000), nullable=False), sa.Column('status', sa.String(10), nullable=False),
                    sa.Column('requested_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
                    sa.Column('decided_by', sa.Uuid(), sa.ForeignKey('users.id')),
                    sa.Column('decided_at', sa.DateTime(timezone=True)),
                    sa.Column('decision_note', sa.String(1000), nullable=False, server_default=''),
                    sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN')", name='ck_grading_change_requests_status'))
    op.create_index('ix_grading_change_requests_status', 'grading_change_requests', ['status', 'created_at'])


def downgrade():
    if op.get_bind().execute(sa.text('SELECT 1 FROM grading_change_requests LIMIT 1')).first():
        raise RuntimeError('grading_change_requests holds records. Export them before downgrading.')
    op.drop_table('grading_change_requests')
    op.drop_column('institutions', 'grading_locked_at')
