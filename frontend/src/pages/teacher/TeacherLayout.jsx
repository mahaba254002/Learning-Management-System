import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import "../LandingPage.css";
import "./TeachingWorkspace.css";

const navItems = [
  { label: "Dashboard", path: "/teacher/dashboard" },
  { label: "My classes", path: "/teacher/classes" },
  { label: "Attendance", path: "/teacher/attendance" },
  { label: "Coursework", path: "/teacher/coursework" },
  { label: "Course materials", path: "/teacher/materials" },
  { label: "Scores", path: "/teacher/scores" },
  { label: "My profile", path: "/teacher/profile" },
];

export default function TeacherLayout() {
  return <DashboardLayout navItems={navItems} brandLabel="Teacher portal"><Outlet /></DashboardLayout>;
}
