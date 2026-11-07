import { useState } from "react";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { inputDate, shortDate } from "./format";
import "./Elearning.css";

const CHOICE = { PENDING: "Waiting for approval", APPROVED: "Approved", REJECTED: "Not approved", DROPPED: "Dropped" };
const STATE = { OPEN: "Open", UPCOMING: "Opens soon", CLOSED: "Closed" };

function limits(w) {
  const units = w.min_units === w.max_units ? `${w.max_units}` : `${w.min_units} to ${w.max_units}`;
  const credits = w.min_credits !== null || w.max_credits !== null
    ? `, ${w.max_credits === null ? `at least ${Number(w.min_credits)}` : `${Number(w.min_credits || 0)} to ${Number(w.max_credits)}`} credits` : "";
  return `Choose ${units} unit${w.max_units === 1 ? "" : "s"}${credits}`;
}

function WindowChoices({ window: w }) {
  const { readOnly } = useAuth();
  const mutation = useTeachingMutation();
  const active = id => ["PENDING", "APPROVED"].includes(w.units.find(u => u.id === id)?.status);
  const [chosen, setChosen] = useState(() => w.units.filter(u => active(u.id)).map(u => u.id));
  const open = w.state === "OPEN";
  const credits = w.units.filter(u => chosen.includes(u.id)).reduce((n, u) => n + Number(u.credits || 0), 0);
  async function save() {
    try { await mutation.mutateAsync({ path: `/api/student/registration/${w.id}`, method: "PUT", body: { subject_ids: chosen } }); } catch { /* shown below */ }
  }
  return <section className="teaching-panel" aria-labelledby={`window-${w.id}`}>
    <div className="section-header"><h2 id={`window-${w.id}`}>{w.title}</h2><span className="course-status">{STATE[w.state]}</span></div>
    <p className="teaching-muted">{open ? `Closes ${shortDate(w.closes_at)}` : w.state === "UPCOMING" ? `Opens ${shortDate(w.opens_at)}` : `Closed ${shortDate(w.closes_at)}`} · {limits(w)}</p>
    {w.units.length === 0 ? <Empty>No optional units are offered to your class in this window.</Empty> : <ul className="registration-units">{w.units.map(u => <li key={u.id}>
      <label className="teaching-checkbox"><input type="checkbox" disabled={!open || readOnly} checked={chosen.includes(u.id)}
        onChange={e => setChosen(e.target.checked ? [...chosen, u.id] : chosen.filter(x => x !== u.id))} />
        <span><strong>{u.name}</strong>{u.credits !== null && <small className="teaching-muted"> · {Number(u.credits)} credits</small>}{u.teacher_name && <small className="teaching-muted"> · {u.teacher_name}</small>}</span></label>
      {u.status && <span className={`course-status course-status--${u.status}`}>{CHOICE[u.status]}</span>}
      {u.status === "REJECTED" && u.note && <p className="teaching-muted">Reason: {u.note}</p>}
    </li>)}</ul>}
    {open && w.units.length > 0 && <><p className="teaching-muted">{chosen.length} chosen{credits ? ` · ${credits} credits` : ""}. New choices wait for approval. You can change them until the window closes.</p>
      <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={mutation.isPending || readOnly} onClick={save}>{mutation.isPending ? "Saving…" : "Save my choices"}</button></div></>}
    <MutationState mutation={mutation} message="Choices saved. They will be approved by the office." />
  </section>;
}

export function StudentRegistrationPage() {
  const query = useTeachingQuery("/api/student/registration");
  return <><PageHeading title="Course registration">Choose your optional units when registration is open.</PageHeading><QueryState query={query} />
    {query.data?.length === 0 && <Empty>No course registration is open for you right now.</Empty>}
    {query.data?.map(w => <WindowChoices key={`${w.id}:${w.units.map(u => u.status).join()}`} window={w} />)}
  </>;
}

