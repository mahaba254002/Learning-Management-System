"""Request centre, institution termination and platform oversight.

School admins ask the platform for restricted operations (deleting an account,
password or recovery help, changing institution details, anything else). The
platform reviews each request, approves or rejects it with an explanation, and
completes it; every step is audited."""
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.teaching import commit, missing
from app.core.config import settings
from app.core.deps import AuthContext, require_platform_admin, require_role, require_tenant_user
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.grading_request import GradingChangeRequest
from app.models.institution import Institution, InstitutionStatus, InstitutionType
from app.models.platform_request import PlatformRequest
from app.models.subscription import Subscription, SubscriptionPayment
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import Input
from app.services.audit_service import record_audit
from app.services.elearning import notify

router = APIRouter(prefix='/api', tags=['Requests and oversight'])
institution_admin = require_role(UserRole.INSTITUTION_ADMIN)

EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
CHANGEABLE = {'name': 255, 'address': 500, 'official_email': 255, 'phone': 50, 'website': 255, 'country': 100, 'type': 40}
TARGETED = {'ACCOUNT_DELETION', 'PASSWORD_RESET', 'ACCOUNT_RECOVERY'}
RESET_PATHS = {UserRole.INSTITUTION_ADMIN: '/reset-password', UserRole.TEACHER: '/teacher/reset-password',
               UserRole.STAFF: '/teacher/reset-password', UserRole.STUDENT: '/student/reset-password'}
LABELS = {'ACCOUNT_DELETION': 'Delete an account', 'PASSWORD_RESET': 'Password reset', 'ACCOUNT_RECOVERY': 'Account recovery',
          'INSTITUTION_CHANGE': 'Change institution details', 'OTHER': 'Other request'}


def now():
    return datetime.now(timezone.utc)


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def person(user):
    return f'{user.first_name} {user.last_name}' if user else ''


class RequestInput(Input):
    kind: Literal['ACCOUNT_DELETION', 'PASSWORD_RESET', 'ACCOUNT_RECOVERY', 'INSTITUTION_CHANGE', 'OTHER']
    target_user_id: uuid.UUID | None = None
    details: str = Field(default='', max_length=2000)
    changes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid(self):
        self.details = self.details.strip()
        self.changes = {k: v.strip() for k, v in self.changes.items()}
        if self.kind in TARGETED and self.target_user_id is None:
            raise ValueError('Choose the account this request is about')
        if self.kind not in TARGETED and self.target_user_id is not None:
            raise ValueError('This request is not about one account')
        if self.kind == 'ACCOUNT_DELETION' and len(self.details) < 5:
            raise ValueError('Say why the account should be deleted')
        if self.kind == 'ACCOUNT_RECOVERY':
            if set(self.changes) != {'email'} or not EMAIL.match(self.changes['email']) or len(self.changes['email']) > 255:
                raise ValueError('Give the email address the person can now use')
        elif self.kind == 'INSTITUTION_CHANGE':
            if not self.changes or not set(self.changes) <= set(CHANGEABLE):
                raise ValueError('Choose at least one detail to change')
            for key, value in self.changes.items():
                if len(value) > CHANGEABLE[key] or (key in {'name', 'country', 'type'} and not value):
                    raise ValueError(f'Check the new {key.replace("_", " ")}')
            if 'type' in self.changes and self.changes['type'] not in InstitutionType.__members__:
                raise ValueError('Choose a valid institution type')
            if 'official_email' in self.changes and self.changes['official_email'] and not EMAIL.match(self.changes['official_email']):
                raise ValueError('Check the new official email')
        elif self.changes:
            raise ValueError('This request does not change any details')
        if self.kind == 'OTHER' and len(self.details) < 10:
            raise ValueError('Describe what you need in a sentence or two')
        return self


class DecisionInput(Input):
    action: Literal['APPROVE', 'REJECT', 'COMPLETE']
    note: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def reason(self):
        self.note = self.note.strip()
        if self.action == 'REJECT' and len(self.note) < 3:
            raise ValueError('Explain why the request is rejected')
        return self


