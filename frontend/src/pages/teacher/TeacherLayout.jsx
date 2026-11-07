import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import "../LandingPage.css";
import "./TeachingWorkspace.css";
import { useAcademicNavigation } from '../../hooks/useAcademicNavigation';
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "./teachingQueries";

const navItems = [
  { label: "Dashboard", path: "/teacher/dashboard" },
  { label: "My course allocations", path: "/teacher/allocations", icon: "classes" },
  { label: "Report cards & transcripts", path: "/teacher/reports" },
  { label: "My timetable", path: "/teacher/timetable" },
  { label: "My classes", path: "/teacher/classes" },
  { label: "My courses", path: "/teacher/courses", icon: "classes" },
  { label: "Attendance", path: "/teacher/attendance" },
  { label: "Coursework", path: "/teacher/coursework" },
  { label: "Course materials", path: "/teacher/materials" },
  { label: "Scores", path: "/teacher/scores" },
  { label: "Marks & marksheets", path: "/teacher/marks" },
  { label: "Student records", path: "/teacher/student-records", icon: "students", classTeacher: true },
  { label: "Fee status", path: "/teacher/fees", icon: "billing", classTeacher: true },
  { label: "Announcements", path: "/teacher/announcements" },
  { label: "My profile", path: "/teacher/profile" },
];

export default function TeacherLayout() {
  const { user } = useAuth();
  const classes = useTeachingQuery("/api/teaching/classes");
  // Student records and fee status are for class teachers only.
  const classTeacher = (classes.data || []).some(c => c.supervisor_id === user.id);
  const nav = useAcademicNavigation(navItems.filter(item => !item.classTeacher || classTeacher));
  return <DashboardLayout navItems={nav} brandLabel="Educator portal"><Outlet /></DashboardLayout>;
}
