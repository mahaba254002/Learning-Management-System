import OperationalDashboard from "../../components/dashboard/OperationalDashboard";
import TeacherAllocationsPage from './TeacherAllocationsPage';
import TeacherProfilePage from './TeacherProfilePage';
import { useTeachingQuery } from './teachingQueries';
import { QueryState } from './TeachingUI';
import { TodayLessons } from "../timetable/TimetableViews";
import { UpcomingDeadlines } from "../elearning/CoursesPages";

export default function DashboardPage(){
  const query = useTeachingQuery('/api/institution/modules');
  if (!query.data) return <QueryState query={query} />;
  const modules = query.data.modules;
  if (!modules.staff_directory) return <p>Your educator workspace is disabled for this institution. Contact your institution administrator.</p>;
  if (!modules.course_allocation) return <TeacherProfilePage />;
  return !modules.student_records || !modules.coursework ? <TeacherAllocationsPage /> : <OperationalDashboard><TodayLessons /><UpcomingDeadlines staff /></OperationalDashboard>;
}