def request_view(db, row, institution=None):
    names = {u.id: person(u) for u in db.query(User).filter(User.id.in_([i for i in (row.requested_by, row.reviewed_by, row.completed_by) if i])).all()}
    return dict(id=row.id, kind=row.kind, kind_label=LABELS[row.kind], status=row.status, institution_id=row.institution_id,
                institution_name=institution.name if institution else None, requested_by=names.get(row.requested_by, ''),
                target_user_id=row.target_user_id, target_label=row.target_label, details=row.details, changes=row.changes,
                created_at=utc(row.created_at), reviewed_by=names.get(row.reviewed_by, ''), reviewed_at=utc(row.reviewed_at),
                decision_note=row.decision_note, completed_by=names.get(row.completed_by, ''), completed_at=utc(row.completed_at))


def institution_target(db, ctx, user_id, kind):
    user = db.query(User).filter(User.id == user_id, User.institution_id == ctx.institution_id).first()
    if user is None:
        missing()
    allowed = {UserRole.TEACHER, UserRole.STUDENT, UserRole.STAFF}
    if kind != 'ACCOUNT_DELETION':
        allowed.add(UserRole.INSTITUTION_ADMIN)
    if user.role not in allowed or user.id == ctx.user_id:
        raise HTTPException(409, 'This request cannot be made for that account')
    return user


