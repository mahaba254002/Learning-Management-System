import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";

export default function TeacherMaterialsPage() {
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const [params, setParams] = useSearchParams();
  const subject = subjects.data?.find(s => s.id === params.get("subject"));
  return <><PageHeading title="Course materials">Post lesson notes, reading resources, and document links for the subjects you teach.</PageHeading><QueryState query={subjects} />
    <Field label="Teaching subject" value={subject?.id || ""} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">Choose a subject</option>{subjects.data?.map(s => <option key={s.id} value={s.id}>{s.class_name} · {s.academic_year} — {s.name}</option>)}</Field>
    {subjects.data?.length === 0 && <Empty>No teaching subjects assigned.</Empty>}{subject && <Materials key={subject.id} subject={subject} />}
  </>;
}

function Materials({ subject }) {
  const query = useTeachingQuery(`/api/teaching/subjects/${subject.id}/materials`);
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  const [validationError, setValidationError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setValidationError("");
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const body = { ...values, body: values.body.trim(), link_url: values.link_url.trim() || null, published: values.published === "on" };
    if (!body.body && !body.link_url) { setValidationError("Add lesson content or a resource link."); return; }
    try {
      await mutation.mutateAsync({ path: editing ? `/api/teaching/materials/${editing.id}` : `/api/teaching/subjects/${subject.id}/materials`, method: editing ? "PUT" : "POST", body });
      setEditing(null); form.reset();
    } catch { /* Error shown below. */ }
  }
  return <><QueryState query={query} /><MutationState mutation={mutation} message="Material saved." />{validationError && <p role="alert" className="form-error">{validationError}</p>}
    <section className="teaching-panel"><h2>{editing ? "Edit material" : "New learning material"}</h2><form key={editing?.id || "new"} className="teaching-form" onSubmit={submit}>
      <Field label="Title" name="title" required maxLength={200} defaultValue={editing?.title || ""} />
      <div className="form-field"><label htmlFor="material-body">Lesson notes / description</label><textarea id="material-body" name="body" maxLength={50000} defaultValue={editing?.body || ""} /></div>
      <Field label="Resource link (optional)" name="link_url" type="url" maxLength={2000} defaultValue={editing?.link_url || ""} />
      <label className="teaching-checkbox"><input type="checkbox" name="published" defaultChecked={editing?.published || false} />Publish to enrolled students</label>
      <p className="teaching-muted">For document links, ensure your students have permission to open the resource.</p>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save material</button>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel</button>}</div>
    </form></section>
    {query.data?.length === 0 && <Empty>No materials posted yet.</Empty>}{query.data?.map(m => <article className="teaching-panel" key={m.id}><div className="section-header"><h2>{m.title}</h2><span className={`status-badge status-badge--${m.published ? "active" : "archived"}`}>{m.published ? "Published" : "Draft"}</span></div><p className="teaching-instructions">{m.body}</p>{m.link_url && <a href={m.link_url} target="_blank" rel="noopener noreferrer">Open resource (new tab)</a>}<div className="teaching-actions"><button type="button" onClick={() => { setEditing(m); mutation.reset(); }}>Edit / change visibility</button></div></article>)}
  </>;
}
