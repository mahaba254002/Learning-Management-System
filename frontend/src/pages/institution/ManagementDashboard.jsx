import MaterialIcon from "../../components/common/MaterialIcon";
import { Link } from 'react-router-dom';
import { useTeachingQuery } from '../teacher/teachingQueries';
import { PageHeading, QueryState } from '../teacher/TeachingUI';
import { moduleLabels } from '../../modules/institutionModules';
import '../../components/common/ModuleEditor.css';

export default function ManagementDashboard() {
  const query = useTeachingQuery('/api/management/overview', { refetchInterval: 30000 });
  const data = query.data;
  return <><PageHeading title="Institution management">Staff, departments, teaching responsibilities and daily operations.</PageHeading><QueryState query={query} />{data && <>
    <div className="management-cards">{[
      ['Active employees', data.active_staff, '/institution/staff'], ['Teaching staff', data.teaching_staff, '/institution/staff'],
      ['Non-teaching staff', data.non_teaching_staff, '/institution/staff'], ['Departments', data.departments, '/institution/departments'],
      ...(data.modules.course_allocation ? [['Active course allocations', data.active_allocations, '/institution/allocations']] : []),
    ].map(([label, count, href]) => <Link className="management-card" key={label} to={href}><strong>{count}</strong><span>{label}</span></Link>)}</div>
    <div className="teaching-grid"><section className="teaching-panel"><h2>Getting your institution ready</h2><ol className="management-setup-list"><li><Link to="/institution/departments">Add institution departments</Link></li>{data.modules.course_allocation && <li><Link to="/institution/academic-structure">Build the course catalogue</Link></li>}<li><Link to="/institution/staff">Record teaching and non-teaching employees</Link></li>{data.modules.course_allocation && <li><Link to="/institution/allocations">Allocate courses and weekly hours</Link></li>}{data.modules.staff_attendance && <li><Link to="/institution/staff-attendance">Record today’s staff attendance</Link></li>}{data.modules.student_records && <li><Link to="/institution/classes">Manage student groups and enrollment</Link></li>}</ol><p>Teacher accounts can be linked to employee records. Other employees can be managed without sign-in accounts.</p></section>
      {data.modules.staff_attendance && <section className="teaching-panel"><h2>Today’s staff attendance</h2>{Object.keys(data.attendance_today || {}).length ? <dl className="management-attendance-summary">{Object.entries(data.attendance_today).map(([status, count]) => <div key={status}><dt>{status.replaceAll('_', ' ').toLowerCase()}</dt><dd>{count}</dd></div>)}</dl> : <p>No staff attendance recorded today.</p>}<Link className="management-action-link" to="/institution/staff-attendance">Open staff register <MaterialIcon name="arrow_forward" size={18} /></Link></section>}</div>
    <section className="teaching-panel"><h2>Enabled modules</h2><p>{Object.entries(data.modules).filter(([, enabled]) => enabled).map(([key]) => moduleLabels[key][0]).join(' · ')}</p><Link className="management-action-link" to="/institution/modules">View institution package <MaterialIcon name="arrow_forward" size={18} /></Link></section>
  </>}</>;
}
