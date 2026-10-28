import test from 'node:test';
import assert from 'node:assert/strict';
import { studentLoginSchema } from '../src/pages/student/studentLoginSchema.js';

test('student login accepts assigned email or ID and preserves the password', () => {
  for (const email of ['student@example.test', 'ALLIANCE-002', '2026/001', '0042']) {
    const result = studentLoginSchema.parse({ email, password: ' Password-123! ', remember_me: false });
    assert.equal(result.email, email);
    assert.equal(result.password, ' Password-123! ');
  }
});

test('student login rejects empty, malformed or overlong identifiers', () => {
  for (const email of ['', 'bad@address', 'has spaces', 'x'.repeat(61), '<script>']) {
    assert.equal(studentLoginSchema.safeParse({ email, password: 'password' }).success, false);
  }
});
