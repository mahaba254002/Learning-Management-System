import { useState } from 'react';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { Field, MutationState, PageHeading, QueryState } from '../teacher/TeachingUI';
import { Pagination } from './StaffDirectoryPage';

const today = () => new Date().toLocaleDateString('en-CA', { timeZone: 'Africa/Nairobi' });
const statuses = { PRESENT: 'Present', ABSENT: 'Absent', LATE: 'Late', LEAVE: 'On leave', OFF_DUTY: 'Off duty' };

export default function StaffAttendancePage() {
  const [day, setDay] = useState(today);
  const [department, setDepartment] = useState('');
  const [category, setCategory] = useState('');
  const [offset, setOffset] = useState(0);
  const [changes, setChanges] = useState({});
  const mutation = useTeachingMutation();
  const options = useTeachingQuery('/api/management/options');
  const query = useTeachingQuery(`/api/management/attendance?${new URLSearchParams({ day, offset, ...(department ? { department_id: department } : {}), ...(category ? { category } : {}) })}`, { refetchOnWindowFocus: false });
  const dirty = Object.keys(changes).length > 0;
  function update(row, values) {
    setChanges(previous => ({ ...previous, [row.staff.id]: { status: row.attendance?.status || '', note: row.attendance?.note || '', ...previous[row.staff.id], ...values } }));
  }
  async function save(event) {
    event.preventDefault();
    const entries = Object.entries(changes).filter(([, entry]) => entry.status).map(([staff_id, entry]) => ({ ...entry, staff_id, expected_updated_at: query.data.items.find(row => row.staff.id === staff_id)?.attendance?.updated_at || null }));
    if (!entries.length) return;
    try { await mutation.mutateAsync({ path: '/api/management/attendance', method: 'PUT', body: { day, entries } }); setChanges({}); } catch { /* Keep unsaved edits. */ }
  }
  return <div className="management-page"><PageHeading title="Staff attendance">Record teaching and non-teaching employees separately from student attendance. Unmarked employees remain unmarked.</PageHeading>
    <div className="management-filters"><Field label="Register date" type="date" value={day} max={today()} required disabled={dirty || mutation.isPending} onChange={event => { if (event.target.value) { setDay(event.target.value); setOffset(0); mutation.reset(); } }} />
      <Field label="Department" value={department} disabled={dirty || mutation.isPending} onChange={event => { setDepartment(event.target.value); setOffset(0); }}><option value="">All departments</option>{options.data?.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</Field>
      <Field label="Category" value={category} disabled={dirty || mutation.isPending} onChange={event => { setCategory(event.target.value); setOffset(0); }}><option value="">All employees</option><option value="TEACHING">Teaching</option><option value="NON_TEACHING">Non-teaching</option></Field></div>
    <QueryState query={options} /><QueryState query={query} /><MutationState mutation={mutation} message="Staff attendance saved." />
    {query.data && <form onSubmit={save} className="teaching-panel"><h2>Register · {day}</h2><p>{query.data.items.filter(row => row.attendance).length} of {query.data.items.length} employees on this page have saved attendance.</p>
      <div className="teaching-actions"><button type="button" disabled={mutation.isPending} onClick={() => { for (const row of query.data.items) if (!row.attendance && !changes[row.staff.id]?.status && row.staff.status !== 'INACTIVE' && (!row.staff.joined_on || row.staff.joined_on <= day)) update(row, { status: 'PRESENT' }); }}>Mark unrecorded employees on this page present</button></div>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Employee</th><th>Role</th><th>Attendance</th><th>Note</th></tr></thead><tbody>{query.data.items.map(row => {
        const entry = changes[row.staff.id] || row.attendance || { status: '', note: '' };
        const unavailable = (!row.attendance && row.staff.status === 'INACTIVE') || Boolean(row.staff.joined_on && row.staff.joined_on > day);
        return <tr key={row.staff.id}><td>{row.staff.first_name} {row.staff.last_name}<small>{row.staff.staff_number}</small></td><td>{row.staff.job_title}<small>{row.staff.category === 'TEACHING' ? 'Teaching' : 'Non-teaching'}</small></td>
          <td><select aria-label={`Attendance for ${row.staff.staff_number}`} value={entry.status} disabled={unavailable || mutation.isPending} onChange={event => update(row, { status: event.target.value })}><option value="" disabled>Unmarked</option>{Object.entries(statuses).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></td>
          <td><input aria-label={`Note for ${row.staff.staff_number}`} value={entry.note} maxLength={500} disabled={unavailable || mutation.isPending} onChange={event => update(row, { note: event.target.value })} /></td></tr>;
      })}</tbody></table></div>
      {!query.data.total && <p>No employees for this register. Add employees in the staff directory.</p>}
      {dirty && <p role="status">Save or discard changes before changing the register date, filters or page. Notes require an attendance status.</p>}
      <div className="teaching-actions"><button className="btn btn--primary" disabled={!dirty || mutation.isPending || Object.values(changes).some(entry => !entry.status)}>{mutation.isPending ? 'Saving…' : `Save ${Object.keys(changes).length} changes`}</button><button type="button" disabled={!dirty || mutation.isPending} onClick={() => { setChanges({}); mutation.reset(); query.refetch(); }}>Discard changes and reload</button></div>
      {!dirty && <Pagination offset={offset} total={query.data.total} setOffset={setOffset} size={100} />}
    </form>}
  </div>;
}
