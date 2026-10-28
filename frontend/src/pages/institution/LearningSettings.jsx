import { useState } from "react";
import WorkspaceForm from "../../components/common/WorkspaceForm";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState, QueryState } from "../teacher/TeachingUI";

export default function LearningSettings() {
  const query = useTeachingQuery("/api/institution/learning-settings");
  const config = useTeachingQuery('/api/institution/academic-configuration');
  const managed = config.data?.managed && !config.data.institution_policy_edits;
  return <section className="teaching-panel"><h2>Learning configuration</h2><QueryState query={query} />{managed && <p>This institution’s academic policy is managed by platform admin. Request changes to terminology, registration rules or grading policy through your platform contact.</p>}{query.data && <fieldset className="workspace-form-fields" disabled={managed}><SettingsForm initial={query.data} /></fieldset>}</section>;
}

function SettingsForm({ initial }) {
  const mutation = useTeachingMutation();
  const [bands, setBands] = useState(initial.grade_bands.map(b => `${b.minimum}: ${b.label}`).join("\n"));
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const grade_bands = bands.trim() ? bands.trim().split("\n").map(line => {
      const colon = line.indexOf(":");
      return { minimum: colon < 0 ? NaN : Number(line.slice(0, colon).trim()), label: line.slice(colon + 1).trim() };
    }) : [];
    if (grade_bands.some(b => !Number.isFinite(b.minimum) || !b.label)) { setError("Use one minimum percentage: grade label per line."); return; }
    setError("");
    try { await mutation.mutateAsync({ path: "/api/institution/learning-settings", method: "PUT", body: { ...values, grade_bands } }); } catch { /* Shown below. */ }
  }
  return <WorkspaceForm className="teaching-form" onSubmit={submit}>
    {[['student_label', 'Learner label'], ['teacher_label', 'Educator label'], ['class_label', 'Class / cohort label'], ['subject_label', 'Subject / course label'], ['period_label', 'Academic period label']].map(([key, label]) => <Field key={key} label={label} name={key} defaultValue={initial[key]} required maxLength={30} />)}
    <Field label="Default new student login" name="default_student_login" defaultValue={initial.default_student_login}><option value="EMAIL">Email and password</option><option value="STUDENT_ID">Student ID and password</option></Field>
    <label htmlFor="grade-bands">Grading bands (optional)</label><textarea id="grade-bands" value={bands} onChange={e => setBands(e.target.value)} rows={6} maxLength={2000} aria-describedby="grade-help" />
    <p id="grade-help">Use one minimum percentage: grade label per line. Include a band starting at 0. Leave blank to report numeric marks only. Use your institution’s approved grading policy.</p>
    {error && <p role="alert" className="form-error">{error}</p>}<MutationState mutation={mutation} message="Learning configuration saved." />
    <button className="btn btn--primary" disabled={mutation.isPending}>Save learning configuration</button>
  </WorkspaceForm>;
}
