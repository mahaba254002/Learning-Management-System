import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "./teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "./TeachingUI";
import { studentName } from "./teachingFormat";

export default function ClassStudentsPage() {
  const { classId } = useParams();
  return <ClassRoster key={classId} classId={classId} />;
}

function ClassRoster({ classId }) {
  const classes = useTeachingQuery("/api/teaching/classes");
  const roster = useTeachingQuery(`/api/teaching/classes/${classId}/students`);
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [credentials, setCredentials] = useState(null);
  const current = classes.data?.find(c => c.id === classId);
  const root = `/api/teaching/classes/${classId}`;

  async function submitStudent(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
      const result = await mutation.mutateAsync({ path: editing ? `${root}/students/${editing.id}` : `${root}/students`, method: editing ? "PUT" : "POST", body: values });
      if (result.temporary_password) setCredentials(result);
      setEditing(null);
      form.reset();
    } catch { /* MutationState shows the error. */ }
  }

  async function enroll(event) {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await mutation.mutateAsync({ path: `${root}/enrollments`, body: Object.fromEntries(new FormData(form)) });
      form.reset();
    } catch { /* MutationState shows the error. */ }
  }

  return <><PageHeading title={current ? `${current.name} — students` : "Class students"}>{current?.academic_year}</PageHeading>
    <QueryState query={classes} /><QueryState query={roster} /><MutationState mutation={mutation} />
    {credentials && <section className="teaching-panel" aria-label="New student sign-in details">
      <h2>Student account created</h2><p>Share these sign-in details securely with the student. They must change the temporary password at first sign-in.</p>
      <dl className="teaching-profile"><dt>Username</dt><dd>{credentials.username}</dd><dt>Temporary password</dt><dd>{credentials.temporary_password}</dd></dl>
      <button type="button" onClick={() => { setCredentials(null); mutation.reset(); }}>Dismiss sign-in details</button>
    </section>}
    {roster.data && <section className="teaching-panel"><h2>Class roster · {roster.data.length}</h2>
      {!roster.data.length ? <Empty>No students enrolled yet.</Empty> : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Admission no.</th><th>Name</th><th>Email</th><th>Phone</th>{current?.can_manage && <th>Actions</th>}</tr></thead>
        <tbody>{roster.data.map(s => <tr key={s.id}><td>{s.admission_number}</td><td>{studentName(s)}</td><td>{s.email}</td><td>{s.phone || "—"}</td>{current?.can_manage && <td>
          <div className="teaching-actions"><button type="button" onClick={() => { setEditing(s); mutation.reset(); }}>Edit</button><button type="button" onClick={() => setRemoving(s)}>Remove from class</button></div>
        </td>}</tr>)}</tbody></table></div>}
    </section>}
    {removing && <section className="teaching-panel" aria-label="Confirm enrollment removal"><h2>Remove {studentName(removing)} from this class?</h2>
      <p>Their account, attendance and scores will be preserved. You can enroll them again using their admission number.</p>
      <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={async () => {
        try { await mutation.mutateAsync({ path: `${root}/enrollments/${removing.id}`, method: "DELETE" }); setRemoving(null); } catch { /* Error above. */ }
      }}>Confirm removal</button><button type="button" onClick={() => setRemoving(null)}>Cancel</button></div></section>}
    {current?.can_manage && <div className="teaching-grid">
      <section className="teaching-panel"><h2>{editing ? `Edit ${studentName(editing)}` : "Add a new student"}</h2>
        <form key={editing?.id || "new"} className="teaching-form" onSubmit={submitStudent}>
          <Field label="First name" name="first_name" required maxLength={100} defaultValue={editing?.first_name || ""} />
          <Field label="Last name" name="last_name" required maxLength={100} defaultValue={editing?.last_name || ""} />
          {!editing && <><Field label="Admission number" name="admission_number" required maxLength={60} /><Field label="Student email" name="email" type="email" required maxLength={255} /></>}
          <Field label="Phone (optional)" name="phone" type="tel" maxLength={50} defaultValue={editing?.phone || ""} />
          {editing && <p className="teaching-muted">Account email and admission number are managed by the institution administrator.</p>}
          <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>{mutation.isPending ? "Saving…" : editing ? "Save student" : "Create and enroll student"}</button>
            {editing && <button type="button" onClick={() => setEditing(null)}>Cancel edit</button>}</div>
        </form>
      </section>
      <section className="teaching-panel"><h2>Enroll an existing student</h2><p className="teaching-muted">Use the student’s exact admission number from your institution.</p>
        <form className="teaching-form" onSubmit={enroll}><Field label="Admission number" name="admission_number" required maxLength={60} /><button className="btn btn--primary" disabled={mutation.isPending}>Enroll student</button></form>
      </section>
    </div>}
  </>;
}
