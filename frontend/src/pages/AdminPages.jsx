import WorkspaceAccessButton from "../components/common/WorkspaceAccessButton";
import LearningSettings from "./institution/LearningSettings";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { useTeachingMutation, useTeachingQuery } from './teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from './teacher/TeachingUI';
import './teacher/TeachingWorkspace.css';
import './platform/PlatformDashboardPage.css';
import './platform/PlatformOperations.css';

function Pages({ offset, total, setOffset }) {
  return <div className="teaching-actions"><button disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{total ? offset + 1 : 0}–{Math.min(offset + 50, total)} of {total}</span><button disabled={offset + 50 >= total} onClick={() => setOffset(offset + 50)}>Next</button></div>;
}

// ACTIVE -> SUSPENDED -> DEACTIVATED -> ARCHIVED, one step at a time, each reversible.
const NEXT_STATUS = { ACTIVE: ['SUSPENDED', 'DEACTIVATED'], SUSPENDED: ['ACTIVE', 'DEACTIVATED'], DEACTIVATED: ['ACTIVE', 'ARCHIVED'], ARCHIVED: ['DEACTIVATED'] };
const STATUS_ACTIONS = { ACTIVE: 'Reactivate', SUSPENDED: 'Suspend', DEACTIVATED: 'Deactivate', ARCHIVED: 'Archive' };
const STATUS_HELP = { ACTIVE: 'They can sign in again.', SUSPENDED: 'Sign-in is blocked until reactivated.', DEACTIVATED: 'Use this when someone leaves. Their records are kept.', ARCHIVED: 'The account is hidden from lists and stays read-only.' };

// Show system values like INSTITUTION_ADMIN as 'Institution admin'.
const words = value => value.charAt(0) + value.slice(1).toLowerCase().replaceAll('_', ' ');

export function AdminUsersPage({ platform = false, studentsOnly = false }) {
  const scope = platform ? 'platform' : 'institution';
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [role, setRole] = useState(studentsOnly ? 'STUDENT' : '');
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const [archived, setArchived] = useState(false);
  const [reason, setReason] = useState('');
  const query = useTeachingQuery(`/api/${scope}/users?${new URLSearchParams({ search, offset, ...(role ? { role } : {}), ...(archived ? { include_archived: 'true' } : {}) })}`);
  const mutation = useTeachingMutation();
  const reset = useTeachingMutation();
  async function change() {
    try { await mutation.mutateAsync({ path: `/api/${scope}/users/${selected.user.id}/status`, method: 'PUT', body: { status: selected.target, reason } }); setSelected(null); setReason(''); } catch { /* Displayed below. */ }
  }
  return <><PageHeading title={studentsOnly ? 'Students' : 'User accounts'}>Search accounts and manage access. Suspending an account preserves its records.</PageHeading>
    {studentsOnly && <p><Link to="/institution/classes">Manage class enrollment and student details</Link></p>}
    <div className="teaching-toolbar"><Field label="Search name, username, email or student ID" value={search} onChange={e => { setSearch(e.target.value); setOffset(0); }} />
      {!studentsOnly && <Field label="Role" value={role} onChange={e => { setRole(e.target.value); setOffset(0); }}><option value="">All roles</option>{['INSTITUTION_ADMIN', 'TEACHER', 'STAFF', 'STUDENT', ...(platform ? ['PLATFORM_ADMIN'] : [])].map(r => <option key={r} value={r}>{r.replaceAll('_', ' ')}</option>)}</Field>}
      <label className="teaching-checkbox"><input type="checkbox" checked={archived} onChange={e => { setArchived(e.target.checked); setOffset(0); }} />Show archived accounts</label></div>
    <QueryState query={query} /><MutationState mutation={mutation} message="Account access updated." />
    {selected && <section className="teaching-panel" aria-label="Confirm account access change"><h2>{STATUS_ACTIONS[selected.target]} {selected.user.first_name} {selected.user.last_name}?</h2><p>{STATUS_HELP[selected.target]} Existing sessions end immediately.</p>
      {['DEACTIVATED', 'ARCHIVED'].includes(selected.target) && <Field label="Reason" value={reason} onChange={e => setReason(e.target.value)} required minLength={3} maxLength={300} />}
      <div className="teaching-actions"><button disabled={mutation.isPending || (['DEACTIVATED', 'ARCHIVED'].includes(selected.target) && reason.trim().length < 3)} onClick={change}>Confirm change</button><button disabled={mutation.isPending} onClick={() => setSelected(null)}>Cancel</button></div></section>}
    {platform && <MutationState mutation={reset} message={reset.data?.message || 'Reset link sent.'} />}
    {query.data && <><div className="table-wrapper"><table className="data-table"><thead><tr><th>Name / username</th><th>Role</th><th>Status</th><th>Access</th><th>Workspace</th></tr></thead><tbody>{query.data.items.map(u => <tr key={u.id}><td>{u.first_name} {u.last_name}<div className="teaching-muted">{u.username}</div></td><td>{words(u.role)}</td><td>{words(u.status)}{u.must_change_password && <div className="teaching-muted">Password change required</div>}</td><td>{u.id !== user.id && u.role !== 'PLATFORM_ADMIN' && (platform || u.role !== 'INSTITUTION_ADMIN') && u.status !== 'INVITED' && <select aria-label={`Change status for ${u.first_name} ${u.last_name}`} value="" disabled={mutation.isPending} onChange={e => { mutation.reset(); setReason(''); setSelected({ user: u, target: e.target.value }); }}><option value="">Change status…</option>{(NEXT_STATUS[u.status] || []).map(s => <option key={s} value={s}>{STATUS_ACTIONS[s]}</option>)}</select>}</td><td><WorkspaceAccessButton userId={u.id} role={u.role} disabled={u.status !== 'ACTIVE'} />{platform && u.role !== 'PLATFORM_ADMIN' && u.status === 'ACTIVE' && u.email && !u.email.endsWith('@deleted.invalid') && <button type='button' className='table-action-link' disabled={reset.isPending} onClick={() => reset.mutate({ path: `/api/platform/users/${u.id}/password-reset`, body: { reason: '' } })}>Send reset link</button>}</td></tr>)}</tbody></table></div>{!query.data.total && <p>No matching accounts.</p>}<Pages offset={offset} total={query.data.total} setOffset={setOffset} /></>}
  </>;
}

