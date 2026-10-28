import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
import pytest
from test_teaching import env
from test_administration import platform
from app.core import rate_limit as limiter
from app.core.security import hash_password
from app.models.academic import AcademicClass
from app.models.audit import AuditEvent
from app.models.user import UserRole
from app.services import backups
from app.models.subscription import Subscription, SubscriptionPayment
from datetime import date, timedelta
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def no_external_rate_limit(monkeypatch):
    monkeypatch.setattr(limiter.redis_client, 'incr', lambda key: 1)
    monkeypatch.setattr(limiter.redis_client, 'expire', lambda *args: True)


def export(env, actor=None, groups=None):
    actor = actor or platform(env)
    c = env['as_user'](actor)
    result = c.post('/api/platform/backups/institution', json={'institution_id': str(env['cls'].institution_id), 'groups': groups or ['learning', 'attendance']})
    assert result.status_code == 200, result.text
    return c, actor, result.content


def plan(env, raw, actor):
    result = env['as_user'](actor).post('/api/platform/backups/restore/preview', content=raw, headers={'Content-Type': 'application/octet-stream'})
    assert result.status_code == 200, result.text
    return result.json()


def grant(env, actor, plan):
    actor.password_hash = hash_password('Restore-password-123!'); env['db'].commit()
    result = env['as_user'](actor).post('/api/platform/backups/restore/authorize', json={'plan_token': plan['plan_token'], 'confirmation': plan['confirmation'], 'password': 'Restore-password-123!'})
    assert result.status_code == 200, result.text
    return result.json()['restore_token']


@pytest.mark.parametrize('who', ['admin', 'teacher', 'pupil'])
def test_backup_and_restore_are_platform_only(env, who):
    c = env['as_user'](env[who])
    assert c.get('/api/platform/backups/capabilities').status_code == 403
    assert c.post('/api/platform/backups/institution', json={'institution_id': str(env['cls'].institution_id), 'groups': ['people']}).status_code == 403
    assert c.post('/api/platform/backups/restore/preview', content=b'bad').status_code == 403


def test_export_is_scoped_and_signed_without_active_invitation_tokens(env):
    c, actor, raw = export(env)
    assert c.get('/api/platform/audit-logs?action=backup.institution_exported').json()['total'] == 1
    manifest, payload = backups.open_archive(raw)
    data = json.loads(payload)
    assert manifest['kind'] == 'institution' and manifest['groups'] == ['academics', 'attendance', 'learning', 'people']
    assert all(user['role'] != 'PLATFORM_ADMIN' for user in data['tables']['users'])
    assert all(user['institution_id'] == str(env['cls'].institution_id) for user in data['tables']['users'])
    assert all(teacher['invited_from'] is None for teacher in data['tables']['teachers'])
    assert str(env['other_cls'].id) not in payload.decode()
    assert c.post('/api/platform/backups/institution', json={'institution_id': str(env['cls'].institution_id), 'groups': ['secrets']}).status_code == 422


def test_tampered_archive_and_untrusted_files_are_rejected(env):
    c, actor, raw = export(env)
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        manifest = zipped.read('manifest.json'); payload = zipped.read('data.json')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as zipped:
        zipped.writestr('manifest.json', manifest); zipped.writestr('data.json', payload.replace(b'Form 1', b'Hacked'))
    for content in [b'not zip', output.getvalue(), b'{"role":"PLATFORM_ADMIN"}']:
        assert c.post('/api/platform/backups/restore/preview', content=content).status_code == 400


def test_review_then_restore_merges_records_and_invalidates_sessions(env):
    c, actor, raw = export(env)
    env['cls'].name = 'Wrong name'; env['db'].commit()
    review = plan(env, raw, actor)
    assert review['counts']['academic_classes'] == 1 and review['confirmation'] == 'RESTORE S0'
    token = grant(env, actor, review)
    result = env['as_user'](actor).post('/api/platform/backups/restore/execute', content=raw, headers={'X-Restore-Token': token})
    assert result.status_code == 200, result.text
    env['db'].refresh(env['cls']); env['db'].refresh(env['pupil'])
    assert env['cls'].name == 'Form 1' and env['pupil'].password_changed_at is not None
    assert env['db'].get(AcademicClass, env['other_cls'].id).name == 'Private class'
    assert env['db'].query(AuditEvent).filter_by(action='backup.institution_restored').count() == 1
    assert env['client'].post('/api/platform/backups/restore/execute', content=raw, headers={'X-Restore-Token': token}).status_code == 409


