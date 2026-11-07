import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../records/Records.css";
import "./Messages.css";

const KINDS = { RESULTS: "Results", FEES: "Fee balance reminder", ANNOUNCEMENT: "Announcement", EMERGENCY: "Emergency notice" };
const STARTERS = {
  RESULTS: "Dear parent, {student}'s {exam} results: {results}. {school}",
  FEES: "Dear parent, {student} has a fee balance of {balance} for {term}. Kindly clear it. {school}",
  ANNOUNCEMENT: "Dear parent, ",
  EMERGENCY: "URGENT from {school}: ",
};
const STATUS = { DRAFT: "Draft", SENDING: "Sending", SENT: "Sent", CANCELLED: "Cancelled" };
const when = value => value ? new Date(value).toLocaleString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium", timeStyle: "short" }) : "";

function SecretForm({ overview }) {
  const mutation = useTeachingMutation();
  const [open, setOpen] = useState(!overview.secret_set);
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    try { await mutation.mutateAsync({ path: "/api/messaging/secret", method: "PUT", body: Object.fromEntries(new FormData(form)) }); form.reset(); setOpen(false); }
    catch { /* Shown below. */ }
  }
  return <section className="teaching-panel" aria-labelledby="secret-title"><h2 id="secret-title">Your secret question</h2>
    <p className="teaching-muted">Every message is sent only after you answer this question. Skynet keeps only a scrambled form of the answer, so nobody can read it. If you forget it, ask the Skynet platform administrator to clear it.</p>
    {overview.secret_set && <p>Question: <strong>{overview.question}</strong></p>}
    <MutationState mutation={mutation} message="Secret question saved." />
    {open ? <form className="teaching-form" onSubmit={submit} autoComplete="off">
      <Field label="Question" name="question" required minLength={5} maxLength={200} placeholder="The name of my first school" />
      <Field label="Answer" name="answer" type="password" required minLength={3} maxLength={200} description="Capital letters and extra spaces don't matter." />
      <Field label="Your account password" name="password" type="password" required autoComplete="current-password" />
      <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save</button>{overview.secret_set && <button className="btn" type="button" onClick={() => setOpen(false)}>Cancel</button>}</div>
    </form> : <button className="btn" type="button" onClick={() => setOpen(true)}>Change question</button>}
  </section>;
}

function StudentPicker({ value, onChange }) {
  const [search, setSearch] = useState("");
  const query = useTeachingQuery(search.length >= 2 ? `/api/records/students?search=${encodeURIComponent(search)}` : null);
  return <div>
    <Field label="Find students" type="search" value={search} onChange={e => setSearch(e.target.value)} description={`${value.length} chosen`} />
    <ul className="messages-picks">{(query.data?.items || []).map(s => <li key={s.id}><label><input type="checkbox" checked={value.includes(s.id)}
      onChange={e => onChange(e.target.checked ? [...value, s.id] : value.filter(id => id !== s.id))} /> {s.first_name} {s.last_name} <span className="teaching-muted">{s.admission_number}</span></label></li>)}</ul>
  </div>;
}

