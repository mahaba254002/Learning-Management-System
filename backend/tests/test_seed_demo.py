from datetime import date
import importlib.util
from pathlib import Path
from test_teaching import env
from app.models.academic import Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.learning import Submission
from app.models.user import User
from app.models.institution import Institution

spec = importlib.util.spec_from_file_location('seed_demo', Path(__file__).resolve().parents[1] / 'scripts/seed_demo.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_complete_demo_is_consistent_and_repeatable(env):
    db = env['db']
    original_name = env['institutions'][0].name
    result = module.seed(db, 'test-only-unused-hash', date(2026, 9, 30))
    db.commit()
    assert result['created']['institutions'] == 4
    assert result['created']['users'] == 49
    assert result['created']['students'] == 36
    assert result['created']['academic_classes'] == 4
    assert result['created']['teaching_subjects'] == 12
    assert result['created']['coursework'] == 72
    assert result['created']['course_materials'] == 36
    assert result['created']['invitations'] == 10
    assert result['created']['assignment_submissions'] == 156
    assert result['created']['student_scores'] == 168
    assert result['created']['student_attendance'] == 1200
    ids = {u.id for u in db.query(User).all() if u.username.startswith('demo.')}
    for student in db.query(Student).filter(Student.user_id.in_(ids)).all():
        assert db.query(Enrollment).filter_by(student_id=student.id).count() == 1
    for row in db.query(Submission).all():
        work = db.get(Coursework, row.coursework_id)
        subject = db.get(Subject, work.subject_id)
        assert work.institution_id == row.institution_id == subject.institution_id
        assert db.query(Enrollment).filter_by(student_id=row.student_id, class_id=subject.class_id, active=True).count() == 1
        assert (row.status == 'SUBMITTED') == (row.submitted_at is not None)
        if row.submitted_at:
            assert row.is_late == (row.submitted_at.replace(tzinfo=None) > work.due_at.replace(tzinfo=None))
    for score in db.query(Score).all():
        assert 0 <= score.score <= db.get(Coursework, score.coursework_id).max_score
    assert all(r.day.weekday() < 5 and r.day < date(2026, 9, 30) for r in db.query(Attendance).all())
    school = db.get(Institution, module.identity('acacia/institution'))
    school.name = 'User edited demo school'
    db.commit()
    again = module.seed(db, 'different-hash', date(2026, 10, 1))
    db.commit()
    assert again['created'] == {}
    assert school.name == 'User edited demo school'
    assert env['institutions'][0].name == original_name
    assert db.get(User, module.identity('demo/platform')).password_hash == 'test-only-unused-hash'
    c = env['as_user'](db.get(User, module.identity('demo/acacia/admin')))
    assert c.get('/api/institution/overview').json()['students'] == 18
    c = env['as_user'](db.get(User, module.identity('demo/acacia/student01')))
    assert len(c.get('/api/student/subjects').json()) == 3
    assert len(c.get('/api/student/assignments').json()) == 15
    assert len(c.get('/api/student/attendance').json()) == 40
