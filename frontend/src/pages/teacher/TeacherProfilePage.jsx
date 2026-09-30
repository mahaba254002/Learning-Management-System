import { Link } from "react-router-dom";
import { useTeachingQuery } from "./teachingQueries";
import { PageHeading, QueryState } from "./TeachingUI";

export default function TeacherProfilePage() {
  const query = useTeachingQuery("/api/teacher/profile");
  const p = query.data;
  const fields = p ? { Name: `${p.first_name} ${p.last_name}`, Username: p.username, Email: p.email, Phone: p.phone,
    Qualification: p.qualification, Specialization: p.specialization, Employment: p.employment_type.replaceAll("_", " "), Status: p.status,
    "Date of birth": p.date_of_birth, "Joined on": new Date(p.joined_at).toLocaleDateString() } : {};
  return <><PageHeading title="My profile">Your institution’s record of your teaching appointment.</PageHeading><QueryState query={query} />
    {p && <section className="teaching-panel"><dl className="teaching-profile">{Object.entries(fields).map(([label, value]) => <div key={label} style={{ display: "contents" }}><dt>{label}</dt><dd>{value || "—"}</dd></div>)}</dl>
      <p className="teaching-muted">Contact your administrator to correct your employment details.</p>
      <div className="teaching-actions"><Link to="/teacher/change-password">Change password</Link></div>
    </section>}</>;
}
