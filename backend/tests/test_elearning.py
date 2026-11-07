"""Phase 9: file uploads, online quizzes with server-enforced timers, course pages, notifications and registration windows."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from test_teaching import env  # noqa: F401
from app.core import rate_limit as limiter
from app.core.config import settings
from app.models.academic import Coursework, Score, Subject
from app.models.curriculum import CourseRegistration
from app.models.elearning import QuizAttempt, StoredFile
from app.models.institution import Institution
from app.services import storage

PDF = b'%PDF-1.4\n% test file\n'
QUESTIONS = [
    dict(kind='SINGLE', prompt='2 + 2 = ?', options=[dict(id='a', text='3'), dict(id='b', text='4')], correct=['b'], points=2),
    dict(kind='MULTIPLE', prompt='Pick the even numbers', options=[dict(id='a', text='2'), dict(id='b', text='3'), dict(id='c', text='6')],
         correct=['a', 'c'], points=3),
    dict(kind='TRUE_FALSE', prompt='Nairobi is in Kenya', correct=['true'], points=1),
]


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', 'local')
    monkeypatch.setattr(settings, 'LOCAL_STORAGE_DIR', str(tmp_path))


@pytest.fixture(autouse=True)
def like_production(env):
    # Production sessions do not autoflush, so pending rows are invisible to queries until flushed.
    env['db'].autoflush = False


def soon(**delta):
    return (datetime.now(timezone.utc) + timedelta(**delta)).isoformat()


def teacher(env):
    return env['as_user'](env['teacher'])


def pupil(env):
    return env['as_user'](env['pupil'])


def make_quiz(env, *, settings_body=None, questions=QUESTIONS, publish=True, **extra):
    c = teacher(env)
    body = dict(title='Quick quiz', instructions='Answer all questions', kind='COURSEWORK', max_score=1, delivery='QUIZ',
                **{'due_at': soon(hours=2), **extra})
    created = c.post(f"/api/teaching/subjects/{env['subject'].id}/coursework", json=body)
    assert created.status_code == 201, created.text
    work = created.json()
    assert c.put(f"/api/teaching/coursework/{work['id']}", json=dict(body, published=True)).status_code == 409  # no questions yet
    if settings_body:
        assert c.put(f"/api/teaching/quizzes/{work['id']}/settings", json=settings_body).status_code == 200
    saved = c.put(f"/api/teaching/quizzes/{work['id']}/questions", json=dict(questions=questions))
    assert saved.status_code == 200, saved.text
    if publish:
        published = c.put(f"/api/teaching/coursework/{work['id']}", json=dict(body, published=True, max_score=saved.json()['max_score']))
        assert published.status_code == 200, published.text
    return uuid.UUID(work['id'])


def test_r2_signing_matches_aws_examples():
    now = datetime(2013, 5, 24, tzinfo=timezone.utc)
    key, secret = 'AKIAIOSFODNN7EXAMPLE', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'
    url = storage.presigned_url('GET', 'examplebucket.s3.amazonaws.com', '/test.txt', access_key=key, secret=secret, now=now,
                                expires=86400, region='us-east-1')
    assert 'X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404' in url
    headers = {'host': 'examplebucket.s3.amazonaws.com', 'range': 'bytes=0-9', 'x-amz-date': '20130524T000000Z',
               'x-amz-content-sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'}
    signature, _, _ = storage.sign('GET', headers['host'], '/test.txt', {}, headers, headers['x-amz-content-sha256'],
                                   access_key=key, secret=secret, now=now, region='us-east-1')
    assert signature == 'f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41'


def test_uploads_are_checked_and_files_follow_their_material(env):
    c = teacher(env)
    url = f"/api/teaching/subjects/{env['subject'].id}/files"
    assert c.post(url + '?filename=notes.exe', content=b'MZ').status_code == 422
    assert c.post(url + '?filename=notes.pdf', content=b'not a pdf').status_code == 422
    assert c.post(url + '?filename=big.pdf', content=PDF + b'0' * storage.MAX_FILE_BYTES).status_code == 413
    uploaded = c.post(url + '?filename=Week 1 notes.pdf', content=PDF)
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()['id']
    # Another teacher cannot attach or read it.
    other = env['as_user'](env['unrelated'])
    assert other.get(f'/api/files/{file_id}').status_code == 404

    c = teacher(env)
    material = c.post(f"/api/teaching/subjects/{env['subject'].id}/materials",
                      json=dict(title='Week 1', section='Week 1', file_id=file_id, published=False))
    assert material.status_code == 201, material.text
    assert material.json()['file']['filename'] == 'Week 1 notes.pdf'
    assert pupil(env).get(f'/api/files/{file_id}').status_code == 404  # not published yet

    c = teacher(env)
    assert c.put(f"/api/teaching/materials/{material.json()['id']}", json=dict(title='Week 1', section='Week 1', file_id=file_id, published=True)).status_code == 200
    s = pupil(env)
    link = s.get(f'/api/files/{file_id}')
    assert link.status_code == 200
    content = s.get(link.json()['url'])
    assert content.content == PDF and content.headers['content-disposition'].startswith('inline')
    assert env['as_user'](env['other_pupil']).get(f'/api/files/{file_id}').status_code == 404
    # The student was told about the new material, once.
    s = pupil(env)
    inbox = s.get('/api/notifications').json()
    assert [n['title'] for n in inbox['items']] == ['New material in Math: Week 1'] and inbox['unread'] == 1
    assert s.post('/api/notifications/read', json=dict(all=True)).json()['unread'] == 0
    course = s.get(f"/api/student/courses/{env['subject'].id}").json()
    assert course['sections'][0]['name'] == 'Week 1' and course['sections'][0]['materials'][0]['file']['id'] == file_id


def test_uploads_switched_off_without_storage(env, monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_BACKEND', '')
    response = teacher(env).post(f"/api/teaching/subjects/{env['subject'].id}/files?filename=a.pdf", content=PDF)
    assert response.status_code == 503 and 'not set up' in response.json()['detail']


def test_students_hand_in_allowed_file_types_and_drafts_stay_private(env):
    db, work = env['db'], env['work']
    work.published, work.submission_file_types = True, ['pdf']
    db.commit()
    s = pupil(env)
    url = f'/api/student/assignments/{work.id}/files'
    assert s.post(url + '?filename=answer.docx', content=b'PK\x03\x04rest').status_code == 422
    file_id = s.post(url + '?filename=answer.pdf', content=PDF).json()['id']
    draft = s.put(f'/api/student/assignments/{work.id}/submission', json=dict(file_id=file_id, submit=False))
    assert draft.status_code == 200, draft.text
    assert teacher(env).get(f'/api/files/{file_id}').status_code == 404
    s = pupil(env)
    final = s.put(f'/api/student/assignments/{work.id}/submission', json=dict(file_id=file_id, submit=True, expected_version=1))
    assert final.status_code == 200 and final.json()['file']['filename'] == 'answer.pdf'
    c = teacher(env)
    assert c.get(f'/api/files/{file_id}').status_code == 200
    assert c.get(f'/api/teaching/coursework/{work.id}/submissions').json()[0]['file']['id'] == file_id
    # Someone else's upload cannot be attached.
    assert pupil(env).post(url + '?filename=late.pdf', content=PDF).status_code == 409


def test_quiz_is_marked_by_the_server_and_feeds_marks(env):
    work_id = make_quiz(env)
    s = pupil(env)
    overview = s.get(f'/api/student/quizzes/{work_id}').json()
    assert overview['can_start'] and overview['rules']['question_count'] == 3 and not overview['rules']['one_at_a_time']
    attempt_id = s.post(f'/api/student/quizzes/{work_id}/attempts').json()['id']
    state = s.get(f'/api/student/quiz-attempts/{attempt_id}').json()
    assert all('correct' not in q for q in state['questions'])  # answers never reach the browser early
    ids = {q['prompt']: q['id'] for q in state['questions']}
    s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=ids['2 + 2 = ?'], selected=['b']))
    s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=ids['Pick the even numbers'], selected=['a']))
    assert s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=ids['2 + 2 = ?'], selected=['a', 'b'])).status_code == 422
    done = s.post(f'/api/student/quiz-attempts/{attempt_id}/submit').json()
    # 2 points for the single answer; partly right multiple-select earns nothing; unanswered earns nothing.
    assert done['status'] == 'SUBMITTED' and float(done['score']) == 2 and float(done['max_score']) == 6
    assert done['answers_visible'] and {q['prompt']: float(q['earned']) for q in done['questions']}['2 + 2 = ?'] == 2
    score = env['db'].query(Score).filter_by(coursework_id=work_id, student_id=env['student'].id).one()
    assert float(score.score) == 2
    assert s.post(f'/api/student/quizzes/{work_id}/attempts').status_code == 409  # one attempt by default
    # Questions are frozen once anyone has started.
    assert teacher(env).put(f'/api/teaching/quizzes/{work_id}/questions', json=dict(questions=QUESTIONS)).status_code == 409


def test_hidden_results_and_extra_attempt_keeps_best_score(env):
    work_id = make_quiz(env, settings_body=dict(hide_results_until_close=True, attempts_allowed=1, log_tab_switches=True))
    s = pupil(env)
    attempt_id = s.post(f'/api/student/quizzes/{work_id}/attempts').json()['id']
    q = s.get(f'/api/student/quiz-attempts/{attempt_id}').json()['questions']
    first = next(x for x in q if x['prompt'] == '2 + 2 = ?')
    s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=first['id'], selected=['b']))
    assert s.post(f'/api/student/quiz-attempts/{attempt_id}/events', json=dict(kind='LEFT_PAGE')).status_code == 204
    done = s.post(f'/api/student/quiz-attempts/{attempt_id}/submit').json()
    assert done['score'] is None and not done['answers_visible'] and 'correct' not in done['questions'][0]

    c = teacher(env)
    results = c.get(f'/api/teaching/quizzes/{work_id}/results').json()
    row = next(r for r in results['students'] if r['student_id'] == str(env['student'].id))
    assert float(row['best']) == 2 and row['attempts'][0]['tab_switches'] == 1
    assert c.put(f'/api/teaching/quizzes/{work_id}/settings', json=dict(hide_results_until_close=False, attempts_allowed=1, log_tab_switches=True)).status_code == 409
    assert c.post(f'/api/teaching/quizzes/{work_id}/extra-attempts', json=dict(student_id=str(env['student'].id), reason='Power cut')).status_code == 201

    s = pupil(env)
    second = s.post(f'/api/student/quizzes/{work_id}/attempts')
    assert second.status_code == 201
    s.post(f"/api/student/quiz-attempts/{second.json()['id']}/submit")  # blank second attempt scores 0
    assert float(env['db'].query(Score).filter_by(coursework_id=work_id, student_id=env['student'].id).one().score) == 2


def test_timed_questions_move_on_and_time_runs_out_on_the_server(env):
    timed = [dict(q, time_limit_seconds=30) for q in QUESTIONS]
    work_id = make_quiz(env, questions=timed)
    s = pupil(env)
    attempt_id = s.post(f'/api/student/quizzes/{work_id}/attempts').json()['id']
    state = s.get(f'/api/student/quiz-attempts/{attempt_id}').json()
    assert state['sequential'] and state['index'] == 0 and 'questions' not in state
    first_question = state['question']['id']
    # The student walks away: the first question's time runs out without them.
    db = env['db']
    attempt = db.query(QuizAttempt).one()
    attempt.current_started_at = attempt.current_started_at - timedelta(seconds=40)
    db.commit()
    s = pupil(env)
    late = s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=first_question, selected=['b']))
    assert late.status_code == 409
    state = s.get(f'/api/student/quiz-attempts/{attempt_id}').json()
    assert state['index'] == 1
    # There is no way back to an earlier question.
    assert s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=first_question, selected=['b'])).status_code == 409
    second = state['question']
    moved = s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=second['id'], selected=[second['options'][0]['id']]))
    assert moved.json()['index'] == 2
    # The whole attempt runs out of time: it submits itself and the mark is recorded.
    attempt = db.query(QuizAttempt).one()
    attempt.ends_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    results = teacher(env).get(f'/api/teaching/quizzes/{work_id}/results').json()
    mine = next(r for r in results['students'] if r['student_id'] == str(env['student'].id))
    assert mine['attempts'][0]['status'] == 'SUBMITTED' and mine['attempts'][0]['auto_submitted']
    assert db.query(Score).filter_by(coursework_id=work_id, student_id=env['student'].id).one() is not None


def test_quiz_rules_and_switch(env):
    c = teacher(env)
    base = dict(title='Q', instructions='x', max_score=1, delivery='QUIZ')
    assert c.post(f"/api/teaching/subjects/{env['subject'].id}/coursework", json=base).status_code == 422  # needs a closing time
    assert c.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
                  json=dict(base, due_at=soon(hours=1), opens_at=soon(hours=2))).status_code == 422
    bad = dict(kind='SINGLE', prompt='?', options=[dict(id='a', text='1'), dict(id='b', text='2')], correct=['a', 'b'])
    work_id = make_quiz(env, publish=False)
    assert teacher(env).put(f'/api/teaching/quizzes/{work_id}/questions', json=dict(questions=[bad])).status_code == 422
    future = make_quiz(env, opens_at=soon(hours=1), due_at=soon(hours=3))
    s = pupil(env)
    assert s.get(f'/api/student/quizzes/{future}').json()['blocked_reason'] == 'NOT_OPEN'
    assert s.post(f'/api/student/quizzes/{future}/attempts').status_code == 409
    # The platform can switch online quizzes off.
    institution = env['db'].get(Institution, env['institutions'][0].id)
    institution.module_settings = {'online_quizzes': False}
    env['db'].commit()
    assert pupil(env).get(f'/api/student/quizzes/{future}').status_code == 403


def test_publishing_notifies_and_deadlines_list_upcoming_work(env):
    c = teacher(env)
    work = c.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
                  json=dict(title='Essay', instructions='Write', max_score=10, due_at=soon(hours=20), published=True, section='Week 2')).json()
    s = pupil(env)
    inbox = s.get('/api/notifications').json()
    assert inbox['items'][0]['title'] == 'New assignment in Math: Essay' and inbox['items'][0]['link'] == f"/student/assignments/{work['id']}"
    assert [d['title'] for d in inbox['due_soon']] == ['Essay']
    deadlines = s.get('/api/student/deadlines').json()
    assert deadlines[0]['title'] == 'Essay' and deadlines[0]['status'] == 'TODO'
    courses = s.get('/api/student/courses').json()
    assert courses[0]['to_do'] == 1 and courses[0]['next_due']['title'] == 'Essay'
    assert teacher(env).get('/api/teaching/deadlines').json()[0]['title'] == 'Essay'
    assert teacher(env).get(f"/api/teaching/courses/{env['subject'].id}").json()['sections'][-1]['name'] == 'Week 2'


def test_registration_window_choices_wait_for_approval(env):
    db, tenant = env['db'], env['institutions'][0].id
    optional = [Subject(institution_id=tenant, class_id=env['cls'].id, name=name, teacher_id=env['teacher'].id, registration_mode='INDIVIDUAL')
                for name in ('French', 'Music', 'Art')]
    db.add_all(optional); db.commit()
    admin = env['as_user'](env['admin'])
    window = admin.post('/api/course-registration/windows', json=dict(title='Term 1 options', opens_at=soon(hours=-1), closes_at=soon(days=7),
                                                                     min_units=1, max_units=2))
    assert window.status_code == 201, window.text
    window_id = window.json()['id']
    s = pupil(env)
    mine = s.get('/api/student/registration').json()
    assert [u['name'] for u in mine[0]['units']] == ['Art', 'French', 'Music']
    ids = {u['name']: u['id'] for u in mine[0]['units']}
    assert s.put(f'/api/student/registration/{window_id}', json=dict(subject_ids=list(ids.values()))).status_code == 422  # max 2
    saved = s.put(f'/api/student/registration/{window_id}', json=dict(subject_ids=[ids['French'], ids['Music']]))
    assert saved.status_code == 200, saved.text
    assert {u['name']: u['status'] for u in saved.json()[0]['units']} == {'Art': None, 'French': 'PENDING', 'Music': 'PENDING'}
    # Pending choices do not give access yet.
    assert 'French' not in [x['name'] for x in s.get('/api/student/subjects').json()]

    admin = env['as_user'](env['admin'])
    pending = admin.get(f'/api/course-registration/requests?window_id={window_id}').json()
    assert len(pending) == 2
    french = next(r for r in pending if r['subject_name'] == 'French')
    music = next(r for r in pending if r['subject_name'] == 'Music')
    assert admin.post('/api/course-registration/decisions', json=dict(ids=[music['id']], approve=False)).status_code == 422  # reason needed
    assert admin.post('/api/course-registration/decisions', json=dict(ids=[music['id']], approve=False, note='Class is full')).json()['decided'] == 1
    assert admin.post('/api/course-registration/decisions', json=dict(ids=[french['id']], approve=True)).json()['decided'] == 1
    s = pupil(env)
    assert 'French' in [x['name'] for x in s.get('/api/student/subjects').json()]
    assert {n['title'] for n in s.get('/api/notifications').json()['items']} >= {'French approved', 'Music not approved'}
    # A teacher without the approval right cannot see the queue.
    assert env['as_user'](env['teacher']).get('/api/course-registration/requests').status_code == 403
    # After the window closes, choices are fixed.
    row = db.query(CourseRegistration).filter_by(subject_id=optional[2].id).first()  # Art was never chosen
    assert row is None
    from app.models.elearning import RegistrationWindow
    w = db.query(RegistrationWindow).one()
    w.closes_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert pupil(env).put(f'/api/student/registration/{window_id}', json=dict(subject_ids=[ids['Art']])).status_code == 409


def test_platform_sees_storage_use(env):
    from test_workspace_access import platform
    teacher(env).post(f"/api/teaching/subjects/{env['subject'].id}/files?filename=a.pdf", content=PDF)
    usage = env['as_user'](platform(env)).get('/api/platform/storage').json()
    assert usage['enabled'] and usage['schools'][0]['files'] == 1 and usage['schools'][0]['bytes'] == len(PDF)
    assert env['db'].query(StoredFile).count() == 1
    assert env['db'].query(Coursework).count() >= 1


def test_answering_the_last_timed_question_counts_it(env):
    work_id = make_quiz(env, questions=[dict(q, time_limit_seconds=60) for q in QUESTIONS])
    s = pupil(env)
    attempt_id = s.post(f'/api/student/quizzes/{work_id}/attempts').json()['id']
    state = s.get(f'/api/student/quiz-attempts/{attempt_id}').json()
    right = {'2 + 2 = ?': ['b'], 'Pick the even numbers': ['a', 'c'], 'Nairobi is in Kenya': ['true']}
    while state['status'] == 'IN_PROGRESS':
        q = state['question']
        state = s.put(f'/api/student/quiz-attempts/{attempt_id}/answer', json=dict(question_id=q['id'], selected=right[q['prompt']])).json()
    assert float(state['score']) == 6 and not state['auto_submitted']


def test_upload_quota_per_person_per_day(env, monkeypatch):
    monkeypatch.setattr(settings, 'STORAGE_USER_DAILY_MB', 0)
    response = teacher(env).post(f"/api/teaching/subjects/{env['subject'].id}/files?filename=a.pdf", content=PDF)
    assert response.status_code == 429 and 'last day' in response.json()['detail']
