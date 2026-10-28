"""Shared entry and progression checks, including legacy enrollment doors."""
from decimal import Decimal
from collections import Counter
from pydantic import Field,model_validator
from fastapi import HTTPException
from app.schemas.academic import Input
from app.models.academic import AcademicClass,Attendance,Coursework,Enrollment,Score,Subject
from app.models.curriculum import CatalogueUnit,CourseCompletion,CourseRegistration,StudyLevel
from app.models.final_grade import FinalGrade
from app.models.pilot import AcademicYear
from app.models.progression import Prerequisite

from app.services.grading_rules import digest


class ProgressionRules(Input):
    enabled:bool=False
    name:str=Field(default='Institution progression policy',min_length=1,max_length=100)
    require_closed_source:bool=True
    allow_same_year_level:bool=False
    require_all_completed:bool=False
    minimum_passed_courses:int=Field(default=0,ge=0,le=200)
    minimum_credits:float=Field(default=0,ge=0,le=10000,allow_inf_nan=False)
    minimum_gpa:float|None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    minimum_attendance:float|None=Field(default=None,ge=0,le=100,allow_inf_nan=False)
    maximum_failed_courses:int|None=Field(default=None,ge=0,le=200)
    competency_labels:list[str]=Field(default_factory=list,max_length=12)
    enforce_prerequisites:bool=False
    exemptions_satisfy_prerequisites:bool=True
    retakes_enabled:bool=True
    maximum_attempts:int=Field(default=3,ge=1,le=20)
    allow_repeat_passed:bool=False
    require_previous_attempt_complete:bool=True
    allow_override:bool=False

    @model_validator(mode='after')
    def labels(self):
        if any(not s.strip() or len(s)>60 for s in self.competency_labels) or len(set(self.competency_labels))!=len(self.competency_labels):raise ValueError('Use distinct valid competency labels')
        return self


def rules(db,tenant):
    from app.models.institution import Institution
    return ProgressionRules.model_validate((db.get(Institution,tenant).academic_configuration or {}).get('progression_rules',{})).model_dump()


def attainment(db,tenant,student,subject):
    from app.services.final_grades import current
    completion=db.query(CourseCompletion).filter_by(institution_id=tenant,subject_id=subject.id,student_id=student,released=True).first()
    if completion and completion.outcome=='EXEMPT':return dict(outcome='EXEMPT',credits=str(completion.credits),percentage=None)
    grade=db.query(FinalGrade).filter_by(institution_id=tenant,subject_id=subject.id,student_id=student,scope='ALL').first()
    if grade:
        if not current(db,grade,subject):return None
        return dict(outcome='PASSED' if grade.result['passed'] else 'FAILED',credits=grade.result['credits'] or '0',percentage=grade.result['percentage'])
    if completion:return dict(outcome=completion.outcome,credits=str(completion.credits),percentage=None)
    accepted=rules(db,tenant)['competency_labels']
    if accepted:
        works=db.query(Coursework).filter_by(institution_id=tenant,subject_id=subject.id,published=True,assessment_mode='COMPETENCY').all()
        marks={m.coursework_id:m for m in db.query(Score).filter_by(institution_id=tenant,student_id=student).filter(Score.coursework_id.in_([w.id for w in works]))}
        if works and all(w.grades_released and w.id in marks and marks[w.id].competency_label in accepted for w in works):
            return dict(outcome='PASSED',credits='0',percentage=None)
    return None


def attempts(db,tenant,student,course,exclude=None):
    query=db.query(Subject).filter_by(institution_id=tenant,catalogue_id=course)
    if exclude:query=query.filter(Subject.id!=exclude)
    enrolled={e.class_id for e in db.query(Enrollment).filter_by(institution_id=tenant,student_id=student).all()}
    registered={r.subject_id for r in db.query(CourseRegistration).filter_by(institution_id=tenant,student_id=student).all()}
    historical={r.subject_id for r in db.query(CourseCompletion).filter_by(institution_id=tenant,student_id=student).all()}
    historical|={r[0] for r in db.query(Coursework.subject_id).join(Score,Score.coursework_id==Coursework.id).filter(Score.institution_id==tenant,Score.student_id==student).distinct()}
    return [s for s in query.all() if s.id in registered or s.id in historical or s.registration_mode=='COHORT' and s.class_id in enrolled]


