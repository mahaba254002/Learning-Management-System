import { Link } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, PageHeading, QueryState } from "../teacher/TeachingUI";

export default function StudentProfilePage() {
  const query = useTeachingQuery("/api/student/profile");
  const p = query.data;
  const fields = p ? { Name: `${p.first_name} ${p.last_name}`, "Admission number": p.admission_number, Username: p.username, Email: p.email, Phone: p.phone } : {};
  return <><PageHeading title="My profile">Your institution’s student record. Contact your class supervisor if any details need correcting.</PageHeading><QueryState query={query} />
    {p && <><section className="teaching-panel"><dl className="teaching-profile">{Object.entries(fields).map(([label, value]) => <div key={label} style={{ display: "contents" }}><dt>{label}</dt><dd>{value || "—"}</dd></div>)}</dl></section>
      <section className="teaching-panel"><h2>Current enrollments</h2>{!p.classes.length && <Empty>No active class enrollments.</Empty>}{p.classes.map(c => <p key={c.id}>{c.name} · {c.academic_year}</p>)}</section>
      <Link to="/student/change-password">Change my password</Link></>}
  </>;
}
