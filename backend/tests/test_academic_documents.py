"""Issued document integrity, release policy, periods and tenant boundaries."""
from datetime import date
from decimal import Decimal
import pytest
from test_teaching import env
from app.models.academic import Attendance, Coursework, Enrollment, Score, Subject
from app.models.academic_document import AcademicDocument
from app.models.curriculum import CourseCompletion, CourseRegistration, CatalogueUnit
from app.models.institution import InstitutionType
from app.models.pilot import AcademicYear, AcademicPeriod
from app.models.user import UserRole
from app.services.academic_configuration import template

ROOT='/api/academic-documents'


def test_builder_options_include_historical_roster_and_only_supervised_groups(env):
    env['db'].query(Enrollment).filter_by(student_id=env['student'].id).update({'active':False});env['db'].commit()
    for who in ['admin','supervisor']:
        c=env['as_user'](env[who]);response=c.get(ROOT+'/options',params={'class_id':str(env['cls'].id)})
        assert response.status_code==200,response.text
        assert response.json()['students'][0]['id']==str(env['student'].id)
        assert len(response.json()['groups'])==1
    c=env['as_user'](env['teacher']);assert c.get(ROOT+'/options').json()['groups']==[]
    assert c.get(ROOT+'/options',params={'class_id':str(env['cls'].id)}).status_code==404


def test_delegated_readonly_preview_and_platform_issue_follow_actor_permissions(env):
    from test_workspace_access import enter,platform
    ready(env)
    c,_=enter(env,env['admin'],env['supervisor'])
    assert c.get(ROOT+'/preview',params=params(env)).status_code==200
    assert c.post(ROOT,json=dict(**params(env),expected_digest='a'*64)).status_code==403
    env['client'].headers.pop('X-Workspace-Token',None)
    actor=platform(env);c,_=enter(env,actor,env['admin'])
    data=c.get(ROOT+'/preview',params=params(env)).json()
    result=c.post(ROOT,json=dict(**params(env),expected_digest=data['source_digest']))
    assert result.status_code==201,result.text
    assert result.json()['issued_by'].startswith(actor.first_name)


def ready(env,competency=False):
    work=env['work'];work.published=True;work.grades_released=True
    if competency: work.assessment_mode='COMPETENCY';work.rubric_labels=['Developing','Secure']
    mark=Score(institution_id=work.institution_id,student_id=env['student'].id,coursework_id=work.id,
        score=None if competency else Decimal('0'),competency_label='Secure' if competency else None,feedback='Keep practising')
    env['db'].add(mark);env['db'].commit();return mark


def params(env,kind='REPORT_CARD',**extra):
    return dict(student_id=str(env['student'].id),kind=kind,**(dict(class_id=str(env['cls'].id)) if kind=='REPORT_CARD' else {}),**extra)


def preview(env,**extra):
    c=env['as_user'](env['admin']);r=c.get(ROOT+'/preview',params=params(env,**extra));assert r.status_code==200,r.text;return r.json()


def issue(env,**extra):
    data=preview(env,**extra);c=env['as_user'](env['admin'])
    response=c.post(ROOT,json=dict(**params(env,**extra),expected_digest=data['source_digest'],remarks='Reviewed by the institution'))
    assert response.status_code==201,response.text;return response.json()


@pytest.mark.parametrize('kind',list(InstitutionType))
def test_each_institution_type_can_issue_report_and_transcript(env,kind):
    institution=env['institutions'][0];institution.type=kind;institution.academic_configuration=template(kind)
    ready(env,kind==InstitutionType.KINDERGARTEN)
    report=issue(env);transcript=issue(env,kind='TRANSCRIPT')
    outcome=report['snapshot']['sections'][0]['courses'][0]['outcomes'][0]
    if kind==InstitutionType.KINDERGARTEN:
        assert report['title']=='Learning progress report' and outcome['competency']=='Secure' and outcome['score'] is None
    else: assert outcome['score']=='0.00' and report['title']=='Report card'
    assert transcript['title']=='Academic transcript'
    c=env['as_user'](env['pupil']);assert c.get(ROOT).json()['total']==2
    assert c.get(ROOT+'/'+report['id']).json()['snapshot']==report['snapshot']


