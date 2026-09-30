"""HTTP-level permissions and persistence checks. Never reads the development .env."""
import os
import uuid
from datetime import date, timedelta

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "isolated-test-only-key-not-a-live-credential"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.institution import Institution, InstitutionType
from app.models.teacher import Teacher, Gender, EmploymentType, TeacherStatus
from app.models.user import User, UserRole


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    institutions = [Institution(name=f"School {n}", code=f"S{n}", type=InstitutionType.HIGH_SCHOOL, country="Kenya") for n in range(2)]
    db.add_all(institutions)
    db.flush()

    def user(name, role=UserRole.TEACHER, tenant=0):
        row = User(institution_id=institutions[tenant].id, username=name, first_name=name, last_name="Test", email=f"{name}@example.test",
                   role=role, password_hash="unused-test-hash", must_change_password=False)
        db.add(row)
        db.flush()
        if role == UserRole.TEACHER:
            db.add(Teacher(institution_id=row.institution_id, user_id=row.id, gender=Gender.OTHER,
                           date_of_birth=date(1990, 1, 1), qualification="Test", employment_type=EmploymentType.FULL_TIME))
        return row

    supervisor, teacher, unrelated, outsider = user("supervisor"), user("teacher"), user("unrelated"), user("outsider", tenant=1)
    admin = user("admin", UserRole.INSTITUTION_ADMIN)
    pupil, other_pupil = user("pupil", UserRole.STUDENT), user("otherpupil", UserRole.STUDENT, tenant=1)
    cls = AcademicClass(institution_id=institutions[0].id, name="Form 1", academic_year="2026", supervisor_id=supervisor.id)
    other_cls = AcademicClass(institution_id=institutions[1].id, name="Private class", academic_year="2026", supervisor_id=outsider.id)
    db.add_all([cls, other_cls]); db.flush()
    subject = Subject(institution_id=institutions[0].id, class_id=cls.id, name="Math", teacher_id=teacher.id)
    other_subject = Subject(institution_id=institutions[1].id, class_id=other_cls.id, name="Science", teacher_id=outsider.id)
    student = Student(institution_id=institutions[0].id, user_id=pupil.id, admission_number="A001")
    other_student = Student(institution_id=institutions[1].id, user_id=other_pupil.id, admission_number="B001")
    db.add_all([subject, other_subject, student, other_student]); db.flush()
    db.add_all([Enrollment(institution_id=cls.institution_id, class_id=cls.id, student_id=student.id),
                Enrollment(institution_id=other_cls.institution_id, class_id=other_cls.id, student_id=other_student.id)])
    work = Coursework(institution_id=cls.institution_id, subject_id=subject.id, title="Algebra", instructions="Solve the problems", max_score=20, published=False)
    other_work = Coursework(institution_id=other_cls.institution_id, subject_id=other_subject.id, title="Private work", instructions="Private", max_score=20)
    db.add_all([work, other_work]); db.commit()
    def session():
        yield db
    app.dependency_overrides[get_db] = session
    client = TestClient(app)
    def as_user(who):
        client.cookies.clear()
        client.cookies.set("access_token", create_access_token(user_id=who.id, institution_id=who.institution_id, role=who.role.value))
        client.cookies.set("csrf_token", "isolated-test-csrf")
        client.headers["X-CSRF-Token"] = "isolated-test-csrf"
        return client
    yield locals()
    client.close()
    app.dependency_overrides.clear()
    db.close(); engine.dispose()


def path(env, suffix="students", other=False):
    return f"/api/teaching/classes/{env['other_cls' if other else 'cls'].id}/{suffix}"


def test_only_assigned_classes_subjects_and_own_profile(env):
    c = env["as_user"](env["teacher"])
    assert [r["id"] for r in c.get("/api/teaching/classes").json()] == [str(env["cls"].id)]
    assert len(c.get("/api/teaching/subjects").json()) == 1
    assert c.get("/api/teacher/profile").json()["user_id"] == str(env["teacher"].id)
    assert c.get(path(env)).status_code == 200
    assert c.get(path(env, other=True)).status_code == 404
    assert env["as_user"](env["unrelated"]).get("/api/teaching/classes").json() == []


@pytest.mark.parametrize("who", ["unrelated", "outsider"])
def test_unassigned_teachers_cannot_read_or_edit_students(env, who):
    c = env["as_user"](env[who])
    assert c.get(path(env)).status_code == 404
    assert c.put(path(env) + f"/{env['student'].id}", json={"first_name": "Changed", "last_name": "Name"}).status_code == 404


