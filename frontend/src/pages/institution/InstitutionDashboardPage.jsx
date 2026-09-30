import { Link } from 'react-router-dom';
import { useTeachingQuery } from '../teacher/teachingQueries';
import { PageHeading, QueryState } from '../teacher/TeachingUI';
import '../teacher/TeachingWorkspace.css';
import '../platform/PlatformDashboardPage.css';

export default function InstitutionDashboardPage() {
  const query = useTeachingQuery('/api/institution/overview');
  const data = query.data;
  return <><PageHeading title={data?.institution.name || 'Institution overview'}>Academic activity and administration for your institution.</PageHeading><QueryState query={query} />
    {data && <><div className="stat-cards">{[['Students', data.students], ['Teachers', data.users_by_role.TEACHER || 0], ['Classes', data.classes], ['Subjects', data.subjects], ['Active enrollments', data.active_enrollments], ['Applications awaiting review', data.pending_invitations]].map(([label, value]) => <div className="stat-card" key={label}><p className="stat-card__value">{value}</p><p className="stat-card__label">{label}</p></div>)}</div>
    <section className="teaching-panel"><h2>Learning activity</h2><p>{data.assessments} assessments · {data.final_submissions} final submissions · {data.scores_recorded} scores recorded</p><p>Recorded attendance across daily class and subject registers: {Object.entries(data.attendance).map(([status, count]) => `${status.toLowerCase()}: ${count}`).join(' · ') || 'No attendance recorded yet'}</p></section>
    <section className="teaching-panel"><h2>Administration</h2><div className="teaching-actions"><Link to="/institution/invitations">Review teacher applications ({data.pending_invitations})</Link><Link to="/institution/classes">Manage classes and enrollment</Link><Link to="/institution/users">Manage user access</Link><Link to="/institution/attendance">Attendance registers</Link><Link to="/institution/scores">Review scores and submitted work</Link></div></section></>}
  </>;
}
