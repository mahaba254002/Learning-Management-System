"""Progression and entry controls through real API endpoints and isolated records."""
import uuid
from datetime import date
from decimal import Decimal
import pytest
from test_teaching import env
from test_curriculum import owner
from app.models.academic import AcademicClass, Enrollment, Subject, Attendance, Score
from app.models.curriculum import CatalogueUnit, CourseCompletion, CourseRegistration, StudyLevel
from app.models.pilot import AcademicYear
from app.models.progression import Prerequisite, ProgressionDecision
from app.models.institution import InstitutionType
from app.models.user import UserRole
from app.services.academic_configuration import template, AcademicConfiguration
from app.services.progression import ProgressionRules


def setup(env, **overrides):
    db=env['db'];tenant=env['institutions'][0]
    config=template(tenant.type);config['progression_rules']={**ProgressionRules(enabled=True).model_dump(),**overrides};tenant.academic_configuration=config
    db.add_all([AcademicYear(institution_id=tenant.id,name='2026',start_date=date(2026,1,1),end_date=date(2026,12,31),status='CLOSED'),AcademicYear(institution_id=tenant.id,name='2027',start_date=date(2027,1,1),end_date=date(2027,12,31),status='PLANNED')])
    low=StudyLevel(institution_id=tenant.id,code='L1',name='Level 1',position=1)
    high=StudyLevel(institution_id=tenant.id,code='L2',name='Level 2',position=2)
    db.add_all([low,high]);db.flush();env['cls'].level_id=low.id
    target=AcademicClass(institution_id=tenant.id,name='Next cohort',academic_year='2027',level_id=high.id)
    db.add(target);db.commit()
    return target


def body(env,target,decision='ADVANCE'):
    return dict(student_id=str(env['student'].id),source_class_id=str(env['cls'].id),target_class_id=str(target.id) if target else None,decision=decision)


def policy(env, **changes):
    tenant=env['institutions'][0];config={**tenant.academic_configuration};config['progression_rules']={**config['progression_rules'],**changes};tenant.academic_configuration=config;env['db'].commit()


def outcome(env,result='PASSED',released=True):
    row=CourseCompletion(institution_id=env['cls'].institution_id,subject_id=env['subject'].id,student_id=env['student'].id,outcome=result,released=released,credits=Decimal('3'))
    env['db'].add(row);env['db'].commit();return row


def preview(env,target,decision='ADVANCE'):
    response=env['as_user'](env['admin']).post('/api/institution/progression/preview',json=body(env,target,decision));assert response.status_code==200,response.text;return response.json()


def test_advance_retains_records_and_own_student_history(env):
    target=setup(env,require_all_completed=True,minimum_passed_courses=1);outcome(env)
    data=preview(env,target);assert data['eligible'];assert data['metrics']['passed']==1
    c=env['as_user'](env['admin']);request={**body(env,target), 'expected_digest':data['digest']}
    assert c.post('/api/institution/progression/approve',json=request).status_code==201
    assert env['db'].query(Enrollment).filter_by(student_id=env['student'].id).count()==2
    assert env['db'].query(CourseCompletion).count()==1
    assert c.post('/api/institution/progression/approve',json=request).status_code==409
    rows=c.get('/api/institution/progression/history').json();assert rows[0]['destination']=='Next cohort · 2027'
    rows=env['as_user'](env['pupil']).get('/api/student/progression').json();assert len(rows)==1;assert 'snapshot' not in rows[0]
    assert env['as_user'](env['other_pupil']).get('/api/student/progression').json()==[]


@pytest.mark.parametrize('result,released,eligible', [('PASSED',True,True),('FAILED',True,False),('EXEMPT',True,True),('PASSED',False,False)])
def test_released_outcomes_control_progression(env,result,released,eligible):
    target=setup(env,require_all_completed=True,minimum_passed_courses=1,maximum_failed_courses=0);outcome(env,result,released)
    assert preview(env,target)['eligible'] is eligible


def test_stale_preview_cannot_approve(env):
    target=setup(env,minimum_passed_courses=1);row=outcome(env);data=preview(env,target)
    row.released=False;env['db'].commit()
    response=env['as_user'](env['admin']).post('/api/institution/progression/approve',json={**body(env,target),'expected_digest':data['digest']})
    assert response.status_code==409;assert env['db'].query(ProgressionDecision).count()==0


