/** Formatting shared by the e-learning pages. */
export const FILE_GROUPS = {
  pdf: { label: "PDF", accept: ".pdf" },
  word: { label: "Word", accept: ".doc,.docx" },
  powerpoint: { label: "PowerPoint", accept: ".ppt,.pptx" },
  excel: { label: "Excel", accept: ".xls,.xlsx" },
  image: { label: "Image (PNG or JPG)", accept: ".png,.jpg,.jpeg" },
};
export const ALL = Object.values(FILE_GROUPS).map(g => g.accept).join(",");
export const MAX_BYTES = 10 * 1024 * 1024;

export function fileSize(bytes) {
  if (!bytes) return "0 KB";
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function acceptFor(groups) {
  return groups?.length ? groups.map(g => FILE_GROUPS[g]?.accept).filter(Boolean).join(",") : ALL;
}

export const STATUS = { TODO: "To do", DONE: "Done", OVERDUE: "Overdue", MISSED: "Missed", UPCOMING: "Not open yet", OPEN: "Open", CLOSED: "Closed" };

export function shortDate(value) {
  return value ? new Date(value).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "";
}

export function kindLabel(item) {
  if (item.delivery === "QUIZ") return "Quiz";
  return { EXAM: "Exam", COURSEWORK: "CAT" }[item.kind] || "Assignment";
}

export function portalBase(pathname) {
  return pathname.startsWith("/institution") ? "/institution" : "/teacher";
}

export function studentWorkLink(item) {
  return item.delivery === "QUIZ" ? `/student/quizzes/${item.id}` : `/student/assignments/${item.id}`;
}

/** A datetime-local input value in the browser's own time zone. */
export function inputDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}
