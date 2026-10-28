import { useState } from "react";
import { Link } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Field, QueryState } from "../teacher/TeachingUI";
import RecordChart from "../../components/common/RecordChart";
import NavIcon from "../../components/layout/NavIcon";
import "./PlatformOperations.css";

export default function PlatformBillingPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const summary = useTeachingQuery("/api/platform/subscription-summary", { refetchInterval: 30000 });
  const directory = useTeachingQuery(`/api/platform/institution-directory?${new URLSearchParams({ search: filter, offset })}`, { refetchInterval: 30000 });
  return <div className="platform-operations"><div className="operations-heading"><div><h1><NavIcon name="billing" />Billing</h1><p>Monthly subscriptions, due dates and verified manual payment records.</p></div></div><QueryState query={summary} />
    {summary.data && <><div className="stat-cards"><div className="stat-card"><p className="stat-card__value">KES {Number(summary.data.payments_recorded_this_month).toLocaleString()}</p><p className="stat-card__label">Payments recorded this month</p></div><div className="stat-card"><p className="stat-card__value">{summary.data.subscription_status.GRACE}</p><p className="stat-card__label">In grace period</p></div><div className="stat-card"><p className="stat-card__value">{summary.data.subscription_status.FROZEN}</p><p className="stat-card__label">Frozen subscriptions</p></div></div><RecordChart title="Subscription access" entries={Object.entries(summary.data.subscription_status)} /></>}
    <form className="operations-filters" onSubmit={e => { e.preventDefault(); setFilter(search); setOffset(0); }}><Field label="Find institution" placeholder="Name, code, email or phone" value={search} onChange={e => setSearch(e.target.value)} /><button className="btn btn--primary">Search</button><button className="operations-secondary" type="button" onClick={() => { setSearch(""); setFilter(""); setOffset(0); }}>Clear</button></form><QueryState query={directory} />
    {directory.data && <section className="operations-card"><div className="table-wrapper"><table className="data-table"><thead><tr><th>Institution</th><th>Contact</th><th>Next due</th><th>Access</th><th>Billing</th></tr></thead><tbody>{directory.data.items.map(inst => <tr key={inst.id}><td>{inst.name}<small>{inst.code}</small></td><td>{inst.official_email || "No email"}</td><td>{inst.next_due_date || "Not configured"}</td><td>{inst.subscription_status.replaceAll('_', ' ')}</td><td><Link to={`/platform/institutions/${inst.id}`}>Manage subscription / payments</Link></td></tr>)}</tbody></table></div><div className="operations-pagination"><button disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{directory.data.total} institutions</span><button disabled={offset + 50 >= directory.data.total} onClick={() => setOffset(offset + 50)}>Next</button></div></section>}
  </div>;
}