@pytest.mark.parametrize('permitted,status',[(False,409),(True,201)])
def test_academic_override_is_explicit_and_policy_controlled(env,permitted,status):
    target=setup(env,minimum_passed_courses=2,allow_override=permitted);data=preview(env,target)
    response=env['as_user'](env['admin']).post('/api/institution/progression/approve',json={**body(env,target),'expected_digest':data['digest'],'override_reason':'Academic board approved conditional progression.'})
    assert response.status_code==status,response.text


def test_structural_issues_cannot_be_overridden(env):
    target=setup(env,allow_override=True);target.level_id=env['cls'].level_id;env['db'].commit();data=preview(env,target)
    assert data['structural']
    assert env['as_user'](env['admin']).post('/api/institution/progression/approve',json={**body(env,target),'expected_digest':data['digest'],'override_reason':'I want to bypass the level structure.'}).status_code==409


def test_repeat_skips_academic_threshold_but_preserves_level(env):
    target=setup(env,minimum_passed_courses=20);target.level_id=env['cls'].level_id;env['db'].commit()
    assert preview(env,target,'REPEAT')['eligible']
    assert not preview(env,target,'ADVANCE')['eligible']


def test_completion_creates_no_destination(env):
    setup(env);data=preview(env,None,'COMPLETE');assert data['eligible']
    assert env['as_user'](env['admin']).post('/api/institution/progression/approve',json={**body(env,None,'COMPLETE'),'expected_digest':data['digest']}).status_code==201
    assert env['db'].query(Enrollment).filter_by(student_id=env['student'].id).count()==1


@pytest.mark.parametrize('role',['teacher','supervisor','pupil','outsider'])
def test_approval_is_admin_only(env,role):
    target=setup(env)
    assert env['as_user'](env[role]).post('/api/institution/progression/approve',json=body(env,target)).status_code==403


def test_tenant_isolation(env):
    target=setup(env);request=body(env,target);request['student_id']=str(env['other_student'].id)
    assert env['as_user'](env['admin']).post('/api/institution/progression/preview',json=request).status_code==404


def test_attendance_uses_recorded_class_days_and_excludes_excused(env):
    target=setup(env,minimum_attendance=75);db=env['db']
    assert not preview(env,target)['eligible']
    for day,status in [(1,'PRESENT'),(2,'LATE'),(3,'ABSENT'),(4,'EXCUSED')]:db.add(Attendance(institution_id=target.institution_id,class_id=env['cls'].id,student_id=env['student'].id,day=date(2026,2,day),scope_key='class',status=status))
    db.commit();data=preview(env,target);assert data['metrics']['attendance']=='66.67';assert not data['eligible']
    policy(env,minimum_attendance=66);assert preview(env,target)['eligible']


def test_normal_enrollment_cannot_bypass_progression(env):
    target=setup(env,minimum_passed_courses=99)
    response=env['as_user'](env['admin']).post(f'/api/teaching/classes/{target.id}/enrollments',json=dict(admission_number='A001'))
    assert response.status_code==409;assert 'progression' in response.json()['detail']


def entry_setup(env, **rules):
    target=setup(env,enforce_prerequisites=True,**rules);db=env['db'];tenant=target.institution_id
    first=CatalogueUnit(institution_id=tenant,code='C101',name='Foundation')
    second=CatalogueUnit(institution_id=tenant,code='C102',name='Advanced')
    db.add_all([first,second]);db.flush();env['subject'].catalogue_id=first.id
    subject=Subject(institution_id=tenant,class_id=target.id,name='Advanced',catalogue_id=second.id,registration_mode='INDIVIDUAL',teacher_id=env['teacher'].id)
    db.add(subject);db.flush();db.add(Enrollment(institution_id=tenant,class_id=target.id,student_id=env['student'].id));db.add(Prerequisite(institution_id=tenant,course_id=second.id,required_id=first.id));db.commit()
    return target,subject,first,second


def register(env,subject):
    return env['as_user'](env['admin']).put(f'/api/institution/subjects/{subject.id}/registrations',json=dict(student_id=str(env['student'].id),active=True))


def test_prerequisites_block_unreleased_and_allow_released_completion(env):
    _,subject,_,_=entry_setup(env)
    assert register(env,subject).status_code==409
    row=outcome(env,released=False);assert register(env,subject).status_code==409
    row.released=True;env['db'].commit();assert register(env,subject).status_code==200


