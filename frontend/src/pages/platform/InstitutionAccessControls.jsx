import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTeachingMutation } from '../teacher/teachingQueries';
import { Field, MutationState } from '../teacher/TeachingUI';

export default function InstitutionAccessControls({ institution }) {
  const [action, setAction] = useState('');
  const [verification, setVerification] = useState(null);
  const mutation = useTeachingMutation();
  const cache = useQueryClient();
  async function submit(event) {
    event.preventDefault();
    try {
      if (action === 'archive' && !verification) {
        const result = await mutation.mutateAsync({ path: `/api/platform/institutions/${institution.id}/request-archive`, body: {} });
        setVerification(result.verification_id); return;
      }
      await mutation.mutateAsync(action === 'archive' ? { path: '/api/platform/institutions/confirm-archive', body: { verification_id: verification, code: new FormData(event.currentTarget).get('code') } } :
        { path: `/api/platform/institutions/${institution.id}/status`, method: 'PUT', body: { status: institution.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' } });
      setAction(''); setVerification(null);
      await cache.invalidateQueries({ queryKey: ['platform-institutions'] });
      await cache.invalidateQueries({ queryKey: ['platform-stats'] });
    } catch { /* Displayed below. */ }
  }
  if (institution.status === 'ARCHIVED') return <span>Archived · records retained</span>;
  return <><div className="teaching-actions"><button onClick={() => { setAction('status'); mutation.reset(); }}>{institution.status === 'ACTIVE' ? 'Suspend' : 'Reactivate'}</button><button onClick={() => { setAction('archive'); mutation.reset(); }}>Archive</button></div>
    {action && <form className="teaching-form" onSubmit={submit}><p>{action === 'archive' ? 'Archive this institution? All institution access will be disabled. Records are retained. An email verification code is required.' : 'Change access for this institution? All existing sessions will be invalidated.'}</p>
      {verification && <Field label="Email verification code" name="code" required pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" />}
      <MutationState mutation={mutation} message={verification ? 'Enter the code sent to your administrator email.' : ''} />
      <button disabled={mutation.isPending}>{action === 'archive' && !verification ? 'Send verification code' : 'Confirm change'}</button><button type="button" disabled={mutation.isPending} onClick={() => { setAction(''); setVerification(null); mutation.reset(); }}>Cancel</button></form>}
  </>;
}
