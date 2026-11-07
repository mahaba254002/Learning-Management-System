import { useTeachingQuery } from "../teacher/teachingQueries";
import { PageHeading, QueryState } from "../teacher/TeachingUI";
import { BillingSummary, HowToPay, MpesaPrompt, PaymentHistory } from "../../components/billing/SubscriptionPayment";

export default function InstitutionBillingPage() {
  const query = useTeachingQuery("/api/institution/subscription");
  const state = query.data;
  return <>
    <PageHeading title="Billing">Skynet subscription, payments and receipts</PageHeading>
    <QueryState query={query} />
    {state && <div className="billing-grid">
      <div>
        <section className="billing-card" aria-labelledby="billing-status"><h2 id="billing-status">Subscription</h2><BillingSummary state={state} /></section>
        <section className="billing-card" aria-labelledby="billing-history"><h2 id="billing-history">Payment history</h2><PaymentHistory payments={state.payments} /></section>
      </div>
      <div>
        {state.payment && <section className="billing-card"><MpesaPrompt suggestedAmount={state.suggested_amount} /></section>}
        <section className="billing-card"><HowToPay payment={state.payment} />
          {state.support_email && <p className="billing-muted">Questions about billing: <a href={`mailto:${state.support_email}`}>{state.support_email}</a></p>}</section>
      </div>
    </div>}
  </>;
}
