import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useTeachingMutation, useTeachingQuery } from './teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from './teacher/TeachingUI';
import './teacher/TeachingWorkspace.css';
import './platform/PlatformDashboardPage.css';

function Pages({ offset, total, setOffset }) {
  return <div className="teaching-actions"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(offset + 50, total)} of {total}</span><button disabled={offset + 50 >= total} onClick={() => setOffset(offset + 50)}>Next</button></div>;
}

export function AdminUsersPage({ platform = false, studentsOnly = false }) {
  const scope = platform ? 'platform' : 'institution';
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState(studentsOnly ? 'STUDENT' : '');
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const query = useTeachingQuery(`/api/${scope}/users?${new URLSearchParams({ search, offset, ...(role ? { role } : {}) })}`);
  const mutation = useTeachingMutation();
  async function change() {
    try { await mutation.mutateAsync({ path: `/api/${scope}/users/${selected.id}/status`, method: 'PUT', body: { status: selected.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' } }); setSelected(null); } catch { /* Displayed below. */ }
  }
  return <><PageHeading title={studentsOnly ? 'Students' : 'User accounts'}>Search accounts and manage access. Suspending an account preserves its records.</PageHeading>
    {studentsOnly && <p><Link to="/institution/classes">Manage class enrollment and student details</Link></p>}
    <div className="teaching-toolbar"><Field label="Search name or username" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} />
      {!studentsOnly && <Field label="Role" value={role} onChange={e => { setRole(e.target.value); setOffset(0); }}><option value="">All roles</option>{['INSTITUTION_ADMIN', 'TEACHER', 'STUDENT', ...(platform ? ['PLATFORM_ADMIN'] : [])].map(r => <option key={r} value={r}>{r.replaceAll('_', ' ')}</option>)}</Field>}</div>
    <QueryState query={query} /><MutationState mutation={mutation} message="Account access updated." />
    {selected && <section className="teaching-panel" aria-label="Confirm account access change"><h2>{selected.status === 'ACTIVE' ? 'Suspend' : 'Reactivate'} {selected.first_name} {selected.last_name}?</h2><p>Existing sessions will be invalidated. The person will need to sign in again after reactivation.</p><div className="teaching-actions"><button disabled={mutation.isPending} onClick={change}>Confirm change</button><button disabled={mutation.isPending} onClick={() => setSelected(null)}>Cancel</button></div></section>}
    {query.data && <><div className="table-wrapper"><table className="data-table"><thead><tr><th>Name / username</th><th>Role</th><th>Status</th><th>Access</th></tr></thead><tbody>{query.data.items.map(u => <tr key={u.id}><td>{u.first_name} {u.last_name}<div className="teaching-muted">{u.username}</div></td><td>{u.role.replaceAll('_', ' ')}</td><td>{u.status}{u.must_change_password && <div className="teaching-muted">Password change required</div>}</td><td>{u.id !== user.id && u.role !== 'PLATFORM_ADMIN' && (platform || u.role !== 'INSTITUTION_ADMIN') && u.status !== 'INVITED' && <button disabled={mutation.isPending} onClick={() => { mutation.reset(); setSelected(u); }}>{u.status === 'ACTIVE' ? 'Suspend' : 'Reactivate'}</button>}</td></tr>)}</tbody></table></div>{!query.data.total && <p>No matching accounts.</p>}<Pages offset={offset} total={query.data.total} setOffset={setOffset} /></>}
  </>;
}

export function AdminAuditPage({ platform = false }) {
  const [offset, setOffset] = useState(0);
  const query = useTeachingQuery(`/api/${platform ? 'platform' : 'institution'}/audit-logs?offset=${offset}`);
  return <><PageHeading title="Administrative audit trail">Administrative changes recorded since audit logging was introduced. Times use your local timezone.</PageHeading><QueryState query={query} />
    {query.data && <><div className="table-wrapper"><table className="data-table"><thead><tr><th>When</th><th>Action</th><th>Actor</th><th>Target</th><th>Details</th></tr></thead><tbody>{query.data.items.map(r => <tr key={r.id}><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.action.replaceAll('_', ' ')}</td><td>{r.actor_id}</td><td>{r.target_id}</td><td>{r.detail || '—'}</td></tr>)}</tbody></table></div>{!query.data.total && <p>No administrative changes recorded yet.</p>}<Pages offset={offset} total={query.data.total} setOffset={setOffset} /></>}
  </>;
}

export function InstitutionSettingsPage() {
  const query = useTeachingQuery('/api/institution/settings');
  const mutation = useTeachingMutation();
  async function save(event) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.currentTarget));
    for (const key of ['address', 'official_email', 'phone', 'website']) body[key] = body[key].trim() || null;
    try { await mutation.mutateAsync({ path: '/api/institution/settings', method: 'PUT', body }); } catch { /* Displayed below. */ }
  }
  return <><PageHeading title="Institution settings">Manage your institution’s official contact information.</PageHeading><QueryState query={query} /><MutationState mutation={mutation} message="Institution settings saved." />
    {query.data && <section className="teaching-panel"><p>Institution code: {query.data.code} · {query.data.status}</p><form className="teaching-form" onSubmit={save}>
      <Field label="Institution name" name="name" required maxLength={255} defaultValue={query.data.name} /><Field label="Country" name="country" required maxLength={100} defaultValue={query.data.country} />
      <Field label="Address" name="address" maxLength={500} defaultValue={query.data.address || ''} /><Field label="Official email" name="official_email" type="email" maxLength={255} defaultValue={query.data.official_email || ''} />
      <Field label="Phone" name="phone" maxLength={50} defaultValue={query.data.phone || ''} /><Field label="Website" name="website" type="url" maxLength={255} defaultValue={query.data.website || ''} />
      <button className="btn btn--primary" disabled={mutation.isPending}>{mutation.isPending ? 'Saving…' : 'Save settings'}</button></form></section>}
  </>;
}

export function PlatformUsagePage() {
  const query = useTeachingQuery('/api/platform/usage');
  return <><PageHeading title="Platform usage">Current records across all institutions.</PageHeading><QueryState query={query} />{query.data && <div className="stat-cards">{Object.entries(query.data).map(([key, value]) => <div className="stat-card" key={key}><p className="stat-card__value">{value}</p><p className="stat-card__label">{key}</p></div>)}</div>}</>;
}

export function AdminAccountPage() {
  const { user } = useAuth();
  return <><PageHeading title="Account & security">Your administrator account.</PageHeading><section className="teaching-panel"><dl><dt>Name</dt><dd>{user.first_name} {user.last_name}</dd><dt>Username</dt><dd>{user.username}</dd><dt>Email</dt><dd>{user.email || 'Not provided'}</dd><dt>Role</dt><dd>{user.role.replaceAll('_', ' ')}</dd></dl><Link className="btn btn--primary" to="/change-password">Change password</Link></section></>;
}
