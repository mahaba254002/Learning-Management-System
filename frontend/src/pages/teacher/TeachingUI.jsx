import { useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";
import "../auth/LoginPage.css";
import "../platform/PlatformDashboardPage.css";
import "./TeachingWorkspace.css";

export function Field({ label, description, children, ...props }) {
  const id = useId();
  const describedBy = [props['aria-describedby'], description ? `${id}-help` : null].filter(Boolean).join(' ') || undefined;
  return <div className="form-field"><label htmlFor={id}>{label}</label>{children
    ? <select id={id} {...props} aria-describedby={describedBy}>{children}</select>
    : <input id={id} {...props} aria-describedby={describedBy} />}{description && <small id={`${id}-help`}>{description}</small>}</div>;
}

export function QueryState({ query }) {
  if (query.isLoading) return <p role="status">Loading…</p>;
  if (query.isError && query.error.code === 'WORKSPACE_ACCESS_EXPIRED') return <WorkspaceAccessRecovery/>;
  if (query.isError) return <div className="form-error" role="alert">{query.error.message} <button type="button" onClick={() => query.refetch()}>Try again</button>{query.error.status === 401 && <> <Link to="/sign-in">Sign in again</Link></>}</div>;
  return null;
}

export function MutationState({ mutation, message = "Changes saved." }) {
  if (mutation.isError && mutation.error.code === 'WORKSPACE_ACCESS_EXPIRED') return <WorkspaceAccessRecovery/>;
  if (mutation.isError) return <p className="form-error" role="alert">{mutation.error.message}</p>;
  if (mutation.isSuccess) return <p className="teaching-notice" role="status">{message}</p>;
  return null;
}

export function PageHeading({ title, children }) {
  return <div className="teaching-heading"><h1 className="page-title">{title}</h1>{children && <p>{children}</p>}</div>;
}

export function Empty({ children }) {
  return <p className="empty-state">{children}</p>;
}


function WorkspaceAccessRecovery() {
  const { stopWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  async function recover() {
    setError('');
    try {
      const actor = await stopWorkspace();
      navigate(actor ? getRoleHomePath(actor.role) : '/sign-in', { replace: true });
    } catch {
      setError('Unable to return yet. Check your connection, then try again.');
    }
  }
  return <section className="workspace-recovery" role="alert">
    <h2>Workspace access has ended</h2>
    <p>Your access to this person’s workspace expired. Return to your own account, then open their workspace again if needed.</p>
    <p>Any change that failed was not confirmed. Check the saved record before submitting again.</p>
    <button type="button" className="btn btn--primary" disabled={isWorkspaceChanging} onClick={recover}>{isWorkspaceChanging ? 'Returning…' : 'Return to my workspace'}</button>
    {error && <p>{error}</p>}
  </section>;
}
