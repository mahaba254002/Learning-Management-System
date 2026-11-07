"""File storage for uploads: Cloudflare R2 (S3-compatible) or a local folder.

R2 requests are signed with AWS Signature Version 4 using only the standard
library. Downloads use short-lived signed links, so file bytes never pass
through the API on the way out."""
import hashlib
import hmac
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings

MAX_FILE_BYTES = 10 * 1024 * 1024
LINK_SECONDS = 300

# Extension -> (content type, accepted leading bytes). Office files are zip
# archives (docx/xlsx/pptx) or the older OLE format (doc/xls/ppt).
ZIP, OLE = (b'PK\x03\x04',), (b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',)
FILE_TYPES = {
    'pdf': ('application/pdf', (b'%PDF-',)),
    'doc': ('application/msword', OLE),
    'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', ZIP),
    'ppt': ('application/vnd.ms-powerpoint', OLE),
    'pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', ZIP),
    'xls': ('application/vnd.ms-excel', OLE),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', ZIP),
    'png': ('image/png', (b'\x89PNG\r\n\x1a\n',)),
    'jpg': ('image/jpeg', (b'\xff\xd8\xff',)),
    'jpeg': ('image/jpeg', (b'\xff\xd8\xff',)),
}
# Groups teachers choose from when saying what students may hand in.
SUBMISSION_GROUPS = {'pdf': ('pdf',), 'word': ('doc', 'docx'), 'powerpoint': ('ppt', 'pptx'),
                     'excel': ('xls', 'xlsx'), 'image': ('png', 'jpg', 'jpeg')}
INLINE = {'pdf', 'png', 'jpg', 'jpeg'}


def enabled():
    if settings.STORAGE_BACKEND == 'r2':
        return all((settings.R2_ACCOUNT_ID, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY, settings.R2_BUCKET))
    return settings.STORAGE_BACKEND == 'local'


def require_enabled():
    if not enabled():
        raise HTTPException(503, 'File uploads are not set up yet. Ask the platform administrator to connect file storage.')


def extension(filename):
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def check_file(filename, data, allowed=None):
    """Return the content type, or refuse a file whose name or contents are not an allowed type."""
    ext = extension(filename)
    if ext not in FILE_TYPES or (allowed is not None and ext not in allowed):
        names = ', '.join(sorted(allowed if allowed is not None else FILE_TYPES)).upper()
        raise HTTPException(422, f'Upload one of these file types: {names}')
    if not data:
        raise HTTPException(422, 'The file is empty')
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, 'Use a file of 10 MB or less')
    content_type, signatures = FILE_TYPES[ext]
    if not any(data.startswith(sig) for sig in signatures):
        raise HTTPException(422, f'This file is not a valid .{ext} file')
    return content_type


def clean_name(filename):
    name = os.path.basename(filename.replace('\\', '/')).strip() or 'file'
    name = ''.join(ch for ch in name if ch.isprintable() and ch not in '"<>|:*?')
    return name[-150:]


# --- Cloudflare R2 ---------------------------------------------------------------------

def _host():
    return f'{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com'


def _quote(value, safe='-_.~'):
    return urllib.parse.quote(value, safe=safe)


def _signing_key(secret, day, region, service):
    key = hmac.new(f'AWS4{secret}'.encode(), day.encode(), hashlib.sha256).digest()
    for part in (region, service, 'aws4_request'):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    return key


