import { useState } from "react";
import NavIcon from "./NavIcon";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { getRoleHomePath } from "../../routes/roleRoutes";
import logo from "../../assets/skynet-logo.png";
import { useAuth } from "../../context/useAuth";
import InstitutionWorkspace from "../common/InstitutionWorkspace";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import "./DashboardLayout.css";

export default function DashboardLayout({ navItems, children, brandLabel }) {
  const { user, logout, workspace, readOnly, stopWorkspace, isWorkspaceChanging } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const terminology = useQuery({ queryKey: ["teaching", user.id, "/api/institution/learning-settings"], queryFn: () => apiRequest("/api/institution/learning-settings"), enabled: Boolean(user.institution_id), retry: false });
  const labels = terminology.data;
  const plural = label => `${label}${label.endsWith("s") ? "es" : "s"}`;
  const navigationLabel = label => labels ? label.replace(/students/gi, plural(labels.student_label)).replace(/teachers/gi, plural(labels.teacher_label)).replace(/classes/gi, plural(labels.class_label)).replace(/subjects/gi, plural(labels.subject_label)) : label;

  const sidebarContent = (
    <>
      <div className="dashboard-sidebar__primary">
        <div className="dashboard-sidebar__brand">
          <img className="dashboard-brand-image" src={logo} alt="Skynet" />
          <button type="button" className="dashboard-sidebar-toggle"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed} aria-controls="dashboard-desktop-sidebar"
            onClick={() => setCollapsed(value => !value)}>
            <NavIcon name={collapsed ? 'expand-sidebar' : 'collapse-sidebar'} />
          </button>
        </div>

        {brandLabel && <p className="dashboard-sidebar__context">{labels ? brandLabel.replace("Teacher", labels.teacher_label).replace("Student", labels.student_label) : brandLabel}</p>}

        <nav className="dashboard-sidebar__nav" aria-label="Workspace navigation">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
            return (
              <Link
                key={item.path}
                to={item.path}
                aria-current={isActive ? "page" : undefined}
                aria-label={navigationLabel(item.label)}
                title={navigationLabel(item.label)}
                className={`dashboard-sidebar__link ${isActive ? "dashboard-sidebar__link--active" : ""}`}
                onClick={() => setMobileNavOpen(false)}
              >
                <NavIcon name={item.icon || item.path.split('/').at(-1).replace('audit-logs', 'audit')} /><span>{navigationLabel(item.label)}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="dashboard-sidebar__account">
        <div className="dashboard-sidebar__user">
          <span className="dashboard-sidebar__avatar" aria-hidden="true">{user.first_name[0]}{user.last_name[0]}</span>
          <span className="dashboard-sidebar__name">{user.first_name} {user.last_name}</span>
          <span className="dashboard-sidebar__role">{user.role.replace("_", " ")}</span>
        </div>
        <button className="dashboard-sidebar__logout" onClick={logout} aria-label="Log out" title="Log out">
          <NavIcon name="logout" /><span>Log out</span>
        </button>
      </div>
    </>
  );

  return (
    <div className={`dashboard-shell ${collapsed ? 'dashboard-shell--collapsed' : ''}`} onKeyDown={event => { if (event.key === 'Escape') { setMobileNavOpen(false); document.querySelector('.dashboard-topbar__menu-btn')?.focus(); } }}>
      <a className="dashboard-skip-link" href="#workspace-main">Skip to workspace</a>
      <aside id="dashboard-desktop-sidebar" className="dashboard-sidebar dashboard-sidebar--desktop">
        {sidebarContent}
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <span className="dashboard-topbar__context">{user.role.replaceAll('_', ' ').toLowerCase()}</span>
          <button
            className="dashboard-topbar__menu-btn"
            aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileNavOpen}
            aria-controls="dashboard-mobile-navigation"
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            <span className="dashboard-topbar__menu-icon" />
          </button>
          <span className="dashboard-topbar__brand-mobile">Skynet</span>
        </header>

        {mobileNavOpen && (
          <div id="dashboard-mobile-navigation" className="dashboard-sidebar dashboard-sidebar--mobile" aria-label="Mobile navigation">
            {sidebarContent}
          </div>
        )}

        {workspace && <section className={`workspace-access-banner ${readOnly ? "" : "workspace-access-banner--full"}`} aria-label="Delegated workspace access">
          <div><strong>{readOnly ? "Read-only view" : "Full access"}: {user.first_name} {user.last_name}</strong>
            <p>Signed in as {workspace.actor.first_name} {workspace.actor.last_name}. {readOnly ? "Changes are blocked." : "Actions are recorded under your platform administrator account."}</p></div>
          <button type="button" disabled={isWorkspaceChanging} onClick={async () => {
            const actor = await stopWorkspace();
            navigate(getRoleHomePath(actor?.role), { replace: true });
          }}>{isWorkspaceChanging ? "Returning…" : "Return to my workspace"}</button>
        </section>}
        <main id="workspace-main" tabIndex={-1} className="dashboard-content" key={`${user.id}:${readOnly}`}>{user.institution_id ? <InstitutionWorkspace>{children}</InstitutionWorkspace> : children}</main>
      </div>
    </div>
  );
}
