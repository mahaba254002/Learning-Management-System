import { Navigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { getRoleHomePath } from "./roleRoutes";

/**
 * @param {string[]} [allowedRoles] - if provided, only these roles may
 * access this route. A logged-in user with a different role is redirected
 * to THEIR OWN correct dashboard, not to /login (they are authenticated,
 * just not authorized for this specific page).
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <p style={{ padding: "2rem" }}>Loading...</p>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getRoleHomePath(user.role)} replace />;
  }

  return children;
}