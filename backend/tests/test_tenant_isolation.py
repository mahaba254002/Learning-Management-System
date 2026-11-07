"""Every route that takes an ID must refuse another institution's records.

The test walks the real route table, so a new route with an ID in its path is
checked automatically. Each ID parameter is filled with a record that belongs
to the second institution, and staff of the first institution make the call.
Any successful (2xx) response or server error fails the test."""
import re
import uuid
from app.models.subscription import MpesaStkRequest
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from test_teaching import env
from app.core import rate_limit as limiter
from app.main import app
from app.models.curriculum import CatalogueUnit, Department
from app.models.invitation import Invitation, InvitationRole
from app.models.learning import CourseMaterial
from app.models.management import StaffMember
from app.models.structure import AssessmentScale, CurriculumStrand, OfferingTeacher
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.timetable import LessonChange, TeacherUnavailability, TimetableEntry, TimetableSlot
from app.models.records import Announcement, DisciplineRecord, Guardian
from app.models.messaging import GuardianMessage

ALLOWED = {400, 403, 404, 405, 409, 422}
# Public invitation links are found by their secret token, not by tenant.
PUBLIC = {"/api/invitations/{token}", "/api/invitations/{token}/submit"}


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


def foreign_records(env):
    """Create one record of each kind in the second institution."""
    db, other = env["db"], env["institutions"][1].id
    department = Department(institution_id=other, code="OD", name="Other department")
    course = CatalogueUnit(institution_id=other, code="OC1", name="Other course")
    year = AcademicYear(institution_id=other, name="2030", start_date=date(2030, 1, 1), end_date=date(2030, 12, 31))
    material = CourseMaterial(institution_id=other, subject_id=env["other_subject"].id, title="Private notes")
    db.add_all([department, course, year, material])
    db.flush()
    staff = StaffMember(institution_id=other, staff_number="O-1", first_name="Other", last_name="Staff",
                        category="NON_TEACHING", job_title="Bursar", department_id=department.id)
    db.add(staff)
    db.flush()
    allocation = OfferingTeacher(institution_id=other, subject_id=env["other_subject"].id, user_id=env["outsider"].id,
                                 role="LEAD", weekly_hours=Decimal("4"))
    strand = CurriculumStrand(institution_id=other, catalogue_id=course.id, code="S1", name="Other strand")
    scale = AssessmentScale(institution_id=other, name="Other scale", kind="PERCENT")
    invitation = Invitation(institution_id=other, invited_role=InvitationRole.TEACHER, email="invitee@other.test",
                            invite_token=uuid.uuid4().hex, invited_by=env["outsider"].id,
                            expires_at=datetime.now(timezone.utc) + timedelta(days=3))
    prompt = MpesaStkRequest(institution_id=other, requested_by=env["outsider"].id, phone="254712345678", amount=100,
                             checkout_request_id="ws_CO_other")
    guardian = Guardian(institution_id=other, full_name="Other parent", phone="+254700000999")
    discipline = DisciplineRecord(institution_id=other, student_id=env["other_student"].id, occurred_on=date.today(),
                                  category="Lateness", description="Other school record", recorded_by=env["outsider"].id)
    notice = Announcement(institution_id=other, title="Other notice", body="Private", audience="EVERYONE", created_by=env["outsider"].id)
    db.add_all([allocation, invitation, strand, scale, prompt, guardian, discipline, notice])
    db.flush()
    period = AcademicPeriod(institution_id=other, year_id=year.id, name="Other term", start_date=date(2030, 1, 1), end_date=date(2030, 4, 1))
    db.add(period); db.flush()
    slot = TimetableSlot(institution_id=other, period_id=period.id, label="Lesson 1", start_time=time(8), end_time=time(8, 40))
    db.add(slot); db.flush()
    entry = TimetableEntry(institution_id=other, period_id=period.id, slot_id=slot.id, weekday=1, subject_id=env["other_subject"].id,
                           class_id=env["other_cls"].id, teacher_id=env["outsider"].id)
    away = TeacherUnavailability(institution_id=other, period_id=period.id, teacher_id=env["outsider"].id, weekday=2,
                                 start_time=time(8), end_time=time(9))
    db.add_all([entry, away]); db.flush()
    change = LessonChange(institution_id=other, entry_id=entry.id, lesson_date=date(2030, 1, 7), kind="CANCELLED", created_by=env["outsider"].id)
    db.add(change)
    message = GuardianMessage(institution_id=other, kind="ANNOUNCEMENT", title="Other notice", template="Hello", audience={}, created_by=env["outsider"].id)
    db.add(message)
    db.commit()
    return dict(
        class_id=env["other_cls"].id, subject_id=env["other_subject"].id, student_id=env["other_student"].id,
        coursework_id=env["other_work"].id, work_id=env["other_work"].id, teacher_id=env["outsider"].id,
        user_id=env["other_pupil"].id, institution_id=other, department_id=department.id, record_id=department.id,
        course_id=course.id, staff_id=staff.id, allocation_id=allocation.id, year_id=year.id,
        material_id=material.id, invitation_id=invitation.id, document_id=uuid.uuid4(),
        kind="departments", token=invitation.invite_token, strand_id=strand.id, scale_id=scale.id,
        prompt_id=prompt.id, sequence=1, transaction_id=uuid.uuid4(), secret="x" * 40,
        guardian_id=guardian.id, discipline_id=discipline.id, announcement_id=notice.id,
        period_id=period.id, slot_id=slot.id, entry_id=entry.id, unavailability_id=away.id, change_id=change.id,
        request_id=uuid.uuid4(), message_id=message.id,
    )


