"""Learner portal: who's online, recently opened courses, course search and read-only messages to students."""
from datetime import datetime, timedelta, timezone

import pytest

from test_teaching import env  # noqa: F401
from app.core import rate_limit as limiter
from app.models.academic import Enrollment, Student
from app.models.elearning import Notification
from app.models.learner import CourseVisit, StudentMessageRecipient
from app.models.user import User, UserRole


@pytest.fixture(autouse=True)
def like_production(env, monkeypatch):
    env['db'].autoflush = False
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


def classmate(env, name='classmate'):
    db = env['db']
    u = User(institution_id=env['cls'].institution_id, username=name, first_name=name.title(), last_name='Test', email=f'{name}@example.test',
             role=UserRole.STUDENT, password_hash='unused', must_change_password=False)
    db.add(u); db.flush()
    s = Student(institution_id=u.institution_id, user_id=u.id, admission_number=f'A-{name}')
    db.add(s); db.flush()
    db.add(Enrollment(institution_id=u.institution_id, class_id=env['cls'].id, student_id=s.id))
    db.commit()
    return u


def test_requests_mark_people_as_seen_at_most_once_a_minute(env):
    c = env['as_user'](env['pupil'])
    assert c.get('/api/student/courses').status_code == 200
    env['db'].refresh(env['pupil'])
    first = env['pupil'].last_seen_at
    assert first is not None
    c.get('/api/student/courses')
    env['db'].refresh(env['pupil'])
    assert env['pupil'].last_seen_at == first


def test_online_shows_only_recent_classmates_and_teachers(env):
    db, now = env['db'], datetime.now(timezone.utc)
    mate, idle = classmate(env), classmate(env, 'idle')
    mate.last_seen_at = env['teacher'].last_seen_at = now
    idle.last_seen_at = now - timedelta(minutes=30)
    env['unrelated'].last_seen_at = env['other_pupil'].last_seen_at = now  # not my teacher; another school
    db.commit()
    data = env['as_user'](env['pupil']).get('/api/student/online').json()
    assert [(p['name'], p['teacher']) for p in data['people']] == [('teacher Test', True), ('Classmate Test', False)]


def test_opening_a_course_records_it_as_recent(env):
    c = env['as_user'](env['pupil'])
    assert c.get('/api/student/courses').json()[0]['last_visited_at'] is None
    assert c.get(f"/api/student/courses/{env['subject'].id}").status_code == 200
    assert c.get(f"/api/student/courses/{env['subject'].id}").status_code == 200
    assert env['db'].query(CourseVisit).count() == 1
    assert c.get('/api/student/courses').json()[0]['last_visited_at'] is not None


def test_course_search_lists_own_institution_only_and_marks_mine(env):
    c = env['as_user'](env['pupil'])
    data = c.get('/api/student/course-search?q=mat').json()
    assert data['total'] == 1 and data['results'][0]['name'] == 'Math' and data['results'][0]['mine'] is True
    assert c.get('/api/student/course-search?q=science').json()['total'] == 0  # other school's course
    assert env['as_user'](env['teacher']).get('/api/student/course-search').status_code == 403


def test_teacher_messages_class_student_reads_and_cannot_reply(env):
    mate = classmate(env)
    t = env['as_user'](env['teacher'])
    classes = t.get('/api/teaching/student-messages/audiences').json()
    assert [c['name'] for c in classes] == ['Form 1'] and len(classes[0]['students']) == 2
    sent = t.post('/api/teaching/student-messages', json=dict(class_id=str(env['cls'].id), title='Trip forms', body='Bring them on Monday'))
    assert sent.status_code == 201 and sent.json()['recipients'] == 2
    one = t.post('/api/teaching/student-messages', json=dict(class_id=str(env['cls'].id), student_user_id=str(mate.id), title='See me', body='After class'))
    assert one.json()['recipients'] == 1
    # A student outside the class can't be targeted.
    assert t.post('/api/teaching/student-messages', json=dict(class_id=str(env['cls'].id), student_user_id=str(env['other_pupil'].id),
                                                              title='x' * 3, body='y')).status_code == 422

    p = env['as_user'](env['pupil'])
    inbox = p.get('/api/student/messages').json()
    assert inbox['unread'] == 1 and inbox['messages'][0]['title'] == 'Trip forms' and inbox['messages'][0]['sender_name'] == 'teacher Test'
    assert env['db'].query(Notification).filter_by(user_id=env['pupil'].id).count() == 1
    assert p.post(f"/api/student/messages/{inbox['messages'][0]['id']}/read").status_code == 204
    assert p.get('/api/student/messages').json()['unread'] == 0
    assert p.post('/api/teaching/student-messages', json=dict(class_id=str(env['cls'].id), title='Reply', body='no')).status_code == 403
    # The other student's private message is not readable by this pupil.
    assert p.post(f"/api/student/messages/{one.json()['id']}/read").status_code == 404

    t_view = env['as_user'](env['teacher']).get('/api/teaching/student-messages').json()
    assert {m['title']: m['read'] for m in t_view} == {'Trip forms': 1, 'See me': 0}
    assert t_view[0]['student_name'] == 'Classmate Test'


def test_teachers_only_message_classes_they_teach_and_admin_sees_all(env):
    body = dict(class_id=str(env['cls'].id), title='Notice', body='Hello')
    assert env['as_user'](env['unrelated']).post('/api/teaching/student-messages', json=body).status_code == 404
    assert env['as_user'](env['outsider']).post('/api/teaching/student-messages', json=body).status_code == 404
    assert env['as_user'](env['teacher']).post('/api/teaching/student-messages', json=body).status_code == 201
    assert env['as_user'](env['unrelated']).get('/api/teaching/student-messages').json() == []
    admin = env['as_user'](env['admin'])
    assert [m['title'] for m in admin.get('/api/teaching/student-messages').json()] == ['Notice']
    assert admin.post('/api/teaching/student-messages', json=dict(body, title='From the office')).status_code == 201
    assert env['db'].query(StudentMessageRecipient).count() == 2
