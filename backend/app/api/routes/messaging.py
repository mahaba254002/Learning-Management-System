"""Messages to parents and guardians: results, fee balances, announcements and emergencies.

Every message is reviewed: an institution admin prepares it, checks the preview,
and sends it by answering their own secret question. Sending stops at the
monthly SMS allowance the platform sets. Each SMS is copied free by email to
guardians who have an email address."""
import hmac
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.teaching import commit, missing
from app.core.config import settings
from app.core.deps import AuthContext, forbid_delegated_credentials, require_platform_admin, require_role
from app.core.rate_limit import rate_limit
from app.core.security import hash_password, verify_password
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Student
from app.models.institution import Institution
from app.models.messaging import GuardianMessage, MessageDelivery, MessagingSecret, SmsAllowance
from app.models.pilot import AcademicPeriod
from app.models.records import FeeStatus, Guardian, StudentGuardian
from app.models.user import User, UserRole
from app.schemas.academic import Input
from app.services import sms
from app.services.audit_service import record_audit

router = APIRouter(prefix="/api", tags=["Parent messages"])
admin = require_role(UserRole.INSTITUTION_ADMIN)
NAIROBI = ZoneInfo('Africa/Nairobi')
MAX_FAILURES, LOCK_MINUTES = 5, 30
PLACEHOLDERS = {
    'RESULTS': {'school', 'student', 'first_name', 'admission', 'class', 'results', 'mean', 'grade', 'position', 'exam', 'term'},
    'FEES': {'school', 'student', 'first_name', 'admission', 'class', 'balance', 'status', 'term'},
    'ANNOUNCEMENT': {'school', 'student', 'first_name', 'admission', 'class'},
    'EMERGENCY': {'school', 'student', 'first_name', 'admission', 'class'},
}
FEE_WORDS = {'PAID': 'paid', 'PARTIAL': 'partly paid', 'UNPAID': 'not paid'}


def month_window(month=None):
    """The Nairobi calendar month as UTC datetimes."""
    today = datetime.now(NAIROBI).date()
    first = month or today.replace(day=1)
    nxt = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    to_utc = lambda d: datetime.combine(d, time.min, NAIROBI).astimezone(timezone.utc)
    return to_utc(first), to_utc(nxt)


def allowance(db, institution_id):
    row = db.get(SmsAllowance, institution_id)
    return row.monthly_parts if row else 0


def used_parts(db, institution_id, month=None):
    start, end = month_window(month)
    return db.query(func.coalesce(func.sum(MessageDelivery.parts), 0)).filter(
        MessageDelivery.institution_id == institution_id, MessageDelivery.channel == 'SMS',
        MessageDelivery.status.in_(['QUEUED', 'SENT', 'DELIVERED']),
        MessageDelivery.created_at >= start, MessageDelivery.created_at < end).scalar() or 0


def email_configured():
    return bool(settings.RESEND_API_KEY)


# --- The admin's secret question -----------------------------------------------------

def normalise(answer):
    return ' '.join(answer.lower().split())


class SecretInput(Input):
    password: str = Field(min_length=1, max_length=256)
    question: str = Field(min_length=5, max_length=200)
    answer: str = Field(min_length=3, max_length=200)


@router.put('/messaging/secret', dependencies=[Depends(rate_limit(max_requests=5, window_seconds=300, key_prefix='messaging-secret'))])
def set_secret(body: SecretInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin),
               _: AuthContext = Depends(forbid_delegated_credentials)):
    user = db.get(User, ctx.user_id)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, 'Your password is not correct')
    if normalise(body.answer) in normalise(body.question):
        raise HTTPException(422, 'The answer must not appear in the question')
    row = db.get(MessagingSecret, ctx.user_id)
    if row is None:
        row = MessagingSecret(user_id=ctx.user_id, institution_id=ctx.institution_id)
        db.add(row)
    row.question, row.answer_hash = body.question.strip(), hash_password(normalise(body.answer))
    row.failed_attempts, row.locked_until = 0, None
    record_audit(db, ctx, 'messaging.secret_set', ctx.user_id, ctx.institution_id)
    commit(db)
    return dict(set=True, question=row.question)


