import { useTeachingQuery } from './teachingQueries';
import { PageHeading, QueryState } from './TeachingUI';

export default function TeacherAllocationsPage() {
  const query = useTeachingQuery('/api/teacher/staff-allocations');
  const data = query.data;
  return <><PageHeading title="My teaching allocations">The offerings you lead or co-teach, as allocated by your institution.</PageHeading><QueryState query={query} />{data && <section className="teaching-panel">{data.employee ? <><h2>{data.employee.job_title} · {data.employee.staff_number}</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Offering</th><th>Class</th><th>Role</th><th>Group</th><th>Hours / week</th></tr></thead><tbody>{data.allocations.map(row => <tr key={row.id}><td>{row.subject_name}</td><td>{row.class_name}{row.stream ? ` ${row.stream}` : ''} · {row.academic_year}</td><td>{row.role === 'LEAD' ? 'Lead' : 'Co-teacher'}</td><td>{row.group_name || 'Whole offering'}</td><td>{row.weekly_hours ?? '—'}</td></tr>)}</tbody></table></div>{!data.allocations.length && <p>No teaching allocations have been recorded for you.</p>}</> : <p>Your account is not linked to a staff record yet. Ask your institution administrator to link it in the staff directory.</p>}</section>}</>;
}
