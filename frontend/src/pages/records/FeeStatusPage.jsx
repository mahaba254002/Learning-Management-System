import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { downloadCsv } from "../institution/importFiles";
import { feeRows } from "./csv";
import { kes } from "../../components/billing/money";
import "./Records.css";

const LABELS = { PAID: "Paid", PARTIAL: "Partly paid", UNPAID: "Not paid", NONE: "Not recorded" };
export const FeeTag = ({ status }) => <span className={`records-tag records-tag--${status || "NONE"}`}>{LABELS[status || "NONE"]}</span>;

function FeeEditor({ item, periodId, onDone }) {
  const mutation = useTeachingMutation();
  const [status, setStatus] = useState(item.fee?.status || "UNPAID");
  async function submit(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await mutation.mutateAsync({ path: `/api/records/fees/${item.id}`, method: "PUT", body: { period_id: periodId, status, balance: status === "PAID" ? "0" : values.balance || "0", note: values.note } });
      onDone();
    } catch { /* Shown below. */ }
  }
  return <form className="records-filters" onSubmit={submit} aria-label={`Fee status for ${item.first_name} ${item.last_name}`}>
    <Field label="Status" value={status} onChange={e => setStatus(e.target.value)}><option value="PAID">Paid</option><option value="PARTIAL">Partly paid</option><option value="UNPAID">Not paid</option></Field>
    {status !== "PAID" && <Field label="Balance (KES)" name="balance" type="number" min={status === "PARTIAL" ? "0.01" : "0"} step="0.01" defaultValue={item.fee?.balance ?? ""} required={status === "PARTIAL"} />}
    <Field label="Note" name="note" maxLength={300} defaultValue={item.fee?.note || ""} />
    <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save</button><button className="btn" type="button" onClick={onDone}>Cancel</button></div>
    <MutationState mutation={mutation} />
  </form>;
}

function FeeUpload({ periodId, periodName }) {
  const mutation = useTeachingMutation();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const preview = mutation.data && !mutation.data.applied ? mutation.data : null;
  async function choose(event) {
    setError(""); mutation.reset(); setRows(null);
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) { setError("Save the list from your fees system as a CSV file first."); return; }
    try {
      const parsed = feeRows(await file.text());
      setRows(parsed);
      await mutation.mutateAsync({ path: "/api/records/fees/import", body: { period_id: periodId, rows: parsed } });
    } catch (e) { if (!mutation.isError) setError(e.message); }
  }
  return <section className="teaching-panel" aria-labelledby="fee-upload">
    <h2 id="fee-upload">Upload a list from your fees system</h2>
    <p className="teaching-muted">CSV with the columns admission_number, status (Paid, Partial or Unpaid), balance and note. Nothing changes until every row is valid and you apply it to {periodName}.</p>
    <div className="records-actions">
      <button className="btn" type="button" onClick={() => downloadCsv("fee-status-template.csv", ["admission_number", "status", "balance", "note"], [["A001", "Partial", "12500", "Lunch fee pending"]])}>Download template</button>
      <label className="btn">Choose CSV file<input type="file" accept=".csv,text/csv" hidden onChange={choose} /></label>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <MutationState mutation={mutation} message={mutation.data?.applied ? `Applied to ${mutation.data.valid} students.` : "Checked."} />
    {preview && <>
      <p>{preview.valid} rows ready{preview.errors ? `, ${preview.errors} with problems` : ""}.</p>
      {preview.errors > 0 && <div className="table-wrapper"><table className="data-table"><thead><tr><th className="records-num">Row</th><th>Admission number</th><th>Problem</th></tr></thead>
        <tbody>{preview.rows.filter(r => r.problems.length).slice(0, 100).map(r => <tr key={r.row}><td className="records-num">{r.row + 1}</td><td>{r.admission_number}</td><td>{r.problems.join("; ")}</td></tr>)}</tbody></table></div>}
      <button className="btn btn--primary" type="button" disabled={Boolean(preview.errors) || mutation.isPending}
        onClick={() => mutation.mutate({ path: "/api/records/fees/import", body: { period_id: periodId, rows, commit: true } })}>Apply to {preview.valid} students</button>
    </>}
  </section>;
}

export default function FeeStatusPage() {
  const [filters, setFilters] = useState({ period_id: "", class_id: "", status: "", search: "" });
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const params = new URLSearchParams([...Object.entries(filters).filter(([, v]) => v), ["offset", offset]]);
  const query = useTeachingQuery(`/api/records/fees?${params}`);
  const data = query.data;
  const period = data?.periods.find(p => p.id === data.period_id);
  const set = (key, value) => { setFilters(old => ({ ...old, [key]: value })); setOffset(0); setEditing(null); };
  return <><PageHeading title="Fee status">Where each student stands on fees this term. Payments are handled in your institution's fees system; record the outcome here.</PageHeading>
    <QueryState query={query} />
    {data && !data.periods.length && <Empty>Add terms or semesters under Academic years first.</Empty>}
    {data && data.periods.length > 0 && <>
      <div className="records-filters">
        <Field label="Term or semester" value={filters.period_id || data.period_id} onChange={e => set("period_id", e.target.value)}>{data.periods.map(p => <option key={p.id} value={p.id}>{p.name} · {p.year}</option>)}</Field>
        <Field label="Class" value={filters.class_id} onChange={e => set("class_id", e.target.value)}><option value="">All classes</option>{data.classes.map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>
        <Field label="Status" value={filters.status} onChange={e => set("status", e.target.value)}><option value="">Any</option>{Object.entries(LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
        <Field label="Search" type="search" value={filters.search} maxLength={100} onChange={e => set("search", e.target.value)} />
      </div>
      <dl className="records-totals">{["PAID", "PARTIAL", "UNPAID", "NONE"].map(k => <div key={k}><dt>{LABELS[k]}</dt><dd>{data.totals[k]?.count || 0}</dd></div>)}
        <div><dt>Total balance</dt><dd>{kes(Object.values(data.totals).reduce((sum, t) => sum + Number(t.balance || 0), 0))}</dd></div></dl>
      <section className="teaching-panel">
        {!data.items.length ? <Empty>No students match.</Empty> : <div className="table-wrapper"><table className="data-table records-table">
          <thead><tr><th>Student</th><th>Class</th><th>Status</th><th className="records-num">Balance</th><th>Note</th>{data.can.edit_fees && <th><span className="records-hidden">Actions</span></th>}</tr></thead>
          <tbody>{data.items.map(item => editing === item.id
            ? <tr key={item.id}><td colSpan={6}><strong>{item.first_name} {item.last_name}</strong><FeeEditor item={item} periodId={data.period_id} onDone={() => setEditing(null)} /></td></tr>
            : <tr key={item.id}><td>{item.first_name} {item.last_name}<div className="teaching-muted">{item.admission_number}</div></td>
              <td>{item.classes.map(c => c.name).join(", ") || "—"}</td><td><FeeTag status={item.fee?.status} /></td>
              <td className="records-num">{item.fee ? kes(item.fee.balance) : "—"}</td><td>{item.fee?.note || ""}</td>
              {data.can.edit_fees && <td><button className="btn" type="button" onClick={() => setEditing(item.id)}>Update</button></td>}</tr>)}</tbody>
        </table></div>}
        <div className="operations-pagination"><button className="btn" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{data.total} students</span><button className="btn" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Next</button></div>
      </section>
      {data.can.edit_fees && <FeeUpload periodId={data.period_id} periodName={period?.name || "this term"} />}
      {!data.can.edit_fees && <p className="teaching-muted">Only the institution administrator and staff with the fees permission can change fee status.</p>}
    </>}
  </>;
}
