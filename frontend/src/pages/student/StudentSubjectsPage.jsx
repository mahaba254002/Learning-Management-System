import { Link, useParams } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, PageHeading, QueryState } from "../teacher/TeachingUI";
import { formatDateTime } from "./learningFormat";

export default function StudentSubjectsPage() {
  const query = useTeachingQuery("/api/student/subjects");
  return <><PageHeading title="My subjects">All courses and subjects in your current class enrollments.</PageHeading><QueryState query={query} />
    {query.data?.length === 0 && <Empty>No subjects assigned yet.</Empty>}
    <div className="teaching-grid">{query.data?.map(s => <article key={s.id} className="teaching-panel"><h2>{s.name}</h2><p>{s.class_name} · {s.academic_year}</p><p className="teaching-muted">Teacher: {s.teacher_name}</p><div className="teaching-actions"><Link to={`/student/subjects/${s.id}`}>Materials & learning</Link><Link to={`/student/attendance?subject=${s.id}`}>My attendance</Link></div></article>)}</div>
  </>;
}

export function StudentSubjectPage() {
  const { subjectId } = useParams();
  const subjects = useTeachingQuery("/api/student/subjects");
  const materials = useTeachingQuery(`/api/student/subjects/${subjectId}/materials`);
  const subject = subjects.data?.find(s => s.id === subjectId);
  return <><PageHeading title={subject?.name || "Subject materials"}>{subject && `${subject.class_name} · ${subject.academic_year} · ${subject.teacher_name}`}</PageHeading>
    <QueryState query={subjects} /><QueryState query={materials} />
    {subject && <><div className="teaching-actions"><Link to={`/student/assignments?subject=${subjectId}`}>Assignments & tasks</Link><Link to={`/student/attendance?subject=${subjectId}`}>My attendance</Link><Link to={`/student/grades?subject=${subjectId}`}>Grades & feedback</Link></div>
      <section className="teaching-panel"><h2>Learning materials</h2>{materials.data?.length === 0 && <Empty>Your teacher has not published materials for this subject yet.</Empty>}
        {materials.data?.map(m => <article className="student-resource" key={m.id}><h3>{m.title}</h3><p className="teaching-muted">Updated {formatDateTime(m.updated_at)}</p><p className="teaching-instructions">{m.body}</p>{m.link_url && <a href={m.link_url} target="_blank" rel="noopener noreferrer">Open resource (new tab)</a>}</article>)}
      </section></>}
  </>;
}
