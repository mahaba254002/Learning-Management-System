"""Wipe every institution and load three fictional but realistic institutions.

Requested by the owner on 2026-11-07: delete all data (no backup), keep the
platform admin sign-in, and load one comprehensive school (PP1 to Form 4), one
TVET college and one university. Names of institutions and people are invented;
email addresses route to the owner's own inbox with Gmail plus-addressing, so no
stranger ever receives mail. Guardian phone numbers are invented too; schools
start with an SMS allowance of 0, so no SMS can go to them.

Default run rehearses and rolls back. --apply commits. Production also needs
--confirm "DELETE ALL PRODUCTION DATA". Logins go to --credentials (keep private).
"""
import argparse
import json
import random
import re
import secrets
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TODAY = date(2026, 11, 7)
NOW = datetime.now(timezone.utc)
CONFIRM = 'DELETE ALL PRODUCTION DATA'
rng = random.Random(20261107)


def wipe(db, keep_ids):
    """Remove every institution with the tested purge, then everything not tied to a kept platform admin."""
    from sqlalchemy import text
    from app.db.base import Base
    from app.models.institution import Institution
    from app.models.user import User, UserRole
    from app.services.lifecycle import purge_institution
    files = []
    for inst in db.query(Institution).all():
        _, keys = purge_institution(db, inst)
        files += keys
    leftovers = db.query(User).filter(User.role != UserRole.PLATFORM_ADMIN).count()
    assert leftovers == 0, f'{leftovers} non-platform accounts survived the purge'
    # Platform-level history goes too, except the built-in grading scales and the kept admins.
    for table in ('audit_events', 'mpesa_transactions', 'payment_messages', 'email_failures', 'grading_change_requests'):
        if table in Base.metadata.tables:
            db.execute(text(f'DELETE FROM {table}'))
    db.execute(text('DELETE FROM verification_codes'))
    db.execute(text("DELETE FROM assessment_scales WHERE institution_id IS NOT NULL"))
    return files


class Seeder:
    def __init__(self, db, inbox, owner):
        self.db, self.owner, self.accounts = db, owner, []
        local, domain = inbox.lower().split('@')
        assert domain == 'gmail.com' and '+' not in local, 'Use a plain Gmail address you control'
        self.local, self.domain = local, domain
        from app.models.structure import AssessmentScale
        self.scales = {s.code: s for s in db.query(AssessmentScale).filter(AssessmentScale.institution_id.is_(None)).all()}
        assert {'CBE_4', 'CBE_8', 'LETTER_A_E', 'TVET_COMPETENCE'} <= set(self.scales), 'Built-in scales missing'

    def email(self, alias):
        return f'{self.local}+{alias}@{self.domain}'

    def add(self, row):
        self.db.add(row)
        return row

    def account(self, inst, code, first, last, role, *, login_id=None, title=''):
        from app.core.security import hash_password
        from app.models.user import User, UserStatus
        password = f'{secrets.token_urlsafe(9)}-{rng.randint(10, 99)}aA'
        alias = re.sub(r'[^a-z0-9.]', '', f'{first}.{last}'.lower())
        user = self.add(User(institution_id=inst.id, username=f'{alias}.{code.lower()}', first_name=first, last_name=last,
                             email=self.email(f'{alias}.{code.lower()}'), role=role, status=UserStatus.ACTIVE,
                             password_hash=hash_password(password), must_change_password=False,
                             student_login_method='STUDENT_ID' if login_id else 'EMAIL', student_login_id=login_id))
        self.accounts.append(dict(institution=inst.name, role=role.value, title=title, name=f'{first} {last}', username=user.username,
                                  sign_in_with=login_id or user.email, portal=PORTALS[role.value], password=password))
        return user


PORTALS = {'INSTITUTION_ADMIN': 'Admin login', 'TEACHER': 'Teacher or staff login', 'STAFF': 'Teacher or staff login',
           'STUDENT': 'Student login', 'PLATFORM_ADMIN': 'Admin login'}

FIRST_F = ['Wanjiru', 'Achieng', 'Njeri', 'Chebet', 'Wambui', 'Akinyi', 'Mumbua', 'Nafula', 'Jepkosgei', 'Kerubo', 'Atieno', 'Nyambura', 'Moraa',
           'Wairimu', 'Makena', 'Nekesa', 'Adhiambo', 'Wanjala', 'Muthoni', 'Kagendo', 'Halima', 'Zawadi', 'Neema', 'Imani', 'Amani']
FIRST_M = ['Kamau', 'Otieno', 'Kipchoge', 'Mutua', 'Omondi', 'Kiprotich', 'Wafula', 'Njoroge', 'Ouma', 'Kibet', 'Mwangi', 'Odhiambo', 'Barasa',
           'Kiptoo', 'Mugo', 'Onyango', 'Juma', 'Baraka', 'Brian', 'Kevin', 'Dennis', 'Ian', 'Collins', 'Hassan', 'Abdi']
LAST = ['Kamau', 'Otieno', 'Wanjiku', 'Mutua', 'Ochieng', 'Kiprono', 'Wekesa', 'Njoroge', 'Ouma', 'Cheruiyot', 'Mwangi', 'Odhiambo', 'Barasa',
        'Koech', 'Mugo', 'Onyango', 'Kariuki', 'Muriuki', 'Gitau', 'Nyaga', 'Rotich', 'Kimani', 'Maina', 'Owino', 'Langat', 'Ndungu', 'Achola',
        'Wambua', 'Kilonzo', 'Musyoka', 'Mbugua', 'Karanja', 'Chege', 'Macharia', 'Ruto', 'Kemboi', 'Simiyu', 'Wanyama', 'Okoth', 'Abdullahi']
used_names = set()


def person(female=None):
    for _ in range(500):
        f = rng.random() < 0.5 if female is None else female
        first, last = rng.choice(FIRST_F if f else FIRST_M), rng.choice(LAST)
        if first != last and (first, last) not in used_names:
            used_names.add((first, last))
            return first, last, 'FEMALE' if f else 'MALE'
    raise RuntimeError('ran out of names')


def phone():
    return f'+2547{rng.randint(10, 99)}{rng.randint(100000, 999999)}'


def weekdays_back(n, until):
    days, d = [], until
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)


