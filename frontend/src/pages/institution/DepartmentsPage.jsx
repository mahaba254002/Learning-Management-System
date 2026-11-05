import { useState } from 'react';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';

export default function DepartmentsPage() {
  const query = useTeachingQuery('/api/management/departments');
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  const [generation, setGeneration] = useState(0);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try { await mutation.mutateAsync({ path: `/api/management/departments${editing ? `/${editing.id}` : ''}`, method: editing ? 'PUT' : 'POST', body: { ...values, ...(editing ? { expected_updated_at: editing.updated_at } : {}) } }); setEditing(null); setGeneration(value => value + 1); } catch { /* Keep inputs. */ }
  }
  return <><PageHeading title="Departments">Organise academic and support departments independently of your institution’s learning structure.</PageHeading><MutationState mutation={mutation} />
    <section className="teaching-panel"><h2>{editing ? 'Edit department' : 'Add department'}</h2><WorkspaceForm className="teaching-form" key={`${generation}:${editing?.id || 'new'}`} onSubmit={save}><Field label="Department code" name="code" required maxLength={30} pattern="[A-Za-z0-9._/-]+" defaultValue={editing?.code || ''} /><Field label="Department name" name="name" required maxLength={160} defaultValue={editing?.name || ''} /><div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save department</button>{editing && <button type="button" onClick={() => setEditing(null)}>Cancel</button>}</div></WorkspaceForm></section>
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>Institution departments</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Code</th><th>Name</th><th>Action</th></tr></thead><tbody>{query.data.map(row => <tr key={row.id}><td>{row.code}</td><td>{row.name}</td><td><button type="button" onClick={() => { setEditing(row); mutation.reset(); }}>Edit</button></td></tr>)}</tbody></table></div>{!query.data.length && <p>No departments yet. Add the institution’s academic and support departments above.</p>}</section>}</>;
}