def test_prerequisite_percentage_requires_numeric_final_not_manual_pass(env):
    _,subject,_,_=entry_setup(env);outcome(env)
    link=env['db'].query(Prerequisite).one();link.minimum_percentage='60';env['db'].commit()
    assert register(env,subject).status_code==409
    row=env['db'].query(CourseCompletion).one();row.outcome='EXEMPT';env['db'].commit()
    assert register(env,subject).status_code==200


@pytest.mark.parametrize('changes,result,expected', [({},'FAILED',200),({'retakes_enabled':False},'FAILED',409),({'maximum_attempts':1},'FAILED',409),({},'PASSED',409),({'allow_repeat_passed':True},'PASSED',200)])
def test_retake_rules(env,changes,result,expected):
    _,subject,first,_=entry_setup(env,**changes);env['db'].query(Prerequisite).delete();subject.catalogue_id=first.id;outcome(env,result);env['db'].commit()
    response=register(env,subject);assert response.status_code==expected,response.text
    assert env['db'].query(CourseCompletion).count()==1


def test_parallel_incomplete_retake_rejected(env):
    _,subject,first,_=entry_setup(env);env['db'].query(Prerequisite).delete();subject.catalogue_id=first.id;env['db'].commit()
    assert register(env,subject).status_code==409


def test_new_cohort_offering_cannot_bypass_entry_rules(env):
    target,subject,first,second=entry_setup(env)
    response=env['as_user'](env['admin']).post(f'/api/teaching/classes/{target.id}/subjects',json=dict(name='Bypass',teacher_id=str(env['teacher'].id),catalogue_id=str(second.id),registration_mode='COHORT'))
    assert response.status_code==409,response.text
    assert env['db'].query(Subject).filter_by(name='Bypass').count()==0


def test_prerequisite_cycles_versions_and_ownership(env):
    target,subject,first,second=entry_setup(env);platform=owner(env);c=env['as_user'](platform);root=f'/api/platform/institutions/{target.institution_id}/prerequisites';data=c.get(root).json()
    request=dict(requirements=[dict(required_id=str(second.id))],expected_updated_at=data['updated_at'])
    assert c.put(root+'/'+str(first.id),json=request).status_code==422
    request['requirements']=[dict(required_id=str(uuid.uuid4()))]
    assert c.put(root+'/'+str(first.id),json=request).status_code==404
    request['requirements']=[];assert c.put(root+'/'+str(first.id),json=request).status_code==200
    assert c.put(root+'/'+str(first.id),json=request).status_code==409
    assert env['as_user'](env['admin']).put(root+'/'+str(first.id),json=request).status_code==403


@pytest.mark.parametrize('kind',list(InstitutionType))
def test_platform_can_configure_progression_for_every_customer_type(env,kind):
    institution=env['institutions'][0];institution.type=kind
    if kind==InstitutionType.KINDERGARTEN:env['work'].assessment_mode='COMPETENCY';env['work'].rubric_labels=['Needs support','Developing','Secure']
    env['db'].commit();c=env['as_user'](owner(env));root=f'/api/platform/institutions/{institution.id}/academic-configuration';data=c.get(root).json();assert not data['configuration']['progression_rules']['enabled']
    data['configuration']['progression_rules']['enabled']=True
    response=c.put(root,json={key:data[key] for key in ['configuration','labels','updated_at']}|{'expected_updated_at':data['updated_at']})
    # Input rejects unexpected fields, keeping contracts explicit.
    assert response.status_code==422
    response=c.put(root,json=dict(configuration=data['configuration'],labels=data['labels'],expected_updated_at=data['updated_at']))
    assert response.status_code==200,response.text
    assert response.json()['configuration']['progression_rules']['enabled']


def test_gpa_and_credit_require_compatible_policy():
    with pytest.raises(ValueError):AcademicConfiguration(progression_rules=ProgressionRules(minimum_gpa=2))
    with pytest.raises(ValueError):AcademicConfiguration(progression_rules=ProgressionRules(minimum_credits=2))


@pytest.mark.parametrize('label,released,expected',[('Secure',True,True),('Developing',True,False),('Secure',False,False)])
def test_competency_progression_does_not_require_numeric_grades(env,label,released,expected):
    target=setup(env,competency_labels=['Secure'],require_all_completed=True,minimum_passed_courses=1)
    work=env['work'];work.assessment_mode='COMPETENCY';work.rubric_labels=['Needs support','Developing','Secure'];work.published=True;work.grades_released=released
    env['db'].add(Score(institution_id=target.institution_id,student_id=env['student'].id,coursework_id=work.id,competency_label=label));env['db'].commit()
    assert preview(env,target)['eligible'] is expected


