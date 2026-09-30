import { Link } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, PageHeading, QueryState } from "../teacher/TeachingUI";
import { assignmentStatus, formatDateTime } from "./learningFormat";

export default function StudentDashboardPage() {
  const { user } = useAuth();
  const subjects = useTeachingQuery("/api/student/subjects");
  const assignments = useTeachingQuery("/api/student/assignments");
  const works = assignments.data || [];
  const pending = works.filter(w => w.kind !== "EXAM" && w.score === null && w.submission?.status !== "SUBMITTED");
  const due = [...pending].filter(w => w.due_at).sort((a, b) => new Date(a.due_at) - new Date(b.due_at));
  return <><PageHeading title={`Welcome, ${user.first_name}`}>Your subjects, deadlines, and learning progress.</PageHeading>
    <QueryState query={subjects} /><QueryState query={assignments} />
    {subjects.data && assignments.data && <><div className="stat-cards">
      <div className="stat-card"><div className="stat-card__value">{subjects.data.length}</div><div className="stat-card__label">Enrolled subjects</div></div>
      <div className="stat-card"><div className="stat-card__value">{pending.length}</div><div className="stat-card__label">Awaiting submission</div></div>
      <div className="stat-card"><div className="stat-card__value">{works.filter(w => w.score !== null).length}</div><div className="stat-card__label">Graded assessments</div></div>
    </div>
    <section className="teaching-panel"><div className="section-header"><h2>Deadlines to watch</h2><Link to="/student/assignments">All assignments</Link></div>
      {due.length ? <ul className="student-due-list">{due.slice(0, 6).map(w => <li key={w.id}><div><Link to={`/student/assignments/${w.id}`}>{w.title}</Link><p className="teaching-muted">{w.subject_name} · {formatDateTime(w.due_at)}</p></div><span className="student-status">{assignmentStatus(w)}</span></li>)}</ul> : <Empty>No outstanding dated assignments.</Empty>}
    </section>
    <section><div className="section-header"><h2>My subjects</h2><Link to="/student/subjects">View all subjects</Link></div>
      {!subjects.data.length && <Empty>No subjects are assigned to your enrolled classes yet. Contact your class supervisor.</Empty>}
      <div className="teaching-grid">{subjects.data.map(s => <article key={s.id} className="teaching-panel"><h3>{s.name}</h3><p>{s.class_name} · {s.academic_year}</p><p className="teaching-muted">{s.teacher_name}</p><div className="teaching-actions"><Link to={`/student/subjects/${s.id}`}>Open subject</Link></div></article>)}</div>
    </section></>}
  </>;
}
