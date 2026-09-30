export function assignmentStatus(work, now = Date.now()) {
  if (work.score !== null && work.score !== undefined) return "Graded";
  if (work.submission?.status === "SUBMITTED") return work.submission.is_late ? "Submitted late" : "Submitted";
  if (work.kind === "EXAM") return "Examination";
  if (work.due_at && new Date(work.due_at).getTime() < now) return work.allow_late_submissions ? "Overdue" : "Closed";
  return work.submission ? "Draft" : "Not started";
}

export function attendanceSummary(records) {
  const counts = { PRESENT: 0, LATE: 0, ABSENT: 0, EXCUSED: 0 };
  for (const record of records) if (record.status in counts) counts[record.status] += 1;
  const counted = counts.PRESENT + counts.LATE + counts.ABSENT;
  return { ...counts, total: records.length, percentage: counted ? Math.round((counts.PRESENT + counts.LATE) * 100 / counted) : null };
}

export function formatDateTime(value) {
  return value ? new Date(value).toLocaleString() : "No deadline";
}
