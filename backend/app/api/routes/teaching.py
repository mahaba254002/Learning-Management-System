"""Class supervision and subject teaching are separate authorization grants."""
import uuid
import json
from app.services.audit_service import record_audit
from datetime import date
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.institution import Institution
from app.models.curriculum import CourseRegistration, CatalogueUnit, CourseCompletion
from app.models.teacher import Teacher, TeacherStatus
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import ClassInput, CourseworkInput, EnrollInput, RegisterInput, ScoresInput, StudentEdit, StudentInput, SubjectInput
from app.schemas.teacher import TeacherSummary
from app.services.password_service import generate_temporary_password
from app.services.username_service import generate_username

router = APIRouter(prefix="/api", tags=["Teaching"])
staff = require_role(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN)
admin = require_role(UserRole.INSTITUTION_ADMIN)


def scoped(db, model, ctx):
    return db.query(model).filter(model.institution_id == ctx.institution_id)


def missing():
    raise HTTPException(404, "Record not found")


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Never disclose global email/username conflicts or another tenant's data.
        raise HTTPException(409, "Could not save these details. Check for duplicate or conflicting records.")


def check_revision(rows, expected):
    revision = json.dumps(sorted([[str(r.id), r.updated_at.isoformat()] for r in rows]), separators=(',', ':'))
    if expected is not None and expected != revision:
        raise HTTPException(409, 'These records changed in another session. Reload and review before saving; your recovery draft is retained.')


def active_teacher(db, teacher_id, ctx):
    found = scoped(db, Teacher, ctx).join(User, Teacher.user_id == User.id).filter(
        User.institution_id == ctx.institution_id, User.id == teacher_id,
        User.role == UserRole.TEACHER, User.status == UserStatus.ACTIVE,
        Teacher.status == TeacherStatus.ACTIVE,
    ).first()
    if not found:
        missing()


def ensure_staff(db, ctx):
    if ctx.role == UserRole.TEACHER:
        active_teacher(db, ctx.user_id, ctx)


def get_class(db, class_id, ctx, *, supervise=False, lock=False):
    ensure_staff(db, ctx)
    q = scoped(db, AcademicClass, ctx).filter(AcademicClass.id == class_id)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        permission = AcademicClass.supervisor_id == ctx.user_id
        if not supervise:
            taught = scoped(db, Subject, ctx).filter(Subject.teacher_id == ctx.user_id).with_entities(Subject.class_id)
            permission = or_(permission, AcademicClass.id.in_(taught))
        q = q.filter(permission)
    row = q.first()
    if not row:
        missing()
    if ctx.request_method and ctx.request_method not in {'GET', 'HEAD', 'OPTIONS'}:
        from app.services.academic_calendar import writable_year
        writable_year(db, ctx.institution_id, row.academic_year)
    if lock:
        row = q.with_for_update().first()
    return row


def get_subject(db, subject_id, ctx):
    ensure_staff(db, ctx)
    q = scoped(db, Subject, ctx).filter(Subject.id == subject_id)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(Subject.teacher_id == ctx.user_id)
    row = q.first()
    if not row:
        missing()
    if ctx.request_method and ctx.request_method not in {'GET', 'HEAD', 'OPTIONS'}:
        from app.services.academic_calendar import writable_year
        cls = scoped(db, AcademicClass, ctx).filter_by(id=row.class_id).one()
        writable_year(db, ctx.institution_id, cls.academic_year)
    return row


def get_coursework(db, coursework_id, ctx, *, lock=False):
    q = scoped(db, Coursework, ctx).filter(Coursework.id == coursework_id)
    row = (q.with_for_update() if lock else q).first()
    if not row:
        missing()
    return row, get_subject(db, row.subject_id, ctx)


def enrolled_students(db, class_id, ctx):
    return scoped(db, Student, ctx).join(Enrollment, Enrollment.student_id == Student.id).join(User, User.id == Student.user_id).filter(
        Enrollment.institution_id == ctx.institution_id, Enrollment.class_id == class_id, Enrollment.active.is_(True),
        User.institution_id == ctx.institution_id, User.role == UserRole.STUDENT,
    ).with_entities(Student, User)


def subject_students(db, subject, ctx):
    query = enrolled_students(db, subject.class_id, ctx)
    if subject.registration_mode == 'INDIVIDUAL':
        registered = scoped(db, CourseRegistration, ctx).filter_by(subject_id=subject.id, active=True).with_entities(CourseRegistration.student_id)
        query = query.filter(Student.id.in_(registered))
    return query


