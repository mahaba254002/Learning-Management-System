import { useId } from "react";
import { Link } from "react-router-dom";
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
  if (query.isError) return <div className="form-error" role="alert">{query.error.message} <button type="button" onClick={() => query.refetch()}>Try again</button>{query.error.status === 401 && <> <Link to="/sign-in">Sign in again</Link></>}</div>;
  return null;
}

export function MutationState({ mutation, message = "Changes saved." }) {
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

