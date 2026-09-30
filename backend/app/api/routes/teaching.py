"""Class supervision and subject teaching are separate authorization grants."""
import uuid
from app.services.audit_service import record_audit
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, require_role
from app.core.security import hash_password
from app.db.session import get_db
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.institution import Institution
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
    row = (q.with_for_update() if lock else q).first()
    if not row:
        missing()
    return row


def get_subject(db, subject_id, ctx):
    ensure_staff(db, ctx)
    q = scoped(db, Subject, ctx).filter(Subject.id == subject_id)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(Subject.teacher_id == ctx.user_id)
    row = q.first()
    if not row:
        missing()
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


def student_view(student, user):
    return dict(id=student.id, admission_number=student.admission_number, first_name=user.first_name,
                last_name=user.last_name, email=user.email, phone=student.phone)


def class_view(row, ctx):
    return dict(id=row.id, name=row.name, academic_year=row.academic_year, supervisor_id=row.supervisor_id,
                can_manage=ctx.role == UserRole.INSTITUTION_ADMIN or row.supervisor_id == ctx.user_id)


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
    return [class_view(row, ctx) for row in q.order_by(AcademicClass.academic_year.desc(), AcademicClass.name).all()]


@router.post("/teaching/classes", status_code=201)
def create_class(payload: ClassInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
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
    return [dict(id=s.id, class_id=c.id, name=s.name, class_name=c.name, academic_year=c.academic_year, teacher_id=s.teacher_id)
            for s, c in q.with_entities(Subject, AcademicClass).order_by(AcademicClass.name, Subject.name).all()]


@router.post("/teaching/classes/{class_id}/subjects", status_code=201)
def create_subject(class_id: uuid.UUID, payload: SubjectInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    get_class(db, class_id, ctx)
    active_teacher(db, payload.teacher_id, ctx)
    row = Subject(institution_id=ctx.institution_id, class_id=class_id, **payload.model_dump())
    row.id = uuid.uuid4()
    db.add(row)
    record_audit(db, ctx, 'subject.created', row.id, ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.put("/teaching/subjects/{subject_id}")
def update_subject(subject_id: uuid.UUID, payload: SubjectInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(admin)):
    row = get_subject(db, subject_id, ctx)
    active_teacher(db, payload.teacher_id, ctx)
    row.name, row.teacher_id = payload.name, payload.teacher_id
    record_audit(db, ctx, 'subject.updated', row.id, ctx.institution_id)
    commit(db)
    return dict(id=row.id)


@router.get("/teaching/classes/{class_id}/students")
def roster(class_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_class(db, class_id, ctx)
    return [student_view(s, u) for s, u in enrolled_students(db, class_id, ctx).order_by(User.first_name, User.last_name).all()]


@router.post("/teaching/classes/{class_id}/students", status_code=201)
def create_student(class_id: uuid.UUID, payload: StudentInput, response: Response, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_class(db, class_id, ctx, supervise=True, lock=True)
    institution = db.query(Institution).filter(Institution.id == ctx.institution_id).one()
    temporary_password = generate_temporary_password()
    try:
        username = generate_username(db=db, first_name=payload.first_name, last_name=payload.last_name, institution_code=institution.code)
    except (ValueError, RuntimeError):
        raise HTTPException(400, "Names must contain letters or digits suitable for a username")
    user = User(institution_id=ctx.institution_id, username=username, first_name=payload.first_name,
                last_name=payload.last_name, email=payload.email, role=UserRole.STUDENT, status=UserStatus.ACTIVE,
                password_hash=hash_password(temporary_password), must_change_password=True)
    db.add(user)
    try:
        db.flush()
        student = Student(institution_id=ctx.institution_id, user_id=user.id, admission_number=payload.admission_number, phone=payload.phone)
        db.add(student)
        db.flush()
        db.add(Enrollment(institution_id=ctx.institution_id, class_id=class_id, student_id=student.id))
        commit(db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Could not create this student. Check the details or contact your administrator.")
    response.headers["Cache-Control"] = "no-store"
    return dict(student=student_view(student, user), username=username, temporary_password=temporary_password)


@router.post("/teaching/classes/{class_id}/enrollments")
def enroll(class_id: uuid.UUID, payload: EnrollInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_class(db, class_id, ctx, supervise=True, lock=True)
    student = scoped(db, Student, ctx).filter(Student.admission_number == payload.admission_number).first()
    if not student:
        missing()
    row = scoped(db, Enrollment, ctx).filter(Enrollment.class_id == class_id, Enrollment.student_id == student.id).first()
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
    allowed = {s.id for s, _ in enrolled_students(db, class_id, ctx).all()}
    if any(e.student_id not in allowed for e in payload.entries):
        missing()
    existing = {r.student_id: r for r in scoped(db, Attendance, ctx).filter(
        Attendance.class_id == class_id, Attendance.scope_key == scope, Attendance.day == payload.day).all()}
    for entry in payload.entries:
        row = existing.get(entry.student_id)
        if row is None:
            row = Attendance(institution_id=ctx.institution_id, class_id=class_id, subject_id=payload.subject_id,
                             scope_key=scope, day=payload.day, student_id=entry.student_id)
            db.add(row)
        row.status, row.note = entry.status, entry.note
    commit(db)
    return {"message": "Attendance saved"}


@router.get("/teaching/subjects/{subject_id}/coursework")
def coursework(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_subject(db, subject_id, ctx)
    return scoped(db, Coursework, ctx).filter(Coursework.subject_id == subject_id).order_by(Coursework.created_at.desc()).all()


@router.post("/teaching/subjects/{subject_id}/coursework", status_code=201)
def create_coursework(subject_id: uuid.UUID, payload: CourseworkInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_subject(db, subject_id, ctx)
    row = Coursework(institution_id=ctx.institution_id, subject_id=subject_id, **payload.model_dump())
    db.add(row)
    commit(db)
    db.refresh(row)
    return row


@router.put("/teaching/coursework/{coursework_id}")
def edit_coursework(coursework_id: uuid.UUID, payload: CourseworkInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    row, _ = get_coursework(db, coursework_id, ctx, lock=True)
    if scoped(db, Score, ctx).filter(Score.coursework_id == row.id, Score.score > payload.max_score).first():
        raise HTTPException(400, "Maximum score cannot be lower than an existing score")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    commit(db)
    db.refresh(row)
    return row


@router.get("/teaching/coursework/{coursework_id}/scores")
def scores(coursework_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_coursework(db, coursework_id, ctx)
    return scoped(db, Score, ctx).filter(Score.coursework_id == coursework_id).all()


@router.put("/teaching/coursework/{coursework_id}/scores")
def save_scores(coursework_id: uuid.UUID, payload: ScoresInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = get_coursework(db, coursework_id, ctx, lock=True)
    get_class(db, subject.class_id, ctx, lock=True)
    allowed = {s.id for s, _ in enrolled_students(db, subject.class_id, ctx).all()}
    if any(e.student_id not in allowed for e in payload.entries):
        missing()
    if any(e.score > work.max_score for e in payload.entries):
        raise HTTPException(400, "A score cannot exceed the assessment maximum")
    existing = {r.student_id: r for r in scoped(db, Score, ctx).filter(Score.coursework_id == coursework_id).all()}
    for entry in payload.entries:
        row = existing.get(entry.student_id)
        if row is None:
            row = Score(institution_id=ctx.institution_id, coursework_id=coursework_id, student_id=entry.student_id)
            db.add(row)
        row.score, row.feedback = entry.score, entry.feedback
    commit(db)
    return {"message": "Scores saved"}


@router.get("/student/coursework")
def student_coursework(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_role(UserRole.STUDENT))):
    student = scoped(db, Student, ctx).filter(Student.user_id == ctx.user_id).first()
    if not student:
        return []
    enrolled = scoped(db, Enrollment, ctx).filter(Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_entities(Enrollment.class_id)
    rows = scoped(db, Coursework, ctx).join(Subject, Subject.id == Coursework.subject_id).filter(
        Subject.institution_id == ctx.institution_id, Subject.class_id.in_(enrolled), Coursework.published.is_(True),
    ).with_entities(Coursework, Subject).order_by(Coursework.created_at.desc()).all()
    marks = {s.coursework_id: s for s in scoped(db, Score, ctx).filter(Score.student_id == student.id).all()}
    return [dict(id=w.id, title=w.title, instructions=w.instructions, kind=w.kind, due_at=w.due_at,
                 max_score=w.max_score, subject_name=s.name,
                 score=marks[w.id].score if w.id in marks else None,
                 feedback=marks[w.id].feedback if w.id in marks else "") for w, s in rows]
