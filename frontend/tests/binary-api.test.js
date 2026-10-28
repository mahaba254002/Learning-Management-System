import test from 'node:test';
import assert from 'node:assert/strict';
import { apiRequest, setWorkspaceAccess } from '../src/api/client.js';

test('binary upload and download keep CSRF, cookies and unmodified bytes', async () => {
  const originalFetch = globalThis.fetch;
  const originalDocument = globalThis.document;
  globalThis.document = { cookie: 'csrf_token=test-csrf' };
  let sent;
  globalThis.fetch = async (path, options) => { sent = { path, ...options }; return new Response(new Blob(['signed-backup'])); };
  try {
    const file = new Blob(['file-contents']);
    const result = await apiRequest('/api/platform/backups/restore/execute', { method: 'POST', rawBody: file, responseType: 'blob', extraHeaders: { 'X-Restore-Token': 'reviewed-token' } });
    assert.equal(sent.body, file);
    assert.equal(sent.credentials, 'include');
    assert.equal(sent.headers['X-CSRF-Token'], 'test-csrf');
    assert.equal(sent.headers['X-Restore-Token'], 'reviewed-token');
    assert.equal(await result.text(), 'signed-backup');
  } finally { globalThis.fetch = originalFetch; globalThis.document = originalDocument; }
});

test('read-only workspaces cannot bypass mutation blocking using binary uploads', async () => {
  setWorkspaceAccess({ read_only: true, token: 'read-only-grant' });
  try {
    await assert.rejects(apiRequest('/api/platform/backups/restore/execute', { method: 'POST', rawBody: new Blob(['file']) }), error => error.status === 403);
  } finally { setWorkspaceAccess(null); }
});
