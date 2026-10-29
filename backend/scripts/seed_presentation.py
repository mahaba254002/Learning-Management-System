"""Explicitly requested fictional presentation records, with controlled email routing.

No mail is sent. No records are deleted or renamed. Default rehearses then rolls
back. A nonempty institution database is rejected, including a repeated run.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import secrets
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def populate(db, owner_id, inbox, today):
    from app.models import User, Institution
    from app.models.user import UserRole, UserStatus
    from app.models.institution import InstitutionType, InstitutionStatus
    from app.models.teacher import Teacher, Gender, EmploymentType
    from app.models.academic import AcademicClass, Student, Subject, Enrollment, Attendance, Coursework, Score
    from app.models.pilot import AcademicYear, AcademicPeriod
    from app.models.curriculum import StudyLevel, CatalogueUnit, CourseCompletion
    from app.models.learning import CourseMaterial, Submission
    from app.models.final_grade import FinalGrade
    from app.models.subscription import Subscription
    from app.models.audit import AuditEvent
    from app.services.academic_configuration import template, AcademicConfiguration
    from app.services.final_grades import compute, prepare
    from app.core.security import hash_password

    owner = db.get(User, owner_id)
    assert owner and owner.role == UserRole.PLATFORM_ADMIN and owner.status == UserStatus.ACTIVE
    assert owner.institution_id is None and owner.email and not owner.email.endswith('@example.test')
    assert db.query(Institution).count() == 0, 'This procedure only populates an empty institution database'
    assert db.query(User).count() == 1, 'Unexpected existing accounts; review instead of overwriting'
    original_hash = owner.password_hash
    namespace = uuid.UUID('ab7439cf-b0c2-45be-aeb8-8271e54a260f')
    counts, accounts = Counter(), []
    def add(model, key, **values):
        row = model(id=uuid.uuid5(namespace, key), **values)
        db.add(row)
        counts[model.__tablename__] += 1
        return row
    local, domain = inbox.lower().split('@')
    assert domain == 'gmail.com' and '+' not in local
    def email(label):
        return f'{local}+{label}@{domain}'
    configuration = template('HIGH_SCHOOL')
    bands = [dict(minimum=80,label='A'), dict(minimum=65,label='B'), dict(minimum=50,label='C'), dict(minimum=40,label='D'), dict(minimum=0,label='E')]
    configuration['grading_rules'].update(enabled=True, name='School assessment policy',
        weights=dict(ASSIGNMENT=30, COURSEWORK=0, EXAM=70), pass_percentage=50, bands=bands)
    configuration = AcademicConfiguration.model_validate(configuration).model_dump()
    inst = add(Institution, 'institution', name='Alliance High School', code='AHS',
        type=InstitutionType.HIGH_SCHOOL, status=InstitutionStatus.ACTIVE, country='Kenya',
        address='Kiambu County, Kenya', official_email=email('alliance.office'),
        academic_configuration=configuration, learning_settings=dict(grade_bands=bands))
    db.flush()
    def account(key, first, last, role, student_id=None):
        password = secrets.token_urlsafe(12) + 'aA1!'
        alias = re.sub(r'[^a-z0-9.]', '', f'{first}.{last}'.lower())
        row = add(User, 'user/'+key, institution_id=inst.id, username=f'{alias}.ahs',
            first_name=first, last_name=last, email=email(alias), role=role, status=UserStatus.ACTIVE,
            password_hash=hash_password(password), must_change_password=True,
            student_login_method='STUDENT_ID' if student_id else 'EMAIL', student_login_id=student_id)
        accounts.append(dict(name=f'{first} {last}',role=role.value,email=row.email,
            login=student_id or row.email,password=password,must_change_password=True))
        return row
    admin = account('admin', 'Salim', 'Hassan', UserRole.INSTITUTION_ADMIN)
    teachers = [account('teacher/'+str(i),first,last,UserRole.TEACHER) for i,(first,last) in enumerate([
        ('Grace','Muli'), ('Daniel','Ouma'), ('Faith','Kariuki')])]
    student_names = [('Reed','McDonald'),('Ali','Salim'),('Amani','Otieno'),('Zuri','Kamau'),
        ('Imani','Njeri'),('Baraka','Mwangi'),('Neema','Wanjiku'),('Jabari','Kiptoo'),
        ('Nia','Achieng'),('Kito','Mutua'),('Sarah','Chebet'),('Kevin','Kilonzo')]
    users = [account('student/'+str(i),first,last,UserRole.STUDENT,
        student_id=f'AHS-{today.year}-{i+1:03}' if i%2 else None) for i,(first,last) in enumerate(student_names)]
    db.flush()
    for i,user in enumerate(teachers):
        add(Teacher,'teacher-profile/'+str(i),institution_id=inst.id,user_id=user.id,
            gender=Gender.PREFER_NOT_TO_SAY,date_of_birth=date(1985+i,4,12),
            qualification='Bachelor of Education',specialization=['Mathematics','English','Biology'][i],
            employment_type=EmploymentType.FULL_TIME)
    students = [add(Student,'student-profile/'+str(i),institution_id=inst.id,user_id=user.id,
        admission_number=f'AHS-{today.year}-{i+1:03}') for i,user in enumerate(users)]
    year = add(AcademicYear,'year',institution_id=inst.id,name=str(today.year),
        start_date=date(today.year,1,1),end_date=date(today.year,12,31),status='ACTIVE')
    levels = [add(StudyLevel,'level/'+str(i),institution_id=inst.id,code=f'F{i+3}',name=f'Form {i+3}',position=i+3) for i in range(2)]
    db.flush()
    periods = [add(AcademicPeriod,'period/'+str(i),institution_id=inst.id,year_id=year.id,name=f'Term {i+1}',
        start_date=date(today.year,1+i*4,1),end_date=date(today.year,4+i*4,30 if i==0 else 31)) for i in range(3)]
    groups = [add(AcademicClass,'class/'+str(i),institution_id=inst.id,name=name,academic_year=str(today.year),
        supervisor_id=teachers[i].id,level_id=levels[i].id) for i,name in enumerate(['Form 3 West','Form 4 East'])]
    add(Subscription,'subscription',institution_id=inst.id,monthly_fee=0,next_due_date=today+timedelta(days=30),
        grace_days=5,enforcement_enabled=False,manually_frozen=False,support_email=inbox)
    db.flush()
    subjects=[]
    lessons = [
        ('Mathematics','Linear equations','Solve 3x + 5 = 20. Show each step and verify the result.','Subtract 5 to get 3x = 15; divide by 3 to get x = 5.'),
        ('English','Evidence in a paragraph','Write a paragraph explaining a benefit of trees at school.','Trees shade the playground, keeping the ground cool and making outdoor breaks more comfortable.'),
        ('Biology','Water cycle','Explain evaporation, condensation and precipitation.','Evaporation forms water vapour. Cooling causes condensation. Water returns to the surface as precipitation.')]
    for ci,group in enumerate(groups):
        cohort=students[ci*6:(ci+1)*6]
        for student in cohort:
            add(Enrollment,f'enrollment/{student.id}',institution_id=inst.id,class_id=group.id,student_id=student.id,active=True)
        for sj,(name,topic,question,answer) in enumerate(lessons):
            unit=add(CatalogueUnit,f'unit/{ci}/{sj}',institution_id=inst.id,level_id=levels[ci].id,
                code=f'F{ci+3}-{["MAT","ENG","BIO"][sj]}',name=name)
            db.flush()
            subject=add(Subject,f'subject/{ci}/{sj}',institution_id=inst.id,class_id=group.id,name=name,
                teacher_id=teachers[sj].id,catalogue_id=unit.id,period_id=periods[2].id,registration_mode='COHORT')
            subjects.append((subject,cohort))
            db.flush()
            add(CourseMaterial,f'material/{ci}/{sj}',institution_id=inst.id,subject_id=subject.id,
                title=topic+' - class notes',body=answer+'\nPractice: '+question,published=True)
            works=[]
            for kind,title,maximum in [('ASSIGNMENT','Continuous assessment',30),('EXAM','End-term assessment',70)]:
                work=add(Coursework,f'work/{ci}/{sj}/{kind}',institution_id=inst.id,subject_id=subject.id,
                    period_id=periods[2].id,title=topic+' - '+title,instructions=question,kind=kind,max_score=maximum,
                    due_at=datetime.combine(today-timedelta(days=3),datetime.min.time(),tzinfo=timezone.utc),
                    published=True,grades_released=True,grading_bands=bands)
                works.append((work,maximum))
            add(Coursework,f'work/{ci}/{sj}/open',institution_id=inst.id,subject_id=subject.id,period_id=periods[2].id,
                title=topic+' - practice exercise',instructions=question,kind='COURSEWORK',max_score=20,
                due_at=datetime.combine(today+timedelta(days=7),datetime.min.time(),tzinfo=timezone.utc),published=True)
            db.flush()
            for si,student in enumerate(cohort):
                for work,maximum in works:
                    add(Submission,f'submission/{work.id}/{student.id}',institution_id=inst.id,coursework_id=work.id,
                        student_id=student.id,answer=answer,status='SUBMITTED',submitted_at=work.due_at-timedelta(days=1))
                    add(Score,f'score/{work.id}/{student.id}',institution_id=inst.id,coursework_id=work.id,student_id=student.id,
                        score=round(maximum*(0.35+((si+sj+ci)%6)*0.10),2),feedback='Review the class notes and explain each step fully.')
        previous=today-timedelta(days=1)
        days=[]
        while len(days)<10:
            if previous.weekday()<5: days.append(previous)
            previous-=timedelta(days=1)
        for di,day in enumerate(days):
            for si,student in enumerate(cohort):
                add(Attendance,f'attendance/{ci}/{di}/{si}',institution_id=inst.id,class_id=group.id,scope_key='class',
                    day=day,student_id=student.id,status='ABSENT' if (di+si)%13==0 else 'LATE' if (di+si)%11==0 else 'PRESENT')
    db.flush()
    for subject,cohort in subjects:
        prepared=prepare(db,subject,[s.id for s in cohort])
        for student in cohort:
            calculated=compute(db,subject,student.id,prepared=prepared)
            assert calculated['ready'],calculated['issues']
            add(FinalGrade,f'final/{subject.id}/{student.id}',institution_id=inst.id,subject_id=subject.id,
                student_id=student.id,scope='ALL',source_digest=calculated['source_digest'],result=calculated['result'],released=True)
            add(CourseCompletion,f'completion/{subject.id}/{student.id}',institution_id=inst.id,subject_id=subject.id,
                student_id=student.id,outcome='PASSED' if calculated['result']['passed'] else 'FAILED',credits=0,released=True)
    add(AuditEvent,'audit',institution_id=inst.id,actor_id=owner.id,action='presentation.seeded',target_id=str(inst.id),
        detail='Owner requested fictional presentation records in production. Names and academic activity are synthetic; email aliases route to the owner. No mail or payments sent.')
    db.flush()
    assert owner.password_hash==original_hash
    assert db.query(User).filter_by(role=UserRole.PLATFORM_ADMIN).count()==1
    assert all(a['email'].endswith('@gmail.com') for a in accounts)
    return dict(institution_id=str(inst.id),institution=inst.name,created=dict(counts),accounts=accounts,
        fictional=True,controlled_inbox=inbox,mail_sent=False,owner_preserved=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file',required=True)
    parser.add_argument('--expected-host',required=True)
    parser.add_argument('--owner',type=uuid.UUID,required=True)
    parser.add_argument('--controlled-inbox',required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--backup-checkpoint',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    load_dotenv(args.env_file,override=True)
    from app.core.config import settings
    from app import models  # noqa: F401
    url=settings.DATABASE_URL_UNPOOLED or settings.DATABASE_URL
    target=make_url(url)
    assert target.host==args.expected_host and target.database=='neondb','Unexpected database target'
    assert re.fullmatch(r'[A-Za-z0-9.]+@gmail\.com',args.controlled_inbox),'Use the owner-controlled Gmail inbox'
    if args.apply:
        assert args.backup_checkpoint,'An existing pre-import data checkpoint is required'
        checkpoint=json.loads(args.backup_checkpoint.read_text(encoding='utf-8'))
        assert checkpoint['schema_revision']=='j2f3a4b5c6d7'
        assert checkpoint['counts']['institutions']==0 and checkpoint['counts']['users']==1
        assert checkpoint['tables']['users'][0]['id']==str(args.owner),'Backup owner mismatch'
    engine=create_engine(url,hide_parameters=True,connect_args={
        'connect_timeout':30,'keepalives':1,'keepalives_idle':30,
        'keepalives_interval':10,'keepalives_count':3,
        'application_name':'skynet-presentation-import'})
    with Session(engine) as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='j2f3a4b5c6d7'
        db.execute(text("SELECT pg_advisory_xact_lock(7281029)"))
        result=populate(db,args.owner,args.controlled_inbox,date.today())
        result['applied']=args.apply
        # Save credentials privately before committing, so a disk error rolls back.
        args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
        if args.apply: db.commit()
        else: db.rollback()
    print(('Applied' if args.apply else 'Rehearsed and rolled back')+' fictional presentation data; private report saved.')
    print(json.dumps(result['created'],indent=2))


if __name__=='__main__':
    main()
