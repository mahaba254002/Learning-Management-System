from datetime import datetime, timezone
from decimal import Decimal
import pytest
from test_teaching import env
from app.models.user import UserRole
from app.models.institution import InstitutionType
from app.models.academic import Coursework, Subject, Score, Student, Enrollment
from app.models.curriculum import CourseCompletion
from app.services.academic_configuration import template


def owner(env):
    user=env['user']('platform-owner',UserRole.PLATFORM_ADMIN);user.institution_id=None;env['db'].commit();return user


@pytest.mark.parametrize('kind,structure,assessment', [('KINDERGARTEN','GROUPED','COMPETENCY'),('PRIMARY_SCHOOL','GROUPED','MIXED'),('HIGH_SCHOOL','GROUPED','NUMERIC'),('COLLEGE','PROGRAMME','MIXED'),('UNIVERSITY','PROGRAMME','MIXED'),('TRAINING_INSTITUTION','PROGRAMME','MIXED')])
def test_platform_templates_are_explicit_and_editable(env,kind,structure,assessment):
    c=env['as_user'](owner(env));rows=c.get('/api/platform/academic-templates').json();row=next(r for r in rows if r['type']==kind)
    assert row['configuration']['structure']==structure and row['configuration']['assessment_policy']==assessment
    assert row['labels']['grade_bands']==[]  # never invent an official grade policy


def test_platform_owns_confirmed_policy_and_rejects_stale_updates(env):
    c=env['as_user'](owner(env));path=f"/api/platform/institutions/{env['cls'].institution_id}/academic-configuration"
    initial=c.get(path).json();body=dict(configuration=initial['configuration'],labels=initial['labels'],expected_updated_at=initial['updated_at'])
    body['labels']['teacher_label']='Tutor'
    assert c.put(path,json=body).status_code==200
    assert c.put(path,json=body).status_code==409
    admin=env['as_user'](env['admin'])
    assert admin.put(path,json=body).status_code==403
    assert admin.put('/api/institution/learning-settings',json=body['labels']).status_code==403
    assert admin.get('/api/institution/academic-configuration').json()['labels']['teacher_label']=='Tutor'


def test_verified_onboarding_keeps_platform_academic_choices(env,monkeypatch):
    from app.api.routes import platform
    from app.core import rate_limit as limiter
    monkeypatch.setattr(limiter.redis_client,'incr',lambda key:1);monkeypatch.setattr(limiter.redis_client,'expire',lambda *args:True)
    captured={}
    import uuid
    def capture(**kwargs): captured.update(kwargs['payload']);return uuid.uuid4()
    monkeypatch.setattr(platform,'generate_verification_code',capture)
    monkeypatch.setattr(platform,'confirm_verification_code',lambda **kwargs:captured)
    c=env['as_user'](owner(env))
    payload=dict(name='Test College',code='new-college',type='COLLEGE',country='Kenya',academic_configuration={**template('COLLEGE'),'registration_mode':'COHORT'})
    request=c.post('/api/platform/institutions/request-create',json=payload);assert request.status_code==200
    confirmed=c.post('/api/platform/institutions/confirm-create',json=dict(verification_id=request.json()['verification_id'],code='123456'))
    assert confirmed.status_code==201
    read=c.get(f"/api/platform/institutions/{confirmed.json()['id']}/academic-configuration").json()
    assert read['managed'] and read['configuration']['structure']=='PROGRAMME' and read['configuration']['registration_mode']=='COHORT'


def university(env):
    institution=env['institutions'][0];institution.type=InstitutionType.UNIVERSITY;institution.academic_configuration=template('UNIVERSITY');env['db'].commit()
    c=env['as_user'](env['admin'])
    def create(kind,**body):
        response=c.post('/api/institution/academic-structure/'+kind,json=body);assert response.status_code==201,response.text;return response.json()['id']
    department=create('departments',code='SCI',name='Science')
    programme=create('programmes',code='CS',name='Computing',department_id=department,award='Institution-defined award')
    level=create('levels',code='CS-1',name='Year 1',programme_id=programme,position=1)
    unit=create('catalogue',code='CS101',name='Computing foundations',programme_id=programme,level_id=level,credits='3')
    response=c.post('/api/teaching/classes',json=dict(name='Computing intake',academic_year='2026',programme_id=programme,level_id=level));assert response.status_code==201,response.text
    group=response.json()['id']
    assert c.post(f'/api/teaching/classes/{group}/enrollments',json=dict(admission_number='A001')).status_code==200
    response=c.post(f'/api/teaching/classes/{group}/subjects',json=dict(name='Computing foundations',teacher_id=str(env['teacher'].id),catalogue_id=unit));assert response.status_code==201,response.text
    return group,response.json()['id'],unit


