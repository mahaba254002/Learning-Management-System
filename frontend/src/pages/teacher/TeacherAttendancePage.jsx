import WorkspaceForm from "../../components/common/WorkspaceForm";
import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";
import { localDate, studentName } from "./teachingFormat";
import { useWorkDraft } from '../../hooks/useWorkDraft';
import { recordRevision } from './recordRevision';
import { useSearchParams } from 'react-router-dom';
import AttendanceSummary from "./AttendanceSummary";

export default function TeacherAttendancePage() {
  const [params] = useSearchParams();
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const [selection, setSelection] = useState(() => params.get('register') || '');
  const [day, setDay] = useState(() => params.get("day") || localDate());
  const suggestedEnd = params.get("lesson_end") || "";
  const choices = [...(classes.data || []).filter(c => c.can_view_class_register || c.can_manage).map(c => ({ key: `class:${c.id}`, classId: c.id, closed: c.academic_year_status === 'CLOSED', label: `${c.name} · ${c.academic_year} — class register` })),
    ...(subjects.data || []).map(s => ({ key: `subject:${s.id}`, classId: s.class_id, subjectId: s.id, closed: s.academic_year_status === 'CLOSED', label: `${s.class_name} · ${s.academic_year} — ${s.name}` }))];
  const target = choices.find(c => c.key === selection);
  return <><PageHeading title="Attendance">Keep a daily class register or record attendance for a subject you teach.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} />
    <div className="teaching-toolbar"><Field label="Class or subject" value={selection} onChange={e => setSelection(e.target.value)}><option value="">Choose a register</option>{choices.map(c => <option key={c.key} value={c.key}>{c.label}</option>)}</Field>
      <Field label="Attendance date" type="date" value={day} max={localDate()} onChange={e => setDay(e.target.value)} required /></div>
    {!classes.isLoading && !subjects.isLoading && !choices.length && <Empty>No registers assigned yet.</Empty>}
    {target && day && <Register key={`${target.key}:${day}`} target={target} day={day} suggestedEnd={suggestedEnd} />}
    {(classes.data || subjects.data) && <AttendanceSummary classes={[...new Map([...(classes.data || []).map(c => [c.id, `${c.name} · ${c.academic_year}`]), ...(subjects.data || []).map(s => [s.class_id, `${s.class_name} · ${s.academic_year}`])]).entries()]} initial={target?.classId} />}
  </>;
}

