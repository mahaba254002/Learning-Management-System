import test from 'node:test';
import assert from 'node:assert/strict';
import { apiRequest } from '../src/api/client.js';
import { recordRevision } from '../src/pages/teacher/recordRevision.js';

test('concurrent expired requests share one renewal and retry once with rotated CSRF', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document;
  globalThis.document = { cookie: 'csrf_token=before' };
  let renewals = 0;
  const calls = [];
  const attempts = {};
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options });
    if (path === '/api/auth/refresh') {
      renewals += 1; globalThis.document.cookie = 'csrf_token=after';
      return new Response('{}', { status: 200 });
    }
    attempts[path] = (attempts[path] || 0) + 1;
    return new Response(JSON.stringify(attempts[path] === 1 ? { detail: 'Session expired' } : { saved: true }), { status: attempts[path] === 1 ? 401 : 200 });
  };
  try {
    const raw = new Blob(['student-file']);
    const values = await Promise.all([
      apiRequest('/api/test/a'), apiRequest('/api/test/b', { method: 'PUT', body: { answer: 'unfinished' } }),
      apiRequest('/api/test/c', { method: 'POST', rawBody: raw }),
    ]);
    assert.equal(renewals, 1); assert.ok(values.every(v => v.saved));
    const retry = calls.filter(c => c.path === '/api/test/b')[1];
    assert.equal(retry.options.headers['X-CSRF-Token'], 'after');
    assert.equal(retry.options.body, JSON.stringify({ answer: 'unfinished' }));
    assert.equal(calls.filter(c => c.path === '/api/test/c')[1].options.body, raw);
  } finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; }
});

test('wrong login passwords are never retried through session renewal', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document;
  globalThis.document = { cookie: '' }; const calls = [];
  globalThis.fetch = async path => { calls.push(path); return new Response('{"detail":"Invalid sign-in details"}', { status: 401 }); };
  try {
    await assert.rejects(apiRequest('/api/auth/login', { method: 'POST', body: { email: 'test@example.test', password: 'wrong' } }), error => error.status === 401);
    assert.deepEqual(calls, ['/api/auth/login']);
  } finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; }
});

test('unavailable renewal preserves a service error and does not replay mutations', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document;
  globalThis.document = { cookie: 'csrf_token=test' }; const calls = [];
  globalThis.fetch = async path => {
    calls.push(path);
    return new Response(JSON.stringify({ detail: 'Unavailable' }), { status: path === '/api/auth/refresh' ? 503 : 401 });
  };
  try {
    await assert.rejects(apiRequest('/api/test/write', { method: 'PUT', body: {} }), error => error.status === 503);
    assert.deepEqual(calls, ['/api/test/write', '/api/auth/refresh']);
  } finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; }
});

test('a second 401 is surfaced instead of renewing in a loop', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document;
  globalThis.document = { cookie: 'csrf_token=test' }; const calls = [];
  globalThis.fetch = async path => { calls.push(path); return new Response('{}', { status: path === '/api/auth/refresh' ? 200 : 401 }); };
  try {
    await assert.rejects(apiRequest('/api/test/revoked'), error => error.status === 401);
    assert.equal(calls.length, 3);
  } finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; }
});

test('register revisions are deterministic and retain exact server timestamps', () => {
  assert.equal(recordRevision([{ id: 'b', updated_at: '2026-01-01T01:02:03.123456+00:00' }, { id: 'a', updated_at: '2026-01-01T00:00:00' }]),
    '[["a","2026-01-01T00:00:00"],["b","2026-01-01T01:02:03.123456+00:00"]]');
});

test('CSRF rotation in another tab retries only a request rejected before mutation', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document;
  globalThis.document = { cookie: 'csrf_token=before' }; const attempts = [];
  globalThis.fetch = async (path, options) => {
    attempts.push(options.headers['X-CSRF-Token']);
    if (attempts.length === 1) { globalThis.document.cookie = 'csrf_token=after'; return new Response('{"detail":"CSRF token missing or invalid"}', { status: 403 }); }
    return new Response('{"saved":true}', { status: 200 });
  };
  try { assert.equal((await apiRequest('/api/test/save', { method: 'PUT', body: {} })).saved, true); assert.deepEqual(attempts, ['before', 'after']); }
  finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; }
});

test('an expired CSRF cookie opens recovery without replaying an unauthenticated write', async () => {
  const previousFetch = globalThis.fetch, previousDocument = globalThis.document, previousWindow = globalThis.window;
  globalThis.document = { cookie: '' }; const events = []; let attempts = 0;
  globalThis.window = { dispatchEvent: event => events.push(event.type) };
  globalThis.fetch = async () => { attempts++; return new Response('{"detail":"CSRF token missing or invalid"}', { status: 403 }); };
  try {
    await assert.rejects(apiRequest('/api/test/save', { method: 'PUT', body: {} }), error => error.status === 403);
    assert.equal(attempts, 1); assert.deepEqual(events, ['skynet:session-ended']);
  } finally { globalThis.fetch = previousFetch; globalThis.document = previousDocument; globalThis.window = previousWindow; }
});
