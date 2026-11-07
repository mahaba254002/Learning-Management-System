export const DAYS = { 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday" };
export const SHORT_DAYS = { 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun" };

export const STATUS_LABELS = {
  SCHEDULED: "", CANCELLED: "Cancelled", MOVED_AWAY: "Moved", MOVED_IN: "Moved here", SUBSTITUTE: "Covered by another teacher", COVERING: "You are covering",
};

/** Today's date in Nairobi as YYYY-MM-DD. */
export function kenyaToday() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Nairobi" });
}

/** ISO weekday (1 Monday ... 7 Sunday) of a YYYY-MM-DD date. */
export function isoWeekday(day) {
  const value = new Date(`${day}T00:00:00Z`).getUTCDay();
  return value === 0 ? 7 : value;
}

export function addDays(day, count) {
  const value = new Date(`${day}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + count);
  return value.toISOString().slice(0, 10);
}

/** The Monday on or before a date. */
export function weekStart(day) {
  return addDays(day, 1 - isoWeekday(day));
}

/** Periods that run on a weekday: an empty list means every teaching day. */
export function slotRuns(slot, weekday) {
  return !slot.weekdays?.length || slot.weekdays.includes(weekday);
}

export function longDate(day) {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-KE", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long" });
}

/** Link that opens the subject register for a lesson, with the lesson end time for the late rule. */
export function attendanceLink(lesson) {
  const params = new URLSearchParams({ register: `subject:${lesson.subject_id}`, day: lesson.date, lesson_end: lesson.end_time });
  return `/teacher/attendance?${params}`;
}
