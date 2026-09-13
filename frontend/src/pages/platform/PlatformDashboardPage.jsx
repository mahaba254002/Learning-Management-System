import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiRequest } from "../../api/client";
import "./PlatformDashboardPage.css";

export default function PlatformDashboardPage() {
  const statsQuery = useQuery({
    queryKey: ["platform-stats"],
    queryFn: () => apiRequest("/api/platform/stats"),
  });

  const institutionsQuery = useQuery({
    queryKey: ["platform-institutions"],
    queryFn: () => apiRequest("/api/platform/institutions"),
  });

  return (
    <div>
      <h1 className="page-title">Platform overview</h1>

      {statsQuery.isLoading && <p>Loading stats...</p>}
      {statsQuery.isError && <p className="page-error">Could not load platform stats.</p>}

      {statsQuery.data && (
        <div className="stat-cards">
          <StatCard label="Total institutions" value={statsQuery.data.total_institutions} />
          <StatCard label="Active institutions" value={statsQuery.data.active_institutions} />
          <StatCard label="Archived institutions" value={statsQuery.data.archived_institutions} />
          <StatCard label="Total users" value={statsQuery.data.total_users} />
        </div>
      )}

      {statsQuery.data && Object.keys(statsQuery.data.users_by_role).length > 0 && (
        <div className="role-breakdown">
          <h2 className="section-title">Users by role</h2>
          <div className="stat-cards">
            {Object.entries(statsQuery.data.users_by_role).map(([role, count]) => (
              <StatCard key={role} label={role.replace("_", " ")} value={count} />
            ))}
          </div>
        </div>
      )}

      <div className="recent-institutions">
        <div className="section-header">
          <h2 className="section-title">Recently added institutions</h2>
          <Link to="/platform/institutions" className="section-link">View all</Link>
        </div>

        {institutionsQuery.isLoading && <p>Loading...</p>}
        {institutionsQuery.isError && <p className="page-error">Could not load institutions.</p>}

        {institutionsQuery.data && institutionsQuery.data.length === 0 && (
          <p className="empty-state">No institutions yet.</p>
        )}

        {institutionsQuery.data && institutionsQuery.data.length > 0 && (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {institutionsQuery.data.slice(0, 5).map((inst) => (
                  <tr key={inst.id}>
                    <td>{inst.name}</td>
                    <td>{inst.code}</td>
                    <td>{inst.type.replace("_", " ")}</td>
                    <td>
                      <span className={`status-badge status-badge--${inst.status.toLowerCase()}`}>
                        {inst.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <p className="stat-card__value">{value}</p>
      <p className="stat-card__label">{label}</p>
    </div>
  );
}