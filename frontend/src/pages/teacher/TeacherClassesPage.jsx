import { Link } from "react-router-dom";
import { useTeachingQuery } from "./teachingQueries";
import { Empty, PageHeading, QueryState } from "./TeachingUI";

export default function TeacherClassesPage() {
  const configuration = useTeachingQuery("/api/institution/learning-settings");
  const labels = configuration.data || { class_label: "Class", period_label: "Academic year" };
  const query = useTeachingQuery("/api/teaching/classes");
  return <><PageHeading title={`My ${labels.class_label.toLowerCase()}${labels.class_label.endsWith("s") ? "es" : "s"}`}>Manage supervised learning groups and view students you teach.</PageHeading><QueryState query={query} />
    {query.data?.length === 0 && <Empty>No classes assigned yet. Your administrator can assign your classes and subjects.</Empty>}
    <div className="teaching-grid">{query.data?.map(c => <article className="teaching-panel" key={c.id}><h2>{c.name}</h2>
      <p>{labels.period_label}: {c.academic_year}</p><p className="teaching-muted">{(c.can_view_class_register || c.can_manage) ? "Class teacher / supervisor" : "Subject teacher"}</p>
      <div className="teaching-actions"><Link to={`/teacher/classes/${c.id}`}>{c.can_manage ? "Manage students" : "View roster"}</Link></div>
    </article>)}</div></>;
}
