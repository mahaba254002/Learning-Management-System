"""Marks in and out: each institution's own grading, mark uploads from Excel or CSV, and Excel marksheets.

Report cards are not generated here. Institutions export marksheets and build
reports in their own format."""
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from app.api.routes.teaching import (assessment_values, commit, get_class, get_coursework, get_subject, missing, staff,
                                     subject_students, enrolled_students, write_scores)
from app.core.deps import AuthContext, require_platform_admin, require_role
from app.core.rate_limit import rate_limit
from app.core.tenancy import scoped
from app.db.session import get_db
from app.models.academic import AcademicClass, Coursework, Score, Subject
from app.models.grading_request import GradingChangeRequest
from app.models.institution import Institution
from app.models.user import User, UserRole
from app.schemas.academic import CourseworkInput, Input, ScoreInput
from app.services import attendance as attendance_service
from app.services import marksheet as marksheet_service
from app.services.academic_configuration import AcademicConfiguration, academic_configuration
from app.services.audit_service import record_audit
from app.services.grading_rules import GradingRules
from app.services.spreadsheet import MAX_BYTES, read_table, workbook_bytes

router = APIRouter(prefix="/api", tags=["Marks"])
institution_admin = require_role(UserRole.INSTITUTION_ADMIN)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
ADMISSION_HEADERS = {'admission_number', 'admission number', 'admission no', 'adm no', 'adm', 'adm. no', 'admno'}


# --- The institution's own grading -------------------------------------------------

def grading_view(db, institution):
    config = academic_configuration(institution)
    requests = db.query(GradingChangeRequest).filter_by(institution_id=institution.id).order_by(GradingChangeRequest.created_at.desc()).limit(20).all()
    return dict(rules=config['grading_rules'], locked=institution.grading_locked_at is not None, locked_at=institution.grading_locked_at,
                assessment_policy=config['assessment_policy'], credits_enabled=config['credits_enabled'],
                requests=[request_view(r) for r in requests])


def request_view(r, institution=None):
    out = dict(id=r.id, status=r.status, reason=r.reason, proposed_rules=r.proposed_rules, previous_rules=r.previous_rules,
               created_at=r.created_at, decided_at=r.decided_at, decision_note=r.decision_note)
    if institution is not None:
        out.update(institution_id=institution.id, institution_name=institution.name, institution_code=institution.code)
    return out


def checked_config(institution, rules):
    """The whole configuration must stay valid, e.g. GPA needs credits."""
    try:
        return AcademicConfiguration.model_validate({**academic_configuration(institution), 'grading_rules': rules}).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, '; '.join(e['msg'].replace('Value error, ', '') for e in exc.errors()))


class GradingInput(Input):
    rules: GradingRules