def test_no_withheld_missing_or_unpublished_results_are_accidentally_certified(env):
    assert not preview(env)['ready']
    env['work'].published=True;env['db'].commit()
    data=preview(env);assert 'withheld' in str(data['issues']) and not data['snapshot']['sections'][0]['courses'][0]['outcomes']
    c=env['as_user'](env['admin']);assert c.post(ROOT,json=dict(**params(env),expected_digest=data['source_digest'])).status_code==409
    env['work'].grades_released=True;env['db'].commit()
    assert 'no recorded outcome' in str(preview(env)['issues'])


def test_released_snapshots_survive_mark_policy_identity_and_enrollment_changes(env):
    mark=ready(env);document=issue(env)
    mark.score=19;env['pupil'].first_name='Changed';env['institutions'][0].name='Renamed';env['institutions'][0].learning_settings={'grade_bands':[{'minimum':0,'label':'New grade'}]}
    env['db'].query(Enrollment).filter_by(student_id=env['student'].id).update({'active':False});env['db'].commit()
    stored=env['as_user'](env['pupil']).get(ROOT+'/'+document['id']).json()
    assert stored['snapshot']==document['snapshot']
    assert preview(env)['snapshot']['learner']['name'].startswith('Changed')


def test_stale_preview_duplicate_issue_and_client_snapshot_injection_are_rejected(env):
    mark=ready(env);data=preview(env);mark.score=12;env['db'].commit()
    c=env['as_user'](env['admin']);assert c.post(ROOT,json=dict(**params(env),expected_digest=data['source_digest'])).status_code==409
    document=issue(env);data=preview(env)
    c=env['as_user'](env['admin']);body=dict(**params(env),expected_digest=data['source_digest'],remarks='Reviewed by the institution')
    assert c.post(ROOT,json=body).status_code==409
    assert c.post(ROOT,json={**body,'snapshot':document['snapshot']}).status_code==422


def test_teacher_authorization_and_student_and_tenant_boundaries(env):
    ready(env);document=issue(env)
    for who in ['teacher','unrelated','outsider']:
        c=env['as_user'](env[who]);assert c.get(ROOT+'/preview',params=params(env)).status_code==404
        assert c.get(ROOT+'/'+document['id']).status_code==404
        assert c.post(ROOT,json=dict(**params(env),expected_digest='a'*64)).status_code==403
    c=env['as_user'](env['supervisor']);assert c.get(ROOT+'/preview',params=params(env)).status_code==200
    assert c.get(ROOT+'/preview',params=params(env,kind='TRANSCRIPT')).status_code==403
    assert c.get(ROOT+'/'+document['id']).status_code==200
    c=env['as_user'](env['other_pupil']);assert c.get(ROOT+'/'+document['id']).status_code==404 and c.get(ROOT).json()['total']==0
    c=env['as_user'](env['pupil']);assert c.get(ROOT+'/preview',params=params(env)).status_code==403
    assert c.post(ROOT+'/'+document['id']+'/revoke',json={'reason':'Not authorized'}).status_code==403


def calendar(env):
    db=env['db'];year=AcademicYear(institution_id=env['cls'].institution_id,name='2026',start_date=date(2026,1,1),end_date=date(2026,12,31))
    db.add(year);db.flush();periods=[AcademicPeriod(institution_id=year.institution_id,year_id=year.id,name=name,start_date=start,end_date=end)
        for name,start,end in [('Term 1',date(2026,1,1),date(2026,4,30)),('Term 2',date(2026,5,1),date(2026,8,31))]]
    db.add_all(periods);db.commit();return year,periods


def test_period_report_uses_explicit_assessment_period_and_date_scoped_attendance(env):
    ready(env);year,periods=calendar(env);db=env['db']
    assert 'assign an academic period' in str(preview(env,period_id=str(periods[0].id))['issues'])
    env['work'].period_id=periods[0].id
    second=Coursework(institution_id=year.institution_id,subject_id=env['subject'].id,period_id=periods[1].id,title='Term 2 only',instructions='Later',max_score=10,published=True,grades_released=False)
    db.add(second)
    for day,status in [(date(2026,2,1),'LATE'),(date(2026,2,2),'EXCUSED'),(date(2026,6,1),'ABSENT')]:
        db.add(Attendance(institution_id=year.institution_id,class_id=env['cls'].id,student_id=env['student'].id,scope_key='class',day=day,status=status))
    db.commit();data=preview(env,period_id=str(periods[0].id));assert data['ready']
    section=data['snapshot']['sections'][0];assert section['attendance']['rate']=='100.00' and section['attendance']['counts']=={'EXCUSED':1,'LATE':1}
    assert len(section['courses'][0]['outcomes'])==1
    assert not preview(env)['ready'] # Whole-year report must not ignore withheld Term 2.
    issued=issue(env,period_id=str(periods[0].id));assert issued['period']=='Term 1'


