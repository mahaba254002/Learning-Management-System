"""Deterministic fictional data. No email delivery, schema changes or destructive reset."""
import argparse
import getpass
import json
import os
import secrets
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.models import *  # registers metadata
from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
from app.models.audit import AuditEvent
from app.models.institution import Institution, InstitutionType, InstitutionStatus
from app.models.invitation import Invitation, InvitationRole, InvitationStatus
from app.models.learning import CourseMaterial, Submission
from app.models.teacher import Teacher, Gender, EmploymentType
from app.models.user import User, UserRole, UserStatus

NAMESPACE = uuid.UUID('7dab1a90-f837-486b-b174-60162e0675d4')
REVISION = 'b4d5e6f7a8c9'


def identity(key):
    return uuid.uuid5(NAMESPACE, 'rollcall-demo-v1/' + key)


def seed(db, password_hash, today, rename_existing=False):
    counts = Counter()
    accounts = []
    start = datetime.combine(today - timedelta(days=35), datetime.min.time(), tzinfo=timezone.utc)
    now = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    cache = {}
    previous_model = None
    tenant_ids = [identity(key) for key in ['acacia/institution', 'harbour/institution', 'institution/SUSPENDED', 'institution/ARCHIVED']]

    def put(model, key, **values):
        nonlocal previous_model
        if previous_model is not model:
            db.flush()
            previous_model = model
        if model not in cache:
            query = db.query(model)
            if model is Institution:
                query = query.filter(model.id.in_(tenant_ids))
            elif model is User:
                query = query.filter((model.institution_id.in_(tenant_ids)) | (model.id == identity('demo/platform')))
            else:
                query = query.filter(model.institution_id.in_(tenant_ids))
            cache[model] = {row.id: row for row in query.all()}
        row = cache[model].get(identity(key))
        if row is None:
            values.setdefault('created_at', start)
            values.setdefault('updated_at', start)
            row = model(id=identity(key), **values)
            db.add(row)
            cache[model][row.id] = row
            counts[model.__tablename__] += 1
        elif rename_existing:
            fields = {Institution: ('name', 'code', 'address', 'official_email'), AcademicClass: ('name',), Student: ('admission_number',), Invitation: ('email', 'submitted_data'), AuditEvent: ('action', 'detail')}.get(model, ())
            for field in fields:
                if field in values: setattr(row, field, values[field])
        return row

    def account(key, institution, role, first, last, status=UserStatus.ACTIVE, change=False):
        suffix = 'platform' if institution is None else institution.code
        username = f'{first.lower()}.{last.lower()}.{suffix}'.replace(' ', '.')
        if key.split('/')[-1].startswith('student'):
            username += '.' + key[-2:]
        row = put(User, key, institution_id=institution.id if institution else None, username=username,
                  first_name=first, last_name=last, email=username + '@example.test', role=role,
                  status=status, password_hash=password_hash, must_change_password=change)
        if rename_existing:
            row.username, row.email = username, username + '@example.test'
            row.first_name, row.last_name = first, last
        if row.username != username or row.email != username + '@example.test':
            raise ValueError('Seed identity conflict; use the explicit rename option for legacy seed records')
        accounts.append(dict(full_name=f'{row.first_name} {row.last_name}', username=row.username, role=row.role.value, institution=institution.code if institution else None,
                             status=row.status.value, must_change_password=row.must_change_password))
        return row

    platform = account('demo/platform', None, UserRole.PLATFORM_ADMIN, 'Nathan', 'Kimani')
    lessons = [
        ('Mathematics', 'Linear equations', 'For 3x + 5 = 20, subtract 5 from both sides, then divide by 3. The solution is x = 5. Verify: 3(5) + 5 = 20.', 'Solve 3x + 5 = 20. Explain both operations and verify your answer.', 'Subtracting 5 gives 3x = 15. Dividing by 3 gives x = 5. Substitution gives 20 = 20.'),
        ('English', 'Evidence in a paragraph', 'A clear paragraph has a topic sentence, supporting evidence and an explanation. For example, trees provide shade, reducing heat around a school playground.', 'Write a paragraph explaining one benefit of trees at school, using an example.', 'Trees make the school playground more comfortable. Their leaves shade the ground, so students can rest outdoors without standing in direct sunlight. This makes shaded areas useful during breaks.'),
        ('Science', 'Water cycle', 'Evaporation changes liquid water to vapour. Cooling causes condensation into droplets. Precipitation returns water to the surface, followed by collection and runoff.', 'Explain evaporation and condensation and name two other parts of the water cycle.', 'Evaporation changes liquid water into vapour. Condensation changes cooled vapour into droplets. Precipitation and collection complete the cycle described in the lesson.'),
    ]
    names = [('Amani', 'Otieno'), ('Zuri', 'Kamau'), ('Imani', 'Njeri'), ('Baraka', 'Mwangi'), ('Neema', 'Wanjiku'), ('Jabari', 'Kiptoo'), ('Nia', 'Achieng'), ('Kito', 'Mutua')]
    for school, school_name in [('acacia', 'Acacia Secondary School'), ('harbour', 'Harbour Academy')]:
        inst = put(Institution, f'{school}/institution', name=school_name, code=school,
                   type=InstitutionType.HIGH_SCHOOL, country='Kenya', address='School Lane, Nairobi' if school == 'acacia' else 'Harbour Road, Mombasa',
                   official_email=f'office.{school}@example.test', website=None, phone=None)
        admin = account(f'demo/{school}/admin', inst, UserRole.INSTITUTION_ADMIN, 'Miriam' if school == 'acacia' else 'David', 'Wanjiru' if school == 'acacia' else 'Odhiambo')
        teachers = []
        for i, (first, last) in enumerate([('Grace', 'Muli'), ('Daniel', 'Ouma'), ('Faith', 'Kariuki'), ('Peter', 'Kibet')]):
            user = account(f'demo/{school}/teacher{i+1}', inst, UserRole.TEACHER, first, last)
            teachers.append(user)
            put(Teacher, f'{school}/teacher-profile/{i}', institution_id=inst.id, user_id=user.id,
                gender=Gender.PREFER_NOT_TO_SAY, date_of_birth=date(1985+i, 4, 12), qualification='Bachelor of Education',
                specialization=lessons[i % 3][0], employment_type=EmploymentType.FULL_TIME)
        extra_students = []
        for suffix, status, change in [('suspended', UserStatus.SUSPENDED, False), ('firstlogin', UserStatus.ACTIVE, True)]:
            user = account(f'demo/{school}/{suffix}', inst, UserRole.STUDENT, 'Kevin' if suffix == 'suspended' else 'Sarah', 'Kilonzo' if suffix == 'suspended' else 'Chebet', status, change)
            extra_students.append(put(Student, f'{school}/special/{suffix}', institution_id=inst.id, user_id=user.id, admission_number=f'{school[:3].upper()}-{suffix.upper()}'))
        for ci in range(2):
            cls = put(AcademicClass, f'{school}/class/{ci}', institution_id=inst.id, name=f'Form {ci+1}', academic_year=str(today.year), supervisor_id=teachers[ci].id)
            if ci == 0:
                for si, student in enumerate(extra_students):
                    put(Enrollment, f'{school}/special/enrollment/{si}', institution_id=inst.id, class_id=cls.id, student_id=student.id, active=True)
            students = []
            for si, (first, last) in enumerate(names):
                key = f'{school}/class/{ci}/student/{si}'
                user = account(f'demo/{school}/student{ci*8+si+1:02}', inst, UserRole.STUDENT, first, last)
                student = put(Student, key, institution_id=inst.id, user_id=user.id, admission_number=f'{school[:3].upper()}-{ci*8+si+1:03}')
                put(Enrollment, key+'/enrollment', institution_id=inst.id, class_id=cls.id, student_id=student.id, active=si != 7)
                students.append(student)
            subjects = []
            for sj, (name, topic, lesson, question, answer) in enumerate(lessons):
                key = f'{school}/class/{ci}/subject/{sj}'
                subject = put(Subject, key, institution_id=inst.id, class_id=cls.id, name=name, teacher_id=teachers[(sj+ci) % 4].id)
                subjects.append(subject)
                put(CourseMaterial, key+'/notes', institution_id=inst.id, subject_id=subject.id, title=topic+' — lesson notes', body=lesson, published=True)
                put(CourseMaterial, key+'/practice', institution_id=inst.id, subject_id=subject.id, title=topic+' — practice guide', body=question+'\nUse the lesson notes and check each step before submitting.', published=True)
                put(CourseMaterial, key+'/draft-notes', institution_id=inst.id, subject_id=subject.id, title='Next lesson — teacher draft', body='Prepare a follow-up explanation and differentiated practice questions.', published=False)
                for kind, title, due, published, late in [
                    ('ASSIGNMENT', 'Marked practice', -10, True, True),
                    ('ASSIGNMENT', 'Open task', 7, True, True),
                    ('COURSEWORK', 'Extension task', -2, True, True),
                    ('ASSIGNMENT', 'Closed practice', -4, True, False),
                    ('EXAM', 'Class assessment', -7, True, False),
                    ('ASSIGNMENT', 'Teacher draft', 14, False, True),
                ]:
                    wk = key+'/'+title
                    work = put(Coursework, wk, institution_id=inst.id, subject_id=subject.id, title=topic+' — '+title,
                        instructions=question, kind=kind, due_at=now+timedelta(days=due, hours=14), max_score=Decimal('20'), published=published, allow_late_submissions=late)
                    for si, student in enumerate(students[:7]):
                        submitted = None
                        status = None
                        if title == 'Marked practice': status, submitted = 'SUBMITTED', now-timedelta(days=11)
                        elif title == 'Open task' and si in (0, 1): status = 'DRAFT'
                        elif title == 'Open task' and si == 2: status, submitted = 'SUBMITTED', now-timedelta(days=1)
                        elif title == 'Extension task' and si < 3: status, submitted = 'SUBMITTED', now-timedelta(days=1)
                        if status:
                            put(Submission, wk+f'/submission/{si}', institution_id=inst.id, coursework_id=work.id, student_id=student.id,
                                answer=answer if status == 'SUBMITTED' else 'Draft: '+answer[:60], status=status, submitted_at=submitted,
                                is_late=title == 'Extension task', version=1, updated_at=submitted or now-timedelta(days=1))
                        if title in ('Marked practice', 'Class assessment'):
                            mark = Decimal(14 + (si+sj) % 7)
                            put(Score, wk+f'/score/{si}', institution_id=inst.id, coursework_id=work.id, student_id=student.id, score=mark,
                                feedback='Core ideas are correct. Develop your explanation with clear steps or examples.' if mark < 20 else 'Complete and clearly explained. Well done.', updated_at=now-timedelta(days=5))
            # Last ten weekdays before today; withdrawn student has only earlier history.
            days = []
            day = today-timedelta(days=1)
            while len(days) < 10:
                if day.weekday() < 5: days.append(day)
                day -= timedelta(days=1)
            for di, day in enumerate(days):
                for si, student in enumerate(students):
                    if si == 7 and di < 5: continue
                    status = ['PRESENT']*7 + ['LATE', 'ABSENT', 'EXCUSED']
                    value = status[(si+di) % 10]
                    for subject in [None]+subjects:
                        scope = str(subject.id) if subject else 'class'
                        put(Attendance, f'{school}/class/{ci}/attendance/{di}/{si}/{scope}', institution_id=inst.id,
                            class_id=cls.id, subject_id=subject.id if subject else None, scope_key=scope, day=day,
                            student_id=student.id, status=value, note={'LATE':'Arrived after the register.', 'ABSENT':'Not present for this session.', 'EXCUSED':'Absence approved by the class supervisor.'}.get(value,''))
        for state in InvitationStatus:
            completed = state in (InvitationStatus.APPROVED, InvitationStatus.REJECTED)
            values = dict(first_name='Alice', last_name='Wambui', gender='PREFER_NOT_TO_SAY', date_of_birth='1992-05-10', qualification='Bachelor of Education', specialization='Science', employment_type='FULL_TIME')
            invite = put(Invitation, f'{school}/invitation/{state.value}', institution_id=inst.id, invited_role=InvitationRole.TEACHER,
                email=(teachers[0].email if state == InvitationStatus.APPROVED else f'alice.wambui.{school}.{state.value.lower()}@example.test'),
                invite_token=secrets.token_urlsafe(32), status=state, invited_by=admin.id,
                expires_at=now+timedelta(days=-1 if state == InvitationStatus.EXPIRED else 14),
                submitted_data=({**values, 'first_name':teachers[0].first_name, 'last_name':teachers[0].last_name} if state == InvitationStatus.APPROVED else values) if state not in (InvitationStatus.SENT, InvitationStatus.EXPIRED) else None,
                reviewed_by=admin.id if completed else None, reviewed_at=now-timedelta(days=15) if completed else None,
                created_user_id=teachers[0].id if state == InvitationStatus.APPROVED else None)
        put(AuditEvent, f'{school}/audit/seed', institution_id=inst.id, actor_id=platform.id, action='sample.seeded', target_id=str(inst.id), detail='Sample institution and academic data created. Not a historical activity log.')
    for state in [InstitutionStatus.SUSPENDED, InstitutionStatus.ARCHIVED]:
        inst = put(Institution, f'institution/{state.value}', name='Ridgeway Training Institute' if state == InstitutionStatus.SUSPENDED else 'Lakeview College', code='ridgeway' if state == InstitutionStatus.SUSPENDED else 'lakeview',
            type=InstitutionType.TRAINING_INSTITUTION, country='Kenya', status=state,
            archived_at=now-timedelta(days=1) if state == InstitutionStatus.ARCHIVED else None, archived_by=platform.id if state == InstitutionStatus.ARCHIVED else None)
        account(f'demo/{state.value.lower()}/admin', inst, UserRole.INSTITUTION_ADMIN, 'Joseph' if state == InstitutionStatus.SUSPENDED else 'Agnes', 'Kariuki' if state == InstitutionStatus.SUSPENDED else 'Naliaka')
        put(AuditEvent, f'{state.value}/audit', institution_id=inst.id, actor_id=platform.id, action='sample.seeded', target_id=str(inst.id), detail='Fictional institution lifecycle example.')
    return dict(created=dict(counts), accounts=accounts, seed_version=1, reference_date=today.isoformat())


