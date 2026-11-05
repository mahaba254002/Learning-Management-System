import MaterialIcon from "../../components/common/MaterialIcon";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import WorkspaceForm from '../../components/common/WorkspaceForm';
import { useTeachingMutation,useTeachingQuery } from '../teacher/teachingQueries';
import { Field,MutationState,PageHeading,QueryState } from '../teacher/TeachingUI';

export default function AcademicStructurePage(){
  const config=useTeachingQuery('/api/institution/academic-configuration');
  const query=useTeachingQuery('/api/institution/academic-structure');
  const levels=useTeachingQuery('/api/institution/levels');
  const [strandsFor,setStrandsFor]=useState(null);
  const [kind,setKind]=useState('levels');
  const [editing,setEditing]=useState(null);
  const [programme,setProgramme]=useState('');
  const mutation=useTeachingMutation();
  const kinds=config.data?.structure==='PROGRAMME'?[['departments','Departments'],['programmes','Programmes'],['levels','Study levels'],['catalogue','Course catalogue']]:[['levels','Study levels'],['catalogue',`${config.data?.labels.subject_label || 'Subject'} catalogue`]];
  async function submit(event){event.preventDefault();const form=event.currentTarget;const values=Object.fromEntries(new FormData(form));for(const key of ['department_id','programme_id','level_id','award','credits','education_level_id'])if(values[key]==='')values[key]=null;
    try{await mutation.mutateAsync({path:`/api/institution/academic-structure/${kind}${editing ? `/${editing.id}` : ""}`,method:editing?"PUT":"POST",body:{...values,...(editing?{expected_updated_at:editing.updated_at}:{})}});form.reset();setProgramme('');setEditing(null);}catch{/* shown below */}}
  const nameOf=(rows,id)=>rows?.find(r=>r.id===id)?.name || '—';
  return <><PageHeading title="Academic structure">Build the institution’s catalogue and study hierarchy. Connect it to yearly teaching groups and allocations.</PageHeading><QueryState query={config}/><QueryState query={query}/><MutationState mutation={mutation} message="Academic record created."/>
    {config.data && <div className="academic-path">{config.data.structure==='PROGRAMME'?'Department / Programme / Study level / Cohort / Course offering':'Study level / Learning group / Subject / learning area'}<Link to="/institution/classes">Manage teaching allocations <MaterialIcon name="arrow_forward" /></Link></div>}
    <div className="academic-tabs" aria-label="Structure section">{kinds.map(([key,label])=><button type="button" key={key} aria-pressed={kind===key} onClick={()=>{setKind(key);setProgramme('');setEditing(null);mutation.reset();}}>{label}</button>)}</div>
    <section className="teaching-panel"><h2>{editing?"Edit":"Add"} {kinds.find(([key])=>key===kind)?.[1].toLowerCase()}</h2><WorkspaceForm key={`${kind}:${editing?.id || "new"}`} onSubmit={submit} className="teaching-form">
      <Field label="Code" name="code" defaultValue={editing?.code ?? ""} required maxLength={30} pattern="[A-Za-z0-9._/-]+"/><Field label="Name" name="name" defaultValue={editing?.name ?? ""} required maxLength={100}/>
      {kind==='programmes'&&<><Field label="Department (optional)" name="department_id" defaultValue={editing?.department_id ?? ""}><option value="">No department</option>{query.data?.departments.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</Field><Field label="Award / qualification (optional)" name="award" defaultValue={editing?.award ?? ""} maxLength={100}/></>}
      {['levels','catalogue'].includes(kind)&&config.data?.structure==='PROGRAMME'&&<Field label="Programme" name="programme_id" value={programme} onChange={e=>setProgramme(e.target.value)}><option value="">Institution-wide</option>{query.data?.programmes.map(r=><option key={r.id} value={r.id}>{r.code} · {r.name}</option>)}</Field>}
      {kind!=='departments'&&levels.data?.length>1&&<Field label="Education level" name="education_level_id" defaultValue={editing?.education_level_id ?? ""}><option value="">Not set</option>{levels.data.map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</Field>}
      {kind!=='departments'&&levels.data?.length===1&&<input type="hidden" name="education_level_id" value={editing ? (editing.education_level_id ?? "") : levels.data[0].id}/>}
      {kind==='levels'&&<Field label="Sequence" name="position" defaultValue={editing?.position ?? 1} type="number" min="1" max="100" required/>}
      {kind==='catalogue'&&<><Field label="Study level (optional)" name="level_id" defaultValue={editing?.level_id ?? ""}><option value="">Any level</option>{query.data?.levels.filter(r=>(r.programme_id || '')===programme).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</Field>{config.data?.credits_enabled&&<Field label="Course credits (optional)" name="credits" defaultValue={editing?.credits ?? ""} type="number" min="0" max="1000" step="0.01"/>}</>}
      <button className="btn btn--primary" disabled={mutation.isPending}>{editing?"Save changes":"Create record"}</button>{editing&&<button type="button" onClick={()=>{setEditing(null);setProgramme('');}}>Cancel edit</button>}</WorkspaceForm></section>
    {query.data&&<section className="teaching-panel"><h2>{kinds.find(([key])=>key===kind)?.[1]}</h2><div className="table-wrapper" tabIndex={0} role="region" aria-label="Academic catalogue"><table className="data-table"><thead><tr><th>Code</th><th>Name</th><th>Programme / department</th><th>Detail</th><th>Action</th></tr></thead><tbody>{query.data[kind].map(r=><tr key={r.id}><td>{r.code}</td><td>{r.name}</td><td>{nameOf(kind==='programmes'?query.data.departments:query.data.programmes,r.department_id || r.programme_id)}</td><td>{r.award || (r.credits!=null?`${r.credits} credits`:r.position?`Level ${r.position}`:'—')}</td><td><div className="teaching-actions"><button type="button" onClick={()=>{setEditing(r);setProgramme(r.programme_id || '');}}>Edit record</button>{kind==='catalogue'&&<button type="button" onClick={()=>setStrandsFor(r)}>Strands</button>}</div></td></tr>)}</tbody></table></div>{query.data[kind].length===0&&<p>No records yet. Add the institution’s actual structure above.</p>}</section>}
    {kind==='catalogue'&&strandsFor&&<StrandsPanel key={strandsFor.id} course={strandsFor} onClose={()=>setStrandsFor(null)}/>}
  </>;
}

// CBE strands and sub-strands of one learning area. Assessments can point at them.
function StrandsPanel({course,onClose}){
  const root=`/api/institution/academic-structure/catalogue/${course.id}/strands`;
  const query=useTeachingQuery(root);
  const mutation=useTeachingMutation();
  const [editing,setEditing]=useState(null);
  const [generation,setGeneration]=useState(0);
  const top=query.data?.filter(s=>!s.parent_id)||[];
  async function save(event){event.preventDefault();const values=Object.fromEntries(new FormData(event.currentTarget));values.parent_id=values.parent_id||null;
    try{await mutation.mutateAsync(editing?{path:`/api/institution/academic-structure/strands/${editing.id}`,method:'PUT',body:{...values,expected_updated_at:editing.updated_at}}:{path:root,body:values});setEditing(null);setGeneration(g=>g+1);}catch{/* shown below */}}
  const ordered=top.flatMap(s=>[s,...(query.data||[]).filter(c=>c.parent_id===s.id)]);
  return <section className="teaching-panel"><h2>Strands for {course.code} · {course.name}</h2><QueryState query={query}/><MutationState mutation={mutation} message="Strand saved."/>
    <WorkspaceForm key={`${generation}:${editing?.id||'new'}`} className="teaching-form" onSubmit={save}>
      <Field label="Code" name="code" required maxLength={30} pattern="[A-Za-z0-9._/-]+" defaultValue={editing?.code||''}/><Field label="Name" name="name" required maxLength={160} defaultValue={editing?.name||''}/>
      <Field label="Part of strand (optional)" name="parent_id" defaultValue={editing?.parent_id||''}><option value="">Top-level strand</option>{top.filter(s=>s.id!==editing?.id).map(s=><option key={s.id} value={s.id}>{s.code} · {s.name}</option>)}</Field>
      <Field label="Order" name="position" type="number" min="1" max="1000" required defaultValue={editing?.position??(top.length+1)}/>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>{editing?'Save strand':'Add strand'}</button>{editing&&<button type="button" onClick={()=>setEditing(null)}>Cancel edit</button>}<button type="button" onClick={onClose}>Close</button></div>
    </WorkspaceForm>
    {query.data&&<div className="table-wrapper"><table className="data-table"><thead><tr><th>Code</th><th>Name</th><th>Action</th></tr></thead><tbody>{ordered.map(s=><tr key={s.id}><td>{s.parent_id?'— ':''}{s.code}</td><td>{s.name}</td><td><button type="button" onClick={()=>setEditing(s)}>Edit</button></td></tr>)}</tbody></table></div>}
    {query.data?.length===0&&<p>No strands yet. Add strands, then sub-strands under them.</p>}
  </section>;
}
