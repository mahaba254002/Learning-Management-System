import { useState } from "react";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import { Pagination } from "../institution/StaffDirectoryPage";

export default function StaffStudentsPage() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const query = useTeachingQuery(`/api/management/students?${new URLSearchParams({ search, offset })}`);
  return <><PageHeading title="Students">Read-only list of students and their current class.</PageHeading>
    <div className="management-filters"><Field label="Search name or admission number" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /></div>
    <QueryState query={query} />
    {query.data && <section className="teaching-panel"><h2>{query.data.total} student{query.data.total === 1 ? "" : "s"}</h2>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Admission no.</th><th>Name</th><th>Class</th><th>Status</th></tr></thead>
        <tbody>{query.data.items.map(row => <tr key={row.id}><td>{row.admission_number}</td><td>{row.first_name} {row.last_name}</td><td>{row.class_name || "Not enrolled"}</td><td>{row.status.toLowerCase()}</td></tr>)}</tbody></table></div>
      {!query.data.total && <p>No students match this search.</p>}
      <Pagination offset={offset} total={query.data.total} setOffset={setOffset} /></section>}</>;
}
