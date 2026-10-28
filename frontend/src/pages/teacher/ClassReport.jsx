import { useTeachingQuery } from "./teachingQueries";
import { QueryState } from "./TeachingUI";

export default function ClassReport({ classId }) {
  const query = useTeachingQuery(`/api/teaching/classes/${classId}/report`, { refetchInterval: 30000 });
  return <section className="teaching-panel"><h2>Class teacher’s academic overview</h2><p>Marks across all teaching subjects. Unreleased marks remain private to staff. Refreshes every 30 seconds.</p><QueryState query={query} />
    {query.data?.students.map(student => <details key={student.id}><summary>{student.name} · {student.admission_number} · {student.marks.length} marked assessments</summary>
      {!student.marks.length ? <p>No marks recorded.</p> : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Subject / course</th><th>Assessment</th><th>Mark</th><th>Grade</th><th>Student visibility</th></tr></thead><tbody>{student.marks.map((mark, i) => <tr key={i}><td>{mark.subject}</td><td>{mark.assessment}</td><td>{mark.competency_label || `${mark.score} / ${mark.maximum}`}</td><td>{mark.grade || (mark.competency_label ? "Competency" : "Numeric marks")}</td><td>{mark.released ? "Released" : "Withheld"}</td></tr>)}</tbody></table></div>}
    </details>)}
  </section>;
}