def sign(method, host, path, query, headers, payload_hash, *, access_key, secret, now, region='auto', service='s3'):
    """AWS Signature V4. Returns (signature, credential scope, signed header names)."""
    stamp, day = now.strftime('%Y%m%dT%H%M%SZ'), now.strftime('%Y%m%d')
    scope = f'{day}/{region}/{service}/aws4_request'
    names = sorted(k.lower() for k in headers)
    lower = {k.lower(): str(v).strip() for k, v in headers.items()}
    canonical_query = '&'.join(f'{_quote(k)}={_quote(v)}' for k, v in sorted(query.items()))
    canonical = '\n'.join([method, _quote(path, safe='/-_.~'), canonical_query,
                           ''.join(f'{n}:{lower[n]}\n' for n in names), ';'.join(names), payload_hash])
    to_sign = '\n'.join(['AWS4-HMAC-SHA256', stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(_signing_key(secret, day, region, service), to_sign.encode(), hashlib.sha256).hexdigest()
    return signature, scope, ';'.join(names)


def presigned_url(method, host, path, *, access_key, secret, now, expires, extra=None, region='auto'):
    query = {'X-Amz-Algorithm': 'AWS4-HMAC-SHA256', 'X-Amz-Credential': f"{access_key}/{now.strftime('%Y%m%d')}/{region}/s3/aws4_request",
             'X-Amz-Date': now.strftime('%Y%m%dT%H%M%SZ'), 'X-Amz-Expires': str(expires), 'X-Amz-SignedHeaders': 'host', **(extra or {})}
    signature, _, _ = sign(method, host, path, query, {'host': host}, 'UNSIGNED-PAYLOAD', access_key=access_key, secret=secret, now=now, region=region)
    query['X-Amz-Signature'] = signature
    return f"https://{host}{_quote(path, safe='/-_.~')}?" + '&'.join(f'{_quote(k)}={_quote(v)}' for k, v in sorted(query.items()))


def _r2_request(method, key, data=b'', content_type=None):
    host, path, now = _host(), f'/{settings.R2_BUCKET}/{key}', datetime.now(timezone.utc)
    payload_hash = hashlib.sha256(data).hexdigest()
    headers = {'host': host, 'x-amz-content-sha256': payload_hash, 'x-amz-date': now.strftime('%Y%m%dT%H%M%SZ')}
    if content_type:
        headers['content-type'] = content_type
    signature, scope, names = sign(method, host, path, {}, headers, payload_hash, access_key=settings.R2_ACCESS_KEY_ID,
                                   secret=settings.R2_SECRET_ACCESS_KEY, now=now)
    headers['authorization'] = f'AWS4-HMAC-SHA256 Credential={settings.R2_ACCESS_KEY_ID}/{scope}, SignedHeaders={names}, Signature={signature}'
    request = urllib.request.Request(f"https://{host}{_quote(path, safe='/-_.~')}", data=data if method == 'PUT' else None, method=method,
                                     headers={k: v for k, v in headers.items() if k != 'host'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as error:
        if method == 'DELETE' and error.code == 404:
            return 404
        raise HTTPException(502, 'File storage did not accept the file. Try again shortly.') from error
    except OSError as error:
        raise HTTPException(502, 'File storage could not be reached. Try again shortly.') from error


# --- Backend-neutral operations -----------------------------------------------------------

def _local_path(key):
    root = Path(settings.LOCAL_STORAGE_DIR).resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise HTTPException(400, 'Invalid file key')
    return path


def put(key, data, content_type):
    require_enabled()
    if settings.STORAGE_BACKEND == 'local':
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    _r2_request('PUT', key, data, content_type)


def delete(key):
    """Best effort: a failed delete leaves an orphan object, never an error for the user."""
    if not enabled():
        return
    try:
        if settings.STORAGE_BACKEND == 'local':
            _local_path(key).unlink(missing_ok=True)
        else:
            _r2_request('DELETE', key)
    except HTTPException:
        pass


def read_local(key):
    return _local_path(key).read_bytes()


def disposition(filename):
    ext = extension(filename)
    ascii_name = filename.encode('ascii', 'ignore').decode() or 'file'
    kind = 'inline' if ext in INLINE else 'attachment'
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{_quote(filename)}"


def download_url(key, filename, content_type):
    """A short-lived link to the file for R2, or None when files are served by the API (local)."""
    require_enabled()
    if settings.STORAGE_BACKEND == 'local':
        return None
    return presigned_url('GET', _host(), f'/{settings.R2_BUCKET}/{key}', access_key=settings.R2_ACCESS_KEY_ID,
                         secret=settings.R2_SECRET_ACCESS_KEY, now=datetime.now(timezone.utc), expires=LINK_SECONDS,
                         extra={'response-content-disposition': disposition(filename), 'response-content-type': content_type})
