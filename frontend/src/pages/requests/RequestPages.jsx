import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { shortDate } from "../elearning/format";
import "../elearning/Elearning.css";

const KINDS = {
  ACCOUNT_DELETION: ["Delete an account", "Close a teacher, student or staff account for good. Personal details are removed; marks and attendance stay."],
  PASSWORD_RESET: ["Password reset", "The platform sends a secure reset link to the person's email."],
  ACCOUNT_RECOVERY: ["Account recovery", "The person lost access to their email. The platform changes it and sends a reset link."],
  INSTITUTION_CHANGE: ["Change institution details", "Name, type, country or contact details you can't edit yourself."],
  OTHER: ["Other request", "Anything else that needs the platform. Describe it in a sentence or two."],
};
const STATUS = { PENDING: "Waiting", APPROVED: "Approved", REJECTED: "Rejected", COMPLETED: "Done", WITHDRAWN: "Withdrawn" };
const STATUS_CLASS = { PENDING: "TODO", APPROVED: "OPEN", REJECTED: "MISSED", COMPLETED: "DONE", WITHDRAWN: "CLOSED" };
const FIELDS = { name: "Name", type: "Institution type", country: "Country", address: "Address", official_email: "Official email", phone: "Phone", website: "Website" };
const TYPES = ["KINDERGARTEN", "PRIMARY_SCHOOL", "HIGH_SCHOOL", "COLLEGE", "UNIVERSITY", "TRAINING_INSTITUTION", "OTHER"];
const TARGETED = ["ACCOUNT_DELETION", "PASSWORD_RESET", "ACCOUNT_RECOVERY"];

function Changes({ changes }) {
  const entries = Object.entries(changes || {});
  if (!entries.length) return null;
  return <dl className="request-changes">{entries.map(([k, v]) => <div key={k}><dt>{FIELDS[k] || (k === "email" ? "New email" : k)}</dt><dd>{v || "(clear)"}</dd></div>)}</dl>;
}

function RequestCard({ r, children }) {
  return <article className="teaching-panel request-card">
    <div className="section-header"><h3>{r.kind_label}{r.institution_name ? ` · ${r.institution_name}` : ""}</h3>
      <span className={`course-status course-status--${STATUS_CLASS[r.status]}`}>{STATUS[r.status]}</span></div>
    <p className="teaching-muted">Sent {shortDate(r.created_at)}{r.requested_by ? ` by ${r.requested_by}` : ""}{r.target_label ? ` · about ${r.target_label}` : ""}</p>
    {r.details && <p className="teaching-instructions">{r.details}</p>}
    <Changes changes={r.changes} />
    {(r.decision_note || r.reviewed_by) && <p className="request-decision"><strong>{r.status === "COMPLETED" ? "Completed" : r.status === "REJECTED" ? "Rejected" : "Reviewed"}</strong>
      {r.reviewed_by ? ` by ${r.reviewed_by}` : ""}{r.completed_at ? `, ${shortDate(r.completed_at)}` : r.reviewed_at ? `, ${shortDate(r.reviewed_at)}` : ""}{r.decision_note ? `: ${r.decision_note}` : ""}</p>}
    {children}
  </article>;
}

function AccountPicker({ value, onChange, kind }) {
  const [search, setSearch] = useState("");
  const query = useTeachingQuery(search.trim().length >= 2 ? `/api/institution/users?${new URLSearchParams({ search: search.trim(), limit: 10 })}` : null);
  // Another admin can only be helped with a reset link; changing their email could hand over their account.
  const roles = kind === "PASSWORD_RESET" ? ["TEACHER", "STUDENT", "STAFF", "INSTITUTION_ADMIN"] : ["TEACHER", "STUDENT", "STAFF"];
  const options = (query.data?.items || []).filter(u => roles.includes(u.role));
  return <div className="form-field">
    <Field label="Find the account (name, username or email)" type="search" value={search} onChange={e => { setSearch(e.target.value); onChange(null); }} />
    {value ? <p>Chosen: <strong>{value.first_name} {value.last_name}</strong> · {value.role.replaceAll("_", " ").toLowerCase()} · {value.username} <button type="button" onClick={() => onChange(null)}>Change</button></p>
      : search.trim().length >= 2 && <ul className="request-picker">{options.map(u => <li key={u.id}><button type="button" onClick={() => onChange(u)}>{u.first_name} {u.last_name} <small className="teaching-muted">{u.role.replaceAll("_", " ").toLowerCase()} · {u.username}</small></button></li>)}
        {query.data && !options.length && <li className="teaching-muted">No matching account.</li>}</ul>}
  </div>;
}

