import { useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import '../../components/common/ModuleEditor.css';

const labels = value => value.replaceAll('_', ' ').toLowerCase();

export default function StaffDirectoryPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [department, setDepartment] = useState('');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const options = useTeachingQuery('/api/management/options');
  const query = useTeachingQuery(`/api/management/staff?${new URLSearchParams({ search, offset, ...(category ? { category } : {}), ...(status ? { status } : {}), ...(department ? { department_id: department } : {}) })}`);
  const filters = setter => event => { setter(event.target.value); setOffset(0); };
  return <div className="management-page"><PageHeading title="Staff directory">Manage every employee, including staff who do not need a login or a teaching workspace.</PageHeading>
    <div className="management-links"><Link to="/institution/departments">Manage departments</Link><Link to="/institution/teachers">Teacher accounts and access</Link></div>
    <QueryState query={options} />
    <div className="management-filters"><Field label="Search staff" value={search} onChange={filters(setSearch)} /><Field label="Staff category" value={category} onChange={filters(setCategory)}><option value="">All categories</option><option value="TEACHING">Teaching</option><option value="NON_TEACHING">Non-teaching</option></Field>
      <Field label="Employment status" value={status} onChange={filters(setStatus)}><option value="">All statuses</option>{['ACTIVE', 'ON_LEAVE', 'INACTIVE'].map(s => <option key={s} value={s}>{labels(s)}</option>)}</Field>
      <Field label="Department" value={department} onChange={filters(setDepartment)}><option value="">All departments</option>{options.data?.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Field></div>
    <button type="button" className="btn btn--primary" onClick={() => { setAdding(true); setEditing(null); }}>Add employee</button>
    {(adding || editing) && options.data && <StaffForm key={editing?.id || 'new'} row={editing} options={options.data} onClose={() => { setAdding(false); setEditing(current => current?.id === editing?.id ? null : current); }} />}
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>{query.data.total} employee{query.data.total === 1 ? '' : 's'}</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Employee</th><th>Category / role</th><th>Department</th><th>Status</th><th>Contact</th><th>Action</th></tr></thead><tbody>{query.data.items.map(row => <tr key={row.id}>
      <td>{row.first_name} {row.last_name}<small>{row.staff_number}</small></td><td>{labels(row.category)}<small>{row.job_title} · {labels(row.employment_type)}</small></td><td>{options.data?.departments.find(d => d.id === row.department_id)?.name || 'Unassigned'}</td><td>{labels(row.status)}</td><td>{row.email || 'No email'}<small>{row.phone || 'No phone'}</small></td><td><button type="button" onClick={() => { setEditing(row); setAdding(false); }}>Edit</button></td>
    </tr>)}</tbody></table></div>{!query.data.total && <p>No employees match these filters. Add an employee to begin.</p>}<Pagination offset={offset} total={query.data.total} setOffset={setOffset} /></section>}
  </div>;
}

function StaffForm({ row, options, onClose }) {
  const mutation = useTeachingMutation();
  const [category, setCategory] = useState(row?.category || 'TEACHING');
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    for (const key of ['department_id', 'teacher_user_id', 'email', 'phone', 'joined_on']) values[key] = values[key] || null;
    if (category !== 'TEACHING') values.teacher_user_id = null;
    try { await mutation.mutateAsync({ path: `/api/management/staff${row ? `/${row.id}` : ''}`, method: row ? 'PUT' : 'POST', body: { ...values, ...(row ? { expected_updated_at: row.updated_at } : {}) } }); onClose(); } catch { /* Keep inputs. */ }
  }
  return <section className="teaching-panel"><h2>{row ? 'Edit employee' : 'Add employee'}</h2><p>Employee records do not create sign-in accounts. Link an existing teacher account when this employee needs the educator portal.</p><MutationState mutation={mutation} />
    <WorkspaceForm className="teaching-form" onSubmit={save}>
      <Field label="Staff number" name="staff_number" required maxLength={40} pattern="[A-Za-z0-9._/-]+" defaultValue={row?.staff_number || ''} />
      <Field label="First name" name="first_name" required maxLength={100} defaultValue={row?.first_name || ''} /><Field label="Last name" name="last_name" required maxLength={100} defaultValue={row?.last_name || ''} />
      <Field label="Category" name="category" value={category} onChange={event => setCategory(event.target.value)}><option value="TEACHING">Teaching</option><option value="NON_TEACHING">Non-teaching</option></Field>
      <Field label="Job title" name="job_title" required maxLength={120} defaultValue={row?.job_title || ''} />
      <Field label="Department" name="department_id" defaultValue={row?.department_id || ''}><option value="">Unassigned</option>{options.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Field>
      <Field label="Employment type" name="employment_type" defaultValue={row?.employment_type || 'FULL_TIME'}>{['FULL_TIME', 'PART_TIME', 'CONTRACT', 'VOLUNTEER'].map(value => <option key={value} value={value}>{labels(value)}</option>)}</Field>
      <Field label="Status" name="status" defaultValue={row?.status || 'ACTIVE'}>{['ACTIVE', 'ON_LEAVE', 'INACTIVE'].map(value => <option key={value} value={value}>{labels(value)}</option>)}</Field>
      <Field label="Date joined" name="joined_on" type="date" defaultValue={row?.joined_on || ''} />
      <Field label="Email (optional)" name="email" type="email" maxLength={255} defaultValue={row?.email || ''} /><Field label="Phone (optional)" name="phone" maxLength={50} defaultValue={row?.phone || ''} />
      {category === 'TEACHING' && <Field label="Linked teacher account (optional)" name="teacher_user_id" defaultValue={row?.teacher_user_id || ''}><option value="">No account</option>{options.teachers.filter(t => t.status === 'ACTIVE' || t.id === row?.teacher_user_id).map(t => <option key={t.id} value={t.id}>{t.name} · {t.email}</option>)}</Field>}
      <p>End this employee’s active course allocations before placing them on leave or marking them inactive. Past attendance and allocations are retained.</p>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save employee</button><button type="button" disabled={mutation.isPending} onClick={onClose}>Cancel</button></div>
    </WorkspaceForm></section>;
}

export function Pagination({ offset, total, setOffset, size = 50 }) {
  return <div className="teaching-actions"><button type="button" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - size))}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(offset + size, total)} of {total}</span><button type="button" disabled={offset + size >= total} onClick={() => setOffset(offset + size)}>Next</button></div>;
}
