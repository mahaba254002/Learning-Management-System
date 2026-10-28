import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import CreateAdminModal from "./CreateAdminModal";
import CreateInstitutionModal from "./CreateInstitutionModal";
import InstitutionAccessControls from "./InstitutionAccessControls";
import NavIcon from "../../components/layout/NavIcon";
import { Field } from "../teacher/TeachingUI";
import "./PlatformOperations.css";

export default function PlatformInstitutionsPage() {
  const [adminInstitution, setAdminInstitution] = useState(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState({ search: "", status: "" });
  const [filters, setFilters] = useState(draft);
  const [offset, setOffset] = useState(0);
  const query = useQuery({ queryKey: ["platform-institutions", "all", filters, offset], queryFn: () => apiRequest(`/api/platform/institution-directory?${new URLSearchParams({ offset, search: filters.search, ...(filters.status ? { status: filters.status } : {}) })}`) });
  return <div className="platform-operations">
    <div className="operations-heading"><div><h1><NavIcon name="institutions" />Institutions</h1><p>Manage institution accounts, administrators and subscription access.</p></div><button className="btn btn--primary" onClick={() => setCreating(true)}>＋ Create institution</button></div>
    <form className="operations-filters" onSubmit={event => { event.preventDefault(); setFilters({ ...draft, search: draft.search.trim() }); setOffset(0); }}>
      <Field label="Search" placeholder="Institution name, code, email or phone" value={draft.search} maxLength={100} onChange={e => setDraft({ ...draft, search: e.target.value })} />
      <Field label="Status" value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })}><option value="">All statuses</option>{["ACTIVE", "SUSPENDED", "ARCHIVED"].map(status => <option key={status}>{status}</option>)}</Field>
      <button className="btn btn--primary" type="submit">Filter</button><button type="button" className="operations-secondary" onClick={() => { const empty = { search: "", status: "" }; setDraft(empty); setFilters(empty); setOffset(0); }}>Clear</button>
    </form>
    {query.isLoading && <p role="status">Loading institutions…</p>}{query.isError && <p role="alert" className="form-error">{query.error.message}</p>}
    {query.data && <section className="operations-card"><div className="operations-card-heading"><h2>Institution accounts</h2><span>{query.data.total} {query.data.total === 1 ? 'institution' : 'institutions'}</span></div><p className="operations-table-hint">Swipe the table horizontally to see contacts, administrators, due dates and actions.</p><div className="table-wrapper" tabIndex={0} role="region" aria-label="Institution accounts table"><table className="data-table"><thead><tr><th>Institution</th><th>Contact</th><th>Administrator</th><th>Due date</th><th>Status / subscription</th><th>Actions</th></tr></thead><tbody>
      {query.data.items.map(inst => <tr key={inst.id}>
        <td><Link className="operations-name" to={`/platform/institutions/${inst.id}`}>{inst.name}</Link><small>{inst.code} · {inst.type.replaceAll("_", " ")}</small></td>
        <td>{inst.official_email ? <a href={`mailto:${inst.official_email}`}>{inst.official_email}</a> : <span>No email</span>}<small>{inst.phone || "No phone"}</small></td>
        <td>{inst.admins?.length ? inst.admins.map(admin => <div key={admin.id} className="operations-admin"><span>{admin.name}</span><small>{admin.email} · {admin.status.toLowerCase()}</small></div>) : <span>Not assigned</span>}</td>
        <td>{inst.next_due_date || "Not configured"}</td><td><span className={`status-badge status-badge--${inst.status.toLowerCase()}`}>{inst.status}</span><small>{inst.subscription_status.replaceAll("_", " ")}</small></td>
        <td><div className="operations-row-actions"><Link to={`/platform/institutions/${inst.id}`}>View details</Link><button className="table-action-link" disabled={inst.status !== "ACTIVE"} onClick={() => setAdminInstitution(inst)}>Create admin</button><InstitutionAccessControls institution={inst} /></div></td>
      </tr>)}
    </tbody></table></div>{!query.data.total && <p className="empty-state">No institutions match these filters.</p>}<div className="operations-pagination"><button disabled={!offset} onClick={() => setOffset(offset - 50)}>Previous</button><span>{query.data.total ? offset + 1 : 0}–{Math.min(offset + 50, query.data.total)} of {query.data.total}</span><button disabled={offset + 50 >= query.data.total} onClick={() => setOffset(offset + 50)}>Next</button></div></section>}
    {creating && <CreateInstitutionModal onClose={() => setCreating(false)} />}{adminInstitution && <CreateAdminModal institution={adminInstitution} onClose={() => setAdminInstitution(null)} />}
  </div>;
}
