"""Phase 7: own grading set once then by approved request, mark uploads, and Excel marksheets."""
import io
from datetime import date, timedelta
from decimal import Decimal

import pytest
from openpyxl import Workbook, load_workbook

from test_teaching import env  # noqa: F401
from test_workspace_access import platform
from app.core import rate_limit as limiter
from app.models.academic import Coursework, Enrollment, Score, Student, Subject
from app.models.pilot import AcademicPeriod, AcademicYear
from app.models.structure import OfferingTeacher
from app.models.user import User, UserRole

BANDS = [dict(minimum=80, label="A", points=12), dict(minimum=70, label="B+", points=9), dict(minimum=60, label="B", points=8),
         dict(minimum=50, label="C", points=6), dict(minimum=0, label="E", points=1)]
RULES = dict(enabled=True, name="School grading", aggregation="CATEGORY_WEIGHTS", weights=dict(ASSIGNMENT=0, COURSEWORK=30, EXAM=70),
             pass_percentage=50, bands=BANDS)


@pytest.fixture(autouse=True)
def rate_stub(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, "incr", lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, "expire", lambda *args: True)


@pytest.fixture
def school(env):
    db, tenant = env["db"], env["institutions"][0].id
    today = date.today()
    year = AcademicYear(institution_id=tenant, name="2026", start_date=today - timedelta(days=200), end_date=today + timedelta(days=100), status="ACTIVE")
    db.add(year); db.flush()
    term = AcademicPeriod(institution_id=tenant, year_id=year.id, name="Term 3", start_date=today - timedelta(days=30), end_date=today + timedelta(days=60))
    english = Subject(institution_id=tenant, class_id=env["cls"].id, name="English", teacher_id=env["supervisor"].id)
    db.add_all([term, english]); db.flush()
    db.add(OfferingTeacher(institution_id=tenant, subject_id=english.id, user_id=env["supervisor"].id, role="LEAD"))
    pupils = [env["student"]]
    for n, first in enumerate(["=cmd", "Faith"], start=2):
        user = User(institution_id=tenant, username=f"p{n}", first_name=first, last_name="Pupil", email=f"p{n}@example.test",
                    role=UserRole.STUDENT, password_hash="x", must_change_password=False)
        db.add(user); db.flush()
        student = Student(institution_id=tenant, user_id=user.id, admission_number=f"A00{n}")
        db.add(student); db.flush()
        db.add(Enrollment(institution_id=tenant, class_id=env["cls"].id, student_id=student.id))
        pupils.append(student)
    db.commit()
    return dict(term=term, english=english, pupils=pupils)


def admin(env):
    return env["as_user"](env["admin"])


def test_grading_is_set_once_then_changed_only_by_approved_request(env):
    response = admin(env).get("/api/institution/grading").json()
    assert response["locked"] is False
    assert env["as_user"](env["teacher"]).put("/api/institution/grading", json=dict(rules=RULES)).status_code == 403
    saved = admin(env).put("/api/institution/grading", json=dict(rules=RULES))
    assert saved.status_code == 200, saved.text
    assert saved.json()["locked"] is True and saved.json()["rules"]["weights"]["EXAM"] == 70
    assert admin(env).put("/api/institution/grading", json=dict(rules=RULES)).status_code == 409

    new_rules = {**RULES, "pass_percentage": 40}
    assert admin(env).post("/api/institution/grading/requests", json=dict(rules=new_rules, reason="short")).status_code == 422
    request = admin(env).post("/api/institution/grading/requests", json=dict(rules=new_rules, reason="Board moved the pass mark to 40%"))
    assert request.status_code == 201
    assert admin(env).post("/api/institution/grading/requests", json=dict(rules=new_rules, reason="A second request now")).status_code == 409
    owner = env["as_user"](platform(env))
    pending = owner.get("/api/platform/grading-requests").json()
    assert pending[0]["institution_name"] == "School 0"
    assert owner.post(f"/api/platform/grading-requests/{pending[0]['id']}/decide", json=dict(approve=False)).status_code == 422
    assert owner.post(f"/api/platform/grading-requests/{pending[0]['id']}/decide", json=dict(approve=True)).status_code == 200
    assert admin(env).get("/api/institution/grading").json()["rules"]["pass_percentage"] == 40
    # Invalid combinations are refused before they reach the platform queue.
    gpa = {**RULES, "gpa_enabled": True}
    assert admin(env).post("/api/institution/grading/requests", json=dict(rules=gpa, reason="We would like GPA as well")).status_code == 422


def test_upload_marks_for_one_assessment(env, school):
    teacher = env["as_user"](env["teacher"])
    work = teacher.post(f"/api/teaching/subjects/{env['subject'].id}/coursework",
                        json=dict(title="CAT 1", instructions="Test", kind="COURSEWORK", max_score="30", published=True, period_id=str(school["term"].id)))
    assert work.status_code == 201, work.text
    url = f"/api/marks/coursework/{work.json()['id']}/import"
    header = ["Adm No", "Name", "Mark", "Comment"]
    rows = [["a001", "Pupil", "25", "Good"], ["A002", "x", "31", ""], ["Z9", "x", "10", ""], ["A003", "x", "", ""]]
    preview = teacher.post(url, json=dict(header=header, rows=rows)).json()
    assert preview["errors"] == 2 and preview["to_save"] == 1
    assert [r["status"] for r in preview["rows"]] == ["NEW", "ERROR", "ERROR", "SKIPPED"]
    assert teacher.post(url, json=dict(header=header, rows=rows, commit=True)).status_code == 422
    saved = teacher.post(url, json=dict(header=header, rows=[rows[0], rows[3]], commit=True)).json()
    assert saved["saved"] and saved["to_save"] == 1
    assert env["db"].query(Score).filter_by(student_id=env["student"].id).one().score == Decimal("25")
    # Someone who does not teach the subject cannot upload.
    assert env["as_user"](env["unrelated"]).post(url, json=dict(header=header, rows=rows)).status_code == 404


