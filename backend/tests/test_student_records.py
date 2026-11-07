"""Phase 5: student status, guardians, fee status, discipline, announcements and attendance percentages."""
from datetime import date, time, timedelta

import pytest

from test_teaching import env  # noqa: F401
from app.core import rate_limit as limiter
from app.models.academic import Attendance
from app.models.management import StaffMember
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.structure import StaffPermission
from app.models.user import User, UserRole, UserStatus
from app.services.attendance import outcome


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


def term(env):
    db, tenant = env["db"], env["institutions"][0].id
    today = date.today()
    year = AcademicYear(institution_id=tenant, name="2026", start_date=today - timedelta(days=200), end_date=today + timedelta(days=100), status="ACTIVE")
    db.add(year); db.flush()
    first = AcademicPeriod(institution_id=tenant, year_id=year.id, name="Term 1", start_date=today - timedelta(days=200), end_date=today - timedelta(days=101))
    current = AcademicPeriod(institution_id=tenant, year_id=year.id, name="Term 2", start_date=today - timedelta(days=100), end_date=today + timedelta(days=100))
    db.add_all([first, current]); db.commit()
    return first, current


def bursar(env, permissions=("fees.manage",)):
    db, tenant = env["db"], env["institutions"][0].id
    user = User(institution_id=tenant, username="bursar", first_name="Bursar", last_name="Test", email="bursar@example.test",
                role=UserRole.STAFF, password_hash="unused", must_change_password=False)
    db.add(user); db.flush()
    db.add(StaffMember(institution_id=tenant, user_id=user.id, staff_number="B-1", first_name="Bursar", last_name="Test",
                       category="NON_TEACHING", job_title="Bursar"))
    db.add_all([StaffPermission(institution_id=tenant, user_id=user.id, permission=p) for p in permissions])
    db.commit()
    return user


def test_late_rule():
    assert outcome("PRESENT") == "ATTENDED"
    assert outcome("ABSENT") == "MISSED"
    assert outcome("EXCUSED") == "EXCUSED"
    assert outcome("LATE", time(8, 5), time(8, 40), cutoff_minutes=30) == "ATTENDED"
    # Exactly 30 minutes left is inside the cut-off.
    assert outcome("LATE", time(8, 10), time(8, 40), cutoff_minutes=30) == "MISSED"
    # Arrived with 20 minutes left of the lesson: counts as missed...
    assert outcome("LATE", time(8, 20), time(8, 40), cutoff_minutes=30) == "MISSED"
    # ...unless the teacher accepted a reason.
    assert outcome("LATE", time(8, 20), time(8, 40), reason_accepted=True, cutoff_minutes=30) == "ATTENDED"
    # Without the lesson's end time, late is attended.
    assert outcome("LATE", time(8, 20), None) == "ATTENDED"


def test_attendance_percentages_per_subject_and_term(env):
    first, current = term(env)
    teacher = env["as_user"](env["teacher"])
    cls, subject, student = env["cls"], env["subject"], env["student"]
    day = date.today()

    def register(day, status, **extra):
        entry = dict(student_id=str(student.id), status=status, note=extra.pop("note", ""), **{k: v for k, v in extra.items() if k != "lesson_end"})
        body = dict(day=day.isoformat(), subject_id=str(subject.id), entries=[entry])
        if "lesson_end" in extra:
            body["lesson_end"] = extra["lesson_end"]
        return teacher.put(f"/api/teaching/classes/{cls.id}/attendance", json=body)

    assert register(day, "LATE", arrived_at="08:20", lesson_end="08:40").status_code == 200
    assert register(day - timedelta(days=1), "PRESENT").status_code == 200
    assert register(day - timedelta(days=2), "EXCUSED").status_code == 200
    assert register(day - timedelta(days=3), "LATE", arrived_at="08:05", lesson_end="08:40").status_code == 200
    # Accepting a reason needs the reason written down.
    assert register(day - timedelta(days=4), "LATE", arrived_at="08:30", lesson_end="08:40", reason_accepted=True).status_code == 422
    assert register(day - timedelta(days=4), "LATE", arrived_at="08:30", lesson_end="08:40", reason_accepted=True, note="Clinic visit").status_code == 200
    # Previous term: absent.
    assert register(first.start_date + timedelta(days=1), "ABSENT").status_code == 200

    row = env["db"].query(Attendance).filter_by(student_id=student.id, day=day).one()
    assert (row.outcome, row.arrived_at, row.lesson_end) == ("MISSED", time(8, 20), time(8, 40))

    summary = teacher.get(f"/api/attendance/summary?class_id={cls.id}").json()
    assert summary["label"] == "Term 2"
    assert [c["key"] for c in summary["columns"]] == [str(subject.id)]  # Subject teacher: no class register column.
    cell = summary["rows"][0]["cells"][str(subject.id)]
    assert (cell["attended"], cell["missed"], cell["excused"], cell["percent"]) == (3, 1, 1, 75.0)

    earlier = teacher.get(f"/api/attendance/summary?class_id={cls.id}&period_id={first.id}").json()
    assert earlier["rows"][0]["cells"][str(subject.id)]["percent"] == 0.0

    supervisor = env["as_user"](env["supervisor"]).get(f"/api/attendance/summary?class_id={cls.id}").json()
    assert [c["key"] for c in supervisor["columns"]][0] == "class"

    mine = env["as_user"](env["pupil"]).get("/api/student/attendance/summary").json()
    assert next(r for r in mine["rows"] if r["key"] == str(subject.id))["percent"] == 75.0
    assert mine["overall"]["percent"] == 75.0
    assert env["as_user"](env["unrelated"]).get(f"/api/attendance/summary?class_id={cls.id}").status_code == 404


