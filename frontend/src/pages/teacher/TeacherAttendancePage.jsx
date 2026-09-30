import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";
import { localDate, studentName } from "./teachingFormat";

export default function TeacherAttendancePage() {
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const [selection, setSelection] = useState("");
  const [day, setDay] = useState(localDate);
  const choices = [...(classes.data || []).filter(c => c.can_manage).map(c => ({ key: `class:${c.id}`, classId: c.id, label: `${c.name} · ${c.academic_year} — class register` })),
    ...(subjects.data || []).map(s => ({ key: `subject:${s.id}`, classId: s.class_id, subjectId: s.id, label: `${s.class_name} · ${s.academic_year} — ${s.name}` }))];
  const target = choices.find(c => c.key === selection);
  return <><PageHeading title="Attendance">Keep a daily class register or record attendance for a subject you teach.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} />
    <div className="teaching-toolbar"><Field label="Class or subject" value={selection} onChange={e => setSelection(e.target.value)}><option value="">Choose a register</option>{choices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</Field>
      <Field label="Attendance date" type="date" value={day} max={localDate()} onChange={e => setDay(e.target.value)} required /></div>
    {!classes.isLoading && !subjects.isLoading && !choices.length && <Empty>No registers assigned yet.</Empty>}
    {target && day && <Register key={`${target.key}:${day}`} target={target} day={day} />}
  </>;
}

function Register({ target, day }) {
  const roster = useTeachingQuery(`/api/teaching/classes/${target.classId}/students`);
  const saved = useTeachingQuery(`/api/teaching/classes/${target.classId}/attendance?day=${day}${target.subjectId ? `&subject_id=${target.subjectId}` : ""}`);
  const mutation = useTeachingMutation();
  const [edits, setEdits] = useState({});
  const records = Object.fromEntries((saved.data || []).map(r => [r.student_id, r]));
  const value = (id, field) => edits[id]?.[field] ?? records[id]?.[field] ?? "";
  const change = (id, field, next) => setEdits(old => ({ ...old, [id]: { ...old[id], [field]: next } }));
  async function submit(event) {
    event.preventDefault();
    const entries = roster.data.filter(s => value(s.id, "status")).map(s => ({ student_id: s.id, status: value(s.id, "status"), note: value(s.id, "note") }));
    try {
      await mutation.mutateAsync({ path: `/api/teaching/classes/${target.classId}/attendance`, method: "PUT", body: { day, subject_id: target.subjectId || null, entries } });
      setEdits({});
    } catch { /* Error shown below. */ }
  }
  return <section className="teaching-panel"><h2>{target.label}</h2><QueryState query={roster} /><QueryState query={saved} />
    <MutationState mutation={mutation} message="Attendance saved." />
    {roster.data && saved.data && (!roster.data.length ? <Empty>No students enrolled.</Empty> : <form onSubmit={submit}>
      <p className="teaching-muted">Unmarked students stay unmarked. Choose a status before saving.</p>
      <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={() => setEdits(Object.fromEntries(roster.data.map(s => [s.id, { status: "PRESENT", note: value(s.id, "note") }])))}>Mark all present</button></div>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Student</th><th>Status</th><th>Note</th></tr></thead><tbody>{roster.data.map(s => <tr key={s.id}>
        <td>{studentName(s)}<div className="teaching-muted">{s.admission_number}</div></td>
        <td><select aria-label={`Attendance for ${studentName(s)}`} value={value(s.id, "status")} disabled={mutation.isPending} onChange={e => change(s.id, "status", e.target.value)}>
          <option value="" disabled={Boolean(records[s.id])}>Unmarked</option>{["PRESENT", "ABSENT", "LATE", "EXCUSED"].map(v => <option key={v} value={v}>{v.toLowerCase()}</option>)}
        </select></td><td><input aria-label={`Attendance note for ${studentName(s)}`} value={value(s.id, "note")} maxLength={500} disabled={mutation.isPending} onChange={e => change(s.id, "note", e.target.value)} /></td>
      </tr>)}</tbody></table></div>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending || !roster.data.some(s => value(s.id, "status"))}>{mutation.isPending ? "Saving…" : "Save attendance"}</button></div>
    </form>)}
  </section>;
}
