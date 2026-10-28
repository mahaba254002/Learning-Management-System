import { useState } from 'react';
import { useAuth } from '../../context/useAuth';
import { Field,QueryState,MutationState } from './TeachingUI';
import { useTeachingQuery,useTeachingMutation } from './teachingQueries';

export default function FinalGradesPanel({subject}){
  const {user,readOnly}=useAuth();const[period,setPeriod]=useState('');
  const periods=useTeachingQuery(`/api/teaching/subjects/${subject.id}/periods`);
  const query=useTeachingQuery(`/api/teaching/subjects/${subject.id}/final-grades${period?'?period_id='+period:''}`);
  const mutation=useTeachingMutation();
  async function approve(row,released){try{await mutation.mutateAsync({path:`/api/institution/subjects/${subject.id}/final-grades`,method:'PUT',body:{student_id:row.id,period_id:period||null,expected_digest:row.source_digest,expected_updated_at:row.updated_at,released}});}catch{/* shown below */}}
  return <section className="teaching-panel"><h2>Final grades & approval</h2><p>Calculated from this offering’s published numeric assessments. Only institution administrators can approve and release final grades. Full-offering approval also updates linked course completion and credits.</p>
    <Field label="Final grading scope" value={period} onChange={e=>{setPeriod(e.target.value);mutation.reset();}}><option value="">Full offering / annual final</option>{periods.data?.map(p=><option key={p.id} value={p.id}>{p.name} · period result only</option>)}</Field><button type="button" disabled={query.isFetching} onClick={()=>{query.refetch();mutation.reset();}}>Refresh final-grade calculation</button><QueryState query={query}/><QueryState query={periods}/><MutationState mutation={mutation} message="Final grade updated."/>
    {query.data&&!query.data.policy.enabled&&<p>Platform admin has not enabled numeric final grading for this offering. Competency outcomes remain in the assessment records.</p>}
    {query.data?.policy.enabled&&<><p><strong>{query.data.policy.name}</strong> · {query.data.pinned?'Policy pinned to this offering':'Policy will be pinned at first approval'} · Pass: {query.data.policy.pass_percentage}% · Grade basis: {query.data.policy.grade_basis.toLowerCase()}</p>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>Learner</th><th>Calculated result</th><th>Readiness / approval</th><th>Actions</th></tr></thead><tbody>{query.data.students.map(row=><tr key={row.id}><td>{row.name}<small>{row.admission_number}</small></td><td>{row.result?<><strong>{row.result.percentage}% · {row.result.grade}</strong><p>{row.result.passed?'Pass':'Fail'}{row.result.points!==null?` · ${row.result.points} grade points`:''}</p>{row.result.contributions.map(c=><small key={c.category}>{c.category}: {c.percentage}% × {c.weight}% = {c.contribution} points<br/></small>)}</>:'Incomplete'}</td><td>{row.stale?'Source changed — review required':row.released?'Approved & released':row.approved?'Withheld':'Not approved'}{row.issues.map((issue,i)=><p key={i}>{issue}</p>)}</td><td>{user.role==='INSTITUTION_ADMIN'&&!readOnly&&<><button type="button" disabled={!row.ready||mutation.isPending||subject.academic_year_status==='CLOSED'} onClick={()=>approve(row,true)}>Approve & release {row.name}</button>{row.released&&<button type="button" disabled={mutation.isPending||subject.academic_year_status==='CLOSED'} onClick={()=>approve(row,false)}>Withhold final grade for {row.name}</button>}</>}</td></tr>)}</tbody></table></div>
    </>}
  </section>;
}
