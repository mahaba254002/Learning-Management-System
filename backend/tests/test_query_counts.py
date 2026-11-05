"""Result calculations must not run extra queries for every grade a student holds."""
from contextlib import contextmanager

from sqlalchemy import event

from test_teaching import env
from test_grading_rules import approve, setup
from app.models.academic import Coursework, Score, Subject
from app.models.final_grade import FinalGrade
from app.services import final_grades as grades


@contextmanager
def counted(db):
    queries = []

    def track(*args):
        queries.append(args[2])

    event.listen(db.get_bind(), "before_cursor_execute", track)
    try:
        yield queries
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", track)


def add_released_grade(env, name):
    db, base = env["db"], env["subject"]
    subject = Subject(institution_id=base.institution_id, class_id=base.class_id, name=name,
                      teacher_id=base.teacher_id, catalogue_id=base.catalogue_id)
    db.add(subject)
    db.flush()
    # The grading policy weights all three kinds, so each offering needs one of each.
    for kind, maximum, score in [("ASSIGNMENT", 20, 15), ("COURSEWORK", 50, 35), ("EXAM", 100, 64)]:
        work = Coursework(institution_id=base.institution_id, subject_id=subject.id, kind=kind, title=kind,
                          instructions="Test", max_score=maximum, published=True, grades_released=True)
        db.add(work)
        db.flush()
        db.add(Score(institution_id=base.institution_id, student_id=env["student"].id, coursework_id=work.id, score=score))
    db.commit()
    db.expire_all()  # Calculate from stored values, as a real request would.
    data = grades.compute(db, subject, env["student"].id)
    assert data["ready"], data["issues"]
    db.add(FinalGrade(institution_id=base.institution_id, subject_id=subject.id, student_id=env["student"].id,
                      scope="ALL", source_digest=data["source_digest"], result=data["result"], released=True))
    db.commit()


def test_academic_results_query_count_does_not_grow_with_grades(env):
    setup(env)
    env["db"].expire_all()  # The test session shares objects with the API; use stored values.
    approve(env)
    db, tenant, student = env["db"], env["institutions"][0].id, env["student"].id
    with counted(db) as one:
        first = grades.academic_results(db, tenant, student)
    assert len(first["final_grades"]) == 1

    for n in range(5):
        add_released_grade(env, f"Extra subject {n}")
    with counted(db) as six:
        result = grades.academic_results(db, tenant, student)
    assert len(result["final_grades"]) == 6
    assert result["gpa"] is not None
    assert len(six) <= len(one) + 1, (len(one), len(six))