def course_check(db,tenant,student,subject):
    policy=rules(db,tenant);issues=[]
    if not policy['enabled'] or not subject.catalogue_id:return issues
    if policy['enforce_prerequisites']:
        for link in db.query(Prerequisite).filter_by(institution_id=tenant,course_id=subject.catalogue_id).all():
            valid=False
            for prior in attempts(db,tenant,student,link.required_id,subject.id):
                outcome=attainment(db,tenant,student,prior)
                if outcome and outcome['outcome']=='EXEMPT' and policy['exemptions_satisfy_prerequisites']:valid=True
                if outcome and outcome['outcome']=='PASSED' and (link.minimum_percentage is None or outcome['percentage'] is not None and Decimal(outcome['percentage'])>=Decimal(link.minimum_percentage)):valid=True
            if not valid:issues.append('Prerequisite not satisfied: '+db.get(CatalogueUnit,link.required_id).code)
    prior=attempts(db,tenant,student,subject.catalogue_id,subject.id)
    outcomes=[attainment(db,tenant,student,s) for s in prior]
    if prior:
        if not policy['retakes_enabled']:issues.append('Repeat attempts are disabled.')
        if len(prior)>=policy['maximum_attempts']:issues.append('Maximum course attempts reached.')
        if not policy['allow_repeat_passed'] and any(o and o['outcome'] in {'PASSED','EXEMPT'} for o in outcomes):issues.append('This course was already passed or exempted.')
        if policy['require_previous_attempt_complete'] and any(o is None for o in outcomes):issues.append('A previous course attempt is not complete and released.')
    return issues


def assert_course(db,tenant,student,subject):
    issues=course_check(db,tenant,student,subject)
    if issues:raise HTTPException(409,'Enrollment blocked: '+'; '.join(issues))


def assert_group(db,tenant,student,class_id):
    for subject in db.query(Subject).filter_by(institution_id=tenant,class_id=class_id,registration_mode='COHORT').all():assert_course(db,tenant,student,subject)


