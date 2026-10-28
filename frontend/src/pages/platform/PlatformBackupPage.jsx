import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { Field } from "../teacher/TeachingUI";
import NavIcon from "../../components/layout/NavIcon";
import "./PlatformOperations.css";

const groups = { people: "Accounts, staff and student profiles (required)", academics: "Classes, subjects and enrollment (required)", learning: "Materials, assignments, submissions and marks", attendance: "Attendance records", billing: "Subscription and payment records" };

export default function PlatformBackupPage() {
  const [institutionId, setInstitutionId] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(Object.keys(groups));
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const capabilities = useQuery({ queryKey: ["backup-capabilities"], queryFn: () => apiRequest("/api/platform/backups/capabilities") });
  const institutions = useQuery({ queryKey: ["backup-institutions", search], queryFn: () => apiRequest(`/api/platform/institution-directory?${new URLSearchParams({ search, limit: 100 })}`) });
  async function download(kind) {
    setBusy(kind); setError(""); setNotice("");
    try {
      const blob = await apiRequest(`/api/platform/backups/${kind}`, { method: "POST", ...(kind === "institution" ? { body: { institution_id: institutionId, groups: selected } } : {}), responseType: "blob" });
      const url = URL.createObjectURL(blob), link = document.createElement("a");
      link.href = url; link.download = `skynet-${kind}-backup.zip`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Backup generated. Your browser download has started.");
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  }
  return <div className="platform-operations"><div className="operations-heading"><div><h1><NavIcon name="backup" />Platform Backup</h1><p>Export one institution or a consistent snapshot of the platform database.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="teaching-notice" role="status">{notice}</p>}
    {capabilities.isError && <p role="alert">{capabilities.error.message}</p>}
    {capabilities.data && !capabilities.data.institution_backup && <p className="operations-warning" role="status">Configure a backup signing key on the API server to enable exports and recovery.</p>}
    <div className="operations-grid"><section className="operations-card"><div className="operations-card-heading"><h2><NavIcon name="backup" />Institution Backup</h2></div><div className="operations-card-body"><p>Export selected institution records in a signed portable archive. Core accounts and academic relationships are included to keep the data connected.</p>
      <form className="operations-form" onSubmit={event => { event.preventDefault(); download("institution"); }}>
        <Field label="Find institution" placeholder="Search name, code or email" value={search} onChange={e => { setSearch(e.target.value); setInstitutionId(""); }} />
        <Field label="Institution" required value={institutionId} onChange={e => setInstitutionId(e.target.value)}><option value="">Select an institution</option>{institutions.data?.items.map(inst => <option key={inst.id} value={inst.id}>{inst.name} ({inst.code})</option>)}</Field>
        {institutions.isError && <p role="alert">{institutions.error.message}</p>}
        <fieldset className="operations-checks"><legend>Include</legend><label><input type="checkbox" checked={selected.length === Object.keys(groups).length} onChange={e => setSelected(e.target.checked ? Object.keys(groups) : ["people", "academics"])} />All data sets</label>
          {Object.entries(groups).map(([key, label]) => <label key={key}><input type="checkbox" disabled={["people", "academics"].includes(key)} checked={selected.includes(key)} onChange={e => setSelected(old => e.target.checked ? [...old, key] : old.filter(item => item !== key))} />{label}</label>)}</fieldset>
        <button className="btn btn--primary" disabled={Boolean(busy) || !capabilities.data?.institution_backup}>{busy === "institution" ? "Preparing backup…" : "Download institution backup"}</button>
      </form></div></section>
      <section className="operations-card"><div className="operations-card-heading"><h2><NavIcon name="billing" />Full Platform Backup</h2></div><div className="operations-card-body"><p>Download a signed PostgreSQL snapshot containing every institution and platform record.</p><button className="operations-download" disabled={Boolean(busy) || !capabilities.data?.full_backup} onClick={() => download("platform")}>{busy === "platform" ? "Preparing database snapshot…" : "Download full database"}</button>
        {capabilities.data && !capabilities.data.full_backup && <p role="status">Full backup requires PostgreSQL backup tools and a backup signing key on the API server.</p>}
        <div className="operations-warning">Backups contain private records and account password hashes. Store downloads securely. Signing verifies authenticity; it does not encrypt the file.</div>
        <h3>After downloading</h3><ol><li>Keep the archive and its signing key safely.</li><li>Use Restore to review and recover a signed archive.</li><li>Full snapshots recover into a separate empty PostgreSQL database for verification.</li></ol>
      </div></section></div>
  </div>;
}
