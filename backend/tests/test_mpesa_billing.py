from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text

from test_teaching import env  # noqa: F401
from app.core import rate_limit as limiter
from app.core.config import settings
from app.models.subscription import MpesaStkRequest, MpesaTransaction, PaymentMessage, Subscription, SubscriptionPayment
from app.models.user import UserRole
from app.services import mpesa
from app.services.billing_reminders import send_billing_reminders
from app.services.payment_ledger import verify_chain
from app.services.subscriptions import add_month, amount_due, apply_payment, kenya_today

SECRET = "s" * 40


@pytest.fixture(autouse=True)
def daraja(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)
    for key, value in dict(MPESA_CONSUMER_KEY='key', MPESA_CONSUMER_SECRET='secret', MPESA_SHORTCODE='174379', MPESA_PASSKEY='pass',
                           MPESA_CALLBACK_BASE_URL='https://api.example.test', MPESA_CALLBACK_SECRET=SECRET, MPESA_TILL_NUMBER='', MPESA_ALLOWED_IPS='').items():
        monkeypatch.setattr(settings, key, value)
    calls = dict(push=[], query={})
    def push(**kwargs):
        calls['push'].append(kwargs)
        return dict(ResponseCode='0', CheckoutRequestID=f"ws_CO_{len(calls['push'])}", MerchantRequestID='m1')
    monkeypatch.setattr(mpesa, 'stk_push', push)
    monkeypatch.setattr(mpesa, 'stk_query', lambda checkout: calls['query'].get(checkout, {'errorCode': '500.001.1001', 'errorMessage': 'processing'}))
    return calls


def frozen_subscription(env, fee='2500', days_overdue=5):
    row = Subscription(institution_id=env['cls'].institution_id, monthly_fee=Decimal(fee), enforcement_enabled=True,
                       next_due_date=kenya_today() - timedelta(days=days_overdue), support_email='support@example.test')
    env['db'].add(row); env['db'].commit()
    return row


def platform(env):
    user = env['user']('owner', UserRole.PLATFORM_ADMIN)
    user.institution_id = None
    env['db'].commit()
    return user


def stk_callback(checkout, code=0, receipt='SFF1234567', amount=2500):
    items = [dict(Name='Amount', Value=amount), dict(Name='MpesaReceiptNumber', Value=receipt), dict(Name='TransactionDate', Value=20261107101010),
             dict(Name='PhoneNumber', Value=254712345678)]
    return dict(Body=dict(stkCallback=dict(MerchantRequestID='m1', CheckoutRequestID=checkout, ResultCode=code, ResultDesc='done',
                                           **(dict(CallbackMetadata=dict(Item=items)) if code == 0 else {}))))


def test_amounts_partial_credit_and_months():
    row = Subscription(monthly_fee=Decimal('1000'), enforcement_enabled=True, next_due_date=kenya_today() - timedelta(days=40), credit_balance=Decimal('0'))
    assert amount_due(row) == Decimal('2000')
    row.next_due_date = kenya_today() + timedelta(days=2)
    assert amount_due(row) == Decimal('1000')
    row.next_due_date = kenya_today() + timedelta(days=10)
    assert amount_due(row) == 0
    assert str(add_month(kenya_today().replace(year=2027, month=1, day=31))) == '2027-02-28'

    class Db:
        def add(self, row): self.row = row
    row.next_due_date = kenya_today().replace(year=2027, month=3, day=15)
    apply_payment(Db(), row, amount=Decimal('600'), reference='A', paid_on=kenya_today(), source='MPESA')
    assert str(row.next_due_date) == '2027-03-15' and row.credit_balance == Decimal('600')
    apply_payment(Db(), row, amount=Decimal('1500'), reference='B', paid_on=kenya_today(), source='MPESA')
    assert str(row.next_due_date) == '2027-05-15' and row.credit_balance == Decimal('100')


def test_frozen_admin_reaches_billing_only_and_others_see_status(env):
    frozen_subscription(env)
    admin = env['as_user'](env['admin'])
    state = admin.get('/api/institution/subscription').json()
    assert state['frozen'] and state['suggested_amount'] == 2500
    assert state['payment'] == dict(method='MPESA', kind='PAYBILL', number='174379', account=env['institutions'][0].code)
    assert admin.get('/api/institution/overview').status_code == 403
    assert admin.post('/api/institution/billing/mpesa/prompt', json=dict(phone='0712 345 678', amount=2500)).status_code == 201
    teacher = env['as_user'](env['teacher'])
    assert teacher.get('/api/institution/subscription').json() == dict(status='FROZEN', frozen=True)
    assert teacher.post('/api/institution/billing/mpesa/prompt', json=dict(phone='0712345678', amount=2500)).status_code == 403