export function AdminAuditPage({ platform = false }) {
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState('');
  const query = useTeachingQuery(`/api/${platform ? 'platform' : 'institution'}/audit-logs?${new URLSearchParams({ offset, ...(action ? { action } : {}) })}`);
  return <><PageHeading title="Administrative audit trail">Administrative changes recorded since audit logging was introduced. Times use your local timezone.</PageHeading><QueryState query={query} />
    <div className="teaching-toolbar"><Field label="Action type" value={action} onChange={e => { setAction(e.target.value); setOffset(0); }}><option value="">All actions</option>{query.data?.action_types?.map(type => <option key={type} value={type}>{type.replaceAll('_', ' ')}</option>)}</Field><button className="operations-secondary" onClick={() => { setAction(''); setOffset(0); }}>Clear filter</button></div>
    {query.data && <section className="operations-card"><div className="table-wrapper"><table className="data-table"><thead><tr><th>When</th><th>Action</th><th>Actor</th><th>IP address</th><th>Details</th></tr></thead><tbody>{query.data.items.map(r => <tr key={r.id}><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.action.replaceAll('_', ' ')}</td><td>{r.actor_name || r.actor_id}<small>{r.actor_email}</small></td><td>{r.ip_address || 'Not recorded'}</td><td><details><summary>View details</summary><dl className="audit-details"><dt>Event ID</dt><dd>{r.id}</dd><dt>Actor ID</dt><dd>{r.actor_id}</dd><dt>Target</dt><dd>{r.target_id}</dd><dt>Institution</dt><dd>{r.institution_id || 'Platform'}</dd><dt>Request</dt><dd>{r.request_method ? `${r.request_method} ${r.request_path}` : 'Not recorded'}</dd><dt>Detail</dt><dd>{r.detail || 'No additional detail'}</dd></dl></details></td></tr>)}</tbody></table></div>{!query.data.total && <p className="empty-state">No matching audit events.</p>}<Pages offset={offset} total={query.data.total} setOffset={setOffset} /></section>}
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
    <LearningSettings />
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
