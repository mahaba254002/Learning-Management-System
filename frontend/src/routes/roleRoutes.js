/**
 * Single source of truth for "where does this role belong". Used by
 * login/change-password redirects AND by ProtectedRoute's role checks —
 * keeping this in one place means both always agree.
 */
export const ROLE_HOME_PATH = {
  PLATFORM_ADMIN: "/platform/dashboard",
  INSTITUTION_ADMIN: "/institution/dashboard",
  TEACHER: "/teacher/dashboard",
  STUDENT: "/student/dashboard",
};

export function getRoleHomePath(role) {
  return ROLE_HOME_PATH[role] || "/";
}

export function getRoleLoginPath(role) {
  if (role === "TEACHER") return "/teacher/login";
  if (role === "STUDENT") return "/student/login";
  return "/login";
}

export function getRoleChangePasswordPath(role) {
  if (role === "TEACHER") return "/teacher/change-password";
  if (role === "STUDENT") return "/student/change-password";
  return "/change-password";
}

export function getProtectedRouteRedirect(user, allowedRoles, pathname) {
  if (!user) return getRoleLoginPath(allowedRoles?.[0]);
  const passwordPath = getRoleChangePasswordPath(user.role);
  if (user.must_change_password && pathname !== passwordPath) return passwordPath;
  if (allowedRoles && !allowedRoles.includes(user.role)) return getRoleHomePath(user.role);
  return null;
}
