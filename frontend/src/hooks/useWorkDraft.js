import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../api/client';
import { useAuth } from '../context/useAuth';

// Draft data lives on the server, never in persistent browser storage on shared school devices.
export function useWorkDraft(kind, resource, initial = {}) {
  const { readOnly, user, workspace } = useAuth();
  const [extraHeaders] = useState(() => ({ 'X-Draft-User': user.id, 'X-Draft-Actor': workspace?.actor?.id || user.id }));
  const [isBlocked, setIsBlocked] = useState(false);
  const [value, setValue] = useState(initial);
  const [status, setStatus] = useState('Loading recovery draft…');
  const [ready, setReady] = useState(false);
  const version = useRef(0);
  const revision = useRef(0);
  const persisted = useRef(0);
  const chain = useRef(Promise.resolve());
  const latest = useRef(value);
  const blocked = useRef(false);
  const path = `/api/drafts/${kind}/${encodeURIComponent(resource)}`;
  useEffect(() => {
    let active = true;
    apiRequest(path, { extraHeaders }).then(data => {
      if (!active) return;
      version.current = data.version;
      if (data.data && Object.keys(data.data).length) {
        setValue(data.data); latest.current = data.data; setStatus('Recovered unfinished work. Review it before saving.');
      } else setStatus('Recovery is ready. Changes will be saved privately.');
      setReady(true);
    }).catch(error => { if (active) setStatus(`Recovery unavailable: ${error.message}. Reload before editing.`); });
    return () => { active = false; };
  }, [path, extraHeaders]);

  const persist = useCallback((snapshot, number) => {
    chain.current = chain.current.catch(() => {}).then(async () => {
      if (blocked.current) return;
      try {
        const result = await apiRequest(path, { method: 'PUT', extraHeaders, body: { data: snapshot, expected_version: version.current } });
        version.current = result.version; persisted.current = number;
        setStatus(number === revision.current ? 'Recovery draft saved privately. Changes are not published or submitted until you save or submit them.' : 'Saving recovery draft…');
      } catch (error) {
        if (error.status === 409) { blocked.current = true; setIsBlocked(true); }
        setStatus(`Recovery draft not saved: ${error.message}`);
      }
    });
    return chain.current;
  }, [path, extraHeaders]);
  const change = useCallback(next => {
    if (readOnly || !ready || blocked.current) return;
    const updated = typeof next === 'function' ? next(latest.current) : next;
    latest.current = updated; revision.current += 1; setValue(updated); setStatus('Saving recovery draft…');
  }, [readOnly, ready]);
  useEffect(() => {
    if (!ready || readOnly || revision.current === persisted.current) return;
    const timer = setTimeout(() => persist(latest.current, revision.current), 600);
    return () => clearTimeout(timer);
  }, [value, ready, readOnly, persist]);
  useEffect(() => {
    const warn = event => { if (revision.current !== persisted.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', warn);
    return () => { window.removeEventListener('beforeunload', warn); };
  }, []);
  // Flush on route changes too; queued saves use captured identities and never publish the draft.
  useEffect(() => () => {
    if (!readOnly && revision.current !== persisted.current) persist(latest.current, revision.current);
  }, [persist, readOnly]);
  useEffect(() => {
    const recovered = () => {
      if (!readOnly && revision.current !== persisted.current) persist(latest.current, revision.current);
    };
    window.addEventListener('skynet:session-restored', recovered);
    return () => window.removeEventListener('skynet:session-restored', recovered);
  }, [persist, readOnly]);
  const clear = useCallback(async () => {
    latest.current = {}; revision.current += 1; setValue({});
    await persist({}, revision.current);
    if (persisted.current === revision.current) setStatus('Saved. Recovery draft cleared.');
  }, [persist]);
  return { value, change, clear, status, ready, blocked: isBlocked };
}
