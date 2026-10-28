import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import "../LandingPage.css";
import "./TeachingWorkspace.css";
import { useAcademicNavigation } from '../../hooks/useAcademicNavigation';

const navItems = [
  { label: "Dashboard", path: "/teacher/dashboard" },
  { label: "Report cards & transcripts", path: "/teacher/reports" },
  { label: "My classes", path: "/teacher/classes" },
  { label: "Attendance", path: "/teacher/attendance" },
  { label: "Coursework", path: "/teacher/coursework" },
  { label: "Course materials", path: "/teacher/materials" },
  { label: "Scores", path: "/teacher/scores" },
  { label: "My profile", path: "/teacher/profile" },
];

export default function TeacherLayout() {
  const nav = useAcademicNavigation(navItems);
  return <DashboardLayout navItems={nav} brandLabel="Educator portal"><Outlet /></DashboardLayout>;
}
