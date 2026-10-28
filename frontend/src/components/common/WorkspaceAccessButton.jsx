import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";

export default function WorkspaceAccessButton({ userId, role, disabled = false }) {
  const { user, workspace, startWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const actor = workspace?.actor || user;
  const fullAccess = actor.role === "PLATFORM_ADMIN";
  const permitted = fullAccess ? ["INSTITUTION_ADMIN", "TEACHER", "STUDENT"].includes(role)
    : actor.role === "INSTITUTION_ADMIN" ? ["TEACHER", "STUDENT"].includes(role)
    : actor.role === "TEACHER" && role === "STUDENT";
  if (!permitted || actor.id === userId) return null;

  async function open() {
    setError("");
    try {
      const target = await startWorkspace(userId);
      navigate(getRoleHomePath(target.role), { replace: true });
    } catch (err) {
      setError(err.message);
    }
  }

  return <div className="workspace-access-action">
    <button type="button" disabled={disabled || isWorkspaceChanging} onClick={open}>
      {isWorkspaceChanging ? "Opening…" : fullAccess ? "Open workspace · full access" : "View workspace · read-only"}
    </button>
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>;
}