def check_answer(db, ctx, answer):
    """Verify the secret answer; five wrong answers lock sending for 30 minutes."""
    row = db.query(MessagingSecret).filter_by(user_id=ctx.user_id, institution_id=ctx.institution_id).with_for_update().first()
    if row is None:
        raise HTTPException(409, 'Set your secret question before sending messages')
    now = datetime.now(timezone.utc)
    locked = row.locked_until.replace(tzinfo=timezone.utc) if row.locked_until and row.locked_until.tzinfo is None else row.locked_until
    if locked and locked > now:
        raise HTTPException(423, 'Too many wrong answers. Try again later.')
    if not verify_password(normalise(answer or ''), row.answer_hash):
        row.failed_attempts += 1
        if row.failed_attempts >= MAX_FAILURES:
            row.failed_attempts, row.locked_until = 0, now + timedelta(minutes=LOCK_MINUTES)
        record_audit(db, ctx, 'messaging.secret_failed', ctx.user_id, ctx.institution_id)
        db.commit()
        raise HTTPException(403, 'That answer is not correct')
    row.failed_attempts, row.locked_until = 0, None


@router.delete('/platform/institutions/{institution_id}/messaging-secrets')
def clear_secrets(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    if not db.get(Institution, institution_id):
        missing()
    count = db.query(MessagingSecret).filter_by(institution_id=institution_id).delete(synchronize_session=False)
    record_audit(db, ctx, 'messaging.secrets_cleared', institution_id, institution_id, f'{count} cleared')
    commit(db)
    return dict(cleared=count)


# --- Overview ----------------------------------------------------------------------------

@router.get('/messaging/overview')
def overview(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    secret = db.get(MessagingSecret, ctx.user_id)
    monthly, used = allowance(db, ctx.institution_id), used_parts(db, ctx.institution_id)
    classes = scoped(db, AcademicClass, ctx).order_by(AcademicClass.academic_year.desc(), AcademicClass.name).all()
    periods = scoped(db, AcademicPeriod, ctx).order_by(AcademicPeriod.start_date.desc()).all()
    return dict(secret_set=secret is not None, question=secret.question if secret else None,
                sms_configured=sms.configured(), email_configured=email_configured(),
                allowance=monthly, used=used, remaining=max(monthly - used, 0), placeholders={k: sorted(v) for k, v in PLACEHOLDERS.items()},
                classes=[dict(id=c.id, name=f"{c.name}{' ' + c.stream if c.stream else ''} · {c.academic_year}") for c in classes],
                periods=[dict(id=p.id, name=p.name, start_date=p.start_date) for p in periods])


# --- Drafts --------------------------------------------------------------------------------

class Audience(Input):
    scope: Literal['SCHOOL', 'CLASS', 'STUDENTS'] = 'SCHOOL'
    class_id: uuid.UUID | None = None
    student_ids: list[uuid.UUID] = Field(default_factory=list, max_length=2000)
    period_id: uuid.UUID | None = None
    exam: str = Field(default='', max_length=200)
    fee_statuses: list[Literal['PARTIAL', 'UNPAID', 'PAID']] = Field(default_factory=lambda: ['PARTIAL', 'UNPAID'], max_length=3)
    all_guardians: bool = False


class MessageInput(Input):
    kind: Literal['RESULTS', 'FEES', 'ANNOUNCEMENT', 'EMERGENCY']
    title: str = Field(min_length=3, max_length=160)
    template: str = Field(min_length=3, max_length=1600)
    audience: Audience = Field(default_factory=Audience)

    @model_validator(mode='after')
    def consistent(self):
        unknown = set(re.findall(r'\{(\w+)\}', self.template)) - PLACEHOLDERS[self.kind]
        if unknown:
            raise ValueError(f"Unknown placeholder {', '.join('{' + u + '}' for u in sorted(unknown))}")
        a = self.audience
        if self.kind == 'RESULTS' and not (a.class_id and a.period_id):
            raise ValueError('Choose the class and term for results')
        if self.kind == 'FEES' and not (a.period_id and a.fee_statuses):
            raise ValueError('Choose the term and which fee statuses to remind')
        if self.kind in {'ANNOUNCEMENT', 'EMERGENCY'}:
            if a.scope == 'CLASS' and not a.class_id:
                raise ValueError('Choose the class')
            if a.scope == 'STUDENTS' and not a.student_ids:
                raise ValueError('Choose at least one student')
        return self


def check_refs(db, ctx, body):
    a = body.audience
    if a.class_id and not scoped(db, AcademicClass, ctx).filter_by(id=a.class_id).first():
        missing()
    if a.period_id and not scoped(db, AcademicPeriod, ctx).filter_by(id=a.period_id).first():
        missing()
    if a.student_ids and scoped(db, Student, ctx).filter(Student.id.in_(a.student_ids)).count() != len(set(a.student_ids)):
        missing()


def message_view(m, counts=None):
    out = dict(id=m.id, kind=m.kind, title=m.title, template=m.template, audience=m.audience, status=m.status,
               created_at=m.created_at, sent_at=m.sent_at)
    if counts is not None:
        out['counts'] = counts
    return out


@router.post('/messaging/messages', status_code=201)
def create_message(body: MessageInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    check_refs(db, ctx, body)
    row = GuardianMessage(institution_id=ctx.institution_id, kind=body.kind, title=body.title, template=body.template,
                          audience=body.audience.model_dump(mode='json'), created_by=ctx.actor_user_id or ctx.user_id)
    db.add(row)
    commit(db)
    return message_view(row)


def get_message(db, ctx, message_id, lock=False):
    q = scoped(db, GuardianMessage, ctx).filter_by(id=message_id)
    row = (q.with_for_update() if lock else q).first()
    if not row:
        missing()
    return row


@router.put('/messaging/messages/{message_id}')
def edit_message(message_id: uuid.UUID, body: MessageInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_message(db, ctx, message_id, lock=True)
    if row.status != 'DRAFT':
        raise HTTPException(409, 'Only drafts can be changed')
    check_refs(db, ctx, body)
    row.kind, row.title, row.template, row.audience = body.kind, body.title, body.template, body.audience.model_dump(mode='json')
    commit(db)
    return message_view(row)


@router.post('/messaging/messages/{message_id}/cancel')
def cancel_message(message_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_message(db, ctx, message_id, lock=True)
    if row.status != 'DRAFT':
        raise HTTPException(409, 'Only drafts can be cancelled')
    row.status = 'CANCELLED'
    commit(db)
    return message_view(row)


def delivery_counts(db, ctx, ids):
    counts = {}
    for mid, channel, state, n in scoped(db, MessageDelivery, ctx).filter(MessageDelivery.message_id.in_(ids or [uuid.uuid4()])).with_entities(
            MessageDelivery.message_id, MessageDelivery.channel, MessageDelivery.status, func.count(MessageDelivery.id)).group_by(
            MessageDelivery.message_id, MessageDelivery.channel, MessageDelivery.status).all():
        counts.setdefault(mid, {}).setdefault(channel, {})[state] = n
    return counts


@router.get('/messaging/messages')
def messages(db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    rows = scoped(db, GuardianMessage, ctx).order_by(GuardianMessage.created_at.desc()).limit(100).all()
    counts = delivery_counts(db, ctx, [r.id for r in rows])
    return [message_view(r, counts.get(r.id, {})) for r in rows]


@router.get('/messaging/messages/{message_id}')
def message_detail(message_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_message(db, ctx, message_id)
    deliveries = scoped(db, MessageDelivery, ctx).filter_by(message_id=row.id).order_by(MessageDelivery.channel, MessageDelivery.guardian_name).all()
    return dict(message_view(row, delivery_counts(db, ctx, [row.id]).get(row.id, {})),
                deliveries=[dict(id=d.id, channel=d.channel, guardian_name=d.guardian_name, address=d.address, status=d.status,
                                 parts=d.parts, error=d.error, sent_at=d.sent_at, body=d.body) for d in deliveries])


# --- Working out who gets what ----------------------------------------------------------------

def fill(template, values):
    return re.sub(r'\{(\w+)\}', lambda m: str(values.get(m.group(1), '')), template).strip()


def kes(value):
    return f"KES {Decimal(value):,.0f}" if Decimal(value) == Decimal(value).to_integral() else f"KES {Decimal(value):,.2f}"


def short(value):
    return f'{Decimal(value):.1f}'.rstrip('0').rstrip('.') if value is not None else ''


def build(db, ctx, message):
    """(deliveries, skipped) for a message. Deliveries are dicts ready for the outbox."""
    a = Audience.model_validate(message.audience)
    institution = db.get(Institution, ctx.institution_id)
    active = scoped(db, Student, ctx).filter(Student.status == 'ACTIVE')
    values, skipped = {}, []
    if message.kind == 'RESULTS':
        from app.services.marksheet import build as marksheet
        sheet = marksheet(db, ctx.institution_id, a.class_id, a.period_id, a.exam or None)
        names = {s['id']: s['name'] for s in sheet['subjects']}
        ranked = sum(1 for r in sheet['rows'] if r['position'])
        for r in sheet['rows']:
            if r['mean'] is None:
                skipped.append(dict(student_id=r['student_id'], reason='No marks'))
                continue
            parts = [f"{names[sid]} {short(c['percent'])}{' ' + c['grade'] if c['grade'] else ''}" for sid, c in r['cells'].items() if c['percent'] is not None]
            values[r['student_id']] = dict(results=', '.join(parts) + f". Mean {short(r['mean'])}{' ' + r['mean_grade'] if r['mean_grade'] else ''}, position {r['position']} of {ranked}",
                                           mean=short(r['mean']), grade=r['mean_grade'] or '', position=f"{r['position']} of {ranked}",
                                           exam=a.exam or 'end of term', term=sheet['period_name'])
        students = active.filter(Student.id.in_(list(values) or [uuid.uuid4()]))
    elif message.kind == 'FEES':
        period = scoped(db, AcademicPeriod, ctx).filter_by(id=a.period_id).one()
        q = active.join(FeeStatus, (FeeStatus.student_id == Student.id) & (FeeStatus.institution_id == Student.institution_id)).filter(
            FeeStatus.period_id == a.period_id, FeeStatus.status.in_(a.fee_statuses))
        if a.class_id:
            q = q.filter(Student.id.in_(scoped(db, Enrollment, ctx).filter_by(class_id=a.class_id, active=True).with_entities(Enrollment.student_id)))
        for student, fee in q.with_entities(Student, FeeStatus).all():
            values[student.id] = dict(balance=kes(fee.balance), status=FEE_WORDS[fee.status], term=period.name)
        students = active.filter(Student.id.in_(list(values) or [uuid.uuid4()]))
    else:
        students = active
        if a.scope == 'CLASS':
            students = students.filter(Student.id.in_(scoped(db, Enrollment, ctx).filter_by(class_id=a.class_id, active=True).with_entities(Enrollment.student_id)))
        elif a.scope == 'STUDENTS':
            students = students.filter(Student.id.in_(a.student_ids))
    rows = students.join(User, User.id == Student.user_id).filter(User.institution_id == ctx.institution_id).with_entities(Student, User).all()
    classes = {}
    for sid, group in scoped(db, Enrollment, ctx).join(AcademicClass, AcademicClass.id == Enrollment.class_id).filter(
            Enrollment.active.is_(True), Enrollment.student_id.in_([s.id for s, _ in rows] or [uuid.uuid4()])).with_entities(Enrollment.student_id, AcademicClass).all():
        classes.setdefault(sid, f"{group.name}{' ' + group.stream if group.stream else ''}")
    links = {}
    for link, guardian in scoped(db, StudentGuardian, ctx).join(Guardian, Guardian.id == StudentGuardian.guardian_id).filter(
            Guardian.institution_id == ctx.institution_id, StudentGuardian.student_id.in_([s.id for s, _ in rows] or [uuid.uuid4()])).with_entities(StudentGuardian, Guardian).all():
        links.setdefault(link.student_id, []).append((link, guardian))
    personal = bool(set(re.findall(r'\{(\w+)\}', message.template)) - {'school'})
    out, seen = [], set()
    for student, user in rows:
        guardians = [g for link, g in links.get(student.id, []) if a.all_guardians or link.is_primary]
        if not guardians:
            skipped.append(dict(student_id=student.id, reason='No guardian contact' if not links.get(student.id) else 'No main contact'))
            continue
        body = fill(message.template, dict(school=institution.name, student=f'{user.first_name} {user.last_name}', first_name=user.first_name,
                                           admission=student.admission_number, **{'class': classes.get(student.id, '')}, **values.get(student.id, {})))
        for g in guardians:
            for channel, address in [('SMS', g.phone), ('EMAIL', g.email)]:
                if not address or (channel == 'EMAIL' and not email_configured()) or (channel == 'SMS' and not sms.configured()):
                    continue
                # One copy per guardian when the text is the same for each child, e.g. a school notice to siblings' parent.
                key = (channel, address.lower(), student.id if personal else None)
                if key in seen:
                    continue
                seen.add(key)
                out.append(dict(student_id=student.id if personal else None, guardian_name=g.full_name, channel=channel, address=address,
                                body=body, parts=sms.parts(body) if channel == 'SMS' else 0))
    return out, skipped


@router.get('/messaging/messages/{message_id}/preview')
def preview(message_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_message(db, ctx, message_id)
    deliveries, skipped = build(db, ctx, row)
    sms_rows = [d for d in deliveries if d['channel'] == 'SMS']
    needed = sum(d['parts'] for d in sms_rows)
    monthly, used = allowance(db, ctx.institution_id), used_parts(db, ctx.institution_id)
    names = {s.id: f'{u.first_name} {u.last_name}' for s, u in scoped(db, Student, ctx).join(User, User.id == Student.user_id).filter(
        Student.id.in_([s['student_id'] for s in skipped] or [uuid.uuid4()])).with_entities(Student, User).all()}
    return dict(sms=len(sms_rows), email=sum(1 for d in deliveries if d['channel'] == 'EMAIL'), parts=needed,
                allowance=monthly, used=used, remaining=max(monthly - used, 0), fits=used + needed <= monthly,
                sms_configured=sms.configured(), email_configured=email_configured(),
                samples=[dict(to=d['guardian_name'], channel=d['channel'], body=d['body'], parts=d['parts']) for d in deliveries[:6]],
                skipped=[dict(name=names.get(s['student_id'], ''), reason=s['reason']) for s in skipped[:200]], skipped_total=len(skipped))


# --- Sending ------------------------------------------------------------------------------------

class SendInput(Input):
    answer: str = Field(min_length=1, max_length=200)


def queue(db, ctx, message, deliveries):
    needed = sum(d['parts'] for d in deliveries if d['channel'] == 'SMS')
    monthly, used = allowance(db, ctx.institution_id), used_parts(db, ctx.institution_id)
    if needed and used + needed > monthly:
        raise HTTPException(409, f'This needs {needed} SMS parts but only {max(monthly - used, 0)} of this month\'s {monthly} are left. '
                                 'Ask the Skynet platform administrator to raise the allowance, or send to fewer guardians.')
    for d in deliveries:
        db.add(MessageDelivery(institution_id=ctx.institution_id, message_id=message.id, **d))


@router.post('/messaging/messages/{message_id}/send', dependencies=[Depends(rate_limit(max_requests=10, window_seconds=300, key_prefix='messaging-send'))])
def send(message_id: uuid.UUID, body: SendInput, tasks: BackgroundTasks, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin),
         _: AuthContext = Depends(forbid_delegated_credentials)):
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()  # One send at a time per institution.
    row = get_message(db, ctx, message_id, lock=True)
    if row.status != 'DRAFT':
        raise HTTPException(409, 'This message was already sent or cancelled')
    check_answer(db, ctx, body.answer)
    if not sms.configured() and not email_configured():
        raise HTTPException(409, 'SMS and email are not set up yet. Contact the Skynet platform administrator.')
    deliveries, skipped = build(db, ctx, row)
    if not deliveries:
        raise HTTPException(409, 'Nobody would receive this message. Check guardian contacts and the audience.')
    queue(db, ctx, row, deliveries)
    row.status, row.sent_by, row.sent_at = 'SENDING', ctx.user_id, datetime.now(timezone.utc)
    record_audit(db, ctx, 'messaging.sent', row.id, ctx.institution_id, f'{row.kind}: {len(deliveries)} deliveries')
    commit(db)
    tasks.add_task(process, db.get_bind(), row.id)
    return dict(message_view(row), queued=len(deliveries), skipped=len(skipped))


@router.post('/messaging/messages/{message_id}/retry')
def retry(message_id: uuid.UUID, body: SendInput, tasks: BackgroundTasks, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin),
          _: AuthContext = Depends(forbid_delegated_credentials)):
    """Send the failed deliveries of a sent message again."""
    db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    row = get_message(db, ctx, message_id, lock=True)
    check_answer(db, ctx, body.answer)
    failed = scoped(db, MessageDelivery, ctx).filter_by(message_id=row.id, status='FAILED').all()
    if not failed:
        raise HTTPException(409, 'Nothing failed')
    needed = sum(d.parts for d in failed if d.channel == 'SMS')
    monthly, used = allowance(db, ctx.institution_id), used_parts(db, ctx.institution_id)
    if needed and used + needed > monthly:
        raise HTTPException(409, f'Retrying needs {needed} SMS parts but only {max(monthly - used, 0)} are left this month.')
    for d in failed:
        d.status, d.error, d.attempts, d.created_at = 'QUEUED', '', 0, datetime.now(timezone.utc)
    row.status = 'SENDING'
    record_audit(db, ctx, 'messaging.retried', row.id, ctx.institution_id, f'{len(failed)} deliveries')
    commit(db)
    tasks.add_task(process, db.get_bind(), row.id)
    return dict(queued=len(failed))


def process(bind, message_id=None, limit=1000):
    """Send queued deliveries. Runs after a send, and from `python send_messages.py` for anything left over."""
    from app.services.email_service import EmailSendError, send_email
    db = Session(bind=bind)
    try:
        q = db.query(MessageDelivery).filter(MessageDelivery.status == 'QUEUED', MessageDelivery.attempts < 3)
        if message_id:
            q = q.filter(MessageDelivery.message_id == message_id)
        rows = q.order_by(MessageDelivery.created_at).limit(limit).all()
        now = lambda: datetime.now(timezone.utc)
        groups = {}
        for d in rows:
            if d.channel == 'SMS':
                groups.setdefault((d.institution_id, d.body), []).append(d)
            else:
                d.attempts += 1
                try:
                    title = db.get(GuardianMessage, d.message_id).title
                    school = db.get(Institution, d.institution_id).name
                    html = '<p>' + '</p><p>'.join(line for line in _escape(d.body).split('\n') if line) + f'</p><p style="color:#71717a">{_escape(school)}</p>'
                    send_email(to=d.address, subject=f'{school}: {title}', html_body=html)
                    d.status, d.sent_at, d.error = 'SENT', now(), ''
                except (EmailSendError, Exception) as exc:  # noqa: BLE001 - one bad address must not stop the rest
                    d.error = str(exc)[:300]
                    if d.attempts >= 3:
                        d.status = 'FAILED'
                db.commit()
        for (_, text), batch in groups.items():
            for start in range(0, len(batch), 100):
                chunk = batch[start:start + 100]
                for d in chunk:
                    d.attempts += 1
                try:
                    result = sms.send([d.address for d in chunk], text)
                    for d in chunk:
                        item = result.get(d.address)
                        if item and item['accepted']:
                            d.status, d.provider_id, d.cost, d.sent_at, d.error = 'SENT', item['message_id'], item['cost'], now(), ''
                        else:
                            d.status, d.error = 'FAILED', (item['status'] if item else 'Not accepted by the provider')[:300]
                except sms.SmsError as exc:
                    for d in chunk:
                        d.error = str(exc)[:300]
                        if d.attempts >= 3:
                            d.status = 'FAILED'
                db.commit()
        for message in db.query(GuardianMessage).filter(GuardianMessage.status == 'SENDING').all():
            if not db.query(MessageDelivery.id).filter_by(message_id=message.id, status='QUEUED').first():
                message.status = 'SENT'
        db.commit()
    finally:
        db.close()


def _escape(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


@router.post('/messaging/at/{secret}/delivery')
async def delivery_report(secret: str, request: Request, db: Session = Depends(get_db)):
    """Africa's Talking delivery report (form fields id, status, failureReason)."""
    expected = settings.AT_CALLBACK_SECRET
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(404, 'Not found')
    raw = (await request.body())[:10000].decode(errors='replace')
    fields = {k: v[0] for k, v in parse_qs(raw).items()}
    provider_id, state = fields.get('id', '')[:100], fields.get('status', '')
    row = db.query(MessageDelivery).filter_by(provider_id=provider_id, channel='SMS').first() if provider_id else None
    if row is not None:
        if state == 'Success':
            row.status, row.error = 'DELIVERED', ''
        elif state in {'Failed', 'Rejected'}:
            row.status, row.error = 'FAILED', (fields.get('failureReason') or state)[:300]
        db.commit()
    return {'ok': True}


# --- Platform: allowances and usage ------------------------------------------------------------------

class AllowanceInput(Input):
    monthly_parts: int = Field(ge=0, le=1000000)


@router.put('/platform/institutions/{institution_id}/sms-allowance')
def set_allowance(institution_id: uuid.UUID, body: AllowanceInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    if not db.get(Institution, institution_id):
        missing()
    row = db.get(SmsAllowance, institution_id)
    if row is None:
        row = SmsAllowance(institution_id=institution_id)
        db.add(row)
    row.monthly_parts = body.monthly_parts
    record_audit(db, ctx, 'messaging.allowance_set', institution_id, institution_id, str(body.monthly_parts))
    commit(db)
    return dict(monthly_parts=row.monthly_parts)


@router.get('/platform/messaging/usage')
def usage(month: str = Query('', pattern=r'^(\d{4}-\d{2})?$'), db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    first = date.fromisoformat(month + '-01') if month else None
    start, end = month_window(first)
    stats = {}
    for iid, channel, state, n, parts, spent in db.query(MessageDelivery.institution_id, MessageDelivery.channel, MessageDelivery.status,
                                                         func.count(MessageDelivery.id), func.coalesce(func.sum(MessageDelivery.parts), 0),
                                                         func.coalesce(func.sum(MessageDelivery.cost), 0)).filter(
            MessageDelivery.created_at >= start, MessageDelivery.created_at < end).group_by(
            MessageDelivery.institution_id, MessageDelivery.channel, MessageDelivery.status).all():
        s = stats.setdefault(iid, dict(sms_parts=0, sms_sent=0, sms_failed=0, emails=0, cost=Decimal(0)))
        if channel == 'SMS':
            if state == 'FAILED':
                s['sms_failed'] += n
            else:
                s['sms_sent'] += n
                s['sms_parts'] += int(parts)
            s['cost'] += Decimal(spent)
        elif state != 'FAILED':
            s['emails'] += n
    allowances = {a.institution_id: a.monthly_parts for a in db.query(SmsAllowance).all()}
    secrets = dict(db.query(MessagingSecret.institution_id, func.count(MessagingSecret.user_id)).group_by(MessagingSecret.institution_id).all())
    rows = []
    for inst in db.query(Institution).order_by(Institution.name).all():
        s = stats.get(inst.id, dict(sms_parts=0, sms_sent=0, sms_failed=0, emails=0, cost=Decimal(0)))
        rows.append(dict(institution_id=inst.id, name=inst.name, code=inst.code, allowance=allowances.get(inst.id, 0), secrets=secrets.get(inst.id, 0), **s))
    return dict(month=(first or datetime.now(NAIROBI).date().replace(day=1)).strftime('%Y-%m'), sms_configured=sms.configured(),
                environment=settings.AT_ENVIRONMENT, rows=rows)