def test_wrong_password_confirmation_stale_review_and_changed_file(env):
    c, actor, raw = export(env)
    review = plan(env, raw, actor)
    actor.password_hash = hash_password('Restore-password-123!'); env['db'].commit()
    body = {'plan_token': review['plan_token'], 'confirmation': review['confirmation'], 'password': 'wrong'}
    assert c.post('/api/platform/backups/restore/authorize', json=body).status_code == 401
    assert c.post('/api/platform/backups/restore/authorize', json={**body, 'password': 'Restore-password-123!', 'confirmation': 'wrong'}).status_code == 422
    token = grant(env, actor, review)
    assert c.post('/api/platform/backups/restore/execute', content=raw + b'x', headers={'X-Restore-Token': token}).status_code == 409
    env['cls'].name = 'Concurrent update'; env['db'].commit()
    result = c.post('/api/platform/backups/restore/execute', content=raw, headers={'X-Restore-Token': token})
    assert result.status_code == 409 and env['cls'].name == 'Concurrent update'


def test_signed_cross_tenant_or_platform_user_payload_is_refused(env):
    c, actor, raw = export(env)
    manifest, payload = backups.open_archive(raw)
    data = json.loads(payload)
    data['tables']['users'][0]['institution_id'] = str(env['other_cls'].institution_id)
    bad = backups.archive(backups.canonical(data), 'institution', institution_id=manifest['institution_id'], institution_code=manifest['institution_code'])
    assert c.post('/api/platform/backups/restore/preview', content=bad).status_code == 400
    data['tables']['users'][0]['institution_id'] = manifest['institution_id']
    data['tables']['users'][0]['role'] = 'PLATFORM_ADMIN'
    bad = backups.archive(backups.canonical(data), 'institution', institution_id=manifest['institution_id'], institution_code=manifest['institution_code'])
    assert c.post('/api/platform/backups/restore/preview', content=bad).status_code == 400


def test_restore_token_cannot_be_used_by_another_owner(env):
    c, actor, raw = export(env)
    review = plan(env, raw, actor)
    other = env['user']('second-owner', UserRole.PLATFORM_ADMIN); other.institution_id = None
    env['db'].commit()
    assert env['as_user'](other).post('/api/platform/backups/restore/authorize', json={'plan_token': review['plan_token'], 'password': 'no', 'confirmation': review['confirmation']}).status_code == 401


def test_audit_filter_keeps_tenant_boundary_and_metadata(env):
    c = env['as_user'](env['admin'])
    assert c.put('/api/institution/settings', json={'name': 'Edited school', 'country': 'Kenya'}, headers={'X-Forwarded-For': '1.2.3.4'}).status_code == 200
    data = c.get('/api/institution/audit-logs?action=institution.settings_updated').json()
    assert data['total'] == 1 and 'institution.settings_updated' in data['action_types']
    event = data['items'][0]
    assert event['request_method'] == 'PUT' and event['request_path'] == '/api/institution/settings'
    assert event['ip_address'] is None  # TestClient is not a real IP; untrusted forwarding header is ignored.
    assert env['as_user'](env['other_pupil']).get('/api/institution/audit-logs').status_code == 403


def test_directory_includes_contact_admin_due_date_and_status_filter(env):
    c = env['as_user'](platform(env))
    env['institutions'][0].official_email = 'office@example.test'; env['institutions'][0].phone = '+254700000001'; env['db'].commit()
    data = c.get('/api/platform/institution-directory?search=office%40example.test&status=ACTIVE').json()
    assert data['total'] == 1
    row = data['items'][0]
    assert row['phone'] == '+254700000001' and row['admins'][0]['name'] == 'admin Test'
    assert row['next_due_date'] is None