def test_upload_a_class_marksheet_for_one_exam(env, school):
    supervisor = env["as_user"](env["supervisor"])
    url = f"/api/marks/classes/{env['cls'].id}/exam-import"
    header = ["admission_number", "Name", "math", "English", "Total"]
    rows = [["A001", "Pupil", "78", "64", "142"], ["A002", "", "55", "ABS", ""], ["A003", "", "120", "40", ""]]
    body = dict(period_id=str(school["term"].id), title="End of term exam", header=header, rows=rows)
    preview = supervisor.post(url, json=body).json()
    assert preview["ignored_columns"] == ["Name", "Total"]
    assert {s["subject"] for s in preview["subjects"]} == {"Math", "English"}
    assert preview["errors"] == 1  # 120 is above 100.
    body["rows"] = rows[:2]
    saved = supervisor.post(url, json={**body, "commit": True})
    assert saved.status_code == 200, saved.text
    exams = env["db"].query(Coursework).filter_by(title="End of term exam").all()
    assert len(exams) == 2 and all(w.published and w.kind == "EXAM" and w.period_id == school["term"].id for w in exams)
    assert env["db"].query(Score).count() == 3
    # Uploading the same file again changes nothing; subject teachers cannot upload the whole class.
    again = supervisor.post(url, json=body).json()
    assert again["to_save"] == 0
    assert env["as_user"](env["teacher"]).post(url, json=body).status_code == 404


def test_marksheet_means_grades_positions_and_excel(env, school):
    admin(env).put("/api/institution/grading", json=dict(rules={**RULES, "aggregation": "POINTS"}))
    supervisor = env["as_user"](env["supervisor"])
    header = ["admission_number", "Math", "English"]
    rows = [["A001", "85", "75"], ["A002", "65", "55"], ["A003", "85", "75"]]
    supervisor.post(f"/api/marks/classes/{env['cls'].id}/exam-import",
                    json=dict(period_id=str(school["term"].id), title="Mid term", header=header, rows=rows, commit=True))
    sheet = supervisor.get(f"/api/marks/classes/{env['cls'].id}/marksheet").json()
    assert sheet["period_name"] == "Term 3" and sheet["exam_titles"] == ["Mid term"]
    by_adm = {r["admission_number"]: r for r in sheet["rows"]}
    first = by_adm["A001"]
    assert first["cells"][str(env["subject"].id)]["grade"] == "A"
    assert (Decimal(first["mean"]), first["mean_grade"], first["position"]) == (Decimal("80.00"), "A", 1)  # Mean points 10.5 rounds to 11; the nearest band is A (12).
    # Equal results share a position; the next one skips.
    assert by_adm["A003"]["position"] == 1 and by_adm["A002"]["position"] == 3
    assert sheet["ranked_by"] == "MEAN_POINTS"
    math = next(a for a in sheet["analysis"] if a["subject"] == "Math")
    assert (math["entries"], Decimal(math["highest"]), math["grades"]) == (3, Decimal("85.00"), {"A": 2, "B": 1})

    exam = supervisor.get(f"/api/marks/classes/{env['cls'].id}/marksheet?exam=Mid%20term&download=true")
    assert exam.status_code == 200 and exam.headers["content-type"].startswith("application/vnd.openxmlformats")
    book = load_workbook(io.BytesIO(exam.content))
    assert book.sheetnames[1:] == ["English", "Math", "Subject analysis"]
    names = [row[2] for row in book.worksheets[0].iter_rows(min_row=2, values_only=True)]
    assert "'=cmd Pupil" in names  # A name that looks like a formula stays text.
    # Subject teacher: class sheet refused, own subject allowed.
    teacher = env["as_user"](env["teacher"])
    assert teacher.get(f"/api/marks/classes/{env['cls'].id}/marksheet").status_code == 404
    own = teacher.get(f"/api/marks/subjects/{env['subject'].id}/marksheet").json()
    assert [s["name"] for s in own["subjects"]] == ["Math"]


def test_reading_csv_and_excel_uploads_and_templates(env, school):
    supervisor = env["as_user"](env["supervisor"])
    csv_rows = supervisor.post("/api/marks/parse?filename=marks.csv", content="admission_number,Math\r\nA001,70\r\n".encode()).json()
    assert csv_rows == dict(header=["admission_number", "Math"], rows=[["A001", "70"]])
    book = Workbook()
    book.active.append(["admission_number", "Math", "Total"])
    book.active.append(["A001", 70, "=B2"])
    out = io.BytesIO(); book.save(out)
    parsed = supervisor.post("/api/marks/parse?filename=marks.xlsx", content=out.getvalue()).json()
    assert parsed["rows"][0][:2] == ["A001", "70"]  # Formulas are not evaluated.
    assert supervisor.post("/api/marks/parse?filename=marks.txt", content=b"x").status_code == 422
    template = supervisor.get(f"/api/marks/classes/{env['cls'].id}/template")
    sheet = load_workbook(io.BytesIO(template.content)).active
    assert [c.value for c in sheet[1]] == ["admission_number", "name", "English", "Math"]
    assert env["as_user"](env["pupil"]).post("/api/marks/parse?filename=m.csv", content=b"a,b\n1,2\n").status_code == 403


def test_report_cards_are_off_until_the_platform_turns_them_on(env):
    assert admin(env).get("/api/academic-documents/options").status_code == 403
    modules = admin(env).get("/api/institution/modules").json()["modules"]
    assert modules["academic_reports"] is False and modules["assessments"] is True
