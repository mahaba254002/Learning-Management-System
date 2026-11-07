import { useState } from "react";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { FeeTag } from "./FeeStatusPage";
import { kes } from "../../components/billing/money";
import "./Records.css";

const STATUS = { ACTIVE: "Active", TRANSFERRED: "Transferred", GRADUATED: "Graduated", WITHDRAWN: "Withdrawn" };
const today = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Nairobi" });
const values = form => Object.fromEntries(new FormData(form));

function StatusForm({ student }) {
  const mutation = useTeachingMutation();
  const [status, setStatus] = useState(student.status);
  async function submit(event) {
    event.preventDefault();
    const v = values(event.currentTarget);
    if (status !== "ACTIVE" && student.status === "ACTIVE" && !window.confirm(`Mark ${student.first_name} as ${STATUS[status].toLowerCase()}? They leave their current classes. Their records are kept.`)) return;
    try { await mutation.mutateAsync({ path: `/api/records/students/${student.id}/status`, method: "PUT", body: { status, left_on: status === "ACTIVE" ? null : v.left_on, note: v.note } }); } catch { /* Shown below. */ }
  }
  return <form className="records-filters" onSubmit={submit}>
    <Field label="Status" value={status} onChange={e => setStatus(e.target.value)}>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
    {status !== "ACTIVE" && <Field label="Date left" name="left_on" type="date" max={today()} defaultValue={student.left_on || today()} required />}
    <Field label="Note" name="note" maxLength={300} defaultValue={student.status_note} placeholder={status === "TRANSFERRED" ? "New school" : ""} />
    <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save status</button></div>
    <p className="teaching-muted">Transferred and withdrawn students can no longer sign in. Graduates keep access to view their records.</p>
    <MutationState mutation={mutation} message="Status saved." />
  </form>;
}

function Guardians({ student, canEdit }) {
  const mutation = useTeachingMutation();
  const [adding, setAdding] = useState(false);
  const base = `/api/records/students/${student.id}/guardians`;
  async function add(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const v = values(form);
    try {
      await mutation.mutateAsync({ path: base, body: { ...v, email: v.email || null, is_primary: v.is_primary === "on" } });
      form.reset(); setAdding(false);
    } catch { /* Shown below. */ }
  }
  return <section aria-labelledby="guardians-title"><h3 id="guardians-title">Parents and guardians</h3>
    {!student.guardians.length ? <p className="teaching-muted">None recorded.</p> : <ul className="records-list">{student.guardians.map(g => <li key={g.id}>
      <h3>{g.full_name}{g.is_primary && <span className="teaching-muted"> · main contact</span>}</h3>
      <div>{g.relationship} · <a href={`tel:${g.phone}`}>{g.phone}</a>{g.email && <> · <a href={`mailto:${g.email}`}>{g.email}</a></>}</div>
      {g.occupation && <div className="teaching-muted">{g.occupation}</div>}
      {canEdit && <div className="records-actions">
        {!g.is_primary && <button className="btn" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({ path: `${base}/${g.id}`, method: "PUT", body: { relationship: g.relationship, is_primary: true } })}>Make main contact</button>}
        <button className="btn" type="button" disabled={mutation.isPending} onClick={() => window.confirm(`Remove ${g.full_name} from ${student.first_name}'s record?`) && mutation.mutate({ path: `${base}/${g.id}`, method: "DELETE" })}>Remove</button>
      </div>}
    </li>)}</ul>}
    <MutationState mutation={mutation} message={mutation.data?.message || "Saved."} />
    {canEdit && (adding ? <form className="records-filters" onSubmit={add} aria-label="Add a guardian">
      <Field label="Full name" name="full_name" required minLength={2} maxLength={160} />
      <Field label="Phone" name="phone" type="tel" required maxLength={25} placeholder="0712 345 678" />
      <Field label="Relationship" name="relationship" required maxLength={40} list="guardian-relationships" />
      <datalist id="guardian-relationships"><option value="Mother" /><option value="Father" /><option value="Guardian" /><option value="Sponsor" /></datalist>
      <Field label="Email (optional)" name="email" type="email" maxLength={255} />
      <Field label="Occupation (optional)" name="occupation" maxLength={120} />
      <label className="attendance-late"><span><input type="checkbox" name="is_primary" /> Main contact</span></label>
      <p className="teaching-muted">A sibling's guardian with the same phone number is linked rather than added twice.</p>
      <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Add guardian</button><button className="btn" type="button" onClick={() => setAdding(false)}>Cancel</button></div>
    </form> : <button className="btn" type="button" onClick={() => setAdding(true)}>Add guardian</button>)}
  </section>;
}

