from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from test_teaching import env  # noqa: F401; sets isolated environment before app imports
from app.models.academic import Attendance, Enrollment, Score, Student
from app.models.learning import CourseMaterial, Submission
from app.models.user import UserRole


def ready(env):
    env['work'].published = True
    env['db'].commit()
    return env['as_user'](env['pupil']), f"/api/student/assignments/{env['work'].id}/submission"


def test_subjects_profile_and_attendance_are_personal(env):
    db = env['db']
    peer = env['user']('peer', UserRole.STUDENT)
    student = Student(institution_id=peer.institution_id, user_id=peer.id, admission_number='A002')
    db.add(student); db.flush()
    db.add(Enrollment(institution_id=peer.institution_id, student_id=student.id, class_id=env['cls'].id))
    for who, status in [(env['student'], 'LATE'), (student, 'ABSENT')]:
        db.add(Attendance(institution_id=who.institution_id, class_id=env['cls'].id, subject_id=env['subject'].id,
                         scope_key=str(env['subject'].id), student_id=who.id, day=date.today(), status=status))
    db.commit()
    c, url = ready(env)
    assert [s['id'] for s in c.get('/api/student/subjects').json()] == [str(env['subject'].id)]
    profile = c.get('/api/student/profile').json()
    assert profile['admission_number'] == 'A001' and 'password_hash' not in profile
    assert c.put('/api/student/profile', json={'first_name': 'Changed'}).status_code == 405
    assert [a['status'] for a in c.get('/api/student/attendance').json()] == ['LATE']
    assert c.get(f"/api/student/attendance?subject_id={env['other_subject'].id}").status_code == 404
    assert c.put(url, json={'answer': 'Private', 'submit': True}).status_code == 200
    assert env['as_user'](peer).get('/api/student/assignments').json()[0]['submission'] is None
    assert env['as_user'](env['teacher']).get('/api/student/profile').status_code == 403


def test_material_publication_and_teacher_scope(env):
    url = f"/api/teaching/subjects/{env['subject'].id}/materials"
    c = env['as_user'](env['teacher'])
    body = {'title': 'Notes', 'body': 'Lesson one', 'published': False}
    result = c.post(url, json=body)
    assert result.status_code == 201
    material_id = result.json()['id']
    student_url = f"/api/student/subjects/{env['subject'].id}/materials"
    assert env['as_user'](env['pupil']).get(student_url).json() == []
    assert c.post(url, json=body).status_code == 403
    c = env['as_user'](env['unrelated'])
    assert c.put(f'/api/teaching/materials/{material_id}', json=body).status_code == 404
    c = env['as_user'](env['teacher'])
    assert c.put(f'/api/teaching/materials/{material_id}', json={**body, 'published': True}).status_code == 200
    assert env['as_user'](env['pupil']).get(student_url).json()[0]['body'] == 'Lesson one'
    assert env['as_user'](env['other_pupil']).get(student_url).status_code == 404


def test_draft_privacy_versions_and_final_receipt(env):
    c, url = ready(env)
    result = c.put(url, json={'answer': 'Working draft'})
    assert result.status_code == 200 and result.json()['version'] == 1
    assert c.get('/api/student/assignments').json()[0]['submission']['answer'] == 'Working draft'
    assert c.put(url, json={'answer': 'Stale'}).status_code == 409
    review = f"/api/teaching/coursework/{env['work'].id}/submissions"
    assert env['as_user'](env['teacher']).get(review).json() == []
    c = env['as_user'](env['pupil'])
    final = c.put(url, json={'answer': 'Final answer', 'submit': True, 'expected_version': 1}).json()
    assert final['status'] == 'SUBMITTED' and final['submitted_at'] and final['version'] == 2
    assert c.put(url, json={'answer': 'Replace', 'expected_version': 2}).status_code == 409
    assert c.get('/api/student/assignments').json()[0]['submission']['submitted_at'] == final['submitted_at']
    assert env['as_user'](env['teacher']).get(review).json()[0]['answer'] == 'Final answer'
    assert env['as_user'](env['unrelated']).get(review).status_code == 404


@pytest.mark.parametrize('body', [{'submit': True}, {'submit': True, 'answer': '   '},
    {'link_url': 'javascript:alert(1)'}, {'link_url': 'data:text/plain,secret'},
    {'link_url': 'https://user:password@example.com/file'}, {'student_id': 'fake'}, {'institution_id': 'fake'}])
def test_invalid_submission_rejected(env, body):
    c, url = ready(env)
    assert c.put(url, json=body).status_code == 422
    assert env['db'].query(Submission).count() == 0


def test_late_policy_and_link_only_submission(env):
    env['work'].due_at = datetime.now(timezone.utc) - timedelta(days=1)
    env['work'].allow_late_submissions = False
    c, url = ready(env)
    assert c.put(url, json={'answer': 'Late draft'}).status_code == 200
    body = {'link_url': 'https://example.com/answer.pdf', 'submit': True, 'expected_version': 1}
    assert c.put(url, json=body).status_code == 409
    env['work'].allow_late_submissions = True; env['db'].commit()
    result = c.put(url, json=body)
    assert result.status_code == 200 and result.json()['is_late'] is True


@pytest.mark.parametrize('condition,code', [('unpublished', 404), ('withdrawn', 404), ('graded', 409), ('exam', 400)])
def test_unavailable_work_cannot_be_submitted(env, condition, code):
    c, url = ready(env)
    if condition == 'unpublished': env['work'].published = False
    if condition == 'withdrawn': env['db'].query(Enrollment).filter_by(student_id=env['student'].id).one().active = False
    if condition == 'exam': env['work'].kind = 'EXAM'
    if condition == 'graded': env['db'].add(Score(institution_id=env['student'].institution_id, coursework_id=env['work'].id, student_id=env['student'].id, score=0))
    env['db'].commit()
    assert c.put(url, json={'answer': 'Answer', 'submit': True}).status_code == code
    assert env['db'].query(Submission).count() == 0


@pytest.mark.parametrize('model', ['material', 'submission'])
def test_database_rejects_cross_tenant_relationships(env, model):
    row = (CourseMaterial(institution_id=env['student'].institution_id, subject_id=env['other_subject'].id, title='Invalid')
           if model == 'material' else Submission(institution_id=env['student'].institution_id, coursework_id=env['other_work'].id, student_id=env['student'].id))
    env['db'].add(row)
    with pytest.raises(IntegrityError): env['db'].commit()
    env['db'].rollback()
