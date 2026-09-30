import { useSearchParams } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import { attendanceSummary } from "./learningFormat";

export default function StudentAttendancePage() {
  const subjects = useTeachingQuery("/api/student/subjects");
  const attendance = useTeachingQuery("/api/student/attendance");
  const [params, setParams] = useSearchParams();
  const selected = params.get("subject") || "";
  const records = attendance.data || [];
  const filtered = records.filter(r => !selected || (selected === "class" ? !r.subject_id : r.subject_id === selected));
  return <><PageHeading title="My attendance">Your recorded attendance for each subject and the daily class register.</PageHeading><QueryState query={subjects} /><QueryState query={attendance} />
    {subjects.data && attendance.data && <>
      <p className="teaching-notice">Attendance rate = present + late, divided by present + late + absent. Excused sessions are excluded. Unrecorded sessions are not counted as absent.</p>
      <div className="teaching-grid">{subjects.data.map(s => {
        const counts = attendanceSummary(records.filter(r => r.subject_id === s.id));
        return <article className="teaching-panel" key={s.id}><h2>{s.name}</h2><p className="teaching-muted">{s.class_name} · {s.academic_year}</p><div className="stat-card__value">{counts.percentage === null ? "—" : `${counts.percentage}%`}</div><p>{counts.total ? `${counts.total} recorded sessions` : "No attendance recorded"}</p><div className="student-attendance-summary"><span>{counts.PRESENT} present</span><span>{counts.LATE} late</span><span>{counts.ABSENT} absent</span><span>{counts.EXCUSED} excused</span></div></article>;
      })}</div>
      <section className="teaching-panel"><h2>Attendance history</h2><Field label="Filter register" value={selected} onChange={e => setParams(e.target.value ? { subject: e.target.value } : {})}><option value="">All registers</option><option value="class">Daily class register</option>{subjects.data.map(s => <option key={s.id} value={s.id}>{s.name} · {s.class_name}</option>)}</Field>
        {!filtered.length ? <Empty>No attendance records for this selection.</Empty> : <div className="table-wrapper"><table className="data-table"><thead><tr><th>Date</th><th>Register</th><th>Status</th><th>Note</th></tr></thead><tbody>{filtered.map(r => <tr key={r.id}><td>{r.day}</td><td>{r.subject_id ? subjects.data.find(s => s.id === r.subject_id)?.name || "Subject" : "Daily class register"}</td><td>{r.status.toLowerCase()}</td><td>{r.note || "—"}</td></tr>)}</tbody></table></div>}
      </section>
    </>}
  </>;
}