@router.get('/institution/grading')
def institution_grading(db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    return grading_view(db, db.get(Institution, ctx.institution_id))


@router.put('/institution/grading')
def set_grading(body: GradingInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    """First-time setup by the institution. Afterwards changes go through a request."""
    institution = db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    if institution.grading_locked_at is not None:
        raise HTTPException(409, 'Grading is already set. Send a change request for the platform administrator to approve.')
    institution.academic_configuration = checked_config(institution, body.rules.model_dump())
    institution.grading_locked_at = datetime.now(timezone.utc)
    record_audit(db, ctx, 'grading.set', institution.id, institution.id, body.rules.name)
    commit(db)
    return grading_view(db, institution)


class ChangeRequestInput(Input):
    rules: GradingRules
    reason: str = Field(min_length=10, max_length=1000)


@router.post('/institution/grading/requests', status_code=201)
def request_change(body: ChangeRequestInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    institution = db.query(Institution).filter_by(id=ctx.institution_id).with_for_update().one()
    if institution.grading_locked_at is None:
        raise HTTPException(409, 'Grading is not set yet. Save it directly.')
    if db.query(GradingChangeRequest).filter_by(institution_id=institution.id, status='PENDING').first():
        raise HTTPException(409, 'A change request is already waiting. Withdraw it first to send a new one.')
    checked_config(institution, body.rules.model_dump())
    row = GradingChangeRequest(institution_id=institution.id, proposed_rules=body.rules.model_dump(), reason=body.reason,
                               previous_rules=academic_configuration(institution)['grading_rules'], requested_by=ctx.actor_user_id or ctx.user_id)
    db.add(row)
    record_audit(db, ctx, 'grading.change_requested', institution.id, institution.id)
    commit(db)
    return request_view(row)


@router.post('/institution/grading/requests/{request_id}/withdraw')
def withdraw_request(request_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(institution_admin)):
    row = db.query(GradingChangeRequest).filter_by(id=request_id, institution_id=ctx.institution_id).with_for_update().first()
    if not row:
        missing()
    if row.status != 'PENDING':
        raise HTTPException(409, 'Only a waiting request can be withdrawn')
    row.status = 'WITHDRAWN'
    commit(db)
    return request_view(row)


@router.get('/platform/grading-requests')
def grading_requests(status: Literal['PENDING', 'APPROVED', 'REJECTED', 'WITHDRAWN', 'ALL'] = 'PENDING', db: Session = Depends(get_db),
                     ctx: AuthContext = Depends(require_platform_admin)):
    q = db.query(GradingChangeRequest, Institution).join(Institution, Institution.id == GradingChangeRequest.institution_id)
    if status != 'ALL':
        q = q.filter(GradingChangeRequest.status == status)
    return [request_view(r, i) for r, i in q.order_by(GradingChangeRequest.created_at.desc()).limit(100).all()]


class DecisionInput(Input):
    approve: bool
    note: str = Field(default='', max_length=1000)


@router.post('/platform/grading-requests/{request_id}/decide')
def decide(request_id: uuid.UUID, body: DecisionInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    row = db.query(GradingChangeRequest).filter_by(id=request_id).with_for_update().first()
    if not row:
        missing()
    if row.status != 'PENDING':
        raise HTTPException(409, 'This request was already decided')
    institution = db.query(Institution).filter_by(id=row.institution_id).with_for_update().one()
    if body.approve:
        institution.academic_configuration = checked_config(institution, row.proposed_rules)
    elif len(body.note.strip()) < 3:
        raise HTTPException(422, 'Give the institution a short reason for rejecting')
    row.status = 'APPROVED' if body.approve else 'REJECTED'
    row.decided_by, row.decided_at, row.decision_note = ctx.user_id, datetime.now(timezone.utc), body.note.strip()
    record_audit(db, ctx, 'grading.change_approved' if body.approve else 'grading.change_rejected', institution.id, institution.id, body.note.strip()[:200])
    commit(db)
    return request_view(row, institution)


@router.post('/platform/institutions/{institution_id}/grading-unlock')
def unlock_grading(institution_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(require_platform_admin)):
    """Let the institution set its grading directly one more time."""
    institution = db.query(Institution).filter_by(id=institution_id).with_for_update().first()
    if not institution:
        missing()
    institution.grading_locked_at = None
    record_audit(db, ctx, 'grading.unlocked', institution.id, institution.id)
    commit(db)
    return dict(locked=False)


# --- Reading upload files -------------------------------------------------------------

@router.post('/marks/parse', dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, key_prefix='marks-parse'))])
async def parse(request: Request, filename: str = Query(max_length=200), ctx: AuthContext = Depends(staff)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, 'Use a file smaller than 3 MB')
    header, rows = read_table(bytes(data), filename)
    return dict(header=header, rows=rows)


def admission_column(header):
    for index, name in enumerate(header):
        if name.strip().lower() in ADMISSION_HEADERS:
            return index
    raise HTTPException(422, 'Add a column named admission_number')


def number(value):
    cleaned = value.replace(',', '').strip()
    try:
        result = Decimal(cleaned)
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def roster_by_admission(rows):
    return {student.admission_number.strip().upper(): student for student, _ in rows}


# --- Upload: one assessment ----------------------------------------------------------------

class TableInput(Input):
    header: list[str] = Field(min_length=2, max_length=60)
    rows: list[list[str]] = Field(min_length=1, max_length=3000)
    commit: bool = False


@router.post('/marks/coursework/{coursework_id}/import')
def import_assessment(coursework_id: uuid.UUID, body: TableInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """Columns: admission_number, mark (a number, or the outcome label for competency assessments), optional feedback."""
    work, subject = get_coursework(db, coursework_id, ctx, lock=body.commit)
    get_class(db, subject.class_id, ctx, lock=body.commit)
    names = [h.strip().lower() for h in body.header]
    adm = admission_column(body.header)
    mark_col = next((i for i, n in enumerate(names) if n in {'mark', 'marks', 'score', 'outcome', 'result'}), None)
    if mark_col is None:
        raise HTTPException(422, 'Add a column named mark')
    feedback_col = next((i for i, n in enumerate(names) if n in {'feedback', 'comment', 'remarks', 'remark'}), None)
    roster = roster_by_admission(subject_students(db, subject, ctx).all())
    existing = {r.student_id: r for r in scoped(db, Score, ctx).filter(Score.coursework_id == work.id).all()}
    seen, results, entries = set(), [], []
    for line, row in enumerate(body.rows, start=2):
        key = row[adm].strip().upper() if adm < len(row) else ''
        raw = row[mark_col].strip() if mark_col < len(row) else ''
        problems = []
        student = roster.get(key)
        if not key:
            continue
        if student is None:
            problems.append('Not a student in this offering')
        if key in seen:
            problems.append('Appears more than once')
        seen.add(key)
        if not raw:
            results.append(dict(row=line, admission_number=row[adm], status='SKIPPED', problems=[]))
            continue
        score = label = None
        if work.assessment_mode == 'COMPETENCY':
            label = next((l for l in work.rubric_labels if l.lower() == raw.lower()), None)
            if label is None:
                problems.append(f"Use one of: {', '.join(work.rubric_labels)}")
        else:
            score = number(raw)
            if score is None or score < 0:
                problems.append('Mark must be a number')
            elif score > work.max_score:
                problems.append(f'Mark is above the maximum of {work.max_score:g}')
        feedback = row[feedback_col].strip()[:5000] if feedback_col is not None and feedback_col < len(row) else None
        status = 'ERROR' if problems else ('REPLACE' if student and student.id in existing else 'NEW')
        if not problems and student.id in existing:
            old = existing[student.id]
            if (old.score, old.competency_label) == (score, label) and (feedback is None or feedback == old.feedback):
                status = 'UNCHANGED'
        results.append(dict(row=line, admission_number=row[adm], mark=raw, status=status, problems=problems))
        if not problems and status != 'UNCHANGED':
            entries.append(ScoreInput(student_id=student.id, score=score, competency_label=label,
                                      feedback=feedback if feedback is not None else (existing[student.id].feedback if student.id in existing else '')))
    errors = sum(1 for r in results if r['problems'])
    if body.commit:
        if errors:
            raise HTTPException(422, 'Fix the rows with problems before saving')
        if entries:
            write_scores(db, ctx, work, subject, entries, existing)
            record_audit(db, ctx, 'assessment.marks_uploaded', work.id, ctx.institution_id, f'{len(entries)} marks')
        commit(db)
    return dict(title=work.title, max_score=work.max_score, rows=results, errors=errors, to_save=len(entries), saved=bool(body.commit))


# --- Upload: whole class marksheet for one exam -----------------------------------------------

class ExamImportInput(TableInput):
    period_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    kind: Literal['EXAM', 'COURSEWORK', 'ASSIGNMENT'] = 'EXAM'
    max_score: Decimal = Field(default=Decimal(100), gt=0, le=10000, max_digits=8, decimal_places=2)


def class_period(db, ctx, group, period_id):
    window = attendance_service.date_range(db, ctx.institution_id, group, period_id)
    if window is None or window['period_id'] is None:
        raise HTTPException(422, "Choose a term or semester in this class's academic year")
    return window


@router.post('/marks/classes/{class_id}/exam-import')
def import_exam(class_id: uuid.UUID, body: ExamImportInput, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """One file for a class and one exam: admission number plus a column per subject.
    Columns that are not subjects (name, total, mean) are ignored."""
    group = get_class(db, class_id, ctx, supervise=True, lock=body.commit)
    class_period(db, ctx, group, body.period_id)
    if academic_configuration(db.get(Institution, ctx.institution_id))['assessment_policy'] == 'COMPETENCY':
        raise HTTPException(409, 'This institution records competency outcomes. Upload them per assessment.')
    subjects = [s for s in scoped(db, Subject, ctx).filter(Subject.class_id == class_id).all() if not s.period_id or s.period_id == body.period_id]
    by_name = {s.name.strip().lower(): s for s in subjects}
    adm = admission_column(body.header)
    columns, ignored = {}, []
    for index, name in enumerate(body.header):
        if index == adm:
            continue
        subject = by_name.get(name.strip().lower())
        (columns.__setitem__(index, subject) if subject else ignored.append(name))
    if not columns:
        raise HTTPException(422, 'No column matches a subject in this class. Use the subject names as column headings.')
    plan = {}
    for index, subject in columns.items():
        work = scoped(db, Coursework, ctx).filter(Coursework.subject_id == subject.id, Coursework.assessment_mode == 'NUMERIC').all()
        work = next((w for w in work if w.title.strip().lower() == body.title.strip().lower() and (w.period_id or subject.period_id) == body.period_id), None)
        students = roster_by_admission(subject_students(db, subject, ctx).all())
        existing = {r.student_id: r for r in scoped(db, Score, ctx).filter(Score.coursework_id == work.id).all()} if work else {}
        plan[index] = dict(subject=subject, work=work, students=students, existing=existing, entries=[],
                           max_score=work.max_score if work else body.max_score)
    class_roster = roster_by_admission(enrolled_students(db, class_id, ctx).all())
    results, seen = [], set()
    for line, row in enumerate(body.rows, start=2):
        key = row[adm].strip().upper() if adm < len(row) else ''
        if not key:
            continue
        problems, counts = [], dict(new=0, replace=0)
        if key not in class_roster:
            problems.append('Not a student in this class')
        if key in seen:
            problems.append('Appears more than once')
        seen.add(key)
        for index, item in plan.items():
            raw = row[index].strip() if index < len(row) else ''
            if not raw or raw in {'-', '—', 'X', 'x', 'ABS', 'abs'} or key not in class_roster:
                continue
            student = item['students'].get(key)
            score = number(raw)
            name = item['subject'].name
            if student is None:
                problems.append(f'{name}: the student does not take this subject')
            elif score is None or score < 0:
                problems.append(f'{name}: "{raw}" is not a mark')
            elif score > item['max_score']:
                problems.append(f"{name}: above the maximum of {item['max_score']:g}")
            else:
                old = item['existing'].get(student.id)
                if old is None or old.score != score:
                    item['entries'].append(ScoreInput(student_id=student.id, score=score, feedback=old.feedback if old else ''))
                    counts['replace' if old else 'new'] += 1
        results.append(dict(row=line, admission_number=row[adm], problems=problems, **counts))
    errors = sum(1 for r in results if r['problems'])
    subjects_out = [dict(column=body.header[i], subject=p['subject'].name, existing_assessment=p['work'] is not None,
                         max_score=p['max_score'], marks=len(p['entries'])) for i, p in plan.items()]
    if body.commit:
        if errors:
            raise HTTPException(422, 'Fix the rows with problems before saving')
        for item in plan.values():
            if not item['entries']:
                continue
            work = item['work']
            if work is None:
                payload = CourseworkInput(period_id=body.period_id, title=body.title, kind=body.kind, max_score=item['max_score'], published=True,
                                          instructions='Marks uploaded from a class marksheet.', assessment_mode='NUMERIC', allow_late_submissions=False)
                work = Coursework(institution_id=ctx.institution_id, subject_id=item['subject'].id, **assessment_values(db, ctx, payload, item['subject']))
                db.add(work)
                db.flush()
            write_scores(db, ctx, work, item['subject'], item['entries'], item['existing'])
        record_audit(db, ctx, 'assessment.class_marksheet_uploaded', class_id, ctx.institution_id,
                     f"{body.title}: {sum(len(p['entries']) for p in plan.values())} marks")
        commit(db)
    return dict(title=body.title, subjects=subjects_out, ignored_columns=ignored, rows=results, errors=errors,
                to_save=sum(len(p['entries']) for p in plan.values()), saved=bool(body.commit))


# --- Marksheets and templates ----------------------------------------------------------------

def sheet_for(db, ctx, group, period_id, exam, subject_ids=None):
    window = class_period(db, ctx, group, period_id)
    data = marksheet_service.build(db, ctx.institution_id, group.id, window['period_id'], exam or None, subject_ids)
    data['periods'] = window['periods']
    return data


def xlsx(content, filename):
    safe = re.sub(r'[^A-Za-z0-9._-]+', '-', filename).strip('-') or 'marksheet'
    return Response(content, media_type=XLSX, headers={'Content-Disposition': f'attachment; filename="{safe}.xlsx"', 'Cache-Control': 'no-store'})


@router.get('/marks/classes/{class_id}/marksheet')
def class_marksheet(class_id: uuid.UUID, period_id: uuid.UUID | None = None, exam: str = Query('', max_length=200),
                    download: bool = False, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """Whole class: institution admin and the class teacher."""
    group = get_class(db, class_id, ctx, supervise=True)
    data = sheet_for(db, ctx, group, period_id, exam)
    if not download:
        return data
    record_audit(db, ctx, 'marksheet.downloaded', class_id, ctx.institution_id, f"{data['period_name']} {exam}".strip())
    commit(db)
    return xlsx(marksheet_service.workbook(data), f"{data['class_name']}-{data['period_name']}-{exam or 'term'}")


@router.get('/marks/subjects/{subject_id}/marksheet')
def subject_marksheet(subject_id: uuid.UUID, period_id: uuid.UUID | None = None, exam: str = Query('', max_length=200),
                      download: bool = False, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """One subject: its teachers (and the admin). Positions rank within the subject."""
    subject = get_subject(db, subject_id, ctx)
    group = scoped(db, AcademicClass, ctx).filter_by(id=subject.class_id).one()
    data = sheet_for(db, ctx, group, period_id, exam, {subject.id})
    if not download:
        return data
    record_audit(db, ctx, 'marksheet.downloaded', subject_id, ctx.institution_id, f"{data['period_name']} {subject.name}")
    commit(db)
    return xlsx(marksheet_service.workbook(data), f"{data['class_name']}-{subject.name}-{data['period_name']}")


@router.get('/marks/classes/{class_id}/template')
def class_template(class_id: uuid.UUID, period_id: uuid.UUID | None = None, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    """A blank class marksheet to fill in: admission number, name and one column per subject."""
    group = get_class(db, class_id, ctx, supervise=True)
    window = class_period(db, ctx, group, period_id)
    subjects = [s for s in scoped(db, Subject, ctx).filter(Subject.class_id == class_id).order_by(Subject.name).all()
                if not s.period_id or s.period_id == window['period_id']]
    rows = [['admission_number', 'name'] + [s.name for s in subjects]]
    rows += [[s.admission_number, f'{u.first_name} {u.last_name}'] + [None] * len(subjects) for s, u in enrolled_students(db, class_id, ctx).order_by(User.first_name, User.last_name).all()]
    name = f"{group.name}{' ' + group.stream if group.stream else ''}"
    return xlsx(workbook_bytes([(f'{name} marks', rows, [18, 28] + [14] * len(subjects))]), f'{name}-marks-template')


@router.get('/marks/coursework/{coursework_id}/template')
def assessment_template(coursework_id: uuid.UUID, db: Session = Depends(get_db), ctx: AuthContext = Depends(staff)):
    work, subject = get_coursework(db, coursework_id, ctx)
    rows = [['admission_number', 'name', 'mark', 'feedback']]
    rows += [[s.admission_number, f'{u.first_name} {u.last_name}', None, None] for s, u in subject_students(db, subject, ctx).order_by(User.first_name, User.last_name).all()]
    return xlsx(workbook_bytes([(work.title, rows, [18, 28, 10, 40])]), f'{subject.name}-{work.title}-template')
