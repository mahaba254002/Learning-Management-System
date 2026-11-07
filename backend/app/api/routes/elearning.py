"""E-learning: file uploads, online quizzes, course pages, deadlines and notifications."""
import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.routes.learning import as_utc, own_student, student_subject, student_subjects, student_work
from app.api.routes.teaching import commit, get_coursework, get_subject, missing, staff, subject_students, taught_subject_ids
from app.core.deps import AuthContext, require_platform_admin, require_role, require_tenant_user
from app.core.rate_limit import rate_limit
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Coursework, Score, Student, Subject
from app.models.elearning import Notification, QuizAnswer, QuizAttempt, QuizExtraAttempt, QuizQuestion, StoredFile
from app.models.institution import Institution
from app.models.learning import CourseMaterial, Submission
from app.models.user import User, UserRole
from app.schemas.academic import Input
from app.services import quiz as engine
from app.services import storage
from app.services.audit_service import record_audit
from app.services.elearning import file_view, files_by_id
from app.services.modules import institution_modules, require_enabled

router = APIRouter(prefix='/api', tags=['E-learning'])
student_role = require_role(UserRole.STUDENT)
upload_limit = rate_limit(max_requests=30, window_seconds=600, key_prefix='file-upload')


# --- Files ---------------------------------------------------------------------------------

async def read_upload(request):
    length = request.headers.get('content-length')
    if length and length.isdigit() and int(length) > storage.MAX_FILE_BYTES:
        raise HTTPException(413, 'Use a file of 10 MB or less')
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > storage.MAX_FILE_BYTES:
            raise HTTPException(413, 'Use a file of 10 MB or less')
    return bytes(data)


def save_file(db, ctx, data, filename, *, purpose, subject_id, student_id=None, allowed=None):
    storage.require_enabled()
    name = storage.clean_name(filename)
    content_type = storage.check_file(name, data, allowed)
    file_id = uuid.uuid4()
    key = f'{ctx.institution_id}/{subject_id}/{file_id}.{storage.extension(name)}'
    storage.put(key, data, content_type)
    row = StoredFile(id=file_id, institution_id=ctx.institution_id, uploaded_by=ctx.user_id, purpose=purpose, subject_id=subject_id,
                     student_id=student_id, filename=name, content_type=content_type, size_bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest(), storage_key=key)
    db.add(row)
    commit(db)
    return file_view(row)