def account_keys():
    keys = ['demo/platform', 'demo/suspended/admin', 'demo/archived/admin']
    for school in ('acacia', 'harbour'):
        keys += [f'demo/{school}/{suffix}' for suffix in ['admin', 'suspended', 'firstlogin']]
        keys += [f'demo/{school}/teacher{i}' for i in range(1,5)]
        keys += [f'demo/{school}/student{i:02}' for i in range(1,17)]
    return keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--rename-existing', action='store_true', help='Update names only on generator-owned legacy records')
    parser.add_argument('--apply', action='store_true', help='Commit; otherwise validate and roll back')
    parser.add_argument('--date', type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument('--password', action='store_true', help='Prompt privately for the initial demo password')
    parser.add_argument('--set-demo-password', action='store_true', help='Only reset known demo accounts, using a private prompt')
    args = parser.parse_args()
    raw = os.environ.get('SEED_DATABASE_URL')
    if not raw: raise ValueError('Set SEED_DATABASE_URL explicitly. Local env files are not read.')
    url = make_url(raw)
    if url.host != args.expected_host or '-pooler' in (url.host or ''): raise ValueError('Expected direct host does not match')
    os.environ['DATABASE_URL'] = raw
    os.environ.setdefault('JWT_SECRET_KEY', 'seed-tool-does-not-issue-tokens')
    from app.core.security import hash_password
    from app.core.password_policy import validate_password_policy
    password = getpass.getpass('Demo password: ') if args.password or args.set_demo_password else secrets.token_urlsafe(32)+'aA1!'
    validate_password_policy(password)
    hashed = hash_password(password)
    engine = create_engine(url, connect_args={'connect_timeout':15})
    with Session(engine) as db:
        db.execute(text('SELECT pg_advisory_xact_lock(73140926)'))
        if db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() != REVISION:
            raise ValueError('Apply the reviewed migrations before seeding')
        if args.set_demo_password:
            # UUID and username must both belong to this generator, not just a loose prefix.
            selected = db.query(User).filter(User.id.in_([identity(key) for key in account_keys()])).all()
            for user in selected:
                user.password_hash = hashed
                user.password_changed_at = datetime.now(timezone.utc)
            result = {'demo_passwords_updated':len(selected)}
        else:
            result = seed(db, hashed, args.date, rename_existing=args.rename_existing)
        if args.apply: db.commit()
        else: db.rollback()
        print(json.dumps(dict(result, committed=args.apply), indent=2))
    engine.dispose()


if __name__ == '__main__':
    try: main()
    except Exception as error:
        # Database exception strings may include connection details or row values.
        print(f'Seed failed ({type(error).__name__}); transaction was not committed.', file=sys.stderr)
        raise SystemExit(1)