def test_supervisor_can_edit_names_but_not_security_fields(env):
    c = env["as_user"](env["supervisor"])
    url = path(env) + f"/{env['student'].id}"
    assert c.put(url, json={"first_name": "New", "last_name": "Name", "phone": "123"}).status_code == 200
    assert c.get(path(env)).json()[0]["first_name"] == "New"
    assert c.put(url, json={"first_name": "New", "last_name": "Name", "role": "TEACHER"}).status_code == 422
    assert env["as_user"](env["teacher"]).put(url, json={"first_name": "X", "last_name": "Y"}).status_code == 404


def test_enrollment_removal_preserves_history_and_can_be_reversed(env):
    c = env["as_user"](env["supervisor"])
    entries = [{"student_id": str(env["student"].id), "status": "LATE"}]
    assert c.put(path(env, "attendance"), json={"day": str(date.today()), "entries": entries}).status_code == 200
    assert c.delete(path(env, f"enrollments/{env['student'].id}")).status_code == 200
    assert c.get(path(env)).json() == []
    assert env["db"].query(Attendance).count() == 1
    assert c.post(path(env, "enrollments"), json={"admission_number": "B001"}).status_code == 404
    assert c.post(path(env, "enrollments"), json={"admission_number": "A001"}).status_code == 200
    assert len(c.get(path(env)).json()) == 1


def test_only_admin_can_assign_classes_and_teachers(env):
    body = {"name": "Form 2", "academic_year": "2026", "supervisor_id": str(env["teacher"].id)}
    assert env["as_user"](env["teacher"]).post("/api/teaching/classes", json=body).status_code == 403
    c = env["as_user"](env["admin"])
    assert c.post("/api/teaching/classes", json={**body, "supervisor_id": str(env["outsider"].id)}).status_code == 404
    assert c.post("/api/teaching/classes", json=body).status_code == 201
    assert c.post(path(env, "subjects"), json={"name": "English", "teacher_id": str(env["pupil"].id)}).status_code == 404


def test_student_creation_creates_forced_change_account(env):
    c = env["as_user"](env["supervisor"])
    result = c.post(path(env), json={"first_name": "New", "last_name": "Student", "email": "new@example.test", "admission_number": "A002"})
    assert result.status_code == 201
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["temporary_password"]
    account = env["db"].query(User).filter(User.username == result.json()["username"]).one()
    assert account.must_change_password and account.role == UserRole.STUDENT
    assert account.institution_id == env["cls"].institution_id
    assert len(c.get(path(env)).json()) == 2


def test_attendance_scopes_idempotence_and_cross_tenant_rejection(env):
    c = env["as_user"](env["teacher"])
    body = {"day": str(date.today()), "subject_id": str(env["subject"].id), "entries": [{"student_id": str(env["student"].id), "status": "PRESENT"}]}
    assert c.put(path(env, "attendance"), json={**body, "subject_id": None}).status_code == 404
    assert c.put(path(env, "attendance"), json=body).status_code == 200
    body["entries"][0]["status"] = "ABSENT"
    assert c.put(path(env, "attendance"), json=body).status_code == 200
    assert env["db"].query(Attendance).count() == 1
    assert c.get(path(env, f"attendance?day={date.today()}&subject_id={env['subject'].id}")).json()[0]["status"] == "ABSENT"
    body["entries"].append({"student_id": str(env["other_student"].id), "status": "PRESENT"})
    assert c.put(path(env, "attendance"), json=body).status_code == 404
    assert env["db"].query(Attendance).count() == 1


@pytest.mark.parametrize("change,code", [({"day": str(date.today() + timedelta(days=1))}, 400), ({"entries": []}, 422), ({"institution_id": str(uuid.uuid4())}, 422)])
def test_invalid_attendance_is_rejected(env, change, code):
    body = {"day": str(date.today()), "entries": [{"student_id": str(env["student"].id), "status": "PRESENT"}], **change}
    assert env["as_user"](env["supervisor"]).put(path(env, "attendance"), json=body).status_code == code
    assert env["db"].query(Attendance).count() == 0


@pytest.mark.parametrize("who", ["supervisor", "unrelated", "outsider"])
def test_supervision_does_not_grant_subject_coursework_or_scores(env, who):
    c = env["as_user"](env[who])
    assert c.get(f"/api/teaching/subjects/{env['subject'].id}/coursework").status_code == 404
    assert c.get(f"/api/teaching/coursework/{env['work'].id}/scores").status_code == 404
    assert c.put(f"/api/teaching/coursework/{env['work'].id}/scores", json={"entries": [{"student_id": str(env['student'].id), "score": 5}]}).status_code == 404


