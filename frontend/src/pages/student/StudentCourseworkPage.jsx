import { Link, useSearchParams } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import { assignmentStatus, formatDateTime } from "./learningFormat";

export default function StudentCourseworkPage({ gradesOnly = false }) {
  const subjects = useTeachingQuery("/api/student/subjects");
  const assignments = useTeachingQuery("/api/student/assignments");
  const [params, setParams] = useSearchParams();
  const selected = params.get("subject") || "";
  const works = (assignments.data || []).filter(w => !selected || w.subject_id === selected);
  return <><PageHeading title={gradesOnly ? "Grades & feedback" : "Assignments & tasks"}>{gradesOnly ? "Your marks and teacher feedback for published assessments." : "Read instructions, save a draft, and submit your work."}</PageHeading>
    <QueryState query={subjects} /><QueryState query={assignments} />
    <Field label="Filter subject" value={selected} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">All subjects</option>{subjects.data?.map(s => <option key={s.id} value={s.id}>{s.name} · {s.class_name}</option>)}</Field>
    {assignments.data && !works.length && <Empty>No published assessments for this selection.</Empty>}
    {works.map(w => <article className="teaching-panel" key={w.id}><div className="section-header"><h2>{w.title}</h2><span className="student-status">{assignmentStatus(w)}</span></div>
      <p className="teaching-muted">{w.subject_name} · {w.kind.toLowerCase()} · {formatDateTime(w.due_at)}</p>
      {gradesOnly ? <><p className="teaching-notice">Score: {w.score === null ? "Not graded" : `${w.score} / ${w.max_score}`}</p>{w.feedback && <p className="teaching-instructions"><strong>Teacher feedback:</strong> {w.feedback}</p>}</> : <p className="teaching-muted">Maximum score: {w.max_score}</p>}
      <div className="teaching-actions"><Link to={`/student/assignments/${w.id}`}>{w.submission?.status === "SUBMITTED" ? "View submission" : "Open assessment"}</Link></div>
    </article>)}
  </>;
}
