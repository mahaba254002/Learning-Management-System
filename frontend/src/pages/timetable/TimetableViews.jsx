import { Link } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { DAYS, STATUS_LABELS, attendanceLink, kenyaToday, slotRuns } from "./timetableFormat";
import "./Timetable.css";

/** Weekly grid for one class: lesson periods down the side, teaching days across. */
export function WeekGrid({ data, renderCell }) {
  const days = data.weekdays;
  return <div className="table-wrapper"><table className="timetable-grid">
    <caption className="records-hidden">{data.class_name} timetable</caption>
    <thead><tr><th scope="col">Period</th>{days.map(d => <th key={d} scope="col">{DAYS[d]}</th>)}</tr></thead>
    <tbody>{data.slots.map(slot => <tr key={slot.id} className={slot.is_break ? "timetable-break" : undefined}>
      <th scope="row">{slot.label}<span className="timetable-time">{slot.start_time}–{slot.end_time}</span></th>
      {days.map(day => {
        if (!slotRuns(slot, day)) return <td key={day} className="timetable-off" aria-label="Not running" />;
        if (slot.is_break) return <td key={day} />;
        const lessons = data.entries.filter(e => e.slot_id === slot.id && e.weekday === day);
        return <td key={day}>{renderCell ? renderCell(slot, day, lessons) : lessons.map(e => <div key={e.id} className="timetable-lesson">
          <strong>{e.subject_name}</strong><small>{e.teacher_name}</small></div>)}</td>;
      })}
    </tr>)}</tbody>
  </table></div>;
}

export function LessonItem({ lesson, teacher }) {
  const today = kenyaToday();
  const flag = STATUS_LABELS[lesson.status];
  const canMark = teacher && lesson.date <= today && ["SCHEDULED", "MOVED_IN", "COVERING"].includes(lesson.status);
  return <div className={`timetable-item timetable-item--${lesson.status}`}>
    <time>{lesson.start_time}–{lesson.end_time}</time>
    <strong>{lesson.subject_name}</strong>
    <span className="teaching-muted">{teacher ? lesson.class_name : lesson.teacher_name}</span>
    {flag && <span className={`timetable-flag timetable-flag--${lesson.status}`}>{flag}{lesson.substitute_name && lesson.status === "SUBSTITUTE" ? `: ${lesson.substitute_name}` : ""}{lesson.note ? ` · ${lesson.note}` : ""}</span>}
    {canMark && <Link to={attendanceLink(lesson)}>Take attendance</Link>}
  </div>;
}

/** Today's lessons for the dashboard. Shows nothing when there is no published timetable. */
export function TodayLessons() {
  const { user } = useAuth();
  const today = kenyaToday();
  const query = useTeachingQuery(`/api/timetable/me?start=${today}&days=1`);
  const lessons = query.data?.lessons || [];
  if (!lessons.length) return null;
  const base = user.role === "TEACHER" ? "/teacher" : "/student";
  return <section className="teaching-panel" aria-labelledby="today-lessons">
    <h2 id="today-lessons">Today's lessons</h2>
    {lessons.map(l => <LessonItem key={`${l.id}:${l.status}`} lesson={l} teacher={user.role === "TEACHER"} />)}
    <p><Link to={`${base}/timetable`}>Full timetable</Link></p>
  </section>;
}