function Discipline({ student }) {
  const me = useAuth().user.id;
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = values(form);
    try {
      await mutation.mutateAsync(editing && editing !== "new" ? { path: `/api/records/discipline/${editing}`, method: "PUT", body } : { path: `/api/records/students/${student.id}/discipline`, body });
      setEditing(null);
    } catch { /* Shown below. */ }
  }
  const current = student.discipline.find(r => r.id === editing);
  return <section aria-labelledby="discipline-title"><h3 id="discipline-title">Discipline</h3>
    {!student.discipline.length ? <p className="teaching-muted">No incidents recorded.</p> : <ul className="records-list">{student.discipline.map(r => <li key={r.id}>
      <h3>{r.category} · {r.occurred_on}</h3><p className="records-announcement">{r.description}</p>
      {r.action_taken && <p className="records-announcement"><strong>Action taken:</strong> {r.action_taken}</p>}
      {(student.can.edit_status || r.recorded_by === me) && <div className="records-actions"><button className="btn" type="button" onClick={() => setEditing(r.id)}>Edit</button>
        <button className="btn" type="button" disabled={mutation.isPending} onClick={() => window.confirm("Delete this record?") && mutation.mutate({ path: `/api/records/discipline/${r.id}`, method: "DELETE" })}>Delete</button></div>}
    </li>)}</ul>}
    <MutationState mutation={mutation} message="Saved." />
    {editing ? <form key={editing} className="teaching-form" onSubmit={submit} aria-label="Discipline record">
      <Field label="Date" name="occurred_on" type="date" max={today()} defaultValue={current?.occurred_on || today()} required />
      <Field label="Category" name="category" required minLength={2} maxLength={60} defaultValue={current?.category} list="discipline-categories" />
      <datalist id="discipline-categories"><option value="Lateness" /><option value="Absenteeism" /><option value="Misconduct" /><option value="Bullying" /><option value="Property damage" /></datalist>
      <label htmlFor="discipline-description">What happened</label><textarea id="discipline-description" name="description" rows={4} required minLength={3} maxLength={5000} defaultValue={current?.description} />
      <label htmlFor="discipline-action">Action taken</label><textarea id="discipline-action" name="action_taken" rows={3} maxLength={5000} defaultValue={current?.action_taken} />
      <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save record</button><button className="btn" type="button" onClick={() => setEditing(null)}>Cancel</button></div>
    </form> : <button className="btn" type="button" onClick={() => setEditing("new")}>Record an incident</button>}
  </section>;
}

function StudentDetail({ id }) {
  const query = useTeachingQuery(`/api/records/students/${id}`);
  const s = query.data;
  return <section className="teaching-panel" aria-labelledby="student-detail"><QueryState query={query} />
    {s && <>
      <h2 id="student-detail">{s.first_name} {s.last_name}</h2>
      <p>{s.admission_number} · <span className={`records-tag records-tag--${s.status}`}>{STATUS[s.status]}</span>{s.left_on && ` since ${s.left_on}`}{s.status_note && ` · ${s.status_note}`}</p>
      <p className="teaching-muted">{s.classes.length ? s.classes.map(c => `${c.name} (${c.academic_year})`).join(", ") : "Not in a class"}{s.phone && ` · ${s.phone}`}</p>
      {s.can.edit_status && <StatusForm key={`${s.id}:${s.status}`} student={s} />}
      {s.guardians && <Guardians student={s} canEdit={s.can.edit_guardians} />}
      {s.fees && <section aria-labelledby="fees-title"><h3 id="fees-title">Fees</h3>{!s.fees.length ? <p className="teaching-muted">No fee status recorded.</p>
        : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Term</th><th>Status</th><th className="records-num">Balance</th><th>Note</th></tr></thead>
          <tbody>{s.fees.map(f => <tr key={f.period_id}><td>{f.period_name}</td><td><FeeTag status={f.status} /></td><td className="records-num">{kes(f.balance)}</td><td>{f.note}</td></tr>)}</tbody></table></div>}</section>}
      {s.discipline && <Discipline student={s} />}
    </>}
  </section>;
}

export default function StudentRecordsPage() {
  const [filters, setFilters] = useState({ search: "", status: "ACTIVE", class_id: "" });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const params = new URLSearchParams([...Object.entries(filters).filter(([, v]) => v), ["offset", offset]]);
  const query = useTeachingQuery(`/api/records/students?${params}`);
  const data = query.data;
  const set = (key, value) => { setFilters(old => ({ ...old, [key]: value })); setOffset(0); };
  return <><PageHeading title="Student records">Status, parents and guardians, fee standing and discipline for each student.</PageHeading>
    <div className="records-split">
      <section className="teaching-panel" aria-label="Students">
        <div className="records-filters">
          <Field label="Search" type="search" value={filters.search} maxLength={100} onChange={e => set("search", e.target.value)} />
          <Field label="Status" value={filters.status} onChange={e => set("status", e.target.value)}>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}<option value="ALL">All</option></Field>
          {data?.classes?.length > 0 && <Field label="Class" value={filters.class_id} onChange={e => set("class_id", e.target.value)}><option value="">All classes</option>{data.classes.map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>}
        </div>
        <QueryState query={query} />
        {data && (!data.items.length ? <Empty>No students match.</Empty> : <div className="table-wrapper"><table className="data-table records-table">
          <thead><tr><th>Student</th><th>Class</th></tr></thead>
          <tbody>{data.items.map(s => <tr key={s.id} className={selected === s.id ? "records-selected" : undefined}>
            <td><button type="button" className="records-row-button" aria-pressed={selected === s.id} onClick={() => setSelected(s.id)}>{s.first_name} {s.last_name}</button>
              <div className="teaching-muted">{s.admission_number}{s.status !== "ACTIVE" && ` · ${STATUS[s.status]}`}</div></td>
            <td>{s.classes.map(c => c.name).join(", ") || "—"}</td></tr>)}</tbody></table></div>)}
        {data && <div className="operations-pagination"><button className="btn" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{data.total} students</span><button className="btn" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Next</button></div>}
      </section>
      {selected ? <StudentDetail key={selected} id={selected} /> : <section className="teaching-panel"><Empty>Choose a student to see their record.</Empty></section>}
    </div>
  </>;
}