def id_routes():
    for route in app.routes:
        path = getattr(route, "path", "")
        if not re.search(r"{\w+}", path) or path in PUBLIC or path.startswith("/api/drafts/"):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield method, path


ROUTES = list(id_routes())


def test_route_table_is_covered():
    # Guards against the walk silently finding nothing.
    assert len(ROUTES) >= 60


@pytest.mark.parametrize("who", ["admin", "supervisor", "teacher"])
def test_staff_cannot_reach_another_institutions_records(env, who):
    ids = foreign_records(env)
    client = env["as_user"](env[who])
    failures = []
    for method, path in ROUTES:
        url = re.sub(r"{(\w+)}", lambda m: str(ids[m.group(1)]), path)
        response = client.request(method, url, json={})
        if response.status_code not in ALLOWED:
            failures.append(f"{method} {url} -> {response.status_code}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("kind,resource", [
    ("scores", "{work}"),
    ("attendance", "{cls}:" + date.today().isoformat()),
    ("assessment", "{subject}:new"),
])
def test_drafts_cannot_reference_another_institutions_records(env, kind, resource):
    ids = foreign_records(env)
    client = env["as_user"](env["admin"])
    headers = {"X-Draft-User": str(env["admin"].id), "X-Draft-Actor": str(env["admin"].id)}
    url = f"/api/drafts/{kind}/" + resource.format(work=ids["work_id"], cls=ids["class_id"], subject=ids["subject_id"])
    for method in ["GET", "PUT"]:
        response = client.request(method, url, json={"data": {}, "expected_version": 0}, headers=headers)
        assert response.status_code in {403, 404}, (method, url, response.status_code, response.text)


def test_students_cannot_reach_another_institutions_records(env):
    ids = foreign_records(env)
    client = env["as_user"](env["pupil"])
    failures = []
    for method, path in ROUTES:
        url = re.sub(r"{(\w+)}", lambda m: str(ids[m.group(1)]), path)
        response = client.request(method, url, json={})
        if response.status_code not in ALLOWED:
            failures.append(f"{method} {url} -> {response.status_code}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/institution/teachers/not-an-id"),
    ("POST", "/api/institution/invitations/not-an-id/reject"),
])
def test_malformed_ids_are_rejected_not_server_errors(env, method, path):
    assert env["as_user"](env["admin"]).request(method, path, json={}).status_code == 422
