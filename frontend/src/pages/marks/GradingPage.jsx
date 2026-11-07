import { useState } from "react";
import GradingRulesEditor from "../../components/common/GradingRulesEditor";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../records/Records.css";
import "./Marks.css";

const STATUS = { PENDING: "Waiting for approval", APPROVED: "Approved", REJECTED: "Rejected", WITHDRAWN: "Withdrawn" };
const when = value => new Date(value).toLocaleDateString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium" });

export function RulesSummary({ rules }) {
  if (!rules.enabled) return <p className="teaching-muted">Final grading is off.</p>;
  return <>
    <p>{rules.name} · pass mark {rules.pass_percentage}% · {rules.aggregation === "POINTS" ? "all marks added together" : `weights: coursework ${rules.weights.COURSEWORK}%, exams ${rules.weights.EXAM}%, assignments ${rules.weights.ASSIGNMENT}%`}{rules.gpa_enabled ? ` · GPA out of ${rules.gpa_scale}` : ""}</p>
    <div className="table-wrapper"><table className="data-table marks-bands"><thead><tr><th>Grade</th><th className="records-num">From %</th><th className="records-num">Points</th></tr></thead>
      <tbody>{[...rules.bands].sort((a, b) => b.minimum - a.minimum).map(b => <tr key={b.label}><td>{b.label}</td><td className="records-num">{b.minimum}</td><td className="records-num">{b.points ?? "—"}</td></tr>)}</tbody></table></div>
  </>;
}

function Editor({ initial, locked }) {
  const mutation = useTeachingMutation();
  const [rules, setRules] = useState(initial);
  const [reason, setReason] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (!locked && !window.confirm("Save this grading? After this, changes need approval from the Skynet platform administrator.")) return;
    try {
      await mutation.mutateAsync(locked ? { path: "/api/institution/grading/requests", body: { rules, reason } } : { path: "/api/institution/grading", method: "PUT", body: { rules } });
      setReason("");
    } catch { /* Shown below. */ }
  }
  return <form className="teaching-form" onSubmit={submit}>
    <GradingRulesEditor rules={rules} onChange={setRules} intro={locked ? "Propose the grading you want." : "Set your institution's grading."} />
    {locked && <><label htmlFor="grading-reason">Why the change is needed</label>
      <textarea id="grading-reason" rows={3} required minLength={10} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></>}
    <MutationState mutation={mutation} message={locked ? "Request sent. You will see the decision here." : "Grading saved."} />
    <button className="btn btn--primary" disabled={mutation.isPending}>{locked ? "Send change request" : "Save grading"}</button>
  </form>;
}

export default function GradingPage() {
  const query = useTeachingQuery("/api/institution/grading");
  const withdraw = useTeachingMutation();
  const [proposing, setProposing] = useState(false);
  const data = query.data;
  const pending = data?.requests.find(r => r.status === "PENDING");
  return <><PageHeading title="Grading">Your grade bands, points, weights and pass mark. They are used for final grades and marksheets.</PageHeading>
    <QueryState query={query} />
    {data && !data.locked && <section className="teaching-panel"><h2>Set your grading</h2>
      <p className="teaching-notice">You can set this once. After that, a change is sent to the Skynet platform administrator for approval.</p>
      <Editor initial={data.rules} locked={false} /></section>}
    {data?.locked && <>
      <section className="teaching-panel"><h2>Current grading</h2><p className="teaching-muted">Set on {when(data.locked_at)}. Changes need platform approval.</p><RulesSummary rules={data.rules} />
        {!pending && !proposing && <button className="btn" type="button" onClick={() => setProposing(true)}>Request a change</button>}
        {pending && <p className="teaching-notice">A change request is waiting for approval.</p>}</section>
      {proposing && !pending && <section className="teaching-panel"><h2>Request a change</h2><Editor initial={data.rules} locked /></section>}
      <section className="teaching-panel"><h2>Change requests</h2><MutationState mutation={withdraw} message="Request withdrawn." />
        {!data.requests.length ? <Empty>No change requests yet.</Empty> : <ul className="records-list">{data.requests.map(r => <li key={r.id}>
          <h3>{STATUS[r.status]} · {when(r.created_at)}</h3><p className="records-announcement">{r.reason}</p>
          {r.decision_note && <p className="records-announcement"><strong>Platform note:</strong> {r.decision_note}</p>}
          {r.status === "PENDING" && <button className="btn" type="button" disabled={withdraw.isPending} onClick={() => withdraw.mutate({ path: `/api/institution/grading/requests/${r.id}/withdraw` })}>Withdraw</button>}
        </li>)}</ul>}
      </section>
    </>}
  </>;
}
