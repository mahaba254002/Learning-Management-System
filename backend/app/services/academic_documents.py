"""Build honest academic statements: no invented final grades, ranks or GPA."""
import hashlib
import json
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.curriculum import CatalogueUnit, CourseCompletion, CourseRegistration, Programme, StudyLevel
from app.models.institution import Institution
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.user import User, UserRole
from app.services.academic_configuration import academic_configuration
from app.services.learning_settings import learning_settings, grade_label
from app.services import final_grades as finals
from app.models.final_grade import FinalGrade
from app.services.grading_rules import gpa
from app.api.routes.teaching import ensure_staff, scoped


@contextmanager
def consistent_session(db):
    # Authentication has already used the request transaction. Read academic data
    # and write the issued snapshot in a separate, consistent PostgreSQL snapshot.
    if db.get_bind().dialect.name != 'postgresql':
        yield db
    else:
        with db.get_bind().connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with Session(bind=connection) as session:
                yield session


def learner(db, ctx, student_id):
    row = scoped(db, Student, ctx).filter_by(id=student_id).first()
    if not row: raise HTTPException(404, 'Learner not found')
    return row


def groups_for(db, ctx, student, class_id=None):
    ensure_staff(db, ctx)
    query = scoped(db, AcademicClass, ctx).join(Enrollment, Enrollment.class_id == AcademicClass.id).filter(
        Enrollment.institution_id == ctx.institution_id, Enrollment.student_id == student.id)
    if class_id: query = query.filter(AcademicClass.id == class_id)
    if ctx.role == UserRole.TEACHER:
        if not class_id: raise HTTPException(403, 'Only institution administrators can prepare cumulative transcripts')
        query = query.filter(AcademicClass.supervisor_id == ctx.user_id)
    groups = query.order_by(AcademicClass.academic_year, AcademicClass.name, AcademicClass.id).all()
    if not groups: raise HTTPException(404, 'No authorized enrollment history found')
    return groups