@router.get('/institution/requests')
def my_requests(db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    rows = db.query(PlatformRequest).filter_by(institution_id=ctx.institution_id).order_by(PlatformRequest.created_at.desc()).limit(200).all()
    return [request_view(db, r) for r in rows]


@router.post('/institution/requests', status_code=201, dependencies=[Depends(rate_limit(max_requests=20, window_seconds=3600, key_prefix='platform-request'))])
def create_request(body: RequestInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    label = ''
    if body.target_user_id:
        user = institution_target(db, ctx, body.target_user_id, body.kind)
        label = f'{person(user)} ({user.role.value.replace("_", " ").lower()}, {user.username})'
    open_rows = db.query(PlatformRequest).filter(PlatformRequest.institution_id == ctx.institution_id, PlatformRequest.kind == body.kind,
                                                 PlatformRequest.status.in_(['PENDING', 'APPROVED']))
    if body.target_user_id:
        open_rows = open_rows.filter(PlatformRequest.target_user_id == body.target_user_id)
    if body.kind != 'OTHER' and open_rows.first():
        raise HTTPException(409, 'A request like this is already waiting for the platform')
    row = PlatformRequest(institution_id=ctx.institution_id, kind=body.kind, status='PENDING', requested_by=ctx.user_id,
                          target_user_id=body.target_user_id, target_label=label, details=body.details, changes=body.changes)
    db.add(row)
    db.flush()
    record_audit(db, ctx, 'request.submitted', row.id, ctx.institution_id, f'{body.kind} {label}'.strip())
    commit(db)
    return request_view(db, row)


@router.post('/institution/requests/{request_id}/withdraw')
def withdraw(request_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    row = db.query(PlatformRequest).filter_by(id=request_id, institution_id=ctx.institution_id).with_for_update().first()
    if row is None:
        missing()
    if row.status != 'PENDING':
        raise HTTPException(409, 'Only a request still waiting for review can be withdrawn')
    row.status = 'WITHDRAWN'
    record_audit(db, ctx, 'request.withdrawn', row.id, ctx.institution_id, row.kind)
    commit(db)
    return request_view(db, row)


# --- Platform side -------------------------------------------------------------------------------

def send_reset(db, user):
    from app.core.verification import VerificationError, generate_verification_code
    from app.models.verification_code import VerificationCode, VerificationPurpose
    if not user.email or user.email.endswith('@deleted.invalid'):
        raise HTTPException(409, 'This account has no email address. Use account recovery to add one, or the school can reset it from User access.')
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(409, 'Reactivate the account before sending a reset link')
    db.query(VerificationCode).filter(VerificationCode.user_id == user.id, VerificationCode.purpose == VerificationPurpose.PASSWORD_RESET,
                                      VerificationCode.consumed_at.is_(None)).update({VerificationCode.consumed_at: now()}, synchronize_session=False)
    try:
        generate_verification_code(db=db, user_id=user.id, user_email=user.email, purpose=VerificationPurpose.PASSWORD_RESET,
                                   payload={'user_id': str(user.id), 'role': user.role.value}, reset_link_path=RESET_PATHS[user.role])
    except VerificationError as error:
        raise HTTPException(502, 'The reset email could not be sent. Check the email service, then try again.') from error


def carry_out(db, ctx, row):
    """Do what an approved request asks. Returns a short summary for the audit trail."""
    institution = db.query(Institution).filter_by(id=row.institution_id).with_for_update().one()
    target = None
    if row.kind in TARGETED:
        target = db.query(User).filter_by(id=row.target_user_id, institution_id=row.institution_id).with_for_update().first()
        if target is None:
            raise HTTPException(409, 'The account no longer exists')
    if row.kind == 'ACCOUNT_DELETION':
        from app.services.lifecycle import anonymise
        anonymise(db, target)
        return 'account anonymised'
    if row.kind == 'PASSWORD_RESET':
        send_reset(db, target)
        return 'reset link sent'
    if row.kind == 'ACCOUNT_RECOVERY':
        email = row.changes['email']
        clash = db.query(User.id).filter(func.lower(User.email) == email.lower(), User.id != target.id).first()
        if clash:
            raise HTTPException(409, 'Another account already uses that email address')
        target.email = email
        db.flush()
        send_reset(db, target)
        return 'email updated and reset link sent'
    if row.kind == 'INSTITUTION_CHANGE':
        for key, value in row.changes.items():
            setattr(institution, key, InstitutionType[value] if key == 'type' else (value or None) if key not in {'name', 'country'} else value)
        return 'changed ' + ', '.join(sorted(row.changes))
    return 'marked complete'


@router.get('/platform/requests')
def platform_requests(status: str | None = Query(None, max_length=10), db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    q = db.query(PlatformRequest, Institution).join(Institution, Institution.id == PlatformRequest.institution_id)
    if status == 'OPEN':
        q = q.filter(PlatformRequest.status.in_(['PENDING', 'APPROVED']))
    elif status:
        q = q.filter(PlatformRequest.status == status)
    return [request_view(db, r, i) for r, i in q.order_by(PlatformRequest.created_at.desc()).limit(300).all()]


@router.post('/platform/requests/{request_id}/decide')
def decide(request_id: uuid.UUID, body: DecisionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.query(PlatformRequest).filter_by(id=request_id).with_for_update().first()
    if row is None:
        missing()
    if row.status not in {'PENDING', 'APPROVED'} or (body.action == 'APPROVE' and row.status != 'PENDING'):
        raise HTTPException(409, 'This request has already been decided')
    at = now()
    if row.reviewed_by is None or body.action == 'REJECT':
        row.reviewed_by, row.reviewed_at = ctx.user_id, at
    if body.note:
        row.decision_note = body.note
    summary = ''
    if body.action == 'REJECT':
        row.status = 'REJECTED'
    elif body.action == 'APPROVE':
        row.status = 'APPROVED'
    else:
        summary = carry_out(db, ctx, row)
        row.status, row.completed_by, row.completed_at = 'COMPLETED', ctx.user_id, at
    record_audit(db, ctx, f'request.{row.status.lower()}', row.id, row.institution_id, f'{row.kind} {row.target_label}; {summary or body.note}'.strip())
    notify(db, row.institution_id, [row.requested_by], f'request:{row.id}:{row.status}', f'{LABELS[row.kind]}: {row.status.lower()}',
           row.decision_note or summary, '/institution/requests')
    commit(db)
    return request_view(db, row, db.get(Institution, row.institution_id))


class ResetInput(Input):
    reason: str = Field(default='', max_length=300)


@router.post('/platform/users/{user_id}/password-reset', dependencies=[Depends(rate_limit(max_requests=20, window_seconds=3600, key_prefix='platform-reset'))])
def platform_reset(user_id: uuid.UUID, body: ResetInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    user = db.query(User).filter(User.id == user_id, User.role != UserRole.PLATFORM_ADMIN).first()
    if user is None:
        missing()
    send_reset(db, user)
    record_audit(db, ctx, 'user.password_reset_sent', user.id, user.institution_id, body.reason.strip())
    commit(db)
    return dict(message=f'A reset link was sent to {user.email}')


# --- Ending an institution -----------------------------------------------------------------------

class TerminateInput(Input):
    days: int = Field(ge=1, le=3650)
    reason: str = Field(min_length=3, max_length=300)
    confirm_name: str = Field(max_length=255)


class ConfirmInput(Input):
    confirm_name: str = Field(max_length=255)


def locked_institution(db, institution_id, confirm_name=None):
    row = db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if row is None:
        missing()
    if confirm_name is not None and confirm_name.strip() != row.name:
        raise HTTPException(422, 'Type the institution name exactly to confirm')
    return row


def lifecycle_view(row):
    return dict(id=row.id, status=row.status, archived_at=utc(row.archived_at), delete_after=utc(row.delete_after))


@router.post('/platform/institutions/{institution_id}/terminate')
def terminate(institution_id: uuid.UUID, body: TerminateInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    from app.models.pilot import AuthSession
    row = locked_institution(db, institution_id, body.confirm_name)
    if row.status == InstitutionStatus.ARCHIVED:
        raise HTTPException(409, 'This institution is already terminated')
    at = now()
    row.status, row.archived_at, row.archived_by, row.delete_after = InstitutionStatus.ARCHIVED, at, ctx.user_id, at + timedelta(days=body.days)
    tenant_users = db.query(User.id).filter(User.institution_id == row.id)
    db.query(AuthSession).filter(AuthSession.user_id.in_(tenant_users), AuthSession.revoked.is_(False)).update(
        {AuthSession.revoked: True}, synchronize_session=False)
    record_audit(db, ctx, 'institution.terminated', row.id, row.id, f'{body.reason.strip()}; can be deleted after {body.days} days')
    commit(db)
    return lifecycle_view(row)


@router.post('/platform/institutions/{institution_id}/reactivate')
def reactivate(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = locked_institution(db, institution_id)
    if row.status != InstitutionStatus.ARCHIVED:
        raise HTTPException(409, 'Only a terminated institution can be reactivated here')
    row.status, row.archived_at, row.archived_by, row.delete_after = InstitutionStatus.ACTIVE, None, None, None
    record_audit(db, ctx, 'institution.reactivated', row.id, row.id, 'Termination reversed')
    commit(db)
    return lifecycle_view(row)


@router.post('/platform/institutions/{institution_id}/permanent-delete')
def permanent_delete(institution_id: uuid.UUID, body: ConfirmInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    from app.services.lifecycle import purge_institution
    row = locked_institution(db, institution_id, body.confirm_name)
    if row.status != InstitutionStatus.ARCHIVED or row.delete_after is None:
        raise HTTPException(409, 'Terminate the institution first')
    if now() < utc(row.delete_after):
        raise HTTPException(409, f'This institution can be deleted after {utc(row.delete_after):%d %b %Y, %H:%M} UTC')
    name, code = row.name, row.code
    removed = purge_institution(db, row)
    # Kept without an institution link, so the platform still knows what was deleted and by whom.
    record_audit(db, ctx, 'institution.deleted', institution_id, None, f'{name} ({code}); {sum(removed.values())} records removed')
    commit(db)
    return dict(deleted=True, records=sum(removed.values()))


# --- Oversight -------------------------------------------------------------------------------------

def health(db):
    checks = {}
    try:
        db.execute(func.now().select())
        checks['database'] = 'ok'
    except Exception:  # noqa: BLE001 - shown to the operator, never raised
        checks['database'] = 'down'
    try:
        from app.core.redis_client import redis_client
        checks['rate_limits'] = 'ok' if redis_client.ping() else 'down'
    except Exception:  # noqa: BLE001
        checks['rate_limits'] = 'down'
    from app.services import storage
    checks['email'] = 'ok' if settings.RESEND_API_KEY else 'off'
    checks['sms'] = 'ok' if settings.AT_USERNAME and settings.AT_API_KEY else 'off'
    checks['mpesa'] = 'ok' if settings.MPESA_CONSUMER_KEY and settings.MPESA_SHORTCODE else 'off'
    checks['file_storage'] = 'ok' if storage.enabled() else 'off'
    return checks


@router.get('/platform/overview')
def overview(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    today = date.today()
    by_status = dict(db.query(Institution.status, func.count(Institution.id)).group_by(Institution.status).all())
    expiring = db.query(Subscription, Institution).join(Institution, Institution.id == Subscription.institution_id).filter(
        Institution.status == InstitutionStatus.ACTIVE, Subscription.next_due_date.isnot(None),
        Subscription.next_due_date <= today + timedelta(days=14)).order_by(Subscription.next_due_date).limit(20).all()
    since = today - timedelta(days=30)
    revenue = db.query(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).filter(SubscriptionPayment.paid_on >= since).scalar()
    terminated = db.query(Institution).filter(Institution.status == InstitutionStatus.ARCHIVED).order_by(Institution.delete_after).limit(20).all()
    recent = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(12).all()
    actors = {u.id: person(u) for u in db.query(User).filter(User.id.in_([e.actor_id for e in recent if e.actor_id])).all()}
    schools = {i.id: i.name for i in db.query(Institution).filter(Institution.id.in_([e.institution_id for e in recent if e.institution_id])).all()}
    return dict(
        institutions=dict(total=sum(by_status.values()), active=by_status.get(InstitutionStatus.ACTIVE, 0),
                          suspended=by_status.get(InstitutionStatus.SUSPENDED, 0), terminated=by_status.get(InstitutionStatus.ARCHIVED, 0)),
        users=db.query(func.count(User.id)).filter(User.role != UserRole.PLATFORM_ADMIN).scalar(),
        open_requests=db.query(PlatformRequest).filter(PlatformRequest.status.in_(['PENDING', 'APPROVED'])).count(),
        grading_requests=db.query(GradingChangeRequest).filter_by(status='PENDING').count(),
        revenue_30_days=revenue,
        expiring=[dict(institution_id=i.id, name=i.name, next_due_date=s.next_due_date, overdue=s.next_due_date < today,
                       frozen=s.manually_frozen, monthly_fee=s.monthly_fee) for s, i in expiring],
        terminated=[dict(institution_id=i.id, name=i.name, delete_after=utc(i.delete_after)) for i in terminated],
        recent=[dict(action=e.action, detail=e.detail, created_at=utc(e.created_at), actor=actors.get(e.actor_id, ''),
                     institution=schools.get(e.institution_id, '')) for e in recent],
        health=health(db),
    )


@router.get('/institution/current-term')
def current_term(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    """The academic year in session and today's term or semester, shown in the top bar."""
    from app.models.pilot import AcademicPeriod, AcademicYear
    today = date.today()
    year = db.query(AcademicYear).filter_by(institution_id=ctx.institution_id, status='ACTIVE').order_by(AcademicYear.start_date.desc()).first()
    if year is None:
        return dict(year=None, period=None)
    period = db.query(AcademicPeriod).filter(AcademicPeriod.institution_id == ctx.institution_id, AcademicPeriod.year_id == year.id,
                                             AcademicPeriod.start_date <= today, AcademicPeriod.end_date >= today).first()
    return dict(year=year.name, period=period.name if period else None)
