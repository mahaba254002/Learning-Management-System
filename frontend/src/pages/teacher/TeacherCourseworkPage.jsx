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

function inputDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function SubjectCoursework({ subject }) {
  const { pathname } = useLocation();
  const portal = pathname.startsWith('/institution') ? 'institution' : 'teacher';
  const query = useTeachingQuery(`/api/teaching/subjects/${subject.id}/coursework`);
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    const body = { ...data, max_score: data.max_score, published: data.published === "on", allow_late_submissions: data.allow_late_submissions === "on", due_at: data.due_at ? new Date(data.due_at).toISOString() : null };
    try {
      await mutation.mutateAsync({ path: editing ? `/api/teaching/coursework/${editing.id}` : `/api/teaching/subjects/${subject.id}/coursework`, method: editing ? "PUT" : "POST", body });
      setEditing(null);
      form.reset();
    } catch { /* Error shown below. */ }
  }
  return <><QueryState query={query} /><MutationState mutation={mutation} message="Coursework saved." />
    <section className="teaching-panel"><h2>{editing ? "Edit assessment" : "New assessment"}</h2>
      <form key={editing?.id || "new"} className="teaching-form" onSubmit={submit}>
        <Field label="Title" name="title" required maxLength={200} defaultValue={editing?.title || ""} />
        <Field label="Type" name="kind" defaultValue={editing?.kind || "ASSIGNMENT"}><option value="ASSIGNMENT">Assignment</option><option value="COURSEWORK">Coursework</option><option value="EXAM">Examination</option></Field>
        <div className="form-field"><label htmlFor="coursework-instructions">Instructions</label><textarea id="coursework-instructions" name="instructions" required maxLength={20000} defaultValue={editing?.instructions || ""} /></div>
        <Field label="Due date and time (optional, your local time)" name="due_at" type="datetime-local" defaultValue={inputDate(editing?.due_at)} />
        <Field label="Maximum score" name="max_score" type="number" min="0.01" max="10000" step="0.01" required defaultValue={editing?.max_score || 100} />
        <label className="teaching-checkbox"><input type="checkbox" name="published" defaultChecked={editing?.published || false} />Publish to students in this class</label>
        <label className="teaching-checkbox"><input type="checkbox" name="allow_late_submissions" defaultChecked={editing?.allow_late_submissions ?? true} />Accept late submissions (marked late)</label>
        <p className="teaching-muted">Drafts are visible to staff only. Published assessments and saved scores appear in enrolled students’ coursework.</p>
        <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>{mutation.isPending ? "Saving…" : "Save assessment"}</button>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel edit</button>}</div>
      </form>
    </section>
    <section><h2 className="section-header">Assessments for {subject.name}</h2>{query.data?.length === 0 && <Empty>No assessments yet.</Empty>}
      {query.data?.map(w => <article className="teaching-panel" key={w.id}><div className="section-header"><h3>{w.title}</h3><span className={`status-badge status-badge--${w.published ? "active" : "archived"}`}>{w.published ? "Published" : "Draft"}</span></div>
        <p className="teaching-muted">{w.kind.toLowerCase()} · Out of {w.max_score} · {w.due_at ? `Due ${new Date(w.due_at).toLocaleString()}` : "No due date"}</p>
        <p className="teaching-instructions">{w.instructions}</p>
        <div className="teaching-actions"><button type="button" onClick={() => { setEditing(w); mutation.reset(); }}>Edit assessment</button><Link to={`/${portal}/scores?subject=${subject.id}&assessment=${w.id}`}>View / enter scores</Link></div>
      </article>)}
    </section>
  </>;
}
