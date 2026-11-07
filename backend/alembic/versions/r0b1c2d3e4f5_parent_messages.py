"""Parent and guardian messages: secret questions, SMS allowances, drafts and the outbox.

Revision ID: r0b1c2d3e4f5
Revises: q9a0b1c2d3e4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'r0b1c2d3e4f5'
down_revision = 'q9a0b1c2d3e4'
branch_labels = None
depends_on = None


def stamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table('messaging_secrets',
                    sa.Column('user_id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True), *stamps(),
                    sa.Column('question', sa.String(200), nullable=False), sa.Column('answer_hash', sa.String(255), nullable=False),
                    sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'),
                    sa.Column('locked_until', sa.DateTime(timezone=True)),
                    sa.ForeignKeyConstraint(['institution_id', 'user_id'], ['users.institution_id', 'users.id'], ondelete='CASCADE'))
    op.create_table('sms_allowances',
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id', ondelete='CASCADE'), primary_key=True), *stamps(),
                    sa.Column('monthly_parts', sa.Integer(), nullable=False, server_default='0'),
                    sa.CheckConstraint('monthly_parts >= 0 AND monthly_parts <= 1000000', name='ck_sms_allowances_parts'))
    op.create_table('guardian_messages',
                    sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True), *stamps(),
                    sa.Column('kind', sa.String(12), nullable=False), sa.Column('title', sa.String(160), nullable=False),
                    sa.Column('template', sa.Text(), nullable=False),
                    sa.Column('audience', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
                    sa.Column('status', sa.String(10), nullable=False), sa.Column('created_by', sa.Uuid(), nullable=False),
                    sa.Column('sent_by', sa.Uuid()), sa.Column('sent_at', sa.DateTime(timezone=True)),
                    sa.UniqueConstraint('institution_id', 'id', name='uq_guardian_messages_tenant_id'),
                    sa.ForeignKeyConstraint(['institution_id', 'created_by'], ['users.institution_id', 'users.id']),
                    sa.ForeignKeyConstraint(['institution_id', 'sent_by'], ['users.institution_id', 'users.id']),
                    sa.CheckConstraint("kind IN ('RESULTS', 'FEES', 'ANNOUNCEMENT', 'EMERGENCY')", name='ck_guardian_messages_kind'),
                    sa.CheckConstraint("status IN ('DRAFT', 'SENDING', 'SENT', 'CANCELLED')", name='ck_guardian_messages_status'))
    op.create_index('ix_guardian_messages_recent', 'guardian_messages', ['institution_id', 'created_at'])
    op.create_table('message_deliveries',
                    sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False, index=True), *stamps(),
                    sa.Column('message_id', sa.Uuid(), nullable=False), sa.Column('student_id', sa.Uuid()),
                    sa.Column('guardian_name', sa.String(160), nullable=False), sa.Column('channel', sa.String(5), nullable=False),
                    sa.Column('address', sa.String(255), nullable=False), sa.Column('body', sa.Text(), nullable=False),
                    sa.Column('parts', sa.Integer(), nullable=False), sa.Column('status', sa.String(10), nullable=False),
                    sa.Column('provider_id', sa.String(100), index=True), sa.Column('cost', sa.Numeric(10, 4)),
                    sa.Column('error', sa.String(300), nullable=False, server_default=''),
                    sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
                    sa.Column('sent_at', sa.DateTime(timezone=True)),
                    sa.UniqueConstraint('institution_id', 'message_id', 'channel', 'address', 'student_id', name='uq_message_deliveries_once'),
                    sa.ForeignKeyConstraint(['institution_id', 'message_id'], ['guardian_messages.institution_id', 'guardian_messages.id'], ondelete='CASCADE'),
                    sa.ForeignKeyConstraint(['institution_id', 'student_id'], ['students.institution_id', 'students.id']),
                    sa.CheckConstraint("channel IN ('SMS', 'EMAIL')", name='ck_message_deliveries_channel'),
                    sa.CheckConstraint("status IN ('QUEUED', 'SENT', 'DELIVERED', 'FAILED')", name='ck_message_deliveries_status'))
    op.create_index('ix_message_deliveries_queue', 'message_deliveries', ['status', 'created_at'])
    op.create_index('ix_message_deliveries_month', 'message_deliveries', ['institution_id', 'channel', 'sent_at'])


def downgrade():
    bind = op.get_bind()
    for table in ('message_deliveries', 'guardian_messages'):
        if bind.execute(sa.text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError(f'{table} holds records. Export them before downgrading.')
    for table in ('message_deliveries', 'guardian_messages', 'sms_allowances', 'messaging_secrets'):
        op.drop_table(table)