def test_prompt_paid_through_callback_and_status_check(env, daraja):
    row = frozen_subscription(env)
    admin = env['as_user'](env['admin'])
    assert admin.post('/api/institution/billing/mpesa/prompt', json=dict(phone='+254 7123', amount=2500)).status_code == 422
    prompt = admin.post('/api/institution/billing/mpesa/prompt', json=dict(phone='0712345678', amount=2500)).json()
    assert daraja['push'][0]['phone'] == '254712345678' and daraja['push'][0]['account_reference'] == env['institutions'][0].code
    assert admin.post('/api/institution/billing/mpesa/prompt', json=dict(phone='0712345678', amount=2500)).status_code == 409
    assert env['client'].post('/api/payments/mpesa/wrong-secret/stk-callback', json=stk_callback('ws_CO_1')).status_code == 404
    daraja['query']['ws_CO_1'] = dict(ResultCode='0', ResultDesc='The service request is processed successfully.')
    for _ in range(2):  # Safaricom may repeat a callback.
        assert env['client'].post(f'/api/payments/mpesa/{SECRET}/stk-callback', json=stk_callback('ws_CO_1')).json()['ResultCode'] == 0
    env['db'].expire_all()
    assert env['db'].query(SubscriptionPayment).filter_by(source='MPESA').count() == 1
    assert env['db'].get(Subscription, row.id).next_due_date == add_month(kenya_today() - timedelta(days=5))
    status = admin.get(f"/api/institution/billing/mpesa/prompt/{prompt['id']}").json()
    assert status['status'] == 'PAID' and status['mpesa_receipt'] == 'SFF1234567' and not status['subscription']['frozen']
    assert env['as_user'](env['teacher']).get('/api/teaching/classes').status_code == 200
    kinds = [m.kind for m in env['db'].query(PaymentMessage).order_by(PaymentMessage.sequence)]
    assert kinds[:2] == ['STK_PROMPT', 'STK_CALLBACK'] and 'PAYMENT_APPLIED' in kinds and kinds.count('STK_CALLBACK') == 2
    assert verify_chain(env['db'])['intact']


def test_forged_success_callback_moves_no_money(env, daraja):
    frozen_subscription(env)
    env['as_user'](env['admin']).post('/api/institution/billing/mpesa/prompt', json=dict(phone='0712345678', amount=2500))
    daraja['query']['ws_CO_1'] = dict(ResultCode='1032', ResultDesc='Request cancelled by user')
    env['client'].post(f'/api/payments/mpesa/{SECRET}/stk-callback', json=stk_callback('ws_CO_1'))
    env['db'].expire_all()
    assert env['db'].query(MpesaStkRequest).one().status == 'FAILED'
    assert env['db'].query(SubscriptionPayment).count() == 0 and env['db'].query(MpesaTransaction).count() == 0


def test_paybill_matched_duplicate_and_unmatched_assignment(env):
    row = frozen_subscription(env, fee='1000', days_overdue=4)
    code = env['institutions'][0].code
    body = dict(TransactionType='Pay Bill', TransID='SFF0000001', TransTime='20261107101010', TransAmount='1500.00', BusinessShortCode='174379',
                BillRefNumber=f' {code.lower()} ', MSISDN='2547***678', FirstName='Jane')
    url = f'/api/payments/mpesa/{SECRET}'
    assert env['client'].post(url + '/c2b-validation', json=body).json()['ResultCode'] == '0'
    assert env['client'].post(url + '/c2b-validation', json={**body, 'BillRefNumber': 'NOPE'}).json()['ResultCode'] == 'C2B00012'
    env['client'].post(url + '/c2b-confirmation', json=body)
    env['client'].post(url + '/c2b-confirmation', json=body)
    env['db'].expire_all()
    row = env['db'].get(Subscription, row.id)
    assert row.credit_balance == Decimal('500') and row.next_due_date == add_month(kenya_today() - timedelta(days=4))
    assert env['db'].query(MpesaTransaction).count() == 1
    env['client'].post(url + '/c2b-confirmation', json={**body, 'TransID': 'SFF0000002', 'BillRefNumber': 'TYPO', 'TransAmount': '500'})
    owner = env['as_user'](platform(env))
    unmatched = owner.get('/api/platform/mpesa').json()['unmatched']
    assert [u['receipt'] for u in unmatched] == ['SFF0000002']
    assert owner.post(f"/api/platform/mpesa/transactions/{unmatched[0]['id']}/assign", json=dict(institution_id=str(row.institution_id))).json()['unmatched'] == []
    env['db'].expire_all()
    assert env['db'].get(Subscription, row.id).credit_balance == 0
    assert env['as_user'](env['admin']).get('/api/platform/payment-messages').status_code == 403


def test_evidence_log_export_and_tamper_check(env, monkeypatch):
    from app.services import billing_reminders
    frozen_subscription(env, days_overdue=0)
    env['institutions'][0].official_email = 'office@example.test'; env['db'].commit()
    sent = []
    monkeypatch.setattr(billing_reminders, 'send_email', lambda **kwargs: sent.append(kwargs))
    assert send_billing_reminders(env['db'], deliver=True)['sent'] == 1
    assert 'business number <strong>174379</strong>' in sent[0]['html_body'] and 'KES 2,500.00' in sent[0]['html_body']
    env['client'].post(f'/api/payments/mpesa/{SECRET}/c2b-confirmation', json=dict(TransID='SFF9', TransAmount='10', BusinessShortCode='174379', BillRefNumber='=cmd()'))
    owner = env['as_user'](platform(env))
    page = owner.get('/api/platform/payment-messages?kind=REMINDER_EMAIL').json()
    assert page['total'] == 1 and page['items'][0]['institution_code'] == env['institutions'][0].code
    detail = owner.get(f"/api/platform/payment-messages/{page['items'][0]['sequence']}").json()
    assert detail['payload']['to'] == 'office@example.test'
    csv = owner.get('/api/platform/payment-messages/export').text
    assert 'REMINDER_EMAIL' in csv and ",=cmd" not in csv and "'Paybill payment to account '=cmd()'" not in csv
    assert owner.get('/api/platform/payment-messages/verify').json()['intact']
    env['db'].execute(text("UPDATE payment_messages SET amount = 1 WHERE sequence = 1")); env['db'].commit()
    assert owner.get('/api/platform/payment-messages/verify').json() == dict(intact=False, checked=1, first_broken_sequence=1)
