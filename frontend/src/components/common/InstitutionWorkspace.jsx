import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useTeachingQuery } from "../../pages/teacher/teachingQueries";
import { QueryState } from "../../pages/teacher/TeachingUI";
import { useAuth } from "../../context/useAuth";
import InstitutionBillingPage from "../../pages/institution/InstitutionBillingPage";
import { kes } from "../billing/money";
import "../billing/SubscriptionPayment.css";

function PausedDialog({ state, onPay }) {
  const { logout } = useAuth();
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  const reason = state.manually_frozen ? "Access was paused by the Skynet platform administrator."
    : `The subscription due on ${state.next_due_date} was not paid within the ${state.grace_days}-day grace period.`;
  return <dialog ref={dialog} className="billing-dialog" aria-labelledby="paused-title" onCancel={event => { event.preventDefault(); onPay(); }}>
    <h2 id="paused-title">Access is paused</h2>
    <p>{reason} Your records are safe. Teachers, staff and students cannot use Skynet until payment is received.</p>
    {Number(state.amount_due) > 0 && <p>Amount to pay: <strong className="billing-figure">{kes(state.amount_due)}</strong></p>}
    {state.payment && <p className="billing-muted">{state.payment.kind === "TILL" ? `Till number ${state.payment.number}` : `Paybill ${state.payment.number}, account ${state.payment.account}`}</p>}
    <div className="billing-actions">
      <button className="btn btn--primary" type="button" onClick={() => { dialog.current?.close(); onPay(); }}>Continue to payment</button>
      <button className="btn" type="button" onClick={logout}>Sign out</button>
    </div>
  </dialog>;
}

function FrozenAdmin({ state }) {
  const [paying, setPaying] = useState(false);
  return <>{!paying && <PausedDialog state={state} onPay={() => setPaying(true)} />}<InstitutionBillingPage /></>;
}

function PausedNotice() {
  const { logout } = useAuth();
  return <section className="billing-paused" aria-labelledby="paused-notice">
    <h1 id="paused-notice">Skynet is paused for your institution</h1>
    <p>Your institution's Skynet subscription needs attention, so access is paused for now. Your records, marks and work are kept safe.</p>
    <p>Your institution administrator has been notified. Everything comes back as soon as the subscription is settled, with nothing for you to do.</p>
    <button className="btn" type="button" onClick={logout}>Sign out</button>
  </section>;
}

function DueBanner({ state }) {
  const overdue = state.status === "GRACE";
  return <section className={`billing-banner${overdue ? " billing-banner--overdue" : ""}`} role="status">
    <p>{overdue ? <>Subscription overdue. Access pauses on <strong>{state.freeze_date}</strong> unless {kes(state.amount_due)} is paid.</>
      : <>Subscription of <strong className="billing-figure">{kes(state.amount_due)}</strong> is due on <strong>{state.next_due_date}</strong>.</>}
      {state.payment && <> M-Pesa {state.payment.kind === "TILL" ? `till ${state.payment.number}` : `paybill ${state.payment.number}, account ${state.payment.account}`}.</>}</p>
    <Link className="btn btn--primary" to="/institution/billing">Pay now</Link>
  </section>;
}

export default function InstitutionWorkspace({ children }) {
  const { user, workspace } = useAuth();
  const query = useTeachingQuery("/api/institution/subscription", { refetchInterval: 30000 });
  if (query.isLoading || query.isError) return <QueryState query={query} />;
  const state = query.data;
  const platformVisit = workspace?.actor.role === "PLATFORM_ADMIN";
  const admin = user.role === "INSTITUTION_ADMIN" && !workspace;
  if (state.frozen && platformVisit) return <><p className="teaching-notice">This institution is paused for non-payment. You keep platform administrator access; its own accounts are limited.</p>{children}</>;
  if (state.frozen) return admin ? <FrozenAdmin state={state} /> : <PausedNotice />;
  const due = admin && state.reminder && Number(state.amount_due) > 0;
  return <>{due && <DueBanner state={state} />}{children}</>;
}
