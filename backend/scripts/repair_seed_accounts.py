"""Rename generator-owned sample data and repair the identified unassigned QA student.
Passwords are generated in memory and returned only for the four requested checks.
"""
import json
import os
import secrets
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
import seed_demo
from seed_demo import identity
from app.models.user import User
from app.models.academic import Student, Enrollment


def run(host, repair_qa=False, credentials=False):
    root = Path(__file__).resolve().parents[2]
    url = make_url(dotenv_values(root / '.env.local')['DATABASE_URL_UNPOOLED']).set(drivername='postgresql+psycopg', host=host)
    os.environ['DATABASE_URL'] = url.render_as_string(hide_password=False)
    os.environ.setdefault('JWT_SECRET_KEY', 'seed-verification-does-not-use-live-tokens')
    from app.core.security import hash_password
    engine = create_engine(url, connect_args={'connect_timeout':15})
    output = []
    with Session(engine) as db:
        db.execute(text('SELECT pg_advisory_xact_lock(73140926)'))
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == seed_demo.REVISION
        result = seed_demo.seed(db, hash_password(secrets.token_urlsafe(32)+'Aa1!'), date(2026,9,30), rename_existing=True)
        assert result['created'] == {}, 'Expected populated seed; do not create another dataset during repair'
        if repair_qa:
            import uuid
            qa = db.get(User, uuid.UUID('2f45f3d0-b353-49db-8087-1fbf652a3cd2'))
            if qa and qa.username == 'qa.test.student' and qa.institution_id is None:
                qa.institution_id = identity('acacia/institution')
                qa.first_name, qa.last_name = 'Ethan', 'Mwenda'
                # Preserve the existing QA username and password so the tester can sign in again.
                qa.password_changed_at = datetime.now(timezone.utc)
                db.flush()
                profile = db.query(Student).filter_by(user_id=qa.id).first()
                if profile is None:
                    profile = Student(id=identity('qa/student-profile'), institution_id=qa.institution_id, user_id=qa.id, admission_number='ACA-019')
                    db.add(profile); db.flush()
                assert profile.institution_id == qa.institution_id
                enrollment = db.query(Enrollment).filter_by(student_id=profile.id, class_id=identity('acacia/class/0')).first()
                if enrollment is None:
                    db.add(Enrollment(id=identity('qa/enrollment'), institution_id=qa.institution_id, student_id=profile.id, class_id=identity('acacia/class/0'), active=True))
                result['qa_repaired'] = True
        if credentials:
            for key in ['demo/platform','demo/acacia/admin','demo/acacia/teacher1','demo/acacia/student01']:
                user = db.get(User, identity(key))
                password = secrets.token_urlsafe(15)+'Aa2!'
                user.password_hash = hash_password(password)
                user.password_changed_at = datetime.now(timezone.utc)
                user.must_change_password = False
                output.append(dict(full_name=f'{user.first_name} {user.last_name}', username=user.username, role=user.role.value, password=password))
        db.commit()
    engine.dispose()
    return result, output


def verify_live(accounts):
    import httpx
    checks = []
    for account in accounts:
        role = account['role']
        portal = '/student' if role == 'STUDENT' else '/teacher' if role == 'TEACHER' else ''
        paths = {'PLATFORM_ADMIN':['/api/platform/stats','/api/platform/users','/api/platform/usage'],
                 'INSTITUTION_ADMIN':['/api/institution/overview','/api/institution/settings','/api/institution/users'],
                 'TEACHER':['/api/teacher/profile','/api/teaching/classes','/api/teaching/subjects'],
                 'STUDENT':['/api/student/profile','/api/student/subjects','/api/student/attendance','/api/student/assignments']}[role]
        try:
            with httpx.Client(base_url='https://learning-management-system-5nws.onrender.com', timeout=30) as client:
                response = client.post('/api/auth'+portal+'/login', json={'username':account['username'], 'password':account['password']})
                checks.append({'role':role,'path':'login','status':response.status_code})
                if response.status_code != 200: continue
                for path in paths:
                    response = client.get(path)
                    check = {'role':role,'path':path,'status':response.status_code}
                    if response.status_code == 200 and isinstance(response.json(),list): check['records'] = len(response.json())
                    checks.append(check)
        except Exception as error:
            checks.append({'role':role,'error':type(error).__name__})
    return checks


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['validation','production'], required=True)
    args = parser.parse_args()
    try:
        production = args.target == 'production'
        host = 'ep-ancient-unit-b5d1d24x.c-7.us-east-2.aws.neon.tech' if production else 'ep-restless-king-b5mp4w10.c-7.us-east-2.aws.neon.tech'
        result, credentials = run(host, repair_qa=production, credentials=production)
        if production:
            result['target'] = 'Neon production'
            (Path(__file__).resolve().parents[1] / 'SAMPLE_ACCOUNTS.json').write_text(json.dumps(result,indent=2), encoding='utf-8')
        checks = verify_live(credentials) if production else []
        print(json.dumps({'renamed':True,'qa_repaired':result.get('qa_repaired',False),'credentials':credentials,'live_checks':checks}))
    except Exception as error:
        print('Repair failed: '+type(error).__name__, file=sys.stderr)
        raise SystemExit(1)
