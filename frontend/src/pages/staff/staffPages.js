import { useTeachingQuery } from "../teacher/teachingQueries";

// Each page appears only when the administrator granted the matching right.
export const STAFF_PAGES = [
  { label: "Staff directory", path: "/staff/staff", icon: "staff", permission: "staff.view" },
  { label: "Staff attendance", path: "/staff/staff-attendance", icon: "staff-attendance", permission: "staff_attendance.manage" },
  { label: "Student records", path: "/staff/students", icon: "students", permission: "students.view" },
  { label: "Fee status", path: "/staff/fees", icon: "billing", permission: "fees.manage" },
  { label: "Course registration", path: "/staff/course-registration", permission: "registrations.approve" },
];

export function useStaffProfile() {
  return useTeachingQuery("/api/staff/me");
}
