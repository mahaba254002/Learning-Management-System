import { useAuth } from "../context/useAuth";

export default function RoleHoldingPage() {
  const { user, logout } = useAuth();

  return (
    <div style={{ padding: "2rem", fontFamily: "var(--font-body)", maxWidth: "480px", margin: "4rem auto", textAlign: "center" }}>
      <h1 style={{ fontFamily: "var(--font-display)", fontSize: "1.5rem", marginBottom: "0.5rem" }}>
        Welcome, {user.first_name}
      </h1>
      <p style={{ color: "var(--color-ink-soft)", marginBottom: "1.5rem" }}>
        Your {user.role.replace("_", " ").toLowerCase()} dashboard is being built. Check back soon.
      </p>
      <button className="btn btn--secondary" onClick={logout}>Log out</button>
    </div>
  );
}