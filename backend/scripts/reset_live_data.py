"""Explicit, backed-up database reset retaining exactly one real platform owner.

Default is a read-only plan. Stop application/scheduled writes before --apply.
Never call from an API route. Use a reviewed release runner with private env.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from app.db.base import Base
from app import models  # noqa: F401
from app.core.config import settings


def reset(connection, owner_id, apply=False):
    if connection.dialect.name != 'postgresql':
        raise ValueError('Reset requires PostgreSQL transaction semantics')
    tables=set(inspect(connection).get_table_names(schema='public'))
    unknown=tables-set(Base.metadata.tables)-{'alembic_version'}
    if unknown:raise ValueError('Unreviewed tables present: '+', '.join(sorted(unknown)))
    metadata=MetaData();metadata.reflect(bind=connection, schema='public')
    users=metadata.tables['public.users']
    owner=connection.execute(select(users).where(users.c.id==owner_id).with_for_update()).mappings().first()
    if not owner or owner['role']!='PLATFORM_ADMIN' or owner['institution_id'] is not None or owner['status']!='ACTIVE':
        raise ValueError('Retained account must be an active institution-free platform admin')
    if not owner['email'] or owner['email'].endswith('@example.test'):
        raise ValueError('A fictional platform account cannot be retained as the real owner')
    counts={name:connection.execute(text('SELECT count(*) FROM '+connection.dialect.identifier_preparer.quote(name))).scalar_one() for name in sorted(tables)}
    if not apply:return dict(apply=False,counts=counts,retained_owner_id=str(owner_id))
    # All affected tables are named explicitly; no CASCADE into unknown schemas.
    names=', '.join(connection.dialect.identifier_preparer.quote(name) for name in sorted(tables-{'alembic_version'}))
    connection.execute(text('SET LOCAL lock_timeout = \'15s\''))
    connection.execute(text('TRUNCATE TABLE '+names+' RESTART IDENTITY'))
    values=dict(owner);values['password_changed_at']=datetime.now(timezone.utc);values['updated_at']=values['password_changed_at']
    connection.execute(users.insert().values(**values))
    now=datetime.now(timezone.utc)
    connection.execute(metadata.tables['public.audit_events'].insert().values(id=uuid.uuid4(),created_at=now,updated_at=now,institution_id=None,actor_id=owner_id,action='platform.data_reset',target_id=str(owner_id),detail='Authorized release reset; retained real platform owner; no fictional production records seeded.'))
    after={name:connection.execute(text('SELECT count(*) FROM '+connection.dialect.identifier_preparer.quote(name))).scalar_one() for name in sorted(tables)}
    assert after['users']==1 and after['institutions']==0
    assert all(total==0 for name,total in after.items() if name not in {'users','audit_events','alembic_version'})
    return dict(apply=True,before=counts,after=after,retained_owner_id=str(owner_id))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host',required=True);parser.add_argument('--expected-database',required=True)
    parser.add_argument('--keep-owner',required=True,type=uuid.UUID);parser.add_argument('--apply',action='store_true')
    parser.add_argument('--backup-manifest',type=Path);parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args();url=settings.DATABASE_URL_UNPOOLED or settings.DATABASE_URL;target=make_url(url)
    if target.host!=args.expected_host or target.database!=args.expected_database:raise SystemExit('Reset target does not match reviewed host/database')
    if args.apply:
        if not args.backup_manifest:raise SystemExit('A verified backup manifest is required')
        manifest=json.loads(args.backup_manifest.read_text(encoding='utf-8'));archive=args.backup_manifest.parent/'live-pre-upgrade.dump'
        if target.host not in {'127.0.0.1','localhost','::1'} and (manifest.get('host')!=target.host or manifest.get('database')!=target.database):raise SystemExit('Backup manifest belongs to a different database target')
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=manifest['sha256']:raise SystemExit('Backup archive is missing or checksum does not match')
    with create_engine(url).begin() as connection:
        if args.apply and connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()!='j2f3a4b5c6d7':raise SystemExit('Reset requires the reviewed release schema revision')
        result=reset(connection,args.keep_owner,args.apply)
    args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Reset applied atomically.' if args.apply else 'Read-only reset plan saved.')


if __name__=='__main__':main()
