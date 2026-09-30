import { Link } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "./teachingQueries";
import { Empty, PageHeading, QueryState } from "./TeachingUI";

export default function TeacherDashboardPage() {
  const { user } = useAuth();
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  return <>
    <PageHeading title={`Welcome, ${user.first_name}`}>Your classes, teaching subjects, and daily work.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} />
    {classes.data && subjects.data && <>
      <div className="stat-cards">
        <div className="stat-card"><div className="stat-card__value">{classes.data.length}</div><div className="stat-card__label">Assigned classes</div></div>
        <div className="stat-card"><div className="stat-card__value">{classes.data.filter(c => c.can_manage).length}</div><div className="stat-card__label">Classes supervised</div></div>
        <div className="stat-card"><div className="stat-card__value">{subjects.data.length}</div><div className="stat-card__label">Subjects taught</div></div>
      </div>
      <section className="teaching-panel"><h2>Start here</h2><div className="teaching-actions">
        <Link className="btn btn--primary" to="/teacher/attendance">Take attendance</Link>
        <Link to="/teacher/coursework">Set coursework</Link><Link to="/teacher/scores">Enter scores</Link>
      </div></section>
      <section><h2 className="section-header">My teaching subjects</h2>
        {!subjects.data.length && <Empty>Your administrator has not assigned any teaching subjects yet.</Empty>}
        <div className="teaching-grid">{subjects.data.map(s => <article key={s.id} className="teaching-panel">
          <h3>{s.name}</h3><p className="teaching-muted">{s.class_name} · {s.academic_year}</p>
          <div className="teaching-actions"><Link to={`/teacher/coursework?subject=${s.id}`}>Coursework</Link><Link to={`/teacher/classes/${s.class_id}`}>Class roster</Link></div>
        </article>)}</div>
      </section>
    </>}
  </>;
}
