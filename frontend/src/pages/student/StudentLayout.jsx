import { Outlet } from "react-router-dom";
import LearnerLayout from "../../components/layout/LearnerLayout";
import "../LandingPage.css";
import "../teacher/TeachingWorkspace.css";
import "./StudentLearning.css";
import { useAcademicNavigation } from '../../hooks/useAcademicNavigation';

// The top bar, as on a course site.
const mainItems = [
  { label: "Dashboard", path: "/student/dashboard" },
  { label: "My courses", path: "/student/courses" },
  { label: "Search course", path: "/student/course-search" },
  { label: "Attendance", path: "/student/attendance" },
];

// Everything else lives in the menu under the student's name.
const menuItems = [
  { label: "Messages", path: "/student/messages" },
  { label: "Assignments", path: "/student/assignments" },
  { label: "Grades & feedback", path: "/student/grades" },
  { label: "Timetable", path: "/student/timetable" },
  { label: "Course registration", path: "/student/registration" },
  { label: "Report cards & transcripts", path: "/student/reports" },
  { label: "Academic record", path: "/student/academic-record" },
  { label: "My progression", path: "/student/progression" },
  { label: "Announcements", path: "/student/announcements" },
  { label: "My profile", path: "/student/profile" },
];

export default function StudentLayout() {
  const menu = useAcademicNavigation(menuItems);
  return <LearnerLayout mainItems={mainItems} menuItems={menu}><Outlet /></LearnerLayout>;
}
