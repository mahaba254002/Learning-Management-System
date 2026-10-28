import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { getProtectedRouteRedirect } from "./roleRoutes";

/**
 * @param {string[]} [allowedRoles] - if provided, only these roles may
 * access this route. A logged-in user with a different role is redirected
 * to THEIR OWN correct dashboard, not to /login (they are authenticated,
 * just not authorized for this specific page).
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { isLoading, user, workspace } = useAuth();
  const { pathname } = useLocation();

  if (isLoading) {
    return <p style={{ padding: "var(--space-8)" }}>Loading...</p>;
  }

  const redirect = getProtectedRouteRedirect(user, allowedRoles, pathname, Boolean(workspace));
  if (redirect) return <Navigate to={redirect} replace />;

  return children;
}
