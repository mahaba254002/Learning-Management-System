import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import { apiRequest } from "../../api/client";
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

const GENDER_LABELS = {
    MALE: "Male",
    FEMALE: "Female",
    OTHER: "Other",
    PREFER_NOT_TO_SAY: "Prefer not to say",
};

function InfoRow({ label, value }) {
    return (
        <div style={{ display: "flex", gap: "1rem", padding: "0.75rem 0", borderBottom: "1px solid var(--color-line)" }}>
            <span style={{ minWidth: "160px", fontSize: "0.8rem", color: "var(--color-ink-soft)", textTransform: "uppercase", letterSpacing: "0.04em", paddingTop: "2px" }}>
                {label}
            </span>
            <span style={{ fontSize: "0.9rem", color: "var(--color-ink)" }}>{value}</span>
        </div>
    );
}

export default function InstitutionTeacherDetailPage() {
    const { teacherId } = useParams();

    const { data: teacher, isLoading, isError } = useQuery({
        queryKey: ["institution-teacher", teacherId],
        queryFn: () => apiRequest(`/api/institution/teachers/${teacherId}`),
    });

    return (
        <div>
            {/* Back nav */}
            <Link
                to="/institution/teachers"
                style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", fontSize: "0.85rem", color: "var(--color-ink-soft)", textDecoration: "none", marginBottom: "1.25rem" }}
            >
                ← Back to Teachers
            </Link>

            {isLoading && <p style={{ color: "var(--color-ink-soft)" }}>Loading…</p>}
            {isError && <p className="page-error">Could not load teacher profile.</p>}

            {teacher && (
                <>
                    {/* Header */}
                    <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", marginBottom: "2rem", flexWrap: "wrap" }}>
                        {/* Avatar initials */}
                        <div style={{
                            width: "64px", height: "64px", borderRadius: "50%",
                            background: "var(--color-accent)", color: "#fff",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: "1.4rem", fontWeight: 700, flexShrink: 0,
                        }}>
                            {teacher.first_name[0]}{teacher.last_name[0]}
                        </div>
                        <div>
                            <h1 className="page-title" style={{ marginBottom: "0.2rem" }}>
                                {teacher.first_name} {teacher.last_name}
                            </h1>
                            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
                                <span style={{ color: "var(--color-ink-soft)", fontSize: "0.875rem" }}>@{teacher.username}</span>
                                <span className={`status-badge status-badge--${STATUS_CLASS[teacher.status] ?? "archived"}`}>
                                    {teacher.status.replace("_", " ")}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.25rem" }}>
                        {/* Personal Info */}
                        <div className="recent-institutions" style={{ padding: "1.5rem" }}>
                            <h2 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-ink-soft)" }}>
                                Personal Information
                            </h2>
                            <div style={{ marginTop: "0.5rem" }}>
                                <InfoRow label="Full name" value={`${teacher.first_name} ${teacher.last_name}`} />
                                <InfoRow label="Email" value={teacher.email} />
                                <InfoRow label="Gender" value={GENDER_LABELS[teacher.gender] ?? teacher.gender} />
                                <InfoRow label="Date of birth" value={new Date(teacher.date_of_birth).toLocaleDateString()} />
                                <InfoRow label="Phone" value={teacher.phone || "—"} />
                            </div>
                        </div>

                        {/* Professional Info */}
                        <div className="recent-institutions" style={{ padding: "1.5rem" }}>
                            <h2 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.25rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-ink-soft)" }}>
                                Professional Information
                            </h2>
                            <div style={{ marginTop: "0.5rem" }}>
                                <InfoRow label="Qualification" value={teacher.qualification} />
                                <InfoRow label="Specialization" value={teacher.specialization || "—"} />
                                <InfoRow label="Employment" value={EMPLOYMENT_LABELS[teacher.employment_type] ?? teacher.employment_type} />
                                <InfoRow label="Joined" value={new Date(teacher.joined_at).toLocaleDateString()} />
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