def test_gpa_and_credit_thresholds_use_current_approved_final_grades(env):
    from test_grading_rules import setup as numeric_setup, approve
    numeric_setup(env);approve(env)
    # Add progression after final approval; closing the year keeps released results valid.
    target=setup(env,minimum_gpa=2,minimum_credits=3)
    config={**env['institutions'][0].academic_configuration};from test_grading_rules import policy as numeric_policy
    config.update(credits_enabled=True,assessment_policy='MIXED',grading_rules=numeric_policy(gpa_enabled=True));env['institutions'][0].academic_configuration=config;env['db'].commit()
    data=preview(env,target);assert data['eligible'];assert data['metrics']['cumulative_gpa']=='2.00'
    env['db'].query(Score).filter_by(coursework_id=env['work'].id).one().score=0;env['db'].commit()
    data=preview(env,target);assert not data['eligible'];assert data['metrics']['source_credits']=='0';assert data['metrics']['cumulative_gpa'] is None


def test_import_preview_and_commit_recheck_prerequisites(env,monkeypatch):
    from app.core import rate_limit as limiter
    monkeypatch.setattr(limiter.redis_client,'incr',lambda key:1);monkeypatch.setattr(limiter.redis_client,'expire',lambda *a:True)
    target,subject,first,second=entry_setup(env);subject.registration_mode='COHORT';env['db'].commit()
    c=env['as_user'](env['admin']);request=dict(class_id=str(target.id),rows=[dict(first_name='New',last_name='Learner',admission_number='A999',login_method='EMAIL',email='new@example.test')])
    assert c.post('/api/institution/student-imports/preview',json=request).status_code==409
    policy(env,enforce_prerequisites=False)
    review=c.post('/api/institution/student-imports/preview',json=request);assert review.status_code==200,review.text
    request['preview_token']=review.json()['preview_token'];assert request['preview_token']
    policy(env,enforce_prerequisites=True)
    assert c.post('/api/institution/student-imports/commit',json=request).status_code==409
    assert not env['db'].query(Enrollment).filter_by(class_id=target.id,student_id=None).first()
    assert not env['db'].query(__import__('app.models.user',fromlist=['User']).User).filter_by(email='new@example.test').first()


def test_enabled_policy_blocks_legacy_bulk_promotion(env):
    target=setup(env);db=env['db'];source_year=db.query(AcademicYear).filter_by(name='2026',institution_id=target.institution_id).one();target_year=db.query(AcademicYear).filter_by(name='2027',institution_id=target.institution_id).one()
    request=dict(target_year_id=str(target_year.id),mappings=[dict(source_class_id=str(env['cls'].id),target_class_id=str(target.id))])
    assert env['as_user'](env['admin']).post(f'/api/institution/academic-years/{source_year.id}/promotion/preview',json=request).status_code==409


def test_prerequisites_and_decisions_survive_signed_backup_roundtrip(env):
    from app.services import backups
    target,subject,first,second=entry_setup(env);policy(env,enforce_prerequisites=False)
    # Remove the destination fixture enrollment so a real decision can add it.
    db=env['db'];db.query(Enrollment).filter_by(class_id=target.id,student_id=env['student'].id).delete();db.commit();data=preview(env,target)
    c=env['as_user'](env['admin']);assert c.post('/api/institution/progression/approve',json={**body(env,target),'expected_digest':data['digest']}).status_code==201
    raw=backups.export_institution(db,target.institution_id,['academics']);manifest,payload=backups.open_archive(raw);institution,tables=backups.institution_payload(manifest,payload)
    assert len(tables['course_prerequisites'])==1;assert len(tables['progression_decisions'])==1
    fingerprint=backups.merge_fingerprint(db,target.institution_id,tables)
    backups.merge_institution(db,manifest,payload,fingerprint);db.commit();assert db.query(ProgressionDecision).count()==1
    row=db.query(ProgressionDecision).one();row.snapshot={**row.snapshot,'override_reason':'Changed historical decision'};db.commit()
    fingerprint=backups.merge_fingerprint(db,target.institution_id,tables)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):backups.merge_institution(db,manifest,payload,fingerprint)
    db.rollback()


