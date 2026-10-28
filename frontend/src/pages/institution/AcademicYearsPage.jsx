import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { apiRequest } from '../../api/client';
import { useAuth } from '../../context/useAuth';

export default function AcademicYearsPage() {
  const query = useTeachingQuery('/api/institution/academic-years');
  const [chosen, setChosen] = useState('');
  const mutation = useTeachingMutation();
  async function create(event) {
    event.preventDefault(); const form = event.currentTarget;
    try { await mutation.mutateAsync({ path: '/api/institution/academic-years', body: Object.fromEntries(new FormData(form)) }); form.reset(); }
    catch { /* shown below */ }
  }
  const year = query.data?.years.find(y => y.id === chosen);
  return <><PageHeading title="Academic years">Plan terms or semesters, review results, close the year and promote classes while retaining academic history.</PageHeading>
    <QueryState query={query} /><MutationState mutation={mutation} message="Academic year created." />
    {query.data?.unconfigured_years.length > 0 && <p className="teaching-notice">Existing class years need calendar dates: {query.data.unconfigured_years.join(', ')}. Create each year below using exactly its existing name; dates are not guessed.</p>}
    <section className="teaching-panel"><h2>Create an academic year</h2><WorkspaceForm className="teaching-form" onSubmit={create}>
      <Field label="Year name" name="name" required maxLength={30} placeholder="e.g. 2026 or 2026/2027" /><Field label="Start date" name="start_date" type="date" required /><Field label="End date" name="end_date" type="date" required />
      <button className="btn btn--primary" disabled={mutation.isPending}>Create planned year</button></WorkspaceForm></section>
    <Field label="Manage academic year" value={chosen} onChange={e => setChosen(e.target.value)}><option value="">Choose a year</option>{query.data?.years.map(y => <option key={y.id} value={y.id}>{y.name} · {y.status.toLowerCase()}</option>)}</Field>
    {year && <YearManager key={year.id} year={year} years={query.data.years} />}
  </>;
}

