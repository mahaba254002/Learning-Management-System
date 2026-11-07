"""Phase 6: hand-entered timetables, clash checks with override, availability, one-day changes and personal views."""
from datetime import date, time, timedelta

import pytest

from test_teaching import env  # noqa: F401
from app.core import rate_limit as limiter
from app.models.academic import Subject
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.structure import OfferingTeacher


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


def monday(offset_weeks=0):
    today = date.today()
    return today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)


@pytest.fixture
def tt(env):
    db, tenant = env["db"], env["institutions"][0].id
    year = AcademicYear(institution_id=tenant, name="2026", start_date=monday(-10), end_date=monday(30), status="ACTIVE")
    db.add(year); db.flush()
    term = AcademicPeriod(institution_id=tenant, year_id=year.id, name="Term 3", start_date=monday(-4), end_date=monday(8))
    english = Subject(institution_id=tenant, class_id=env["cls"].id, name="English", teacher_id=env["supervisor"].id)
    db.add_all([term, english]); db.flush()
    db.add(OfferingTeacher(institution_id=tenant, subject_id=english.id, user_id=env["supervisor"].id, role="LEAD"))
    db.commit()
    admin = lambda: env["as_user"](env["admin"])
    base = f"/api/timetable/terms/{term.id}"
    slots = {}
    for label, start, end, brk in [("Lesson 1", "08:00", "08:40", False), ("Lesson 2", "08:40", "09:20", False), ("Break", "09:20", "09:40", True)]:
        response = admin().post(f"{base}/slots", json=dict(label=label, start_time=start, end_time=end, is_break=brk))
        assert response.status_code == 201, response.text
        slots[label] = response.json()["id"]
    return dict(env=env, term=term, english=english, base=base, slots=slots, admin=admin)


def test_bell_schedule_rejects_overlaps_and_lessons_in_breaks(tt):
    admin, base, slots = tt["admin"], tt["base"], tt["slots"]
    assert admin().post(f"{base}/slots", json=dict(label="Bad", start_time="08:30", end_time="09:00")).status_code == 409
    # A Saturday-only period may share times with weekday periods.
    assert admin().post(f"{base}/slots", json=dict(label="Sat prep", start_time="08:30", end_time="09:00", weekdays=[6])).status_code == 201
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Break"], weekday=1, subject_id=str(tt["env"]["subject"].id))).status_code == 409
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=6, subject_id=str(tt["env"]["subject"].id))).status_code == 409
    assert tt["env"]["as_user"](tt["env"]["teacher"]).post(f"{base}/slots", json=dict(label="X", start_time="10:00", end_time="10:40")).status_code == 403


def test_clashes_are_refused_unless_overridden_with_a_reason(tt):
    env, admin, base, slots = tt["env"], tt["admin"], tt["base"], tt["slots"]
    math, english = env["subject"], tt["english"]
    first = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=1, subject_id=str(math.id)))
    assert first.status_code == 201, first.text
    # Same class, same time, both cohort subjects: class clash.
    clash = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=1, subject_id=str(english.id)))
    assert clash.status_code == 409
    assert clash.json()["detail"]["clashes"][0]["kind"] == "CLASS"
    saved = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=1, subject_id=str(english.id), override_reason="Combined lesson"))
    assert saved.status_code == 201 and saved.json()["clashes"]
    # Teacher unavailable on Tuesday morning.
    away = admin().post(f"{base}/unavailability", json=dict(teacher_id=str(env["teacher"].id), weekday=2, start_time="08:00", end_time="10:00", reason="Part-time"))
    assert away.status_code == 201
    blocked = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 2"], weekday=2, subject_id=str(math.id)))
    assert blocked.status_code == 409 and blocked.json()["detail"]["clashes"][0]["kind"] == "UNAVAILABLE"
    # Only an allocated teacher can take a lesson.
    other = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 2"], weekday=3, subject_id=str(math.id), teacher_id=str(env["unrelated"].id)))
    assert other.status_code == 409


def test_optional_offerings_may_share_a_class_period(tt):
    env, admin, base, slots = tt["env"], tt["admin"], tt["base"], tt["slots"]
    for subject in (env["subject"], tt["english"]):
        subject.registration_mode = "INDIVIDUAL"
    env["db"].commit()
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 2"], weekday=4, subject_id=str(env["subject"].id))).status_code == 201
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 2"], weekday=4, subject_id=str(tt["english"].id))).status_code == 201