function Composer({ overview, row, onDone }) {
  const mutation = useTeachingMutation();
  const [kind, setKind] = useState(row?.kind || "FEES");
  const [title, setTitle] = useState(row?.title || "");
  const [template, setTemplate] = useState(row?.template || STARTERS.FEES);
  const [audience, setAudience] = useState(row?.audience || { scope: "SCHOOL", class_id: null, student_ids: [], period_id: overview.periods[0]?.id || null, exam: "", fee_statuses: ["PARTIAL", "UNPAID"], all_guardians: false });
  const set = (key, value) => setAudience(old => ({ ...old, [key]: value }));
  const sheet = useTeachingQuery(kind === "RESULTS" && audience.class_id && audience.period_id ? `/api/marks/classes/${audience.class_id}/marksheet?period_id=${audience.period_id}` : null);
  function changeKind(next) {
    setKind(next);
    if (!template.trim() || Object.values(STARTERS).includes(template)) setTemplate(STARTERS[next]);
  }
  async function submit(event) {
    event.preventDefault();
    const body = { kind, title, template, audience: { ...audience, class_id: audience.class_id || null, period_id: audience.period_id || null } };
    try { await mutation.mutateAsync(row ? { path: `/api/messaging/messages/${row.id}`, method: "PUT", body } : { path: "/api/messaging/messages", body }); onDone(); }
    catch { /* Shown below. */ }
  }
  const length = template.length;
  return <form className="teaching-form" onSubmit={submit} aria-label={row ? "Edit message" : "New message"}>
    <div className="records-filters">
      <Field label="Type" value={kind} onChange={e => changeKind(e.target.value)}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
      <Field label="Title (for your records and the email subject)" value={title} required minLength={3} maxLength={160} onChange={e => setTitle(e.target.value)} />
    </div>
    {(kind === "RESULTS" || kind === "FEES") && <div className="records-filters">
      <Field label="Term or semester" value={audience.period_id || ""} required onChange={e => set("period_id", e.target.value)}><option value="" disabled>Choose</option>{overview.periods.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</Field>
      <Field label={kind === "RESULTS" ? "Class" : "Class (optional)"} value={audience.class_id || ""} required={kind === "RESULTS"} onChange={e => set("class_id", e.target.value || null)}>
        <option value="">{kind === "RESULTS" ? "Choose" : "All classes"}</option>{overview.classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</Field>
      {kind === "RESULTS" && <Field label="Results" value={audience.exam} onChange={e => set("exam", e.target.value)}><option value="">Term result</option>{(sheet.data?.exam_titles || []).map(t => <option key={t} value={t}>{t}</option>)}</Field>}
      {kind === "FEES" && <fieldset className="messages-inline"><legend className="teaching-muted">Remind guardians of students who are</legend>
        {[["UNPAID", "Not paid"], ["PARTIAL", "Partly paid"]].map(([k, v]) => <label key={k}><input type="checkbox" checked={audience.fee_statuses.includes(k)}
          onChange={e => set("fee_statuses", e.target.checked ? [...audience.fee_statuses, k] : audience.fee_statuses.filter(x => x !== k))} /> {v}</label>)}</fieldset>}
    </div>}
    {(kind === "ANNOUNCEMENT" || kind === "EMERGENCY") && <div className="records-filters">
      <Field label="Send to guardians of" value={audience.scope} onChange={e => set("scope", e.target.value)}><option value="SCHOOL">The whole school</option><option value="CLASS">One class</option><option value="STUDENTS">Chosen students</option></Field>
      {audience.scope === "CLASS" && <Field label="Class" value={audience.class_id || ""} required onChange={e => set("class_id", e.target.value)}><option value="" disabled>Choose</option>{overview.classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</Field>}
    </div>}
    {audience.scope === "STUDENTS" && (kind === "ANNOUNCEMENT" || kind === "EMERGENCY") && <StudentPicker value={audience.student_ids} onChange={ids => set("student_ids", ids)} />}
    <label className="messages-inline"><input type="checkbox" checked={audience.all_guardians} onChange={e => set("all_guardians", e.target.checked)} /> Send to every guardian, not only the main contact (costs more SMS)</label>
    <label htmlFor="message-text">Message</label>
    <textarea id="message-text" rows={5} required minLength={3} maxLength={1600} value={template} onChange={e => setTemplate(e.target.value)} aria-describedby="message-help" />
    <p id="message-help" className="teaching-muted">{length} characters. About 160 characters is one SMS. Insert: {overview.placeholders[kind].map(p => <button key={p} type="button" className="messages-chip" onClick={() => setTemplate(t => `${t}{${p}}`)}>{`{${p}}`}</button>)}</p>
    <MutationState mutation={mutation} />
    <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save draft</button><button className="btn" type="button" onClick={onDone}>Cancel</button></div>
  </form>;
}

function Preview({ row, overview, onClose }) {
  const query = useTeachingQuery(`/api/messaging/messages/${row.id}/preview`);
  const send = useTeachingMutation();
  const [answer, setAnswer] = useState("");
  const data = query.data;
  return <section className="teaching-panel" aria-labelledby="preview-title"><h2 id="preview-title">Check before sending: {row.title}</h2>
    <QueryState query={query} />
    {data && <>
      <dl className="records-totals">
        <div><dt>SMS</dt><dd>{data.sms}</dd></div><div><dt>SMS parts</dt><dd>{data.parts}</dd></div><div><dt>Email copies</dt><dd>{data.email}</dd></div>
        <div><dt>Left this month</dt><dd>{data.remaining} of {data.allowance}</dd></div>
      </dl>
      {!data.sms_configured && <p className="teaching-notice">SMS is not switched on yet; only email copies would go out.</p>}
      {!data.fits && data.parts > 0 && <p className="form-error" role="alert">This needs {data.parts} SMS parts but only {data.remaining} are left this month. Ask the Skynet platform administrator to raise your allowance, or send to fewer guardians.</p>}
      <h3>Examples</h3>
      <ul className="records-list">{data.samples.map((s, i) => <li key={i}><div className="teaching-muted">{s.channel === "SMS" ? `SMS to ${s.to} · ${s.parts} part${s.parts === 1 ? "" : "s"}` : `Email to ${s.to}`}</div><p className="records-announcement">{s.body}</p></li>)}</ul>
      {data.skipped_total > 0 && <details><summary>{data.skipped_total} students left out</summary><ul>{data.skipped.map((s, i) => <li key={i}>{s.name}: {s.reason}</li>)}</ul></details>}
      {overview.secret_set ? <form className="teaching-form" onSubmit={e => { e.preventDefault(); send.mutate({ path: `/api/messaging/messages/${row.id}/send`, body: { answer } }); }} autoComplete="off">
        <Field label={overview.question} type="password" value={answer} required onChange={e => setAnswer(e.target.value)} description="Answer your secret question to send." />
        <MutationState mutation={send} message={send.data ? `Sending to ${send.data.queued} recipients.` : "Sent."} />
        <div className="records-actions"><button className="btn btn--primary" disabled={send.isPending || send.isSuccess || (!data.fits && data.parts > 0) || (!data.sms && !data.email)}>Send now</button><button className="btn" type="button" onClick={onClose}>Close</button></div>
      </form> : <p className="teaching-notice">Set your secret question above before sending.</p>}
    </>}
  </section>;
}

function Detail({ row, overview, onClose }) {
  const query = useTeachingQuery(`/api/messaging/messages/${row.id}`, { refetchInterval: row.status === "SENDING" ? 5000 : false });
  const retry = useTeachingMutation();
  const [answer, setAnswer] = useState("");
  const data = query.data;
  const failed = data?.deliveries.filter(d => d.status === "FAILED").length || 0;
  return <section className="teaching-panel" aria-labelledby="detail-title"><h2 id="detail-title">{row.title}</h2><QueryState query={query} />
    {data && <>
      <p className="teaching-muted">{KINDS[data.kind]} · sent {when(data.sent_at)}</p>
      <p className="records-announcement">{data.template}</p>
      <div className="table-wrapper"><table className="data-table"><thead><tr><th>To</th><th>By</th><th>Status</th><th>Note</th></tr></thead>
        <tbody>{data.deliveries.map(d => <tr key={d.id}><td>{d.guardian_name}<div className="teaching-muted">{d.address}</div></td><td>{d.channel === "SMS" ? `SMS (${d.parts})` : "Email"}</td>
          <td><span className={`messages-status messages-status--${d.status}`}>{d.status.toLowerCase()}</span></td><td>{d.error}</td></tr>)}</tbody></table></div>
      {failed > 0 && overview.secret_set && <form className="records-filters" onSubmit={e => { e.preventDefault(); retry.mutate({ path: `/api/messaging/messages/${row.id}/retry`, body: { answer } }); }} autoComplete="off">
        <Field label={overview.question} type="password" value={answer} required onChange={e => setAnswer(e.target.value)} />
        <div className="records-actions"><button className="btn" disabled={retry.isPending}>Retry {failed} failed</button></div>
        <MutationState mutation={retry} message="Retrying." />
      </form>}
      <button className="btn" type="button" onClick={onClose}>Close</button>
    </>}
  </section>;
}

export default function MessagesPage() {
  const overview = useTeachingQuery("/api/messaging/overview");
  const list = useTeachingQuery("/api/messaging/messages");
  const cancel = useTeachingMutation();
  const [mode, setMode] = useState(null);
  const data = overview.data;
  return <><PageHeading title="Parent messages">Results, fee balances, announcements and emergency notices to parents and guardians by SMS, with an email copy where they have an email address.</PageHeading>
    <QueryState query={overview} />
    {data && <>
      <dl className="records-totals">
        <div><dt>SMS parts this month</dt><dd>{data.used} of {data.allowance}</dd></div>
        <div><dt>SMS</dt><dd>{data.sms_configured ? "On" : "Not set up"}</dd></div>
        <div><dt>Email copies</dt><dd>{data.email_configured ? "On" : "Off"}</dd></div>
      </dl>
      {data.allowance === 0 && <p className="teaching-notice">Your school has no SMS allowance yet. Ask the Skynet platform administrator to set one.</p>}
      <SecretForm overview={data} />
      {mode?.type === "new" || mode?.type === "edit" ? <section className="teaching-panel"><h2>{mode.type === "new" ? "New message" : "Edit draft"}</h2>
        <Composer overview={data} row={mode.row} onDone={() => setMode(null)} /></section>
        : <button className="btn btn--primary" type="button" onClick={() => setMode({ type: "new" })}>New message</button>}
      {mode?.type === "preview" && <Preview key={mode.row.id} row={mode.row} overview={data} onClose={() => setMode(null)} />}
      {mode?.type === "detail" && <Detail key={mode.row.id} row={mode.row} overview={data} onClose={() => setMode(null)} />}
      <section className="teaching-panel" aria-labelledby="history-title"><h2 id="history-title">Messages</h2><QueryState query={list} /><MutationState mutation={cancel} message="Draft cancelled." />
        {list.data && (!list.data.length ? <Empty>No messages yet.</Empty> : <div className="table-wrapper"><table className="data-table">
          <thead><tr><th>Message</th><th>Status</th><th className="records-num">SMS</th><th className="records-num">Email</th><th><span className="records-hidden">Actions</span></th></tr></thead>
          <tbody>{list.data.map(m => {
            const total = channel => Object.values(m.counts?.[channel] || {}).reduce((a, b) => a + b, 0);
            const failed = (m.counts?.SMS?.FAILED || 0) + (m.counts?.EMAIL?.FAILED || 0);
            return <tr key={m.id}><td>{m.title}<div className="teaching-muted">{KINDS[m.kind]} · {when(m.sent_at || m.created_at)}</div></td>
              <td>{STATUS[m.status]}{failed > 0 && <div className="form-error">{failed} failed</div>}</td>
              <td className="records-num">{total("SMS") || ""}</td><td className="records-num">{total("EMAIL") || ""}</td>
              <td><div className="records-actions">{m.status === "DRAFT" ? <>
                <button className="btn btn--primary" type="button" onClick={() => setMode({ type: "preview", row: m })}>Check and send</button>
                <button className="btn" type="button" onClick={() => setMode({ type: "edit", row: m })}>Edit</button>
                <button className="btn" type="button" disabled={cancel.isPending} onClick={() => window.confirm("Cancel this draft?") && cancel.mutate({ path: `/api/messaging/messages/${m.id}/cancel` })}>Cancel</button></>
                : m.status !== "CANCELLED" && <button className="btn" type="button" onClick={() => setMode({ type: "detail", row: m })}>Delivery</button>}</div></td></tr>;
          })}</tbody></table></div>)}
      </section>
    </>}
  </>;
}
