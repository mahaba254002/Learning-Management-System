import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../../api/client';
import PasswordInput from './PasswordInput';

export default function SessionRecovery({ user, onRecovered, onLogout }) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const dialog = useRef(null);
  useEffect(() => {
    const node = dialog.current;
    node.showModal();
    return () => node.close();
  }, []);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    const path = user.role === 'STUDENT' ? '/api/auth/student/login' : user.role === 'TEACHER' ? '/api/auth/teacher/login' : '/api/auth/login';
    const identity = user.role === 'STUDENT' && user.student_login_method === 'STUDENT_ID' ? { student_id: user.student_login_id } : { email: user.email };
    try {
      const data = await apiRequest(path, { method: 'POST', body: { ...identity, password }, workspace: false });
      if (data.user.id !== user.id) throw new Error('Sign in to the original account to recover this workspace.');
      onRecovered(data.user);
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} onCancel={event => event.preventDefault()} aria-labelledby="session-recovery-title" className="teaching-panel session-recovery">
    <h2 id="session-recovery-title">Sign in to continue</h2><p>Your session ended. Your open work is still on this screen. Sign in again, then retry saving.</p>
    <form onSubmit={submit}><p>{user.email || user.student_login_id}</p><label htmlFor="session-password">Password</label><PasswordInput id="session-password" value={password} onChange={e => setPassword(e.target.value)} required autoFocus autoComplete="current-password" />
      {error && <p role="alert" className="form-error">{error}</p>}<div className="teaching-actions"><button className="btn btn--primary" disabled={busy}>{busy ? 'Signing in…' : 'Continue my session'}</button><button type="button" disabled={busy} onClick={onLogout}>Sign out</button></div></form>
  </dialog>;
}