def test_cutoff_is_an_institution_setting(env):
    admin = env["as_user"](env["admin"])
    settings = admin.get("/api/institution/learning-settings").json()
    assert settings["late_cutoff_minutes"] == 30
    saved = admin.put("/api/institution/learning-settings", json={**{k: v for k, v in settings.items() if k in {
        "student_label", "teacher_label", "class_label", "subject_label", "period_label", "default_student_login", "grade_bands"}},
        "late_cutoff_minutes": 10})
    assert saved.status_code == 200, saved.text
    teacher = env["as_user"](env["teacher"])
    body = dict(day=date.today().isoformat(), subject_id=str(env["subject"].id), lesson_end="08:40",
                entries=[dict(student_id=str(env["student"].id), status="LATE", arrived_at="08:20")])
    assert teacher.put(f"/api/teaching/classes/{env['cls'].id}/attendance", json=body).status_code == 200
    assert env["db"].query(Attendance).filter_by(student_id=env["student"].id).one().outcome == "ATTENDED"


def test_fee_status_access_and_rules(env):
    _, current = term(env)
    student = env["student"]
    admin = env["as_user"](env["admin"])
    url = f"/api/records/fees/{student.id}"
    assert admin.put(url, json=dict(period_id=str(current.id), status="PARTIAL", balance="0")).status_code == 422
    saved = admin.put(url, json=dict(period_id=str(current.id), status="PARTIAL", balance="12500.50", note="Bus fee pending"))
    assert saved.status_code == 200, saved.text
    paid = admin.put(url, json=dict(period_id=str(current.id), status="PAID", balance="999"))
    assert paid.json()["balance"] in ("0", "0.00", 0)

    listing = admin.get("/api/records/fees").json()
    assert listing["period_id"] == str(current.id)
    assert listing["items"][0]["fee"]["status"] == "PAID"

    # Class teacher reads their class only; cannot edit.
    supervisor = env["as_user"](env["supervisor"])
    assert supervisor.get("/api/records/fees").json()["items"][0]["admission_number"] == "A001"
    assert supervisor.put(url, json=dict(period_id=str(current.id), status="UNPAID", balance="10")).status_code == 403
    # Subject teachers and students have no access.
    assert env["as_user"](env["teacher"]).get("/api/records/fees").status_code == 403
    assert env["as_user"](env["pupil"]).get("/api/records/fees").status_code == 403

    # Bursar with fees.manage edits; without it, refused.
    clerk = env["as_user"](bursar(env))
    assert clerk.put(url, json=dict(period_id=str(current.id), status="UNPAID", balance="4000")).status_code == 200
    assert clerk.get("/api/records/students").status_code == 403


def test_fee_list_import_checks_every_row_before_applying(env):
    _, current = term(env)
    admin = env["as_user"](env["admin"])
    rows = [dict(admission_number="a001 ", status="Partly paid", balance="KES 3,000"), dict(admission_number="ZZZ", status="Paid")]
    preview = admin.post("/api/records/fees/import", json=dict(period_id=str(current.id), rows=rows)).json()
    assert (preview["valid"], preview["errors"]) == (1, 1)
    assert admin.post("/api/records/fees/import", json=dict(period_id=str(current.id), rows=rows, commit=True)).status_code == 422
    applied = admin.post("/api/records/fees/import", json=dict(period_id=str(current.id), rows=rows[:1], commit=True)).json()
    assert applied["applied"] is True
    item = admin.get(f"/api/records/fees?period_id={current.id}").json()["items"][0]
    assert item["fee"]["status"] == "PARTIAL" and float(item["fee"]["balance"]) == 3000


