"""Closing accounts for good and removing terminated institutions.

Deleting a person anonymises them: sign-in ends and personal details are
replaced, while marks, attendance and audit history stay so past results and
marksheets do not change. Deleting an institution removes every row that
belongs to it, after the deletion date the platform chose has passed."""
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.base import Base
from app.models.user import User, UserRole, UserStatus

DELETED_FIRST, DELETED_LAST = 'Deleted', 'user'
# Accounts must keep a sign-in identity; .invalid addresses can never receive mail.
DELETED_DOMAIN = '@deleted.invalid'


def anonymise(db, user):
    """Close an account permanently and remove personal details. Callers audit and commit."""
    from app.api.routes.administration import leaving_checks
    from app.models.academic import Student
    from app.models.elearning import Notification
    from app.models.management import StaffMember
    from app.models.pilot import AuthSession
    from app.models.records import Guardian, StudentGuardian
    from app.models.teacher import Teacher
    from app.models.verification_code import VerificationCode

    if user.role not in {UserRole.TEACHER, UserRole.STUDENT, UserRole.STAFF}:
        raise HTTPException(409, 'Only teacher, student and staff accounts can be deleted this way')
    if (user.email or '').endswith(DELETED_DOMAIN):
        raise HTTPException(409, 'This account has already been deleted')
    leaving_checks(db, user)
    now = datetime.now(timezone.utc)
    tenant = user.institution_id
    user.first_name, user.last_name = DELETED_FIRST, DELETED_LAST
    user.email, user.student_login_method, user.student_login_id = f'deleted-{user.id.hex}{DELETED_DOMAIN}', 'EMAIL', None
    user.username = f'deleted-{user.id.hex[:20]}'
    user.status, user.login_enabled = UserStatus.ARCHIVED, False
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.password_changed_at = now
    db.query(AuthSession).filter(AuthSession.user_id == user.id).update({AuthSession.revoked: True}, synchronize_session=False)
    db.query(VerificationCode).filter(VerificationCode.user_id == user.id, VerificationCode.consumed_at.is_(None)).update(
        {VerificationCode.consumed_at: now}, synchronize_session=False)
    db.query(Notification).filter(Notification.user_id == user.id).delete(synchronize_session=False)

    for staff in db.query(StaffMember).filter_by(institution_id=tenant, user_id=user.id).all():
        staff.first_name, staff.last_name = DELETED_FIRST, DELETED_LAST
        staff.email = staff.phone = staff.date_of_birth = staff.gender = staff.qualification = staff.specialization = None
        staff.status = 'INACTIVE'
    for teacher in db.query(Teacher).filter_by(institution_id=tenant, user_id=user.id).all():
        teacher.phone, teacher.specialization = None, None
    student = db.query(Student).filter_by(institution_id=tenant, user_id=user.id).first()
    if student is not None:
        student.phone = None
        student.status_note = 'Account deleted at the institution\'s request'
        guardian_ids = [g for (g,) in db.query(StudentGuardian.guardian_id).filter_by(institution_id=tenant, student_id=student.id).all()]
        db.query(StudentGuardian).filter_by(institution_id=tenant, student_id=student.id).delete(synchronize_session=False)
        db.flush()
        # A parent who has no other child here is removed too.
        for guardian_id in guardian_ids:
            if not db.query(StudentGuardian.id).filter_by(institution_id=tenant, guardian_id=guardian_id).first():
                db.query(Guardian).filter_by(institution_id=tenant, id=guardian_id).delete(synchronize_session=False)
    db.flush()


def _tenant_tables():
    """Every table holding institution rows, and every column pointing at a user."""
    out = []
    for table in Base.metadata.tables.values():
        if table.name == 'institutions':
            continue
        user_columns = [fk.parent for fk in table.foreign_keys if fk.column.table.name == 'users' and fk.column.name == 'id'
                        and fk.parent.name != 'institution_id']
        if 'institution_id' in table.c or user_columns:
            out.append((table, user_columns))
    return out


def purge_institution(db, institution):
    """Delete everything belonging to an institution, then the institution.
    Returns rows removed per table and the stored file keys, which the caller deletes after committing."""
    from app.models.elearning import StoredFile
    tenant = institution.id
    file_keys = [key for (key,) in db.query(StoredFile.storage_key).filter(StoredFile.institution_id == tenant).all()]
    users = select(User.id).where(User.institution_id == tenant).scalar_subquery()
    pending = _tenant_tables()
    removed = {}
    # Foreign keys decide the order; retrying in passes finds it without a hand-kept list.
    for _ in range(len(pending) + 2):
        if not pending:
            break
        still = []
        for table, user_columns in pending:
            conditions = ([table.c.institution_id == tenant] if 'institution_id' in table.c else []) + [c.in_(users) for c in user_columns]
            if table.name == 'users':
                conditions = [table.c.institution_id == tenant]
            statement = delete(table).where(or_(*conditions))
            savepoint = db.begin_nested()
            try:
                count = db.execute(statement).rowcount
                savepoint.commit()
                if count:
                    removed[table.name] = removed.get(table.name, 0) + count
            except IntegrityError:
                savepoint.rollback()
                still.append((table, user_columns))
        if len(still) == len(pending):
            names = ', '.join(sorted(t.name for t, _ in still))
            raise HTTPException(409, f'Some records could not be removed: {names}')
        pending = still
    db.delete(institution)
    db.flush()
    return removed, file_keys
