import { useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import { Pagination } from './StaffDirectoryPage';

export default function StaffAllocationsPage() {
  const [period, setPeriod] = useState('');
  const [staff, setStaff] = useState('');
  const [active, setActive] = useState('true');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const options = useTeachingQuery('/api/management/options');
  const query = useTeachingQuery(`/api/management/allocations?${new URLSearchParams({ offset, ...(period ? { period } : {}), ...(staff ? { staff_id: staff } : {}), ...(active ? { active } : {}) })}`);
  const filters = setter => event => { setter(event.target.value); setOffset(0); };
  return <div className="management-page"><PageHeading title="Staff course allocations">Assign courses and weekly teaching hours without requiring student accounts or learning submissions.</PageHeading>
    <div className="management-links"><Link to="/institution/staff">Manage employees</Link><Link to="/institution/academic-structure">Manage course catalogue</Link></div>
    <QueryState query={options} />{options.data && <AllocationForm key={editing?.id || 'new'} row={editing} options={options.data} onClose={() => setEditing(current => current?.id === editing?.id ? null : current)} />}
    <div className="management-filters"><Field label="Period (exact name)" value={period} onChange={filters(setPeriod)} placeholder="e.g. 2026 Term 3" /><Field label="Employee" value={staff} onChange={filters(setStaff)}><option value="">All employees</option>{options.data?.staff.map(s => <option key={s.id} value={s.id}>{s.staff_number} · {s.name}</option>)}</Field><Field label="Allocation status" value={active} onChange={filters(setActive)}><option value="true">Active</option><option value="false">Ended</option><option value="">All</option></Field></div>
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>Teaching responsibilities</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Employee</th><th>Course</th><th>Period / group</th><th>Hours / week</th><th>Status</th><th>Action</th></tr></thead><tbody>{query.data.items.map(row => <tr key={row.id}><td>{options.data?.staff.find(s => s.id === row.staff_id)?.name || 'Employee'}</td><td>{options.data?.courses.find(c => c.id === row.course_id)?.name || 'Course'}</td><td>{row.period}<small>{row.group_name || 'No group specified'}</small></td><td>{row.weekly_hours}</td><td>{row.active ? 'Active' : 'Ended'}</td><td><button type="button" onClick={() => setEditing(row)}>Edit / end</button></td></tr>)}</tbody></table></div>{!query.data.total && <p>No allocations match these filters. Add an active teaching employee and a catalogue course to begin.</p>}<Pagination offset={offset} total={query.data.total} setOffset={setOffset} /></section>}
  </div>;
}

function AllocationForm({ row, options, onClose }) {
  const mutation = useTeachingMutation();
  const [generation, setGeneration] = useState(0);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try { await mutation.mutateAsync({ path: `/api/management/allocations${row ? `/${row.id}` : ''}`, method: row ? 'PUT' : 'POST', body: { ...values, active: values.active === 'on', ...(row ? { expected_updated_at: row.updated_at } : {}) } }); setGeneration(value => value + 1); onClose(); } catch { /* Shown below. */ }
  }
  return <section className="teaching-panel"><h2>{row ? 'Edit allocation' : 'Allocate a course'}</h2><MutationState mutation={mutation} message="Course allocation saved." /><WorkspaceForm key={generation} className="teaching-form" onSubmit={save}>
    <Field label="Teaching employee" name="staff_id" required defaultValue={row?.staff_id || ''}><option value="">Choose employee</option>{options.staff.filter(s => (s.category === 'TEACHING' && s.status === 'ACTIVE') || s.id === row?.staff_id).map(s => <option key={s.id} value={s.id}>{s.staff_number} · {s.name}</option>)}</Field>
    <Field label="Course" name="course_id" required defaultValue={row?.course_id || ''}><option value="">Choose course</option>{options.courses.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</Field>
    <Field label="Period" name="period" required maxLength={100} defaultValue={row?.period || ''} placeholder="e.g. 2026 Term 3" /><Field label="Group / section (optional)" name="group_name" maxLength={100} defaultValue={row?.group_name || ''} />
    <Field label="Weekly teaching hours" name="weekly_hours" type="number" min="0.01" max="168" step="0.01" required defaultValue={row?.weekly_hours || ''} />
    <label><input type="checkbox" name="active" defaultChecked={row?.active ?? true} /> Active responsibility</label>
    <p>Use the same period name for related allocations. Ending an allocation retains its history. Class teaching groups and their student enrollments remain managed under Classes & teaching when student records are enabled.</p>
    <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save allocation</button>{row && <button type="button" disabled={mutation.isPending} onClick={onClose}>Cancel edit</button>}</div>
  </WorkspaceForm></section>;
}
