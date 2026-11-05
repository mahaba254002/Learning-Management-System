import { useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import { Pagination } from './StaffDirectoryPage';

const offeringName = o => `${o.name} · ${o.class_name}${o.stream ? ` ${o.stream}` : ''} · ${o.academic_year}`;

export default function StaffAllocationsPage() {
  const [staff, setStaff] = useState('');
  const [offering, setOffering] = useState('');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const options = useTeachingQuery('/api/management/options');
  const query = useTeachingQuery(`/api/management/allocations?${new URLSearchParams({ offset, ...(staff ? { staff_id: staff } : {}), ...(offering ? { subject_id: offering } : {}) })}`);
  const mutation = useTeachingMutation();
  const filters = setter => event => { setter(event.target.value); setOffset(0); };
  async function remove(row) {
    try { await mutation.mutateAsync({ path: `/api/management/allocations/${row.id}`, method: 'DELETE' }); } catch { /* Shown below. */ }
  }
  return <div className="management-page"><PageHeading title="Teaching allocations">Who teaches each offering. One lead teacher per offering, plus any co-teachers. Co-teachers can take registers and enter marks.</PageHeading>
    <div className="management-links"><Link to="/institution/staff">Employees</Link><Link to="/institution/classes">Classes and offerings</Link></div>
    <QueryState query={options} />{options.data && <AllocationForm key={editing?.id || 'new'} row={editing} options={options.data} onClose={() => setEditing(null)} />}
    <div className="management-filters"><Field label="Employee" value={staff} onChange={filters(setStaff)}><option value="">All employees</option>{options.data?.staff.filter(s => s.category === 'TEACHING').map(s => <option key={s.id} value={s.id}>{s.staff_number} · {s.name}</option>)}</Field>
      <Field label="Offering" value={offering} onChange={filters(setOffering)}><option value="">All offerings</option>{options.data?.offerings.map(o => <option key={o.id} value={o.id}>{offeringName(o)}</option>)}</Field></div>
    <MutationState mutation={mutation} message="Allocation removed." />
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>Allocations</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Teacher</th><th>Offering</th><th>Role / group</th><th>Hours / week</th><th>Action</th></tr></thead><tbody>{query.data.items.map(row => <tr key={row.id}>
      <td>{row.staff_name}<small>{row.staff_number || 'No staff record'}</small></td><td>{row.subject_name}<small>{row.class_name}{row.stream ? ` ${row.stream}` : ''} · {row.academic_year}</small></td>
      <td>{row.role === 'LEAD' ? 'Lead' : 'Co-teacher'}<small>{row.group_name || 'Whole offering'}</small></td><td>{row.weekly_hours ?? '—'}</td>
      <td><div className="teaching-actions"><button type="button" onClick={() => setEditing(row)}>Edit</button>{row.role !== 'LEAD' && <button type="button" disabled={mutation.isPending} onClick={() => remove(row)}>Remove</button>}</div></td></tr>)}</tbody></table></div>
      {!query.data.total && <p>No allocations yet. Offerings get their lead teacher when they are created under Classes and teaching.</p>}<Pagination offset={offset} total={query.data.total} setOffset={setOffset} /></section>}
  </div>;
}

function AllocationForm({ row, options, onClose }) {
  const mutation = useTeachingMutation();
  const [generation, setGeneration] = useState(0);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const body = { role: values.role, group_name: values.group_name, weekly_hours: values.weekly_hours || null };
    try {
      await mutation.mutateAsync(row
        ? { path: `/api/management/allocations/${row.id}`, method: 'PUT', body: { ...body, expected_updated_at: row.updated_at } }
        : { path: '/api/management/allocations', body: { ...body, subject_id: values.subject_id, staff_id: values.staff_id } });
      setGeneration(value => value + 1); onClose();
    } catch { /* Shown below. */ }
  }
  const teachers = options.staff.filter(s => s.category === 'TEACHING' && s.status === 'ACTIVE' && s.user_id);
  return <section className="teaching-panel"><h2>{row ? `Edit ${row.staff_name} on ${row.subject_name}` : 'Add a teacher to an offering'}</h2><MutationState mutation={mutation} message="Allocation saved." /><WorkspaceForm key={generation} className="teaching-form" onSubmit={save}>
    {!row && <><Field label="Offering" name="subject_id" required defaultValue=""><option value="">Choose offering</option>{options.offerings.map(o => <option key={o.id} value={o.id}>{offeringName(o)}</option>)}</Field>
      <Field label="Teacher" name="staff_id" required defaultValue=""><option value="">Choose teacher</option>{teachers.map(s => <option key={s.id} value={s.id}>{s.staff_number} · {s.name}</option>)}</Field></>}
    <Field label="Role" name="role" defaultValue={row?.role || 'ASSISTANT'} disabled={row?.role === 'LEAD'}><option value="ASSISTANT">Co-teacher</option><option value="LEAD">Lead teacher</option></Field>
    {row?.role === 'LEAD' && <input type="hidden" name="role" value="LEAD" />}
    <Field label="Group or section (optional)" name="group_name" maxLength={100} defaultValue={row?.group_name || ''} description="Leave empty for the lead teacher." />
    <Field label="Weekly hours (optional)" name="weekly_hours" type="number" min="0.01" max="168" step="0.01" defaultValue={row?.weekly_hours || ''} />
    <p>Making someone the lead keeps the previous lead on as a co-teacher. Remove them afterwards if they no longer teach it.</p>
    <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save allocation</button>{row && <button type="button" disabled={mutation.isPending} onClick={onClose}>Cancel edit</button>}</div>
  </WorkspaceForm></section>;
}
