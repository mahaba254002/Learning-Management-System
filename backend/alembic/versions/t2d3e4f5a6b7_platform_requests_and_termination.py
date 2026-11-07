"""Platform request centre and institution termination with a deletion date.

Revision ID: t2d3e4f5a6b7
Revises: s1c2d3e4f5a6
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 't2d3e4f5a6b7'
down_revision = 's1c2d3e4f5a6'
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade():
    op.add_column('institutions', sa.Column('delete_after', sa.DateTime(timezone=True)))
    op.create_table('platform_requests',
                    sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('kind', sa.String(20), nullable=False), sa.Column('status', sa.String(10), nullable=False),
                    sa.Column('requested_by', sa.Uuid(), nullable=False), sa.Column('target_user_id', sa.Uuid()),
                    sa.Column('target_label', sa.String(200), nullable=False), sa.Column('details', sa.Text(), nullable=False),
                    sa.Column('changes', JSON, nullable=False),
                    sa.Column('reviewed_by', sa.Uuid(), sa.ForeignKey('users.id')), sa.Column('reviewed_at', sa.DateTime(timezone=True)),
                    sa.Column('decision_note', sa.String(1000), nullable=False),
                    sa.Column('completed_by', sa.Uuid(), sa.ForeignKey('users.id')), sa.Column('completed_at', sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(['institution_id', 'requested_by'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint("kind IN ('ACCOUNT_DELETION', 'PASSWORD_RESET', 'ACCOUNT_RECOVERY', 'INSTITUTION_CHANGE', 'OTHER')", name='ck_platform_requests_kind'),
                    sa.CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED', 'COMPLETED', 'WITHDRAWN')", name='ck_platform_requests_status'))
    op.create_index('ix_platform_requests_queue', 'platform_requests', ['status', 'created_at'])


def downgrade():
    op.drop_index('ix_platform_requests_queue', 'platform_requests')
    op.drop_table('platform_requests')
    op.drop_column('institutions', 'delete_after')
