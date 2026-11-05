import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";

export default function WorkspaceAccessButton({ userId, role, disabled = false }) {
  const { user, workspace, startWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [opening, setOpening] = useState(false);
  const actor = workspace?.actor || user;
  const fullAccess = actor.role === "PLATFORM_ADMIN";
  const permitted = fullAccess ? ["INSTITUTION_ADMIN", "TEACHER", "STUDENT"].includes(role)
    : actor.role === "INSTITUTION_ADMIN" ? ["TEACHER", "STUDENT"].includes(role)
    : actor.role === "TEACHER" && role === "STUDENT";
  if (!permitted || actor.id === userId) return null;

  async function open() {
    if (disabled || isWorkspaceChanging || opening) return;
    setError("");
    setOpening(true);
    try {
      const target = await startWorkspace(userId);
      navigate(getRoleHomePath(target.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setOpening(false);
    }
  }

  return <div className="workspace-access-action">
    <button type="button" disabled={disabled || opening} aria-disabled={disabled || isWorkspaceChanging || opening} aria-busy={opening} onClick={open}>
      {opening ? "Opening…" : fullAccess ? "Open workspace · full access" : "View workspace · read-only"}
    </button>
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>;
}
