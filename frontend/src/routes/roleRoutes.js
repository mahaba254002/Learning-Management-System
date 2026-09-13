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