import PrerequisitesEditor from './PrerequisitesEditor';
import OfferingGradingPolicy from './OfferingGradingPolicy';
import { useState } from 'react';
import AcademicConfigurationEditor from '../../components/common/AcademicConfigurationEditor';
import { useTeachingMutation, useTeachingQuery } from '../teacher/teachingQueries';
import { MutationState, QueryState } from '../teacher/TeachingUI';

export default function InstitutionAcademicSetup({ root }) {
  const query = useTeachingQuery(`${root}/academic-configuration`);
  return <section className="teaching-panel"><h2>Academic configuration</h2><QueryState query={query} />{query.data && <Setup key={query.data.updated_at} initial={query.data} root={root} />}<OfferingGradingPolicy root={root}/><PrerequisitesEditor root={root}/></section>;
}
function Setup({ initial, root }) {
  const [value,setValue] = useState(initial);
  const mutation=useTeachingMutation();
  return <form onSubmit={async event => {event.preventDefault();try { await mutation.mutateAsync({path:`${root}/academic-configuration`,method:'PUT',body:{configuration:value.configuration,labels:value.labels,expected_updated_at:initial.updated_at}}); }catch{/* shown below */}}}>
    <AcademicConfigurationEditor value={value} onChange={setValue} disabled={mutation.isPending}/><p>Existing offerings keep their registration method. Existing assessments keep their method and rubric. Setup changes do not rewrite academic history.</p><MutationState mutation={mutation} message="Academic setup saved."/><button className="btn btn--primary" disabled={mutation.isPending}>Save academic setup</button>
  </form>;
}
