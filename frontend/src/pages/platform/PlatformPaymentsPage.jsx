import { useState } from "react";
import { apiRequest } from "../../api/client";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { kes } from "../../components/billing/money";
import "../../components/billing/SubscriptionPayment.css";
import "./PlatformPayments.css";

const KIND_LABELS = {
  REMINDER_EMAIL: "Reminder email", RECEIPT_EMAIL: "Receipt email", STK_PROMPT: "Phone prompt sent", STK_REJECTED: "Prompt refused",
  STK_CALLBACK: "M-Pesa callback", STK_QUERY: "M-Pesa status check", PAYBILL_VALIDATION: "Paybill check", PAYBILL_CONFIRMATION: "Paybill payment",
  PAYBILL_REGISTERED: "Paybill registered", PAYMENT_APPLIED: "Payment applied", PAYMENT_UNMATCHED: "Unmatched payment",
  PAYMENT_UNAPPLIED: "Payment not applied", PAYMENT_ASSIGNED: "Payment assigned", PAYMENT_RECORDED_MANUALLY: "Recorded by hand",
  SUBSCRIPTION_CHANGED: "Subscription changed",
};
const label = kind => KIND_LABELS[kind] || kind;
const when = value => new Date(value).toLocaleString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium", timeStyle: "short" });

