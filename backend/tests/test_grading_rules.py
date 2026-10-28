from copy import deepcopy
from decimal import Decimal
import pytest
from pydantic import ValidationError
from test_teaching import env
from test_curriculum import owner
from test_academic_documents import calendar
from app.models.academic import Coursework,Score,Subject,Student,Enrollment
from app.models.curriculum import CatalogueUnit,CourseCompletion
from app.models.final_grade import FinalGrade
from app.models.institution import InstitutionType
from app.models.user import User, UserRole
from app.services.grading_rules import GradingRules,calculate,gpa


def policy(**changes):
    return GradingRules(enabled=True,name='Test institution v1',weights={'ASSIGNMENT':20,'COURSEWORK':30,'EXAM':50},
        bands=[{'minimum':70,'label':'A','points':4},{'minimum':50,'label':'C','points':2},{'minimum':0,'label':'F','points':0}],**changes).model_dump()


def configure(env,rules=None):
    c=env['as_user']((env['db'].query(User).filter_by(role=UserRole.PLATFORM_ADMIN).first() or owner(env)));path=f"/api/platform/institutions/{env['institutions'][0].id}/academic-configuration"
    data=c.get(path).json();data['configuration'].update(assessment_policy='MIXED',credits_enabled=True,grading_rules=rules or policy(gpa_enabled=True))
    response=c.put(path,json={'configuration':data['configuration'],'labels':data['labels'],'expected_updated_at':data['updated_at']})
    assert response.status_code==200,response.text;return path,response.json()


def setup(env,rules=None):
    configure(env,rules);db=env['db'];subject=env['subject'];unit=CatalogueUnit(institution_id=subject.institution_id,code='M101',name='Mathematics',credits=3)
    db.add(unit);db.flush();subject.catalogue_id=unit.id
    env['work'].published=True;env['work'].grades_released=True
    db.add(Score(institution_id=subject.institution_id,student_id=env['student'].id,coursework_id=env['work'].id,score=16))
    for kind,maximum,score in [('COURSEWORK',50,30),('EXAM',100,70)]:
        work=Coursework(institution_id=subject.institution_id,subject_id=subject.id,kind=kind,title=kind,instructions='Test',max_score=maximum,published=True,grades_released=True)
        db.add(work);db.flush();db.add(Score(institution_id=subject.institution_id,student_id=env['student'].id,coursework_id=work.id,score=score))
    db.commit()


def preview(env,period=None,who='admin'):
    c=env['as_user'](env[who]);r=c.get(f"/api/teaching/subjects/{env['subject'].id}/final-grades",params={'period_id':period} if period else {})
    assert r.status_code==200,r.text;return r.json()['students'][0]


def approve(env,period=None,released=True):
    row=preview(env,period);c=env['as_user'](env['admin']);r=c.put(f"/api/institution/subjects/{env['subject'].id}/final-grades",json=dict(student_id=str(env['student'].id),period_id=period,released=released,expected_digest=row['source_digest'],expected_updated_at=row['updated_at']))
    assert r.status_code==200,r.text;return r.json()


def assessments():
    return [dict(title=kind,kind=kind,maximum=maximum,score=score,released=True) for kind,maximum,score in [('ASSIGNMENT','20','16'),('COURSEWORK','50','30'),('EXAM','100','70')]]


def test_weighted_math_and_zero_marks():
    result=calculate(policy(),assessments())['result'];assert result['percentage']=='69.00' and result['grade']=='C' and result['passed']
    rows=assessments();rows[0]['score']='0';assert calculate(policy(),rows)['result']['percentage']=='53.00'


@pytest.mark.parametrize('field,value',[('score',None),('released',False)])
def test_incomplete_marks_never_become_zero_or_redistributed(field,value):
    rows=assessments();rows[0][field]=value;result=calculate(policy(),rows)
    assert not result['ready'] and result['result'] is None


def test_missing_category_and_zero_weight_exclusion():
    rows=assessments()[1:];assert not calculate(policy(),rows)['ready']
    p=policy();p['weights']={'ASSIGNMENT':0,'COURSEWORK':50,'EXAM':50};assert calculate(p,rows)['result']['percentage']=='65.00'


