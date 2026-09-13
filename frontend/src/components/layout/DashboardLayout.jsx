import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import "./DashboardLayout.css";

export default function DashboardLayout({ navItems, children, brandLabel }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const sidebarContent = (
    <>
      <div>
        <div className="dashboard-sidebar__brand">
          <span className="dashboard-sidebar__logo" aria-hidden="true" />
          <span>Rollcall</span>
        </div>

        {brandLabel && <p className="dashboard-sidebar__context">{brandLabel}</p>}

        <nav className="dashboard-sidebar__nav">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`dashboard-sidebar__link ${isActive ? "dashboard-sidebar__link--active" : ""}`}
                onClick={() => setMobileNavOpen(false)}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="dashboard-sidebar__account">
        <div className="dashboard-sidebar__user">
          <span className="dashboard-sidebar__name">{user.first_name} {user.last_name}</span>
          <span className="dashboard-sidebar__role">{user.role.replace("_", " ")}</span>
        </div>
        <button className="dashboard-sidebar__logout" onClick={logout}>
          Log out
        </button>
      </div>
    </>
  );

  return (
    <div className="dashboard-shell">
      <aside className="dashboard-sidebar dashboard-sidebar--desktop">
        {sidebarContent}
      </aside>

      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <button
            className="dashboard-topbar__menu-btn"
            aria-label={mobileNavOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            <span className="dashboard-topbar__menu-icon" />
          </button>
          <span className="dashboard-topbar__brand-mobile">Rollcall</span>
        </header>

        {mobileNavOpen && (
          <div className="dashboard-sidebar dashboard-sidebar--mobile">
            {sidebarContent}
          </div>
        )}

        <main className="dashboard-content">{children}</main>
      </div>
    </div>
  );
}