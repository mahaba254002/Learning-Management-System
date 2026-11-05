import { useState } from 'react';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, QueryState } from '../teacher/TeachingUI';

const LEVELS = [
  ['ECDE', 'ECDE (PP1–PP2)'], ['LOWER_PRIMARY', 'Lower primary (Grades 1–3)'], ['UPPER_PRIMARY', 'Upper primary (Grades 4–6)'],
  ['JUNIOR_SCHOOL', 'Junior school (Grades 7–9)'], ['SENIOR_SCHOOL', 'Senior school (Grades 10–12)'],
  ['COLLEGE', 'College'], ['TVET', 'TVET'], ['UNIVERSITY', 'University'],
];
const TERTIARY = new Set(['COLLEGE', 'TVET', 'UNIVERSITY']);
const KINDS = { COMPETENCY: 'Competency levels', LETTER: 'Letter grades', GPA: 'Grade points', PERCENT: 'Percentage only' };

export default function InstitutionLevels({ root, institutionId }) {
  const levels = useTeachingQuery(`${root}/levels`);
  const scales = useTeachingQuery(`/api/platform/assessment-scales?institution_id=${institutionId}`);
  return <section className="teaching-panel"><h2>Levels and assessment scales</h2>
    <p>Choose the levels this institution offers and the scale each one is marked with, as agreed at onboarding. Marks already entered keep the scale they were marked with.</p>
    <QueryState query={levels} /><QueryState query={scales} />
    {levels.data && scales.data && <LevelsForm key={levels.data.updated_at} initial={levels.data} scales={scales.data} root={root} />}
    {scales.data && <ScaleLibrary scales={scales.data} root={root} />}
  </section>;
}

function LevelsForm({ initial, scales, root }) {
  const mutation = useTeachingMutation();
  const current = Object.fromEntries(initial.levels.map(row => [row.level, row]));
  const [rows, setRows] = useState(() => Object.fromEntries(LEVELS.map(([level]) => {
    const row = current[level];
    return [level, row ? { on: true, active: row.active, scale_id: row.scale?.id || '', structure: row.structure, period_kind: row.period_kind, class_label: row.terminology.class_label || '' }
      : { on: false, active: true, scale_id: '', structure: TERTIARY.has(level) ? 'PROGRAMME' : 'GROUPED', period_kind: level === 'COLLEGE' || level === 'UNIVERSITY' ? 'SEMESTER' : 'TERM', class_label: '' }];
  })));
  const set = (level, key, value) => setRows(old => ({ ...old, [level]: { ...old[level], [key]: value } }));
  async function save(event) {
    event.preventDefault();
    const levels = LEVELS.filter(([level]) => rows[level].on).map(([level]) => {
      const row = rows[level];
      return { level, active: row.active, scale_id: row.scale_id || null, structure: row.structure, period_kind: row.period_kind,
               terminology: row.class_label ? { class_label: row.class_label } : {} };
    });
    try { await mutation.mutateAsync({ path: `${root}/levels`, method: 'PUT', body: { levels, expected_updated_at: initial.updated_at } }); } catch { /* Shown below. */ }
  }
  return <form onSubmit={save}><div className="table-wrapper"><table className="data-table"><thead><tr><th>Level</th><th>Assessment scale</th><th>Structure</th><th>Periods</th><th>Class label</th><th>Active</th></tr></thead><tbody>
    {LEVELS.map(([level, name]) => { const row = rows[level]; return <tr key={level}>
      <td><label className="teaching-checkbox"><input type="checkbox" checked={row.on} onChange={e => set(level, 'on', e.target.checked)} />{name}</label></td>
      <td><select aria-label={`${name} scale`} disabled={!row.on} value={row.scale_id} onChange={e => set(level, 'scale_id', e.target.value)}><option value="">Institution grade bands</option>{scales.map(s => <option key={s.id} value={s.id}>{s.name}{s.preset ? '' : ' (custom)'}</option>)}</select></td>
      <td><select aria-label={`${name} structure`} disabled={!row.on} value={row.structure} onChange={e => set(level, 'structure', e.target.value)}><option value="GROUPED">Classes and streams</option><option value="PROGRAMME">Programmes</option></select></td>
      <td><select aria-label={`${name} periods`} disabled={!row.on} value={row.period_kind} onChange={e => set(level, 'period_kind', e.target.value)}><option value="TERM">Terms</option><option value="SEMESTER">Semesters</option><option value="BLOCK">Blocks</option></select></td>
      <td><input aria-label={`${name} class label`} disabled={!row.on} maxLength={30} placeholder="Default" value={row.class_label} onChange={e => set(level, 'class_label', e.target.value)} /></td>
      <td><input type="checkbox" aria-label={`${name} active`} disabled={!row.on} checked={row.active} onChange={e => set(level, 'active', e.target.checked)} /></td>
    </tr>; })}</tbody></table></div>
    <p>A level with classes or courses cannot be removed. Mark it inactive instead.</p>
    <MutationState mutation={mutation} message="Levels saved." /><button className="btn btn--primary" disabled={mutation.isPending}>Save levels</button></form>;
}

