import OperationalDashboard from "../../components/dashboard/OperationalDashboard";
import ManagementDashboard from './ManagementDashboard';
import { useTeachingQuery } from '../teacher/teachingQueries';
import { QueryState } from '../teacher/TeachingUI';

export default function DashboardPage(){
  const query = useTeachingQuery('/api/institution/modules');
  if (!query.data) return <QueryState query={query} />;
  return query.data.modules.staff_directory && (!query.data.modules.student_records || !query.data.modules.coursework) ? <ManagementDashboard /> : <OperationalDashboard />;
}
