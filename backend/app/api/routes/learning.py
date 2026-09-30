"""Student learning access is derived from the signed-in user and active enrollment."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.teaching import commit, enrolled_students, get_coursework, get_subject, missing, scoped, staff
from app.core.deps import AuthContext, require_role
from app.db.session import get_db
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.learning import CourseMaterial, Submission
from app.models.user import User, UserRole
from app.schemas.learning import MaterialInput, SubmissionInput

router = APIRouter(prefix="/api", tags=["Student learning"])
student_role = require_role(UserRole.STUDENT)


def own_student(db, ctx):
    student = scoped(db, Student, ctx).filter(Student.user_id == ctx.user_id).first()
    if not student:
        missing()
    return student


def student_subjects(db, student, ctx):
    enrolled = scoped(db, Enrollment, ctx).filter(Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_entities(Enrollment.class_id)
    return scoped(db, Subject, ctx).filter(Subject.class_id.in_(enrolled))


def student_subject(db, subject_id, student, ctx):
    row = student_subjects(db, student, ctx).filter(Subject.id == subject_id).first()
    if not row:
        missing()
    return row


def student_work(db, work_id, student, ctx, *, lock=False):
    q = scoped(db, Coursework, ctx).filter(Coursework.id == work_id, Coursework.published.is_(True))
    work = (q.with_for_update() if lock else q).first()
    if not work:
        missing()
    subject = student_subject(db, work.subject_id, student, ctx)
    # Lock the enrollment during writes so removal cannot race a submission.
    if lock:
        enrollment = scoped(db, Enrollment, ctx).filter(Enrollment.class_id == subject.class_id,
            Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_for_update().first()
        if not enrollment:
            missing()
    return work, subject


def as_utc(value):
    # SQLite's test dialect drops timezone info; production stores timestamptz.
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def submission_view(row):
    if row is None:
        return None
    return dict(id=row.id, answer=row.answer, link_url=row.link_url, status=row.status,
                submitted_at=as_utc(row.submitted_at), updated_at=as_utc(row.updated_at), is_late=row.is_late, version=row.version)


def material_view(row):
    return dict(id=row.id, subject_id=row.subject_id, title=row.title, body=row.body, link_url=row.link_url,
                published=row.published, created_at=as_utc(row.created_at), updated_at=as_utc(row.updated_at))


@router.get("/student/profile")
def profile(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    user = scoped(db, User, ctx).filter(User.id == ctx.user_id).one()
    classes = scoped(db, AcademicClass, ctx).join(Enrollment, Enrollment.class_id == AcademicClass.id).filter(
        Enrollment.institution_id == ctx.institution_id, Enrollment.student_id == student.id, Enrollment.active.is_(True)).all()
    return dict(first_name=user.first_name, last_name=user.last_name, username=user.username, email=user.email,
                admission_number=student.admission_number, phone=student.phone,
                classes=[dict(id=c.id, name=c.name, academic_year=c.academic_year) for c in classes])


@router.get("/student/subjects")
def subjects(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    rows = student_subjects(db, student, ctx).join(AcademicClass, Subject.class_id == AcademicClass.id).join(User, Subject.teacher_id == User.id).filter(
        AcademicClass.institution_id == ctx.institution_id, User.institution_id == ctx.institution_id,
    ).with_entities(Subject, AcademicClass, User).order_by(AcademicClass.name, Subject.name).all()
    return [dict(id=s.id, name=s.name, class_id=c.id, class_name=c.name, academic_year=c.academic_year,
                 teacher_name=f"{u.first_name} {u.last_name}") for s, c, u in rows]


@router.get("/student/attendance")
def attendance(subject_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    classes = scoped(db, Enrollment, ctx).filter(Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_entities(Enrollment.class_id)
    q = scoped(db, Attendance, ctx).filter(Attendance.student_id == student.id, Attendance.class_id.in_(classes))
    if subject_id is not None:
        student_subject(db, subject_id, student, ctx)
        q = q.filter(Attendance.subject_id == subject_id)
    return [dict(id=r.id, class_id=r.class_id, subject_id=r.subject_id, day=r.day, status=r.status, note=r.note)
            for r in q.order_by(Attendance.day.desc()).all()]


@router.get("/student/subjects/{subject_id}/materials")
def materials(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student_subject(db, subject_id, own_student(db, ctx), ctx)
    rows = scoped(db, CourseMaterial, ctx).filter(CourseMaterial.subject_id == subject_id, CourseMaterial.published.is_(True)).order_by(CourseMaterial.created_at.desc()).all()
    return [material_view(row) for row in rows]


@router.get("/student/assignments")
def assignments(subject_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    subjects_q = student_subjects(db, student, ctx)
    if subject_id is not None:
        student_subject(db, subject_id, student, ctx)
        subjects_q = subjects_q.filter(Subject.id == subject_id)
    rows = scoped(db, Coursework, ctx).join(Subject, Subject.id == Coursework.subject_id).filter(
        Subject.institution_id == ctx.institution_id, Coursework.subject_id.in_(subjects_q.with_entities(Subject.id)), Coursework.published.is_(True),
    ).with_entities(Coursework, Subject).order_by(Coursework.created_at.desc()).all()
    ids = [w.id for w, _ in rows]
    marks = {r.coursework_id: r for r in scoped(db, Score, ctx).filter(Score.student_id == student.id, Score.coursework_id.in_(ids)).all()}
    submissions = {r.coursework_id: r for r in scoped(db, Submission, ctx).filter(Submission.student_id == student.id, Submission.coursework_id.in_(ids)).all()}
    return [dict(id=w.id, subject_id=s.id, subject_name=s.name, class_id=s.class_id, title=w.title, instructions=w.instructions,
                 kind=w.kind, due_at=as_utc(w.due_at), max_score=w.max_score, allow_late_submissions=w.allow_late_submissions,
                 score=marks[w.id].score if w.id in marks else None, feedback=marks[w.id].feedback if w.id in marks else "",
                 submission=submission_view(submissions.get(w.id))) for w, s in rows]


@router.put("/student/assignments/{work_id}/submission")
def save_submission(work_id: uuid.UUID, payload: SubmissionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    work, _ = student_work(db, work_id, student, ctx, lock=True)
    if work.kind == "EXAM":
        raise HTTPException(400, "This examination does not accept online submissions")
    if scoped(db, Score, ctx).filter(Score.coursework_id == work.id, Score.student_id == student.id).first():
        raise HTTPException(409, "This assessment has already been graded")
    row = scoped(db, Submission, ctx).filter(Submission.coursework_id == work.id, Submission.student_id == student.id).first()
    if row and row.status == "SUBMITTED":
        raise HTTPException(409, "Your final submission has already been received")
    if payload.expected_version != (row.version if row else 0):
        raise HTTPException(409, "Your draft changed in another session. Reload the saved draft before continuing.")
    now = datetime.now(timezone.utc)
    is_late = bool(work.due_at and now > as_utc(work.due_at))
    if payload.submit and is_late and not work.allow_late_submissions:
        raise HTTPException(409, "The submission deadline has passed and late submissions are closed")
    if row is None:
        row = Submission(institution_id=ctx.institution_id, coursework_id=work.id, student_id=student.id, version=0)
        db.add(row)
    row.answer = payload.answer
    row.link_url = str(payload.link_url) if payload.link_url else None
    row.version += 1
    if payload.submit:
        row.status, row.submitted_at, row.is_late = "SUBMITTED", now, is_late
    else:
        row.status = "DRAFT"
    commit(db)
    db.refresh(row)
    return submission_view(row)


@router.get("/teaching/subjects/{subject_id}/materials")
def teacher_materials(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_subject(db, subject_id, ctx)
    return [material_view(row) for row in scoped(db, CourseMaterial, ctx).filter(CourseMaterial.subject_id == subject_id).order_by(CourseMaterial.created_at.desc()).all()]


@router.post("/teaching/subjects/{subject_id}/materials", status_code=201)
def create_material(subject_id: uuid.UUID, payload: MaterialInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    get_subject(db, subject_id, ctx)
    row = CourseMaterial(institution_id=ctx.institution_id, subject_id=subject_id, **payload.model_dump(mode="json"))
    db.add(row)
    commit(db)
    return material_view(row)


@router.put("/teaching/materials/{material_id}")
def update_material(material_id: uuid.UUID, payload: MaterialInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    row = scoped(db, CourseMaterial, ctx).filter(CourseMaterial.id == material_id).first()
    if not row:
        missing()
    get_subject(db, row.subject_id, ctx)
    for key, value in payload.model_dump(mode="json").items():
        setattr(row, key, value)
    commit(db)
    return material_view(row)


@router.get("/teaching/coursework/{work_id}/submissions")
def review_submissions(work_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = get_coursework(db, work_id, ctx)
    # Draft text is private to the student. Only final submissions reach staff.
    rows = scoped(db, Submission, ctx).filter(Submission.coursework_id == work.id, Submission.status == "SUBMITTED").all()
    roster = {s.id: u for s, u in enrolled_students(db, subject.class_id, ctx).all()}
    return [dict(**submission_view(row), student_id=row.student_id, student_name=f"{roster[row.student_id].first_name} {roster[row.student_id].last_name}")
            for row in rows if row.student_id in roster]
