import { Field } from '../../pages/teacher/TeachingUI';

export default function GradingRulesEditor({rules,onChange}){
  const set=(key,value)=>onChange({...rules,[key]:value});
  const band=(index,key,value)=>set('bands',rules.bands.map((b,i)=>i===index?{...b,[key]:value}:b));
  return <section className="grading-policy-editor"><h3>Final grades, assessment weights & GPA</h3>
    <label className="academic-check"><input type="checkbox" checked={rules.enabled} onChange={e=>set('enabled',e.target.checked)}/>Enable numeric final grading for this institution</label>
    <p>Platform-controlled rules. Competency observations remain separate. An offering keeps its policy when its first final grade is approved; later changes apply to offerings that have not yet pinned a policy.</p>
    {rules.enabled&&<><div className="academic-config-grid">
      <Field label="Grading policy name / version" required maxLength={100} value={rules.name} onChange={e=>set('name',e.target.value)}/>
      <Field label="Final percentage calculation" value={rules.aggregation} onChange={e=>set('aggregation',e.target.value)}><option value="CATEGORY_WEIGHTS">Weighted assessment categories</option><option value="POINTS">All numeric points / all maxima</option></Field>
      {rules.aggregation==='CATEGORY_WEIGHTS'&&<><Field label="Within each category" value={rules.within_category} onChange={e=>set('within_category',e.target.value)}><option value="POINTS">Total points / total maxima</option><option value="MEAN_PERCENT">Equal assessment percentages</option></Field>{['ASSIGNMENT','COURSEWORK','EXAM'].map(k=><Field key={k} label={`${k} weight (%)`} type="number" min={0} max={100} step="0.01" required value={rules.weights[k]} onChange={e=>set('weights',{...rules.weights,[k]:Number(e.target.value)})}/>)}</>}
      <Field label="Pass percentage" type="number" min={0} max={100} step="0.01" required value={rules.pass_percentage} onChange={e=>set('pass_percentage',Number(e.target.value))}/>
      <Field label="Percentage decimal places" type="number" min={0} max={4} required value={rules.percentage_places} onChange={e=>set('percentage_places',Number(e.target.value))}/>
      <Field label="Rounding rule" value={rules.rounding} onChange={e=>set('rounding',e.target.value)}><option value="HALF_UP">Half up</option><option value="HALF_EVEN">Half even</option><option value="DOWN">Truncate</option></Field>
      <Field label="Grade and pass threshold basis" value={rules.grade_basis} onChange={e=>set('grade_basis',e.target.value)}><option value="RAW">Unrounded final percentage</option><option value="ROUNDED">Rounded final percentage</option></Field>
    </div><p>Category weights must total 100%. Every positive-weight category needs published numeric assessments and every contributing mark must be released. Missing marks stay incomplete.</p>
    <h4>Final grade bands</h4><p>Enter this institution’s approved thresholds. Include zero. No national grading scale is supplied.</p>
    {rules.bands.map((b,i)=><div className="academic-config-grid grading-band-row" key={i}><Field label={`Band ${i+1} minimum (%)`} type="number" min={0} max={100} step="0.01" required value={b.minimum} onChange={e=>band(i,'minimum',Number(e.target.value))}/><Field label={`Band ${i+1} label`} required maxLength={30} value={b.label} onChange={e=>band(i,'label',e.target.value)}/>{rules.gpa_enabled&&<Field label={`Band ${i+1} grade points`} type="number" min={0} max={rules.gpa_scale} step="0.01" required value={b.points??''} onChange={e=>band(i,'points',e.target.value===''?null:Number(e.target.value))}/>}<button type="button" onClick={()=>set('bands',rules.bands.filter((_,n)=>n!==i))}>Remove band {i+1}</button></div>)}
    <button type="button" disabled={rules.bands.length>=20} onClick={()=>set('bands',[...rules.bands,{minimum:0,label:'',points:null}])}>Add final grade band</button>
    <label className="academic-check"><input type="checkbox" checked={rules.gpa_enabled} onChange={e=>set('gpa_enabled',e.target.checked)}/>Enable credit-weighted GPA</label>
    {rules.gpa_enabled&&<div className="academic-config-grid"><Field label="GPA scheme name" required maxLength={80} value={rules.gpa_scheme} onChange={e=>set('gpa_scheme',e.target.value)}/><Field label="Maximum GPA / scale" type="number" min="0.01" max={100} step="0.01" required value={rules.gpa_scale} onChange={e=>set('gpa_scale',Number(e.target.value))}/><Field label="GPA decimal places" type="number" min={0} max={4} required value={rules.gpa_places} onChange={e=>set('gpa_places',Number(e.target.value))}/><Field label="Repeated catalogue courses in GPA" value={rules.repeats} onChange={e=>set('repeats',e.target.value)}><option value="ALL">All attempts, including failures</option><option value="LATEST">Latest academic attempt only</option><option value="BEST">Best grade points only</option></Field></div>}
    <p>GPA = Σ(grade points × attempted course credits) / Σ(attempted credits). Failed attempts count under the selected repeat rule. Exemptions and term sub-results are excluded. Enable course credits above and link positive catalogue credits before approval. Different GPA schemes are reported separately.</p>
    </>}
  </section>;
}