def test_assessment_period_cannot_cross_institution_or_year(env):
    year,periods=calendar(env);c=env['as_user'](env['teacher'])
    path=f"/api/teaching/subjects/{env['subject'].id}/coursework"
    body=dict(title='Period test',instructions='Instructions',max_score=20,period_id=str(periods[0].id))
    assert c.post(path,json=body).status_code==201
    outsider=AcademicYear(institution_id=env['other_cls'].institution_id,name='2026',start_date=date(2026,1,1),end_date=date(2026,12,31))
    env['db'].add(outsider);env['db'].flush();foreign=AcademicPeriod(institution_id=outsider.institution_id,year_id=outsider.id,name='Private term',start_date=outsider.start_date,end_date=outsider.end_date)
    env['db'].add(foreign);env['db'].commit()
    assert c.post(path,json={**body,'period_id':str(foreign.id)}).status_code==422
    assert env['as_user'](env['admin']).get(ROOT+'/preview',params={**params(env),'period_id':str(foreign.id)}).status_code==422


def test_revocation_removes_learner_access_preserves_staff_history_and_audit(env):
    from app.models.audit import AuditEvent
    ready(env);document=issue(env);c=env['as_user'](env['admin'])
    assert c.post(ROOT+'/'+document['id']+'/revoke',json={'reason':'Correction needed'}).status_code==200
    assert c.post(ROOT+'/'+document['id']+'/revoke',json={'reason':'Correction needed'}).status_code==409
    assert c.get(ROOT+'/'+document['id']).json()['status']=='REVOKED'
    c=env['as_user'](env['pupil']);assert c.get(ROOT).json()['total']==0 and c.get(ROOT+'/'+document['id']).status_code==404
    assert {'academic_document.issued','academic_document.revoked'} <= {e.action for e in env['db'].query(AuditEvent).all()}


def test_closed_year_reports_can_be_issued_without_reopening_academic_records(env):
    ready(env);year,_=calendar(env);year.status='CLOSED';env['db'].commit()
    assert issue(env)['status']=='ISSUED'


def test_transcript_preserves_attempts_and_deduplicates_approved_credits(env):
    ready(env);db=env['db'];institution=env['institutions'][0];institution.type=InstitutionType.UNIVERSITY;institution.academic_configuration=template('UNIVERSITY')
    unit=CatalogueUnit(institution_id=institution.id,code='CS101',name='Foundations',credits=3);db.add(unit);db.flush()
    env['subject'].catalogue_id=unit.id
    repeated=Subject(institution_id=institution.id,class_id=env['cls'].id,name='Repeat Foundations',teacher_id=env['teacher'].id,catalogue_id=unit.id,registration_mode='INDIVIDUAL');db.add(repeated);db.flush()
    for subject in [env['subject'],repeated]:db.add(CourseCompletion(institution_id=institution.id,student_id=env['student'].id,subject_id=subject.id,outcome='PASSED',credits=3,released=True))
    db.commit();data=preview(env,kind='TRANSCRIPT');assert data['ready'] and data['snapshot']['earned_credits']=='3.00'
    assert len(data['snapshot']['sections'][0]['courses'])==2


def test_backup_contains_issued_snapshot_and_cannot_resurrect_revocation(env):
    from app.services import backups
    ready(env);document=issue(env);db=env['db']
    raw=backups.export_institution(db,env['cls'].institution_id,['learning'])
    manifest,payload=backups.open_archive(raw)
    assert document['id'].encode() in payload
    c=env['as_user'](env['admin']);c.post(ROOT+'/'+document['id']+'/revoke',json={'reason':'Corrected report pending'})
    _,tables=backups.institution_payload(manifest,payload)
    fingerprint=backups.merge_fingerprint(db,env['cls'].institution_id,tables)
    backups.merge_institution(db,manifest,payload,fingerprint);db.commit()
    assert db.query(AcademicDocument).one().status=='REVOKED'