def test_university_registration_controls_all_learning_doors(env):
    group,subject,unit=university(env)
    c=env['as_user'](env['pupil'])
    assert str(subject) not in [r['id'] for r in c.get('/api/student/subjects').json()]
    assert c.get(f'/api/student/subjects/{subject}/materials').status_code==404
    c=env['as_user'](env['admin'])
    assert c.put(f'/api/institution/subjects/{subject}/registrations',json=dict(student_id=str(env['student'].id),active=True)).status_code==200
    c=env['as_user'](env['pupil'])
    assert subject in [r['id'] for r in c.get('/api/student/subjects').json()]
    assert c.get(f'/api/student/subjects/{subject}/materials').status_code==200
    teacher=env['as_user'](env['teacher'])
    assert len(teacher.get(f'/api/teaching/subjects/{subject}/students').json())==1
    assert teacher.put(f'/api/institution/subjects/{subject}/registrations',json=dict(student_id=str(env['student'].id),active=False)).status_code==403
    c=env['as_user'](env['admin'])
    assert c.put(f'/api/institution/subjects/{subject}/registrations',json=dict(student_id=str(env['other_student'].id),active=True)).status_code==404


def test_programme_and_level_links_cannot_cross_tenants(env):
    group,subject,unit=university(env)
    outsider=env['user']('other-admin',UserRole.INSTITUTION_ADMIN,tenant=1);env['db'].commit()
    c=env['as_user'](outsider)
    records=c.get('/api/institution/academic-structure').json()
    assert all(not rows for rows in records.values())
    assert c.post(f"/api/teaching/classes/{env['other_cls'].id}/subjects",json=dict(name='Stolen course',teacher_id=str(env['outsider'].id),catalogue_id=unit)).status_code==404


def test_approved_credits_are_private_until_release_and_repeats_do_not_double_count(env):
    group,subject,unit=university(env);c=env['as_user'](env['admin'])
    c.put(f'/api/institution/subjects/{subject}/registrations',json=dict(student_id=str(env['student'].id),active=True))
    body=dict(student_id=str(env['student'].id),outcome='PASSED',released=False)
    assert c.put(f'/api/institution/subjects/{subject}/completion',json=body).status_code==200
    c=env['as_user'](env['pupil']);assert c.get('/api/student/academic-record').json()['earned_credits']==0
    row=env['db'].query(CourseCompletion).one()
    c=env['as_user'](env['admin']);body.update(released=True,expected_updated_at=row.updated_at.isoformat())
    assert c.put(f'/api/institution/subjects/{subject}/completion',json=body).status_code==200
    assert c.put(f'/api/institution/subjects/{subject}/completion',json=body).status_code==409
    second=c.post(f'/api/teaching/classes/{group}/subjects',json=dict(name='Repeated offering',teacher_id=str(env['teacher'].id),catalogue_id=unit)).json()['id']
    c.put(f'/api/institution/subjects/{second}/registrations',json=dict(student_id=str(env['student'].id),active=True))
    assert c.put(f'/api/institution/subjects/{second}/completion',json=dict(student_id=str(env['student'].id),outcome='PASSED',released=True)).status_code==200
    c=env['as_user'](env['pupil']);record=c.get('/api/student/academic-record').json();assert Decimal(record['earned_credits'])==3 and len(record['courses'])==2


def test_kindergarten_competencies_are_not_fabricated_numeric_marks(env):
    institution=env['institutions'][0];institution.type=InstitutionType.KINDERGARTEN;institution.academic_configuration=template('KINDERGARTEN');env['db'].commit()
    c=env['as_user'](env['teacher'])
    response=c.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",json=dict(title='Language observation',instructions='Observe conversation',max_score=100,published=True))
    assert response.status_code==201,response.text
    work=response.json();assert work['assessment_mode']=='COMPETENCY' and work['rubric_labels']
    path=f"/api/teaching/coursework/{work['id']}/scores"
    assert c.put(path,json=dict(entries=[dict(student_id=str(env['student'].id),score=10)])).status_code==422
    assert c.put(path,json=dict(entries=[dict(student_id=str(env['student'].id),competency_label='Invented outcome')])).status_code==422
    assert c.put(path,json=dict(entries=[dict(student_id=str(env['student'].id),competency_label='Developing',feedback='Good progress')])).status_code==200
    pupil=env['as_user'](env['pupil']);hidden=next(w for w in pupil.get('/api/student/assignments').json() if w['id']==work['id']);assert hidden['competency_label'] is None and hidden['feedback']==''
    c=env['as_user'](env['teacher']);c.put(f"/api/teaching/coursework/{work['id']}/results-release",json=dict(released=True))
    pupil=env['as_user'](env['pupil']);shown=next(w for w in pupil.get('/api/student/assignments').json() if w['id']==work['id']);assert shown['competency_label']=='Developing' and shown['score'] is None and shown['graded']
    assert next(w for w in pupil.get('/api/student/coursework').json() if w['id']==work['id'])['competency_label']=='Developing'


@pytest.mark.parametrize('who',['admin','teacher','pupil'])
def test_operational_dashboards_use_scoped_persisted_records(env,who):
    c=env['as_user'](env[who]);response=c.get('/api/dashboard?days=7');assert response.status_code==200,response.text
    data=response.json();assert data['role']==env[who].role.value and data['institution']['name']=='School 0'
    assert len(data['trend'])==7 and all(point['value'] is None for point in data['trend'])
    assert not any('Private' in str(row) for row in data['queue'])
    assert data['metrics'] and data['generated_at']


