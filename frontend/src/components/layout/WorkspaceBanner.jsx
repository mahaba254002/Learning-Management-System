import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";

/** Shown while a platform admin is viewing someone else's workspace. */
export default function WorkspaceBanner() {
  const { user, workspace, readOnly, stopWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const [returnError, setReturnError] = useState("");
  if (!workspace) return null;
  return (<section className={`workspace-access-banner ${readOnly ? "" : "workspace-access-banner--full"}`} aria-label="Delegated workspace access">
    <div><strong>{readOnly ? "Read-only view" : "Full access"}: {user.first_name} {user.last_name}</strong>
      <p>Signed in as {workspace.actor.first_name} {workspace.actor.last_name}. {readOnly ? "Changes are blocked." : "Actions are recorded under your platform administrator account."}</p></div>
    <button type="button" disabled={isWorkspaceChanging} onClick={async () => {
      setReturnError("");
      try {
        const actor = await stopWorkspace();
        navigate(getRoleHomePath(actor?.role), { replace: true });
      } catch (error) { setReturnError(error.message); }
    }}>{isWorkspaceChanging ? "Returning…" : "Return to my workspace"}</button>
    {returnError && <p role="alert">{returnError}</p>}
  </section>);
}
