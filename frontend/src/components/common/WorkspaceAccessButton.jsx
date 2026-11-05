import { useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";

// Matches MIN_REASON_LENGTH in backend/app/api/routes/workspace_access.py.
const MIN_REASON_LENGTH = 10;

export default function WorkspaceAccessButton({ userId, role, disabled = false }) {
  const { user, workspace, startWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const reasonId = useId();
  const [error, setError] = useState("");
  const [opening, setOpening] = useState(false);
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const actor = workspace?.actor || user;
  const fullAccess = actor.role === "PLATFORM_ADMIN";
  const permitted = fullAccess ? ["INSTITUTION_ADMIN", "TEACHER", "STUDENT", "STAFF"].includes(role)
    : actor.role === "INSTITUTION_ADMIN" ? ["TEACHER", "STUDENT", "STAFF"].includes(role)
    : actor.role === "TEACHER" && role === "STUDENT";
  if (!permitted || actor.id === userId) return null;

  async function open() {
    if (disabled || isWorkspaceChanging || opening) return;
    setError("");
    setOpening(true);
    try {
      const target = await startWorkspace(userId, fullAccess ? reason.trim() : undefined);
      navigate(getRoleHomePath(target.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setOpening(false);
    }
  }

  if (fullAccess && asking) {
    const short = reason.trim().length < MIN_REASON_LENGTH;
    return <form className="workspace-access-action" onSubmit={(event) => { event.preventDefault(); if (!short) open(); }}>
      <label htmlFor={reasonId}>Reason for opening this workspace</label>
      <textarea id={reasonId} rows={2} maxLength={300} required value={reason} onChange={(event) => setReason(event.target.value)}
        aria-describedby={`${reasonId}-hint`} placeholder="For example: support request about missing marks" />
      <p id={`${reasonId}-hint`} className="field-hint">The institution can see this reason in its audit log.</p>
      <div className="workspace-access-buttons">
        <button type="submit" disabled={disabled || opening || short} aria-busy={opening}>{opening ? "Opening…" : "Open workspace"}</button>
        <button type="button" onClick={() => { setAsking(false); setError(""); }} disabled={opening}>Cancel</button>
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
    </form>;
  }

  return <div className="workspace-access-action">
    <button type="button" disabled={disabled || opening} aria-disabled={disabled || isWorkspaceChanging || opening} aria-busy={opening}
      onClick={fullAccess ? () => setAsking(true) : open}>
      {opening ? "Opening…" : fullAccess ? "Open workspace · full access" : "View workspace · read-only"}
    </button>
    {error && <p className="field-error" role="alert">{error}</p>}
  </div>;
}