def test_category_equal_percentages_differ_from_pooled_points():
    p=policy();p['weights']={'ASSIGNMENT':100,'COURSEWORK':0,'EXAM':0}
    rows=[dict(title='Small',kind='ASSIGNMENT',maximum='10',score='10',released=True),dict(title='Large',kind='ASSIGNMENT',maximum='90',score='0',released=True)]
    assert calculate(p,rows)['result']['percentage']=='10.00'
    p['within_category']='MEAN_PERCENT';assert calculate(p,rows)['result']['percentage']=='50.00'
    p['aggregation']='POINTS';assert calculate(p,rows)['result']['percentage']=='10.00'


@pytest.mark.parametrize('basis,grade,passed',[('RAW','F',False),('ROUNDED','C',True)])
def test_grade_and_pass_rounding_boundaries_are_explicit(basis,grade,passed):
    p=policy();p.update(aggregation='POINTS',grade_basis=basis)
    r=calculate(p,[dict(title='Boundary',kind='EXAM',maximum='10000',score='4999.5',released=True)])['result']
    assert r['percentage']=='50.00' and r['grade']==grade and r['passed']==passed


@pytest.mark.parametrize('change',[
    {'weights':{'ASSIGNMENT':20,'COURSEWORK':30,'EXAM':40}},
    {'weights':{'ASSIGNMENT':-1,'COURSEWORK':30,'EXAM':71}},
    {'weights':{'ASSIGNMENT':100}},
    {'bands':[{'minimum':10,'label':'A'}]},
    {'bands':[{'minimum':0,'label':'F'},{'minimum':0,'label':'A'}]},
    {'gpa_enabled':True,'gpa_scale':1},
    {'gpa_enabled':True,'bands':[{'minimum':0,'label':'F','points':None}]},
    {'pass_percentage':float('nan')},
    {'gpa_enabled':True,'bands':[{'minimum':0,'label':'F','points':4},{'minimum':50,'label':'A','points':0}]},
])
def test_invalid_or_ambiguous_policy_rejected(change):
    with pytest.raises(ValidationError):GradingRules.model_validate({**policy(),**change})


@pytest.mark.parametrize('repeat,expected,credits',[('ALL','2.33','9'),('LATEST','2.00','6'),('BEST','2.50','6')])
def test_credit_weighted_gpa_repeats_failures_and_exemptions(repeat,expected,credits):
    p=policy(gpa_enabled=True);p['repeats']=repeat
    rows=[dict(id=str(i),course_key=key,order=(i,),result=dict(policy=p,points=str(points),credits=str(c))) for i,key,points,c in [(1,'a',3,3),(2,'a',2,3),(3,'b',2,3)]]
    # Use a zero-point failed latest attempt for b, plus an exempt high-point course.
    rows[2]['result']['points']='2'
    entries=gpa(rows);assert entries[0]['gpa']==expected and entries[0]['attempted_credits']==credits
    exempt=dict(id='4',course_key='x',order=(4,),exempt=True,result=dict(policy=p,points='4',credits='100'))
    assert gpa(rows+[exempt])==entries


def test_gpa_includes_failed_attempt_and_separates_schemes():
    p=policy(gpa_enabled=True);a=dict(id='a',course_key='a',order=(1,),result=dict(policy=p,points='4',credits='3'))
    b=dict(id='b',course_key='b',order=(2,),result=dict(policy=p,points='0',credits='3'))
    assert gpa([a,b])[0]['gpa']=='2.00'
    c=deepcopy(a);c.update(id='c',course_key='c');c['result']['policy']['gpa_scale']=5
    assert len(gpa([a,b,c]))==2


@pytest.mark.parametrize('kind',list(InstitutionType))
def test_platform_can_configure_explicit_numeric_rules_for_each_type(env,kind):
    env['institutions'][0].type=kind;env['db'].commit();path,data=configure(env)
    assert data['configuration']['grading_rules']['enabled']
    assert env['as_user'](env['admin']).put(path,json=dict(configuration=data['configuration'],labels=data['labels'],expected_updated_at=data['updated_at'])).status_code==403


