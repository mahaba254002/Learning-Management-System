import { useTeachingQuery } from './teachingQueries';
import { PageHeading, QueryState } from './TeachingUI';

export default function TeacherAllocationsPage() {
  const query = useTeachingQuery('/api/teacher/staff-allocations');
  const data = query.data;
  return <><PageHeading title="My course allocations">Your course responsibilities and weekly teaching hours, as allocated by your institution.</PageHeading><QueryState query={query} />{data && <section className="teaching-panel">{data.employee ? <><h2>{data.employee.job_title} · {data.employee.staff_number}</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Course</th><th>Period</th><th>Group</th><th>Hours / week</th><th>Status</th></tr></thead><tbody>{data.allocations.map(row => <tr key={row.id}><td>{row.course_code} · {row.course_name}</td><td>{row.period}</td><td>{row.group_name || '—'}</td><td>{row.weekly_hours}</td><td>{row.active ? 'Active' : 'Ended'}</td></tr>)}</tbody></table></div>{!data.allocations.length && <p>No course allocations have been recorded for you.</p>}</> : <p>Your teacher account has not been linked to an employee record. Ask your institution administrator to link it in the staff directory.</p>}</section>}</>;
}
