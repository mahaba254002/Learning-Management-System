import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../../api/client';
import { useAuth } from '../../context/useAuth';
import { useTeachingQuery } from '../teacher/teachingQueries';
import { Field, PageHeading, QueryState } from '../teacher/TeachingUI';
import { downloadCsv, studentColumns } from './importFiles';
import WorkspaceForm from '../../components/common/WorkspaceForm';

export default function StudentImportPage() {
  const { readOnly } = useAuth();
  const queryClient = useQueryClient();
  const classes = useTeachingQuery('/api/teaching/classes');
  const [classId, setClassId] = useState('');
  const [rows, setRows] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function load(file) {
    setPreview(null); setRows(null); setError('');
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { setError('Choose a file smaller than 2 MB.'); return; }
    setBusy(true);
    try { const data = await apiRequest(`/api/institution/student-imports/parse?filename=${encodeURIComponent(file.name)}`, { method: 'POST', rawBody: file }); setRows(data.rows); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function review(event) {
    event.preventDefault(); setBusy(true); setError(''); setPreview(null);
    try { setPreview(await apiRequest('/api/institution/student-imports/preview', { method: 'POST', body: { class_id: classId, rows } })); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function execute() {
    setBusy(true); setError('');
    try {
      setResult(await apiRequest('/api/institution/student-imports/commit', { method: 'POST', body: { class_id: classId, rows, preview_token: preview.preview_token } }));
      setPreview(null); setRows(null); await queryClient.invalidateQueries();
    } catch (failure) { setError(failure.message); setPreview(null); }
    finally { setBusy(false); }
  }
  return <><PageHeading title="Import students">Upload, review and create student accounts in one class. Existing accounts are never changed by an import.</PageHeading>
    <QueryState query={classes} />{error && <p role="alert" className="form-error">{error}</p>}
    {result ? <section className="teaching-panel"><h2>{result.created} students imported</h2><p>Each account must change its temporary password at first sign-in. Download these credentials now and distribute them privately. They are not stored in readable form and cannot be downloaded again.</p>
      <div className="teaching-actions"><button type="button" className="btn btn--primary" onClick={() => downloadCsv('student-access.csv', ['Name', 'Admission number', 'Login method', 'Login identity', 'Temporary password'], result.credentials.map(r => [r.name, r.admission_number, r.login_method, r.login_identity, r.temporary_password]))}>Download private credentials</button>
      <button type="button" onClick={() => { setResult(null); setClassId(''); }}>Clear credentials and import another file</button></div></section> : <>
      <section className="teaching-panel"><h2>1. Prepare the file</h2><p>Use UTF-8 CSV or one Excel worksheet (.xlsx), at most 500 students. Keep student IDs as text to preserve leading zeros. Choose EMAIL or STUDENT_ID for each account. Student login IDs must be unique across the platform; admission numbers must be unique within your institution.</p>
        <button type="button" onClick={() => downloadCsv('student-import-template.csv', studentColumns, [['Mary', 'Example', 'ADM-001', 'STUDENT_ID', 'SCHOOL-001', '', ''], ['John', 'Example', 'ADM-002', 'EMAIL', '', 'john@example.test', '']])}>Download example CSV template</button><p className="teaching-muted">Replace the example students before importing. Passwords are generated securely; do not add a password column.</p></section>
      <section className="teaching-panel"><h2>2. Choose class and file</h2><WorkspaceForm onSubmit={review}><fieldset className="workspace-form-fields" disabled={busy || readOnly}>
        <Field label="Destination class" required value={classId} onChange={e => { setClassId(e.target.value); setPreview(null); }}><option value="">Choose class and year</option>{classes.data?.filter(c => c.academic_year_status !== 'CLOSED').map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>
        <Field label="Student file" type="file" accept=".csv,.xlsx" onChange={e => load(e.target.files[0])} />
        {rows && <p>{rows.length} rows read. No accounts have been created.</p>}<button className="btn btn--primary" disabled={!rows || !classId || busy}>{busy ? 'Working…' : 'Validate and preview'}</button>
      </fieldset></WorkspaceForm></section>
      {preview && <section className="teaching-panel"><h2>3. Review {preview.class_name} · {preview.academic_year}</h2>
        {preview.errors.length > 0 ? <><p role="alert">Fix these issues in the original file, then upload it again. No students were imported.</p><button type="button" onClick={() => downloadCsv('student-import-errors.csv', ['Spreadsheet row', 'Issue'], preview.errors.map(e => [e.row, e.message]))}>Download error report</button><ul>{preview.errors.map((e, i) => <li key={i}>Row {e.row}: {e.message}</li>)}</ul></> : <><p>{preview.students.length} valid new accounts. Confirm the names, admission numbers and login identities below.</p>
          <div className="table-wrapper" tabIndex={0} role="region" aria-label="Student import preview"><table className="data-table"><thead><tr><th>Name</th><th>Admission number</th><th>Login method</th><th>Login identity</th></tr></thead><tbody>{preview.students.map((s, i) => <tr key={i}><td>{s.first_name} {s.last_name}</td><td>{s.admission_number}</td><td>{s.login_method}</td><td>{s.login_method === 'EMAIL' ? s.email : s.login_id}</td></tr>)}</tbody></table></div>
          <button type="button" className="btn btn--primary" disabled={busy || readOnly} onClick={execute}>{busy ? 'Creating accounts…' : `Confirm import of ${preview.students.length} students`}</button></>}
      </section>}
    </>}
  </>;
}
