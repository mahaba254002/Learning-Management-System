import { useState } from "react";
import { Link } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";

export default function InstitutionClassesPage() {
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const teachers = useTeachingQuery("/api/institution/teachers");
  const mutation = useTeachingMutation();
  const [editingClass, setEditingClass] = useState(null);
  const [editingSubject, setEditingSubject] = useState(null);
  const teacherOptions = teachers.data?.filter(t => t.status === "ACTIVE").map(t => <option key={t.user_id} value={t.user_id}>{t.first_name} {t.last_name}</option>);
  const teacherName = id => {
    const t = teachers.data?.find(t => t.user_id === id);
    return t ? `${t.first_name} ${t.last_name}` : "Unassigned";
  };
  async function saveClass(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
      await mutation.mutateAsync({ path: editingClass ? `/api/teaching/classes/${editingClass.id}` : "/api/teaching/classes", method: editingClass ? "PUT" : "POST", body: { ...values, supervisor_id: values.supervisor_id || null } });
      setEditingClass(null); form.reset();
    } catch { /* Error shown below. */ }
  }
  async function saveSubject(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const { class_id, ...body } = Object.fromEntries(new FormData(form));
    try {
      await mutation.mutateAsync({ path: editingSubject ? `/api/teaching/subjects/${editingSubject.id}` : `/api/teaching/classes/${class_id}/subjects`, method: editingSubject ? "PUT" : "POST", body });
      setEditingSubject(null); form.reset();
    } catch { /* Error shown below. */ }
  }
  return <><PageHeading title="Classes & teaching">Set up classes, appoint supervisors, and assign teaching subjects. Open a class to manage its students.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} /><QueryState query={teachers} /><MutationState mutation={mutation} />
    <div className="teaching-grid"><section className="teaching-panel"><h2>{editingClass ? "Edit class" : "Create class"}</h2>
      <form key={editingClass?.id || "new-class"} className="teaching-form" onSubmit={saveClass}>
        <Field label="Class name" name="name" required maxLength={100} defaultValue={editingClass?.name || ""} />
        <Field label="Academic year / session" name="academic_year" required maxLength={30} placeholder="e.g. 2026/2027" defaultValue={editingClass?.academic_year || ""} />
        <Field label="Class teacher / supervisor" name="supervisor_id" defaultValue={editingClass?.supervisor_id || ""}><option value="">Unassigned</option>{teacherOptions}</Field>
        <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save class</button>{editingClass && <button type="button" onClick={() => setEditingClass(null)}>Cancel</button>}</div>
      </form></section>
      <section className="teaching-panel"><h2>{editingSubject ? "Edit teaching assignment" : "Assign a subject"}</h2>
        <form key={editingSubject?.id || "new-subject"} className="teaching-form" onSubmit={saveSubject}>
          <Field label="Class" name="class_id" required defaultValue={editingSubject?.class_id || ""} disabled={Boolean(editingSubject)}><option value="">Choose a class</option>{classes.data?.map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>
          <Field label="Subject / course name" name="name" required maxLength={100} defaultValue={editingSubject?.name || ""} />
          <Field label="Subject teacher" name="teacher_id" required defaultValue={editingSubject?.teacher_id || ""}><option value="">Choose a teacher</option>{teacherOptions}</Field>
          <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save teaching assignment</button>{editingSubject && <button type="button" onClick={() => setEditingSubject(null)}>Cancel</button>}</div>
        </form>
      </section></div>
    {classes.data?.length === 0 && <Empty>No classes yet. Create a class above to begin.</Empty>}
    {classes.data?.map(c => <section className="teaching-panel" key={c.id}><h2>{c.name} · {c.academic_year}</h2><p className="teaching-muted">Supervisor: {teacherName(c.supervisor_id)}</p>
      <div className="teaching-actions"><Link to={`/institution/classes/${c.id}`}>Manage students</Link><button type="button" onClick={() => setEditingClass(c)}>Edit class</button></div>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Subject</th><th>Teacher</th><th>Action</th></tr></thead><tbody>{subjects.data?.filter(s => s.class_id === c.id).map(s => <tr key={s.id}><td>{s.name}</td><td>{teacherName(s.teacher_id)}</td><td><button type="button" onClick={() => setEditingSubject(s)}>Edit assignment</button></td></tr>)}</tbody></table></div>
    </section>)}
  </>;
}
