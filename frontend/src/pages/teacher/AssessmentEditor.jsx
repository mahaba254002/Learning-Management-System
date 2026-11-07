import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useWorkDraft } from '../../hooks/useWorkDraft';
import { useState } from 'react';
import { Field } from './TeachingUI';
import { FileUpload } from '../elearning/files';
import { FILE_GROUPS, inputDate } from '../elearning/format';
import { useTeachingQuery } from './teachingQueries';

export default function AssessmentEditor({ subject, editing, pending, save, cancel }) {
  const draft = useWorkDraft('assessment', `${subject.id}:${editing?.id || 'new'}`);
  const periods = useTeachingQuery(`/api/teaching/subjects/${subject.id}/periods`);
  const config = useTeachingQuery('/api/institution/academic-configuration');
  const strands = useTeachingQuery(`/api/teaching/subjects/${subject.id}/strands`);
  const method = draft.value.assessment_mode ?? editing?.assessment_mode ?? (config.data?.assessment_policy === 'COMPETENCY' ? 'COMPETENCY' : 'NUMERIC');
  const value = (field, fallback = '') => draft.value[field] ?? editing?.[field] ?? fallback;
  const delivery = value('delivery', 'STANDARD');
  const quiz = delivery === 'QUIZ';
  // The uploaded paper is kept outside the recovery draft: it is a stored file, not typed text.
  const [paper, setPaper] = useState(editing?.paper || null);
  const fileTypes = value('submission_file_types', []);
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
      {strands.data?.length > 0 && <Field label="Strand (optional)" name="strand_id" value={value('strand_id', '') || ''} onChange={e => change('strand_id', e.target.value)}><option value="">Whole learning area</option>{strands.data.map(s => <option key={s.id} value={s.id}>{s.parent_id ? '— ' : ''}{s.code} · {s.name}</option>)}</Field>}
      <Field label="How students answer" name="delivery" value={delivery} disabled={Boolean(editing)} onChange={e => change('delivery', e.target.value)}
        description={editing ? 'This cannot change after the assessment is created.' : 'An online quiz is answered question by question on Skynet and marked automatically.'}>
        <option value="STANDARD">Hand in work (typed answer, link or file)</option><option value="QUIZ">Online quiz (multiple choice, true/false)</option></Field>
      {editing && <input type="hidden" name="delivery" value={delivery} />}
      <Field label="Title" name="title" required maxLength={200} value={value('title')} onChange={e => change('title', e.target.value)} />
      <Field label="Week or topic (optional)" name="section" maxLength={120} value={value('section')} onChange={e => change('section', e.target.value)} description="Groups this with materials under the same heading on the course page." />
      <Field label="Type" name="kind" value={value('kind', 'ASSIGNMENT')} onChange={e => change('kind', e.target.value)}><option value="ASSIGNMENT">Assignment</option><option value="COURSEWORK">Coursework</option><option value="EXAM">Examination</option></Field>
      <div className="form-field"><label htmlFor="coursework-instructions">Instructions</label><textarea id="coursework-instructions" name="instructions" required maxLength={20000} value={value('instructions')} onChange={e => change('instructions', e.target.value)} /></div>
      {quiz && <Field label="Opens (optional, your local time)" name="opens_at" type="datetime-local" value={draft.value.opens_at ?? inputDate(editing?.opens_at)} onChange={e => change('opens_at', e.target.value)} description="Students can see the quiz before this but cannot start it." />}
      <Field label={quiz ? 'Closes (your local time)' : 'Due date and time (optional, your local time)'} name="due_at" type="datetime-local" required={quiz} value={draft.value.due_at ?? inputDate(editing?.due_at)} onChange={e => change('due_at', e.target.value)} />
      <input type="hidden" name="paper_file_id" value={paper?.id || ''} />
      <FileUpload label={quiz ? 'Attach a file (optional)' : 'Question paper or brief (optional)'} path={`/api/teaching/subjects/${subject.id}/files?purpose=PAPER`}
        hint="PDF, Word, PowerPoint, Excel or an image, up to 10 MB. Students can open it once the work is published." current={paper}
        onUploaded={setPaper} onRemove={() => setPaper(null)} disabled={subject.academic_year_status === 'CLOSED'} />
      {!quiz && value('kind', 'ASSIGNMENT') !== 'EXAM' && <fieldset className="file-types"><legend>Students may hand in files</legend>
        {Object.entries(FILE_GROUPS).map(([key, group]) => <label key={key} className="teaching-checkbox"><input type="checkbox" name="submission_file_types" value={key} checked={fileTypes.includes(key)}
          onChange={e => change('submission_file_types', e.target.checked ? [...fileTypes, key] : fileTypes.filter(k => k !== key))} />{group.label}</label>)}
        <p className="teaching-muted">Leave all unticked for typed answers and links only.</p></fieldset>}
      {quiz ? <><input type="hidden" name="max_score" value={editing?.max_score || 1} /><p className="teaching-muted">A quiz is marked out of the total of its question marks. Add questions after saving.</p></> : method==='NUMERIC' ? <Field label="Maximum score" name="max_score" type="number" min="0.01" max="10000" step="0.01" required value={value('max_score', 100)} onChange={e => change('max_score', e.target.value)} /> : <><input type="hidden" name="max_score" value="100"/><p>Rubric: {(editing?.rubric_labels || config.data?.competency_labels || []).join(' · ')}. No numeric mark is assigned.</p></>}
      <label className="teaching-checkbox"><input type="checkbox" name="published" checked={value('published', false)} onChange={e => change('published', e.target.checked)} />Publish to students in this class</label>
      {!quiz && <label className="teaching-checkbox"><input type="checkbox" name="allow_late_submissions" checked={value('allow_late_submissions', true)} onChange={e => change('allow_late_submissions', e.target.checked)} />Accept late submissions (marked late)</label>}
      <p className="teaching-muted">Recovery drafts are private. Save assessment to update it, and release results separately in Scores.</p>
      <div className="teaching-actions"><button className="btn btn--primary">{pending ? 'Saving…' : 'Save assessment'}</button><button type="button" onClick={() => draft.clear()}>Discard recovery draft</button>{editing && <button type="button" onClick={cancel}>Cancel edit</button>}</div>
    </fieldset></WorkspaceForm></>;
}