function Register({ target, day, suggestedEnd = "" }) {
  const roster = useTeachingQuery(target.subjectId ? `/api/teaching/subjects/${target.subjectId}/students` : `/api/teaching/classes/${target.classId}/students`);
  const saved = useTeachingQuery(`/api/teaching/classes/${target.classId}/attendance?day=${day}${target.subjectId ? `&subject_id=${target.subjectId}` : ""}`);
  const mutation = useTeachingMutation();
  const draft = useWorkDraft('attendance', `${target.classId}:${day}${target.subjectId ? `:${target.subjectId}` : ''}`);
  const edits = draft.value;
  const setEdits = draft.change;
  const records = Object.fromEntries((saved.data || []).map(r => [r.student_id, r]));
  const value = (id, field) => edits[id]?.[field] ?? records[id]?.[field] ?? "";
  const savedEnd = (saved.data || []).find(r => r.lesson_end)?.lesson_end?.slice(0, 5) || "";
  const lessonEnd = edits.__lessonEnd ?? (savedEnd || (target.subjectId ? suggestedEnd : ""));
  const change = (id, field, next) => setEdits(old => ({ ...old, __revision: old.__revision ?? recordRevision(saved.data || []), [id]: { ...old[id], [field]: next } }));
  async function submit(event) {
    event.preventDefault();
    const entries = roster.data.filter(s => value(s.id, "status")).map(s => {
      const status = value(s.id, "status");
      const late = status === "LATE";
      return { student_id: s.id, status, note: value(s.id, "note"), arrived_at: late && value(s.id, "arrived_at") ? String(value(s.id, "arrived_at")).slice(0, 5) : null, reason_accepted: late && Boolean(value(s.id, "reason_accepted")) };
    });
    try {
      await mutation.mutateAsync({ path: `/api/teaching/classes/${target.classId}/attendance`, method: "PUT", body: { day, subject_id: target.subjectId || null, lesson_end: target.subjectId && lessonEnd ? lessonEnd : null, entries, expected_revision: edits.__revision ?? recordRevision(saved.data) } });
      await draft.clear();
    } catch { /* Error shown below. */ }
  }
  return <section className="teaching-panel"><h2>{target.label}</h2><QueryState query={roster} /><QueryState query={saved} />
    <p role="status" className="teaching-muted">{draft.status}</p>
    <MutationState mutation={mutation} message="Attendance saved." />
    {mutation.error?.status === 409 && <button type="button" onClick={async () => { const result = await saved.refetch(); if (result.data) setEdits(old => ({ ...old, __revision: recordRevision(result.data) })); }}>Reload current register, keeping my draft for review</button>}
    {target.closed && <p className="teaching-notice">This academic year is closed. The register is read-only.</p>}
    {roster.data && saved.data && (!roster.data.length ? <Empty>No students enrolled.</Empty> : <WorkspaceForm onSubmit={submit}><fieldset disabled={target.closed || !draft.ready || draft.blocked} className="workspace-form-fields">
      <p className="teaching-muted">Unmarked students stay unmarked. Choose a status before saving. For late students, record the arrival time.</p>
      {target.subjectId && <Field label="Lesson ends at" type="time" value={lessonEnd} disabled={mutation.isPending} onChange={e => setEdits(old => ({ ...old, __revision: old.__revision ?? recordRevision(saved.data || []), __lessonEnd: e.target.value }))}
        description="Used for the late rule: arriving close to the end counts as absent unless you accept a reason." />}
      <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={() => setEdits({ __revision: edits.__revision ?? recordRevision(saved.data), ...Object.fromEntries(roster.data.map(s => [s.id, { status: "PRESENT", note: value(s.id, "note") }])) })}>Mark all present</button></div>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Student</th><th>Status</th><th>Late arrival</th><th>Note or reason</th></tr></thead><tbody>{roster.data.map(s => <tr key={s.id}>
        <td>{studentName(s)}<div className="teaching-muted">{s.admission_number}</div></td>
        <td><select aria-label={`Attendance for ${studentName(s)}`} value={value(s.id, "status")} disabled={mutation.isPending} onChange={e => change(s.id, "status", e.target.value)}>
          <option value="" disabled={Boolean(records[s.id])}>Unmarked</option>{["PRESENT", "ABSENT", "LATE", "EXCUSED"].map(v => <option key={v} value={v}>{v.toLowerCase()}</option>)}
        </select>{records[s.id]?.outcome === "MISSED" && records[s.id]?.status === "LATE" && <div className="teaching-muted">Counts as absent</div>}</td>
        <td>{value(s.id, "status") === "LATE" ? <div className="attendance-late">
          <input type="time" aria-label={`Arrival time for ${studentName(s)}`} value={String(value(s.id, "arrived_at")).slice(0, 5)} disabled={mutation.isPending} onChange={e => change(s.id, "arrived_at", e.target.value)} />
          <label><input type="checkbox" checked={Boolean(value(s.id, "reason_accepted"))} disabled={mutation.isPending} onChange={e => change(s.id, "reason_accepted", e.target.checked)} /> Reason accepted</label>
        </div> : <span className="teaching-muted">—</span>}</td>
        <td><input aria-label={`Attendance note for ${studentName(s)}`} value={value(s.id, "note")} maxLength={500} disabled={mutation.isPending} onChange={e => change(s.id, "note", e.target.value)} /></td>
      </tr>)}</tbody></table></div>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending || !roster.data.some(s => value(s.id, "status"))}>{mutation.isPending ? "Saving…" : "Save attendance"}</button></div>
    </fieldset></WorkspaceForm>)}
  </section>;
}
