import test from 'node:test';
import assert from 'node:assert/strict';
import { describe, isTemporary, retryDelay, shouldRetry } from '../src/api/errors.js';

test('only connection and start-up failures are retried', () => {
  assert.equal(isTemporary({ status: 0 }), true);
  assert.equal(isTemporary({ status: 503 }), true);
  assert.equal(isTemporary({ status: 500 }), false);
  assert.equal(isTemporary({ status: 403 }), false);
  assert.equal(shouldRetry(5, { status: 0 }), true);
  assert.equal(shouldRetry(6, { status: 0 }), false);
  assert.equal(shouldRetry(0, { status: 404 }), false);
  assert.deepEqual([0, 1, 2, 3, 4].map(retryDelay), [2000, 4000, 8000, 15000, 15000]);
});

test('messages match what happened', () => {
  assert.equal(describe({ status: 0 }).kind, 'offline');
  assert.match(describe({ status: 0 }, { saving: true }).text, /may not have been saved/);
  assert.doesNotMatch(describe({ status: 0 }).text, /saved/);
  assert.equal(describe({ status: 403, message: 'Student attendance is not enabled for this institution.' }).kind, 'feature');
  assert.equal(describe({ status: 403, message: 'You do not have permission to perform this action' }).kind, 'denied');
  assert.equal(describe({ status: 403, message: 'You do not have permission to perform this action' }, { saving: true }).text, "You don't have permission to do this.");
  assert.equal(describe({ status: 409, message: 'This lesson clashes' }).text, 'This lesson clashes');
});
