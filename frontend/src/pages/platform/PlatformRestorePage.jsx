import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { Field } from "../teacher/TeachingUI";
import PasswordInput from "../../components/common/PasswordInput";
import NavIcon from "../../components/layout/NavIcon";
import "./PlatformOperations.css";

export default function PlatformRestorePage() {
  const cache = useQueryClient();
  const [file, setFile] = useState(null), [plan, setPlan] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(""), [notice, setNotice] = useState("");
  async function preview(event) {
    event.preventDefault(); setError(""); setNotice(""); setBusy(true); setPlan(null);
    try {
      if (file.size > 512 * 1024 * 1024) throw new Error("Backup file exceeds 512 MB.");
      setPlan(await apiRequest("/api/platform/backups/restore/preview", { method: "POST", rawBody: file }));
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  async function restore(event) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
      const grant = await apiRequest("/api/platform/backups/restore/authorize", { method: "POST", body: { ...values, plan_token: plan.plan_token } });
      form.reset();
      const result = await apiRequest("/api/platform/backups/restore/execute", { method: "POST", rawBody: file, extraHeaders: { "X-Restore-Token": grant.restore_token } });
      setNotice(result.message); setPlan(null); await cache.invalidateQueries();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="platform-operations"><div className="operations-heading"><div><h1><NavIcon name="restore" />Platform Restore</h1><p>Review a signed backup and its destination before recovering records.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}{notice && <p className="teaching-notice" role="status">{notice}</p>}
    <section className="operations-card"><div className="operations-card-heading"><h2>Choose backup</h2></div><div className="operations-card-body"><form className="operations-form" onSubmit={preview}><label htmlFor="restore-file">Original Skynet backup archive (.zip)</label><input id="restore-file" className="operations-file" type="file" accept=".zip,application/zip" required disabled={busy} onChange={e => { setFile(e.target.files[0] || null); setPlan(null); setNotice(""); setError(""); }} /><button className="btn btn--primary" disabled={busy || !file}>{busy ? "Working…" : "Preview restore"}</button></form></div></section>
    {plan && <section className="operations-card"><div className="operations-card-heading"><h2>Review recovery</h2></div><div className="operations-card-body"><p><strong>Destination:</strong> {plan.destination}</p><p><strong>Backup created:</strong> {new Date(plan.created_at).toLocaleString()}</p><div className="operations-warning">{plan.mode}</div>
      {Object.keys(plan.counts).length > 0 && <div className="table-wrapper" role="region" aria-label="Recovery data sets" tabIndex={0}><table className="data-table"><thead><tr><th>Data set</th><th>Records</th></tr></thead><tbody>{Object.entries(plan.counts).map(([name, count]) => <tr key={name}><td>{name.replaceAll('_', ' ')}</td><td>{count}</td></tr>)}</tbody></table></div>}
      <form className="operations-form" onSubmit={restore}><Field label={`Type ${plan.confirmation} to confirm`} name="confirmation" required autoComplete="off" /><label htmlFor="restore-password">Your current platform administrator password</label><PasswordInput id="restore-password" name="password" required autoComplete="current-password" /><button className="btn btn--primary" disabled={busy}>{busy ? "Restoring…" : "Confirm and restore reviewed backup"}</button></form>
    </div></section>}
  </div>;
}