function NewRequest({ done }) {
  const mutation = useTeachingMutation();
  const [kind, setKind] = useState("ACCOUNT_DELETION");
  const [target, setTarget] = useState(null);
  const [details, setDetails] = useState("");
  const [email, setEmail] = useState("");
  const [changes, setChanges] = useState({});
  const targeted = TARGETED.includes(kind);
  async function submit(event) {
    event.preventDefault();
    const body = { kind, details, target_user_id: targeted ? target?.id : null,
      changes: kind === "ACCOUNT_RECOVERY" ? { email } : kind === "INSTITUTION_CHANGE" ? Object.fromEntries(Object.entries(changes).filter(([, v]) => v !== undefined)) : {} };
    try { await mutation.mutateAsync({ path: "/api/institution/requests", body }); done(); } catch { /* shown below */ }
  }
  return <section className="teaching-panel"><h2>New request</h2>
    <form className="teaching-form" onSubmit={submit}>
      <Field label="What do you need?" value={kind} onChange={e => { setKind(e.target.value); setTarget(null); setChanges({}); mutation.reset(); }} description={KINDS[kind][1]}>
        {Object.entries(KINDS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}</Field>
      {targeted && <AccountPicker value={target} onChange={setTarget} kind={kind} />}
      {kind === "ACCOUNT_RECOVERY" && <Field label="Email address they can use now" type="email" required maxLength={255} value={email} onChange={e => setEmail(e.target.value)} />}
      {kind === "INSTITUTION_CHANGE" && <fieldset className="registration-classes"><legend>Tick what should change and type the new value</legend>
        {Object.entries(FIELDS).map(([key, label]) => <div key={key} className="request-change-row">
          <label className="teaching-checkbox"><input type="checkbox" checked={key in changes} onChange={e => { const next = { ...changes }; if (e.target.checked) next[key] = key === "type" ? TYPES[0] : ""; else delete next[key]; setChanges(next); }} />{label}</label>
          {key in changes && (key === "type" ? <select aria-label="New institution type" value={changes.type} onChange={e => setChanges({ ...changes, type: e.target.value })}>{TYPES.map(t => <option key={t} value={t}>{t.replaceAll("_", " ").toLowerCase()}</option>)}</select>
            : <input aria-label={`New ${label.toLowerCase()}`} value={changes[key]} maxLength={key === "address" ? 500 : 255} onChange={e => setChanges({ ...changes, [key]: e.target.value })} />)}
        </div>)}</fieldset>}
      <div className="form-field"><label htmlFor="request-details">{kind === "ACCOUNT_DELETION" ? "Why should it be deleted?" : kind === "OTHER" ? "What do you need?" : "Anything the platform should know (optional)"}</label>
        <textarea id="request-details" maxLength={2000} required={kind === "ACCOUNT_DELETION" || kind === "OTHER"} value={details} onChange={e => setDetails(e.target.value)} /></div>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending || (targeted && !target)}>{mutation.isPending ? "Sending…" : "Send to platform"}</button><button type="button" onClick={done}>Cancel</button></div>
    </form><MutationState mutation={mutation} />
  </section>;
}

