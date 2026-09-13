import { useAuth } from "../context/useAuth";

export default function DashboardPlaceholder() {
  const { user, logout } = useAuth();

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>Dashboard</h1>
      <p>Welcome, {user.first_name} {user.last_name} — role: {user.role}</p>
      <button onClick={logout}>Log out</button>
    </div>
  );
}