def evaluate(db,tenant,student,source,target,decision):
    from app.services.final_grades import academic_results
    policy=rules(db,tenant);structural=[];issues=[]
    if not policy['enabled']:structural.append('Platform admin has not enabled progression.')
    if not db.query(Enrollment).filter_by(institution_id=tenant,class_id=source.id,student_id=student).first():structural.append('Learner has no source enrollment.')
    source_year=db.query(AcademicYear).filter_by(institution_id=tenant,name=source.academic_year).first()
    if not source_year:structural.append('Configure the source academic year.')
    elif policy['require_closed_source'] and source_year.status!='CLOSED':structural.append('Close the source academic year first.')
    if target:
        target_year=db.query(AcademicYear).filter_by(institution_id=tenant,name=target.academic_year).first()
        if not target_year or target_year.status=='CLOSED':structural.append('Destination needs an open configured academic year.')
        if target.id==source.id:structural.append('Choose another destination group.')
        if db.query(Enrollment).filter_by(institution_id=tenant,student_id=student,class_id=target.id,active=True).first():structural.append('Learner is already enrolled in this destination.')
        if target.programme_id!=source.programme_id:structural.append('Destination must belong to the same programme.')
        source_level=db.get(StudyLevel,source.level_id) if source.level_id else None
        target_level=db.get(StudyLevel,target.level_id) if target.level_id else None
        if source_year and target_year:
            later=target_year.start_date>source_year.end_date
            same=target_year.id==source_year.id and policy['allow_same_year_level'] and decision=='ADVANCE'
            if not later and not same:structural.append('Choose a later year, or enable same-year level progression.')
            if same and (not source_level or not target_level):structural.append('Same-year progression requires configured study levels.')
        if source_level and target_level:
            if decision=='ADVANCE' and target_level.position<=source_level.position:structural.append('Advancement must move to a higher level.')
            if decision=='REPEAT' and target_level.position!=source_level.position:structural.append('A repeat must keep the same study level.')
        for offering in db.query(Subject).filter_by(institution_id=tenant,class_id=target.id,registration_mode='COHORT').all():
            structural.extend(course_check(db,tenant,student,offering))
    elif decision!='COMPLETE':structural.append('Select a destination group.')
    subjects=db.query(Subject).filter_by(institution_id=tenant,class_id=source.id).all()
    registered={r.subject_id for r in db.query(CourseRegistration).filter_by(institution_id=tenant,student_id=student)}
    registered|={r.subject_id for r in db.query(CourseCompletion).filter_by(institution_id=tenant,student_id=student)}
    registered|={r[0] for r in db.query(Coursework.subject_id).join(Score,Score.coursework_id==Coursework.id).filter(Score.institution_id==tenant,Score.student_id==student).distinct()}
    passed=failed=incomplete=applicable=0;earned={}
    for subject in subjects:
        if subject.registration_mode=='INDIVIDUAL' and subject.id not in registered:continue
        applicable+=1
        outcome=attainment(db,tenant,student,subject)
        if not outcome:incomplete+=1
        elif outcome['outcome']=='FAILED':failed+=1
        else:
            passed+=1;key=subject.catalogue_id or subject.id;earned[str(key)]=max(earned.get(str(key),Decimal(0)),Decimal(outcome['credits']))
    credits=sum(earned.values(),Decimal(0))
    records=db.query(Attendance).filter_by(institution_id=tenant,class_id=source.id,student_id=student,scope_key='class').all();counts=Counter(r.status for r in records)
    denominator=sum(counts[s] for s in ['PRESENT','LATE','ABSENT']);attendance=Decimal(counts['PRESENT']+counts['LATE'])/denominator*100 if denominator else None
    gpas=academic_results(db,tenant,student)['gpa'];gpa_value=Decimal(gpas[0]['gpa']) if len(gpas)==1 and gpas[0]['gpa'] is not None else None
    if decision!='REPEAT':
        if passed<policy['minimum_passed_courses']:issues.append('Minimum passed courses not met.')
        if policy['require_all_completed'] and (incomplete or not applicable):issues.append('Complete and release all source outcomes.')
        if policy['maximum_failed_courses'] is not None and failed>policy['maximum_failed_courses']:issues.append('Too many failed courses.')
        if credits<Decimal(str(policy['minimum_credits'])):issues.append('Minimum source-group earned credits not met.')
        if policy['minimum_gpa'] is not None and (gpa_value is None or gpa_value<Decimal(str(policy['minimum_gpa']))):issues.append('Minimum cumulative GPA not met, or GPA scheme is ambiguous.')
        if policy['minimum_attendance'] is not None and (attendance is None or attendance<Decimal(str(policy['minimum_attendance']))):issues.append('Minimum recorded attendance not met.')
    metrics=dict(passed=passed,failed=failed,incomplete=incomplete,source_credits=str(credits),cumulative_gpa=str(gpa_value) if gpa_value is not None else None,attendance=str(round(attendance,2)) if attendance is not None else None)
    data=dict(policy=policy,metrics=metrics,structural=list(dict.fromkeys(structural)),blockers=issues,eligible=not structural and not issues,
        source_id=str(source.id),target_id=str(target.id) if target else None,student_id=str(student),decision=decision)
    data['digest']=digest(data);return data


def assert_transition(db, tenant, student, class_id):
    """Existing learners advance through a reviewed decision, including after completion."""
    if not rules(db, tenant)['enabled']: return
    target = db.get(AcademicClass, class_id)
    prior = db.query(AcademicClass).join(Enrollment, Enrollment.class_id == AcademicClass.id).filter(
        Enrollment.institution_id == tenant, Enrollment.student_id == student,
        AcademicClass.id != class_id).all()
    if any(c.academic_year != target.academic_year or c.level_id != target.level_id for c in prior):
        raise HTTPException(409, 'Use Student progression to review advancement or repetition for an existing learner.')


def lock_entry(db, tenant):
    """Serialize entry with policy changes and recorded academic outcomes.

    Use the same institution -> calendar order as reviewed progression approvals.
    Academic mark/attendance writers already lock their configured calendar year.
    """
    from app.models.institution import Institution
    db.query(Institution).filter_by(id=tenant).with_for_update().one()
    db.query(AcademicYear).filter_by(institution_id=tenant).order_by(AcademicYear.start_date).with_for_update().all()
