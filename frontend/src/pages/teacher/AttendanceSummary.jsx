import { useState } from "react";
import { useTeachingQuery } from "./teachingQueries";
import { Empty, Field, QueryState } from "./TeachingUI";
import "../records/Records.css";

export function Percent({ cell }) {
  if (!cell || cell.percent === null || cell.percent === undefined) return <span className="teaching-muted">—</span>;
  const low = cell.percent < 75;
  return <span className={`records-percent${low ? " records-percent--low" : ""}`} title={`${cell.attended} attended, ${cell.missed} missed, ${cell.excused} excused`}>{cell.percent}%</span>;
}

/** Attendance percentages per student for one class, per subject and term or semester. */
export default function AttendanceSummary({ classes, initial }) {
  const [classId, setClassId] = useState(initial || "");
  const [periodId, setPeriodId] = useState("");
  const chosen = classId || initial || "";
  const query = useTeachingQuery(chosen ? `/api/attendance/summary?class_id=${chosen}${periodId ? `&period_id=${periodId}` : ""}` : null);
  const data = query.data;
  return <section className="teaching-panel" aria-labelledby="attendance-percentages">
    <h2 id="attendance-percentages">Attendance percentages</h2>
    <p className="teaching-muted">Present and late count as attended. Late within the cut-off before the lesson ends counts as absent unless a reason was accepted. Excused sessions are left out.</p>
    <div className="teaching-toolbar">
      <Field label="Class" value={chosen} onChange={e => { setClassId(e.target.value); setPeriodId(""); }}>
        <option value="">Choose a class</option>{classes.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </Field>
      {data?.periods?.length > 0 && <Field label="Term or semester" value={periodId || data.period_id || ""} onChange={e => setPeriodId(e.target.value)}>
        {!data.period_id && <option value="">Whole year</option>}{data.periods.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </Field>}
    </div>
    <QueryState query={query} />
    {data && (!data.rows.length ? <Empty>No students in this class.</Empty> : <>
      <p className="teaching-muted">{data.label}{data.start ? ` · ${data.start} to ${data.end}` : ""}</p>
      <div className="table-wrapper"><table className="data-table records-table">
        <thead><tr><th>Student</th>{data.columns.map(c => <th key={c.key} className="records-num">{c.label}</th>)}{data.columns.some(c => c.key !== "class") && <th className="records-num">All subjects</th>}</tr></thead>
        <tbody>{data.rows.map(r => <tr key={r.student_id}><td>{r.name}<div className="teaching-muted">{r.admission_number}</div></td>
          {data.columns.map(c => <td key={c.key} className="records-num"><Percent cell={r.cells[c.key]} /></td>)}
          {data.columns.some(c => c.key !== "class") && <td className="records-num"><Percent cell={r.subjects} /></td>}</tr>)}</tbody>
      </table></div>
      <p className="teaching-muted">Below 75% is highlighted.</p>
    </>)}
  </section>;
}
