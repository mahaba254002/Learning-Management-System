import { useState } from "react";
import { Link } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";

export default function InstitutionClassesPage() {
  const configuration = useTeachingQuery("/api/institution/learning-settings");
  const labels = configuration.data || { student_label: "Student", teacher_label: "Teacher", class_label: "Class", subject_label: "Subject", period_label: "Academic year" };
  const classesLabel = `${labels.class_label}${labels.class_label.endsWith("s") ? "es" : "s"}`;
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const teachers = useTeachingQuery("/api/institution/teachers");
  const structure = useTeachingQuery('/api/institution/academic-structure');
  const calendar = useTeachingQuery('/api/institution/academic-years');
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
      await mutation.mutateAsync({ path: editingClass ? `/api/teaching/classes/${editingClass.id}` : "/api/teaching/classes", method: editingClass ? "PUT" : "POST", body: { ...values, supervisor_id: values.supervisor_id || null, programme_id: values.programme_id || null, level_id: values.level_id || null } });
      setEditingClass(null); form.reset();
    } catch { /* Error shown below. */ }
  }
  async function saveSubject(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const { class_id, ...body } = Object.fromEntries(new FormData(form));
    try {
      await mutation.mutateAsync({ path: editingSubject ? `/api/teaching/subjects/${editingSubject.id}` : `/api/teaching/classes/${class_id}/subjects`, method: editingSubject ? "PUT" : "POST", body: {...body, catalogue_id: body.catalogue_id || null, period_id: body.period_id || null, registration_mode: body.registration_mode || null} });
      setEditingSubject(null); form.reset();
    } catch { /* Error shown below. */ }
  }
  return <><PageHeading title={`${classesLabel} & teaching`}>Set up learning groups, appoint supervisors, and assign teaching responsibilities. Open a group to manage enrollment.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} /><QueryState query={teachers} /><MutationState mutation={mutation} />
    <div className="teaching-grid"><section className="teaching-panel"><h2>{editingClass ? `Edit ${labels.class_label.toLowerCase()}` : `Create ${labels.class_label.toLowerCase()}`}</h2>
      <form key={editingClass?.id || "new-class"} className="teaching-form" onSubmit={saveClass}>
        <Field label={`${labels.class_label} name`} name="name" required maxLength={100} defaultValue={editingClass?.name || ""} />
        <Field label="Academic year" name="academic_year" required defaultValue={editingClass?.academic_year || ""}><option value="">Choose a configured year</option>{calendar.data?.years.filter(y => y.status !== 'CLOSED' || y.name === editingClass?.academic_year).map(y => <option key={y.id} value={y.name}>{y.name} · {y.status.toLowerCase()}</option>)}{calendar.data?.unconfigured_years.map(name => <option key={name} value={name}>{name} · calendar not configured</option>)}</Field>
        <Field label="Programme (optional)" name="programme_id" defaultValue={editingClass?.programme_id || ""}><option value="">School / institution-wide</option>{structure.data?.programmes.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Field>
        <Field label="Study level (optional)" name="level_id" defaultValue={editingClass?.level_id || ""}><option value="">No level</option>{structure.data?.levels.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}</Field>
        <Link to="/institution/academic-years">Set up academic years and terms</Link>
        <Field label={`${labels.class_label} supervisor`} name="supervisor_id" defaultValue={editingClass?.supervisor_id || ""}><option value="">Unassigned</option>{teacherOptions}</Field>
        <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save class</button>{editingClass && <button type="button" onClick={() => setEditingClass(null)}>Cancel</button>}</div>
      </form></section>
      <section className="teaching-panel"><h2>{editingSubject ? "Edit teaching assignment" : `Assign a ${labels.subject_label.toLowerCase()}`}</h2>
        <form key={editingSubject?.id || "new-subject"} className="teaching-form" onSubmit={saveSubject}>
          <Field label={labels.class_label} name="class_id" required defaultValue={editingSubject?.class_id || ""} disabled={Boolean(editingSubject)}><option value="">Choose a {labels.class_label.toLowerCase()}</option>{classes.data?.map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>
          <Field label="Catalogue record (optional)" name="catalogue_id" defaultValue={editingSubject?.catalogue_id || ""}><option value="">Standalone offering</option>{structure.data?.catalogue.map(p => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}</Field>
          <Field label="Term / semester (optional)" name="period_id" defaultValue={editingSubject?.period_id || ""}><option value="">Whole academic year</option>{calendar.data?.years.flatMap(y => y.periods.map(p => <option key={p.id} value={p.id}>{y.name} · {p.name}</option>))}</Field>
          <Field label="Registration method" name="registration_mode" defaultValue={editingSubject?.registration_mode || ""}><option value="">Institution default (new offering)</option><option value="COHORT">Whole group / cohort</option><option value="INDIVIDUAL">Individual course registration</option></Field>
          <Field label={`${labels.subject_label} name`} name="name" required maxLength={100} defaultValue={editingSubject?.name || ""} />
          <Field label={labels.teacher_label} name="teacher_id" required defaultValue={editingSubject?.teacher_id || ""}><option value="">Choose a {labels.teacher_label.toLowerCase()}</option>{teacherOptions}</Field>
          <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save teaching assignment</button>{editingSubject && <button type="button" onClick={() => setEditingSubject(null)}>Cancel</button>}</div>
        </form>
      </section></div>
    {classes.data?.length === 0 && <Empty>No classes yet. Create a class above to begin.</Empty>}
    {classes.data?.map(c => <section className="teaching-panel" key={c.id}><h2>{c.name} · {c.academic_year}</h2><p className="teaching-muted">Supervisor: {teacherName(c.supervisor_id)}{c.academic_year_status === "CLOSED" ? " · Closed year, read-only history" : ""}</p>
      <div className="teaching-actions"><Link to={`/institution/classes/${c.id}`}>Manage students</Link><button type="button" disabled={c.academic_year_status === "CLOSED"} onClick={() => setEditingClass(c)}>Edit class</button></div>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>{labels.subject_label}</th><th>{labels.teacher_label}</th><th>Action</th></tr></thead><tbody>{subjects.data?.filter(s => s.class_id === c.id).map(s => <tr key={s.id}><td>{s.name}</td><td>{teacherName(s.teacher_id)}</td><td><button type="button" disabled={c.academic_year_status === "CLOSED"} onClick={() => setEditingSubject(s)}>Edit assignment</button></td></tr>)}</tbody></table></div>
    </section>)}
  </>;
}
