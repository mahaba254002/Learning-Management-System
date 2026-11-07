import { useState } from "react";
import { Link } from "react-router-dom";
import PasswordInput from "../../components/common/PasswordInput";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState } from "../teacher/TeachingUI";

/** The platform admin's own secret question, asked before terminating, deleting, exporting or restoring. */
export function SecretAnswer({ value, onChange, name = "answer" }) {
  const query = useTeachingQuery("/api/platform/secret");
  if (query.data && !query.data.set) return <p className="teaching-notice">Set your secret question in <Link to="/platform/settings">Settings</Link> first. It is asked before this action.</p>;
  const props = value === undefined ? {} : { value, onChange: e => onChange(e.target.value) };
  return <Field label={query.data ? `Secret question: ${query.data.question}` : "Secret question"} name={name} type="password" required autoComplete="off" maxLength={200} {...props}
    description="Five wrong answers lock these actions for 30 minutes." />;
}

export function PlatformSecretSettings() {
  const query = useTeachingQuery("/api/platform/secret");
  const mutation = useTeachingMutation();
  const [open, setOpen] = useState(false);
  async function save(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try { await mutation.mutateAsync({ path: "/api/platform/secret", method: "PUT", body: values }); form.reset(); setOpen(false); } catch { /* shown below */ }
  }
  return <section className="teaching-panel" aria-labelledby="secret-question"><h2 id="secret-question">Secret question</h2>
    <p>Asked before you terminate or permanently delete an institution, export or back up data, or restore a backup. Only a scrambled copy of the answer is kept; capital letters and extra spaces don't matter.</p>
    {query.data?.set && !open && <p className="teaching-muted">Your question: {query.data.question}</p>}
    {open || (query.data && !query.data.set) ? <form className="teaching-form" onSubmit={save}>
      <Field label="Question" name="question" required minLength={5} maxLength={200} placeholder="e.g. The first school I taught at" />
      <Field label="Answer" name="answer" type="password" required minLength={3} maxLength={200} autoComplete="off" />
      <div className="form-field"><label htmlFor="secret-password">Your current password</label><PasswordInput id="secret-password" name="password" required autoComplete="current-password" /></div>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save secret question</button>{query.data?.set && <button type="button" onClick={() => setOpen(false)}>Cancel</button>}</div>
    </form> : <div className="teaching-actions"><button type="button" className="btn" onClick={() => setOpen(true)}>Change secret question</button></div>}
    <MutationState mutation={mutation} message="Secret question saved." />
  </section>;
}
