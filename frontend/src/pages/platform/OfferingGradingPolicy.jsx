import { useState } from 'react';
import { Field,QueryState,MutationState } from '../teacher/TeachingUI';
import { useTeachingQuery,useTeachingMutation } from '../teacher/teachingQueries';

export default function OfferingGradingPolicy({root}){
  const[search,setSearch]=useState(''),[selected,setSelected]=useState(''),[confirmation,setConfirmation]=useState('');
  const query=useTeachingQuery(`${root}/grading-offerings?search=${encodeURIComponent(search)}`);const mutation=useTeachingMutation();
  const offering=query.data?.items.find(s=>s.id===selected);
  return <details className="teaching-panel"><summary>Apply revised grading rules to an existing offering</summary><p>Save the institution policy above first. This action replaces the offering’s pinned policy and withholds its final grades and linked completion records until institution admin reviews and releases them again. Issued documents stay unchanged; revoke incorrect documents separately. Closed academic years cannot be changed.</p>
    <Field label="Search offerings for policy revision" value={search} onChange={e=>{setSearch(e.target.value);setSelected('');setConfirmation('');}}/><QueryState query={query}/>
    <Field label="Offering to receive revised grading rules" value={selected} onChange={e=>{setSelected(e.target.value);setConfirmation('');mutation.reset();}}><option value="">Choose an offering (first 100 matching)</option>{query.data?.items.map(s=><option key={s.id} value={s.id}>{s.name} · {s.group} · {s.year} · {s.policy_name}</option>)}</Field>
    {offering&&<><Field label={`Type ${offering.name} to confirm policy revision`} value={confirmation} onChange={e=>setConfirmation(e.target.value)}/><button type="button" disabled={confirmation!==offering.name||mutation.isPending} onClick={async()=>{try{await mutation.mutateAsync({path:`${root}/grading-offerings/${offering.id}`,method:'PUT',body:{confirmation,expected_subject_updated_at:offering.updated_at,expected_institution_updated_at:query.data.institution_updated_at}});setConfirmation('');}catch{/* shown below */}}}>Apply current policy & require grade review</button></>}
    <MutationState mutation={mutation} message="Policy applied. Institution admin must review and release final results again."/><button type="button" onClick={()=>query.refetch()}>Refresh offering policies</button>
  </details>;
}