function Integrity() {
  const [checking, setChecking] = useState(false);
  const check = useTeachingQuery(checking ? "/api/platform/payment-messages/verify" : null);
  const result = check.data;
  return <div className="payments-integrity">
    <button className="btn" type="button" onClick={() => { setChecking(true); check.refetch?.(); }} disabled={check.isFetching}>{check.isFetching ? "Checking…" : "Check the record is untouched"}</button>
    {result && (result.intact
      ? <p role="status"><span className="billing-dot billing-dot--current" aria-hidden="true" />All {result.checked} entries are intact</p>
      : <p role="alert" className="form-error"><span className="billing-dot billing-dot--frozen" aria-hidden="true" />Entry #{result.first_broken_sequence} does not match its seal. The record was changed outside Skynet.</p>)}
  </div>;
}

function MpesaSetup({ institutions }) {
  const status = useTeachingQuery("/api/platform/mpesa");
  const action = useTeachingMutation();
  const data = status.data;
  return <section className="billing-card" aria-labelledby="mpesa-setup"><h2 id="mpesa-setup">M-Pesa</h2><QueryState query={status} />
    {data && <>
      <dl className="billing-summary">
        <div><dt>Connection</dt><dd><span className={`billing-dot billing-dot--${data.configured ? "current" : "frozen"}`} aria-hidden="true" />{data.configured ? `Connected (${data.environment})` : "Not set up"}</dd></div>
        <div><dt>{data.kind === "TILL" ? "Till number" : "Paybill"}</dt><dd className="billing-figure">{data.number || "Not set"}</dd></div>
      </dl>
      {!data.configured && <p className="billing-muted">Add the Daraja keys on the server to switch on M-Pesa payments.</p>}
      {data.configured && data.kind === "PAYBILL" && <p className="billing-muted">Paybill payments made from the phone menu reach Skynet once the callback addresses are registered with Safaricom.{" "}
        <button className="btn" type="button" disabled={action.isPending} onClick={() => action.mutate({ path: "/api/platform/mpesa/register-paybill" })}>Register paybill</button></p>}
      <MutationState mutation={action} message="Done" />
      <h3 className="payments-subheading">Payments with an unknown account number</h3>
      {data.unmatched.length ? <div className="table-wrapper"><table className="data-table"><thead><tr><th>Receipt</th><th>Paid by</th><th>Account typed</th><th className="billing-num">Amount</th><th>Give to</th></tr></thead>
        <tbody>{data.unmatched.map(t => <tr key={t.id}><td className="billing-figure">{t.receipt}</td><td>{t.payer_name || t.phone || "Unknown"}</td><td className="billing-figure">{t.account_reference || "None"}</td><td className="billing-num">{kes(t.amount)}</td>
          <td><form className="payments-assign" onSubmit={e => { e.preventDefault(); const id = new FormData(e.currentTarget).get("institution_id"); if (id && window.confirm(`Apply ${t.receipt} to this institution? This cannot be undone.`)) action.mutate({ path: `/api/platform/mpesa/transactions/${t.id}/assign`, body: { institution_id: id } }); }}>
            <select name="institution_id" aria-label={`Institution for ${t.receipt}`} required defaultValue=""><option value="" disabled>Choose</option>{institutions.map(i => <option key={i.id} value={i.id}>{i.name} ({i.code})</option>)}</select>
            <button className="btn" disabled={action.isPending}>Apply</button></form></td></tr>)}</tbody></table></div>
        : <p className="billing-muted">None. Every paybill payment matched an institution.</p>}
    </>}
  </section>;
}

function Entry({ sequence, onClose }) {
  const entry = useTeachingQuery(`/api/platform/payment-messages/${sequence}`);
  const data = entry.data;
  return <section className="billing-card payments-entry" aria-labelledby="entry-title">
    <div className="payments-entry-head"><h2 id="entry-title">Entry #{sequence}</h2><button className="btn" type="button" onClick={onClose}>Close</button></div>
    <QueryState query={entry} />
    {data && <>
      <dl className="billing-summary">
        <div><dt>Time (Kenya)</dt><dd>{when(data.created_at)}</dd></div>
        <div><dt>Type</dt><dd>{label(data.kind)}</dd></div>
        <div><dt>Institution</dt><dd>{data.institution_name || "None"}</dd></div>
        <div><dt>Amount</dt><dd className="billing-figure">{data.amount != null ? kes(data.amount) : "None"}</dd></div>
        <div><dt>Reference</dt><dd className="billing-figure">{data.reference || "None"}</dd></div>
      </dl>
      <p>{data.summary}</p>
      <h3 className="payments-subheading">Exactly as received or sent</h3>
      <pre className="payments-payload">{JSON.stringify(data.payload, null, 2)}</pre>
      <p className="billing-muted payments-hash">Seal <span className="billing-figure">{data.entry_hash}</span><br />Previous <span className="billing-figure">{data.previous_hash}</span></p>
    </>}
  </section>;
}

export default function PlatformPaymentsPage() {
  const [filters, setFilters] = useState({});
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(null);
  const [exportError, setExportError] = useState("");
  const directory = useTeachingQuery("/api/platform/institution-directory?offset=0");
  const institutions = directory.data?.items || [];
  const params = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
  const list = useTeachingQuery(`/api/platform/payment-messages?${new URLSearchParams([...params, ["offset", offset]])}`, { refetchInterval: 30000 });
  const data = list.data;

  async function download() {
    setExportError("");
    try {
      const blob = await apiRequest(`/api/platform/payment-messages/export?${params}`, { responseType: "blob" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `skynet-payment-records-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (error) { setExportError(error.message); }
  }

  return <>
    <PageHeading title="Payment records">Every reminder, M-Pesa prompt, callback and applied payment, in the order it happened. Entries cannot be edited or deleted, and each one is sealed to the one before it.</PageHeading>
    <Integrity />
    <form className="payments-filters" onSubmit={e => { e.preventDefault(); setFilters(Object.fromEntries(new FormData(e.currentTarget))); setOffset(0); }}>
      <Field label="Institution" name="institution_id" defaultValue=""><option value="">All institutions</option>{institutions.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}</Field>
      <Field label="Type" name="kind" defaultValue=""><option value="">All types</option>{(data?.kinds || []).map(k => <option key={k} value={k}>{label(k)}</option>)}</Field>
      <Field label="Receipt or text" name="search" maxLength={100} />
      <Field label="From" name="date_from" type="date" />
      <Field label="To" name="date_to" type="date" />
      <div className="payments-filter-actions"><button className="btn btn--primary">Filter</button><button className="btn" type="button" onClick={download}>Download CSV</button></div>
    </form>
    {exportError && <p className="form-error" role="alert">{exportError}</p>}
    {open && <Entry sequence={open} onClose={() => setOpen(null)} />}
    <QueryState query={list} />
    {data && <section className="billing-card"><div className="table-wrapper"><table className="data-table payments-table">
      <thead><tr><th className="billing-num">#</th><th>Time (Kenya)</th><th>Institution</th><th>Type</th><th>Reference</th><th className="billing-num">Amount</th><th>Details</th></tr></thead>
      <tbody>{data.items.map(m => <tr key={m.sequence}><td className="billing-num billing-figure">{m.sequence}</td><td>{when(m.created_at)}</td><td>{m.institution_name || "None"}</td><td>{label(m.kind)}</td>
        <td className="billing-figure">{m.reference || ""}</td><td className="billing-num">{m.amount != null ? kes(m.amount) : ""}</td>
        <td><button className="payments-link" type="button" onClick={() => setOpen(m.sequence)} aria-label={`Open entry ${m.sequence}`}>{m.summary}</button></td></tr>)}</tbody></table></div>
      {!data.items.length && <p className="billing-muted">No entries match these filters.</p>}
      <div className="operations-pagination"><button className="btn" disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{data.total} entries</span><button className="btn" disabled={offset + 50 >= data.total} onClick={() => setOffset(offset + 50)}>Next</button></div>
    </section>}
    <MpesaSetup institutions={institutions} />
  </>;
}
