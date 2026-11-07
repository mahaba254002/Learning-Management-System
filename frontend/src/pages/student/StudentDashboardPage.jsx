import OperationalDashboard from "../../components/dashboard/OperationalDashboard";
import { TodayLessons } from "../timetable/TimetableViews";
import { UpcomingDeadlines } from "../elearning/CoursesPages";

export default function DashboardPage(){ return <OperationalDashboard><TodayLessons /><UpcomingDeadlines /></OperationalDashboard>; }