function WindowForm({ editing, done }) {
  const mutation = useTeachingMutation();
  const years = useTeachingQuery("/api/institution/academic-years");
  const classes = useTeachingQuery("/api/teaching/classes");
  const [classIds, setClassIds] = useState(editing?.class_ids || []);
  async function submit(event) {
    event.preventDefault();
    const f = Object.fromEntries(new FormData(event.currentTarget));
    const number = v => (v === "" ? null : Number(v));
    const body = { title: f.title.trim(), period_id: f.period_id || null, opens_at: new Date(f.opens_at).toISOString(), closes_at: new Date(f.closes_at).toISOString(),
      min_units: Number(f.min_units), max_units: Number(f.max_units), min_credits: number(f.min_credits), max_credits: number(f.max_credits), class_ids: classIds };
    try {
      await mutation.mutateAsync({ path: editing ? `/api/course-registration/windows/${editing.id}` : "/api/course-registration/windows", method: editing ? "PUT" : "POST", body });
      done();
    } catch { /* shown below */ }
  }
  const periods = (years.data?.years || []).flatMap(y => y.periods.map(p => ({ ...p, year: y.name })));
  return <section className="teaching-panel"><h2>{editing ? "Edit window" : "Open a registration window"}</h2>
    <form className="teaching-form" onSubmit={submit}>
      <Field label="Title" name="title" required maxLength={120} defaultValue={editing?.title || ""} placeholder="e.g. Semester 1 electives" />
      <Field label="Term or semester (optional)" name="period_id" defaultValue={editing?.period_id || ""} description="Only optional units in this term or semester are offered.">
        <option value="">Any</option>{periods.map(p => <option key={p.id} value={p.id}>{p.year} · {p.name}</option>)}</Field>
      <div className="quiz-editor__row">
        <Field label="Opens" name="opens_at" type="datetime-local" required defaultValue={inputDate(editing?.opens_at)} />
        <Field label="Closes" name="closes_at" type="datetime-local" required defaultValue={inputDate(editing?.closes_at)} />
      </div>
      <div className="quiz-editor__row">
        <Field label="Fewest units" name="min_units" type="number" min="0" max="50" required defaultValue={editing?.min_units ?? 0} />
        <Field label="Most units" name="max_units" type="number" min="1" max="50" required defaultValue={editing?.max_units ?? 3} />
        <Field label="Fewest credits (optional)" name="min_credits" type="number" min="0" step="0.5" defaultValue={editing?.min_credits ?? ""} />
        <Field label="Most credits (optional)" name="max_credits" type="number" min="0" step="0.5" defaultValue={editing?.max_credits ?? ""} />
      </div>
      <fieldset className="registration-classes"><legend>Classes (none ticked = every class)</legend>
        {(classes.data || []).map(c => <label key={c.id} className="teaching-checkbox"><input type="checkbox" checked={classIds.includes(c.id)}
          onChange={e => setClassIds(e.target.checked ? [...classIds, c.id] : classIds.filter(x => x !== c.id))} />{c.name} · {c.academic_year}</label>)}
      </fieldset>
      <p className="teaching-muted">Students see the optional units of their own class. Their choices wait until you or a staff member with the approval right approves them.</p>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save window</button><button type="button" onClick={done}>Cancel</button></div>
    </form><MutationState mutation={mutation} />
  </section>;
}

