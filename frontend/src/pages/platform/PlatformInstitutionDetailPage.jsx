import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import WorkspaceAccessButton from "../../components/common/WorkspaceAccessButton";
import RecordChart from "../../components/common/RecordChart";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../teacher/TeachingWorkspace.css";
import InstitutionAcademicSetup from './InstitutionAcademicSetup';

export default function PlatformInstitutionDetailPage() {
  const { institutionId } = useParams();
  return <InstitutionDetail key={institutionId} institutionId={institutionId} />;
}

function InstitutionDetail({ institutionId }) {
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [offset, setOffset] = useState(0);
  const root = `/api/platform/institutions/${institutionId}`;
  const query = useTeachingQuery(`${root}/detail?${new URLSearchParams({ search, offset, ...(role ? { role } : {}) })}`, { refetchInterval: 30000 });
  const data = query.data;
  return <><Link to="/platform/institutions">All institutions</Link><PageHeading title={data?.institution.name || "Institution details"}>Institution records and subscription controls. Data refreshes every 30 seconds.</PageHeading><QueryState query={query} />
    {data && <><p>{data.institution.type.replaceAll("_", " ")} · {data.institution.code} · {data.institution.status} · {data.institution.official_email || "No official email"}</p>
      <div className="teaching-grid"><RecordChart title="Institution accounts" entries={Object.entries(data.users_by_role)} /><RecordChart title="Daily attendance records" entries={Object.entries(data.attendance)} /></div>
      <Billing root={root} initial={data.billing} />
      <InstitutionAcademicSetup root={root} />
      <section className="teaching-panel"><h2>Students, teachers and administrators</h2>
        <div className="teaching-toolbar"><Field label="Search institution accounts" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} /><Field label="Role" value={role} onChange={e => { setRole(e.target.value); setOffset(0); }}><option value="">All roles</option>{["STUDENT", "TEACHER", "INSTITUTION_ADMIN"].map(r => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}</Field></div>
        <div className="table-wrapper"><table className="data-table"><thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Status</th><th>Workspace</th></tr></thead><tbody>{data.users.items.map(user => <tr key={user.id}><td>{user.first_name} {user.last_name}</td><td>{user.role.replaceAll("_", " ")}</td><td>{user.email || "No email"}</td><td>{user.status}</td><td><WorkspaceAccessButton userId={user.id} role={user.role} /></td></tr>)}</tbody></table></div>
        {!data.users.total && <p>No matching accounts.</p>}<div className="teaching-actions"><button disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{data.users.total ? offset + 1 : 0}–{Math.min(offset + 50, data.users.total)} of {data.users.total}</span><button disabled={offset + 50 >= data.users.total} onClick={() => setOffset(offset + 50)}>Next</button></div>
      </section>
    </>}
  </>;
}

function Billing({ root, initial }) {
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(false);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const body = { ...values, expected_due_date: initial.next_due_date, next_due_date: values.next_due_date || null, enforcement_enabled: values.enforcement_enabled === "on", manually_frozen: values.manually_frozen === "on" };
    try { await mutation.mutateAsync({ path: `${root}/subscription`, method: "PUT", body }); setEditing(false); } catch { /* Shown below. */ }
  }
  async function pay(event) {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await mutation.mutateAsync({ path: `${root}/payments`, body: { ...Object.fromEntries(new FormData(form)), expected_due_date: initial.next_due_date } });
      form.reset();
    } catch { /* Keep inputs on failure. */ }
  }
  return <section className="teaching-panel"><h2>Subscription · {initial.status.replaceAll("_", " ")}</h2>
    <p>KES {Number(initial.monthly_fee).toLocaleString()} per month · Next due: {initial.next_due_date || "Not configured"} · Grace: {initial.grace_days} days</p>
    <p>{initial.freeze_date ? `Access freezes at 00:00 Kenya time on ${initial.freeze_date} if unpaid.` : "Automatic freezing is disabled until a subscription is configured."} Support: {initial.support_email || "Not set"}</p>
    {initial.frozen && <p role="status">Academic access is frozen. Recording payment advances the due date; any manual freeze must also be cleared.</p>}
    <MutationState mutation={mutation} message="Subscription updated." />
    <button type="button" onClick={() => setEditing(value => !value)}>{editing ? "Cancel configuration" : "Configure subscription / freeze"}</button>
    {editing && <form className="teaching-form" onSubmit={save}>
      <Field label="Monthly subscription (KES)" type="number" name="monthly_fee" required min="0" max="100000000" step="0.01" defaultValue={initial.monthly_fee} />
      <Field label="Next due date" type="date" name="next_due_date" defaultValue={initial.next_due_date || ""} />
      <Field label="Grace days" type="number" name="grace_days" required min="0" max="90" defaultValue={initial.grace_days} />
      <Field label="Support email" type="email" name="support_email" required maxLength={255} defaultValue={initial.support_email} />
      <label><input type="checkbox" name="enforcement_enabled" defaultChecked={initial.enforcement_enabled} /> Automatically freeze overdue access</label>
      <label><input type="checkbox" name="manually_frozen" defaultChecked={initial.manually_frozen} /> Freeze access manually</label>
      <p>Saving an overdue due date with enforcement enabled, or selecting manual freeze, immediately blocks institution access.</p>
      <button className="btn btn--primary" disabled={mutation.isPending}>Save subscription</button>
    </form>}
    {initial.status !== "NOT_CONFIGURED" && <details><summary>Record a received payment</summary><p>Record verified payments only. This records a payment; it does not collect money. Set the next agreed monthly due date explicitly.</p>
      <form className="teaching-form" onSubmit={pay}>
        <Field label="Amount received (KES)" name="amount" type="number" required min="0.01" max="100000000" step="0.01" />
        <Field label="Unique payment reference" name="reference" required maxLength={100} />
        <Field label="Payment date" name="paid_on" type="date" required />
        <Field label="New next due date" name="next_due_date" type="date" required />
        <button className="btn btn--primary" disabled={mutation.isPending}>Record payment and advance due date</button>
      </form>
    </details>}
    <h3>Recent payments</h3>{!initial.payments.length ? <p>No payments recorded.</p> : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Paid on</th><th>Amount (KES)</th><th>Reference</th><th>Next due</th></tr></thead><tbody>{initial.payments.map(p => <tr key={p.id}><td>{p.paid_on}</td><td>{p.amount}</td><td>{p.reference}</td><td>{p.next_due_date}</td></tr>)}</tbody></table></div>}
  </section>;
}
