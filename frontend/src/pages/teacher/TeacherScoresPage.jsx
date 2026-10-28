import FinalGradesPanel from './FinalGradesPanel';
import WorkspaceForm from "../../components/common/WorkspaceForm";
import { useAuth } from "../../context/useAuth";
import { useWorkDraft } from '../../hooks/useWorkDraft';
import { recordRevision } from './recordRevision';
import { useSearchParams } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";
import { studentName } from "./teachingFormat";

export default function TeacherScoresPage() {
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const [params, setParams] = useSearchParams();
  const subject = subjects.data?.find(s => s.id === params.get("subject"));
  const works = useTeachingQuery(subject ? `/api/teaching/subjects/${subject.id}/coursework` : null);
  const work = works.data?.find(w => w.id === params.get("assessment"));
  return <><PageHeading title="Scores">View and enter marks for the subjects you teach. Blank entries stay ungraded.</PageHeading><QueryState query={subjects} />
    <div className="teaching-toolbar"><Field label="Teaching subject" value={subject?.id || ""} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">Choose a subject</option>{subjects.data?.map(s => <option key={s.id} value={s.id}>{s.class_name} · {s.academic_year} — {s.name}</option>)}</Field>
      {subject && <Field label="Assessment" value={work?.id || ""} onChange={e => setParams({ subject: subject.id, assessment: e.target.value })}><option value="">Choose an assessment</option>{works.data?.map(w => <option key={w.id} value={w.id}>{w.title} (out of {w.max_score})</option>)}</Field>}
    </div>
    {subject && <QueryState query={works} />}
    {works.data?.length === 0 && <Empty>Create an assessment in Coursework before entering scores.</Empty>}
    {subjects.data?.length === 0 && <Empty>No teaching subjects assigned yet.</Empty>}
    {subject && <FinalGradesPanel key={subject.id} subject={subject}/>}
    {subject && work && <Gradebook key={work.id} subject={subject} work={work} />}
  </>;
}

function Gradebook({ subject, work }) {
  const { readOnly } = useAuth();
  const roster = useTeachingQuery(`/api/teaching/subjects/${subject.id}/students`);
  const saved = useTeachingQuery(`/api/teaching/coursework/${work.id}/scores`);
  const submissions = useTeachingQuery(`/api/teaching/coursework/${work.id}/submissions`);
  const mutation = useTeachingMutation();
  const draft = useWorkDraft('scores', work.id);
  const edits = draft.value;
  const setEdits = draft.change;
  const records = Object.fromEntries((saved.data || []).map(r => [r.student_id, r]));
  const outcomeField = work.assessment_mode === 'COMPETENCY' ? 'competency_label' : 'score';
  const value = (id, field) => edits[id]?.[field] ?? records[id]?.[field] ?? "";
  const change = (id, field, next) => setEdits(old => ({ ...old, __revision: old.__revision ?? recordRevision(saved.data || []), [id]: { ...old[id], [field]: next } }));
  async function submit(event) {
    event.preventDefault();
    const entries = roster.data.filter(s => value(s.id, outcomeField) !== "").map(s => ({ student_id: s.id, [outcomeField]: value(s.id, outcomeField), feedback: value(s.id, "feedback") }));
    try {
      await mutation.mutateAsync({ path: `/api/teaching/coursework/${work.id}/scores`, method: "PUT", body: { entries, expected_revision: edits.__revision ?? recordRevision(saved.data) } });
      await draft.clear();
    } catch { /* Error shown below. */ }
  }
  return <section className="teaching-panel"><h2>{work.title}</h2><p className="teaching-muted">{work.assessment_mode === "COMPETENCY" ? "Competency observation." : `Maximum score: ${work.max_score}.`} {work.published && work.grades_released ? "Results are released to students." : "Marks and feedback are withheld from students."}</p>
    <p role="status" className="teaching-muted">{draft.status}</p>
    {mutation.error?.status === 409 && <button type="button" onClick={async () => { const result = await saved.refetch(); if (result.data) setEdits(old => ({ ...old, __revision: recordRevision(result.data) })); }}>Reload current marks, keeping my draft for review</button>}
    {subject.academic_year_status === 'CLOSED' && <p className="teaching-notice">This academic year is closed. Marks and results are read-only.</p>}
    <button type="button" disabled={subject.academic_year_status === 'CLOSED' || readOnly || mutation.isPending || !work.published} onClick={async () => {
      try { await mutation.mutateAsync({ path: `/api/teaching/coursework/${work.id}/results-release`, method: "PUT", body: { released: !work.grades_released } }); } catch { /* Shown below. */ }
    }}>{work.grades_released ? "Withhold results" : "Release results to students"}</button>
    <QueryState query={roster} /><QueryState query={saved} /><QueryState query={submissions} /><MutationState mutation={mutation} message="Scores saved." />
    <section aria-label="Student submissions"><h3>Submitted work</h3>{submissions.data?.length === 0 && <Empty>No final submissions yet. Drafts are not listed here.</Empty>}
      {submissions.data?.map(s => <details key={s.id} className="teaching-panel"><summary>{s.student_name} · {new Date(s.submitted_at).toLocaleString()}{s.is_late ? " · Late" : ""}</summary><p className="teaching-instructions">{s.answer}</p>{s.link_url && <a href={s.link_url} target="_blank" rel="noopener noreferrer">Open submitted document (new tab)</a>}</details>)}
    </section>
    {roster.data && saved.data && (!roster.data.length ? <Empty>No students enrolled.</Empty> : <WorkspaceForm onSubmit={submit}><fieldset disabled={subject.academic_year_status === 'CLOSED' || !draft.ready || draft.blocked} className="workspace-form-fields">
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Student</th><th>Score</th><th>Feedback</th></tr></thead><tbody>{roster.data.map(s => <tr key={s.id}>
        <td>{studentName(s)}<div className="teaching-muted">{s.admission_number}</div></td>
        <td>{work.assessment_mode === 'COMPETENCY' ? <select aria-label={`Outcome for ${studentName(s)}`} value={value(s.id, 'competency_label')} disabled={mutation.isPending} onChange={e => change(s.id, 'competency_label', e.target.value)}><option value="">Not observed</option>{work.rubric_labels.map(label => <option key={label} value={label}>{label}</option>)}</select> : <input aria-label={`Score for ${studentName(s)}`} type="number" min="0" max={work.max_score} step="0.01" required={Boolean(records[s.id])} value={value(s.id, "score")} disabled={mutation.isPending} onChange={e => change(s.id, "score", e.target.value)} />}</td>
        <td><input aria-label={`Feedback for ${studentName(s)}`} maxLength={5000} value={value(s.id, "feedback")} disabled={mutation.isPending} onChange={e => change(s.id, "feedback", e.target.value)} /></td>
      </tr>)}</tbody></table></div>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending || !roster.data.some(s => value(s.id, outcomeField) !== "")}>{mutation.isPending ? "Saving…" : "Save scores"}</button></div>
    </fieldset></WorkspaceForm>)}
  </section>;
}
