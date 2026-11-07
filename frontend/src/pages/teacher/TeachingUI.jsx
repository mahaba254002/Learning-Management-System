import { useId, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { getRoleHomePath } from "../../routes/roleRoutes";
import { describe } from "../../api/errors";
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
  if (query.isLoading) return <p role="status" className="teaching-muted">{query.failureCount > 0 ? "Skynet is starting up. This can take up to a minute…" : "Loading…"}</p>;
  if (query.isError && query.error.code === 'WORKSPACE_ACCESS_EXPIRED') return <WorkspaceAccessRecovery/>;
  if (!query.isError) return null;
  const info = describe(query.error);
  if (info.kind === "denied" || info.kind === "feature") return <AccessDenied title={info.title} text={info.text} />;
  return <div className={`state-message state-message--${info.kind}`} role="alert">
    {info.title && <strong>{info.title}</strong>}<p>{info.text}</p>
    <div className="state-actions">
      {info.kind !== "missing" && info.kind !== "session" && <button type="button" className="btn" disabled={query.isFetching} onClick={() => query.refetch()}>{query.isFetching ? "Trying…" : "Try again"}</button>}
      {info.kind === "session" && <Link className="btn" to="/sign-in">Sign in again</Link>}
    </div>
  </div>;
}

export function MutationState({ mutation, message = "Changes saved." }) {
  if (mutation.isError && mutation.error.code === 'WORKSPACE_ACCESS_EXPIRED') return <WorkspaceAccessRecovery/>;
  if (mutation.isError) {
    const info = describe(mutation.error, { saving: true });
    return <p className={`state-message state-message--${info.kind}`} role="alert">{info.title && <strong>{info.title}. </strong>}{info.text}</p>;
  }
  if (mutation.isSuccess) return <p className="teaching-notice" role="status">{message}</p>;
  return null;
}

/** Shown instead of an error when someone opens something they may not use. */
export function AccessDenied({ title = "No access", text = "You don't have access to this page. If you think you should, ask your administrator." }) {
  const { user } = useAuth();
  return <section className="state-message state-message--denied" role="alert">
    <strong>{title}</strong><p>{text}</p>
    {user && <div className="state-actions"><Link className="btn" to={getRoleHomePath(user.role)}>Go to my home page</Link></div>}
  </section>;
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
