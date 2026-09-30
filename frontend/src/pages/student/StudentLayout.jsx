import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import "../LandingPage.css";
import "../teacher/TeachingWorkspace.css";
import "./StudentLearning.css";

const navItems = [
  { label: "Dashboard", path: "/student/dashboard" },
  { label: "My subjects", path: "/student/subjects" },
  { label: "Assignments", path: "/student/assignments" },
  { label: "Attendance", path: "/student/attendance" },
  { label: "Grades & feedback", path: "/student/grades" },
  { label: "My profile", path: "/student/profile" },
];

export default function StudentLayout() {
  return <DashboardLayout navItems={navItems} brandLabel="Student portal"><Outlet /></DashboardLayout>;
}
