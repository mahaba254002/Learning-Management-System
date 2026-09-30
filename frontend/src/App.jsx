import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import PortalPickerPage from "./pages/PortalPickerPage";
import LoginPage from "./pages/auth/LoginPage";
import ProtectedRoute from "./routes/ProtectedRoute";

import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import ChangePasswordPage from "./pages/auth/ChangePasswordPage";

import PlatformLayout from "./pages/platform/PlatformLayout";
import PlatformDashboardPage from "./pages/platform/PlatformDashboardPage";
import PlatformInstitutionsPage from "./pages/platform/PlatformInstitutionsPage";
import { AdminAccountPage, AdminAuditPage, AdminUsersPage, InstitutionSettingsPage, PlatformUsagePage } from "./pages/AdminPages";
import TeacherLayout from "./pages/teacher/TeacherLayout";
import TeacherDashboardPage from "./pages/teacher/TeacherDashboardPage";
import TeacherProfilePage from "./pages/teacher/TeacherProfilePage";
import TeacherClassesPage from "./pages/teacher/TeacherClassesPage";
import ClassStudentsPage from "./pages/teacher/ClassStudentsPage";
import TeacherAttendancePage from "./pages/teacher/TeacherAttendancePage";
import TeacherCourseworkPage from "./pages/teacher/TeacherCourseworkPage";
import TeacherScoresPage from "./pages/teacher/TeacherScoresPage";
import InstitutionClassesPage from "./pages/institution/InstitutionClassesPage";
import StudentCourseworkPage from "./pages/student/StudentCourseworkPage";
import StudentLayout from "./pages/student/StudentLayout";
import StudentDashboardPage from "./pages/student/StudentDashboardPage";
import StudentSubjectsPage, { StudentSubjectPage } from "./pages/student/StudentSubjectsPage";
import StudentAttendancePage from "./pages/student/StudentAttendancePage";
import StudentProfilePage from "./pages/student/StudentProfilePage";
import StudentAssignmentPage from "./pages/student/StudentAssignmentPage";
import TeacherMaterialsPage from "./pages/teacher/TeacherMaterialsPage";

import InvitePage from "./pages/invite/InvitePage";
import InstitutionLayout from "./pages/institution/InstitutionLayout";
import InstitutionDashboardPage from "./pages/institution/InstitutionDashboardPage";
import InstitutionInvitationsPage from "./pages/institution/InstitutionInvitationsPage";
import InstitutionTeachersPage from "./pages/institution/InstitutionTeachersPage";
import InstitutionTeacherDetailPage from "./pages/institution/InstitutionTeacherDetailPage";


import StudentLoginPage from "./pages/student/StudentLoginPage";
import StudentForgotPasswordPage from "./pages/student/StudentForgotPasswordPage";
import StudentResetPasswordPage from "./pages/student/StudentResetPasswordPage";

import TeacherLoginPage from "./pages/teacher/TeacherLoginPage";
import TeacherForgotPasswordPage from "./pages/teacher/TeacherForgotPasswordPage";
import TeacherResetPasswordPage from "./pages/teacher/TeacherResetPasswordPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/sign-in" element={<PortalPickerPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/student/login" element={<StudentLoginPage />} />
        <Route path="/student/forgot-password" element={<StudentForgotPasswordPage />} />
        <Route path="/student/reset-password" element={<StudentResetPasswordPage />} />
        <Route
          path="/student/change-password"
          element={<ProtectedRoute allowedRoles={["STUDENT"]}><ChangePasswordPage /></ProtectedRoute>}
        />
        <Route
          path="/teacher/change-password"
          element={<ProtectedRoute allowedRoles={["TEACHER"]}><ChangePasswordPage /></ProtectedRoute>}
        />

        <Route
          path="/change-password"
          element={
            <ProtectedRoute>
              <ChangePasswordPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/institution"
          element={
            <ProtectedRoute allowedRoles={["INSTITUTION_ADMIN"]}>
              <InstitutionLayout />
            </ProtectedRoute>
          }
        >
          <Route path="dashboard" element={<InstitutionDashboardPage />} />
          <Route path="invitations" element={<InstitutionInvitationsPage />} />
          <Route path="teachers" element={<InstitutionTeachersPage />} />
          <Route path="teachers/:teacherId" element={<InstitutionTeacherDetailPage />} />
          <Route path="classes" element={<InstitutionClassesPage />} />
          <Route path="classes/:classId" element={<ClassStudentsPage />} />
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="students" element={<AdminUsersPage key="students" studentsOnly />} />
          <Route path="users" element={<AdminUsersPage key="institution-users" />} />
          <Route path="attendance" element={<TeacherAttendancePage />} />
          <Route path="coursework" element={<TeacherCourseworkPage />} />
          <Route path="materials" element={<TeacherMaterialsPage />} />
          <Route path="scores" element={<TeacherScoresPage />} />
          <Route path="audit-logs" element={<AdminAuditPage />} />
          <Route path="settings" element={<InstitutionSettingsPage />} />
          <Route path="account" element={<AdminAccountPage />} />
        </Route>
        <Route
          path="/teacher"
          element={
            <ProtectedRoute allowedRoles={["TEACHER"]}>
              <TeacherLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<TeacherDashboardPage />} />
          <Route path="profile" element={<TeacherProfilePage />} />
          <Route path="classes" element={<TeacherClassesPage />} />
          <Route path="classes/:classId" element={<ClassStudentsPage />} />
          <Route path="attendance" element={<TeacherAttendancePage />} />
          <Route path="coursework" element={<TeacherCourseworkPage />} />
          <Route path="materials" element={<TeacherMaterialsPage />} />
          <Route path="scores" element={<TeacherScoresPage />} />
        </Route>
        <Route
          path="/student"
          element={
            <ProtectedRoute allowedRoles={["STUDENT"]}>
              <StudentLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<StudentDashboardPage />} />
          <Route path="subjects" element={<StudentSubjectsPage />} />
          <Route path="subjects/:subjectId" element={<StudentSubjectPage />} />
          <Route path="attendance" element={<StudentAttendancePage />} />
          <Route path="assignments" element={<StudentCourseworkPage />} />
          <Route path="assignments/:assignmentId" element={<StudentAssignmentPage />} />
          <Route path="grades" element={<StudentCourseworkPage gradesOnly />} />
          <Route path="profile" element={<StudentProfilePage />} />
        </Route>
        <Route path="/teacher/login" element={<TeacherLoginPage />} />
        <Route path="/teacher/forgot-password" element={<TeacherForgotPasswordPage />} />
        <Route path="/teacher/reset-password" element={<TeacherResetPasswordPage />} />
        <Route
          path="/platform"
          element={
            <ProtectedRoute allowedRoles={["PLATFORM_ADMIN"]}>
              <PlatformLayout />
            </ProtectedRoute>
          }
        >
          <Route path="dashboard" element={<PlatformDashboardPage />} />
          <Route path="institutions" element={<PlatformInstitutionsPage />} />
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="users" element={<AdminUsersPage key="platform-users" platform />} />
          <Route path="usage" element={<PlatformUsagePage />} />
          <Route path="revenue" element={<Navigate to="/platform/usage" replace />} />
          <Route path="audit-logs" element={<AdminAuditPage platform />} />
          <Route path="settings" element={<AdminAccountPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