def test_competency_only_and_credit_free_gpa_are_rejected(env):
    path,data=configure(env);c=env['as_user']((env['db'].query(User).filter_by(role=UserRole.PLATFORM_ADMIN).first() or owner(env)));body=dict(configuration=data['configuration'],labels=data['labels'],expected_updated_at=data['updated_at'])
    body['configuration']['assessment_policy']='COMPETENCY';assert c.put(path,json=body).status_code==422
    body['configuration']['assessment_policy']='MIXED';body['configuration']['credits_enabled']=False;assert c.put(path,json=body).status_code==422


def test_final_approval_connects_credits_gpa_and_report_transcript(env):
    setup(env);p=preview(env);assert p['result']['percentage']=='69.00' and p['ready'] and not p['approved']
    document_params=dict(student_id=str(env['student'].id),kind='REPORT_CARD',class_id=str(env['cls'].id))
    c=env['as_user'](env['admin']);assert not c.get('/api/academic-documents/preview',params=document_params).json()['ready']
    approve(env)
    c=env['as_user'](env['pupil']);data=c.get('/api/student/academic-record').json()
    assert data['earned_credits']==3 and data['gpa'][0]['gpa']=='2.00' and data['final_grades'][0]['result']['grade']=='C'
    c=env['as_user'](env['admin']);report=c.get('/api/academic-documents/preview',params=document_params).json()
    assert report['ready'] and report['snapshot']['sections'][0]['courses'][0]['final_grade']['grade']=='C'
    assert report['snapshot']['gpa'][0]['gpa']=='2.00'
    assert c.put(f"/api/institution/subjects/{env['subject'].id}/completion",json=dict(student_id=str(env['student'].id),outcome='FAILED')).status_code==409


def test_changed_marks_hide_stale_results_and_credits_until_reapproval(env):
    setup(env);approve(env);env['db'].query(Score).filter_by(coursework_id=env['work'].id).one().score=0;env['db'].commit()
    assert preview(env)['stale']
    c=env['as_user'](env['pupil']);data=c.get('/api/student/academic-record').json();assert not data['gpa'] and not data['final_grades'] and data['earned_credits']==0
    approve(env);assert not preview(env)['stale']
    approve(env,released=False)
    assert not env['as_user'](env['pupil']).get('/api/student/final-grades').json()['final_grades']
    assert not env['db'].query(CourseCompletion).one().released


def test_policy_changes_do_not_reinterpret_pinned_offerings_or_issued_documents(env):
    setup(env);approve(env);db=env['db'];subject=env['subject'];db.refresh(subject)
    assert subject.grading_policy['name']=='Test institution v1'
    c=env['as_user'](env['admin']);params=dict(student_id=str(env['student'].id),kind='TRANSCRIPT');p=c.get('/api/academic-documents/preview',params=params).json()
    issued=c.post('/api/academic-documents',json={**params,'expected_digest':p['source_digest']});assert issued.status_code==201,issued.text
    next_policy=policy(gpa_enabled=True);next_policy.update(name='Next year v2',pass_percentage=90)
    configure(env,next_policy)
    assert preview(env)['result']['policy']['name']=='Test institution v1'
    assert env['as_user'](env['pupil']).get('/api/academic-documents/'+issued.json()['id']).json()['snapshot']==issued.json()['snapshot']


def test_stale_approval_and_wrong_role_tenant_are_blocked(env):
    setup(env);p=preview(env);path=f"/api/institution/subjects/{env['subject'].id}/final-grades";body=dict(student_id=str(env['student'].id),expected_digest=p['source_digest'])
    for who in ['teacher','pupil','outsider']:
        assert env['as_user'](env[who]).put(path,json=body).status_code==403
    assert env['as_user'](env['unrelated']).get(f"/api/teaching/subjects/{env['subject'].id}/final-grades").status_code==404
    env['db'].query(Score).filter_by(coursework_id=env['work'].id).one().score=2;env['db'].commit()
    assert env['as_user'](env['admin']).put(path,json=body).status_code==409
    approve(env);p=preview(env)
    assert env['as_user'](env['admin']).put(path,json=dict(student_id=str(env['student'].id),expected_digest=p['source_digest'],expected_updated_at=None)).status_code==409