function YearManager({ year, years }) {
  const { readOnly } = useAuth();
  const mutation = useTeachingMutation();
  const [confirmation, setConfirmation] = useState('');
  const [target, setTarget] = useState('');
  const [mappings, setMappings] = useState({});
  const [plan, setPlan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const classes = useTeachingQuery('/api/teaching/classes');
  const sourceClasses = classes.data?.filter(c => c.academic_year === year.name) || [];
  const destinationYear = years.find(y => y.id === target);
  const targets = classes.data?.filter(c => c.academic_year === destinationYear?.name) || [];
  async function addPeriod(event) {
    event.preventDefault(); const form = event.currentTarget;
    try { await mutation.mutateAsync({ path: `/api/institution/academic-years/${year.id}/periods`, body: Object.fromEntries(new FormData(form)) }); form.reset(); }
    catch { /* shown below */ }
  }
  async function transition(event) {
    event.preventDefault();
    try { await mutation.mutateAsync({ path: `/api/institution/academic-years/${year.id}/transition`, body: { status: year.status === 'PLANNED' ? 'ACTIVE' : 'CLOSED', confirmation } }); setConfirmation(''); }
    catch { /* shown below */ }
  }
  const promotionBody = () => ({ target_year_id: target, mappings: sourceClasses.map(c => ({ source_class_id: c.id, target_class_id: mappings[c.id] === 'completed' ? null : mappings[c.id] })) });
  async function preview(event) {
    event.preventDefault(); setBusy(true); setError(''); setPlan(null);
    try { setPlan(await apiRequest(`/api/institution/academic-years/${year.id}/promotion/preview`, { method: 'POST', body: promotionBody() })); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function promote() {
    setBusy(true); setError('');
    try { await mutation.mutateAsync({ path: `/api/institution/academic-years/${year.id}/promotion/commit`, body: { ...promotionBody(), preview_token: plan.preview_token } }); setPlan(null); }
    catch { setPlan(null); }
    finally { setBusy(false); }
  }
  const action = year.status === 'PLANNED' ? 'ACTIVE' : 'CLOSED';
  return <><MutationState mutation={mutation} message="Academic workflow saved." /><QueryState query={classes} />{error && <p role="alert" className="form-error">{error}</p>}
    <section className="teaching-panel"><h2>{year.name} · {year.status.toLowerCase()}</h2><p>{year.start_date} to {year.end_date}</p>
      <div className="table-wrapper"><table className="data-table"><caption>Year review</caption><thead><tr><th>Classes</th><th>Enrollments</th><th>Assessments</th><th>Unreleased results</th><th>Unassigned classes</th></tr></thead><tbody><tr><td>{year.readiness.classes}</td><td>{year.readiness.students}</td><td>{year.readiness.assessments}</td><td>{year.readiness.unreleased_results}</td><td>{year.readiness.unassigned_classes}</td></tr></tbody></table></div>
      <p>Unpublished assessments: {year.readiness.unpublished_assessments}. Recorded scores: {year.readiness.scores}. Missing marks for published assessments: {year.readiness.missing_scores}. Review class reports before closure.</p><Link to="/institution/classes">Open classes and reports</Link>
      <h3>Terms / semesters</h3>{year.periods.length === 0 ? <p>No periods configured.</p> : <ul>{year.periods.map(p => <li key={p.id}>{p.name}: {p.start_date} to {p.end_date}</li>)}</ul>}
      {year.status !== 'CLOSED' && <WorkspaceForm className="teaching-form" onSubmit={addPeriod}><Field label="Term or semester name" name="name" maxLength={60} required /><Field label="Period start" name="start_date" type="date" min={year.start_date} max={year.end_date} required /><Field label="Period end" name="end_date" type="date" min={year.start_date} max={year.end_date} required /><button disabled={mutation.isPending}>Add period</button></WorkspaceForm>}
    </section>
    {year.status !== 'CLOSED' ? <section className="teaching-panel"><h2>{action === 'ACTIVE' ? 'Activate year' : 'Close and approve year'}</h2><p>{action === 'ACTIVE' ? 'Add at least one term or semester. Only one year can be active.' : 'Release all published assessment results first. Closing locks academic editing and student submissions for this year; existing records remain readable. Closure cannot be undone here.'}</p>
      <WorkspaceForm onSubmit={transition}><Field label={`Type ${action} ${year.name} to confirm`} value={confirmation} onChange={e => setConfirmation(e.target.value)} required /><button className="btn btn--primary" disabled={mutation.isPending || confirmation !== `${action} ${year.name}`}>{action === 'ACTIVE' ? 'Activate academic year' : 'Close academic year'}</button></WorkspaceForm></section> : <section className="teaching-panel"><h2>Promote to the next academic year</h2><p>Create the destination year and classes first. Map each class to its next class, or explicitly mark it completed/leaving. This moves the whole class together. Students who repeat or change streams can be adjusted in the destination class afterward. Previous enrollments, attendance and marks remain available as history.</p>
      <WorkspaceForm onSubmit={preview}><fieldset className="workspace-form-fields" disabled={busy || readOnly}><Field label="Destination year" value={target} onChange={e => { setTarget(e.target.value); setMappings({}); setPlan(null); }} required><option value="">Choose later year</option>{years.filter(y => y.start_date > year.end_date && y.status !== 'CLOSED').map(y => <option key={y.id} value={y.id}>{y.name}</option>)}</Field>
        {target && sourceClasses.map(c => <Field key={c.id} label={`${c.name} →`} value={mappings[c.id] || ''} required onChange={e => { setMappings(old => ({ ...old, [c.id]: e.target.value })); setPlan(null); }}><option value="">Choose outcome</option><option value="completed">Completed / leaving</option>{targets.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</Field>)}
        <button disabled={!target || !sourceClasses.length || busy}>Review promotion plan</button></fieldset></WorkspaceForm>
      {plan && <section className="teaching-notice"><h3>Confirm promotion</h3><ul>{plan.summary.map((r, i) => <li key={i}>{r.source} → {r.target}: {r.students} students</li>)}</ul><p>{plan.enrollments} destination enrollments. A year can be promoted once.</p><button type="button" className="btn btn--primary" disabled={busy || readOnly} onClick={promote}>Confirm reviewed promotion</button></section>}
    </section>}
  </>;
}
