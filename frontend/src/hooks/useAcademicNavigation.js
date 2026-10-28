import { useTeachingQuery } from '../pages/teacher/teachingQueries';
export function plural(value){return value.endsWith('s')?`${value}es`:`${value}s`;}
export function useAcademicNavigation(items){
  const query=useTeachingQuery('/api/institution/academic-configuration');const config=query.data;
  if(!config)return items;
  const labels=config.labels;
  return items.filter(item=>!item.path.endsWith('/academic-record')||config.credits_enabled).map(item=>{
    let label=item.label;
    if(item.path.endsWith('/classes'))label=item.path.startsWith('/teacher')?`My ${plural(labels.class_label).toLowerCase()}`:`${plural(labels.class_label)} & teaching`;
    if(item.path.endsWith('/students'))label=plural(labels.student_label);
    if(item.path.endsWith('/teachers'))label=plural(labels.teacher_label);
    if(item.path.endsWith('/subjects'))label=`My ${plural(labels.subject_label).toLowerCase()}`;
    if(item.path.endsWith('/scores'))label=config.assessment_policy==='COMPETENCY'?'Observations & feedback':'Assessment outcomes';
    if(item.path.endsWith('/grades'))label='Outcomes & feedback';
    return {...item,label};
  });
}