@router.post('/teaching/subjects/{subject_id}/files', status_code=201, dependencies=[Depends(upload_limit)])
async def upload_teaching_file(subject_id: uuid.UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                               purpose: Literal['MATERIAL', 'PAPER'] = 'MATERIAL', db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    subject = get_subject(db, subject_id, ctx)
    require_enabled(db.get(Institution, ctx.institution_id), 'learning_materials' if purpose == 'MATERIAL' else 'coursework')
    data = await read_upload(request)
    return save_file(db, ctx, data, filename, purpose=purpose, subject_id=subject.id)


@router.post('/student/assignments/{work_id}/files', status_code=201, dependencies=[Depends(upload_limit)])
async def upload_submission_file(work_id: uuid.UUID, request: Request, filename: str = Query(min_length=1, max_length=200),
                                 db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    work, _ = student_work(db, work_id, student, ctx)
    if work.delivery == 'QUIZ' or not work.submission_file_types:
        raise HTTPException(422, 'This work does not accept file uploads')
    row = scoped(db, Submission, ctx).filter_by(coursework_id=work.id, student_id=student.id).first()
    if row and row.status == 'SUBMITTED' or scoped(db, Score, ctx).filter_by(coursework_id=work.id, student_id=student.id).first():
        raise HTTPException(409, 'Your work has already been handed in')
    allowed = {ext for group in work.submission_file_types for ext in storage.SUBMISSION_GROUPS[group]}
    data = await read_upload(request)
    return save_file(db, ctx, data, filename, purpose='SUBMISSION', subject_id=work.subject_id, student_id=student.id, allowed=allowed)


def readable_file(db, ctx, file_id):
    row = scoped(db, StoredFile, ctx).filter(StoredFile.id == file_id, StoredFile.deleted_at.is_(None)).first()
    if row is None:
        missing()
    if row.uploaded_by == ctx.user_id:
        return row
    if ctx.role in {UserRole.TEACHER, UserRole.INSTITUTION_ADMIN}:
        get_subject(db, row.subject_id, ctx)
        # Drafts are private to the student until handed in.
        if row.purpose == 'SUBMISSION' and not scoped(db, Submission, ctx).filter_by(file_id=row.id, status='SUBMITTED').first():
            missing()
        return row
    if ctx.role == UserRole.STUDENT:
        student = own_student(db, ctx)
        student_subject(db, row.subject_id, student, ctx)
        if row.purpose == 'MATERIAL' and scoped(db, CourseMaterial, ctx).filter_by(file_id=row.id, published=True).first():
            return row
        if row.purpose == 'PAPER':
            work = scoped(db, Coursework, ctx).filter_by(paper_file_id=row.id, published=True).first()
            if work and (work.opens_at is None or engine.now() >= as_utc(work.opens_at)):
                return row
    missing()


@router.get('/files/{file_id}')
def file_link(file_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    row = readable_file(db, ctx, file_id)
    url = storage.download_url(row.storage_key, row.filename, row.content_type) or f'/api/files/{row.id}/content'
    return dict(**file_view(row), url=url)


@router.get('/files/{file_id}/content')
def file_content(file_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    """Serves file bytes for local development storage. R2 files are downloaded from R2 directly."""
    row = readable_file(db, ctx, file_id)
    if storage.download_url(row.storage_key, row.filename, row.content_type):
        missing()
    return Response(storage.read_local(row.storage_key), media_type=row.content_type,
                    headers={'Content-Disposition': storage.disposition(row.filename), 'Cache-Control': 'private, no-store'})


@router.get('/platform/storage')
def storage_usage(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    rows = db.query(Institution.id, Institution.name, func.count(StoredFile.id), func.coalesce(func.sum(StoredFile.size_bytes), 0)).join(
        StoredFile, StoredFile.institution_id == Institution.id).filter(StoredFile.deleted_at.is_(None)).group_by(Institution.id, Institution.name).all()
    schools = sorted((dict(institution_id=i, name=n, files=c, bytes=int(b)) for i, n, c, b in rows), key=lambda r: -r['bytes'])
    return dict(enabled=storage.enabled(), backend=storage.settings.STORAGE_BACKEND or None, free_bytes=10 * 1024 ** 3,
                total_bytes=sum(r['bytes'] for r in schools), schools=schools)


# --- Quiz building (staff) -------------------------------------------------------------------

class OptionInput(Input):
    id: str = Field(min_length=1, max_length=8, pattern=r'^[a-z0-9]+$')
    text: str = Field(min_length=1, max_length=500)


class QuestionInput(Input):
    kind: Literal['SINGLE', 'MULTIPLE', 'TRUE_FALSE']
    prompt: str = Field(min_length=1, max_length=5000)
    options: list[OptionInput] = Field(default_factory=list, max_length=8)
    correct: list[str] = Field(min_length=1, max_length=8)
    points: Decimal = Field(default=Decimal(1), gt=0, le=1000, max_digits=6, decimal_places=2)
    time_limit_seconds: int | None = Field(default=None, ge=10, le=3600)

    @model_validator(mode='after')
    def valid(self):
        if self.kind == 'TRUE_FALSE':
            self.options = [OptionInput(id='true', text='True'), OptionInput(id='false', text='False')]
        ids = [o.id for o in self.options]
        if len(ids) < 2 or len(set(ids)) != len(ids):
            raise ValueError('Give each question at least two different options')
        if len(set(self.correct)) != len(self.correct) or not set(self.correct) <= set(ids):
            raise ValueError('Correct answers must be options of the question')
        if self.kind != 'MULTIPLE' and len(self.correct) != 1:
            raise ValueError('Single-answer and true/false questions have exactly one correct answer')
        return self


class QuestionsInput(Input):
    questions: list[QuestionInput] = Field(min_length=1, max_length=200)


class QuizSettingsInput(Input):
    time_limit_minutes: int | None = Field(default=None, ge=1, le=600)
    attempts_allowed: int = Field(default=1, ge=1, le=10)
    no_going_back: bool = False
    shuffle_questions: bool = False
    shuffle_options: bool = False
    hide_results_until_close: bool = False
    log_tab_switches: bool = False


class ExtraAttemptInput(Input):
    student_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=300)


SETTING_FIELDS = tuple(QuizSettingsInput.model_fields)


def staff_quiz(db, work_id, ctx, *, lock=False):
    work, subject = get_coursework(db, work_id, ctx, lock=lock)
    if work.delivery != 'QUIZ':
        missing()
    return work, subject


def question_view(q, *, with_answers):
    out = dict(id=q.id, position=q.position, kind=q.kind, prompt=q.prompt, options=q.options, points=q.points,
               time_limit_seconds=q.time_limit_seconds)
    if with_answers:
        out['correct'] = q.correct
    return out


def settings_view(row):
    return {name: getattr(row, name) for name in SETTING_FIELDS}


def has_attempts(db, work):
    return db.query(QuizAttempt.id).filter_by(institution_id=work.institution_id, coursework_id=work.id).first() is not None


@router.get('/teaching/quizzes/{work_id}')
def quiz_detail(work_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = staff_quiz(db, work_id, ctx)
    settings = engine.settings_for(db, work)
    questions = engine.questions_for(db, work)
    return dict(id=work.id, title=work.title, subject_id=subject.id, subject_name=subject.name, published=work.published,
                opens_at=as_utc(work.opens_at), due_at=as_utc(work.due_at), max_score=work.max_score, settings=settings_view(settings),
                sequential=engine.is_sequential(settings, questions), locked=has_attempts(db, work),
                questions=[question_view(q, with_answers=True) for q in questions])


@router.put('/teaching/quizzes/{work_id}/settings')
def save_quiz_settings(work_id: uuid.UUID, body: QuizSettingsInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, _ = staff_quiz(db, work_id, ctx, lock=True)
    settings = engine.settings_for(db, work)
    if has_attempts(db, work):
        # Students already started under these rules; only more attempts or more time may be given.
        changed = [n for n in SETTING_FIELDS if n not in {'attempts_allowed', 'time_limit_minutes'} and getattr(body, n) != getattr(settings, n)]
        if changed or body.attempts_allowed < settings.attempts_allowed or (
                settings.time_limit_minutes and (body.time_limit_minutes is None or body.time_limit_minutes < settings.time_limit_minutes)):
            raise HTTPException(409, 'Students have started this quiz. You can only allow more attempts or more time now.')
    for name in SETTING_FIELDS:
        setattr(settings, name, getattr(body, name))
    commit(db)
    return settings_view(settings)


@router.put('/teaching/quizzes/{work_id}/questions')
def save_questions(work_id: uuid.UUID, body: QuestionsInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, _ = staff_quiz(db, work_id, ctx, lock=True)
    if has_attempts(db, work):
        raise HTTPException(409, 'Students have started this quiz, so its questions can no longer change')
    for row in engine.questions_for(db, work):
        db.delete(row)
    db.flush()
    rows = [QuizQuestion(institution_id=ctx.institution_id, coursework_id=work.id, position=i, kind=q.kind, prompt=q.prompt,
                         options=[o.model_dump() for o in q.options], correct=q.correct, points=q.points, time_limit_seconds=q.time_limit_seconds)
            for i, q in enumerate(body.questions)]
    db.add_all(rows)
    work.max_score = sum((q.points for q in body.questions), Decimal(0))
    commit(db)
    return dict(max_score=work.max_score, questions=[question_view(q, with_answers=True) for q in rows])


def student_names(db, ctx, ids):
    rows = scoped(db, Student, ctx).join(User, User.id == Student.user_id).filter(Student.id.in_(ids)).with_entities(Student, User).all()
    return {s.id: dict(name=f'{u.first_name} {u.last_name}', admission_number=s.admission_number) for s, u in rows}


@router.get('/teaching/quizzes/{work_id}/results')
def quiz_results(work_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = staff_quiz(db, work_id, ctx)
    engine.finish_expired(db, work)
    commit(db)
    settings = engine.settings_for(db, work)
    attempts = scoped(db, QuizAttempt, ctx).filter_by(coursework_id=work.id).order_by(QuizAttempt.number).all()
    extras = scoped(db, QuizExtraAttempt, ctx).filter_by(coursework_id=work.id).all()
    out = []
    for student, user in subject_students(db, subject, ctx).order_by(User.first_name, User.last_name).all():
        mine = [a for a in attempts if a.student_id == student.id]
        done = [a for a in mine if a.status == 'SUBMITTED']
        out.append(dict(student_id=student.id, name=f'{user.first_name} {user.last_name}', admission_number=student.admission_number,
                        attempts=[dict(id=a.id, number=a.number, status=a.status, score=a.score, started_at=as_utc(a.started_at),
                                       submitted_at=as_utc(a.submitted_at), auto_submitted=a.auto_submitted, tab_switches=a.tab_switches) for a in mine],
                        best=max((a.score for a in done), default=None),
                        allowed=settings.attempts_allowed + sum(1 for e in extras if e.student_id == student.id),
                        extra_reasons=[e.reason for e in extras if e.student_id == student.id]))
    return dict(max_score=work.max_score, log_tab_switches=settings.log_tab_switches, students=out)


@router.get('/teaching/quiz-attempts/{attempt_id}')
def staff_attempt(attempt_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    attempt = scoped(db, QuizAttempt, ctx).filter_by(id=attempt_id).first()
    if attempt is None:
        missing()
    work, subject = staff_quiz(db, attempt.coursework_id, ctx)
    by_id = {str(q.id): q for q in engine.questions_for(db, work)}
    if engine.catch_up(db, attempt, by_id):
        commit(db)
    return dict(**attempt_summary(attempt), student=student_names(db, ctx, [attempt.student_id]).get(attempt.student_id),
                questions=review_items(attempt, by_id, engine.answers_for(db, attempt), with_answers=True))


@router.post('/teaching/quizzes/{work_id}/extra-attempts', status_code=201)
def grant_attempt(work_id: uuid.UUID, body: ExtraAttemptInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = staff_quiz(db, work_id, ctx, lock=True)
    if not subject_students(db, subject, ctx).filter(Student.id == body.student_id).first():
        missing()
    db.add(QuizExtraAttempt(institution_id=ctx.institution_id, coursework_id=work.id, student_id=body.student_id,
                            granted_by=ctx.user_id, reason=body.reason.strip()))
    record_audit(db, ctx, 'quiz.extra_attempt', work.id, ctx.institution_id, f'{body.student_id}: {body.reason.strip()}')
    commit(db)
    return dict(message='Another attempt is allowed')


# --- Taking a quiz (students) ----------------------------------------------------------------

class AnswerInput(Input):
    question_id: uuid.UUID
    selected: list[str] = Field(default_factory=list, max_length=8)


class EventInput(Input):
    kind: Literal['LEFT_PAGE']


def student_quiz(db, work_id, student, ctx, *, lock=False):
    work, subject = student_work(db, work_id, student, ctx, lock=lock)
    if work.delivery != 'QUIZ':
        missing()
    return work, subject


def own_attempt(db, attempt_id, student, ctx, *, lock=False):
    q = scoped(db, QuizAttempt, ctx).filter_by(id=attempt_id, student_id=student.id)
    attempt = (q.with_for_update() if lock else q).first()
    if attempt is None:
        missing()
    return attempt


def attempt_summary(attempt):
    return dict(id=attempt.id, number=attempt.number, status=attempt.status, started_at=as_utc(attempt.started_at),
                ends_at=as_utc(attempt.ends_at), submitted_at=as_utc(attempt.submitted_at), auto_submitted=attempt.auto_submitted,
                score=attempt.score, max_score=attempt.max_score, tab_switches=attempt.tab_switches)


def shown_question(q, option_order):
    by_id = {o['id']: o for o in q.options}
    return dict(id=q.id, kind=q.kind, prompt=q.prompt, points=q.points, time_limit_seconds=q.time_limit_seconds,
                options=[by_id[i] for i in option_order if i in by_id])


def review_items(attempt, by_id, answers, *, with_answers):
    items = []
    for item in attempt.plan:
        q = by_id.get(item['q'])
        if q is None:
            continue
        answer = answers.get(item['q'])
        selected = answer.selected if answer else []
        out = dict(**shown_question(q, item['o']), selected=selected)
        if with_answers:
            out.update(correct=q.correct, earned=q.points if engine.is_correct(q, selected) else Decimal(0))
        items.append(out)
    return items


def rules_view(work, settings, questions):
    return dict(time_limit_minutes=settings.time_limit_minutes, question_count=len(questions),
                timed_questions=sum(1 for q in questions if q.time_limit_seconds), one_at_a_time=engine.is_sequential(settings, questions),
                shuffled=settings.shuffle_questions or settings.shuffle_options, log_tab_switches=settings.log_tab_switches,
                hide_results_until_close=settings.hide_results_until_close)


@router.get('/student/quizzes/{work_id}')
def quiz_overview(work_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    work, subject = student_quiz(db, work_id, student, ctx)
    settings = engine.settings_for(db, work)
    questions = engine.questions_for(db, work)
    by_id = {str(q.id): q for q in questions}
    attempts = scoped(db, QuizAttempt, ctx).filter_by(coursework_id=work.id, student_id=student.id).order_by(QuizAttempt.number).all()
    if any([engine.catch_up(db, a, by_id) for a in attempts if a.status == 'IN_PROGRESS']):
        commit(db)
    allowed = engine.attempts_allowed(db, work, settings, student.id)
    used = len(attempts)
    at = engine.now()
    open_attempt = next((a for a in attempts if a.status == 'IN_PROGRESS'), None)
    reason = None
    if work.opens_at and at < as_utc(work.opens_at):
        reason = 'NOT_OPEN'
    elif engine.closed(work, at):
        reason = 'CLOSED'
    elif used >= allowed and not open_attempt:
        reason = 'NO_ATTEMPTS_LEFT'
    show_score = engine.results_visible(work, settings)
    return dict(id=work.id, title=work.title, instructions=work.instructions, subject_id=subject.id, subject_name=subject.name,
                opens_at=as_utc(work.opens_at), due_at=as_utc(work.due_at), max_score=work.max_score,
                rules=rules_view(work, settings, questions), attempts_allowed=allowed, attempts_used=used,
                open_attempt_id=open_attempt.id if open_attempt else None, can_start=reason is None, blocked_reason=reason,
                results_visible=show_score, answers_visible=engine.answers_visible(work, settings, used, allowed),
                attempts=[dict(attempt_summary(a), score=a.score if show_score else None) for a in attempts])


@router.post('/student/quizzes/{work_id}/attempts', status_code=201)
def start_attempt(work_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    work, _ = student_quiz(db, work_id, student, ctx, lock=True)
    settings = engine.settings_for(db, work)
    questions = engine.questions_for(db, work)
    by_id = {str(q.id): q for q in questions}
    attempts = scoped(db, QuizAttempt, ctx).filter_by(coursework_id=work.id, student_id=student.id).all()
    for attempt in attempts:
        if attempt.status == 'IN_PROGRESS' and not engine.catch_up(db, attempt, by_id):
            return dict(id=attempt.id)
    at = engine.now()
    if work.opens_at and at < as_utc(work.opens_at):
        raise HTTPException(409, 'This quiz has not opened yet')
    if engine.closed(work, at):
        raise HTTPException(409, 'This quiz has closed')
    if not questions:
        raise HTTPException(409, 'This quiz has no questions yet')
    if len(attempts) >= engine.attempts_allowed(db, work, settings, student.id):
        raise HTTPException(409, 'You have used all your attempts for this quiz')
    attempt = engine.start(db, work, settings, questions, student.id, len(attempts) + 1)
    commit(db)
    return dict(id=attempt.id)


def attempt_state(db, work, settings, attempt, by_id):
    out = dict(**attempt_summary(attempt), quiz_id=work.id, title=work.title, server_now=engine.now(),
               sequential=attempt.sequential, total=len(attempt.plan), log_tab_switches=settings.log_tab_switches)
    answers = engine.answers_for(db, attempt)
    if attempt.status == 'SUBMITTED':
        used = db.query(QuizAttempt).filter_by(institution_id=work.institution_id, coursework_id=work.id, student_id=attempt.student_id).count()
        allowed = engine.attempts_allowed(db, work, settings, attempt.student_id)
        show_answers = engine.answers_visible(work, settings, used, allowed)
        if not engine.results_visible(work, settings):
            out['score'] = None
        out.update(results_visible=engine.results_visible(work, settings), answers_visible=show_answers,
                   questions=review_items(attempt, by_id, answers, with_answers=show_answers))
        return out
    if attempt.sequential:
        item = attempt.plan[attempt.current_index]
        question = by_id[item['q']]
        out.update(index=attempt.current_index, question=shown_question(question, item['o']),
                   question_ends_at=engine.question_deadline(attempt, question), answered=len(answers))
    else:
        out.update(questions=[dict(**shown_question(by_id[i['q']], i['o']), selected=answers[i['q']].selected if i['q'] in answers else [])
                              for i in attempt.plan if i['q'] in by_id])
    return out


def load_attempt(db, attempt_id, ctx, *, lock=False):
    student = own_student(db, ctx)
    attempt = own_attempt(db, attempt_id, student, ctx, lock=lock)
    work, _ = student_quiz(db, attempt.coursework_id, student, ctx, lock=lock)
    settings = engine.settings_for(db, work)
    by_id = {str(q.id): q for q in engine.questions_for(db, work)}
    return attempt, work, settings, by_id


@router.get('/student/quiz-attempts/{attempt_id}')
def get_attempt(attempt_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    attempt, work, settings, by_id = load_attempt(db, attempt_id, ctx)
    if attempt.status == 'IN_PROGRESS':
        engine.catch_up(db, attempt, by_id)
        commit(db)
    return attempt_state(db, work, settings, attempt, by_id)


@router.put('/student/quiz-attempts/{attempt_id}/answer')
def answer(attempt_id: uuid.UUID, body: AnswerInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    attempt, work, settings, by_id = load_attempt(db, attempt_id, ctx, lock=True)
    at = engine.now()
    if engine.catch_up(db, attempt, by_id, at):
        commit(db)
        raise HTTPException(409, 'Time is up. Your answers were handed in.')
    key = str(body.question_id)
    question = by_id.get(key)
    if question is None or key not in {i['q'] for i in attempt.plan}:
        missing()
    if attempt.sequential and attempt.plan[attempt.current_index]['q'] != key:
        commit(db)
        raise HTTPException(409, 'Time ran out for that question. The quiz has moved on.')
    if not set(body.selected) <= {o['id'] for o in question.options} or len(set(body.selected)) != len(body.selected):
        raise HTTPException(422, 'Choose from the options shown')
    if question.kind != 'MULTIPLE' and len(body.selected) > 1:
        raise HTTPException(422, 'Choose one answer')
    row = scoped(db, QuizAnswer, ctx).filter_by(attempt_id=attempt.id, question_id=question.id).first()
    if row is None:
        row = QuizAnswer(institution_id=ctx.institution_id, attempt_id=attempt.id, question_id=question.id, selected=[], answered_at=at)
        db.add(row)
    row.selected, row.answered_at = body.selected, at
    if attempt.sequential:
        # Answering moves on for good; the next question's clock starts now.
        attempt.current_index += 1
        attempt.current_started_at = at
        if attempt.current_index >= len(attempt.plan):
            engine.finish(db, attempt, by_id, at=at)
    commit(db)
    return attempt_state(db, work, settings, attempt, by_id)


@router.post('/student/quiz-attempts/{attempt_id}/submit')
def submit(attempt_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    attempt, work, settings, by_id = load_attempt(db, attempt_id, ctx, lock=True)
    if not engine.catch_up(db, attempt, by_id):
        engine.finish(db, attempt, by_id)
    commit(db)
    return attempt_state(db, work, settings, attempt, by_id)


@router.post('/student/quiz-attempts/{attempt_id}/events', status_code=204)
def attempt_event(attempt_id: uuid.UUID, body: EventInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    attempt, work, settings, by_id = load_attempt(db, attempt_id, ctx, lock=True)
    if attempt.status == 'IN_PROGRESS' and settings.log_tab_switches:
        attempt.tab_switches = min(attempt.tab_switches + 1, 10000)
        commit(db)
    return Response(status_code=204)


# --- Course pages and deadlines ------------------------------------------------------------------

def work_status(work, submission, score, attempts, at):
    """TODO, DONE, OVERDUE (late hand-in still possible), MISSED, UPCOMING (not open yet)."""
    if work.delivery == 'QUIZ':
        if any(a.status == 'SUBMITTED' for a in attempts):
            return 'DONE'
        if work.opens_at and at < as_utc(work.opens_at):
            return 'UPCOMING'
        return 'MISSED' if work.due_at and at >= as_utc(work.due_at) else 'TODO'
    if score is not None or (submission is not None and submission.status == 'SUBMITTED'):
        return 'DONE'
    if work.kind == 'EXAM':
        return 'UPCOMING'
    if work.due_at and at >= as_utc(work.due_at):
        return 'OVERDUE' if work.allow_late_submissions else 'MISSED'
    return 'TODO'


def student_items(db, ctx, student, subject_ids):
    works = scoped(db, Coursework, ctx).filter(Coursework.subject_id.in_(subject_ids), Coursework.published.is_(True)).all()
    ids = [w.id for w in works]
    subs = {s.coursework_id: s for s in scoped(db, Submission, ctx).filter(Submission.student_id == student.id, Submission.coursework_id.in_(ids)).all()}
    scores = {s.coursework_id: s for s in scoped(db, Score, ctx).filter(Score.student_id == student.id, Score.coursework_id.in_(ids)).all()}
    attempts = {}
    for a in scoped(db, QuizAttempt, ctx).filter(QuizAttempt.student_id == student.id, QuizAttempt.coursework_id.in_(ids)).all():
        attempts.setdefault(a.coursework_id, []).append(a)
    at = engine.now()
    return [(w, work_status(w, subs.get(w.id), scores.get(w.id), attempts.get(w.id, []), at)) for w in works]


def work_item(work, status, subject=None):
    return dict(id=work.id, title=work.title, kind=work.kind, delivery=work.delivery, section=work.section,
                opens_at=as_utc(work.opens_at), due_at=as_utc(work.due_at), status=status, published=work.published,
                subject_id=work.subject_id, subject_name=subject.name if subject else None)


def sections(materials, works):
    """Group a course's items under their week or topic headings, in the order headings first appear."""
    groups = {}
    for m in materials:
        groups.setdefault(m['section'] or '', dict(materials=[], work=[]))['materials'].append(m)
    for w in works:
        groups.setdefault(w['section'] or '', dict(materials=[], work=[]))['work'].append(w)
    return [dict(name=name, **items) for name, items in groups.items()]


@router.get('/student/courses')
def student_courses(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    student = own_student(db, ctx)
    rows = student_subjects(db, student, ctx).join(AcademicClass, AcademicClass.id == Subject.class_id).join(User, User.id == Subject.teacher_id).with_entities(
        Subject, AcademicClass, User).order_by(Subject.name).all()
    ids = [s.id for s, _, _ in rows]
    items = student_items(db, ctx, student, ids)
    material_counts = dict(scoped(db, CourseMaterial, ctx).filter(CourseMaterial.subject_id.in_(ids), CourseMaterial.published.is_(True)).with_entities(
        CourseMaterial.subject_id, func.count(CourseMaterial.id)).group_by(CourseMaterial.subject_id).all())
    out = []
    for s, c, u in rows:
        mine = [(w, st) for w, st in items if w.subject_id == s.id]
        todo = sorted((w for w, st in mine if st in {'TODO', 'OVERDUE'} and w.due_at), key=lambda w: as_utc(w.due_at))
        out.append(dict(id=s.id, name=s.name, class_name=c.name, academic_year=c.academic_year, teacher_name=f'{u.first_name} {u.last_name}',
                        materials=material_counts.get(s.id, 0), to_do=sum(1 for _, st in mine if st in {'TODO', 'OVERDUE'}),
                        next_due=work_item(todo[0], 'TODO') if todo else None))
    return out


@router.get('/student/courses/{subject_id}')
def student_course(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    from app.api.routes.learning import material_views
    student = own_student(db, ctx)
    subject = student_subject(db, subject_id, student, ctx)
    cls = db.get(AcademicClass, subject.class_id)
    teacher = db.get(User, subject.teacher_id)
    modules = institution_modules(db.get(Institution, ctx.institution_id))
    materials = material_views(db, ctx, scoped(db, CourseMaterial, ctx).filter_by(subject_id=subject.id, published=True).order_by(CourseMaterial.created_at).all()) if modules['learning_materials'] else []
    works = [work_item(w, st) for w, st in sorted(student_items(db, ctx, student, [subject.id]), key=lambda x: x[0].created_at)
             if modules['coursework'] and (w.delivery != 'QUIZ' or modules['online_quizzes'])]
    return dict(id=subject.id, name=subject.name, class_name=cls.name, academic_year=cls.academic_year,
                teacher_name=f'{teacher.first_name} {teacher.last_name}' if teacher else '', sections=sections(materials, works))


@router.get('/student/deadlines')
def student_deadlines(db: Session = Depends(get_db), ctx: AuthContext = Depends(student_role)):
    if not institution_modules(db.get(Institution, ctx.institution_id))['coursework']:
        return []
    student = own_student(db, ctx)
    subjects = {s.id: s for s in student_subjects(db, student, ctx).all()}
    at = engine.now()
    out = []
    for w, st in student_items(db, ctx, student, list(subjects)):
        due = as_utc(w.due_at)
        if due is None:
            continue
        upcoming = at <= due <= at + timedelta(days=30)
        recent = at - timedelta(days=14) <= due < at and st in {'OVERDUE', 'MISSED', 'DONE'}
        if upcoming or recent:
            out.append(work_item(w, st, subjects[w.subject_id]))
    return sorted(out, key=lambda i: i['due_at'])


@router.get('/teaching/courses')
def teaching_courses(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    q = scoped(db, Subject, ctx)
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(Subject.id.in_(taught_subject_ids(db, ctx)))
    rows = q.join(AcademicClass, AcademicClass.id == Subject.class_id).with_entities(Subject, AcademicClass).order_by(Subject.name).all()
    ids = [s.id for s, _ in rows]
    materials = dict(scoped(db, CourseMaterial, ctx).filter(CourseMaterial.subject_id.in_(ids)).with_entities(
        CourseMaterial.subject_id, func.count(CourseMaterial.id)).group_by(CourseMaterial.subject_id).all())
    works = dict(scoped(db, Coursework, ctx).filter(Coursework.subject_id.in_(ids)).with_entities(
        Coursework.subject_id, func.count(Coursework.id)).group_by(Coursework.subject_id).all())
    to_mark = dict(scoped(db, Submission, ctx).join(Coursework, Coursework.id == Submission.coursework_id).outerjoin(
        Score, (Score.coursework_id == Submission.coursework_id) & (Score.student_id == Submission.student_id)).filter(
        Coursework.subject_id.in_(ids), Submission.status == 'SUBMITTED', Score.id.is_(None)).with_entities(
        Coursework.subject_id, func.count(Submission.id)).group_by(Coursework.subject_id).all())
    return [dict(id=s.id, name=s.name, class_id=c.id, class_name=c.name, academic_year=c.academic_year, materials=materials.get(s.id, 0),
                 work=works.get(s.id, 0), to_mark=to_mark.get(s.id, 0)) for s, c in rows]


@router.get('/teaching/courses/{subject_id}')
def teaching_course(subject_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    from app.api.routes.learning import material_views
    subject = get_subject(db, subject_id, ctx)
    cls = db.get(AcademicClass, subject.class_id)
    materials = material_views(db, ctx, scoped(db, CourseMaterial, ctx).filter_by(subject_id=subject.id).order_by(CourseMaterial.created_at).all())
    works = scoped(db, Coursework, ctx).filter_by(subject_id=subject.id).order_by(Coursework.created_at).all()
    handed = dict(scoped(db, Submission, ctx).filter(Submission.coursework_id.in_([w.id for w in works]), Submission.status == 'SUBMITTED').with_entities(
        Submission.coursework_id, func.count(Submission.id)).group_by(Submission.coursework_id).all())
    tried = dict(scoped(db, QuizAttempt, ctx).filter(QuizAttempt.coursework_id.in_([w.id for w in works]), QuizAttempt.status == 'SUBMITTED').with_entities(
        QuizAttempt.coursework_id, func.count(func.distinct(QuizAttempt.student_id))).group_by(QuizAttempt.coursework_id).all())
    roster = subject_students(db, subject, ctx).count()
    items = [dict(work_item(w, None), handed_in=tried.get(w.id, 0) if w.delivery == 'QUIZ' else handed.get(w.id, 0)) for w in works]
    return dict(id=subject.id, name=subject.name, class_id=cls.id, class_name=cls.name, academic_year=cls.academic_year,
                students=roster, sections=sections(materials, items))


@router.get('/teaching/deadlines')
def teaching_deadlines(db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    if not institution_modules(db.get(Institution, ctx.institution_id))['coursework']:
        return []
    q = scoped(db, Coursework, ctx).join(Subject, Subject.id == Coursework.subject_id).filter(Coursework.published.is_(True), Coursework.due_at.isnot(None))
    if ctx.role != UserRole.INSTITUTION_ADMIN:
        q = q.filter(Coursework.subject_id.in_(taught_subject_ids(db, ctx)))
    at = engine.now()
    rows = q.filter(Coursework.due_at >= at - timedelta(days=7), Coursework.due_at <= at + timedelta(days=14)).with_entities(Coursework, Subject).all()
    return sorted((work_item(w, 'CLOSED' if as_utc(w.due_at) <= at else 'OPEN', s) for w, s in rows), key=lambda i: i['due_at'])


# --- Notifications ---------------------------------------------------------------------------------

class ReadInput(Input):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    all: bool = False


@router.get('/notifications')
def notifications(db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    rows = scoped(db, Notification, ctx).filter_by(user_id=ctx.user_id).order_by(Notification.created_at.desc()).limit(30).all()
    unread = scoped(db, Notification, ctx).filter(Notification.user_id == ctx.user_id, Notification.read_at.is_(None)).count()
    due_soon = []
    if ctx.role == UserRole.STUDENT:
        enabled = institution_modules(db.get(Institution, ctx.institution_id))
        student = scoped(db, Student, ctx).filter_by(user_id=ctx.user_id).first()
        if student and enabled['student_portal'] and enabled['coursework']:
            subjects = {s.id: s for s in student_subjects(db, student, ctx).all()}
            at = engine.now()
            due_soon = [work_item(w, st, subjects[w.subject_id]) for w, st in student_items(db, ctx, student, list(subjects))
                        if st == 'TODO' and w.due_at and at <= as_utc(w.due_at) <= at + timedelta(hours=48)]
            due_soon.sort(key=lambda i: i['due_at'])
    return dict(unread=unread, due_soon=due_soon,
                items=[dict(id=n.id, title=n.title, body=n.body, link=n.link, created_at=as_utc(n.created_at), read=n.read_at is not None) for n in rows])


@router.post('/notifications/read')
def mark_read(body: ReadInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_tenant_user)):
    q = scoped(db, Notification, ctx).filter(Notification.user_id == ctx.user_id, Notification.read_at.is_(None))
    if not body.all:
        q = q.filter(Notification.id.in_(body.ids))
    q.update({Notification.read_at: engine.now()}, synchronize_session=False)
    commit(db)
    return dict(unread=scoped(db, Notification, ctx).filter(Notification.user_id == ctx.user_id, Notification.read_at.is_(None)).count())