def test_platform_dashboard_counts_and_links_real_customers(env):
    c=env['as_user'](owner(env));response=c.get('/api/dashboard');assert response.status_code==200,response.text
    data=response.json();assert data['role']=='PLATFORM_ADMIN' and data['institution'] is None
    assert len(data['trend'])==6 and all(point['value']==0 for point in data['trend'])
    assert data['queue_total']==2 and all(r['href'].startswith('/platform/institutions/') for r in data['queue'])


def test_individual_lecturer_cannot_bypass_registration_through_class_roster(env):
    group,subject,_=university(env);c=env['as_user'](env['admin'])
    response=c.post(f'/api/teaching/classes/{group}/students',json=dict(first_name='Unregistered',last_name='Peer',admission_number='C002',login_method='STUDENT_ID',login_id='UNREGISTERED-PEER'))
    assert response.status_code==201
    c.put(f'/api/institution/subjects/{subject}/registrations',json=dict(student_id=str(env['student'].id),active=True))
    teacher=env['as_user'](env['teacher']);roster=teacher.get(f'/api/teaching/classes/{group}/students').json()
    assert [r['id'] for r in roster]==[str(env['student'].id)]
    assert teacher.post('/api/workspace-access/start',json=dict(target_user_id=response.json()['student']['user_id'])).status_code==404


def test_used_catalogue_credit_and_programme_cannot_be_reinterpreted(env):
    group,subject,unit=university(env);c=env['as_user'](env['admin'])
    record=next(r for r in c.get('/api/institution/academic-structure').json()['catalogue'] if r['id']==unit)
    body={k:record[k] for k in ['code','name','programme_id','level_id','credits']};body.update(expected_updated_at=record['updated_at'],credits='9')
    assert c.put(f'/api/institution/academic-structure/catalogue/{unit}',json=body).status_code==409
    c=env['as_user'](owner(env));path=f"/api/platform/institutions/{env['cls'].institution_id}/academic-configuration";initial=c.get(path).json()
    body=dict(configuration={**initial['configuration'],'structure':'GROUPED'},labels=initial['labels'],expected_updated_at=initial['updated_at'])
    assert c.put(path,json=body).status_code==409


def test_numeric_grading_policy_is_snapshotted_on_first_mark(env):
    institution=env['institutions'][0];institution.learning_settings={'grade_bands':[{'minimum':0,'label':'Developing'},{'minimum':80,'label':'Excellent'}]};env['work'].published=True;env['db'].commit()
    c=env['as_user'](env['teacher']);path=f"/api/teaching/coursework/{env['work'].id}"
    assert c.put(path+'/scores',json=dict(entries=[dict(student_id=str(env['student'].id),score=18)])).status_code==200
    c.put(path+'/results-release',json=dict(released=True))
    institution.learning_settings={'grade_bands':[{'minimum':0,'label':'Changed policy'}]};env['db'].commit()
    pupil=env['as_user'](env['pupil']);assert pupil.get('/api/student/assignments').json()[0]['grade']=='Excellent'
    assert env['work'].grading_bands[1]['label']=='Excellent'


def test_competency_and_calendar_structure_survive_signed_backup_validation(env):
    from app.services import backups
    env['work'].assessment_mode='COMPETENCY';env['work'].rubric_labels=['Developing','Secure'];env['work'].grading_bands=[];env['db'].commit()
    raw=backups.export_institution(env['db'],env['cls'].institution_id,['learning'])
    manifest,payload=backups.open_archive(raw);institution,tables=backups.institution_payload(manifest,payload)
    work=next(w for w in tables['coursework'] if w['id']==env['work'].id)
    assert work['rubric_labels']==['Developing','Secure'] and work['grading_bands']==[]


def test_dashboard_marking_queue_counts_real_submissions_without_exposing_answers(env):
    from app.models.learning import Submission
    env['work'].published=True;env['db'].add(Submission(institution_id=env['cls'].institution_id,coursework_id=env['work'].id,student_id=env['student'].id,answer='PRIVATE LEARNER ANSWER',status='SUBMITTED',version=1,submitted_at=datetime.now(timezone.utc)));env['db'].commit()
    data=env['as_user'](env['teacher']).get('/api/dashboard').json()
    assert next(m for m in data['metrics'] if m['label']=='Awaiting marking')['value']==1
    assert 'PRIVATE LEARNER ANSWER' not in str(data)
    assert data['actions'][0]['href'].endswith(f"assessment={env['work'].id}")


def test_teaching_offering_rejects_a_period_from_another_academic_year(env):
    c=env['as_user'](env['admin']);year=c.post('/api/institution/academic-years',json=dict(name='2027',start_date='2027-01-01',end_date='2027-12-31')).json()['id']
    period=c.post(f'/api/institution/academic-years/{year}/periods',json=dict(name='Term 1',start_date='2027-01-01',end_date='2027-04-01')).json()['id']
    result=c.post(f"/api/teaching/classes/{env['cls'].id}/subjects",json=dict(name='Wrong year offering',teacher_id=str(env['teacher'].id),period_id=period))
    assert result.status_code==422
