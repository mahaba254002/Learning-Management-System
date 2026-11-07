import { useState } from "react";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import { LessonItem, WeekGrid } from "./TimetableViews";
import { DAYS, addDays, isoWeekday, kenyaToday, longDate, weekStart } from "./timetableFormat";
import "./Timetable.css";

function ClassTimetable({ classes }) {
  const [classId, setClassId] = useState(classes[0]?.id || "");
  const query = useTeachingQuery(classId ? `/api/timetable/classes/${classId}` : null, { retry: false });
  return <section className="teaching-panel" aria-labelledby="class-timetable"><h2 id="class-timetable">Class timetable{query.data ? ` · ${query.data.period_name}` : ""}</h2>
    {classes.length > 1 && <Field label="Class" value={classId} onChange={e => setClassId(e.target.value)}>{classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</Field>}
    {query.isError ? <Empty>No timetable has been published for this class yet.</Empty> : <QueryState query={query} />}
    {query.data && (query.data.entries.length ? <WeekGrid data={query.data} /> : <Empty>No lessons yet.</Empty>)}
  </section>;
}

export default function MyTimetablePage() {
  const { user } = useAuth();
  const teacher = user.role === "TEACHER";
  const today = kenyaToday();
  const [start, setStart] = useState(() => weekStart(today));
  const query = useTeachingQuery(`/api/timetable/me?start=${start}&days=7`);
  const teacherClasses = useTeachingQuery(teacher ? "/api/teaching/classes" : null);
  const teacherSubjects = useTeachingQuery(teacher ? "/api/teaching/subjects" : null);
  const studentSubjects = useTeachingQuery(teacher ? null : "/api/student/subjects");
  const classes = teacher
    ? [...new Map([...(teacherClasses.data || []).map(c => [c.id, `${c.name} · ${c.academic_year}`]), ...(teacherSubjects.data || []).map(s => [s.class_id, `${s.class_name} · ${s.academic_year}`])]).entries()].map(([id, name]) => ({ id, name }))
    : [...new Map((studentSubjects.data || []).map(s => [s.class_id, `${s.class_name} · ${s.academic_year}`])).entries()].map(([id, name]) => ({ id, name }));
  const lessons = query.data?.lessons || [];
  const days = [...Array(7)].map((_, i) => addDays(start, i)).filter(d => isoWeekday(d) <= 5 || lessons.some(l => l.date === d));
  return <><PageHeading title={teacher ? "My timetable" : "Timetable"}>{teacher ? "Your lessons this week, including any changes. Open a lesson's register from here." : "Your lessons this week, including any changes."}</PageHeading>
    <div className="timetable-nav">
      <button className="btn" type="button" onClick={() => setStart(addDays(start, -7))}>Previous week</button>
      <button className="btn" type="button" onClick={() => setStart(weekStart(today))} disabled={start === weekStart(today)}>This week</button>
      <button className="btn" type="button" onClick={() => setStart(addDays(start, 7))}>Next week</button>
      <span className="teaching-muted">Week of {longDate(start)}</span>
    </div>
    <QueryState query={query} />
    {query.data && (!lessons.length ? <Empty>No lessons this week. The timetable may not be published yet.</Empty> : <div className="timetable-week">
      {days.map(d => <section key={d} className={`timetable-day${d === today ? " timetable-day--today" : ""}`} aria-label={longDate(d)}>
        <h3>{DAYS[isoWeekday(d)]} <span className="teaching-muted">{d.slice(8)}/{d.slice(5, 7)}</span></h3>
        {lessons.filter(l => l.date === d).map(l => <LessonItem key={`${l.id}:${l.date}:${l.status}`} lesson={l} teacher={teacher} />)}
        {!lessons.some(l => l.date === d) && <p className="teaching-muted">No lessons</p>}
      </section>)}
    </div>)}
    {classes.length > 0 && <ClassTimetable classes={classes} />}
  </>;
}
