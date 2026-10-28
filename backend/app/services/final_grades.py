import uuid
from app.models.academic import AcademicClass, Coursework, Score, Subject
from app.models.curriculum import CatalogueUnit, CourseCompletion
from app.models.final_grade import FinalGrade
from app.models.institution import Institution
from app.models.pilot import AcademicYear, AcademicPeriod
from app.services.academic_configuration import academic_configuration
from app.services.grading_rules import GradingRules, calculate, digest, gpa
from fastapi import HTTPException


def scope_period(db,subject,period_id):
    if not period_id:return 'ALL'
    group=db.get(AcademicClass,subject.class_id)
    period=db.query(AcademicPeriod).filter_by(id=period_id,institution_id=subject.institution_id).first()
    year=db.query(AcademicYear).filter_by(institution_id=subject.institution_id,name=group.academic_year).first()
    if not period or not year or period.year_id!=year.id:raise HTTPException(422,'Choose a period in this offering’s academic year')
    return str(period.id)


def policy_for(db,subject):
    return GradingRules.model_validate(subject.grading_policy or academic_configuration(db.get(Institution,subject.institution_id))['grading_rules']).model_dump()


def prepare(db,subject,student_ids):
    works=db.query(Coursework).filter_by(institution_id=subject.institution_id,subject_id=subject.id,published=True,assessment_mode='NUMERIC').order_by(Coursework.id).all()
    scores={}
    for row in db.query(Score).filter(Score.institution_id==subject.institution_id,Score.student_id.in_(student_ids),Score.coursework_id.in_([w.id for w in works])).all():
        scores.setdefault(row.student_id,{})[row.coursework_id]=row
    unit=db.get(CatalogueUnit,subject.catalogue_id) if subject.catalogue_id else None
    return dict(policy=policy_for(db,subject),works=works,scores=scores,credits=str(unit.credits) if unit and unit.credits is not None else None)


def compute(db,subject,student_id,scope='ALL',prepared=None):
    prepared=prepared or prepare(db,subject,[student_id])
    policy=prepared['policy'];works=prepared['works'];scores=prepared['scores'].get(student_id,{})
    assessments=[];unassigned=False
    for w in works:
        if scope!='ALL':
            period=w.period_id or subject.period_id
            if not period:unassigned=True;continue
            if str(period)!=scope:continue
        score=scores.get(w.id)
        assessments.append(dict(id=str(w.id),title=w.title,kind=w.kind,maximum=str(w.max_score),
            score=str(score.score) if score and score.score is not None else None,released=w.grades_released))
    data=calculate(policy,assessments)
    if unassigned:data.update(ready=False,issues=[*data['issues'],'Assign a reporting period to every published numeric assessment.'],result=None)
    credits=prepared['credits']
    if data['ready'] and policy['gpa_enabled'] and (credits is None or float(credits)<=0):
        data.update(ready=False,issues=['GPA needs a linked catalogue course with positive credits.'],result=None)
    if data['result']:data['result']['credits']=credits
    data['source_digest']=digest(dict(policy=policy,assessments=assessments,scope=scope,credits=credits,unassigned=unassigned))
    return data


def current(db,row,subject=None):
    subject=subject or db.get(Subject,row.subject_id)
    data=compute(db,subject,row.student_id,row.scope)
    return row.released and data['ready'] and data['source_digest']==row.source_digest


def academic_results(db,institution_id,student_id):
    rows=db.query(FinalGrade,Subject,AcademicClass).join(Subject,Subject.id==FinalGrade.subject_id).join(AcademicClass,AcademicClass.id==Subject.class_id).filter(
        FinalGrade.institution_id==institution_id,FinalGrade.student_id==student_id,FinalGrade.released.is_(True)).order_by(AcademicClass.academic_year,FinalGrade.created_at,FinalGrade.id).all()
    results=[];attempts=[]
    for row,subject,group in rows:
        if not current(db,row,subject):continue
        period=db.get(AcademicPeriod,uuid.UUID(row.scope)) if row.scope!='ALL' else None
        completion=db.query(CourseCompletion).filter_by(institution_id=institution_id,subject_id=subject.id,student_id=student_id,released=True).first()
        results.append(dict(id=str(row.id),subject_id=str(subject.id),course=subject.name,year=group.academic_year,
            scope=row.scope,period=period.name if period else 'Full offering',result=row.result))
        if row.scope=='ALL':
            attempts.append(dict(id=str(row.id),course_key=str(subject.catalogue_id or subject.id),order=attempt_order(db,subject,row),
                exempt=bool(completion and completion.outcome=='EXEMPT'),result=row.result))
    return dict(final_grades=results,gpa=gpa(attempts))


def attempt_order(db,subject,row):
    group=db.get(AcademicClass,subject.class_id)
    period=db.get(AcademicPeriod,subject.period_id) if subject.period_id else None
    year=db.query(AcademicYear).filter_by(institution_id=subject.institution_id,name=group.academic_year).first()
    start=period.start_date.isoformat() if period else year.start_date.isoformat() if year else group.created_at.date().isoformat()
    return (start,subject.created_at.isoformat(),str(subject.id),row.created_at.isoformat(),str(row.id))
