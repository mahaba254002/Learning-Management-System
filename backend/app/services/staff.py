"""Staff profiles, sign-in accounts for staff, and single-use set-password links."""
import hashlib
import html
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.core.security import hash_password
from app.models.management import StaffMember
from app.models.structure import PasswordSetupToken
from app.models.user import User, UserRole, UserStatus
from app.schemas.teacher import TeacherSummary
from app.services.password_service import generate_temporary_password
from app.services.username_service import generate_username

SETUP_LINK_HOURS = 72
TEMPORARY_PASSWORD_DAYS = 7


def teacher_summary(profile, user):
    return TeacherSummary(
        id=profile.id, user_id=user.id, first_name=user.first_name, last_name=user.last_name, email=user.email,
        username=user.username, staff_number=profile.staff_number, job_title=profile.job_title,
        department_id=profile.department_id, gender=profile.gender, date_of_birth=profile.date_of_birth,
        phone=profile.phone, qualification=profile.qualification, specialization=profile.specialization,
        employment_type=profile.employment_type, status=profile.status, account_status=user.status.value,
        joined_at=profile.created_at)


def next_staff_number(db, institution_id, prefix='T'):
    taken = {n for (n,) in db.query(StaffMember.staff_number).filter_by(institution_id=institution_id).all()}
    n = 1
    while f'{prefix}{n:04d}' in taken: n += 1
    return f'{prefix}{n:04d}'


def role_for(category):
    return UserRole.TEACHER if category == 'TEACHING' else UserRole.STAFF


def login_path(role):
    return '/teacher/login' if role in {UserRole.TEACHER, UserRole.STAFF} else '/student/login' if role == UserRole.STUDENT else '/login'


def _digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def issue_setup_link(db, user, created_by):
    """Retire earlier links for this account and return a new one. Only the digest is stored."""
    now = datetime.now(timezone.utc)
    db.query(PasswordSetupToken).filter(PasswordSetupToken.user_id == user.id, PasswordSetupToken.used_at.is_(None)).update(
        {PasswordSetupToken.used_at: now}, synchronize_session=False)
    token = secrets.token_urlsafe(32)
    db.add(PasswordSetupToken(user_id=user.id, token_digest=_digest(token), created_by=created_by,
                              expires_at=now + timedelta(hours=SETUP_LINK_HOURS)))
    # The token travels in the URL fragment, which browsers never send to servers or logs.
    return f'{settings.FRONTEND_BASE_URL}/set-password#token={token}'


def find_setup_token(db, token, lock=False):
    q = db.query(PasswordSetupToken).filter(PasswordSetupToken.token_digest == _digest(token or ''))
    row = (q.with_for_update() if lock else q).first()
    if row is None or row.used_at is not None: return None
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc): return None
    user = db.get(User, row.user_id)
    if user is None or user.status != UserStatus.ACTIVE or not user.login_enabled: return None
    return row, user


def send_setup_link(db, user, institution, link):
    from app.services.email_failure_service import record_email_failure
    from app.services.email_service import EmailSendError, send_email
    subject = f'Set up your {institution.name} account on Skynet'
    body = (f'<p>Hello {html.escape(user.first_name)},</p>'
            f'<p>{html.escape(institution.name)} has created a Skynet account for you.</p>'
            f'<p><a href="{link}">Choose your password</a></p>'
            f'<p>This link works once and expires in {SETUP_LINK_HOURS} hours. Your username is '
            f'<strong>{html.escape(user.username)}</strong>.</p>')
    try:
        send_email(to=user.email, subject=subject, html_body=body)
        return True
    except EmailSendError as error:
        record_email_failure(db=db, recipient=user.email, subject=subject, email_type='ACCOUNT_SETUP',
                             error_message=str(error), context={'user_id': str(user.id), 'institution_id': str(institution.id)})
        db.commit()
        return False


def create_account(db, profile, institution, created_by, delivery):
    """Create a sign-in for a staff record. Returns (user, setup_link, temporary_password)."""
    if profile.user_id is not None: raise HTTPException(409, 'This employee already has a sign-in account')
    if not profile.email: raise HTTPException(422, 'Add an email address before creating a sign-in account')
    if profile.status != 'ACTIVE': raise HTTPException(409, 'Only active employees can be given a sign-in account')
    try:
        username = generate_username(db=db, first_name=profile.first_name, last_name=profile.last_name, institution_code=institution.code)
    except (ValueError, RuntimeError):
        raise HTTPException(400, 'Names must contain letters or digits suitable for a username')
    temporary = generate_temporary_password() if delivery == 'TEMPORARY_PASSWORD' else None
    user = User(institution_id=institution.id, username=username, first_name=profile.first_name, last_name=profile.last_name,
                email=profile.email, role=role_for(profile.category), status=UserStatus.ACTIVE, must_change_password=True,
                # Nobody knows this password; the person chooses their own through the link.
                password_hash=hash_password(temporary or secrets.token_urlsafe(32)))
    if temporary:
        user.temporary_password_expires_at = datetime.now(timezone.utc) + timedelta(days=TEMPORARY_PASSWORD_DAYS)
    db.add(user)
    db.flush()
    profile.user_id = user.id
    link = issue_setup_link(db, user, created_by) if delivery == 'LINK' else None
    return user, link, temporary
