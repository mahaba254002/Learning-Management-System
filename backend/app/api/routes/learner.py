"""Learner portal extras: who's online, course search, and messages to students (students read, never reply)."""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.routes.learning import own_student, student_subjects
from app.api.routes.teaching import commit, enrolled_students, missing, staff, taught_class_ids, taught_subject_ids
from app.core.deps import AuthContext, require_role
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Enrollment, Student, Subject
from app.models.elearning import Notification
from app.models.learner import StudentMessage, StudentMessageRecipient
from app.models.structure import OfferingTeacher
from app.models.user import User, UserRole, UserStatus
from app.schemas.academic import Input
from app.services.audit_service import record_audit

router = APIRouter(prefix='/api', tags=['learner'])
student_role = require_role(UserRole.STUDENT)
ONLINE_MINUTES = 5
PAGE_SIZE = 20


def name(u):
    return f'{u.first_name} {u.last_name}'


# --- Who's online -----------------------------------------------------------------------------------

@router.get('/student/online')
def online(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    """Classmates and teachers active in the last five minutes. Only people who share a class or course."""
    student = own_student(db, ctx)
    since = datetime.now(timezone.utc) - timedelta(minutes=ONLINE_MINUTES)
    classes = scoped(db, Enrollment, ctx).filter(Enrollment.student_id == student.id, Enrollment.active.is_(True)).with_entities(Enrollment.class_id)
    classmates = scoped(db, Student, ctx).join(Enrollment, Enrollment.student_id == Student.id).filter(
        Enrollment.institution_id == ctx.institution_id, Enrollment.class_id.in_(classes), Enrollment.active.is_(True)).with_entities(Student.user_id)
    subjects = student_subjects(db, student, ctx)
    leads = subjects.with_entities(Subject.teacher_id)
    co = db.query(OfferingTeacher.user_id).filter(OfferingTeacher.institution_id == ctx.institution_id,
                                                  OfferingTeacher.subject_id.in_(subjects.with_entities(Subject.id)))
    rows = scoped(db, User, ctx).filter(User.id != ctx.user_id, User.status == UserStatus.ACTIVE, User.last_seen_at >= since,
                                        or_(User.id.in_(classmates), User.id.in_(leads), User.id.in_(co))).order_by(User.last_seen_at.desc()).all()
    people = [dict(id=u.id, name=name(u), teacher=u.role != UserRole.STUDENT) for u in rows]
    people.sort(key=lambda p: (not p['teacher'], p['name']))
    return dict(minutes=ONLINE_MINUTES, count=len(people), people=people[:12])


# --- Course search ----------------------------------------------------------------------------------

@router.get('/student/course-search')
def course_search(q: str = Query('', max_length=80), page: int = Query(1, ge=1, le=500),
                  db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    """Every course offered this institution, so a student can see what exists; only their own courses open."""
    student = own_student(db, ctx)
    mine = {s.id for s in student_subjects(db, student, ctx).all()}
    query = scoped(db, Subject, ctx).join(AcademicClass, AcademicClass.id == Subject.class_id).join(User, User.id == Subject.teacher_id)
    term = q.strip()
    if term:
        like = f"%{term.replace('%', '').replace('_', '')}%"
        query = query.filter(or_(Subject.name.ilike(like), AcademicClass.name.ilike(like)))
    total = query.count()
    rows = query.with_entities(Subject, AcademicClass, User).order_by(Subject.name, AcademicClass.name).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all()
    return dict(total=total, page=page, pages=max(1, -(-total // PAGE_SIZE)), results=[
        dict(id=s.id, name=s.name, class_name=c.name, academic_year=c.academic_year, teacher_name=name(u), mine=s.id in mine)
        for s, c, u in rows])


# --- Messages to students ---------------------------------------------------------------------------

def message_view(m, sender, **extra):
    return dict(id=m.id, title=m.title, body=m.body, audience=m.audience, class_id=m.class_id,
                sender_name=name(sender) if sender else '', sent_at=m.created_at, **extra)


@router.get('/student/messages')
def inbox(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    rows = scoped(db, StudentMessageRecipient, ctx).filter(StudentMessageRecipient.user_id == ctx.user_id).join(
        StudentMessage, StudentMessage.id == StudentMessageRecipient.message_id).join(User, User.id == StudentMessage.sender_id).with_entities(
        StudentMessageRecipient, StudentMessage, User).order_by(StudentMessage.created_at.desc()).limit(100).all()
    return dict(unread=sum(1 for r, _, _ in rows if r.read_at is None),
                messages=[message_view(m, u, read=r.read_at is not None) for r, m, u in rows])


@router.post('/student/messages/{message_id}/read', status_code=204)
def mark_read(message_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    row = scoped(db, StudentMessageRecipient, ctx).filter_by(message_id=message_id, user_id=ctx.user_id).first()
    if not row:
        missing()
    if row.read_at is None and not ctx.actor_user_id:
        row.read_at = datetime.now(timezone.utc)
        scoped(db, Notification, ctx).filter_by(user_id=ctx.user_id, ref=f'student-message:{message_id}', read_at=None).update(
            {Notification.read_at: row.read_at}, synchronize_session=False)
        commit(db)


def allowed_classes(db, ctx):
    q = scoped(db, AcademicClass, ctx)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(AcademicClass.id.in_(taught_class_ids(db, ctx)))
    return q


@router.get('/teaching/student-messages/audiences')
def audiences(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """Classes this person may message, with their students. Teachers: classes they teach. Admins: every class."""
    out = []
    for c in allowed_classes(db, ctx).order_by(AcademicClass.academic_year.desc(), AcademicClass.name).all():
        students = enrolled_students(db, c.id, ctx).order_by(User.first_name, User.last_name).all()
        out.append(dict(id=c.id, name=c.name, academic_year=c.academic_year,
                        students=[dict(user_id=u.id, name=name(u), admission_number=s.admission_number) for s, u in students]))
    return out


class MessageInput(Input):
    class_id: uuid.UUID
    student_user_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=160)
    body: str = Field(min_length=1, max_length=4000)


@router.post('/teaching/student-messages', status_code=201)
def send(body: MessageInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    cls = allowed_classes(db, ctx).filter(AcademicClass.id == body.class_id).first()
    if not cls:
        missing()
    roster = enrolled_students(db, cls.id, ctx)
    if body.student_user_id:
        roster = roster.filter(User.id == body.student_user_id)
    recipients = [u for _, u in roster.all()]
    if not recipients:
        raise HTTPException(422, 'That student is not in this class.' if body.student_user_id else 'This class has no students yet.')
    message = StudentMessage(id=uuid.uuid4(), institution_id=ctx.institution_id, sender_id=ctx.user_id, class_id=cls.id,
                             audience='STUDENT' if body.student_user_id else 'CLASS', title=body.title.strip(), body=body.body.strip())
    db.add(message)
    db.flush()
    for u in recipients:
        db.add(StudentMessageRecipient(institution_id=ctx.institution_id, message_id=message.id, user_id=u.id))
        db.add(Notification(institution_id=ctx.institution_id, user_id=u.id, ref=f'student-message:{message.id}',
                            title=f'Message: {message.title}'[:200], body=message.body[:500], link='/student/messages'))
    record_audit(db, ctx, 'student_message.sent', message.id, ctx.institution_id, f'{message.audience} {cls.name}: {len(recipients)} recipient(s)')
    commit(db)
    return dict(id=message.id, recipients=len(recipients))


@router.get('/teaching/student-messages')
def sent(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """Teachers see what they sent. Admins see every message in the institution, read-only."""
    q = scoped(db, StudentMessage, ctx)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(StudentMessage.sender_id == ctx.user_id)
    rows = q.join(User, User.id == StudentMessage.sender_id).join(AcademicClass, AcademicClass.id == StudentMessage.class_id).with_entities(
        StudentMessage, User, AcademicClass).order_by(StudentMessage.created_at.desc()).limit(200).all()
    ids = [m.id for m, _, _ in rows]
    recipients = {}
    for r, u in scoped(db, StudentMessageRecipient, ctx).filter(StudentMessageRecipient.message_id.in_(ids)).join(
            User, User.id == StudentMessageRecipient.user_id).with_entities(StudentMessageRecipient, User).all():
        recipients.setdefault(r.message_id, []).append((r, u))
    out = []
    for m, sender, cls in rows:
        people = recipients.get(m.id, [])
        out.append(message_view(m, sender, class_name=cls.name, recipients=len(people), read=sum(1 for r, _ in people if r.read_at),
                                student_name=name(people[0][1]) if m.audience == 'STUDENT' and people else None))
    return out