def test_scores_bounds_zero_atomicity_and_persistence(env):
    c = env["as_user"](env["teacher"])
    url = f"/api/teaching/coursework/{env['work'].id}/scores"
    def mark(score):
        return {"entries": [{"student_id": str(env["student"].id), "score": score}]}
    assert c.put(url, json=mark(21)).status_code == 400
    assert c.put(url, json=mark(-1)).status_code == 422
    assert c.put(url, json=mark(0)).status_code == 200
    assert c.get(url).json()[0]["score"] == 0
    assert c.put(url, json=mark(15)).status_code == 200
    assert env["db"].query(Score).count() == 1
    invalid_batch = mark(19)
    invalid_batch["entries"].append({"student_id": str(env["other_student"].id), "score": 10})
    assert c.put(url, json=invalid_batch).status_code == 404
    assert c.get(url).json()[0]["score"] == 15


def test_coursework_publication_and_student_score_privacy(env):
    student_client = env["as_user"](env["pupil"])
    assert student_client.get("/api/student/coursework").json() == []
    c = env["as_user"](env["teacher"])
    url = f"/api/teaching/coursework/{env['work'].id}"
    body = {"title": "Published algebra", "instructions": "Solve these", "max_score": 20, "published": True}
    assert c.put(url, json=body).status_code == 200
    assert c.put(url + "/scores", json={"entries": [{"student_id": str(env["student"].id), "score": 18, "feedback": "Good work"}]}).status_code == 200
    assert c.put(url, json={**body, "max_score": 10}).status_code == 400
    published = env["as_user"](env["pupil"]).get("/api/student/coursework").json()
    assert len(published) == 1 and published[0]["score"] == 18
    assert env["as_user"](env["other_pupil"]).get("/api/student/coursework").json() == []


def test_auth_role_csrf_and_forced_change_still_apply(env):
    c = env["client"]
    assert c.get("/api/teaching/classes").status_code == 401
    assert env["as_user"](env["pupil"]).get("/api/teaching/classes").status_code == 403
    c = env["as_user"](env["teacher"])
    c.headers.pop("X-CSRF-Token")
    assert c.post("/api/teaching/classes", json={"name": "No", "academic_year": "2026"}).status_code == 403
    env["teacher"].must_change_password = True; env["db"].commit()
    assert c.get("/api/teaching/classes").status_code == 403


def test_inactive_teacher_loses_teaching_access(env):
    row = env["db"].query(Teacher).filter(Teacher.user_id == env["teacher"].id).one()
    row.status = TeacherStatus.SUSPENDED; env["db"].commit()
    assert env["as_user"](env["teacher"]).get("/api/teaching/classes").status_code == 404


def test_database_rejects_cross_tenant_enrollment_even_outside_api(env):
    db = env["db"]
    db.add(Enrollment(institution_id=env["cls"].institution_id, class_id=env["cls"].id, student_id=env["other_student"].id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_coursework_create_edit_and_tenant_id_injection(env):
    c = env["as_user"](env["teacher"])
    url = f"/api/teaching/subjects/{env['subject'].id}/coursework"
    body = {"title": "Homework", "instructions": "Read chapter one", "max_score": 10, "kind": "COURSEWORK"}
    assert c.post(url, json={**body, "institution_id": str(env["other_cls"].institution_id)}).status_code == 422
    created = c.post(url, json=body)
    assert created.status_code == 201 and created.json()["published"] is False
    work_url = f"/api/teaching/coursework/{created.json()['id']}"
    assert c.put(work_url, json={**body, "title": "Revised homework"}).status_code == 200
    assert any(w["title"] == "Revised homework" for w in c.get(url).json())


def test_removed_students_cannot_be_graded_or_see_published_work(env):
    env["work"].published = True
    env["db"].commit()
    c = env["as_user"](env["supervisor"])
    assert c.delete(path(env, f"enrollments/{env['student'].id}")).status_code == 200
    c = env["as_user"](env["teacher"])
    assert c.put(f"/api/teaching/coursework/{env['work'].id}/scores", json={"entries": [{"student_id": str(env['student'].id), "score": 5}]}).status_code == 404
    assert env["as_user"](env["pupil"]).get("/api/student/coursework").json() == []


def test_duplicate_register_and_score_entries_rejected(env):
    c = env["as_user"](env["teacher"])
    attendance_entry = {"student_id": str(env["student"].id), "status": "PRESENT"}
    assert c.put(path(env, "attendance"), json={"day": str(date.today()), "subject_id": str(env["subject"].id), "entries": [attendance_entry, attendance_entry]}).status_code == 422
    score_entry = {"student_id": str(env["student"].id), "score": 5}
    assert c.put(f"/api/teaching/coursework/{env['work'].id}/scores", json={"entries": [score_entry, score_entry]}).status_code == 422


def test_foreign_and_missing_records_have_identical_errors(env):
    c = env["as_user"](env["teacher"])
    foreign = c.get(path(env, other=True))
    absent = c.get(f"/api/teaching/classes/{uuid.uuid4()}/students")
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json() == absent.json()
