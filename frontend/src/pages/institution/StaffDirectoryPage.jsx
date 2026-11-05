import { useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useAuth } from '../../context/useAuth';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import '../../components/common/ModuleEditor.css';

const labels = value => value.replaceAll('_', ' ').toLowerCase();
const DETAIL_FIELDS = ['department_id', 'user_id', 'email', 'phone', 'joined_on', 'gender', 'date_of_birth', 'qualification', 'specialization'];

export default function StaffDirectoryPage({ readOnly = false }) {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [department, setDepartment] = useState('');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const [adding, setAdding] = useState(false);
  const [account, setAccount] = useState(null);
  const options = useTeachingQuery('/api/management/options');
  const query = useTeachingQuery(`/api/management/staff?${new URLSearchParams({ search, offset, ...(category ? { category } : {}), ...(status ? { status } : {}), ...(department ? { department_id: department } : {}) })}`);
  const filters = setter => event => { setter(event.target.value); setOffset(0); };
  const open = (row, panel) => { setEditing(panel === 'edit' ? row : null); setAccount(panel === 'account' ? row : null); setAdding(false); };
  return <div className="management-page"><PageHeading title="Staff directory">{readOnly ? 'Everyone employed by the institution.' : 'Every employee, with or without a sign-in account.'}</PageHeading>
    {!readOnly && <div className="management-links"><Link to="/institution/departments">Departments and faculties</Link><Link to="/institution/allocations">Teaching allocations</Link></div>}
    <QueryState query={options} />
    <div className="management-filters"><Field label="Search staff" value={search} onChange={filters(setSearch)} /><Field label="Staff category" value={category} onChange={filters(setCategory)}><option value="">All categories</option><option value="TEACHING">Teaching</option><option value="NON_TEACHING">Non-teaching</option></Field>
      <Field label="Employment status" value={status} onChange={filters(setStatus)}><option value="">All statuses</option>{['ACTIVE', 'ON_LEAVE', 'INACTIVE'].map(s => <option key={s} value={s}>{labels(s)}</option>)}</Field>
      <Field label="Department" value={department} onChange={filters(setDepartment)}><option value="">All departments</option>{options.data?.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Field></div>
    {!readOnly && <button type="button" className="btn btn--primary" onClick={() => { setAdding(true); setEditing(null); setAccount(null); }}>Add employee</button>}
    {!readOnly && (adding || editing) && options.data && <StaffForm key={editing?.id || 'new'} row={editing} options={options.data} onClose={() => { setAdding(false); setEditing(null); }} />}
    {!readOnly && account && options.data && <AccountPanel key={account.id} row={account} options={options.data} onClose={() => setAccount(null)} />}
    <QueryState query={query} />{query.data && <section className="teaching-panel"><h2>{query.data.total} employee{query.data.total === 1 ? '' : 's'}</h2><div className="table-wrapper"><table className="data-table"><thead><tr><th>Employee</th><th>Category / role</th><th>Department</th><th>Status</th><th>Sign-in</th>{!readOnly && <th>Action</th>}</tr></thead><tbody>{query.data.items.map(row => <tr key={row.id}>
      <td>{row.first_name} {row.last_name}<small>{row.staff_number}</small></td><td>{labels(row.category)}<small>{row.job_title} · {labels(row.employment_type)}</small></td><td>{options.data?.departments.find(d => d.id === row.department_id)?.name || 'Unassigned'}</td><td>{labels(row.status)}</td>
      <td>{row.account ? <>{labels(row.account.status)}<small>{row.account.setup_pending ? 'Password not set yet' : row.account.username}</small></> : 'No account'}</td>
      {!readOnly && <td><div className="teaching-actions"><button type="button" onClick={() => open(row, 'edit')}>Edit</button><button type="button" onClick={() => open(row, 'account')}>Sign-in</button></div></td>}
    </tr>)}</tbody></table></div>{!query.data.total && <p>No employees match these filters.</p>}<Pagination offset={offset} total={query.data.total} setOffset={setOffset} /></section>}
  </div>;
}

function StaffForm({ row, options, onClose }) {
  const mutation = useTeachingMutation();
  const [category, setCategory] = useState(row?.category || 'TEACHING');
  const [login, setLogin] = useState('NONE');
  const [created, setCreated] = useState(null);
  async function save(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    for (const key of DETAIL_FIELDS) values[key] = values[key] || null;
    if (!row) values.login = login;
    try {
      const result = await mutation.mutateAsync({ path: `/api/management/staff${row ? `/${row.id}` : ''}`, method: row ? 'PUT' : 'POST', body: { ...values, ...(row ? { expected_updated_at: row.updated_at, user_id: row.user_id } : {}) } });
      if (result.credentials) setCreated(result.credentials); else onClose();
    } catch { /* Keep inputs. */ }
  }
  if (created) return <section className="teaching-panel"><h2>Employee added</h2><Credentials result={created} /><button type="button" className="btn btn--primary" onClick={onClose}>Done</button></section>;
  const accounts = options.accounts.filter(a => a.role === (category === 'TEACHING' ? 'TEACHER' : 'STAFF') && (a.status === 'ACTIVE' || a.id === row?.user_id));
  return <section className="teaching-panel"><h2>{row ? 'Edit employee' : 'Add employee'}</h2><MutationState mutation={mutation} />
    <WorkspaceForm className="teaching-form" onSubmit={save}>
      <Field label="Staff number" name="staff_number" required maxLength={40} pattern="[A-Za-z0-9._/-]+" defaultValue={row?.staff_number || ''} />
      <Field label="First name" name="first_name" required maxLength={100} defaultValue={row?.first_name || ''} /><Field label="Last name" name="last_name" required maxLength={100} defaultValue={row?.last_name || ''} />
      <Field label="Category" name="category" value={category} onChange={event => setCategory(event.target.value)} disabled={Boolean(row?.user_id)}><option value="TEACHING">Teaching</option><option value="NON_TEACHING">Non-teaching</option></Field>
      {row?.user_id && <input type="hidden" name="category" value={category} />}
      <Field label="Job title" name="job_title" required maxLength={120} defaultValue={row?.job_title || ''} />
      <Field label="Department" name="department_id" defaultValue={row?.department_id || ''}><option value="">Unassigned</option>{options.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Field>
      <Field label="Employment type" name="employment_type" defaultValue={row?.employment_type || 'FULL_TIME'}>{['FULL_TIME', 'PART_TIME', 'CONTRACT', 'VOLUNTEER'].map(value => <option key={value} value={value}>{labels(value)}</option>)}</Field>
      <Field label="Status" name="status" defaultValue={row?.status || 'ACTIVE'}>{['ACTIVE', 'ON_LEAVE', 'INACTIVE'].map(value => <option key={value} value={value}>{labels(value)}</option>)}</Field>
      <Field label="Date joined" name="joined_on" type="date" defaultValue={row?.joined_on || ''} />
      <Field label="Email" name="email" type="email" maxLength={255} required={login !== 'NONE'} defaultValue={row?.email || ''} /><Field label="Phone (optional)" name="phone" maxLength={50} defaultValue={row?.phone || ''} />
      <Field label="Gender (optional)" name="gender" defaultValue={row?.gender || ''}><option value="">Not recorded</option>{['FEMALE', 'MALE', 'OTHER', 'PREFER_NOT_TO_SAY'].map(value => <option key={value} value={value}>{labels(value)}</option>)}</Field>
      <Field label="Date of birth (optional)" name="date_of_birth" type="date" defaultValue={row?.date_of_birth || ''} />
      <Field label="Qualification (optional)" name="qualification" maxLength={255} defaultValue={row?.qualification || ''} /><Field label="Specialisation (optional)" name="specialization" maxLength={255} defaultValue={row?.specialization || ''} />
      {!row && <Field label="Sign-in account" value={login} onChange={event => setLogin(event.target.value)} description="A link lets the person choose their own password. It works once and expires in 72 hours.">
        <option value="NONE">No account, record only</option><option value="LINK">Create account and email a set-password link</option><option value="TEMPORARY_PASSWORD">Create account with a temporary password</option></Field>}
      {!row && login === 'NONE' && accounts.length > 0 && <Field label="Or link an existing account (optional)" name="user_id" defaultValue=""><option value="">No account</option>{accounts.map(a => <option key={a.id} value={a.id}>{a.name} · {a.email}</option>)}</Field>}
      <p>Hand over this person’s teaching allocations before placing them on leave or marking them inactive. Past records are kept.</p>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save employee</button><button type="button" disabled={mutation.isPending} onClick={onClose}>Cancel</button></div>
    </WorkspaceForm></section>;
}

function Credentials({ result }) {
  if (result.temporary_password) return <div role="status"><p>Share this temporary password privately. It expires in 7 days and must be changed at first sign-in.</p><p>Username: <code>{result.username}</code></p><p>Temporary password: <code>{result.temporary_password}</code></p></div>;
  if (result.emailed) return <p role="status">A set-password link was emailed to them. It expires in {result.link_expires_in_hours} hours.</p>;
  return <div role="status"><p>The email could not be sent. Give this link to the person directly. It works once and expires in {result.link_expires_in_hours} hours.</p><p><code className="credential-value">{result.setup_link}</code></p></div>;
}

const NEXT_STATUS = { ACTIVE: ['SUSPENDED', 'DEACTIVATED'], SUSPENDED: ['ACTIVE', 'DEACTIVATED'], DEACTIVATED: ['ACTIVE', 'ARCHIVED'], ARCHIVED: ['DEACTIVATED'] };
const STATUS_HELP = { SUSPENDED: 'Temporarily blocks sign-in.', DEACTIVATED: 'They have left. Their record is kept.', ARCHIVED: 'Hidden from lists and read-only.', ACTIVE: 'Restores sign-in.' };

function AccountPanel({ row, options, onClose }) {
  const mutation = useTeachingMutation();
  const { workspace } = useAuth();
  const [credentials, setCredentials] = useState(null);
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  const account = row.account;
  async function issue(delivery) {
    try { setCredentials(await mutation.mutateAsync({ path: `/api/management/staff/${row.id}/account`, body: { delivery } })); } catch { /* Shown below. */ }
  }
  async function changeStatus(event) {
    event.preventDefault();
    try { await mutation.mutateAsync({ path: `/api/institution/users/${account.id}/status`, method: 'PUT', body: { status: target, reason } }); onClose(); } catch { /* Shown below. */ }
  }
  return <section className="teaching-panel"><h2>Sign-in for {row.first_name} {row.last_name}</h2><MutationState mutation={mutation} />
    {credentials && <Credentials result={credentials} />}
    {!account && <>{!row.email ? <p>Add an email address to this employee before creating a sign-in.</p> : workspace ? <p>Return to your own workspace to create sign-in details.</p> :
      <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={mutation.isPending} onClick={() => issue('LINK')}>Create account and email link</button><button type="button" disabled={mutation.isPending} onClick={() => issue('TEMPORARY_PASSWORD')}>Create with temporary password</button></div>}</>}
    {account && <>
      <p>{labels(account.role)} account · {account.username} · {labels(account.status)}</p>
      {account.setup_pending && account.status === 'ACTIVE' && !workspace && <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={() => issue('LINK')}>Send a new set-password link</button><button type="button" disabled={mutation.isPending} onClick={() => issue('TEMPORARY_PASSWORD')}>Issue a temporary password</button></div>}
      <form className="teaching-form" onSubmit={changeStatus}>
        <Field label="Change account status" value={target} onChange={e => setTarget(e.target.value)} description={STATUS_HELP[target]}><option value="">Keep as {labels(account.status)}</option>{(NEXT_STATUS[account.status] || []).map(s => <option key={s} value={s}>{labels(s)}</option>)}</Field>
        {['DEACTIVATED', 'ARCHIVED'].includes(target) && <Field label="Reason" value={reason} onChange={e => setReason(e.target.value)} required minLength={3} maxLength={300} />}
        <button type="submit" disabled={!target || mutation.isPending}>Apply</button>
      </form>
      {account.role === 'STAFF' && <Permissions row={row} labels={options.permissions} />}
    </>}
    <div className="teaching-actions"><button type="button" onClick={onClose}>Close</button></div>
  </section>;
}

function Permissions({ row, labels: names }) {
  const query = useTeachingQuery(`/api/management/staff/${row.id}/permissions`);
  const mutation = useTeachingMutation();
  async function save(event) {
    event.preventDefault();
    const permissions = Object.keys(names).filter(key => event.currentTarget.elements[key]?.checked);
    try { await mutation.mutateAsync({ path: `/api/management/staff/${row.id}/permissions`, method: 'PUT', body: { permissions } }); } catch { /* Shown below. */ }
  }
  return <><h3>What they can do</h3><QueryState query={query} /><MutationState mutation={mutation} message="Permissions saved." />
    {query.data && <form className="teaching-form" key={query.data.granted.join(',')} onSubmit={save}>
      {Object.entries(names).map(([key, label]) => <label key={key} className="teaching-checkbox"><input type="checkbox" name={key} defaultChecked={query.data.granted.includes(key)} />{label}</label>)}
      <button type="submit" disabled={mutation.isPending}>Save permissions</button></form>}</>;
}

export function Pagination({ offset, total, setOffset, size = 50 }) {
  return <div className="teaching-actions"><button type="button" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - size))}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(offset + size, total)} of {total}</span><button type="button" disabled={offset + size >= total} onClick={() => setOffset(offset + size)}>Next</button></div>;
}