function blankLevel() { return { code: '', label: '', min_percent: '', points: '', descriptor: '' }; }

function ScaleLibrary({ scales, root }) {
  const [editing, setEditing] = useState(null);
  return <><h3>Scale library</h3>
    <div className="table-wrapper"><table className="data-table"><thead><tr><th>Scale</th><th>Levels</th><th>Action</th></tr></thead><tbody>{scales.map(s => <tr key={s.id}>
      <td>{s.name}<small>{s.preset ? 'Preset' : s.in_use ? 'Custom · used by marks' : 'Custom'}</small></td>
      <td>{s.levels.map(lv => lv.min_percent != null ? `${lv.code} ${Number(lv.min_percent)}%+` : lv.code).join(' · ') || 'Percentage only'}</td>
      <td><div className="teaching-actions"><button type="button" onClick={() => setEditing({ copy: true, scale: s })}>Copy</button>{!s.preset && !s.in_use && <button type="button" onClick={() => setEditing({ copy: false, scale: s })}>Edit</button>}</div></td></tr>)}</tbody></table></div>
    {!editing && <button type="button" onClick={() => setEditing({ copy: false, scale: null })}>New scale</button>}
    {editing && <ScaleEditor key={`${editing.scale?.id}:${editing.copy}`} {...editing} root={root} onClose={() => setEditing(null)} />}</>;
}

function ScaleEditor({ scale, copy, root, onClose }) {
  const mutation = useTeachingMutation();
  const [name, setName] = useState(scale ? (copy ? `${scale.name} (copy)` : scale.name) : '');
  const [kind, setKind] = useState(scale?.kind || 'COMPETENCY');
  const [levels, setLevels] = useState(scale?.levels.length ? scale.levels.map(lv => ({ code: lv.code, label: lv.label, descriptor: lv.descriptor || '', min_percent: lv.min_percent ?? '', points: lv.points ?? '' })) : [blankLevel(), blankLevel()]);
  const set = (index, key, value) => setLevels(old => old.map((row, i) => i === index ? { ...row, [key]: value } : row));
  async function save(event) {
    event.preventDefault();
    const body = { name, kind, levels: kind === 'PERCENT' ? [] : levels.map(lv => ({ code: lv.code, label: lv.label, descriptor: lv.descriptor,
      min_percent: lv.min_percent === '' ? null : lv.min_percent, points: lv.points === '' ? null : lv.points })) };
    const editingOwn = scale && !copy;
    try {
      await mutation.mutateAsync(editingOwn
        ? { path: `${root}/assessment-scales/${scale.id}`, method: 'PUT', body: { ...body, expected_updated_at: scale.updated_at } }
        : { path: `${root}/assessment-scales`, body: { ...body, copied_from_id: copy ? scale.id : null } });
      onClose();
    } catch { /* Shown below. */ }
  }
  return <form className="teaching-form" onSubmit={save}><h3>{scale && !copy ? 'Edit scale' : 'New scale for this institution'}</h3><MutationState mutation={mutation} />
    <Field label="Name" value={name} onChange={e => setName(e.target.value)} required maxLength={100} />
    <Field label="Kind" value={kind} onChange={e => setKind(e.target.value)}>{Object.entries(KINDS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field>
    {kind !== 'PERCENT' && <><p>List levels from highest to lowest. Give each a minimum percentage, with the lowest at 0, or leave all minimums empty for observation-only competencies.</p>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Code</th><th>Label</th><th>Minimum %</th><th>Points</th><th></th></tr></thead><tbody>{levels.map((lv, i) => <tr key={i}>
        <td><input aria-label="Code" required maxLength={20} value={lv.code} onChange={e => set(i, 'code', e.target.value)} /></td>
        <td><input aria-label="Label" required maxLength={60} value={lv.label} onChange={e => set(i, 'label', e.target.value)} /></td>
        <td><input aria-label="Minimum percentage" type="number" min="0" max="100" step="0.01" value={lv.min_percent} onChange={e => set(i, 'min_percent', e.target.value)} /></td>
        <td><input aria-label="Points" type="number" min="0" max="100" step="0.01" value={lv.points} onChange={e => set(i, 'points', e.target.value)} /></td>
        <td><button type="button" disabled={levels.length <= 2} onClick={() => setLevels(old => old.filter((_, j) => j !== i))}>Remove</button></td></tr>)}</tbody></table></div>
      <button type="button" disabled={levels.length >= 20} onClick={() => setLevels(old => [...old, blankLevel()])}>Add level</button></>}
    <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save scale</button><button type="button" onClick={onClose}>Cancel</button></div></form>;
}