def test_student_status_leaves_classes_and_keeps_records(env):
    admin = env["as_user"](env["admin"])
    student, pupil = env["student"], env["pupil"]
    url = f"/api/records/students/{student.id}/status"
    assert admin.put(url, json=dict(status="TRANSFERRED")).status_code == 422  # Needs a date.
    assert env["as_user"](env["supervisor"]).put(url, json=dict(status="TRANSFERRED", left_on=date.today().isoformat())).status_code == 403
    admin = env["as_user"](env["admin"])
    assert admin.put(url, json=dict(status="TRANSFERRED", left_on=date.today().isoformat(), note="Moved to Nakuru")).status_code == 200
    env["db"].expire_all()
    assert env["db"].get(User, pupil.id).status == UserStatus.DEACTIVATED
    assert admin.get(f"/api/teaching/classes/{env['cls'].id}/students").json() == []
    assert admin.get("/api/records/students").json()["total"] == 0
    assert admin.get("/api/records/students?status=TRANSFERRED").json()["items"][0]["status"] == "TRANSFERRED"
    assert admin.post(f"/api/teaching/classes/{env['cls'].id}/enrollments", json=dict(admission_number="A001")).status_code == 409
    assert admin.put(url, json=dict(status="ACTIVE")).status_code == 200
    env["db"].expire_all()
    assert env["db"].get(User, pupil.id).status == UserStatus.ACTIVE


def test_guardians_are_shared_by_siblings_and_visible_to_class_teacher(env):
    admin = env["as_user"](env["admin"])
    student = env["student"]
    url = f"/api/records/students/{student.id}/guardians"
    added = admin.post(url, json=dict(full_name="Jane Wanjiru", phone="0712 345 678", relationship="Mother"))
    assert added.status_code == 201, added.text
    assert added.json()["guardians"][0]["phone"] == "+254712345678"
    assert added.json()["guardians"][0]["is_primary"] is True
    assert admin.post(url, json=dict(full_name="Jane W", phone="+254712345678", relationship="Mother")).status_code == 409
    assert admin.post(url, json=dict(full_name="Bad", phone="12", relationship="Father")).status_code == 422
    assert env["as_user"](env["supervisor"]).get(url).json()[0]["full_name"] == "Jane Wanjiru"
    assert env["as_user"](env["supervisor"]).post(url, json=dict(full_name="X Y", phone="0700000001", relationship="Aunt")).status_code == 403
    assert env["as_user"](env["teacher"]).get(url).status_code == 403
    guardian_id = added.json()["guardians"][0]["id"]
    admin = env["as_user"](env["admin"])
    assert admin.delete(f"{url}/{guardian_id}").json() == []
    assert admin.get("/api/records/guardians").json()["total"] == 0


def test_discipline_records_for_admin_and_class_teacher_only(env):
    student = env["student"]
    url = f"/api/records/students/{student.id}/discipline"
    supervisor = env["as_user"](env["supervisor"])
    made = supervisor.post(url, json=dict(occurred_on=date.today().isoformat(), category="Lateness", description="Late three days running",
                                          action_taken="Spoke with the student"))
    assert made.status_code == 201, made.text
    assert env["as_user"](env["teacher"]).get(url).status_code == 403
    assert env["as_user"](env["pupil"]).get(url).status_code == 403
    assert env["as_user"](bursar(env, ("students.view",))).get(url).status_code == 403
    admin = env["as_user"](env["admin"])
    assert admin.get(url).json()[0]["category"] == "Lateness"
    future = (date.today() + timedelta(days=1)).isoformat()
    assert supervisor.post(url, json=dict(occurred_on=future, category="X1", description="Not yet")).status_code == 422
    assert admin.delete(f"/api/records/discipline/{made.json()['id']}").status_code == 200


def test_announcements_reach_the_right_people(env):
    admin = env["as_user"](env["admin"])
    cls = env["cls"]
    for audience, extra in [("EVERYONE", {}), ("STAFF", {}), ("STUDENTS", {}), ("CLASS", {"class_id": str(cls.id)})]:
        assert admin.post("/api/announcements", json=dict(title=f"For {audience}", body="Details here", audience=audience, **extra)).status_code == 201
    assert admin.post("/api/announcements", json=dict(title="Bad one", body="Details", audience="CLASS")).status_code == 422
    expired = (date.today() - timedelta(days=1)).isoformat()
    assert admin.post("/api/announcements", json=dict(title="Old news", body="Gone", audience="EVERYONE", expires_on=expired)).status_code == 201

    titles = lambda who: {a["title"] for a in env["as_user"](env[who]).get("/api/announcements").json()}
    assert titles("pupil") == {"For EVERYONE", "For STUDENTS", "For CLASS"}
    assert titles("teacher") == {"For EVERYONE", "For STAFF", "For CLASS"}
    assert titles("unrelated") == {"For EVERYONE", "For STAFF"}
    admin = env["as_user"](env["admin"])
    assert "Old news" in {a["title"] for a in admin.get("/api/announcements?include_expired=true").json()}
    assert env["as_user"](env["teacher"]).post("/api/announcements", json=dict(title="Mine", body="Nope", audience="EVERYONE")).status_code == 403
