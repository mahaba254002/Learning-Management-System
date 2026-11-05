import { useState } from 'react';
import ModuleEditor from '../../components/common/ModuleEditor';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { MutationState, QueryState } from '../teacher/TeachingUI';

export default function InstitutionModules({ root }) {
  const query = useTeachingQuery(`${root}/modules`);
  return <section className="teaching-panel"><h2>Institution modules</h2><p>Select what this customer uses. Disabled modules keep their records and become available again when enabled.</p>
    <QueryState query={query} />{query.data && <Editor key={query.data.updated_at} data={query.data} root={root} />}</section>;
}

function Editor({ data, root }) {
  const [modules, setModules] = useState(data.modules);
  const mutation = useTeachingMutation();
  const disabled = Object.keys(modules).filter(key => data.modules[key] && !modules[key]);
  return <form onSubmit={async event => { event.preventDefault(); try { await mutation.mutateAsync({ path: `${root}/modules`, method: 'PUT', body: { modules, expected_updated_at: data.updated_at } }); } catch { /* Displayed below. */ } }}>
    <ModuleEditor value={modules} onChange={setModules} presets={data.presets} dependencies={data.dependencies} disabled={mutation.isPending} />
    {disabled.length > 0 && <p role="status">Saving disables {disabled.length} feature{disabled.length === 1 ? '' : 's'}. Affected users lose access immediately, including students when their portal is disabled. Existing records are retained.</p>}
    <MutationState mutation={mutation} />
    <button className="btn btn--primary" disabled={mutation.isPending || JSON.stringify(modules) === JSON.stringify(data.modules)}>{mutation.isPending ? 'Saving…' : 'Save institution modules'}</button>
  </form>;
}
