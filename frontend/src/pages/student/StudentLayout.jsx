import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import "../LandingPage.css";
import "../teacher/TeachingWorkspace.css";
import "./StudentLearning.css";
import { useAcademicNavigation } from '../../hooks/useAcademicNavigation';

const navItems = [
  { label: "Dashboard", path: "/student/dashboard" },
  { label: "Report cards & transcripts", path: "/student/reports" },
  { label: "My subjects", path: "/student/subjects" },
  { label: "Assignments", path: "/student/assignments" },
  { label: "Attendance", path: "/student/attendance" },
  { label: "Grades & feedback", path: "/student/grades" },
  { label: "Academic record", path: "/student/academic-record" },
  { label: "My progression", path: "/student/progression" },
  { label: "My profile", path: "/student/profile" },
];

export default function StudentLayout() {
  const nav = useAcademicNavigation(navItems);
  return <DashboardLayout navItems={nav} brandLabel="Learner portal"><Outlet /></DashboardLayout>;
}