def build_institution(s, spec):
    """Create one institution from a spec dict. Returns a summary."""
    from app.models.academic import AcademicClass, Attendance, Coursework, Enrollment, Score, Student, Subject
    from app.models.curriculum import CatalogueUnit, CourseRegistration, Department, Programme, StudyLevel
    from app.models.elearning import QuizQuestion, QuizSettings, RegistrationWindow
    from app.models.institution import Institution, InstitutionStatus, InstitutionType
    from app.models.learning import CourseMaterial, Submission
    from app.models.management import StaffMember
    from app.models.pilot import AcademicPeriod, AcademicYear
    from app.models.records import Announcement, FeeStatus, Guardian, StudentGuardian
    from app.models.structure import InstitutionLevel, OfferingTeacher, ScaleLevel, StaffPermission
    from app.models.subscription import Subscription
    from app.models.timetable import TimetableEntry, TimetableSlot, TimetableTerm
    from app.models.user import UserRole
    from app.services.academic_configuration import AcademicConfiguration, template
    db, code = s.db, spec['code']

    config = template(spec['type'])
    config.update(spec.get('config', {}))
    config = AcademicConfiguration.model_validate(config).model_dump()
    inst = s.add(Institution(id=uuid.uuid4(), name=spec['name'], code=code, type=InstitutionType[spec['type']], status=InstitutionStatus.ACTIVE,
                             country='Kenya', address=spec['address'], official_email=s.email(f'office.{code.lower()}'), phone=spec['phone'],
                             website=None, academic_configuration=config, learning_settings=spec.get('learning', {}),
                             grading_locked_at=NOW if config['grading_rules']['enabled'] else None))
    db.flush()
    s.add(Subscription(institution_id=inst.id, monthly_fee=Decimal(spec['fee']), next_due_date=TODAY + timedelta(days=24),
                       enforcement_enabled=False, manually_frozen=False, support_email=s.email('billing'), credit_balance=Decimal(0)))

    levels = {}
    for key, (level, structure, kind, scale) in spec['levels'].items():
        levels[key] = s.add(InstitutionLevel(id=uuid.uuid4(), institution_id=inst.id, level=level, structure=structure, period_kind=kind,
                                             terminology={}, scale_id=s.scales[scale].id if scale else None, active=True))
    db.flush()

    # People: an admin, teaching staff, non-teaching staff.
    admin_first, admin_last, admin_gender = spec['admin']
    used_names.add((admin_first, admin_last))
    admin = s.account(inst, code, admin_first, admin_last, UserRole.INSTITUTION_ADMIN, title=spec['admin_title'])
    departments = {}
    for dcode, (dname, kind, parent) in spec['departments'].items():
        departments[dcode] = s.add(Department(id=uuid.uuid4(), institution_id=inst.id, code=dcode, name=dname, kind=kind,
                                              parent_id=departments[parent].id if parent else None))
        db.flush()
    teachers = {}
    for n, (key, dept, title, specialization) in enumerate(spec['teachers']):
        first, last, gender = person()
        user = s.account(inst, code, first, last, UserRole.TEACHER, title=title)
        db.flush()
        s.add(StaffMember(institution_id=inst.id, staff_number=f'{code}/TSC/{2014 + n % 9}/{101 + n}', first_name=first, last_name=last,
                          category='TEACHING', job_title=title, department_id=departments[dept].id, user_id=user.id, email=user.email,
                          phone=phone(), employment_type='FULL_TIME', status='ACTIVE', joined_on=date(2014 + n % 10, 1 + n % 12, 5),
                          gender=gender, date_of_birth=date(1975 + n % 20, 1 + (n * 5) % 12, 3 + n % 25),
                          qualification=spec['qualification'], specialization=specialization))
        teachers[key] = user
    for n, (title, permissions, dept) in enumerate(spec['support_staff']):
        first, last, gender = person()
        user = s.account(inst, code, first, last, UserRole.STAFF, title=title)
        db.flush()
        s.add(StaffMember(institution_id=inst.id, staff_number=f'{code}/ADM/{301 + n}', first_name=first, last_name=last, category='NON_TEACHING',
                          job_title=title, department_id=departments[dept].id if dept else None, user_id=user.id, email=user.email, phone=phone(),
                          employment_type='FULL_TIME', status='ACTIVE', joined_on=date(2019 + n, 2, 1), gender=gender))
        for p in permissions:
            s.add(StaffPermission(institution_id=inst.id, user_id=user.id, permission=p, granted_by=admin.id))
    db.flush()

    # Calendar.
    year = s.add(AcademicYear(id=uuid.uuid4(), institution_id=inst.id, name=spec['year'][0], start_date=spec['year'][1], end_date=spec['year'][2], status='ACTIVE'))
    db.flush()
    periods = [s.add(AcademicPeriod(id=uuid.uuid4(), institution_id=inst.id, year_id=year.id, name=n, start_date=a, end_date=b)) for n, a, b in spec['periods']]
    db.flush()
    current = next(p for p in periods if p.start_date <= TODAY <= p.end_date)

    # Programmes and study levels (colleges and universities).
    programmes, study_levels = {}, {}
    for pcode, (pname, award, dept, lvl) in spec.get('programmes', {}).items():
        programmes[pcode] = s.add(Programme(id=uuid.uuid4(), institution_id=inst.id, department_id=departments[dept].id,
                                            education_level_id=levels[lvl].id, code=pcode, name=pname, award=award))
    db.flush()
    for skey, (sname, prog, lvl, position) in spec.get('study_levels', {}).items():
        study_levels[skey] = s.add(StudyLevel(id=uuid.uuid4(), institution_id=inst.id, programme_id=programmes[prog].id if prog else None,
                                              education_level_id=levels[lvl].id, code=skey, name=sname, position=position))
    db.flush()

    # Classes, learners and their subjects.
    summary = dict(classes=0, students=0, subjects=0, assessments=0, scores=0, attendance=0)
    adm = 0
    all_students = []
    timetable_classes = []
    window_offer = []
    for cdef in spec['classes']:
        lvl = levels[cdef['level']]
        cls = s.add(AcademicClass(id=uuid.uuid4(), institution_id=inst.id, name=cdef['name'], stream=cdef.get('stream', ''),
                                  education_level_id=lvl.id, academic_year=year.name, supervisor_id=teachers[cdef['class_teacher']].id,
                                  programme_id=programmes[cdef['programme']].id if cdef.get('programme') else None,
                                  level_id=study_levels[cdef['study_level']].id if cdef.get('study_level') else None))
        db.flush()
        summary['classes'] += 1
        students = []
        for i in range(cdef['size']):
            adm += 1
            first, last, gender = person()
            admission = f"{spec['admission_prefix']}{adm:04d}{spec.get('admission_suffix', '')}"
            login_id = admission.upper() if spec['student_login'] == 'ID' else None
            user = s.account(inst, code, first, last, UserRole.STUDENT, login_id=login_id, title=cdef['name'])
            db.flush()
            st = s.add(Student(id=uuid.uuid4(), institution_id=inst.id, user_id=user.id, admission_number=admission,
                               phone=phone() if spec['student_phones'] else None, status='ACTIVE'))
            db.flush()
            s.add(Enrollment(institution_id=inst.id, class_id=cls.id, student_id=st.id, active=True))
            students.append((st, user))
            if spec['guardians']:
                gfirst, glast, ggender = person()
                g = s.add(Guardian(id=uuid.uuid4(), institution_id=inst.id, full_name=f'{gfirst} {last}', phone=phone(),
                                   email=s.email(f'parent.{first.lower()}.{last.lower()}.{code.lower()}'), occupation=''))
                db.flush()
                s.add(StudentGuardian(institution_id=inst.id, student_id=st.id, guardian_id=g.id,
                                      relationship='Mother' if ggender == 'FEMALE' else 'Father', is_primary=True))
            # Fee status this term: most paid, some with a balance.
            roll = rng.random()
            status, balance = ('PAID', 0) if roll < 0.55 else ('PARTIAL', rng.choice([2500, 4800, 7500, 12000])) if roll < 0.85 else ('UNPAID', spec['term_fee'])
            s.add(FeeStatus(institution_id=inst.id, student_id=st.id, period_id=current.id, status=status, balance=Decimal(balance),
                            note='' if status == 'PAID' else 'Balance to be cleared before end-of-term exams', updated_by=admin.id))
        summary['students'] += len(students)
        all_students += students
        db.flush()

        subjects = []
        for sdef in cdef['subjects']:
            unit = None
            if sdef.get('unit_code'):
                unit = s.add(CatalogueUnit(id=uuid.uuid4(), institution_id=inst.id, education_level_id=lvl.id,
                                           programme_id=programmes[cdef['programme']].id if cdef.get('programme') else None,
                                           level_id=study_levels[cdef['study_level']].id if cdef.get('study_level') else None,
                                           code=sdef['unit_code'], name=sdef['name'], credits=Decimal(sdef['credits']) if sdef.get('credits') else None))
                db.flush()
            teacher = teachers[sdef['teacher']]
            optional = sdef.get('optional', False)
            subject = s.add(Subject(id=uuid.uuid4(), institution_id=inst.id, class_id=cls.id, name=f"{sdef['unit_code']} {sdef['name']}" if sdef.get('unit_code') else sdef['name'],
                                    teacher_id=teacher.id, catalogue_id=unit.id if unit else None, period_id=current.id,
                                    registration_mode='INDIVIDUAL' if (optional or spec['registration'] == 'INDIVIDUAL') else 'COHORT'))
            db.flush()
            s.add(OfferingTeacher(institution_id=inst.id, subject_id=subject.id, user_id=teacher.id, role='LEAD', weekly_hours=Decimal(sdef.get('hours', 4))))
            summary['subjects'] += 1
            if optional:
                window_offer.append(subject)
                continue  # chosen in the registration window
            if subject.registration_mode == 'INDIVIDUAL':
                for st, _ in students:
                    s.add(CourseRegistration(institution_id=inst.id, subject_id=subject.id, student_id=st.id, active=True, status='APPROVED'))
            subjects.append((subject, sdef, teacher))
        db.flush()
        timetable_classes.append((cls, subjects))

        # Learning activity per subject: notes, past work with released marks, open work, and one quiz per class.
        scale = s.scales.get(spec['levels'][cdef['level']][3]) if spec['levels'][cdef['level']][3] else None
        competency = scale is not None and scale.kind == 'COMPETENCY'
        labels = [lv.label for lv in db.query(ScaleLevel).filter_by(scale_id=scale.id).order_by(ScaleLevel.position).all()] if competency else []
        bands = [dict(minimum=float(lv.min_percent), label=lv.code) for lv in db.query(ScaleLevel).filter_by(scale_id=scale.id).order_by(ScaleLevel.position).all()] \
            if scale is not None and not competency else spec.get('learning', {}).get('grade_bands')
        for si, (subject, sdef, teacher) in enumerate(subjects):
            topic, task = sdef['topic'], sdef['task']
            s.add(CourseMaterial(institution_id=inst.id, subject_id=subject.id, title=f'{topic}: notes', section=sdef.get('week', 'Week 9'),
                                 body=sdef['notes'], published=True))
            past = s.add(Coursework(id=uuid.uuid4(), institution_id=inst.id, subject_id=subject.id, period_id=current.id,
                                    title=f'{topic}: {spec["past_label"]}', instructions=task, kind='COURSEWORK' if not competency else 'ASSIGNMENT',
                                    due_at=datetime.combine(TODAY - timedelta(days=9 + si), time(15, 0), tzinfo=timezone.utc), max_score=Decimal(30 if not competency else 100),
                                    published=True, grades_released=True, assessment_mode='COMPETENCY' if competency else 'NUMERIC',
                                    rubric_labels=labels, grading_bands=None if competency else bands, scale_id=scale.id if scale else None,
                                    section=sdef.get('week', 'Week 9'), allow_late_submissions=True, delivery='STANDARD', submission_file_types=['pdf', 'word']))
            upcoming = s.add(Coursework(id=uuid.uuid4(), institution_id=inst.id, subject_id=subject.id, period_id=current.id,
                                        title=f'{topic}: {spec["next_label"]}', instructions=sdef.get('next_task', task), kind='ASSIGNMENT',
                                        due_at=datetime.combine(TODAY + timedelta(days=3 + si), time(15, 0), tzinfo=timezone.utc), max_score=Decimal(20 if not competency else 100),
                                        published=True, grades_released=False, assessment_mode='COMPETENCY' if competency else 'NUMERIC',
                                        rubric_labels=labels, scale_id=scale.id if scale else None, section=sdef.get('next_week', 'Week 10'),
                                        allow_late_submissions=False, delivery='STANDARD', submission_file_types=['pdf', 'word', 'image']))
            summary['assessments'] += 2
            db.flush()
            for k, (st, _) in enumerate(students):
                ability = 0.45 + ((hash((st.admission_number, subject.name)) % 50) / 100)
                s.add(Submission(institution_id=inst.id, coursework_id=past.id, student_id=st.id, answer=sdef.get('answer', 'Answer handed in.'),
                                 status='SUBMITTED', submitted_at=past.due_at - timedelta(hours=6 + k), is_late=False, version=1))
                if competency:
                    # Stronger learners land nearer the top level of whatever scale the level uses.
                    label = labels[min(len(labels) - 1, int((1 - min(ability, 0.99)) * len(labels) * 1.4))]
                    s.add(Score(institution_id=inst.id, coursework_id=past.id, student_id=st.id, score=None, competency_label=label, feedback=sdef.get('feedback', '')))
                else:
                    s.add(Score(institution_id=inst.id, coursework_id=past.id, student_id=st.id, score=Decimal(round(30 * min(ability, 0.97))),
                                competency_label=None, feedback=sdef.get('feedback', '')))
                summary['scores'] += 1
            if sdef['quiz'] and not competency:
                quiz = s.add(Coursework(id=uuid.uuid4(), institution_id=inst.id, subject_id=subject.id, period_id=current.id, title=f'{topic}: quick quiz',
                                        instructions='Answer each question before its time runs out. You cannot go back.', kind='COURSEWORK',
                                        opens_at=datetime.combine(TODAY, time(6, 0), tzinfo=timezone.utc),
                                        due_at=datetime.combine(TODAY + timedelta(days=5), time(17, 0), tzinfo=timezone.utc),
                                        max_score=Decimal(sum(q[3] for q in sdef['quiz'])), published=True, assessment_mode='NUMERIC', delivery='QUIZ',
                                        section=sdef.get('next_week', 'Week 10'), allow_late_submissions=False, submission_file_types=[]))
                db.flush()
                s.add(QuizSettings(institution_id=inst.id, coursework_id=quiz.id, time_limit_minutes=15, attempts_allowed=1, no_going_back=True,
                                   shuffle_questions=True, shuffle_options=True, hide_results_until_close=True, log_tab_switches=True))
                for qi, (prompt, options, correct, points) in enumerate(sdef['quiz']):
                    kind = 'TRUE_FALSE' if options is None else 'MULTIPLE' if len(correct) > 1 else 'SINGLE'
                    opts = [dict(id='true', text='True'), dict(id='false', text='False')] if options is None else [dict(id=chr(97 + i), text=t) for i, t in enumerate(options)]
                    s.add(QuizQuestion(institution_id=inst.id, coursework_id=quiz.id, position=qi, kind=kind, prompt=prompt, options=opts,
                                       correct=correct, points=Decimal(points), time_limit_seconds=60))
                summary['assessments'] += 1
        # Class register for the last three weeks.
        for d in weekdays_back(15, TODAY - timedelta(days=1)):
            for k, (st, _) in enumerate(students):
                r = rng.random()
                status = 'ABSENT' if r < 0.05 else 'LATE' if r < 0.12 else 'EXCUSED' if r < 0.14 else 'PRESENT'
                s.add(Attendance(institution_id=inst.id, class_id=cls.id, subject_id=None, scope_key='class', day=d, student_id=st.id, status=status,
                                 note='Medical appointment' if status == 'EXCUSED' else '', arrived_at=time(7, 40 + rng.randint(0, 15)) if status == 'LATE' else None,
                                 outcome='MISSED' if status == 'ABSENT' else 'EXCUSED' if status == 'EXCUSED' else 'ATTENDED'))
                summary['attendance'] += 1
        db.flush()

    # Weekly timetable for the current term, with no teacher in two places at once.
    s.add(TimetableTerm(institution_id=inst.id, period_id=current.id, weekdays=[1, 2, 3, 4, 5], published_at=NOW))
    slots = []
    for label, a, b, brk in spec['bell']:
        slots.append(s.add(TimetableSlot(id=uuid.uuid4(), institution_id=inst.id, period_id=current.id, label=label,
                                         start_time=time(*a), end_time=time(*b), is_break=brk, weekdays=[])))
    db.flush()
    teaching = [x for x in slots if not x.is_break]
    busy = set()
    for cls, subjects in timetable_classes:
        if not subjects:
            continue
        queue = [sub for sub, sdef, _ in subjects for _ in range(spec['lessons_per_week'])]
        rng.shuffle(queue)
        cells = [(day, slot) for day in range(1, 6) for slot in teaching]
        for day, slot in cells:
            for idx, sub in enumerate(queue):
                if (sub.teacher_id, day, slot.id) not in busy:
                    s.add(TimetableEntry(institution_id=inst.id, period_id=current.id, slot_id=slot.id, weekday=day, subject_id=sub.id,
                                         class_id=cls.id, teacher_id=sub.teacher_id))
                    busy.add((sub.teacher_id, day, slot.id))
                    queue.pop(idx)
                    break
            if not queue:
                break
    db.flush()

    # Notices.
    for title, body, audience in spec['announcements']:
        s.add(Announcement(institution_id=inst.id, title=title, body=body, audience=audience, class_id=None, created_by=admin.id,
                           expires_on=TODAY + timedelta(days=30)))

    # Course registration window for optional units (university).
    if window_offer:
        window = s.add(RegistrationWindow(id=uuid.uuid4(), institution_id=inst.id, title=spec['window_title'], period_id=current.id,
                                          opens_at=NOW - timedelta(days=2), closes_at=NOW + timedelta(days=12), min_units=1, max_units=1,
                                          min_credits=None, max_credits=None, class_ids=[str(c.id) for c, _ in timetable_classes if any(o.class_id == c.id for o in window_offer)]))
        db.flush()
        offered_classes = {o.class_id for o in window_offer}
        chooser = [(st, u) for (st, u) in all_students if db.query(Enrollment).filter_by(institution_id=inst.id, student_id=st.id, active=True).first().class_id in offered_classes]
        for k, (st, _) in enumerate(chooser[: len(chooser) // 2]):
            pick = [o for o in window_offer][k % len(window_offer)]
            s.add(CourseRegistration(institution_id=inst.id, subject_id=pick.id, student_id=st.id, active=False, status='PENDING', window_id=window.id))
    db.flush()
    summary.update(institution=inst.name, code=code, staff=len(teachers) + len(spec['support_staff']) + 1, current_period=f'{current.name} · {year.name}')
    return summary


def specs():
    from app.services.grading_rules import GradingRules  # noqa: F401  (validated via AcademicConfiguration)
    kcse = [dict(minimum=80, label='A', points=12), dict(minimum=75, label='A-', points=11), dict(minimum=70, label='B+', points=10),
            dict(minimum=65, label='B', points=9), dict(minimum=60, label='B-', points=8), dict(minimum=55, label='C+', points=7),
            dict(minimum=50, label='C', points=6), dict(minimum=45, label='C-', points=5), dict(minimum=40, label='D+', points=4),
            dict(minimum=35, label='D', points=3), dict(minimum=30, label='D-', points=2), dict(minimum=0, label='E', points=1)]
    uni = [dict(minimum=70, label='A', points=4), dict(minimum=60, label='B', points=3), dict(minimum=50, label='C', points=2),
           dict(minimum=40, label='D', points=1), dict(minimum=0, label='E', points=0)]
    school_bell = [('Lesson 1', (8, 0), (8, 40), False), ('Lesson 2', (8, 40), (9, 20), False), ('Short break', (9, 20), (9, 30), True),
                   ('Lesson 3', (9, 30), (10, 10), False), ('Lesson 4', (10, 10), (10, 50), False), ('Tea break', (10, 50), (11, 20), True),
                   ('Lesson 5', (11, 20), (12, 0), False), ('Lesson 6', (12, 0), (12, 40), False), ('Lunch', (12, 40), (13, 40), True),
                   ('Lesson 7', (13, 40), (14, 20), False), ('Lesson 8', (14, 20), (15, 0), False)]
    college_bell = [('Session 1', (8, 0), (10, 0), False), ('Break', (10, 0), (10, 30), True), ('Session 2', (10, 30), (12, 30), False),
                    ('Lunch', (12, 30), (13, 30), True), ('Session 3', (13, 30), (15, 30), False), ('Session 4', (15, 30), (17, 30), False)]

    def sub(name, teacher, topic, task, notes, quiz=None, **extra):
        return dict(name=name, teacher=teacher, topic=topic, task=task, notes=notes, quiz=quiz or [], **extra)

    math_quiz = [('What is 15% of 240?', ['24', '36', '40', '30'], ['b'], 1), ('Which of these are prime numbers?', ['21', '29', '31', '33'], ['b', 'c'], 2),
                 ('The sum of interior angles of a triangle is 180°.', None, ['true'], 1)]
    eng_quiz = [('Choose the correctly punctuated sentence.', ['Its raining, take an umbrella.', "It's raining; take an umbrella.", 'Its raining take an umbrella'], ['b'], 1),
                ('A metaphor compares two things using "like" or "as".', None, ['false'], 1)]
    sci_quiz = [('Which gas do plants take in for photosynthesis?', ['Oxygen', 'Carbon dioxide', 'Nitrogen', 'Hydrogen'], ['b'], 1),
                ('Which of these are renewable energy sources?', ['Solar', 'Coal', 'Wind', 'Diesel'], ['a', 'c'], 2)]
    ict_quiz = [('Which device is an output device?', ['Keyboard', 'Monitor', 'Scanner', 'Mouse'], ['b'], 1),
                ('RAM keeps its contents when the computer is switched off.', None, ['false'], 1)]
    prog_quiz = [('Which data structure works first in, first out?', ['Stack', 'Queue', 'Tree', 'Graph'], ['b'], 1),
                 ('Which of these are Python keywords?', ['def', 'function', 'return', 'var'], ['a', 'c'], 2),
                 ('An algorithm of O(n log n) is faster than O(n²) for large n.', None, ['true'], 1)]
    acc_quiz = [('Which statement shows a business’s financial position on a date?', ['Income statement', 'Balance sheet', 'Cash book'], ['b'], 1),
                ('Assets = Liabilities + Capital.', None, ['true'], 1)]

    ecde = lambda name, teacher, topic: sub(name, teacher, topic, f'Activity: {topic.lower()} with a parent at home and tell the class about it.',  # noqa: E731
                                           f'This week we explore {topic.lower()} through songs, games and drawing.')
    tumaini = dict(
        name='Tumaini Ridge Academy', code='TRA', type='HIGH_SCHOOL', address='Kiganjo Road, Nyeri Town, Nyeri County', phone='+254 61 203 0417',
        fee=4500, term_fee=18500, admin=('Margaret', 'Wachira', 'FEMALE'), admin_title='School Principal', qualification='Bachelor of Education (Arts/Science)',
        config=dict(assessment_policy='MIXED', competency_labels=['Exceeding expectations', 'Meeting expectations', 'Approaching expectations', 'Below expectations',
                                                                  'Exceeding expectations 1', 'Exceeding expectations 2', 'Meeting expectations 1', 'Meeting expectations 2',
                                                                  'Approaching expectations 1', 'Approaching expectations 2', 'Below expectations 1', 'Below expectations 2'],
                    grading_rules=dict(enabled=True, name='Tumaini Ridge Academy grading (KCSE-style 12 points)', aggregation='CATEGORY_WEIGHTS',
                                       weights=dict(ASSIGNMENT=0, COURSEWORK=30, EXAM=70), pass_percentage=40, bands=kcse)),
        learning=dict(grade_bands=[dict(minimum=b['minimum'], label=b['label']) for b in kcse]),
        levels={'ECDE': ('ECDE', 'GROUPED', 'TERM', 'CBE_4'), 'LP': ('LOWER_PRIMARY', 'GROUPED', 'TERM', 'CBE_4'), 'UP': ('UPPER_PRIMARY', 'GROUPED', 'TERM', 'CBE_4'),
                'JS': ('JUNIOR_SCHOOL', 'GROUPED', 'TERM', 'CBE_8'), 'SS': ('SENIOR_SCHOOL', 'GROUPED', 'TERM', 'LETTER_A_E')},
        departments={'ECDE': ('Early Years and Lower Primary', 'DEPARTMENT', None), 'LANG': ('Languages', 'DEPARTMENT', None),
                     'MATH': ('Mathematics', 'DEPARTMENT', None), 'SCI': ('Sciences', 'DEPARTMENT', None), 'HUM': ('Humanities', 'DEPARTMENT', None),
                     'ADM': ('Administration and Finance', 'DEPARTMENT', None)},
        teachers=[('ecde1', 'ECDE', 'ECDE Teacher', 'Early Childhood Education'), ('ecde2', 'ECDE', 'ECDE Teacher', 'Early Childhood Education'),
                  ('lp1', 'ECDE', 'Lower Primary Teacher', 'Primary Education'), ('lp2', 'ECDE', 'Lower Primary Teacher', 'Primary Education'),
                  ('eng', 'LANG', 'Head of Languages', 'English and Literature'), ('kis', 'LANG', 'Teacher', 'Kiswahili'),
                  ('math', 'MATH', 'Head of Mathematics', 'Mathematics and Physics'), ('math2', 'MATH', 'Teacher', 'Mathematics and Computer Studies'),
                  ('sci', 'SCI', 'Head of Sciences', 'Biology and Chemistry'), ('sci2', 'SCI', 'Teacher', 'Integrated Science and Agriculture'),
                  ('hum', 'HUM', 'Teacher', 'History, Government and CRE'), ('hum2', 'HUM', 'Teacher', 'Social Studies and Geography')],
        support_staff=[('Bursar', ['fees.manage', 'students.view'], 'ADM'), ('School Secretary', ['students.view', 'staff.view'], 'ADM')],
        year=('2026', date(2026, 1, 5), date(2026, 11, 27)),
        periods=[('Term 1', date(2026, 1, 5), date(2026, 4, 2)), ('Term 2', date(2026, 4, 27), date(2026, 7, 31)), ('Term 3', date(2026, 8, 24), date(2026, 11, 27))],
        admission_prefix='TRA/', student_login='ID', student_phones=False, guardians=True, registration='COHORT', lessons_per_week=4,
        past_label='CAT 2', next_label='homework', bell=school_bell,
        announcements=[('Grade 9 KJSEA and Form 4 KCSE timetable', 'National examinations run through November. Candidates should be in school by 7:30 am with their index numbers. Parents of other classes: normal lessons continue.', 'EVERYONE'),
                       ('Closing day: Friday 27 November', 'Term 3 closes on 27 November at 12:30 pm. Report forms will be shared after the staff meeting. Please clear outstanding fees before closing day.', 'EVERYONE'),
                       ('Staff meeting on Wednesday', 'All teaching staff: staff meeting in the library on Wednesday at 3:30 pm to plan the end-of-term reports.', 'STAFF')],
        classes=[
            dict(name='PP1 Sunflower', level='ECDE', class_teacher='ecde1', size=6, subjects=[ecde('Language Activities', 'ecde1', 'Sounds and letters'), ecde('Mathematical Activities', 'ecde1', 'Counting 1 to 20'), ecde('Environmental Activities', 'ecde2', 'Animals at home')]),
            dict(name='PP2 Jacaranda', level='ECDE', class_teacher='ecde2', size=6, subjects=[ecde('Language Activities', 'ecde2', 'Reading short words'), ecde('Mathematical Activities', 'ecde2', 'Shapes around us'), ecde('Creative Activities', 'ecde1', 'Colours and painting')]),
            *[dict(name=f'Grade {g} {stream}', level='LP', class_teacher=t, size=6, subjects=[
                sub('English', t, 'Reading for meaning', 'Read the story "The Lost Goat" and answer the five questions.', 'Read aloud daily for 15 minutes.'),
                sub('Kiswahili', 'kis', 'Kusoma na kuandika', 'Andika sentensi tano kuhusu familia yako.', 'Soma hadithi fupi kila siku.'),
                sub('Mathematics', t, 'Addition and subtraction', 'Solve the ten sums on page 42.', 'Use counters to add and take away.')])
              for g, stream, t in [(1, 'Simba', 'lp1'), (2, 'Chui', 'lp2'), (3, 'Duma', 'lp1')]],
            *[dict(name=f'Grade {g} {stream}', level='UP', class_teacher=t, size=6, subjects=[
                sub('English', 'eng', 'Comprehension', 'Read the passage about Lake Nakuru and answer the questions.', 'Identify the main idea of each paragraph.'),
                sub('Mathematics', 'math2', 'Fractions', 'Simplify the fractions in Exercise 5B.', 'A fraction has a numerator and a denominator.'),
                sub('Science and Technology', 'sci2', 'Plants and their parts', 'Draw a bean plant and label its parts.', 'Roots hold the plant and take in water.')])
              for g, stream, t in [(4, 'Tausi', 'lp2'), (5, 'Kifaru', 'hum2'), (6, 'Nyati', 'sci2')]],
            *[dict(name=f'Grade {g} {stream}', level='JS', class_teacher=t, size=6, subjects=[
                sub('English', 'eng', 'Argumentative writing', 'Write 300 words: should mobile phones be allowed in school?', 'State your position, give reasons and a conclusion.'),
                sub('Mathematics', 'math', 'Linear equations', 'Solve the equations in Exercise 3.4, showing working.', 'Do the same to both sides of the equation.', quiz=math_quiz),
                sub('Integrated Science', 'sci', 'Electrical circuits', 'Draw a circuit with a cell, switch and two bulbs in series.', 'Current flows only in a closed circuit.'),
                sub('Social Studies', 'hum2', 'Kenya’s physical features', 'Locate five physical features on the map of Kenya.', 'The Great Rift Valley runs from north to south.')])
              for g, stream, t in [(7, 'Mlima', 'math'), (8, 'Ziwa', 'eng'), (9, 'Bahari', 'sci')]],
            dict(name='Grade 10 STEM', level='SS', class_teacher='math2', size=6, subjects=[
                sub('English', 'eng', 'Oral literature', 'Collect and transcribe one riddle and one proverb from your community.', 'Oral literature is passed on by word of mouth.', quiz=eng_quiz),
                sub('Core Mathematics', 'math2', 'Quadratic expressions', 'Factorise the expressions in Exercise 2.1.', 'Look for two numbers whose product and sum match.'),
                sub('Biology', 'sci', 'Cell structure', 'Draw and label an animal cell and a plant cell.', 'Plant cells have a cell wall and chloroplasts.'),
                sub('Computer Studies', 'math2', 'Introduction to algorithms', 'Write the steps to make tea as an algorithm.', 'An algorithm is a finite set of clear steps.')]),
            dict(name='Form 3 East', level='SS', class_teacher='hum', size=6, subjects=[
                sub('Mathematics', 'math', 'Probability', 'Answer questions 1–8 on probability in Exercise 7.', 'Probability = favourable outcomes / total outcomes.', quiz=math_quiz),
                sub('Chemistry', 'sci', 'The mole', 'Calculate the moles in 12 g of carbon and 4 g of hydrogen.', 'One mole contains 6.02 × 10²³ particles.'),
                sub('History and Government', 'hum', 'The Kenyan constitution', 'Explain four functions of the National Assembly.', 'The constitution was promulgated in August 2010.'),
                sub('Kiswahili', 'kis', 'Insha ya kubuni', 'Andika insha kuhusu siku ya michezo shuleni.', 'Tumia methali na nahau ipasavyo.')]),
            dict(name='Form 4 West', level='SS', class_teacher='sci', size=6, subjects=[
                sub('Mathematics', 'math', 'Revision: calculus', 'Differentiate the functions in the revision paper, questions 1–5.', 'The derivative gives the rate of change.', quiz=math_quiz),
                sub('Biology', 'sci', 'Revision: genetics', 'Work through the KCSE 2023 genetics questions.', 'Alleles can be dominant or recessive.', quiz=sci_quiz),
                sub('English', 'eng', 'Set book: Blossoms of the Savannah', 'Discuss the theme of cultural conflict with examples.', 'Refer to characters and events to support each point.'),
                sub('History and Government', 'hum', 'Revision: devolution', 'Explain five functions of county governments.', 'There are 47 county governments.')]),
        ])

    chtvc = dict(
        name='Chemchemi Hills Technical and Vocational College', code='CHTVC', type='COLLEGE', address='Off Nakuru–Eldama Ravine Road, Kabarak area, Nakuru County',
        phone='+254 51 221 4380', fee=6000, term_fee=22500, admin=('Peter', 'Kiplagat', 'MALE'), admin_title='Principal', qualification='Diploma/Degree with TVET trainer certification',
        config=dict(assessment_policy='COMPETENCY', registration_mode='COHORT', period_kind='TERM', structure='PROGRAMME',
                    competency_labels=['Competent', 'Not yet competent'], credits_enabled=False),
        levels={'TVET': ('TVET', 'PROGRAMME', 'TERM', 'TVET_COMPETENCE')},
        departments={'ICT': ('Information and Communication Technology', 'DEPARTMENT', None), 'BUS': ('Business Studies', 'DEPARTMENT', None),
                     'EEE': ('Electrical and Electronic Engineering', 'DEPARTMENT', None), 'REG': ('Registry and Finance', 'DEPARTMENT', None)},
        programmes={'DICT': ('Diploma in Information Communication Technology', 'Diploma (KNQF Level 6)', 'ICT', 'TVET'),
                    'DBM': ('Diploma in Business Management', 'Diploma (KNQF Level 6)', 'BUS', 'TVET'),
                    'CEI': ('Certificate in Electrical Installation', 'Certificate (KNQF Level 5)', 'EEE', 'TVET')},
        study_levels={'DICT-M1': ('Module I', 'DICT', 'TVET', 1), 'DBM-M1': ('Module I', 'DBM', 'TVET', 1), 'CEI-M2': ('Module II', 'CEI', 'TVET', 2)},
        teachers=[('ict1', 'ICT', 'Trainer, ICT', 'Networking and computer applications'), ('ict2', 'ICT', 'Head of Department, ICT', 'Software development'),
                  ('bus1', 'BUS', 'Trainer, Business', 'Accounting and entrepreneurship'), ('bus2', 'BUS', 'Head of Department, Business', 'Business management'),
                  ('eee1', 'EEE', 'Trainer, Electrical', 'Electrical installation'), ('eee2', 'EEE', 'Head of Department, Electrical', 'Electrical principles')],
        support_staff=[('Accounts Clerk', ['fees.manage', 'students.view'], 'REG'), ('Registrar', ['students.view', 'staff.view'], 'REG')],
        year=('2026', date(2026, 1, 5), date(2026, 12, 4)),
        periods=[('January–April term', date(2026, 1, 5), date(2026, 4, 10)), ('May–August term', date(2026, 5, 4), date(2026, 8, 7)),
                 ('September–December term', date(2026, 9, 7), date(2026, 12, 4))],
        admission_prefix='CHTVC/', admission_suffix='/2026', student_login='ID', student_phones=True, guardians=False, registration='COHORT', lessons_per_week=2,
        past_label='practical assessment', next_label='portfolio task', bell=college_bell,
        announcements=[('Industrial attachment placements', 'Module II trainees: submit your attachment acceptance letters to your head of department by 20 November.', 'STUDENTS'),
                       ('KNEC/CDACC assessment registration', 'Registration for the November–December assessment series closes on 14 November. Confirm your details with the Registrar.', 'EVERYONE')],
        classes=[
            dict(name='DICT Module I, September 2026 intake', level='TVET', class_teacher='ict2', programme='DICT', study_level='DICT-M1', size=7, subjects=[
                sub('Computer Applications', 'ict1', 'Spreadsheets', 'Build a class fees spreadsheet with totals and an average using formulas.', 'Use absolute references like $B$2 for fixed cells.', unit_code='DICT 101', hours=6),
                sub('Introduction to Networking', 'ict1', 'Network cabling', 'Terminate one straight-through and one crossover Cat6 cable and test them.', 'Follow the T568B colour order.', unit_code='DICT 102', hours=6),
                sub('Programming Fundamentals', 'ict2', 'Variables and loops', 'Write a Python program that prints the multiplication table of 7.', 'A for loop repeats a block a set number of times.', unit_code='DICT 103', hours=6)]),
            dict(name='DBM Module I, September 2026 intake', level='TVET', class_teacher='bus2', programme='DBM', study_level='DBM-M1', size=7, subjects=[
                sub('Principles of Management', 'bus2', 'Functions of management', 'Explain planning, organising, leading and controlling with a local business example.', 'Management gets work done through people.', unit_code='DBM 101', hours=5),
                sub('Financial Accounting I', 'bus1', 'The accounting equation', 'Record ten transactions for a small shop and balance the accounts.', 'Every transaction has two sides.', unit_code='DBM 102', hours=5),
                sub('Entrepreneurship Education', 'bus1', 'Business ideas', 'Present one business idea for your county with a simple budget.', 'Start from a problem people will pay to solve.', unit_code='DBM 103', hours=4)]),
            dict(name='Electrical Installation Module II', level='TVET', class_teacher='eee2', programme='CEI', study_level='CEI-M2', size=6, subjects=[
                sub('Electrical Installation Practice', 'eee1', 'Domestic wiring', 'Wire a one-way switch lighting circuit on the practice board.', 'Isolate the supply before you start.', unit_code='CEI 201', hours=8),
                sub('Electrical Principles', 'eee2', 'Ohm’s law', 'Calculate current and power for the five circuits on the worksheet.', 'V = I × R; P = V × I.', unit_code='CEI 202', hours=5),
                sub('Workshop Safety', 'eee1', 'Fire safety', 'List the classes of fire and the extinguisher for each.', 'Never use water on an electrical fire.', unit_code='CEI 203', hours=3)]),
        ])

    mhu = dict(
        name='Mlimani Heights University', code='MHU', type='UNIVERSITY', address='Machakos–Kitui Road, Machakos County', phone='+254 44 212 0650',
        fee=12000, term_fee=65000, admin=('Grace', 'Mutiso', 'FEMALE'), admin_title='Academic Registrar', qualification='PhD / Masters in the field',
        config=dict(assessment_policy='NUMERIC', registration_mode='INDIVIDUAL', period_kind='SEMESTER', structure='PROGRAMME', credits_enabled=True,
                    grading_rules=dict(enabled=True, name='Mlimani Heights University undergraduate grading', aggregation='CATEGORY_WEIGHTS',
                                       weights=dict(ASSIGNMENT=10, COURSEWORK=20, EXAM=70), pass_percentage=40, bands=uni)),
        learning=dict(grade_bands=[dict(minimum=b['minimum'], label=b['label']) for b in uni]),
        levels={'UNI': ('UNIVERSITY', 'PROGRAMME', 'SEMESTER', 'LETTER_A_E')},
        departments={'SCI': ('School of Computing and Informatics', 'SCHOOL', None), 'CS': ('Department of Computer Science', 'DEPARTMENT', 'SCI'),
                     'SBE': ('School of Business and Economics', 'SCHOOL', None), 'ACC': ('Department of Accounting and Finance', 'DEPARTMENT', 'SBE'),
                     'REG': ('Office of the Registrar', 'DEPARTMENT', None)},
        programmes={'BSCS': ('Bachelor of Science in Computer Science', 'BSc', 'CS', 'UNI'), 'BCOM': ('Bachelor of Commerce', 'BCom', 'ACC', 'UNI')},
        study_levels={'BSCS-Y1': ('Year 1', 'BSCS', 'UNI', 1), 'BSCS-Y2': ('Year 2', 'BSCS', 'UNI', 2), 'BCOM-Y1': ('Year 1', 'BCOM', 'UNI', 1)},
        teachers=[('cs1', 'CS', 'Lecturer', 'Software engineering'), ('cs2', 'CS', 'Senior Lecturer', 'Algorithms and data structures'),
                  ('cs3', 'CS', 'Lecturer', 'Databases and information systems'), ('math', 'CS', 'Lecturer', 'Discrete mathematics'),
                  ('acc1', 'ACC', 'Lecturer', 'Financial accounting'), ('eco1', 'ACC', 'Senior Lecturer', 'Economics'),
                  ('com1', 'ACC', 'Lecturer', 'Communication skills')],
        support_staff=[('Finance Officer', ['fees.manage', 'students.view'], 'REG'), ('Senior Assistant Registrar', ['students.view', 'registrations.approve', 'staff.view'], 'REG')],
        year=('2026/2027', date(2026, 9, 7), date(2027, 7, 30)),
        periods=[('Semester 1', date(2026, 9, 7), date(2026, 12, 18)), ('Semester 2', date(2027, 1, 11), date(2027, 4, 30)), ('Semester 3', date(2027, 5, 17), date(2027, 7, 30))],
        admission_prefix='SCI/', admission_suffix='/2026', student_login='ID', student_phones=True, guardians=False, registration='INDIVIDUAL', lessons_per_week=2,
        past_label='CAT 1', next_label='assignment 2', bell=college_bell, window_title='Semester 1 elective registration',
        announcements=[('Semester 1 examinations begin 7 December', 'The final examination timetable is on the notice boards and here. Clear fees to receive your examination card.', 'EVERYONE'),
                       ('Elective registration is open', 'Year 2 Computer Science students: choose one elective under Course registration by 19 November.', 'STUDENTS')],
        classes=[
            dict(name='BSc Computer Science, Year 1', level='UNI', class_teacher='cs2', programme='BSCS', study_level='BSCS-Y1', size=8, subjects=[
                sub('Introduction to Programming', 'cs2', 'Functions in Python', 'Write functions to compute the mean, median and mode of a list.', 'Functions take inputs and return outputs.', quiz=prog_quiz, unit_code='CSC 111', credits=3),
                sub('Discrete Mathematics', 'math', 'Sets and logic', 'Prove De Morgan’s laws using truth tables.', 'A set is a well-defined collection of objects.', unit_code='CSC 112', credits=3),
                sub('Communication Skills', 'com1', 'Academic writing', 'Write a 500-word essay on digital learning in Kenya with references.', 'Use the APA referencing style.', unit_code='UCU 101', credits=2)]),
            dict(name='BSc Computer Science, Year 2', level='UNI', class_teacher='cs1', programme='BSCS', study_level='BSCS-Y2', size=8, subjects=[
                sub('Data Structures and Algorithms', 'cs2', 'Linked lists', 'Implement a singly linked list with insert, delete and search.', 'Each node stores data and a pointer to the next node.', quiz=prog_quiz, unit_code='CSC 211', credits=3),
                sub('Database Systems', 'cs3', 'Normalisation', 'Normalise the given student records table to third normal form.', 'Remove repeating groups, then partial and transitive dependencies.', unit_code='CSC 212', credits=3),
                sub('Web Development', 'cs1', 'Responsive layouts', 'Build a responsive page for a school notice board.', 'Use CSS grid and media queries.', unit_code='CSC 215', credits=3, optional=True),
                sub('Mobile Computing', 'cs1', 'Android activities', 'Create an app with two screens and pass data between them.', 'An activity is one screen of an app.', unit_code='CSC 216', credits=3, optional=True)]),
            dict(name='Bachelor of Commerce, Year 1', level='UNI', class_teacher='acc1', programme='BCOM', study_level='BCOM-Y1', size=8, subjects=[
                sub('Principles of Accounting', 'acc1', 'Trial balance', 'Prepare a trial balance from the given ledger accounts.', 'Total debits must equal total credits.', quiz=acc_quiz, unit_code='BCM 111', credits=3),
                sub('Microeconomics', 'eco1', 'Demand and supply', 'Explain how a rise in fuel prices affects matatu fares.', 'Price settles where demand meets supply.', unit_code='BCM 112', credits=3),
                sub('Business Communication', 'com1', 'Business letters', 'Write a formal letter applying for an internship.', 'Keep it clear, polite and short.', unit_code='UCU 102', credits=2)]),
        ])
    return [tumaini, chtvc, mhu]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', required=True, help='Target database; must match --expected-host')
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--inbox', required=True, help='Gmail address that receives every account email')
    parser.add_argument('--credentials', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm', default='')
    args = parser.parse_args()
    import os
    from sqlalchemy.engine import make_url
    target = make_url(args.database_url)
    if target.host != args.expected_host:
        raise SystemExit('Database host does not match --expected-host')
    local = target.host in {'127.0.0.1', 'localhost', '::1'}
    if args.apply and not local and args.confirm != CONFIRM:
        raise SystemExit(f'Production needs --confirm "{CONFIRM}"')
    os.environ['DATABASE_URL'] = os.environ['DATABASE_URL_UNPOOLED'] = args.database_url
    os.environ.setdefault('ENVIRONMENT', 'development' if local else 'production')
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app import models  # noqa: F401
    from app.models.user import User, UserRole, UserStatus
    from app.models.institution import Institution
    from app.models.platform_secret import PlatformSecret  # noqa: F401

    engine = create_engine(args.database_url)
    with Session(engine, autoflush=False) as db:
        owners = db.query(User).filter(User.role == UserRole.PLATFORM_ADMIN, User.status == UserStatus.ACTIVE).all()
        assert owners, 'No active platform admin to keep'
        before = dict(institutions=db.query(Institution).count(), users=db.query(User).count())
        wipe(db, [o.id for o in owners])
        db.flush()
        seeder = Seeder(db, args.inbox, owners[0])
        summaries = [build_institution(seeder, spec) for spec in specs()]
        db.flush()
        from app.services.audit_service import record_audit
        from types import SimpleNamespace
        record_audit(db, SimpleNamespace(user_id=owners[0].id, actor_user_id=None, ip_address=None, request_method='SCRIPT', request_path='scripts/reset_and_seed.py'), 'platform.data_reset', 'platform', None,
                     'Owner-requested reset: all institutions deleted without backup; three fictional institutions loaded.')
        after = dict(institutions=db.query(Institution).count(), users=db.query(User).count())
        platform = [dict(institution='(platform)', role='PLATFORM_ADMIN', title='Platform administrator', name=f'{o.first_name} {o.last_name}', username=o.username,
                         sign_in_with=o.email, portal='Admin login', password='(unchanged: use your current platform admin password)') for o in owners]
        report = dict(applied=args.apply, database=f'{target.host}/{target.database}', before=before, after=after, institutions=summaries)
        if args.apply:
            db.commit()
        else:
            db.rollback()

    if args.apply:
        args.credentials.parent.mkdir(parents=True, exist_ok=True)
        args.credentials.write_text(json.dumps(dict(generated=NOW.isoformat(), website='https://skynet.mahaba955.workers.dev/login',
                                                    note='Private. Every password is unique; accounts do not have to change it at first sign-in.',
                                                    accounts=platform + seeder.accounts), indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    main()
