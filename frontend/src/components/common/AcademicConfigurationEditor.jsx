import ProgressionRulesEditor from './ProgressionRulesEditor';
import GradingRulesEditor from './GradingRulesEditor';
import { Field } from '../../pages/teacher/TeachingUI';
import { useState } from 'react';
import '../dashboard/OperationalDashboard.css';

export default function AcademicConfigurationEditor({ value, onChange, disabled = false }) {
  const config = value.configuration, labels = value.labels;
  const [bandText,setBandText] = useState(() => labels.grade_bands.map(b => `${b.minimum}: ${b.label}`).join('\n'));
  const set = (key, next) => onChange({ ...value, configuration: { ...config, [key]: next } });
  const label = (key, next) => onChange({ ...value, labels: { ...labels, [key]: next } });
  return <fieldset className="academic-config" disabled={disabled}><legend>Academic setup</legend><p>Choose how this customer operates. Templates are starting points; confirm the institution’s own academic and grading policy.</p>
    <div className="academic-config-grid">
      <Field label="Academic structure" value={config.structure} onChange={e => set('structure', e.target.value)}><option value="GROUPED">Levels → groups → subjects / learning areas</option><option value="PROGRAMME">Departments → programmes → levels → cohorts → courses</option></Field>
      <Field label="Default registration for new offerings" value={config.registration_mode} onChange={e => set('registration_mode', e.target.value)}><option value="COHORT">Whole group / cohort</option><option value="INDIVIDUAL">Individual course registration</option></Field>
      <Field label="Calendar periods" value={config.period_kind} onChange={e => set('period_kind', e.target.value)}><option value="TERM">Terms</option><option value="SEMESTER">Semesters</option><option value="BLOCK">Blocks / sessions</option></Field>
      <Field label="Assessment policy" value={config.assessment_policy} onChange={e => set('assessment_policy', e.target.value)}><option value="NUMERIC">Numeric marks</option><option value="COMPETENCY">Competency observations</option><option value="MIXED">Numeric and competency assessments</option></Field>
      <label className="academic-check"><input type="checkbox" checked={config.credits_enabled} onChange={e => set('credits_enabled', e.target.checked)} />Enable course credits and approved completion records</label>
      <label className="academic-check"><input type="checkbox" checked={config.institution_policy_edits} onChange={e => set('institution_policy_edits', e.target.checked)} />Allow institution admin to edit terminology and grade bands</label>
    </div>
    <details open><summary>Terminology and learner access</summary><div className="academic-config-grid">
      {[['student_label','Learner label'],['teacher_label','Educator label'],['class_label','Group / cohort label'],['subject_label','Subject / course label'],['period_label','Calendar label']].map(([key,title]) => <Field key={key} label={title} required maxLength={30} value={labels[key]} onChange={e => label(key,e.target.value)} />)}
      <Field label="Default learner sign-in" value={labels.default_student_login} onChange={e => label('default_student_login',e.target.value)}><option value="EMAIL">Email and password</option><option value="STUDENT_ID">Student ID and password</option></Field>
    </div></details>
    {config.assessment_policy !== 'NUMERIC' && <div className="form-field"><label htmlFor="policy-competencies">Competency outcomes (one per line)</label><textarea id="policy-competencies" rows={3} value={config.competency_labels.join('\n')} onChange={e => set('competency_labels',e.target.value.split('\n'))} /><small>These are editable starter labels, not an official curriculum rubric. Each new assessment keeps a snapshot of its rubric.</small></div>}
    <ProgressionRulesEditor rules={config.progression_rules} labels={config.competency_labels} onChange={rules=>set('progression_rules',rules)}/>
    <GradingRulesEditor rules={config.grading_rules} onChange={rules=>set('grading_rules',rules)}/>
    <details><summary>Individual assessment grade labels</summary><div className="form-field"><label htmlFor="policy-grades">Minimum percentage: label (one per line)</label><textarea id="policy-grades" rows={4} value={bandText} onChange={e => {setBandText(e.target.value);label('grade_bands',e.target.value.trim() ? e.target.value.split('\n').map(line => { const [minimum,...rest]=line.split(':'); return {minimum:Number(minimum),label:rest.join(':').trim()}; }) : []);}} /><small>Include 0 when using bands. Leave empty for numeric marks only. These labels apply to individual assessment marks. Final grades and GPA use the separate platform policy above.</small></div></details>
  </fieldset>;
}