def test_term_result_does_not_double_count_course_credits_or_gpa(env):
    setup(env);_,periods=calendar(env)
    env['db'].query(Coursework).filter_by(subject_id=env['subject'].id).update({'period_id':periods[0].id});env['db'].commit()
    approve(env,period=str(periods[0].id));data=env['as_user'](env['pupil']).get('/api/student/final-grades').json()
    assert len(data['final_grades'])==1 and data['gpa']==[] and env['db'].query(CourseCompletion).count()==0


def test_gpa_cannot_approve_missing_credits_and_closed_years(env):
    setup(env);db=env['db'];db.query(CatalogueUnit).one().credits=0;db.commit()
    assert not preview(env)['ready']
    db.query(CatalogueUnit).one().credits=3;year,_=calendar(env);year.status='CLOSED';db.commit()
    p=preview(env);response=env['as_user'](env['admin']).put(f"/api/institution/subjects/{env['subject'].id}/final-grades",json=dict(student_id=str(env['student'].id),expected_digest=p['source_digest']))
    assert response.status_code==409


@pytest.mark.parametrize('rounding,expected',[('HALF_UP','51'),('HALF_EVEN','50'),('DOWN','50')])
def test_rounding_modes_are_not_platform_float_rounding(rounding,expected):
    p=policy();p.update(aggregation='POINTS',percentage_places=0,rounding=rounding)
    assert calculate(p,[dict(title='Tie',kind='EXAM',maximum='1000',score='505',released=True)])['result']['percentage']==expected


def test_withdrawn_source_assessments_cannot_leave_a_certifiable_stale_grade(env):
    setup(env);approve(env);env['db'].query(Coursework).filter_by(subject_id=env['subject'].id).update({'published':False});env['db'].commit()
    c=env['as_user'](env['admin']);r=c.get('/api/academic-documents/preview',params=dict(student_id=str(env['student'].id),kind='TRANSCRIPT')).json()
    assert not r['ready'] and 'current final grade' in str(r['issues'])
    assert not env['as_user'](env['pupil']).get('/api/student/final-grades').json()['gpa']


def test_signed_backup_round_trip_includes_final_grade_and_policy(env):
    from app.services import backups
    setup(env);approve(env);db=env['db'];raw=backups.export_institution(db,env['cls'].institution_id,['learning'])
    manifest,payload=backups.open_archive(raw);_,tables=backups.institution_payload(manifest,payload)
    assert tables['final_grades'][0]['result']['grade']=='C'
    assert tables['teaching_subjects'][0]['grading_policy']['name']=='Test institution v1'


def test_exempt_completion_is_not_an_unmarked_failure_or_gpa_attempt(env):
    setup(env);db=env['db'];db.add(CourseCompletion(institution_id=env['cls'].institution_id,subject_id=env['subject'].id,student_id=env['student'].id,outcome='EXEMPT',credits=3,released=True));db.commit()
    c=env['as_user'](env['admin']);doc=c.get('/api/academic-documents/preview',params=dict(student_id=str(env['student'].id),kind='TRANSCRIPT')).json()
    assert doc['ready'] and not doc['snapshot']['gpa'] and doc['snapshot']['earned_credits']=='3.00'


