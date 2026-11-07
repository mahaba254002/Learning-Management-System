import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../../pages/teacher/teachingQueries";
import { Field, MutationState } from "../../pages/teacher/TeachingUI";
import "./SubscriptionPayment.css";
import { kes } from "./money";


export function HowToPay({ payment }) {
  if (!payment) return <p className="billing-muted">M-Pesa payments are not set up yet. Contact the platform administrator for payment details.</p>;
  const till = payment.kind === "TILL";
  return <div className="billing-steps">
    <h3>Pay from any M-Pesa phone</h3>
    <ol>
      <li>Open M-Pesa and choose Lipa na M-Pesa</li>
      <li>{till ? "Choose Buy Goods and Services" : "Choose Pay Bill"}</li>
      <li>{till ? "Till number" : "Business number"} <strong className="billing-figure">{payment.number}</strong></li>
      {!till && <li>Account number <strong className="billing-figure">{payment.account}</strong></li>}
      <li>Enter the amount and your M-Pesa PIN</li>
    </ol>
    <p className="billing-muted">Access is restored automatically once M-Pesa confirms the payment.</p>
  </div>;
}

export function MpesaPrompt({ suggestedAmount }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const start = useTeachingMutation();
  const [promptId, setPromptId] = useState(null);
  const status = useTeachingQuery(promptId ? `/api/institution/billing/mpesa/prompt/${promptId}` : null,
    { refetchInterval: query => query.state.data?.status === "PENDING" || !query.state.data ? 4000 : false });
  const result = status.data?.status;
  useEffect(() => {
    if (result === "PAID") queryClient.invalidateQueries({ queryKey: ["teaching", user.id] });
  }, [result, queryClient, user.id]);

  function submit(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    start.mutate({ path: "/api/institution/billing/mpesa/prompt", body: { phone: values.phone, amount: Number(values.amount) } },
      { onSuccess: data => setPromptId(data.id) });
  }

  if (promptId && result !== "FAILED") return <div className="billing-prompt" role="status" aria-live="polite">
    {result === "PAID"
      ? <><h3>Payment received</h3><p>M-Pesa receipt <strong className="billing-figure">{status.data.mpesa_receipt || "pending"}</strong>. Paid until {status.data.subscription.next_due_date}.</p></>
      : <><h3>Check your phone</h3><p>Enter your M-Pesa PIN on {status.data?.phone || "your phone"} to pay {kes(status.data?.amount)}. This page updates on its own.</p></>}
  </div>;

  return <form className="billing-form" onSubmit={submit}>
    <h3>Get a payment prompt on your phone</h3>
    {result === "FAILED" && <p className="form-error" role="alert">The payment did not go through: {status.data.result_description || "no answer from M-Pesa"}. You can try again.</p>}
    <Field label="Safaricom number" name="phone" type="tel" inputMode="tel" autoComplete="tel" placeholder="0712 345 678" required />
    <Field label="Amount (KES)" name="amount" type="number" min="1" max="250000" step="1" required defaultValue={suggestedAmount || ""} />
    <button className="btn btn--primary" disabled={start.isPending}>{start.isPending ? "Sending prompt…" : "Pay with M-Pesa"}</button>
    <MutationState mutation={start} message="Prompt sent" />
  </form>;
}

export function PaymentHistory({ payments }) {
  if (!payments?.length) return <p className="billing-muted">No payments recorded yet.</p>;
  return <div className="table-wrapper"><table className="data-table billing-table"><thead><tr><th>Paid on</th><th>Reference</th><th>Method</th><th className="billing-num">Amount</th><th>Paid until</th></tr></thead>
    <tbody>{payments.map(p => <tr key={p.id}><td>{p.paid_on}</td><td className="billing-figure">{p.reference}</td><td>{p.source === "MPESA" ? "M-Pesa" : "Recorded by Skynet"}</td><td className="billing-num">{kes(p.amount)}</td><td>{p.next_due_date}</td></tr>)}</tbody></table></div>;
}

export function BillingSummary({ state }) {
  const label = { CURRENT: "Paid up", GRACE: "Overdue", FROZEN: "Access paused", DISABLED: "Not billed", NOT_CONFIGURED: "Not billed" }[state.status];
  return <dl className="billing-summary">
    <div><dt>Status</dt><dd><span className={`billing-dot billing-dot--${state.status.toLowerCase()}`} aria-hidden="true" />{label}</dd></div>
    <div><dt>Amount to pay now</dt><dd className="billing-figure billing-figure--large">{kes(state.amount_due)}</dd></div>
    <div><dt>Monthly fee</dt><dd className="billing-figure">{kes(state.monthly_fee)}</dd></div>
    <div><dt>Next due</dt><dd>{state.next_due_date || "Not set"}</dd></div>
    {Number(state.credit_balance) > 0 && <div><dt>Credit carried forward</dt><dd className="billing-figure">{kes(state.credit_balance)}</dd></div>}
  </dl>;
}
