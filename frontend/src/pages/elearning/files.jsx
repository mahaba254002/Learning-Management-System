import { useId, useState } from "react";
import { apiRequest } from "../../api/client";
import { describe } from "../../api/errors";
import { ALL, MAX_BYTES, fileSize } from "./format";
import "./Elearning.css";

/** Opens a stored file. Links are short-lived, so a fresh one is fetched on each click. */
export function FileLink({ file, children }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!file) return null;
  async function open() {
    setError("");
    // Open the tab first so the browser does not treat it as an unwanted pop-up.
    const tab = window.open("", "_blank");
    setBusy(true);
    try {
      const { url } = await apiRequest(`/api/files/${file.id}`);
      if (tab) { tab.opener = null; tab.location.href = url; } else window.location.assign(url);
    } catch (err) {
      tab?.close();
      setError(describe(err).text);
    } finally { setBusy(false); }
  }
  return <span className="file-link">
    <button type="button" className="file-link__button" onClick={open} disabled={busy}>{children || file.filename}</button>
    <span className="teaching-muted"> {fileSize(file.size_bytes)}</span>
    {error && <span className="form-error" role="alert"> {error}</span>}
  </span>;
}

/** Uploads one file straight away and reports it with onUploaded(file). */
export function FileUpload({ label, path, accept = ALL, hint, current, onUploaded, onRemove, disabled }) {
  const id = useId();
  const [state, setState] = useState({ busy: false, error: "" });
  async function choose(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_BYTES) { setState({ busy: false, error: "Use a file of 10 MB or less." }); return; }
    setState({ busy: true, error: "" });
    try {
      const saved = await apiRequest(`${path}${path.includes("?") ? "&" : "?"}filename=${encodeURIComponent(file.name)}`, { method: "POST", rawBody: file });
      setState({ busy: false, error: "" });
      onUploaded(saved);
    } catch (err) {
      // Storage not being connected is a setup issue, not a slow start.
      setState({ busy: false, error: /not set up/.test(err.message || "") ? err.message : describe(err, { saving: true }).text });
    }
  }
  return <div className="form-field file-upload">
    <label htmlFor={id}>{label}</label>
    {current && <p className="file-upload__current"><FileLink file={current} />{onRemove && <button type="button" className="file-upload__remove" onClick={onRemove} disabled={disabled}>Remove</button>}</p>}
    <input id={id} type="file" accept={accept} onChange={choose} disabled={disabled || state.busy} />
    <p className="teaching-muted">{state.busy ? "Uploading…" : hint || "Up to 10 MB."}</p>
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
  </div>;
}