def test_teachers_and_students_see_it_only_once_published(tt):
    env, admin, base, slots = tt["env"], tt["admin"], tt["base"], tt["slots"]
    today = date.today()
    weekday = today.isoweekday() if today.isoweekday() <= 5 else 1
    assert admin().post(f"{base}/publish", json=dict(published=True)).status_code == 409  # Nothing to publish yet.
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=weekday, subject_id=str(env["subject"].id))).status_code == 201
    start = monday().isoformat()
    teacher = lambda: env["as_user"](env["teacher"])
    assert teacher().get(f"/api/timetable/me?start={start}").json()["lessons"] == []
    assert teacher().get(f"/api/timetable/classes/{env['cls'].id}?period_id={tt['term'].id}").status_code == 404
    assert admin().post(f"{base}/publish", json=dict(published=True)).status_code == 200
    lessons = teacher().get(f"/api/timetable/me?start={start}").json()["lessons"]
    assert [(l["subject_name"], l["start_time"], l["end_time"], l["status"]) for l in lessons] == [("Math", "08:00", "08:40", "SCHEDULED")]
    pupil = env["as_user"](env["pupil"]).get(f"/api/timetable/me?start={start}").json()["lessons"]
    assert len(pupil) == 1 and pupil[0]["teacher_name"] == "teacher Test"
    grid = env["as_user"](env["pupil"]).get(f"/api/timetable/classes/{env['cls'].id}?period_id={tt['term'].id}").json()
    assert len(grid["entries"]) == 1 and "subjects" not in grid
    assert env["as_user"](env["unrelated"]).get(f"/api/timetable/classes/{env['cls'].id}?period_id={tt['term'].id}").status_code == 404


def test_one_day_changes(tt):
    env, admin, base, slots = tt["env"], tt["admin"], tt["base"], tt["slots"]
    entry = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=1, subject_id=str(env["subject"].id))).json()["id"]
    english = admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 2"], weekday=1, subject_id=str(tt["english"].id))).json()["id"]
    assert admin().post(f"{base}/publish", json=dict(published=True)).status_code == 200
    mon, next_mon = monday(1), monday(2)
    url = f"/api/timetable/entries/{entry}/changes"
    # The date must be a Monday in the term.
    assert admin().post(url, json=dict(lesson_date=(mon + timedelta(days=1)).isoformat(), kind="CANCELLED")).status_code == 409
    assert admin().post(url, json=dict(lesson_date=mon.isoformat(), kind="CANCELLED", note="Sports day")).status_code == 201
    # The supervisor already teaches English at 08:40 on Mondays, so covering Math then needs no override,
    # but covering at the same time as their own lesson does.
    sub = admin().post(url, json=dict(lesson_date=next_mon.isoformat(), kind="SUBSTITUTE", substitute_id=str(env["supervisor"].id)))
    assert sub.status_code == 201, sub.text
    moved = admin().post(f"/api/timetable/entries/{english}/changes", json=dict(lesson_date=next_mon.isoformat(), kind="MOVED",
                                                                                   new_date=next_mon.isoformat(), new_slot_id=slots["Lesson 1"]))
    assert moved.status_code == 409  # The supervisor is covering Math at 08:00 that day.
    teacher = env["as_user"](env["teacher"]).get(f"/api/timetable/me?start={mon.isoformat()}&days=14").json()["lessons"]
    assert [(l["date"], l["status"]) for l in teacher] == [(mon.isoformat(), "CANCELLED"), (next_mon.isoformat(), "SUBSTITUTE")]
    covering = env["as_user"](env["supervisor"]).get(f"/api/timetable/me?start={next_mon.isoformat()}&days=1").json()["lessons"]
    assert {(l["subject_name"], l["status"]) for l in covering} == {("Math", "COVERING"), ("English", "SCHEDULED")}
    listed = admin().get(f"/api/timetable/changes?start={mon.isoformat()}&end={next_mon.isoformat()}").json()
    assert [c["kind"] for c in listed] == ["CANCELLED", "SUBSTITUTE"]
    assert admin().delete(f"/api/timetable/changes/{listed[0]['id']}").status_code == 200


def test_copy_a_term_into_an_empty_term(tt):
    env, admin, base, slots = tt["env"], tt["admin"], tt["base"], tt["slots"]
    assert admin().post(f"{base}/entries", json=dict(slot_id=slots["Lesson 1"], weekday=2, subject_id=str(env["subject"].id))).status_code == 201
    db = env["db"]
    nxt = AcademicPeriod(institution_id=tt["term"].institution_id, year_id=tt["term"].year_id, name="Term 4", start_date=monday(9), end_date=monday(20))
    db.add(nxt); db.commit()
    copied = admin().post(f"/api/timetable/terms/{nxt.id}/copy?source_period_id={tt['term'].id}").json()
    assert (copied["slots"], copied["lessons"]) == (3, 1)
    assert admin().post(f"/api/timetable/terms/{nxt.id}/copy?source_period_id={tt['term'].id}").status_code == 409
    assert len(admin().get(f"/api/timetable/classes/{env['cls'].id}?period_id={nxt.id}").json()["entries"]) == 1
