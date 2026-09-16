import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest, ApiError } from "../../api/client";
import "../platform/PlatformDashboardPage.css";

function SendInviteForm({ onSent }) {
    const [email, setEmail] = useState("");
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    const sendMutation = useMutation({
        mutationFn: (email) =>
            apiRequest("/api/institution/invitations/teachers", {
                method: "POST",
                body: { email },
            }),
        onSuccess: () => {
            setSuccess(`Invitation sent to ${email}`);
            setError(null);
            setEmail("");
            onSent();
        },
        onError: (err) => {
            setError(err instanceof ApiError ? err.message : "Failed to send invitation.");
            setSuccess(null);
        },
    });

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!email.trim()) return;
        setError(null);
        setSuccess(null);
        sendMutation.mutate(email.trim());
    };

    return (
        <div className="recent-institutions" style={{ marginBottom: "1.5rem", padding: "1.25rem" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "1rem" }}>Send teacher invitation</h2>
            <form onSubmit={handleSubmit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <input
                    type="email"
                    className="form-input"
                    placeholder="teacher@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    style={{ flex: "1", minWidth: "220px" }}
                />
                <button
                    type="submit"
                    className="btn btn--primary"
                    disabled={sendMutation.isPending}
                >
                    {sendMutation.isPending ? "Sending…" : "Send invite"}
                </button>
            </form>
            {error && <p className="form-error" style={{ marginTop: "0.75rem" }}>{error}</p>}
            {success && <p style={{ marginTop: "0.75rem", color: "var(--color-success, green)" }}>{success}</p>}
        </div>
    );
}

export default function InstitutionInvitationsPage() {
    const [actionError, setActionError] = useState(null);
    const [approvedCredentials, setApprovedCredentials] = useState(null);
    const queryClient = useQueryClient();

    const invitationsQuery = useQuery({
        queryKey: ["institution-invitations"],
        queryFn: () => apiRequest("/api/institution/invitations"),
    });

    const approveMutation = useMutation({
        mutationFn: (id) =>
            apiRequest(`/api/institution/invitations/${id}/approve`, { method: "POST" }),
        onSuccess: (data) => {
            setApprovedCredentials(data);
            setActionError(null);
            queryClient.invalidateQueries({ queryKey: ["institution-invitations"] });
        },
        onError: (err) => {
            setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
        },
    });

    const rejectMutation = useMutation({
        mutationFn: (id) =>
            apiRequest(`/api/institution/invitations/${id}/reject`, { method: "POST" }),
        onSuccess: () => {
            setActionError(null);
            queryClient.invalidateQueries({ queryKey: ["institution-invitations"] });
        },
        onError: (err) => {
            setActionError(err instanceof ApiError ? err.message : "Something went wrong.");
        },
    });

    return (
        <div>
            <h1 className="page-title">Teacher invitations</h1>

            <SendInviteForm
                onSent={() =>
                    queryClient.invalidateQueries({ queryKey: ["institution-invitations"] })
                }
            />

            {actionError && <p className="page-error" style={{ marginBottom: "1rem" }}>{actionError}</p>}

            {approvedCredentials && (
                <div className="recent-institutions" style={{ marginBottom: "1.5rem" }}>
                    <p className="credential-warning">
                        {approvedCredentials.credentials_emailed
                            ? "Credentials were emailed to the teacher. A copy is shown below in case you need to relay them manually."
                            : "We could not email the credentials automatically — please share these with the teacher directly."}
                    </p>
                    <div className="credential-row">
                        <span className="credential-label">Username</span>
                        <code className="credential-value">{approvedCredentials.username}</code>
                    </div>
                    <div className="credential-row">
                        <span className="credential-label">Temporary password</span>
                        <code className="credential-value">{approvedCredentials.temporary_password}</code>
                    </div>
                    <button className="btn btn--primary" onClick={() => setApprovedCredentials(null)}>
                        Done
                    </button>
                </div>
            )}

            {invitationsQuery.isLoading && <p>Loading...</p>}
            {invitationsQuery.isError && <p className="page-error">Could not load invitations.</p>}

            {invitationsQuery.data && invitationsQuery.data.length === 0 && (
                <p className="empty-state">No invitations yet.</p>
            )}

            {invitationsQuery.data && invitationsQuery.data.length > 0 && (
                <div className="recent-institutions">
                    <div className="table-wrapper">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Email</th>
                                    <th>Status</th>
                                    <th>Sent</th>
                                    <th>Expires</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {invitationsQuery.data.map((inv) => (
                                    <tr key={inv.id}>
                                        <td>{inv.email}</td>
                                        <td>
                                            <span className={`status-badge status-badge--${inv.status === "SUBMITTED" ? "active" : inv.status === "REJECTED" ? "suspended" : "archived"}`}>
                                                {inv.status}
                                            </span>
                                        </td>
                                        <td>{new Date(inv.created_at).toLocaleDateString()}</td>
                                        <td>{new Date(inv.expires_at).toLocaleDateString()}</td>
                                        <td>
                                            {inv.status === "SUBMITTED" && (
                                                <div style={{ display: "flex", gap: "0.75rem" }}>
                                                    <button
                                                        className="table-action-link"
                                                        onClick={() => approveMutation.mutate(inv.id)}
                                                        disabled={approveMutation.isPending}
                                                    >
                                                        Approve
                                                    </button>
                                                    <button
                                                        className="table-action-link"
                                                        style={{ color: "#b3261e" }}
                                                        onClick={() => rejectMutation.mutate(inv.id)}
                                                        disabled={rejectMutation.isPending}
                                                    >
                                                        Reject
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}