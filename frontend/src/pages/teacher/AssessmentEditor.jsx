import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useWorkDraft } from '../../hooks/useWorkDraft';
import { Field } from './TeachingUI';
import { useTeachingQuery } from './teachingQueries';

function inputDate(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export default function AssessmentEditor({ subject, editing, pending, save, cancel }) {
  const draft = useWorkDraft('assessment', `${subject.id}:${editing?.id || 'new'}`);
  const periods = useTeachingQuery(`/api/teaching/subjects/${subject.id}/periods`);
  const config = useTeachingQuery('/api/institution/academic-configuration');
  const method = draft.value.assessment_mode ?? editing?.assessment_mode ?? (config.data?.assessment_policy === 'COMPETENCY' ? 'COMPETENCY' : 'NUMERIC');
  const value = (field, fallback = '') => draft.value[field] ?? editing?.[field] ?? fallback;
  const change = (field, next) => draft.change(old => ({ ...old, __base_updated_at: old.__base_updated_at ?? editing?.updated_at, [field]: next }));
  async function submit(event) {
    if (await save(event)) await draft.clear();
  }
  return <><p role="status" className="teaching-muted">{draft.status}</p><WorkspaceForm className="teaching-form" onSubmit={submit}>
    <fieldset className="workspace-form-fields" disabled={subject.academic_year_status === 'CLOSED' || pending || !draft.ready || draft.blocked}>
      {editing && <input type="hidden" name="expected_updated_at" value={draft.value.__base_updated_at ?? editing.updated_at} />}
      <Field label="Assessment method" name="assessment_mode" value={method} onChange={e => change('assessment_mode',e.target.value)}>
        {config.data?.assessment_policy !== 'COMPETENCY' && <option value="NUMERIC">Numeric marks</option>}{config.data?.assessment_policy !== 'NUMERIC' && <option value="COMPETENCY">Competency observation</option>}
      </Field>
      <Field label="Reporting term / semester" name="period_id" value={value('period_id', '') || ''} onChange={e=>change('period_id',e.target.value)}><option value="">Offering period / not assigned</option>{periods.data?.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</Field>
      <Field label="Title" name="title" required maxLength={200} value={value('title')} onChange={e => change('title', e.target.value)} />
      <Field label="Type" name="kind" value={value('kind', 'ASSIGNMENT')} onChange={e => change('kind', e.target.value)}><option value="ASSIGNMENT">Assignment</option><option value="COURSEWORK">Coursework</option><option value="EXAM">Examination</option></Field>
      <div className="form-field"><label htmlFor="coursework-instructions">Instructions</label><textarea id="coursework-instructions" name="instructions" required maxLength={20000} value={value('instructions')} onChange={e => change('instructions', e.target.value)} /></div>
      <Field label="Due date and time (optional, your local time)" name="due_at" type="datetime-local" value={draft.value.due_at ?? inputDate(editing?.due_at)} onChange={e => change('due_at', e.target.value)} />
      {method==='NUMERIC' ? <Field label="Maximum score" name="max_score" type="number" min="0.01" max="10000" step="0.01" required value={value('max_score', 100)} onChange={e => change('max_score', e.target.value)} /> : <><input type="hidden" name="max_score" value="100"/><p>Rubric: {(editing?.rubric_labels || config.data?.competency_labels || []).join(' · ')}. No numeric mark is assigned.</p></>}
      <label className="teaching-checkbox"><input type="checkbox" name="published" checked={value('published', false)} onChange={e => change('published', e.target.checked)} />Publish to students in this class</label>
      <label className="teaching-checkbox"><input type="checkbox" name="allow_late_submissions" checked={value('allow_late_submissions', true)} onChange={e => change('allow_late_submissions', e.target.checked)} />Accept late submissions (marked late)</label>
      <p className="teaching-muted">Recovery drafts are private. Save assessment to update it, and release results separately in Scores.</p>
      <div className="teaching-actions"><button className="btn btn--primary">{pending ? 'Saving…' : 'Save assessment'}</button><button type="button" onClick={() => draft.clear()}>Discard recovery draft</button>{editing && <button type="button" onClick={cancel}>Cancel edit</button>}</div>
    </fieldset></WorkspaceForm></>;
}
