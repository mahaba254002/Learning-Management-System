import OperationalDashboard from "../../components/dashboard/OperationalDashboard";
import { TodayLessons } from "../timetable/TimetableViews";
import { UpcomingDeadlines } from "../elearning/CoursesPages";

export default function DashboardPage(){ return <><TodayLessons /><UpcomingDeadlines /><OperationalDashboard /></>; }
