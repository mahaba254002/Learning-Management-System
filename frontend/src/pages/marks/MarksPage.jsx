import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../records/Records.css";
import "./Marks.css";

const fmt = value => value === null || value === undefined ? "" : Number(value).toLocaleString("en-KE", { maximumFractionDigits: 2 });

async function download(path, filename) {
  const blob = await apiRequest(path, { responseType: "blob" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

async function readFile(file) {
  return apiRequest(`/api/marks/parse?filename=${encodeURIComponent(file.name)}`, { method: "POST", rawBody: file });
}

function DownloadButton({ path, filename, children }) {
  const [state, setState] = useState("");
  return <><button className="btn" type="button" disabled={state === "busy"} onClick={async () => {
    setState("busy");
    try { await download(path, filename); setState(""); } catch (e) { setState(e.message); }
  }}>{state === "busy" ? "Preparing…" : children}</button>{state && state !== "busy" && <span className="form-error" role="alert">{state}</span>}</>;
}

function Problems({ rows }) {
  const bad = rows.filter(r => r.problems.length);
  if (!bad.length) return null;
  return <div className="table-wrapper"><table className="data-table"><thead><tr><th className="records-num">Row</th><th>Admission number</th><th>Problem</th></tr></thead>
    <tbody>{bad.slice(0, 100).map(r => <tr key={r.row}><td className="records-num">{r.row}</td><td>{r.admission_number}</td><td>{r.problems.join("; ")}</td></tr>)}</tbody></table></div>;
}

function ClassUpload({ classId, periodId, titles }) {
  const mutation = useTeachingMutation();
  const queryClient = useQueryClient();
  const [table, setTable] = useState(null);
  const [meta, setMeta] = useState({ title: "", kind: "EXAM", max_score: "100" });
  const [error, setError] = useState("");
  const preview = mutation.data && !mutation.data.saved ? mutation.data : null;
  const send = (commit, data = table) => mutation.mutateAsync({ path: `/api/marks/classes/${classId}/exam-import`, body: { period_id: periodId, ...meta, max_score: meta.max_score || "100", ...data, commit } });
  async function choose(event) {
    setError(""); mutation.reset(); setTable(null);
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!meta.title.trim()) { setError("Name the exam first, for example End of term exam."); return; }
    try { const data = await readFile(file); setTable(data); await send(false, data); } catch (e) { if (!mutation.isError) setError(e.message); }
  }
  return <section className="teaching-panel marks-upload" aria-labelledby="class-upload"><h2 id="class-upload">Upload a class marksheet for one exam</h2>
    <p className="teaching-muted">Excel or CSV: an admission_number column and one column per subject, named as in Skynet. Other columns such as name or total are ignored. Leave a cell blank, or write ABS, when there is no mark.</p>
    <div className="records-filters">
      <Field label="Exam name" value={meta.title} maxLength={200} list="exam-titles" onChange={e => setMeta({ ...meta, title: e.target.value })} placeholder="End of term exam" />
      <datalist id="exam-titles">{titles.map(t => <option key={t} value={t} />)}</datalist>
      <Field label="Type" value={meta.kind} onChange={e => setMeta({ ...meta, kind: e.target.value })}><option value="EXAM">Exam</option><option value="COURSEWORK">Continuous assessment (CAT)</option><option value="ASSIGNMENT">Assignment</option></Field>
      <Field label="Out of" type="number" min="1" max="10000" value={meta.max_score} onChange={e => setMeta({ ...meta, max_score: e.target.value })} description="Used only when the exam is new" />
    </div>
    <div className="records-actions">
      <DownloadButton path={`/api/marks/classes/${classId}/template?period_id=${periodId}`} filename="class-marks-template.xlsx">Download blank marksheet</DownloadButton>
      <label className="btn">Choose file<input type="file" accept=".xlsx,.csv" hidden onChange={choose} /></label>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <MutationState mutation={mutation} message={mutation.data?.saved ? `Saved ${mutation.data.to_save} marks.` : "Checked."} />
    {preview && <>
      <ul>{preview.subjects.map(s => <li key={s.column}>{s.subject}: {s.marks} marks to save{s.existing_assessment ? ", into the existing exam" : `, new exam out of ${fmt(s.max_score)}`}</li>)}</ul>
      {preview.ignored_columns.length > 0 && <p className="teaching-muted">Ignored columns: {preview.ignored_columns.join(", ")}</p>}
      <Problems rows={preview.rows} />
      <button className="btn btn--primary" type="button" disabled={Boolean(preview.errors) || !preview.to_save || mutation.isPending}
        onClick={async () => { try { await send(true); queryClient.invalidateQueries(); } catch { /* Shown above. */ } }}>{preview.to_save ? `Save ${preview.to_save} marks` : "Nothing new to save"}</button>
    </>}
  </section>;
}

function Sheet({ data }) {
  if (!data.rows.length) return <Empty>No students in this class.</Empty>;
  return <div className="table-wrapper"><table className="data-table marks-sheet">
    <thead><tr><th className="records-num">Pos.</th><th className="marks-sticky">Student</th>{data.subjects.map(s => <th key={s.id} colSpan={2}>{s.name}</th>)}<th className="records-num">Mean %</th><th className="records-num">Points</th><th>Grade</th></tr></thead>
    <tbody>{data.rows.map(r => <tr key={r.student_id}><td className="records-num">{r.position ?? ""}</td>
      <td className="marks-sticky">{r.name}<div className="teaching-muted">{r.admission_number}</div></td>
      {data.subjects.map(s => { const c = r.cells[s.id]; return [<td key={`${s.id}p`} className="records-num" title={c.note}>{fmt(c.percent)}</td>, <td key={`${s.id}g`} className="marks-grade">{c.grade || ""}</td>]; })}
      <td className="records-num">{fmt(r.mean)}</td><td className="records-num">{fmt(r.mean_points)}</td><td>{r.mean_grade || ""}</td></tr>)}</tbody>
  </table></div>;
}

function ClassMarksheet({ classes }) {
  const [classId, setClassId] = useState(classes[0]?.id || "");
  const [periodId, setPeriodId] = useState("");
  const [exam, setExam] = useState("");
  const params = new URLSearchParams([...(periodId ? [["period_id", periodId]] : []), ...(exam ? [["exam", exam]] : [])]);
  const query = useTeachingQuery(classId ? `/api/marks/classes/${classId}/marksheet?${params}` : null);
  const data = query.data;
  const chosen = classes.find(c => c.id === classId);
  return <>
    <section className="teaching-panel" aria-labelledby="class-marksheet"><h2 id="class-marksheet">Class marksheet</h2>
      <div className="records-filters">
        <Field label="Class" value={classId} onChange={e => { setClassId(e.target.value); setPeriodId(""); setExam(""); }}>{classes.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}</Field>
        {data?.periods?.length > 0 && <Field label="Term or semester" value={periodId || data.period_id} onChange={e => { setPeriodId(e.target.value); setExam(""); }}>{data.periods.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Field>}
        {data && <Field label="Marks" value={exam} onChange={e => setExam(e.target.value)}><option value="">Term result</option>{data.exam_titles.map(t => <option key={t} value={t}>{t}</option>)}</Field>}
      </div>
      <QueryState query={query} />
      {data && <>
        <p className="teaching-muted">{exam ? `${exam}: each subject's mark as a percentage.` : "Term result: your grading rule applied to every mark entered so far, released or not."} Position is by {data.ranked_by === "MEAN_POINTS" ? "mean points" : "mean percentage"}; equal results share a position.</p>
        <div className="records-actions"><DownloadButton path={`/api/marks/classes/${classId}/marksheet?${new URLSearchParams([["period_id", data.period_id], ...(exam ? [["exam", exam]] : []), ["download", "true"]])}`}
          filename={`${chosen?.label || "class"} ${data.period_name}${exam ? ` ${exam}` : ""}.xlsx`}>Download Excel</DownloadButton></div>
        <Sheet data={data} />
      </>}
    </section>
    {data && <ClassUpload key={`${classId}:${data.period_id}`} classId={classId} periodId={data.period_id} titles={data.exam_titles} />}
  </>;
}

function AssessmentUpload({ subject }) {
  const works = useTeachingQuery(`/api/teaching/subjects/${subject.id}/coursework`);
  const [workId, setWorkId] = useState("");
  const [table, setTable] = useState(null);
  const [error, setError] = useState("");
  const mutation = useTeachingMutation();
  const work = (works.data || []).find(w => w.id === workId);
  const preview = mutation.data && !mutation.data.saved ? mutation.data : null;
  async function choose(event) {
    setError(""); mutation.reset();
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try { const data = await readFile(file); setTable(data); await mutation.mutateAsync({ path: `/api/marks/coursework/${workId}/import`, body: { ...data, commit: false } }); }
    catch (e) { if (!mutation.isError) setError(e.message); }
  }
  return <div className="marks-upload">
    <QueryState query={works} />
    <Field label="Assessment" value={workId} onChange={e => { setWorkId(e.target.value); mutation.reset(); }}><option value="">Choose</option>{(works.data || []).map(w => <option key={w.id} value={w.id}>{w.title} (out of {fmt(w.max_score)})</option>)}</Field>
    {work && <>
      <p className="teaching-muted">Columns: admission_number and mark{work.assessment_mode === "COMPETENCY" ? ` (one of: ${work.rubric_labels.join(", ")})` : ""}, with optional feedback.</p>
      <div className="records-actions"><DownloadButton path={`/api/marks/coursework/${work.id}/template`} filename={`${subject.name} ${work.title}.xlsx`}>Download blank list</DownloadButton>
        <label className="btn">Choose file<input type="file" accept=".xlsx,.csv" hidden onChange={choose} /></label></div>
    </>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <MutationState mutation={mutation} message={mutation.data?.saved ? `Saved ${mutation.data.to_save} marks.` : "Checked."} />
    {preview && <><p>{preview.to_save} marks to save{preview.errors ? `, ${preview.errors} rows with problems` : ""}.</p><Problems rows={preview.rows} />
      <button className="btn btn--primary" type="button" disabled={Boolean(preview.errors) || !preview.to_save || mutation.isPending}
        onClick={() => mutation.mutate({ path: `/api/marks/coursework/${workId}/import`, body: { ...table, commit: true } })}>{preview.to_save ? `Save ${preview.to_save} marks` : "Nothing new to save"}</button></>}
  </div>;
}

function SubjectMarks({ subjects }) {
  const [subjectId, setSubjectId] = useState(subjects[0]?.id || "");
  const subject = subjects.find(s => s.id === subjectId);
  return <section className="teaching-panel" aria-labelledby="subject-marks"><h2 id="subject-marks">One subject</h2>
    <Field label="Subject" value={subjectId} onChange={e => setSubjectId(e.target.value)}>{subjects.map(s => <option key={s.id} value={s.id}>{s.class_name} · {s.name}</option>)}</Field>
    {subject && <>
      <div className="records-actions"><DownloadButton path={`/api/marks/subjects/${subject.id}/marksheet?download=true`} filename={`${subject.class_name} ${subject.name}.xlsx`}>Download this term's marks</DownloadButton></div>
      <h3>Upload marks for one assessment</h3><AssessmentUpload key={subject.id} subject={subject} />
    </>}
  </section>;
}

export default function MarksPage() {
  const { user } = useAuth();
  const admin = user.role === "INSTITUTION_ADMIN";
  const classes = useTeachingQuery("/api/teaching/classes");
  const subjects = useTeachingQuery("/api/teaching/subjects");
  const own = (classes.data || []).filter(c => admin || c.supervisor_id === user.id)
    .map(c => ({ id: c.id, label: `${c.name}${c.stream ? ` ${c.stream}` : ""} · ${c.academic_year}` }));
  return <><PageHeading title="Marks and marksheets">Upload marks from Excel and download marksheets to build reports in your own format.</PageHeading>
    <QueryState query={classes} /><QueryState query={subjects} />
    {own.length > 0 && <ClassMarksheet classes={own} />}
    {subjects.data?.length > 0 && <SubjectMarks subjects={subjects.data} />}
    {classes.data && subjects.data && !own.length && !subjects.data.length && <Empty>You have no classes or subjects yet.</Empty>}
  </>;
}
