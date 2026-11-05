import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest, ApiError } from "../../api/client";
import PasswordInput from "../../components/common/PasswordInput";
import "./LoginPage.css";

// The token is in the URL fragment, so it never reaches a server log.
function readToken() {
  return new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
}

export default function SetPasswordPage() {
  const [token] = useState(readToken);
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!token) return;
    // Drop the token from the address bar once read.
    window.history.replaceState(null, "", window.location.pathname);
    apiRequest("/api/auth/set-password/check", { method: "POST", body: { token }, workspace: false, retrySession: false })
      .then(setAccount)
      .catch(err => setError(err instanceof ApiError ? err.message : "Could not check this link. Try again."));
  }, [token]);

  async function submit(event) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (values.new_password !== values.confirm_password) { setError("Passwords do not match"); return; }
    setPending(true); setError("");
    try {
      setDone(await apiRequest("/api/auth/set-password", { method: "POST", body: { token, ...values }, workspace: false, retrySession: false }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setPending(false);
    }
  }

  if (!token) return <Notice title="Link incomplete">Open the link from your email again, or ask your administrator for a new one.</Notice>;
  if (done) return <Notice title="Password set">You can now sign in with your username or email. <Link to={done.login_path}>Go to sign in</Link></Notice>;
  if (!account) return <Notice title="Set your password">{error || "Checking your link…"}</Notice>;

  return <div className="auth-page"><form className="auth-form" onSubmit={submit}>
    <h1>Set your password</h1>
    <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem", fontSize: "var(--text-sm)" }}>
      {account.first_name}, choose a password for your {account.institution_name || "Skynet"} account. Your username is <strong>{account.username}</strong>.
    </p>
    <div className="form-field"><label htmlFor="new_password">New password</label><PasswordInput id="new_password" name="new_password" autoComplete="new-password" required /></div>
    <div className="form-field"><label htmlFor="confirm_password">Confirm new password</label><PasswordInput id="confirm_password" name="confirm_password" autoComplete="new-password" required /></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button type="submit" disabled={pending}>{pending ? "Saving…" : "Set password"}</button>
  </form></div>;
}

function Notice({ title, children }) {
  return <div className="auth-page"><div className="auth-form"><h1>{title}</h1><p style={{ color: "var(--color-ink-soft)" }}>{children}</p></div></div>;
}
