import { useState } from 'react';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';

const KIND_LABELS = { FACULTY: 'Faculty', SCHOOL: 'School', DEPARTMENT: 'Department' };

export default function DepartmentsPage() {
  const query = useTeachingQuery('/api/management/departments');
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  const [kind, setKind] = useState('DEPARTMENT');
  const [generation, setGeneration] = useState(0);
  const parents = query.data?.filter(row => row.kind !== 'DEPARTMENT' && row.id !== editing?.id) || [];
  const nameOf = id => query.data?.find(row => row.id === id)?.name;
  function edit(row) { setEditing(row); setKind(row?.kind || 'DEPARTMENT'); mutation.reset(); }
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    values.parent_id = values.parent_id || null;
    try { await mutation.mutateAsync({ path: `/api/management/departments${editing ? `/${editing.id}` : ''}`, method: editing ? 'PUT' : 'POST', body: { ...values, kind, ...(editing ? { expected_updated_at: editing.updated_at } : {}) } }); edit(null); setGeneration(value => value + 1); } catch { /* Keep inputs. */ }
  }
  const rows = [...(query.data || [])].sort((a, b) => (nameOf(a.parent_id) || a.name).localeCompare(nameOf(b.parent_id) || b.name) || (a.parent_id ? 1 : 0) - (b.parent_id ? 1 : 0));
  return <><PageHeading title="Departments and faculties">Universities can group departments under faculties or schools. Schools can keep a flat list of departments.</PageHeading><MutationState mutation={mutation} />
    <section className="teaching-panel"><h2>{editing ? `Edit ${KIND_LABELS[editing.kind].toLowerCase()}` : 'Add a unit'}</h2><WorkspaceForm className="teaching-form" key={`${generation}:${editing?.id || 'new'}`} onSubmit={save}>
      <Field label="Type" value={kind} onChange={event => setKind(event.target.value)}>{Object.entries(KIND_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Field>
      <Field label="Code" name="code" required maxLength={30} pattern="[A-Za-z0-9._/-]+" defaultValue={editing?.code || ''} /><Field label="Name" name="name" required maxLength={160} defaultValue={editing?.name || ''} />
      {kind === 'DEPARTMENT' && <Field label="Faculty or school (optional)" name="parent_id" defaultValue={editing?.parent_id || ''}><option value="">None</option>{parents.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</Field>}
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save</button>{editing && <button type="button" onClick={() => edit(null)}>Cancel</button>}</div></WorkspaceForm></section>
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>Units</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Code</th><th>Name</th><th>Type</th><th>Part of</th><th>Action</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.code}</td><td>{row.name}</td><td>{KIND_LABELS[row.kind]}</td><td>{nameOf(row.parent_id) || '—'}</td><td><button type="button" onClick={() => edit(row)}>Edit</button></td></tr>)}</tbody></table></div>{!query.data.length && <p>No departments yet.</p>}</section>}</>;
}
