import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "../records/Records.css";

const month = () => new Date().toLocaleDateString("en-CA", { timeZone: "Africa/Nairobi" }).slice(0, 7);

function AllowanceCell({ row }) {
  const mutation = useTeachingMutation();
  const [value, setValue] = useState(String(row.allowance));
  return <form className="records-actions" onSubmit={e => { e.preventDefault(); mutation.mutate({ path: `/api/platform/institutions/${row.institution_id}/sms-allowance`, method: "PUT", body: { monthly_parts: Number(value) } }); }}>
    <input type="number" min="0" max="1000000" value={value} onChange={e => setValue(e.target.value)} aria-label={`Monthly SMS parts for ${row.name}`} style={{ width: 100 }} />
    <button className="btn" disabled={mutation.isPending || String(row.allowance) === value}>Save</button>
    {mutation.isError && <span className="form-error" role="alert">{mutation.error.message}</span>}
  </form>;
}

export default function PlatformMessagingPage() {
  const [chosen, setChosen] = useState(month());
  const query = useTeachingQuery(`/api/platform/messaging/usage?month=${chosen}`);
  const clear = useTeachingMutation();
  const data = query.data;
  const total = key => (data?.rows || []).reduce((sum, r) => sum + Number(r[key] || 0), 0);
  return <><PageHeading title="SMS usage">Parent messages are paid for by the platform. Set each school's monthly allowance in SMS parts (about 160 characters each) and watch usage and cost.</PageHeading>
    <Field label="Month" type="month" value={chosen} max={month()} onChange={e => setChosen(e.target.value || month())} />
    <QueryState query={query} /><MutationState mutation={clear} message="Secret answers cleared. The school's admins must set new ones." />
    {data && <>
      {!data.sms_configured && <p className="teaching-notice">SMS is off. Add the Africa's Talking settings on the server to switch it on.</p>}
      <dl className="records-totals"><div><dt>SMS parts</dt><dd>{total("sms_parts")}</dd></div><div><dt>Failed SMS</dt><dd>{total("sms_failed")}</dd></div>
        <div><dt>Emails</dt><dd>{total("emails")}</dd></div><div><dt>Provider cost</dt><dd>KES {total("cost").toLocaleString("en-KE", { maximumFractionDigits: 2 })}</dd></div></dl>
      <section className="teaching-panel"><div className="table-wrapper"><table className="data-table">
        <thead><tr><th>School</th><th>Monthly allowance (parts)</th><th className="records-num">Parts used</th><th className="records-num">SMS sent</th><th className="records-num">Failed</th><th className="records-num">Emails</th><th className="records-num">Cost (KES)</th><th>Secret answers</th></tr></thead>
        <tbody>{data.rows.map(r => <tr key={r.institution_id}><td>{r.name}<div className="teaching-muted">{r.code}</div></td>
          <td>{chosen === month() ? <AllowanceCell key={r.allowance} row={r} /> : r.allowance}</td>
          <td className="records-num">{r.sms_parts}</td><td className="records-num">{r.sms_sent}</td><td className="records-num">{r.sms_failed}</td><td className="records-num">{r.emails}</td>
          <td className="records-num">{Number(r.cost).toLocaleString("en-KE", { maximumFractionDigits: 2 })}</td>
          <td>{r.secrets ? <button className="btn" type="button" disabled={clear.isPending} onClick={() => window.confirm(`Clear the secret answers of ${r.name}'s admins? They will have to set new ones before sending.`) && clear.mutate({ path: `/api/platform/institutions/${r.institution_id}/messaging-secrets`, method: "DELETE" })}>Clear ({r.secrets})</button> : <span className="teaching-muted">None set</span>}</td></tr>)}</tbody>
      </table></div></section>
    </>}
  </>;
}