def test_competency_observations_satisfy_prerequisites_without_numeric_threshold(env):
    _,subject,_,_=entry_setup(env,competency_labels=['Secure'])
    work=env['work'];work.assessment_mode='COMPETENCY';work.published=True;work.grades_released=True;work.rubric_labels=['Needs support','Developing','Secure']
    env['db'].add(Score(institution_id=subject.institution_id,student_id=env['student'].id,coursework_id=work.id,competency_label='Secure'));env['db'].commit()
    assert register(env,subject).status_code==200


def test_cancelled_registration_does_not_hide_unfinished_progression_attempt(env):
    target=setup(env,require_all_completed=True);env['subject'].registration_mode='INDIVIDUAL'
    env['db'].add(CourseRegistration(institution_id=target.institution_id,subject_id=env['subject'].id,student_id=env['student'].id,active=False));env['db'].commit()
    assert preview(env,target)['metrics']['incomplete']==1
    assert not preview(env,target)['eligible']


def test_active_destination_is_reported_before_approval(env):
    target=setup(env);env['db'].add(Enrollment(institution_id=target.institution_id,class_id=target.id,student_id=env['student'].id));env['db'].commit()
    data=preview(env,target);assert not data['eligible'];assert 'already enrolled' in str(data['structural'])


def test_prerequisite_precision_is_validated_before_database_write(env):
    target,_,first,second=entry_setup(env);c=env['as_user'](owner(env));root=f'/api/platform/institutions/{target.institution_id}/prerequisites';data=c.get(root).json()
    response=c.put(root+'/'+str(second.id),json=dict(requirements=[dict(required_id=str(first.id),minimum_percentage=33.33333333333333)],expected_updated_at=data['updated_at']))
    assert response.status_code==422


def test_individual_offering_reassignment_cannot_bypass_prerequisites(env):
    target,subject,first,second=entry_setup(env);db=env['db'];third=CatalogueUnit(institution_id=target.institution_id,code='C103',name='Specialist course');db.add(third);db.flush()
    db.add(Prerequisite(institution_id=target.institution_id,course_id=third.id,required_id=second.id));db.add(CourseRegistration(institution_id=target.institution_id,subject_id=subject.id,student_id=env['student'].id,active=True));db.commit()
    response=env['as_user'](env['admin']).put(f'/api/teaching/subjects/{subject.id}',json=dict(name='Reassigned',catalogue_id=str(third.id),teacher_id=str(env['teacher'].id),registration_mode='INDIVIDUAL'))
    assert response.status_code==409,response.text;db.refresh(subject);assert subject.catalogue_id==second.id


def test_same_year_level_advancement_requires_explicit_policy(env):
    target=setup(env,require_closed_source=False,allow_same_year_level=True);target.academic_year='2026';env['db'].query(AcademicYear).filter_by(institution_id=target.institution_id,name='2026').one().status='ACTIVE';env['db'].commit()
    assert preview(env,target)['eligible'];policy(env,allow_same_year_level=False);assert not preview(env,target)['eligible']


def test_gpa_progression_threshold_cannot_exceed_scale():
    from test_grading_rules import policy as numeric_policy
    with pytest.raises(ValueError):AcademicConfiguration(credits_enabled=True,grading_rules=numeric_policy(gpa_enabled=True),progression_rules=ProgressionRules(minimum_gpa=5))


def test_numeric_prerequisite_threshold_and_stale_final_grade(env):
    from test_grading_rules import setup as numeric_setup, approve
    numeric_setup(env);approve(env);source_unit=env['subject'].catalogue_id
    target=setup(env,enforce_prerequisites=True);db=env['db'];unit=CatalogueUnit(institution_id=target.institution_id,code='NEXT',name='Next course');db.add(unit);db.flush()
    subject=Subject(institution_id=target.institution_id,class_id=target.id,name='Next course',teacher_id=env['teacher'].id,catalogue_id=unit.id,registration_mode='INDIVIDUAL');db.add(subject);db.flush()
    link=Prerequisite(institution_id=target.institution_id,course_id=unit.id,required_id=source_unit,minimum_percentage='70');db.add_all([link,Enrollment(institution_id=target.institution_id,class_id=target.id,student_id=env['student'].id)]);db.commit()
    assert register(env,subject).status_code==409
    link.minimum_percentage='60';db.commit();assert register(env,subject).status_code==200
    registration=db.query(CourseRegistration).filter_by(subject_id=subject.id).one();registration.active=False;db.query(Score).filter_by(coursework_id=env['work'].id).one().score=0;db.commit()
    assert register(env,subject).status_code==409
