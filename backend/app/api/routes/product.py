"""Tenant configuration, class supervision and platform subscription operations."""
import uuid
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.deps import AuthContext, require_platform_admin, require_role, require_tenant_user
from app.db.session import get_db
from app.models.institution import Institution, InstitutionStatus
from app.models.user import User, UserRole
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.subscription import Subscription, SubscriptionPayment
from app.schemas.academic import Input, StudentAccessInput
from app.services.subscriptions import kenya_today, subscription_view
from app.services.learning_settings import LearningSettings, learning_settings, grade_label
from app.services.audit_service import record_audit
from app.api.routes.teaching import commit, staff, get_class, enrolled_students, scoped, ensure_staff
from app.api.routes.administration import institution_view, user_page

router = APIRouter(prefix="/api", tags=["Institution operations"])
institution_admin = require_role(UserRole.INSTITUTION_ADMIN)


@router.get("/teaching/overview")
def teaching_overview(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    ensure_staff(db, ctx)
    assigned = scoped(db, Subject, ctx)
    visible = scoped(db, AcademicClass, ctx)
    from app.models.pilot import AcademicYear
    closed_years = scoped(db, AcademicYear, ctx).filter_by(status='CLOSED').with_entities(AcademicYear.name)
    visible = visible.filter(AcademicClass.academic_year.not_in(closed_years))
    if ctx.role == UserRole.TEACHER:
        assigned = assigned.filter(Subject.teacher_id == ctx.user_id)
        visible = visible.filter(or_(AcademicClass.supervisor_id == ctx.user_id, AcademicClass.id.in_(assigned.with_entities(Subject.class_id))))
    counts = scoped(db, Enrollment, ctx).filter(Enrollment.active.is_(True)).with_entities(Enrollment.class_id, func.count(Enrollment.student_id).label("students")).group_by(Enrollment.class_id).subquery()
    class_counts = visible.outerjoin(counts, counts.c.class_id == AcademicClass.id).with_entities(AcademicClass.name, AcademicClass.academic_year, func.coalesce(counts.c.students, 0)).order_by(AcademicClass.name).all()
    return dict(enrollment_by_class=[dict(name=f'{name} · {year}', students=total) for name, year, total in class_counts])


@router.get("/platform/institution-directory")
def institution_directory(search: str = Query("", max_length=100), status: InstitutionStatus | None = None, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                          db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    query = db.query(Institution).outerjoin(Subscription, Subscription.institution_id == Institution.id)
    if search:
        term = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.filter(or_(Institution.name.ilike(term, escape='\\'), Institution.code.ilike(term, escape='\\'), Institution.official_email.ilike(term, escape='\\'), Institution.phone.ilike(term, escape='\\')))
    if status: query = query.filter(Institution.status == status)
    total = query.count()
    items = query.with_entities(Institution, Subscription).order_by(Institution.created_at.desc(), Institution.id).offset(offset).limit(limit).all()
    admins = {}
    ids = [row.id for row, _ in items]
    for user in db.query(User).filter(User.institution_id.in_(ids), User.role == UserRole.INSTITUTION_ADMIN).order_by(User.created_at, User.id).all():
        admins.setdefault(user.institution_id, []).append(dict(id=user.id, name=f"{user.first_name} {user.last_name}", email=user.email, status=user.status))
    return dict(total=total, items=[dict(**institution_view(row), subscription_status=subscription_view(subscription)["status"],
        next_due_date=subscription.next_due_date if subscription else None, admins=admins.get(row.id, [])) for row, subscription in items])


@router.get("/platform/subscription-summary")
def subscription_summary(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    counts = {"CURRENT": 0, "GRACE": 0, "FROZEN": 0, "DISABLED": 0}
    today = kenya_today()
    for row in db.query(Subscription).yield_per(500):
        counts[subscription_view(row, today)["status"]] += 1
    counts["NOT_CONFIGURED"] = db.query(Institution).count() - sum(counts.values())
    received = db.query(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).filter(
        SubscriptionPayment.paid_on >= today.replace(day=1), SubscriptionPayment.paid_on <= today).scalar()
    return dict(subscription_status=counts, payments_recorded_this_month=received, currency="KES")


@router.get("/institution/learning-settings")
def read_learning_settings(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    return learning_settings(db.get(Institution, ctx.institution_id))


@router.put("/institution/learning-settings")
def save_learning_settings(body: LearningSettings, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    row = db.get(Institution, ctx.institution_id)
    from app.services.academic_configuration import academic_configuration
    if row.academic_configuration and not academic_configuration(row)['institution_policy_edits']:
        raise HTTPException(403, 'Academic policy is managed by platform admin. Request a configuration change.')
    row.learning_settings = body.model_dump()
    record_audit(db, ctx, "institution.learning_settings_updated", row.id, row.id)
    commit(db)
    return learning_settings(row)


@router.put("/institution/students/{user_id}/login")
def student_access(user_id: uuid.UUID, body: StudentAccessInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    # Identity changes are institution-admin operations and immediately revoke sessions.
    from datetime import datetime, timezone
    user = scoped(db, User, ctx).filter(User.id == user_id, User.role == UserRole.STUDENT).with_for_update().first()
    if not user:
        raise HTTPException(404, "Student not found")
    user.email = body.email
    user.student_login_method, user.student_login_id = body.login_method, body.login_id
    user.password_changed_at = datetime.now(timezone.utc)
    record_audit(db, ctx, "student.login_updated", user.id, ctx.institution_id)
    commit(db)
    return {"message": "Student login updated. Existing sessions were revoked."}


@router.post("/institution/students/{user_id}/reset-password")
def reset_student_password(user_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    from datetime import datetime, timezone
    from app.core.security import hash_password
    from app.services.password_service import generate_temporary_password
    user = scoped(db, User, ctx).filter(User.id == user_id, User.role == UserRole.STUDENT).with_for_update().first()
    if not user:
        raise HTTPException(404, "Student not found")
    password = generate_temporary_password()
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    record_audit(db, ctx, "student.password_reset", user.id, ctx.institution_id)
    commit(db)
    return dict(temporary_password=password, login_method=user.student_login_method,
                login_identity=user.email if user.student_login_method == "EMAIL" else user.student_login_id)


@router.get("/teaching/classes/{class_id}/report")
def class_report(class_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    cls = get_class(db, class_id, ctx, supervise=True)
    people = enrolled_students(db, class_id, ctx).order_by(User.first_name, User.last_name).all()
    rows = scoped(db, Score, ctx).join(Coursework, Coursework.id == Score.coursework_id).join(Subject, Subject.id == Coursework.subject_id).filter(
        Coursework.institution_id == ctx.institution_id, Subject.institution_id == ctx.institution_id, Subject.class_id == cls.id,
        Score.student_id.in_([s.id for s, _ in people])).with_entities(Score, Coursework, Subject).all()
    settings = learning_settings(db.get(Institution, ctx.institution_id))
    marks = {}
    for mark, work, subject in rows:
        marks.setdefault(mark.student_id, []).append(dict(subject=subject.name, assessment=work.title, score=mark.score,
            maximum=work.max_score, competency_label=mark.competency_label, assessment_mode=work.assessment_mode, grade=grade_label(mark.score, work.max_score, settings, work.grading_bands), released=work.grades_released))
    return dict(class_name=cls.name, students=[dict(id=s.id, name=f"{u.first_name} {u.last_name}", admission_number=s.admission_number, marks=marks.get(s.id, [])) for s, u in people])


class SubscriptionInput(Input):
    monthly_fee: Decimal = Field(ge=0, le=100000000, max_digits=12, decimal_places=2)
    next_due_date: date | None = None
    grace_days: int = Field(default=5, ge=0, le=90)
    enforcement_enabled: bool = False
    manually_frozen: bool = False
    support_email: str = Field(default="", max_length=255)
    expected_due_date: date | None = None

    @model_validator(mode="after")
    def enforce_configuration(self):
        import re
        if self.support_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.support_email):
            raise ValueError("Enter a valid support email")
        if (self.enforcement_enabled or self.manually_frozen) and (not self.next_due_date or not self.support_email):
            raise ValueError("A due date and support email are required before enforcing access")
        return self


class PaymentInput(Input):
    amount: Decimal = Field(gt=0, le=100000000, max_digits=12, decimal_places=2)
    reference: str = Field(min_length=1, max_length=100)
    paid_on: date
    expected_due_date: date | None
    next_due_date: date


def get_institution(db, institution_id):
    row = db.get(Institution, institution_id)
    if not row:
        raise HTTPException(404, "Institution not found")
    return row


def billing_detail(db, institution_id):
    subscription = db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    payments = db.query(SubscriptionPayment).filter(SubscriptionPayment.institution_id == institution_id).order_by(SubscriptionPayment.created_at.desc()).limit(50).all()
    return dict(**subscription_view(subscription), currency="KES", payments=[dict(id=p.id, amount=p.amount, reference=p.reference,
        paid_on=p.paid_on, previous_due_date=p.previous_due_date, next_due_date=p.next_due_date) for p in payments])


@router.get("/institution/subscription")
def institution_subscription(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    if ctx.role == UserRole.INSTITUTION_ADMIN:
        return billing_detail(db, ctx.institution_id)
    state = subscription_view(db.query(Subscription).filter(Subscription.institution_id == ctx.institution_id).first())
    return {key: state[key] for key in ("status", "frozen", "next_due_date", "freeze_date", "support_email")}


@router.get("/platform/institutions/{institution_id}/detail")
def institution_detail(institution_id: uuid.UUID, search: str = Query("", max_length=100), role: UserRole | None = None,
                       offset: int = Query(0, ge=0), db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    institution = get_institution(db, institution_id)
    counts = dict(db.query(User.role, func.count(User.id)).filter(User.institution_id == institution_id).group_by(User.role).all())
    attendance = dict(db.query(Attendance.status, func.count(Attendance.id)).filter(Attendance.institution_id == institution_id, Attendance.scope_key == "class").group_by(Attendance.status).all())
    return dict(institution=institution_view(institution), users_by_role=counts, attendance=attendance,
                billing=billing_detail(db, institution_id), users=user_page(db, institution_id, search, role, offset, 50))


@router.put("/platform/institutions/{institution_id}/subscription")
def configure_subscription(institution_id: uuid.UUID, body: SubscriptionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    # Serialize creation, configuration and payment recording on the parent row.
    db.query(Institution).filter(Institution.id == institution_id).with_for_update().one_or_none() or get_institution(db, institution_id)
    row = db.query(Subscription).filter(Subscription.institution_id == institution_id).first()
    if row and row.next_due_date != body.expected_due_date:
        raise HTTPException(409, "The due date changed. Reload before changing subscription configuration.")
    if not row:
        row = Subscription(institution_id=institution_id)
        db.add(row)
    for key, value in body.model_dump(exclude={"expected_due_date"}).items():
        setattr(row, key, value)
    record_audit(db, ctx, "subscription.configured", institution_id, institution_id, str(body.next_due_date))
    commit(db)
    return billing_detail(db, institution_id)


@router.post("/platform/institutions/{institution_id}/payments", status_code=201)
def record_payment(institution_id: uuid.UUID, body: PaymentInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    db.query(Institution).filter(Institution.id == institution_id).with_for_update().one_or_none() or get_institution(db, institution_id)
    row = db.query(Subscription).filter(Subscription.institution_id == institution_id).with_for_update().first()
    if not row:
        raise HTTPException(409, "Configure this subscription first")
    if row.next_due_date != body.expected_due_date:
        raise HTTPException(409, "The due date changed. Reload before recording this payment.")
    if body.paid_on > kenya_today() or (row.next_due_date and body.next_due_date <= row.next_due_date):
        raise HTTPException(422, "Payment date must not be in the future and the new due date must advance")
    payment = SubscriptionPayment(institution_id=institution_id, amount=body.amount, reference=body.reference, paid_on=body.paid_on,
        previous_due_date=row.next_due_date, next_due_date=body.next_due_date, recorded_by=str(ctx.actor_user_id or ctx.user_id))
    db.add(payment)
    row.next_due_date = body.next_due_date
    record_audit(db, ctx, "subscription.payment_recorded", institution_id, institution_id, f"KES {body.amount}; reference {body.reference}")
    commit(db)
    return billing_detail(db, institution_id)
