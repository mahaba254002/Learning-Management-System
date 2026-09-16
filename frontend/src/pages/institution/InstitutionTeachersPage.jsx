import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { Link } from "react-router-dom";
import "../platform/PlatformDashboardPage.css";

const STATUS_CLASS = {
    ACTIVE: "active",
    ON_LEAVE: "archived",
    SUSPENDED: "suspended",
    TERMINATED: "suspended",
};

const EMPLOYMENT_LABELS = {
    FULL_TIME: "Full-time",
    PART_TIME: "Part-time",
    CONTRACT: "Contract",
    VISITING: "Visiting",
};

export default function InstitutionTeachersPage() {
    const { data: teachers, isLoading, isError } = useQuery({
        queryKey: ["institution-teachers"],
        queryFn: () => apiRequest("/api/institution/teachers"),
    });

    return (
        <div>
            <div className="section-header">
                <h1 className="page-title" style={{ marginBottom: 0 }}>Teachers</h1>
                <Link to="/institution/invitations" className="btn btn--primary" style={{ textDecoration: "none" }}>
                    + Invite teacher
                </Link>
            </div>

            {/* Stats row */}
            {teachers && (
                <div className="stat-cards" style={{ marginTop: "1.5rem" }}>
                    <div className="stat-card">
                        <div className="stat-card__value">{teachers.length}</div>
                        <div className="stat-card__label">Total teachers</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card__value">
                            {teachers.filter((t) => t.status === "ACTIVE").length}
                        </div>
                        <div className="stat-card__label">Active</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card__value">
                            {teachers.filter((t) => t.employment_type === "FULL_TIME").length}
                        </div>
                        <div className="stat-card__label">Full-time</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-card__value">
                            {teachers.filter((t) => t.employment_type === "PART_TIME").length}
                        </div>
                        <div className="stat-card__label">Part-time</div>
                    </div>
                </div>
            )}

            <div className="recent-institutions">
                {isLoading && <p style={{ color: "var(--color-ink-soft)" }}>Loading teachers…</p>}
                {isError && <p className="page-error">Could not load teachers.</p>}

                {teachers && teachers.length === 0 && (
                    <p className="empty-state">
                        No teachers yet.{" "}
                        <Link to="/institution/invitations" style={{ color: "var(--color-accent)" }}>
                            Send an invitation
                        </Link>{" "}
                        to get started.
                    </p>
                )}

                {teachers && teachers.length > 0 && (
                    <div className="table-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Qualification</th>
                                    <th>Specialization</th>
                                    <th>Type</th>
                                    <th>Status</th>
                                    <th>Joined</th>
                                </tr>
                            </thead>
                            <tbody>
                                {teachers.map((t) => (
                                    <tr key={t.id} style={{ cursor: "pointer" }}>
                                        <td>
                                            <Link
                                                to={`/institution/teachers/${t.id}`}
                                                style={{ textDecoration: "none", color: "inherit" }}
                                            >
                                                <strong style={{ color: "var(--color-accent)" }}>{t.first_name} {t.last_name}</strong>
                                                <div style={{ fontSize: "0.75rem", color: "var(--color-ink-soft)" }}>
                                                    @{t.username}
                                                </div>
                                            </Link>
                                        </td>
                                        <td>{t.email}</td>
                                        <td>{t.qualification}</td>
                                        <td>{t.specialization || <span style={{ color: "var(--color-ink-soft)" }}>—</span>}</td>
                                        <td>{EMPLOYMENT_LABELS[t.employment_type] ?? t.employment_type}</td>
                                        <td>
                                            <span className={`status-badge status-badge--${STATUS_CLASS[t.status] ?? "archived"}`}>
                                                {t.status.replace("_", " ")}
                                            </span>
                                        </td>
                                        <td>{new Date(t.joined_at).toLocaleDateString()}</td>
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