def test_existing_financial_history_cannot_be_overwritten_and_merge_rolls_back(env):
    actor = platform(env)
    tenant = env['cls'].institution_id
    env['db'].add(Subscription(institution_id=tenant, monthly_fee=2500))
    payment = SubscriptionPayment(institution_id=tenant, amount=2500, reference='Paid-1', paid_on=date.today(), next_due_date=date.today()+timedelta(days=30), recorded_by=str(actor.id))
    env['db'].add(payment); env['db'].commit()
    c, actor, raw = export(env, actor, ['billing'])
    payment.amount = 5000
    env['cls'].name = 'Newer class name'
    env['db'].commit()
    review = plan(env, raw, actor)
    token = grant(env, actor, review)
    result = env['as_user'](actor).post('/api/platform/backups/restore/execute', content=raw, headers={'X-Restore-Token': token})
    assert result.status_code == 409 and 'Financial history' in result.json()['detail']
    assert env['cls'].name == 'Newer class name' and payment.amount == 5000


def test_full_recovery_cannot_target_running_database_or_pooled_alias(monkeypatch):
    monkeypatch.setattr(backups.settings, 'DATABASE_URL', 'postgresql+psycopg://example@ep-test-pooler.example/db')
    for target in ['postgresql+psycopg://example@ep-test-pooler.example/db', 'postgresql+psycopg://example@ep-test.example/db']:
        monkeypatch.setattr(backups.settings, 'RESTORE_DATABASE_URL', target)
        with pytest.raises(HTTPException) as error:
            backups.recovery_engine()
        assert error.value.status_code == 409


def test_production_requires_backup_key_and_missing_tools_fail_closed(env, monkeypatch):
    monkeypatch.setattr(backups.settings, 'ENVIRONMENT', 'production')
    monkeypatch.setattr(backups.settings, 'BACKUP_SIGNING_KEY', '')
    with pytest.raises(HTTPException) as error: backups.signing_key()
    assert error.value.status_code == 503
    monkeypatch.setattr(backups, 'postgres_tool', lambda name: None)
    with pytest.raises(HTTPException) as error: backups.full_backup()
    assert error.value.status_code == 503


def test_platform_archives_are_staged_to_files_and_tampered_payloads_are_removed(env, monkeypatch, tmp_path):
    from pathlib import Path
    monkeypatch.setattr(backups.tempfile, 'tempdir', str(tmp_path))
    raw = backups.archive(b'PGDMP-test-snapshot', 'platform')
    source = tmp_path / 'upload.zip'; source.write_bytes(raw)
    manifest, payload = backups.open_archive(source)
    assert isinstance(payload, Path) and payload.read_bytes() == b'PGDMP-test-snapshot'
    payload.unlink()
    assert set(tmp_path.iterdir()) == {source}
    with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
        manifest_bytes = zipped.read('manifest.json')
    with zipfile.ZipFile(source, 'w') as zipped:
        zipped.writestr('manifest.json', manifest_bytes)
        zipped.writestr('data.dump', b'tampered data')
    with pytest.raises(HTTPException) as error: backups.open_archive(source)
    assert error.value.status_code == 400 and set(tmp_path.iterdir()) == {source}


def test_full_download_streams_and_removes_temporary_snapshot(env, monkeypatch, tmp_path):
    snapshot = tmp_path / 'snapshot.zip'; snapshot.write_bytes(b'fake-backup-for-response-test')
    monkeypatch.setattr(backups, 'full_backup', lambda: snapshot)
    c = env['as_user'](platform(env))
    result = c.post('/api/platform/backups/platform')
    assert result.status_code == 200 and result.content == b'fake-backup-for-response-test'
    assert 'skynet-platform-backup.zip' in result.headers['content-disposition']
    assert result.headers['cache-control'] == 'no-store' and not snapshot.exists()