def build(db, ctx, student_id, kind, class_id=None, period_id=None, remarks=''):
    student = learner(db, ctx, student_id)
    if kind == 'REPORT_CARD' and class_id is None: raise HTTPException(422, 'Choose a teaching group for the report card')
    if kind == 'TRANSCRIPT' and (class_id or period_id): raise HTTPException(422, 'A transcript includes all enrollment history')
    groups = groups_for(db, ctx, student, class_id)
    institution = db.get(Institution, ctx.institution_id)
    settings = learning_settings(institution); config = academic_configuration(institution)
    person = db.get(User, student.user_id)
    period = scoped(db, AcademicPeriod, ctx).filter_by(id=period_id).first() if period_id else None
    year = scoped(db, AcademicYear, ctx).filter_by(name=groups[0].academic_year).first() if class_id else None
    if period_id and (not period or not year or period.year_id != year.id):
        raise HTTPException(422, 'Select a period in this teaching group’s academic year')
    issues=[]; sections=[]; earned={}; final_attempts=[]; total_assessments=0; completions=0
    for group in groups:
        programme = db.get(Programme, group.programme_id) if group.programme_id else None
        level = db.get(StudyLevel, group.level_id) if group.level_id else None
        subjects = scoped(db, Subject, ctx).filter_by(class_id=group.id).order_by(Subject.name, Subject.id).all()
        registrations = {r.subject_id for r in scoped(db, CourseRegistration, ctx).filter_by(student_id=student.id).all()}
        rows=[]
        for subject in subjects:
            scores = {s.coursework_id:s for s in scoped(db, Score, ctx).join(Coursework, Coursework.id==Score.coursework_id).filter(
                Coursework.subject_id==subject.id, Score.student_id==student.id).all()}
            completion = scoped(db, CourseCompletion, ctx).filter_by(subject_id=subject.id, student_id=student.id).first()
            if subject.registration_mode=='INDIVIDUAL' and subject.id not in registrations and not scores and not completion: continue
            works = scoped(db, Coursework, ctx).filter_by(subject_id=subject.id, published=True).order_by(Coursework.created_at, Coursework.id).all()
            unit = db.get(CatalogueUnit, subject.catalogue_id) if subject.catalogue_id else None
            course_period = db.get(AcademicPeriod, subject.period_id) if subject.period_id else None
            if completion and completion.released and completion.outcome=='EXEMPT': works=[]
            outcomes=[]; points=Decimal(0); maximum=Decimal(0)
            for work in works:
                if period:
                    assigned_period=work.period_id or subject.period_id
                    if assigned_period is None:
                        issues.append(f'{subject.name} / {work.title}: assign an academic period before issuing a period report.')
                        continue
                    if assigned_period != period.id: continue
                if not work.grades_released:
                    issues.append(f'{subject.name} / {work.title}: results are withheld.'); continue
                mark=scores.get(work.id)
                if not mark:
                    issues.append(f'{subject.name} / {work.title}: this learner has no recorded outcome.'); continue
                total_assessments+=1
                if work.assessment_mode=='NUMERIC': points+=mark.score; maximum+=work.max_score
                outcomes.append(dict(assessment=work.title, mode=work.assessment_mode,
                    score=str(mark.score) if mark.score is not None else None,
                    maximum=str(work.max_score) if work.assessment_mode=='NUMERIC' else None,
                    competency=mark.competency_label, grade=grade_label(mark.score, work.max_score, settings, work.grading_bands),
                    feedback=mark.feedback))
            final=None
            final_scope='ALL' if not period or subject.period_id==period.id else str(period.id)
            final_row=db.query(FinalGrade).filter_by(institution_id=ctx.institution_id,subject_id=subject.id,student_id=student.id,scope=final_scope).first()
            if not (completion and completion.released and completion.outcome=='EXEMPT') and (final_row or any(o['mode']=='NUMERIC' for o in outcomes)) and finals.policy_for(db,subject)['enabled']:
                if not final_row or not finals.current(db,final_row,subject):
                    issues.append(f'{subject.name}: approve and release the current final grade before issuing this report.')
                else:
                    final=final_row.result
                    if final_scope=='ALL':
                        final_attempts.append(dict(id=str(final_row.id),course_key=str(subject.catalogue_id or subject.id),
                            order=finals.attempt_order(db,subject,final_row),result=final,exempt=bool(completion and completion.outcome=='EXEMPT')))
            approved=None
            if completion and (not period or subject.period_id == period.id):
                if completion.released:
                    completions+=1
                    approved=dict(outcome=completion.outcome, credits=str(completion.credits) if config['credits_enabled'] else None)
                    if config['credits_enabled'] and completion.outcome in {'PASSED','EXEMPT'}:
                        key=str(subject.catalogue_id or subject.id); earned[key]=max(earned.get(key,Decimal(0)),completion.credits)
                else: issues.append(f'{subject.name}: final course outcome is withheld.')
            if period and not outcomes and subject.period_id != period.id: continue
            rows.append(dict(name=subject.name, code=unit.code if unit else None, period=course_period.name if course_period else None,
                outcomes=outcomes, completion=approved, final_grade=final,
                observed_percentage=str(round(points/maximum*100,2)) if maximum else None))
        attendance=scoped(db, Attendance, ctx).filter_by(student_id=student.id,class_id=group.id,scope_key='class')
        if period: attendance=attendance.filter(Attendance.day>=period.start_date,Attendance.day<=period.end_date)
        counts=Counter(r.status for r in attendance.all())
        denominator=sum(counts[s] for s in ['PRESENT','LATE','ABSENT'])
        sections.append(dict(group=group.name,year=group.academic_year,programme=programme.name if programme else None,
            award=programme.award if programme else None,level=level.name if level else None,courses=rows,
            attendance=dict(counts=dict(sorted(counts.items())),rate=str(round(Decimal(counts['PRESENT']+counts['LATE'])/denominator*100,2)) if denominator else None)))
    if not total_assessments and not completions: issues.append('No released academic outcomes are available for this scope.')
    title='Academic transcript' if kind=='TRANSCRIPT' else 'Learning progress report' if config['assessment_policy']=='COMPETENCY' else 'Report card'
    snapshot=dict(schema=1,title=title,kind=kind,institution=dict(name=institution.name,code=institution.code,type=institution.type.value,
        address=institution.address,email=institution.official_email,phone=institution.phone),
        learner=dict(name=f'{person.first_name} {person.last_name}',admission_number=student.admission_number),
        labels={k:v for k,v in settings.items() if k.endswith('_label')},credits_enabled=config['credits_enabled'],
        period=period.name if period else 'All recorded academic years' if kind=='TRANSCRIPT' else 'Full academic year',
        sections=sections,earned_credits=str(sum(earned.values(),Decimal(0))) if config['credits_enabled'] else None,
        gpa=gpa(final_attempts),remarks=remarks,method=('Competency observations are reported individually using the assessment’s saved rubric. ' if config['assessment_policy']=='COMPETENCY' else 'Observed percentages are total recorded numeric points divided by their maxima, not weighted final grades. Competencies remain separate. ') + ('Credits require released administrator-approved completion. Awards are not inferred. ' if config['credits_enabled'] else '') + 'Approved final grades use the named saved policy and its assessment weights. GPA uses released full-offering grades, attempted credits and the stated repeat rule; different GPA schemes remain separate. Attendance includes recorded daily registers only; it is not a count of scheduled school days.')
    digest=hashlib.sha256(json.dumps(dict(snapshot=snapshot,issues=issues),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return dict(snapshot=snapshot,issues=issues,ready=not issues,source_digest=digest)
