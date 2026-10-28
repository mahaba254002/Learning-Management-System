import { useAuth } from "../../context/useAuth";
import AssessmentEditor from "./AssessmentEditor";
import { useState } from "react";
import { Link, useSearchParams, useLocation } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";

export default function TeacherCourseworkPage() {
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const [params, setParams] = useSearchParams();
  const subject = subjects.data?.find(s => s.id === params.get("subject"));
  return <><PageHeading title="Coursework">Create assignments, coursework, and examinations for your teaching subjects.</PageHeading><QueryState query={subjects} />
    <Field label="Teaching subject" value={subject?.id || ""} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">Choose a subject</option>{subjects.data?.map(s => <option key={s.id} value={s.id}>{s.class_name} · {s.academic_year} — {s.name}</option>)}</Field>
    {subjects.data?.length === 0 && <Empty>Your administrator has not assigned any subjects yet.</Empty>}
    {subject && <SubjectCoursework key={subject.id} subject={subject} />}
  </>;
}

function SubjectCoursework({ subject }) {
  const { readOnly } = useAuth();
  const { pathname } = useLocation();
  const portal = pathname.startsWith('/institution') ? 'institution' : 'teacher';
  const query = useTeachingQuery(`/api/teaching/subjects/${subject.id}/coursework`);
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const body = { ...data, period_id: data.period_id || null, max_score: data.max_score, published: data.published === "on", allow_late_submissions: data.allow_late_submissions === "on", due_at: data.due_at ? new Date(data.due_at).toISOString() : null };
    try {
      await mutation.mutateAsync({ path: editing ? `/api/teaching/coursework/${editing.id}` : `/api/teaching/subjects/${subject.id}/coursework`, method: editing ? "PUT" : "POST", body });
      setEditing(null);
      form.reset();
      return true;
    } catch { return false; /* Error shown below. */ }
  }
  return <><QueryState query={query} /><MutationState mutation={mutation} message="Coursework saved." />
    {mutation.error?.status === 409 && <button type="button" onClick={async () => { const result = await query.refetch(); if (editing && result.data) setEditing(result.data.find(w => w.id === editing.id) || null); }}>Reload latest assessment for review</button>}
    <section className="teaching-panel">{subject.academic_year_status === "CLOSED" && <p className="teaching-notice">This academic year is closed. Assessments are read-only.</p>}<h2>{editing ? "Edit assessment" : "New assessment"}</h2>
      <AssessmentEditor key={editing?.id || "new"} subject={subject} editing={editing} pending={mutation.isPending} save={submit} cancel={() => setEditing(null)} />
    </section>
    <section><h2 className="section-header">Assessments for {subject.name}</h2>{query.data?.length === 0 && <Empty>No assessments yet.</Empty>}
      {query.data?.map(w => <article className="teaching-panel" key={w.id}><div className="section-header"><h3>{w.title}</h3><span className={`status-badge status-badge--${w.published ? "active" : "archived"}`}>{w.published ? "Published" : "Draft"}</span></div>
        <p className="teaching-muted">{w.kind.toLowerCase()} · {w.assessment_mode === "COMPETENCY" ? "Competency observation" : `Out of ${w.max_score}`} · {w.due_at ? `Due ${new Date(w.due_at).toLocaleString()}` : "No due date"}</p>
        <p className="teaching-instructions">{w.instructions}</p>
        <div className="teaching-actions"><button type="button" disabled={readOnly || subject.academic_year_status === "CLOSED"} onClick={() => { setEditing(w); mutation.reset(); }}>Edit assessment</button><Link to={`/${portal}/scores?subject=${subject.id}&assessment=${w.id}`}>View / enter scores</Link></div>
      </article>)}
    </section>
  </>;
}
