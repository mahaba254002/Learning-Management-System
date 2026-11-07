import test from 'node:test';
import assert from 'node:assert/strict';
import { addDays, attendanceLink, isoWeekday, slotRuns, weekStart } from '../src/pages/timetable/timetableFormat.js';

test('works out ISO weekdays and the start of the week', () => {
  assert.equal(isoWeekday('2026-11-09'), 1);
  assert.equal(isoWeekday('2026-11-08'), 7);
  assert.equal(weekStart('2026-11-08'), '2026-11-02');
  assert.equal(weekStart('2026-11-09'), '2026-11-09');
  assert.equal(addDays('2026-12-30', 3), '2027-01-02');
});

test('a period with no days set runs every teaching day', () => {
  assert.equal(slotRuns({ weekdays: [] }, 3), true);
  assert.equal(slotRuns({ weekdays: [6] }, 3), false);
});

test('attendance link carries the register, date and lesson end', () => {
  const url = attendanceLink({ subject_id: 'abc', date: '2026-11-09', end_time: '08:40' });
  assert.equal(url, '/teacher/attendance?register=subject%3Aabc&day=2026-11-09&lesson_end=08%3A40');
});