function Requests({ windows }) {
  const { readOnly } = useAuth();
  const [windowId, setWindowId] = useState("");
  const [status, setStatus] = useState("PENDING");
  const [picked, setPicked] = useState([]);
  const [note, setNote] = useState("");
  const query = useTeachingQuery(`/api/course-registration/requests?status=${status}${windowId ? `&window_id=${windowId}` : ""}`);
  const mutation = useTeachingMutation();
  const rows = query.data || [];
  async function decide(approve) {
    try {
      const result = await mutation.mutateAsync({ path: "/api/course-registration/decisions", body: { ids: picked, approve, note } });
      setPicked(result.skipped.map(s => s.id)); setNote("");
    } catch { /* shown below */ }
  }
  return <section className="teaching-panel" aria-labelledby="registration-requests"><h2 id="registration-requests">Student choices</h2>
    <div className="quiz-editor__row">
      <Field label="Window" value={windowId} onChange={e => { setWindowId(e.target.value); setPicked([]); }}><option value="">All windows</option>{windows.map(w => <option key={w.id} value={w.id}>{w.title}</option>)}</Field>
      <Field label="Show" value={status} onChange={e => { setStatus(e.target.value); setPicked([]); }}>{Object.entries(CHOICE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
    </div>
    <QueryState query={query} />
    {mutation.data?.skipped?.length > 0 && <div className="teaching-notice" role="status"><p>Some choices were not approved because entry rules are not met. They stay selected:</p>
      <ul>{mutation.data.skipped.map(s => <li key={s.id}>{rows.find(r => r.id === s.id)?.student_name}: {s.reason}</li>)}</ul></div>}
    <MutationState mutation={mutation} message="Decisions saved and students notified." />
    {query.data && (rows.length === 0 ? <Empty>Nothing here.</Empty> : <>
      <div className="table-wrapper"><table className="data-table"><thead><tr>
        {status === "PENDING" && <th scope="col"><input type="checkbox" aria-label="Select all" checked={picked.length === rows.length} onChange={e => setPicked(e.target.checked ? rows.map(r => r.id) : [])} /></th>}
        <th scope="col">Student</th><th scope="col">Class</th><th scope="col">Unit</th><th scope="col">Credits</th><th scope="col">{status === "PENDING" ? "Chosen" : "Note"}</th></tr></thead>
        <tbody>{rows.map(r => <tr key={r.id}>
          {status === "PENDING" && <td><input type="checkbox" aria-label={`Select ${r.student_name}, ${r.subject_name}`} checked={picked.includes(r.id)} onChange={e => setPicked(e.target.checked ? [...picked, r.id] : picked.filter(x => x !== r.id))} /></td>}
          <td>{r.student_name}<br /><small className="teaching-muted">{r.admission_number}</small></td><td>{r.class_name}</td><td>{r.subject_name}</td>
          <td>{r.credits !== null ? Number(r.credits) : "—"}</td><td>{status === "PENDING" ? shortDate(r.requested_at) : r.note || "—"}</td></tr>)}</tbody></table></div>
      {status === "PENDING" && !readOnly && <div className="registration-decide">
        <Field label="Note to students (needed when not approving)" value={note} maxLength={300} onChange={e => setNote(e.target.value)} />
        <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={!picked.length || mutation.isPending} onClick={() => decide(true)}>Approve {picked.length || ""}</button>
          <button type="button" disabled={!picked.length || note.trim().length < 3 || mutation.isPending} onClick={() => decide(false)}>Don't approve</button></div>
      </div>}
    </>)}
  </section>;
}

export function RegistrationAdminPage() {
  const { user, readOnly } = useAuth();
  const admin = user.role === "INSTITUTION_ADMIN";
  const query = useTeachingQuery("/api/course-registration/windows");
  const [editing, setEditing] = useState(null);
  return <><PageHeading title="Course registration">Open windows for students to choose optional units, then approve their choices.</PageHeading><QueryState query={query} />
    {admin && !readOnly && (editing ? <WindowForm key={editing.id || "new"} editing={editing.id ? editing : null} done={() => setEditing(null)} />
      : <div className="teaching-actions"><button type="button" className="btn btn--primary" onClick={() => setEditing({})}>Open a registration window</button></div>)}
    {query.data?.length > 0 && <section className="teaching-panel"><h2>Windows</h2><ul className="registration-windows">{query.data.map(w => <li key={w.id}>
      <span><strong>{w.title}</strong> <span className="course-status">{STATE[w.state]}</span><br /><small className="teaching-muted">{shortDate(w.opens_at)} to {shortDate(w.closes_at)} · {limits(w)}{w.pending ? ` · ${w.pending} waiting` : ""}</small></span>
      {admin && !readOnly && <button type="button" onClick={() => setEditing(w)}>Edit</button>}</li>)}</ul></section>}
    {query.data?.length === 0 && <Empty>No registration windows yet.</Empty>}
    {query.data && <Requests windows={query.data} />}
  </>;
}
