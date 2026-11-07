import { Navigate, useLocation } from "react-router-dom";
import ConnectionScreen from "../components/common/ConnectionScreen";
import { useAuth } from "../context/useAuth";
import { getProtectedRouteRedirect } from "./roleRoutes";

/**
 * @param {string[]} [allowedRoles] - if provided, only these roles may
 * access this route. A logged-in user with a different role is redirected
 * to THEIR OWN correct dashboard, not to /login (they are authenticated,
 * just not authorized for this specific page).
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { isLoading, user, workspace, connection } = useAuth();
  const { pathname, search } = useLocation();

  if (isLoading || connection === "unreachable") return <ConnectionScreen />;

  const redirect = getProtectedRouteRedirect(user, allowedRoles, pathname, Boolean(workspace));
  // Signed-out visitors come back to the page they asked for after signing in.
  if (redirect) return <Navigate to={redirect} replace state={!user ? { from: pathname + search } : undefined} />;

  return children;
}