export function InstitutionRequestsPage() {
  const { readOnly } = useAuth();
  const query = useTeachingQuery("/api/institution/requests");
  const mutation = useTeachingMutation();
  const [creating, setCreating] = useState(false);
  const open = (query.data || []).filter(r => ["PENDING", "APPROVED"].includes(r.status));
  const closed = (query.data || []).filter(r => !["PENDING", "APPROVED"].includes(r.status));
  return <><PageHeading title="Requests">Ask the platform for things only it can do, and follow each request until it is done.</PageHeading><QueryState query={query} />
    {!readOnly && (creating ? <NewRequest done={() => setCreating(false)} /> : <div className="teaching-actions"><button type="button" className="btn btn--primary" onClick={() => setCreating(true)}>New request</button></div>)}
    <MutationState mutation={mutation} message="Request withdrawn." />
    {query.data && <>
      <h2 className="section-header">Open</h2>{open.length ? open.map(r => <RequestCard key={r.id} r={r}>
        {r.status === "PENDING" && !readOnly && <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({ path: `/api/institution/requests/${r.id}/withdraw` })}>Withdraw</button></div>}
      </RequestCard>) : <Empty>No open requests.</Empty>}
      {closed.length > 0 && <><h2 className="section-header">Finished</h2>{closed.map(r => <RequestCard key={r.id} r={r} />)}</>}
    </>}
  </>;
}

const DOES = {
  ACCOUNT_DELETION: "Closes the account and replaces the person's name, email and phone. Marks, attendance and audit history are kept.",
  PASSWORD_RESET: "Sends a reset link to the account's email.",
  ACCOUNT_RECOVERY: "Changes the account's email to the one requested, then sends a reset link there.",
  INSTITUTION_CHANGE: "Applies the changes shown.",
  OTHER: "Marks the request done. Carry out the work yourself first.",
};

function Review({ r }) {
  const mutation = useTeachingMutation();
  const [note, setNote] = useState("");
  const [confirm, setConfirm] = useState(false);
  const act = action => mutation.mutate({ path: `/api/platform/requests/${r.id}/decide`, body: { action, note } });
  return <RequestCard r={r}>
    <div className="teaching-form">
      <Field label="Note to the school (needed to reject)" value={note} maxLength={1000} onChange={e => setNote(e.target.value)} />
      <p className="teaching-muted">Complete: {DOES[r.kind]}</p>
      {confirm ? <div className="teaching-notice"><p>Carry this out now? {r.kind === "ACCOUNT_DELETION" ? "This cannot be undone." : ""}</p>
        <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={mutation.isPending} onClick={() => act("COMPLETE")}>Yes, complete</button><button type="button" onClick={() => setConfirm(false)}>Cancel</button></div></div>
        : <div className="teaching-actions">
          <button type="button" className="btn btn--primary" disabled={mutation.isPending} onClick={() => setConfirm(true)}>Complete</button>
          {r.status === "PENDING" && <button type="button" disabled={mutation.isPending} onClick={() => act("APPROVE")}>Approve, complete later</button>}
          <button type="button" disabled={mutation.isPending || note.trim().length < 3} onClick={() => act("REJECT")}>Reject</button>
        </div>}
      <MutationState mutation={mutation} message="Saved. The school has been notified." />
    </div>
  </RequestCard>;
}

export function PlatformRequestsPage() {
  const [status, setStatus] = useState("OPEN");
  const query = useTeachingQuery(`/api/platform/requests${status ? `?status=${status}` : ""}`);
  return <><PageHeading title="Requests">Restricted operations schools have asked for. Grading changes have their own page: <Link to="/platform/grading-requests">Grading requests</Link>.</PageHeading>
    <Field label="Show" value={status} onChange={e => setStatus(e.target.value)}><option value="OPEN">Open (waiting or approved)</option><option value="COMPLETED">Done</option><option value="REJECTED">Rejected</option><option value="">All</option></Field>
    <QueryState query={query} />
    {query.data && (query.data.length ? query.data.map(r => (["PENDING", "APPROVED"].includes(r.status) ? <Review key={r.id} r={r} /> : <RequestCard key={r.id} r={r} />))
      : <Empty>{status === "OPEN" ? "Nothing is waiting." : "Nothing here."}</Empty>)}
  </>;
}
