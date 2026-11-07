"""M-Pesa subscription payments, a fixed three-day grace period and an append-only payment evidence log.

Revision ID: n6d7e8f9a0b1
Revises: m5c6d7e8f9a0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'n6d7e8f9a0b1'
down_revision = 'm5c6d7e8f9a0'
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.drop_column('institution_subscriptions', 'grace_days')
    op.add_column('institution_subscriptions', sa.Column('credit_balance', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.create_check_constraint('ck_institution_subscriptions_credit', 'institution_subscriptions', 'credit_balance >= 0')

    op.add_column('subscription_payments', sa.Column('source', sa.String(10), nullable=False, server_default='MANUAL'))
    op.create_check_constraint('ck_subscription_payments_source', 'subscription_payments', "source IN ('MANUAL', 'MPESA')")
    op.alter_column('subscription_payments', 'recorded_by', nullable=True)

    op.create_table('mpesa_stk_requests', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id'), nullable=False), *timestamps(),
                    sa.Column('requested_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
                    sa.Column('phone', sa.String(12), nullable=False), sa.Column('amount', sa.Integer(), nullable=False),
                    sa.Column('checkout_request_id', sa.String(100), nullable=False, unique=True),
                    sa.Column('merchant_request_id', sa.String(100), nullable=False),
                    sa.Column('status', sa.String(10), nullable=False), sa.Column('result_code', sa.String(20)),
                    sa.Column('result_description', sa.String(255), nullable=False), sa.Column('mpesa_receipt', sa.String(30)),
                    sa.Column('completed_at', sa.DateTime(timezone=True)),
                    sa.CheckConstraint('amount > 0'),
                    sa.CheckConstraint("status IN ('PENDING', 'PAID', 'FAILED')", name='ck_mpesa_stk_requests_status'))
    op.create_index('ix_mpesa_stk_requests_institution_id', 'mpesa_stk_requests', ['institution_id'])

    op.create_table('mpesa_transactions', sa.Column('id', sa.Uuid(), primary_key=True), *timestamps(),
                    sa.Column('receipt', sa.String(30), nullable=False, unique=True),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id')),
                    sa.Column('channel', sa.String(10), nullable=False), sa.Column('amount', sa.Numeric(12, 2), nullable=False),
                    sa.Column('phone', sa.String(20), nullable=False), sa.Column('payer_name', sa.String(150), nullable=False),
                    sa.Column('account_reference', sa.String(40), nullable=False),
                    sa.Column('transacted_at', sa.DateTime(timezone=True)), sa.Column('applied_at', sa.DateTime(timezone=True)),
                    sa.CheckConstraint('amount > 0'),
                    sa.CheckConstraint("channel IN ('STK', 'PAYBILL')", name='ck_mpesa_transactions_channel'))
    op.create_index('ix_mpesa_transactions_institution_id', 'mpesa_transactions', ['institution_id'])

    op.create_table('payment_messages', sa.Column('sequence', sa.BigInteger(), primary_key=True, autoincrement=False),
                    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
                    sa.Column('institution_id', sa.Uuid(), sa.ForeignKey('institutions.id')),
                    sa.Column('kind', sa.String(40), nullable=False), sa.Column('direction', sa.String(3), nullable=False),
                    sa.Column('reference', sa.String(100), nullable=False), sa.Column('amount', sa.Numeric(12, 2)),
                    sa.Column('summary', sa.Text(), nullable=False), sa.Column('payload', postgresql.JSONB(), nullable=False),
                    sa.Column('previous_hash', sa.String(64), nullable=False), sa.Column('entry_hash', sa.String(64), nullable=False, unique=True))
    for column in ('institution_id', 'kind', 'reference'):
        op.create_index(f'ix_payment_messages_{column}', 'payment_messages', [column])
    op.execute("""
        CREATE FUNCTION payment_messages_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'payment_messages is append-only';
        END $$""")
    op.execute("CREATE TRIGGER payment_messages_no_change BEFORE UPDATE OR DELETE ON payment_messages "
               "FOR EACH ROW EXECUTE FUNCTION payment_messages_append_only()")
    op.execute("CREATE TRIGGER payment_messages_no_truncate BEFORE TRUNCATE ON payment_messages "
               "FOR EACH STATEMENT EXECUTE FUNCTION payment_messages_append_only()")


def downgrade():
    bind = op.get_bind()
    held = bind.execute(sa.text("SELECT (SELECT count(*) FROM payment_messages) + (SELECT count(*) FROM mpesa_transactions) "
                                "+ (SELECT count(*) FROM subscription_payments WHERE source = 'MPESA' OR recorded_by IS NULL)")).scalar()
    if held:
        raise RuntimeError(f'{held} payment records exist. Export them before downgrading; the evidence log cannot be carried back.')
    op.execute('DROP TABLE payment_messages')
    op.execute('DROP FUNCTION payment_messages_append_only()')
    op.drop_table('mpesa_transactions')
    op.drop_table('mpesa_stk_requests')
    op.alter_column('subscription_payments', 'recorded_by', nullable=False)
    op.drop_constraint('ck_subscription_payments_source', 'subscription_payments', type_='check')
    op.drop_column('subscription_payments', 'source')
    op.drop_constraint('ck_institution_subscriptions_credit', 'institution_subscriptions', type_='check')
    op.drop_column('institution_subscriptions', 'credit_balance')
    op.add_column('institution_subscriptions', sa.Column('grace_days', sa.Integer(), nullable=False, server_default='3'))
    op.create_check_constraint('institution_subscriptions_grace_days_check', 'institution_subscriptions', 'grace_days >= 0 AND grace_days <= 90')
