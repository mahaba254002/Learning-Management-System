import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { RulesSummary } from "../marks/GradingPage";
import "../records/Records.css";
import "../marks/Marks.css";

const when = value => new Date(value).toLocaleString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium", timeStyle: "short" });

function Decide({ request }) {
  const mutation = useTeachingMutation();
  const [note, setNote] = useState("");
  const decide = approve => (approve ? window.confirm(`Apply the new grading to ${request.institution_name}?`) : true)
    && mutation.mutate({ path: `/api/platform/grading-requests/${request.id}/decide`, body: { approve, note } });
  return <div>
    <Field label="Note to the institution (required to reject)" value={note} maxLength={1000} onChange={e => setNote(e.target.value)} />
    <div className="records-actions"><button className="btn btn--primary" type="button" disabled={mutation.isPending} onClick={() => decide(true)}>Approve</button>
      <button className="btn" type="button" disabled={mutation.isPending || note.trim().length < 3} onClick={() => decide(false)}>Reject</button></div>
    <MutationState mutation={mutation} message="Decision saved." />
  </div>;
}

export default function PlatformGradingRequestsPage() {
  const [status, setStatus] = useState("PENDING");
  const query = useTeachingQuery(`/api/platform/grading-requests?status=${status}`);
  return <><PageHeading title="Grading requests">Institutions set their grading once. Changes after that come here for your approval.</PageHeading>
    <Field label="Show" value={status} onChange={e => setStatus(e.target.value)}><option value="PENDING">Waiting</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option><option value="ALL">All</option></Field>
    <QueryState query={query} />
    {query.data && (!query.data.length ? <Empty>No requests.</Empty> : query.data.map(r => <section key={r.id} className="teaching-panel" aria-label={`${r.institution_name} request`}>
      <h2>{r.institution_name} <span className="teaching-muted">{r.institution_code}</span></h2>
      <p className="teaching-muted">{when(r.created_at)} · {r.status.toLowerCase()}</p>
      <p className="records-announcement">{r.reason}</p>
      <div className="marks-compare"><div><h3>Now</h3><RulesSummary rules={r.previous_rules} /></div><div><h3>Proposed</h3><RulesSummary rules={r.proposed_rules} /></div></div>
      {r.decision_note && <p><strong>Your note:</strong> {r.decision_note}</p>}
      {r.status === "PENDING" && <Decide request={r} />}
    </section>))}
  </>;
}
