import { useState } from "react";
import { Link } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, QueryState } from "../teacher/TeachingUI";
import { shortDate } from "../elearning/format";
import "../elearning/Elearning.css";
import { SecretAnswer } from "./PlatformSecret";
import "../records/Records.css";

/** Terminate, reactivate and permanently delete an institution. */
export function InstitutionLifecycle({ root, institution }) {
  const mutation = useTeachingMutation();
  const [days, setDays] = useState(30);
  const [reason, setReason] = useState("");
  const [name, setName] = useState("");
  const [answer, setAnswer] = useState("");
  const terminated = institution.status === "ARCHIVED";
  const deletable = terminated && institution.delete_after && new Date(institution.delete_after) <= new Date();
  const matches = name.trim() === institution.name;
  return <section className="teaching-panel danger-zone" aria-labelledby="lifecycle"><h2 id="lifecycle">End this institution</h2>
    <MutationState mutation={mutation} message="Saved." />
    {!terminated ? <form className="teaching-form" onSubmit={e => { e.preventDefault(); mutation.mutate({ path: `${root}/terminate`, body: { days: Number(days), reason, confirm_name: name, answer } }); }}>
      <p>Terminating locks everyone at this institution out straight away. Its data is kept until the deletion date, and you can reactivate it until then. Download a backup first if the school may want its records.</p>
      <Field label="Days before it can be permanently deleted" type="number" min="1" max="3650" required value={days} onChange={e => setDays(e.target.value)} />
      <Field label="Reason (kept on the audit trail)" required minLength={3} maxLength={300} value={reason} onChange={e => setReason(e.target.value)} />
      <Field label={`Type "${institution.name}" to confirm`} required value={name} onChange={e => setName(e.target.value)} />
      <SecretAnswer value={answer} onChange={setAnswer} />
      <div className="teaching-actions"><button className="btn btn--danger" disabled={!matches || reason.trim().length < 3 || !answer || mutation.isPending}>Terminate institution</button></div>
    </form> : <>
      <p>Terminated {shortDate(institution.archived_at)}. {deletable ? "The waiting period is over; it can now be permanently deleted." : `It can be permanently deleted after ${shortDate(institution.delete_after)}.`}</p>
      <div className="teaching-actions"><button type="button" className="btn" disabled={mutation.isPending} onClick={() => mutation.mutate({ path: `${root}/reactivate` })}>Reactivate</button>
        <Link to="/platform/backup">Download a backup</Link></div>
      {deletable && <form className="teaching-form" onSubmit={e => { e.preventDefault(); mutation.mutate({ path: `${root}/permanent-delete`, body: { confirm_name: name, answer } }); }}>
        <p className="teaching-notice">Permanent deletion removes every account, record and uploaded file of this institution. It cannot be undone.</p>
        <Field label={`Type "${institution.name}" to confirm`} required value={name} onChange={e => setName(e.target.value)} />
        <SecretAnswer value={answer} onChange={setAnswer} />
        <div className="teaching-actions"><button className="btn btn--danger" disabled={!matches || !answer || mutation.isPending}>Delete permanently</button></div>
      </form>}
    </>}
  </section>;
}

const HEALTH = { database: "Database", rate_limits: "Sign-in protection (Redis)", email: "Email (Resend)", sms: "SMS (Africa's Talking)", mpesa: "M-Pesa", file_storage: "File storage (R2)" };
const STATE = { ok: "Working", off: "Not set up", down: "Not responding" };

/** What needs the platform admin's attention, on the dashboard. */
export function PlatformOverview() {
  const query = useTeachingQuery("/api/platform/overview", { refetchInterval: 60000 });
  const d = query.data;
  if (!d) return <QueryState query={query} />;
  return <>
    <div className="overview-grid">
      <section className="teaching-panel"><h2>Waiting for you</h2>
        <ul className="overview-list">
          <li><Link to="/platform/requests">School requests</Link><strong>{d.open_requests}</strong></li>
          <li><Link to="/platform/grading-requests">Grading changes</Link><strong>{d.grading_requests}</strong></li>
        </ul></section>
      <section className="teaching-panel"><h2>Service health</h2>
        <ul className="overview-list">{Object.entries(d.health).map(([k, v]) => <li key={k}><span>{HEALTH[k]}</span><span className={`health health--${v}`}>{STATE[v]}</span></li>)}</ul></section>
      <section className="teaching-panel"><h2>Subscriptions due in 14 days</h2>
        {d.expiring.length ? <ul className="overview-list">{d.expiring.map(s => <li key={s.institution_id}><Link to={`/platform/institutions/${s.institution_id}`}>{s.name}</Link>
          <span className={s.overdue ? "health health--down" : "teaching-muted"}>{s.overdue ? "Overdue since " : ""}{new Date(`${s.next_due_date}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" })}{s.frozen ? " · frozen" : ""}</span></li>)}</ul> : <Empty>None.</Empty>}</section>
      {d.terminated.length > 0 && <section className="teaching-panel"><h2>Terminated schools</h2>
        <ul className="overview-list">{d.terminated.map(t => <li key={t.institution_id}><Link to={`/platform/institutions/${t.institution_id}`}>{t.name}</Link><span className="teaching-muted">deletable after {shortDate(t.delete_after)}</span></li>)}</ul></section>}
    </div>
    <section className="teaching-panel"><h2>Recent activity</h2>
      {d.recent.length ? <ul className="overview-activity">{d.recent.map((e, i) => <li key={i}><time>{shortDate(e.created_at)}</time><span><strong>{e.action.replaceAll(/[._]/g, " ")}</strong>{e.institution ? ` · ${e.institution}` : ""}{e.actor ? ` · ${e.actor}` : ""}<br /><small className="teaching-muted">{e.detail}</small></span></li>)}</ul> : <Empty>No activity yet.</Empty>}
      <p><Link to="/platform/audit-logs">Full audit trail</Link></p></section>
  </>;
}