def test_large_roster_calculation_batches_shared_academic_queries(env):
    from sqlalchemy import event
    setup(env);db=env['db']
    for i in range(12):
        user=env['user']('additional-'+str(i),UserRole.STUDENT)
        student=Student(institution_id=env['cls'].institution_id,user_id=user.id,admission_number='EX-'+str(i));db.add(student);db.flush()
        db.add(Enrollment(institution_id=env['cls'].institution_id,student_id=student.id,class_id=env['cls'].id))
    db.commit();queries=[]
    def track(*args):queries.append(args[2])
    event.listen(db.get_bind(),'before_cursor_execute',track)
    try:
        r=env['as_user'](env['admin']).get(f"/api/teaching/subjects/{env['subject'].id}/final-grades")
        assert r.status_code==200 and len(r.json()['students'])==13
        assert len(queries)<30
    finally:event.remove(db.get_bind(),'before_cursor_execute',track)


def test_latest_attempt_uses_academic_offering_order_not_approval_order(env):
    from datetime import datetime,timezone,timedelta
    from app.services.final_grades import attempt_order
    setup(env);approve(env);db=env['db'];first=db.query(FinalGrade).one()
    subject=env['subject'];subject.created_at=datetime(2026,1,1,tzinfo=timezone.utc)
    later=Subject(institution_id=subject.institution_id,class_id=subject.class_id,name='Retake',teacher_id=subject.teacher_id,catalogue_id=subject.catalogue_id,
        created_at=datetime(2026,6,1,tzinfo=timezone.utc));db.add(later);db.flush()
    second=FinalGrade(institution_id=subject.institution_id,subject_id=later.id,student_id=env['student'].id,scope='ALL',source_digest='a'*64,result=first.result,
        created_at=first.created_at-timedelta(days=1));db.add(second);db.commit()
    assert attempt_order(db,subject,first)<attempt_order(db,later,second)


def test_readonly_delegation_cannot_release_final_grades(env):
    from test_workspace_access import enter
    setup(env);row=preview(env)
    c,_=enter(env,env['admin'],env['teacher'])
    assert c.get(f"/api/teaching/subjects/{env['subject'].id}/final-grades").status_code==200
    assert c.put(f"/api/institution/subjects/{env['subject'].id}/final-grades",json=dict(student_id=str(env['student'].id),expected_digest=row['source_digest'])).status_code==403


def test_platform_explicit_policy_revision_withholds_results_for_reapproval(env):
    setup(env);approve(env);new=policy(gpa_enabled=True);new.update(name='Revised v2',pass_percentage=90);path,_=configure(env,new)
    actor=env['db'].query(User).filter_by(role=UserRole.PLATFORM_ADMIN).one();c=env['as_user'](actor)
    options=c.get(path.replace('/academic-configuration','/grading-offerings')).json();item=options['items'][0]
    endpoint=path.replace('/academic-configuration','/grading-offerings/')+item['id']
    body=dict(confirmation=item['name'],expected_subject_updated_at=item['updated_at'],expected_institution_updated_at=options['institution_updated_at'])
    assert c.put(endpoint,json={**body,'confirmation':'wrong'}).status_code==422
    assert c.put(endpoint,json=body).status_code==200
    assert not env['as_user'](env['pupil']).get('/api/student/final-grades').json()['final_grades']
    assert preview(env)['result']['policy']['name']=='Revised v2'
    approve(env);assert env['db'].query(CourseCompletion).one().outcome=='FAILED'
    c=env['as_user'](env['pupil']);data=c.get('/api/student/academic-record').json()
    assert data['earned_credits']==0 and data['gpa'][0]['attempted_credits']=='3.00'
    assert env['as_user'](env['admin']).put(endpoint,json=body).status_code==403


def test_platform_policy_revision_respects_tenant_and_closed_year(env):
    setup(env);approve(env);year,_=calendar(env);year.status='CLOSED';env['db'].commit()
    actor=env['db'].query(User).filter_by(role=UserRole.PLATFORM_ADMIN).one();c=env['as_user'](actor)
    root=f"/api/platform/institutions/{env['cls'].institution_id}/grading-offerings";options=c.get(root).json();item=options['items'][0]
    body=dict(confirmation=item['name'],expected_subject_updated_at=item['updated_at'],expected_institution_updated_at=options['institution_updated_at'])
    assert c.put(root+'/'+item['id'],json=body).status_code==409
    assert c.put(root+'/'+str(env['other_subject'].id),json=body).status_code==404
