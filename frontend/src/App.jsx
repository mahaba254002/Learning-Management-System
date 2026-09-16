import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/auth/LoginPage";
import ProtectedRoute from "./routes/ProtectedRoute";

import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import ChangePasswordPage from "./pages/auth/ChangePasswordPage";

import PlatformLayout from "./pages/platform/PlatformLayout";
import PlatformDashboardPage from "./pages/platform/PlatformDashboardPage";
import PlatformInstitutionsPage from "./pages/platform/PlatformInstitutionsPage";
import ComingSoon from "./components/common/ComingSoon";
import RoleHoldingPage from "./pages/RoleHoldingPage";

import InvitePage from "./pages/invite/InvitePage";
import InstitutionLayout from "./pages/institution/InstitutionLayout";
import InstitutionDashboardPage from "./pages/institution/InstitutionDashboardPage";
import InstitutionInvitationsPage from "./pages/institution/InstitutionInvitationsPage";
import InstitutionTeachersPage from "./pages/institution/InstitutionTeachersPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/invite/:token" element={<InvitePage />} />

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
          <Route path="students" element={<ComingSoon title="Students" />} />
          <Route path="settings" element={<ComingSoon title="Settings" />} />
        </Route>
        <Route
          path="/teacher/dashboard"
          element={
            <ProtectedRoute allowedRoles={["TEACHER"]}>
              <RoleHoldingPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/student/dashboard"
          element={
            <ProtectedRoute allowedRoles={["STUDENT"]}>
              <RoleHoldingPage />
            </ProtectedRoute>
          }
        />

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
          <Route path="users" element={<ComingSoon title="Platform Users" />} />
          <Route path="revenue" element={<ComingSoon title="Revenue" />} />
          <Route path="audit-logs" element={<ComingSoon title="Audit Logs" />} />
          <Route path="settings" element={<ComingSoon title="Settings" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;