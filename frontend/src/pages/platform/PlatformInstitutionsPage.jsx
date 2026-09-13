import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import CreateAdminModal from "./CreateAdminModal";
import CreateInstitutionModal from "./CreateInstitutionModal";
import "./PlatformDashboardPage.css";

export default function PlatformInstitutionsPage() {
  const [adminModalInstitution, setAdminModalInstitution] = useState(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);

  const institutionsQuery = useQuery({
    queryKey: ["platform-institutions"],
    queryFn: () => apiRequest("/api/platform/institutions"),
  });

  return (
    <div>
      <div className="section-header">
        <h1 className="page-title" style={{ marginBottom: 0 }}>Institutions</h1>
        <button className="btn btn--primary" onClick={() => setCreateModalOpen(true)}>
          Create institution
        </button>
      </div>

      {institutionsQuery.isLoading && <p>Loading...</p>}
      {institutionsQuery.isError && <p className="page-error">Could not load institutions.</p>}

      {institutionsQuery.data && institutionsQuery.data.length === 0 && (
        <p className="empty-state">No institutions yet.</p>
      )}

      {institutionsQuery.data && institutionsQuery.data.length > 0 && (
        <div className="recent-institutions">
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {institutionsQuery.data.map((inst) => (
                  <tr key={inst.id}>
                    <td>{inst.name}</td>
                    <td>{inst.code}</td>
                    <td>{inst.type.replace("_", " ")}</td>
                    <td>
                      <span className={`status-badge status-badge--${inst.status.toLowerCase()}`}>
                        {inst.status}
                      </span>
                    </td>
                    <td>
                      <button
                        className="table-action-link"
                        onClick={() => setAdminModalInstitution(inst)}
                      >
                        Create admin
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {adminModalInstitution && (
        <CreateAdminModal
          institution={adminModalInstitution}
          onClose={() => setAdminModalInstitution(null)}
        />
      )}

      {createModalOpen && (
        <CreateInstitutionModal onClose={() => setCreateModalOpen(false)} />
      )}
    </div>
  );
}