def class_links(db, ctx, payload):
    from app.api.routes.curriculum import validate_links
    validate_links(db, ctx.institution_id, payload.programme_id, payload.level_id)


def offering_values(db, ctx, payload, cls, current=None):
    from app.api.routes.curriculum import owned
    from app.services.academic_configuration import academic_configuration
    unit = owned(db, CatalogueUnit, payload.catalogue_id, ctx.institution_id)
    from app.models.pilot import AcademicPeriod, AcademicYear
    period = owned(db, AcademicPeriod, payload.period_id, ctx.institution_id)
    if period and db.get(AcademicYear, period.year_id).name != cls.academic_year: raise HTTPException(422, 'Offering period must belong to its group’s academic year')
    if unit and unit.programme_id and unit.programme_id != cls.programme_id: raise HTTPException(422, 'Catalogue course must match the cohort programme')
    if unit and unit.level_id and unit.level_id != cls.level_id: raise HTTPException(422, 'Catalogue course must match the cohort study level')
    mode = payload.registration_mode or (current.registration_mode if current else academic_configuration(db.get(Institution, ctx.institution_id))['registration_mode'])
    if current and mode != current.registration_mode: raise HTTPException(409, 'Registration mode is fixed for an existing offering. Create a new offering to change enrollment rules.')
    historical = current and (scoped(db, Coursework, ctx).filter_by(subject_id=current.id).first() or scoped(db, CourseCompletion, ctx).filter_by(subject_id=current.id).first())
    if current and current.catalogue_id != payload.catalogue_id and historical:
        raise HTTPException(409, 'This offering has assessments. Its catalogue identity cannot be changed.')
    if current and current.period_id != payload.period_id and historical: raise HTTPException(409, 'An offering with academic history cannot be moved to another period')
    return dict(name=payload.name, teacher_id=payload.teacher_id, catalogue_id=payload.catalogue_id, period_id=payload.period_id, registration_mode=mode)


def assessment_values(db, ctx, payload, subject, current=None):
    from app.models.pilot import AcademicPeriod, AcademicYear
    if payload.period_id:
        period = scoped(db, AcademicPeriod, ctx).filter_by(id=payload.period_id).first()
        group = scoped(db, AcademicClass, ctx).filter_by(id=subject.class_id).one()
        year = scoped(db, AcademicYear, ctx).filter_by(name=group.academic_year).first()
        if not period or not year or period.year_id != year.id or (subject.period_id and subject.period_id != period.id):
            raise HTTPException(422, "Choose a period within this offering’s academic year and period")
    from app.services.academic_configuration import academic_configuration
    policy = academic_configuration(db.get(Institution, ctx.institution_id))
    mode = payload.assessment_mode or (current.assessment_mode if current else ('COMPETENCY' if policy['assessment_policy'] == 'COMPETENCY' else 'NUMERIC'))
    if policy['assessment_policy'] not in {'MIXED', mode}: raise HTTPException(422, 'This assessment type is not enabled by the institution policy')
    if current and mode != current.assessment_mode: raise HTTPException(409, 'Create a new assessment to change its method; existing history is preserved.')
    return dict(**payload.model_dump(exclude={'expected_updated_at', 'assessment_mode'}), assessment_mode=mode,
        rubric_labels=current.rubric_labels if current else (policy['competency_labels'] if mode == 'COMPETENCY' else []))


def student_view(student, user):
    return dict(id=student.id, user_id=user.id, admission_number=student.admission_number, first_name=user.first_name,
                last_name=user.last_name, email=user.email, phone=student.phone,
                login_method=user.student_login_method, login_id=user.student_login_id)


def class_view(row, ctx, year_status=None):
    return dict(id=row.id, name=row.name, academic_year=row.academic_year, supervisor_id=row.supervisor_id,
                academic_year_status=year_status or 'UNCONFIGURED',
                programme_id=row.programme_id, level_id=row.level_id,
                can_view_class_register=ctx.role == UserRole.INSTITUTION_ADMIN or row.supervisor_id == ctx.user_id,
                can_manage=year_status != 'CLOSED' and not ctx.read_only and (ctx.role == UserRole.INSTITUTION_ADMIN or row.supervisor_id == ctx.user_id))


@router.get("/teacher/profile")
def profile(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_role(UserRole.TEACHER))):
    active_teacher(db, ctx.user_id, ctx)
    teacher, user = scoped(db, Teacher, ctx).join(User, User.id == Teacher.user_id).filter(
        User.institution_id == ctx.institution_id, User.id == ctx.user_id).with_entities(Teacher, User).one()
    return TeacherSummary.from_orm_join(teacher, user)


