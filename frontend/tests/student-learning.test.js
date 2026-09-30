import test from 'node:test';
import assert from 'node:assert/strict';
import { assignmentStatus, attendanceSummary } from '../src/pages/student/learningFormat.js';

test('attendance excludes excused sessions and includes late arrivals', () => {
  const result = attendanceSummary(['PRESENT', 'LATE', 'ABSENT', 'EXCUSED'].map(status => ({ status })));
  assert.equal(result.percentage, 67);
  assert.equal(result.total, 4);
  assert.equal(attendanceSummary([]).percentage, null);
  assert.equal(attendanceSummary([{ status: 'EXCUSED' }]).percentage, null);
});

test('zero marks and final receipts take precedence over deadline status', () => {
  const work = { due_at: '2026-01-01T00:00:00Z', allow_late_submissions: false };
  const now = Date.parse('2026-02-01T00:00:00Z');
  assert.equal(assignmentStatus(work, now), 'Closed');
  assert.equal(assignmentStatus({ ...work, allow_late_submissions: true }, now), 'Overdue');
  assert.equal(assignmentStatus({ ...work, score: 0 }, now), 'Graded');
  assert.equal(assignmentStatus({ ...work, submission: { status: 'SUBMITTED', is_late: true } }, now), 'Submitted late');
  assert.equal(assignmentStatus({ submission: { status: 'DRAFT' } }, now), 'Draft');
  assert.equal(assignmentStatus({}, now), 'Not started');
});
