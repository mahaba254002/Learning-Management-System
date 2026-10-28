import { useState } from "react";
import WorkspaceForm from "../../components/common/WorkspaceForm";
import { useTeachingMutation } from "../teacher/teachingQueries";
import { Field, MutationState } from "../teacher/TeachingUI";

export default function StudentAccessEditor({ student, onClose }) {
  const [method, setMethod] = useState(student.login_method || "EMAIL");
  const [credentials, setCredentials] = useState(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const mutation = useTeachingMutation();
  const root = `/api/institution/students/${student.user_id}`;
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try { await mutation.mutateAsync({ path: `${root}/login`, method: "PUT", body: { ...values, email: values.email || null, login_id: values.login_id || null, login_method: method } }); } catch { /* Shown below. */ }
  }
  return <section className="teaching-panel" aria-label="Manage student sign-in"><h2>Sign-in access · {student.first_name} {student.last_name}</h2><p>Changing sign-in details revokes existing sessions. Admission and academic records stay attached to this student.</p>
    <MutationState mutation={mutation} message="Student access updated." />
    <WorkspaceForm className="teaching-form" onSubmit={save}>
      <Field label="Sign-in method" value={method} onChange={e => setMethod(e.target.value)}><option value="EMAIL">Email and password</option><option value="STUDENT_ID">Student ID and password</option></Field>
      <Field label={method === "EMAIL" ? "Email" : "Email (optional)"} name="email" type="email" required={method === "EMAIL"} maxLength={255} defaultValue={student.email || ""} />
      {method === "STUDENT_ID" && <Field label="Platform-wide unique student ID" name="login_id" required maxLength={60} defaultValue={student.login_id || ""} />}
      <button className="btn btn--primary" disabled={mutation.isPending}>Save sign-in method</button>
    </WorkspaceForm>
    {!confirmReset ? <button type="button" onClick={() => setConfirmReset(true)}>Reset student password…</button> : <><p>This revokes sessions and requires a password change at the next login. Share the new password securely.</p><button type="button" disabled={mutation.isPending} onClick={async () => {
      try { const result = await mutation.mutateAsync({ path: `${root}/reset-password` }); setCredentials(result); setConfirmReset(false); } catch { /* Shown above. */ }
    }}>Confirm password reset</button></>}
    {credentials && <div role="status"><p>{credentials.login_method === "EMAIL" ? "Email" : "Student ID"}: {credentials.login_identity}</p><p>Temporary password: <strong>{credentials.temporary_password}</strong></p></div>}
    <button type="button" onClick={() => { setCredentials(null); mutation.reset(); onClose(); }}>Close and dismiss credentials</button>
  </section>;
}
