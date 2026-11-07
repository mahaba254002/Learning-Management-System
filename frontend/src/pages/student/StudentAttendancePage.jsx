import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../records/Records.css";

const pct = cell => cell?.percent === null || cell?.percent === undefined ? "—" : `${cell.percent}%`;

export default function StudentAttendancePage() {
  const subjects = useTeachingQuery("/api/student/subjects");
  const attendance = useTeachingQuery("/api/student/attendance");
  const [periodId, setPeriodId] = useState("");
  const summary = useTeachingQuery(`/api/student/attendance/summary${periodId ? `?period_id=${periodId}` : ""}`);
  const [params, setParams] = useSearchParams();
  const selected = params.get("subject") || "";
  const records = attendance.data || [];
  const filtered = records.filter(r => !selected || (selected === "class" ? !r.subject_id : r.subject_id === selected));
  const data = summary.data;
  return <><PageHeading title="My attendance">Your attendance for each subject and the daily class register, by term or semester.</PageHeading>
    <QueryState query={subjects} /><QueryState query={attendance} /><QueryState query={summary} />
    {data && <section className="teaching-panel" aria-labelledby="attendance-rates">
      <h2 id="attendance-rates">Attendance rate{data.label ? ` · ${data.label}` : ""}</h2>
      {data.periods.length > 0 && <Field label="Term or semester" value={periodId || data.period_id || ""} onChange={e => setPeriodId(e.target.value)}>
        {!data.period_id && <option value="">Whole year</option>}{data.periods.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
      </Field>}
      <p className="teaching-muted">Present and late count as attended. Arriving close to the end of a lesson counts as absent unless your teacher accepted a reason. Excused sessions are left out.</p>
      {!data.rows.length ? <Empty>You are not in a class yet.</Empty> : <div className="table-wrapper"><table className="data-table">
        <thead><tr><th>Register</th><th className="records-num">Attended</th><th className="records-num">Missed</th><th className="records-num">Excused</th><th className="records-num">Rate</th></tr></thead>
        <tbody>{data.rows.map(r => <tr key={r.key}><td>{r.label}</td><td className="records-num">{r.attended}</td><td className="records-num">{r.missed}</td><td className="records-num">{r.excused}</td>
          <td className="records-num"><span className={`records-percent${r.percent !== null && r.percent < 75 ? " records-percent--low" : ""}`}>{pct(r)}</span></td></tr>)}
          <tr><td><strong>All subjects</strong></td><td className="records-num">{data.overall.attended}</td><td className="records-num">{data.overall.missed}</td><td className="records-num">{data.overall.excused}</td><td className="records-num"><strong>{pct(data.overall)}</strong></td></tr>
        </tbody></table></div>}
    </section>}
    {subjects.data && attendance.data && <section className="teaching-panel"><h2>Attendance history</h2><Field label="Filter register" value={selected} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">All registers</option><option value="class">Daily class register</option>{subjects.data.map(s => <option key={s.id} value={s.id}>{s.name} · {s.class_name}</option>)}</Field>
      {!filtered.length ? <Empty>No attendance records for this selection.</Empty> : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Date</th><th>Register</th><th>Status</th><th>Note</th></tr></thead><tbody>{filtered.map(r => <tr key={r.id}><td>{r.day}</td><td>{r.subject_id ? subjects.data.find(s => s.id === r.subject_id)?.name || "Subject" : "Daily class register"}</td><td>{r.status.toLowerCase()}{r.arrived_at ? ` at ${r.arrived_at.slice(0, 5)}` : ""}{r.outcome === "MISSED" && r.status === "LATE" ? " (counted absent)" : ""}</td><td>{r.note || "—"}</td></tr>)}</tbody></table></div>}
    </section>}
  </>;
}
