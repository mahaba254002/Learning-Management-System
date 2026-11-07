import { useAuth } from "../../context/useAuth";

/** Shown while checking the session. Explains a slow start instead of failing or signing people out. */
export default function ConnectionScreen() {
  const { connection, retryConnection } = useAuth();
  if (connection === "unreachable") return <main className="connection-screen" role="alert">
    <h1>Can't reach Skynet</h1>
    <p>Check your internet connection. If it's working, Skynet may be restarting; try again in a minute.</p>
    <button type="button" className="btn btn--primary" onClick={retryConnection}>Try again</button>
  </main>;
  return <main className="connection-screen" role="status">
    {connection === "waking" ? <><h1>Starting Skynet</h1><p>This can take up to a minute after a quiet period. You don't need to do anything.</p></> : <p>Loading…</p>}
  </main>;
}