@router.get("/teaching/classes")
def classes(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    ensure_staff(db, ctx)
    q = scoped(db, AcademicClass, ctx)
    if ctx.role == UserRole.TEACHER:
        taught = scoped(db, Subject, ctx).filter(Subject.teacher_id == ctx.user_id).with_entities(Subject.class_id)
        q = q.filter(or_(AcademicClass.supervisor_id == ctx.user_id, AcademicClass.id.in_(taught)))
    from app.models.pilot import AcademicYear
    statuses = {y.name: y.status for y in scoped(db, AcademicYear, ctx).all()}
    return [class_view(row, ctx, statuses.get(row.academic_year)) for row in q.order_by(AcademicClass.academic_year.desc(), AcademicClass.name).all()]


@router.post("/teaching/classes", status_code=201)
def create_class(payload: ClassInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.services.academic_calendar import writable_year
    writable_year(db, ctx.institution_id, payload.academic_year)
    class_links(db, ctx, payload)
    if payload.supervisor_id:
        active_teacher(db, payload.supervisor_id, ctx)
    row = AcademicClass(institution_id=ctx.institution_id, **payload.model_dump())
    row.id = uuid.uuid4()
    db.add(row)
    record_audit(db, ctx, 'class.created', row.id, ctx.institution_id)
    commit(db)
    return class_view(row, ctx)


@router.put("/teaching/classes/{class_id}")
def update_class(class_id: uuid.UUID, payload: ClassInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_class(db, class_id, ctx, lock=True)
    class_links(db, ctx, payload)
    if row.programme_id != payload.programme_id and scoped(db, Subject, ctx).filter_by(class_id=row.id).first():
        raise HTTPException(409, 'This group has teaching allocations. Its programme cannot be reassigned.')
    from app.services.academic_calendar import writable_year
    writable_year(db, ctx.institution_id, payload.academic_year)
    if row.academic_year != payload.academic_year:
        raise HTTPException(409, 'Create a new class for another year. Use promotion to preserve the original academic history.')
    if payload.supervisor_id:
        active_teacher(db, payload.supervisor_id, ctx)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    record_audit(db, ctx, 'class.updated', row.id, ctx.institution_id)
    commit(db)
    return class_view(row, ctx)


@router.get("/teaching/subjects")
def subjects(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    ensure_staff(db, ctx)
    q = scoped(db, Subject, ctx).join(AcademicClass, AcademicClass.id == Subject.class_id).filter(AcademicClass.institution_id == ctx.institution_id)
    if ctx.role == UserRole.TEACHER:
        q = q.filter(Subject.teacher_id == ctx.user_id)
    from app.models.pilot import AcademicYear
    statuses = {y.name: y.status for y in scoped(db, AcademicYear, ctx).all()}
    return [dict(id=s.id, class_id=c.id, name=s.name, class_name=c.name, academic_year=c.academic_year, teacher_id=s.teacher_id, catalogue_id=s.catalogue_id, period_id=s.period_id, registration_mode=s.registration_mode, academic_year_status=statuses.get(c.academic_year, 'UNCONFIGURED'))
            for s, c in q.with_entities(Subject, AcademicClass).order_by(AcademicClass.name, Subject.name).all()]


@router.post("/teaching/classes/{class_id}/subjects", status_code=201)
def create_subject(class_id: uuid.UUID, payload: SubjectInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.services.progression import lock_entry
    lock_entry(db, ctx.institution_id)
    cls = get_class(db, class_id, ctx, lock=True)
    active_teacher(db, payload.teacher_id, ctx)
    row = Subject(institution_id=ctx.institution_id, class_id=class_id, **offering_values(db, ctx, payload, cls))
    row.id = uuid.uuid4()
    from app.services.progression import assert_course
    if row.registration_mode == "COHORT":
        for student, _ in enrolled_students(db, class_id, ctx).all(): assert_course(db, ctx.institution_id, student.id, row)
    db.add(row)
    record_audit(db, ctx, 'subject.created', row.id, ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.put("/teaching/subjects/{subject_id}")
def update_subject(subject_id: uuid.UUID, payload: SubjectInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.services.progression import lock_entry
    lock_entry(db, ctx.institution_id)
    row = get_subject(db, subject_id, ctx)
    active_teacher(db, payload.teacher_id, ctx)
    cls = get_class(db, row.class_id, ctx, lock=True)
    values = offering_values(db, ctx, payload, cls, row)
    from app.services.progression import assert_course
    if values.get("catalogue_id") != row.catalogue_id:
        candidate = Subject(id=row.id, institution_id=ctx.institution_id, class_id=row.class_id, **values)
        for student, _ in subject_students(db, row, ctx).all(): assert_course(db, ctx.institution_id, student.id, candidate)
    for key, value in values.items(): setattr(row, key, value)
    record_audit(db, ctx, 'subject.updated', row.id, ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.get("/teaching/classes/{class_id}/students")
def roster(class_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    cls = get_class(db, class_id, ctx)
    people = enrolled_students(db, class_id, ctx)
    if ctx.role == UserRole.TEACHER and cls.supervisor_id != ctx.user_id:
        offerings = scoped(db, Subject, ctx).filter_by(class_id=class_id, teacher_id=ctx.user_id)
        if not offerings.filter_by(registration_mode='COHORT').first():
            registered = scoped(db, CourseRegistration, ctx).filter(CourseRegistration.subject_id.in_(offerings.with_entities(Subject.id)), CourseRegistration.active.is_(True)).with_entities(CourseRegistration.student_id)
            people = people.filter(Student.id.in_(registered))
    return [student_view(s, u) for s, u in people.order_by(User.first_name, User.last_name).all()]


@router.post("/teaching/classes/{class_id}/students", status_code=201)
def create_student(class_id: uuid.UUID, payload: StudentInput, response: Response, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    from app.services.progression import lock_entry
    lock_entry(db, ctx.institution_id)
    get_class(db, class_id, ctx, supervise=True, lock=True)
    institution = db.query(Institution).filter(Institution.id == ctx.institution_id).one()
    from app.services.progression import assert_group
    assert_group(db, ctx.institution_id, None, class_id)
    temporary_password = generate_temporary_password()
    try:
        username = generate_username(db=db, first_name=payload.first_name, last_name=payload.last_name, institution_code=institution.code)
    except (ValueError, RuntimeError):
        raise HTTPException(400, "Names must contain letters or digits suitable for a username")
    user = User(institution_id=ctx.institution_id, username=username, first_name=payload.first_name,
                last_name=payload.last_name, email=payload.email, role=UserRole.STUDENT, status=UserStatus.ACTIVE,
                password_hash=hash_password(temporary_password), must_change_password=True)
    user.student_login_method = payload.login_method
    user.student_login_id = payload.login_id
    db.add(user)
    try:
        db.flush()
        student = Student(institution_id=ctx.institution_id, user_id=user.id, admission_number=payload.admission_number, phone=payload.phone)
        db.add(student)
        db.flush()
        db.add(Enrollment(institution_id=ctx.institution_id, class_id=class_id, student_id=student.id))
        record_audit(db, ctx, 'student.created', student.id, ctx.institution_id)
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Could not create this student. Check the details or contact your administrator.")
    response.headers["Cache-Control"] = "no-store"
    return dict(student=student_view(student, user), username=username, login_method=user.student_login_method,
                login_identity=user.email if user.student_login_method == "EMAIL" else user.student_login_id,
                temporary_password=temporary_password)


@router.post("/teaching/classes/{class_id}/enrollments")
def enroll(class_id: uuid.UUID, payload: EnrollInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    from app.services.progression import lock_entry
    lock_entry(db, ctx.institution_id)
    get_class(db, class_id, ctx, supervise=True, lock=True)
    student = scoped(db, Student, ctx).filter(Student.admission_number == payload.admission_number).first()
    if not student:
        missing()
    row = scoped(db, Enrollment, ctx).filter(Enrollment.class_id == class_id, Enrollment.student_id == student.id).first()
    if not row or not row.active:
        from app.services.progression import assert_group, assert_transition
        assert_transition(db, ctx.institution_id, student.id, class_id)
        assert_group(db, ctx.institution_id, student.id, class_id)
    if row:
        row.active = True
    else:
        db.add(Enrollment(institution_id=ctx.institution_id, class_id=class_id, student_id=student.id))
    commit(db)
    return {"message": "Student enrolled"}


@router.put("/teaching/classes/{class_id}/students/{student_id}")
def edit_student(class_id: uuid.UUID, student_id: uuid.UUID, payload: StudentEdit, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_class(db, class_id, ctx, supervise=True, lock=True)
    row = enrolled_students(db, class_id, ctx).filter(Student.id == student_id).first()
    if not row:
        missing()
    student, user = row
    user.first_name, user.last_name, student.phone = payload.first_name, payload.last_name, payload.phone
    commit(db)
    return student_view(student, user)


@router.delete("/teaching/classes/{class_id}/enrollments/{student_id}")
def remove_enrollment(class_id: uuid.UUID, student_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_class(db, class_id, ctx, supervise=True, lock=True)
    row = scoped(db, Enrollment, ctx).filter(Enrollment.class_id == class_id, Enrollment.student_id == student_id).first()
    if not row:
        missing()
    row.active = False  # Keep attendance, marks and the student account intact.
    commit(db)
    return {"message": "Student removed from class"}


def attendance_scope(db, class_id, subject_id, ctx, *, lock=False):
    get_class(db, class_id, ctx, supervise=subject_id is None, lock=lock)
    if subject_id is not None:
        subject = get_subject(db, subject_id, ctx)
        if subject.class_id != class_id:
            missing()
    return str(subject_id) if subject_id else "class"


@router.get("/teaching/classes/{class_id}/attendance")
def attendance(class_id: uuid.UUID, day: date, subject_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    scope = attendance_scope(db, class_id, subject_id, ctx)
    return scoped(db, Attendance, ctx).filter(Attendance.class_id == class_id, Attendance.scope_key == scope, Attendance.day == day).all()


@router.put("/teaching/classes/{class_id}/attendance")
def save_attendance(class_id: uuid.UUID, payload: RegisterInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    scope = attendance_scope(db, class_id, payload.subject_id, ctx, lock=True)
    if payload.day > date.today():
        raise HTTPException(400, "Attendance cannot be recorded for a future date")
    roster_query = subject_students(db, get_subject(db, payload.subject_id, ctx), ctx) if payload.subject_id else enrolled_students(db, class_id, ctx)
    allowed = {s.id for s, _ in roster_query.all()}
    if any(e.student_id not in allowed for e in payload.entries):
        missing()
    existing = {r.student_id: r for r in scoped(db, Attendance, ctx).filter(
        Attendance.class_id == class_id, Attendance.scope_key == scope, Attendance.day == payload.day).all()}
    check_revision(existing.values(), payload.expected_revision)
    for entry in payload.entries:
        row = existing.get(entry.student_id)
        if row is None:
            row = Attendance(institution_id=ctx.institution_id, class_id=class_id, subject_id=payload.subject_id,
                             scope_key=scope, day=payload.day, student_id=entry.student_id)
            db.add(row)
        row.status, row.note = entry.status, entry.note
    record_audit(db, ctx, 'attendance.register_saved', class_id, ctx.institution_id, f'{payload.day}; {len(payload.entries)} entries')
    commit(db)
    return {"message": "Attendance saved"}


@router.get("/teaching/subjects/{subject_id}/coursework")
def coursework(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_subject(db, subject_id, ctx)
    return scoped(db, Coursework, ctx).filter(Coursework.subject_id == subject_id).order_by(Coursework.created_at.desc()).all()


@router.post("/teaching/subjects/{subject_id}/coursework", status_code=201)
def create_coursework(subject_id: uuid.UUID, payload: CourseworkInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    subject = get_subject(db, subject_id, ctx)
    row = Coursework(institution_id=ctx.institution_id, subject_id=subject_id, **assessment_values(db, ctx, payload, subject))
    db.add(row)
    commit(db)
    db.refresh(row)
    return row


@router.put("/teaching/coursework/{coursework_id}")
def edit_coursework(coursework_id: uuid.UUID, payload: CourseworkInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    row, subject = get_coursework(db, coursework_id, ctx, lock=True)
    if payload.expected_updated_at is not None and payload.expected_updated_at != row.updated_at.isoformat():
        raise HTTPException(409, 'This assessment changed in another session. Reload its saved version before editing.')
    if scoped(db, Score, ctx).filter(Score.coursework_id == row.id, Score.score > payload.max_score).first():
        raise HTTPException(400, "Maximum score cannot be lower than an existing score")
    for key, value in assessment_values(db, ctx, payload, subject, row).items():
        setattr(row, key, value)
    commit(db)
    db.refresh(row)
    return row


@router.get("/teaching/coursework/{coursework_id}/scores")
def scores(coursework_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_coursework(db, coursework_id, ctx)
    return scoped(db, Score, ctx).filter(Score.coursework_id == coursework_id).all()


class ResultsRelease(BaseModel):
    released: bool
    model_config = {"extra": "forbid"}


@router.put("/teaching/coursework/{coursework_id}/results-release")
def release_results(coursework_id: uuid.UUID, body: ResultsRelease, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, _ = get_coursework(db, coursework_id, ctx, lock=True)
    if body.released and not work.published:
        raise HTTPException(409, "Publish the assessment before releasing its results")
    work.grades_released = body.released
    record_audit(db, ctx, "assessment.results_released" if body.released else "assessment.results_withheld", work.id, ctx.institution_id)
    commit(db)
    return {"released": work.grades_released}


@router.put("/teaching/coursework/{coursework_id}/scores")
def save_scores(coursework_id: uuid.UUID, payload: ScoresInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = get_coursework(db, coursework_id, ctx, lock=True)
    get_class(db, subject.class_id, ctx, lock=True)
    allowed = {s.id for s, _ in subject_students(db, subject, ctx).all()}
    if any(e.student_id not in allowed for e in payload.entries):
        missing()
    if work.assessment_mode == 'COMPETENCY' and any(e.score is not None or e.competency_label not in work.rubric_labels for e in payload.entries):
        raise HTTPException(422, 'Choose an outcome from this assessment rubric')
    if work.assessment_mode == 'NUMERIC' and any(e.score is None for e in payload.entries): raise HTTPException(422, 'This assessment requires numeric marks')
    if any(e.score is not None and e.score > work.max_score for e in payload.entries):
        raise HTTPException(400, "A score cannot exceed the assessment maximum")
    existing = {r.student_id: r for r in scoped(db, Score, ctx).filter(Score.coursework_id == coursework_id).all()}
    check_revision(existing.values(), payload.expected_revision)
    for entry in payload.entries:
        row = existing.get(entry.student_id)
        if row is None:
            row = Score(institution_id=ctx.institution_id, coursework_id=coursework_id, student_id=entry.student_id)
            db.add(row)
        row.score, row.competency_label, row.feedback = entry.score, entry.competency_label, entry.feedback
    if work.grading_bands is None:
        from app.services.learning_settings import learning_settings
        work.grading_bands = learning_settings(db.get(Institution, ctx.institution_id))['grade_bands']
    record_audit(db, ctx, 'assessment.outcomes_saved', work.id, ctx.institution_id, f'{len(payload.entries)} outcomes; {work.assessment_mode}')
    commit(db)
    return {"message": "Scores saved"}


@router.get("/student/coursework")
def student_coursework(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_role(UserRole.STUDENT))):
    student = scoped(db, Student, ctx).filter(Student.user_id == ctx.user_id).first()
    if not student:
        return []
    from app.api.routes.learning import student_subjects
    enrolled = student_subjects(db, student, ctx).with_entities(Subject.id)
    rows = scoped(db, Coursework, ctx).join(Subject, Subject.id == Coursework.subject_id).filter(
        Subject.institution_id == ctx.institution_id, Subject.id.in_(enrolled), Coursework.published.is_(True),
    ).with_entities(Coursework, Subject).order_by(Coursework.created_at.desc()).all()
    marks = {s.coursework_id: s for s in scoped(db, Score, ctx).filter(Score.student_id == student.id).all()}
    return [dict(id=w.id, title=w.title, instructions=w.instructions, kind=w.kind, due_at=w.due_at,
                 max_score=w.max_score, subject_name=s.name,
                 grades_released=w.grades_released,
                 assessment_mode=w.assessment_mode, competency_label=marks[w.id].competency_label if w.grades_released and w.id in marks else None,
                 score=marks[w.id].score if w.grades_released and w.id in marks else None,
                 feedback=marks[w.id].feedback if w.grades_released and w.id in marks else "") for w, s in rows]


@router.get('/teaching/subjects/{subject_id}/periods')
def assessment_periods(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    from app.models.pilot import AcademicPeriod, AcademicYear
    subject = get_subject(db, subject_id, ctx)
    group = scoped(db, AcademicClass, ctx).filter_by(id=subject.class_id).one()
    year = scoped(db, AcademicYear, ctx).filter_by(name=group.academic_year).first()
    if not year: return []
    query = scoped(db, AcademicPeriod, ctx).filter_by(year_id=year.id)
    if subject.period_id: query = query.filter_by(id=subject.period_id)
    return [dict(id=p.id,name=p.name) for p in query.order_by(AcademicPeriod.start_date).all()]
