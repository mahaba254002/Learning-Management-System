import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import NotFoundPage from "./pages/NotFoundPage";
const LoginPage = lazy(() => import("./pages/auth/LoginPage"));
import ProtectedRoute from "./routes/ProtectedRoute";

const ForgotPasswordPage = lazy(() => import("./pages/auth/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("./pages/auth/ResetPasswordPage"));
const ChangePasswordPage = lazy(() => import("./pages/auth/ChangePasswordPage"));

const PlatformLayout = lazy(() => import("./pages/platform/PlatformLayout"));
const PlatformDashboardPage = lazy(() => import("./pages/platform/PlatformDashboardPage"));
const PlatformInstitutionsPage = lazy(() => import("./pages/platform/PlatformInstitutionsPage"));
const AdminAccountPage = lazy(() => import("./pages/AdminPages").then(module => ({ default: module.AdminAccountPage })));
const AdminAuditPage = lazy(() => import("./pages/AdminPages").then(module => ({ default: module.AdminAuditPage })));
const AdminUsersPage = lazy(() => import("./pages/AdminPages").then(module => ({ default: module.AdminUsersPage })));
const InstitutionSettingsPage = lazy(() => import("./pages/AdminPages").then(module => ({ default: module.InstitutionSettingsPage })));
const PlatformUsagePage = lazy(() => import("./pages/AdminPages").then(module => ({ default: module.PlatformUsagePage })));
const TeacherLayout = lazy(() => import("./pages/teacher/TeacherLayout"));
const TeacherDashboardPage = lazy(() => import("./pages/teacher/TeacherDashboardPage"));
const TeacherProfilePage = lazy(() => import("./pages/teacher/TeacherProfilePage"));
const TeacherClassesPage = lazy(() => import("./pages/teacher/TeacherClassesPage"));
const TeacherAllocationsPage = lazy(() => import('./pages/teacher/TeacherAllocationsPage'));
const ClassStudentsPage = lazy(() => import("./pages/teacher/ClassStudentsPage"));
const TeacherAttendancePage = lazy(() => import("./pages/teacher/TeacherAttendancePage"));
const TeacherCourseworkPage = lazy(() => import("./pages/teacher/TeacherCourseworkPage"));
const TeacherScoresPage = lazy(() => import("./pages/teacher/TeacherScoresPage"));
const InstitutionClassesPage = lazy(() => import("./pages/institution/InstitutionClassesPage"));
const StudentCourseworkPage = lazy(() => import("./pages/student/StudentCourseworkPage"));
const StudentLayout = lazy(() => import("./pages/student/StudentLayout"));
const StudentDashboardPage = lazy(() => import("./pages/student/StudentDashboardPage"));
const StudentAttendancePage = lazy(() => import("./pages/student/StudentAttendancePage"));
const StudentProfilePage = lazy(() => import("./pages/student/StudentProfilePage"));
const StudentAssignmentPage = lazy(() => import("./pages/student/StudentAssignmentPage"));
const TeacherMaterialsPage = lazy(() => import("./pages/teacher/TeacherMaterialsPage"));
const PlatformInstitutionDetailPage = lazy(() => import("./pages/platform/PlatformInstitutionDetailPage"));
const PlatformBillingPage = lazy(() => import("./pages/platform/PlatformBillingPage"));
const PlatformBackupPage = lazy(() => import("./pages/platform/PlatformBackupPage"));
const PlatformRestorePage = lazy(() => import("./pages/platform/PlatformRestorePage"));

const InvitePage = lazy(() => import("./pages/invite/InvitePage"));
const SetPasswordPage = lazy(() => import("./pages/auth/SetPasswordPage"));
const StaffLayout = lazy(() => import("./pages/staff/StaffLayout"));
const StaffDashboardPage = lazy(() => import("./pages/staff/StaffLayout").then(module => ({ default: module.StaffDashboardPage })));
const StaffPermissionGate = lazy(() => import("./pages/staff/StaffLayout").then(module => ({ default: module.RequirePermission })));
const StudentRecordsPage = lazy(() => import("./pages/records/StudentRecordsPage"));
const FeeStatusPage = lazy(() => import("./pages/records/FeeStatusPage"));
const AnnouncementsPage = lazy(() => import("./pages/records/AnnouncementsPage"));
const TimetableAdminPage = lazy(() => import("./pages/timetable/TimetableAdminPage"));
const MyTimetablePage = lazy(() => import("./pages/timetable/MyTimetablePage"));
const MarksPage = lazy(() => import("./pages/marks/MarksPage"));
const GradingPage = lazy(() => import("./pages/marks/GradingPage"));
const PlatformGradingRequestsPage = lazy(() => import("./pages/platform/PlatformGradingRequestsPage"));
const MessagesPage = lazy(() => import("./pages/messaging/MessagesPage"));
const PlatformMessagingPage = lazy(() => import("./pages/platform/PlatformMessagingPage"));
const CoursesPages = () => import("./pages/elearning/CoursesPages");
const StudentCoursesPage = lazy(() => CoursesPages().then(m => ({ default: m.StudentCoursesPage })));
const StudentCoursePage = lazy(() => CoursesPages().then(m => ({ default: m.StudentCoursePage })));
const TeachingCoursesPage = lazy(() => CoursesPages().then(m => ({ default: m.TeachingCoursesPage })));
const TeachingCoursePage = lazy(() => CoursesPages().then(m => ({ default: m.TeachingCoursePage })));
const StudentQuizPage = lazy(() => import("./pages/elearning/StudentQuizPages").then(m => ({ default: m.StudentQuizPage })));
const QuizAttemptPage = lazy(() => import("./pages/elearning/StudentQuizPages").then(m => ({ default: m.QuizAttemptPage })));
const QuizBuilderPage = lazy(() => import("./pages/elearning/QuizBuilderPage"));
const StudentRegistrationPage = lazy(() => import("./pages/elearning/RegistrationPages").then(m => ({ default: m.StudentRegistrationPage })));
const RegistrationAdminPage = lazy(() => import("./pages/elearning/RegistrationPages").then(m => ({ default: m.RegistrationAdminPage })));
const InstitutionRequestsPage = lazy(() => import("./pages/requests/RequestPages").then(m => ({ default: m.InstitutionRequestsPage })));
const PlatformRequestsPage = lazy(() => import("./pages/requests/RequestPages").then(m => ({ default: m.PlatformRequestsPage })));
const PlatformSecretSettings = lazy(() => import("./pages/platform/PlatformSecret").then(m => ({ default: m.PlatformSecretSettings })));
const PlatformStoragePage = lazy(() => import("./pages/platform/PlatformStoragePage"));
const InstitutionLayout = lazy(() => import("./pages/institution/InstitutionLayout"));
const AcademicStructurePage = lazy(() => import('./pages/institution/AcademicStructurePage'));
const CourseRegistrationsPage = lazy(() => import('./pages/institution/CourseRegistrationsPage'));
const AcademicDocumentsPage = lazy(() => import('./pages/AcademicDocumentsPage'));
const AcademicRecordPage = lazy(() => import('./pages/student/AcademicRecordPage'));
const StudentProgressionPage = lazy(() => import('./pages/student/StudentProgressionPage'));
const InstitutionProgressionPage = lazy(() => import('./pages/institution/StudentProgressionPage'));
const AcademicYearsPage = lazy(() => import('./pages/institution/AcademicYearsPage'));
const StudentImportPage = lazy(() => import('./pages/institution/StudentImportPage'));
const InstitutionDashboardPage = lazy(() => import("./pages/institution/InstitutionDashboardPage"));
const InstitutionInvitationsPage = lazy(() => import("./pages/institution/InstitutionInvitationsPage"));
const InstitutionTeachersPage = lazy(() => import("./pages/institution/InstitutionTeachersPage"));
const StaffDirectoryPage = lazy(() => import('./pages/institution/StaffDirectoryPage'));
const StaffAllocationsPage = lazy(() => import('./pages/institution/StaffAllocationsPage'));
const StaffAttendancePage = lazy(() => import('./pages/institution/StaffAttendancePage'));
const InstitutionModulesPage = lazy(() => import('./pages/institution/InstitutionModulesPage'));
const InstitutionBillingPage = lazy(() => import('./pages/institution/InstitutionBillingPage'));
const PlatformPaymentsPage = lazy(() => import('./pages/platform/PlatformPaymentsPage'));
const DepartmentsPage = lazy(() => import('./pages/institution/DepartmentsPage'));
const InstitutionTeacherDetailPage = lazy(() => import("./pages/institution/InstitutionTeacherDetailPage"));


const StudentLoginPage = lazy(() => import("./pages/student/StudentLoginPage"));
const StudentForgotPasswordPage = lazy(() => import("./pages/student/StudentForgotPasswordPage"));
const StudentResetPasswordPage = lazy(() => import("./pages/student/StudentResetPasswordPage"));

const TeacherLoginPage = lazy(() => import("./pages/teacher/TeacherLoginPage"));
const TeacherForgotPasswordPage = lazy(() => import("./pages/teacher/TeacherForgotPasswordPage"));
const TeacherResetPasswordPage = lazy(() => import("./pages/teacher/TeacherResetPasswordPage"));

// Old subject links (bookmarks, notifications) open the matching course page.
function StudentSubjectRedirect() {
  const { subjectId } = useParams();
  return <Navigate to={`/student/courses/${subjectId}`} replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div role="status" className="route-loading">Opening your workspace...</div>}>
      <Routes>
        <Route path="/" element={<LoginPage key="staff-home" />} />
        <Route path="/sign-in" element={<LoginPage key="staff-sign-in" />} />
        <Route path="/login" element={<LoginPage key="staff-admin" />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/invite/:token" element={<InvitePage />} />
        <Route path="/set-password" element={<SetPasswordPage />} />
        <Route path="/student/login" element={<StudentLoginPage />} />
        <Route path="/student/forgot-password" element={<StudentForgotPasswordPage />} />
        <Route path="/student/reset-password" element={<StudentResetPasswordPage />} />
        <Route
          path="/student/change-password"
          element={<ProtectedRoute allowedRoles={["STUDENT"]}><ChangePasswordPage /></ProtectedRoute>}
        />
        <Route
          path="/teacher/change-password"
          element={<ProtectedRoute allowedRoles={["TEACHER", "STAFF"]}><ChangePasswordPage /></ProtectedRoute>}
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
          <Route path="staff" element={<StaffDirectoryPage />} />
          <Route path="departments" element={<DepartmentsPage />} />
          <Route path="allocations" element={<StaffAllocationsPage />} />
          <Route path="staff-attendance" element={<StaffAttendancePage />} />
          <Route path="modules" element={<InstitutionModulesPage />} />
          <Route path="billing" element={<InstitutionBillingPage />} />
          <Route path="reports" element={<AcademicDocumentsPage />} />
          <Route path="invitations" element={<InstitutionInvitationsPage />} />
          <Route path="teachers" element={<InstitutionTeachersPage />} />
          <Route path="teachers/:teacherId" element={<InstitutionTeacherDetailPage />} />
          <Route path="classes" element={<InstitutionClassesPage />} />
          <Route path="progression" element={<InstitutionProgressionPage />} />
          <Route path="academic-years" element={<AcademicYearsPage />} />
          <Route path="academic-structure" element={<AcademicStructurePage />} />
          <Route path="course-enrollment" element={<CourseRegistrationsPage />} />
          <Route path="student-imports" element={<StudentImportPage />} />
          <Route path="classes/:classId" element={<ClassStudentsPage />} />
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="students" element={<AdminUsersPage key="students" studentsOnly />} />
          <Route path="student-records" element={<StudentRecordsPage />} />
          <Route path="fees" element={<FeeStatusPage />} />
          <Route path="announcements" element={<AnnouncementsPage />} />
          <Route path="timetable" element={<TimetableAdminPage />} />
          <Route path="marks" element={<MarksPage />} />
          <Route path="grading" element={<GradingPage />} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="users" element={<AdminUsersPage key="institution-users" />} />
          <Route path="attendance" element={<TeacherAttendancePage />} />
          <Route path="coursework" element={<TeacherCourseworkPage />} />
          <Route path="materials" element={<TeacherMaterialsPage />} />
          <Route path="scores" element={<TeacherScoresPage />} />
          <Route path="courses" element={<TeachingCoursesPage />} />
          <Route path="courses/:subjectId" element={<TeachingCoursePage />} />
          <Route path="quizzes/:quizId" element={<QuizBuilderPage />} />
          <Route path="course-registration" element={<RegistrationAdminPage />} />
          <Route path="requests" element={<InstitutionRequestsPage />} />
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
          <Route path="reports" element={<AcademicDocumentsPage />} />
          <Route path="profile" element={<TeacherProfilePage />} />
          <Route path="allocations" element={<TeacherAllocationsPage />} />
          <Route path="classes" element={<TeacherClassesPage />} />
          <Route path="classes/:classId" element={<ClassStudentsPage />} />
          <Route path="attendance" element={<TeacherAttendancePage />} />
          <Route path="coursework" element={<TeacherCourseworkPage />} />
          <Route path="materials" element={<TeacherMaterialsPage />} />
          <Route path="scores" element={<TeacherScoresPage />} />
          <Route path="student-records" element={<StudentRecordsPage />} />
          <Route path="fees" element={<FeeStatusPage />} />
          <Route path="announcements" element={<AnnouncementsPage />} />
          <Route path="timetable" element={<MyTimetablePage />} />
          <Route path="marks" element={<MarksPage />} />
          <Route path="courses" element={<TeachingCoursesPage />} />
          <Route path="courses/:subjectId" element={<TeachingCoursePage />} />
          <Route path="quizzes/:quizId" element={<QuizBuilderPage />} />
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
          <Route path="reports" element={<AcademicDocumentsPage />} />
          <Route path="subjects" element={<Navigate to="/student/courses" replace />} />
          <Route path="subjects/:subjectId" element={<StudentSubjectRedirect />} />
          <Route path="courses" element={<StudentCoursesPage />} />
          <Route path="courses/:subjectId" element={<StudentCoursePage />} />
          <Route path="quizzes/:quizId" element={<StudentQuizPage />} />
          <Route path="quiz-attempts/:attemptId" element={<QuizAttemptPage />} />
          <Route path="registration" element={<StudentRegistrationPage />} />
          <Route path="attendance" element={<StudentAttendancePage />} />
          <Route path="assignments" element={<StudentCourseworkPage />} />
          <Route path="assignments/:assignmentId" element={<StudentAssignmentPage />} />
          <Route path="grades" element={<StudentCourseworkPage gradesOnly />} />
          <Route path="profile" element={<StudentProfilePage />} />
          <Route path="progression" element={<StudentProgressionPage />} />
          <Route path="academic-record" element={<AcademicRecordPage />} />
          <Route path="announcements" element={<AnnouncementsPage />} />
          <Route path="timetable" element={<MyTimetablePage />} />
        </Route>
        <Route
          path="/staff"
          element={
            <ProtectedRoute allowedRoles={["STAFF"]}>
              <StaffLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<StaffDashboardPage />} />
          <Route path="staff" element={<StaffPermissionGate permission="staff.view"><StaffDirectoryPage readOnly /></StaffPermissionGate>} />
          <Route path="staff-attendance" element={<StaffPermissionGate permission="staff_attendance.manage"><StaffAttendancePage /></StaffPermissionGate>} />
          <Route path="students" element={<StaffPermissionGate permission="students.view"><StudentRecordsPage /></StaffPermissionGate>} />
          <Route path="fees" element={<StaffPermissionGate permission="fees.manage"><FeeStatusPage /></StaffPermissionGate>} />
          <Route path="course-registration" element={<StaffPermissionGate permission="registrations.approve"><RegistrationAdminPage /></StaffPermissionGate>} />
          <Route path="announcements" element={<AnnouncementsPage />} />
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
          <Route path="grading-requests" element={<PlatformGradingRequestsPage />} />
          <Route path="messaging" element={<PlatformMessagingPage />} />
          <Route path="storage" element={<PlatformStoragePage />} />
          <Route path="requests" element={<PlatformRequestsPage />} />
          <Route path="institutions" element={<PlatformInstitutionsPage />} />
          <Route path="institutions/:institutionId" element={<PlatformInstitutionDetailPage />} />
          <Route path="billing" element={<PlatformBillingPage />} />
          <Route path="payments" element={<PlatformPaymentsPage />} />
          <Route path="backup" element={<PlatformBackupPage />} />
          <Route path="restore" element={<PlatformRestorePage />} />
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="users" element={<AdminUsersPage key="platform-users" platform />} />
          <Route path="usage" element={<PlatformUsagePage />} />
          <Route path="revenue" element={<Navigate to="/platform/usage" replace />} />
          <Route path="audit-logs" element={<AdminAuditPage platform />} />
          <Route path="settings" element={<><AdminAccountPage /><PlatformSecretSettings /></>} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
