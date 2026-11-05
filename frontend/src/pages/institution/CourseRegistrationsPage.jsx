import { useState } from 'react';
import { useTeachingMutation,useTeachingQuery } from '../teacher/teachingQueries';
import { Field,PageHeading,MutationState,QueryState } from '../teacher/TeachingUI';
import { useAuth } from '../../context/useAuth';

export default function CourseRegistrationsPage(){
  const subjects=useTeachingQuery('/api/teaching/subjects');const[id,setId]=useState('');
  return <><PageHeading title="Course enrollment & completion">Register learners for individual offerings and approve final course outcomes. Credits are awarded only from released completion records.</PageHeading><QueryState query={subjects}/><Field label="Teaching offering" value={id} onChange={e=>setId(e.target.value)}><option value="">Choose a course / subject</option>{subjects.data?.map(s=><option key={s.id} value={s.id}>{s.name} · {s.class_name} · {s.academic_year}</option>)}</Field>{id&&<Registrations key={id} subject={subjects.data.find(s=>s.id===id)}/>}</>;
}
function Registrations({ subject }) {
  const root = `/api/institution/subjects/${subject.id}`;
  const query = useTeachingQuery(`${root}/registrations`);
  return <section className="teaching-panel">
    <h2>{subject.name}</h2>
    <p>{subject.registration_mode === 'COHORT' ? 'All learners in this group are enrolled.' : 'Select the learners taking this offering. Registration controls access to materials, assessments and subject attendance.'}</p>
    <QueryState query={query}/>
    {query.data && <div className="table-wrapper"><table className="data-table">
      <thead><tr><th>Learner</th><th>Registered</th><th>Final outcome</th><th>Approval</th></tr></thead>
      <tbody>{query.data.students.map(student => <RegistrationRow key={student.id} student={student} subject={subject} root={root}/>)}</tbody>
    </table></div>}
    <p>Approve only the institution’s verified final outcome. Assessment marks do not automatically imply course completion. Link catalogue courses in teaching setup first.</p>
  </section>;
}

function RegistrationRow({ student, subject, root }) {
  const { readOnly } = useAuth();
  const mutation = useTeachingMutation();
  const [outcome, setOutcome] = useState('');
  const [registrationEdit, setRegistrationEdit] = useState(null);
  const closed = subject.academic_year_status === 'CLOSED';
  const name = `${student.first_name} ${student.last_name}`;
  async function register(active) {
    if (mutation.isPending) return;
    setRegistrationEdit(active);
    try {
      await mutation.mutateAsync({ path: `${root}/registrations`, method: 'PUT', body: { student_id: student.id, active } });
    } catch { /* Show this learner's error below. */ }
    finally { setRegistrationEdit(null); }
  }
  async function complete() {
    if (mutation.isPending) return;
    try {
      await mutation.mutateAsync({ path: `${root}/completion`, method: 'PUT', body: { student_id: student.id, outcome, released: true, expected_updated_at: student.completion_updated_at } });
    } catch { /* Show this learner's error below. */ }
  }
  const approving = mutation.isPending && mutation.variables?.path.endsWith('/completion');
  return <tr>
    <td>{name}<small>{student.admission_number}{student.completion ? ` · Approved: ${student.completion}` : ''}</small></td>
    <td>{student.entry_issues?.map((issue, i) => <small key={i}>{issue}</small>)}
      <input type="checkbox" aria-label={`Register ${name}`} checked={registrationEdit ?? student.registered}
        disabled={readOnly || (!student.registered && student.entry_issues?.length > 0) || mutation.isPending || subject.registration_mode === 'COHORT' || closed}
        onChange={e => register(e.target.checked)}/>
    </td>
    <td><select aria-label={`Final outcome for ${name}`} value={outcome} onChange={e => setOutcome(e.target.value)} disabled={readOnly || !student.registered || closed || mutation.isPending}>
      <option value="">Choose verified outcome</option><option value="PASSED">Passed</option><option value="FAILED">Failed</option><option value="EXEMPT">Exempt</option>
    </select></td>
    <td><button type="button" disabled={readOnly || mutation.isPending || !outcome || !subject.catalogue_id || !student.registered || closed} aria-busy={approving} onClick={complete}>
      {approving ? `Releasing ${name}…` : 'Approve & release'}
    </button><MutationState mutation={mutation} message={`Course record saved for ${name}.`}/></td>
  </tr>;
}
