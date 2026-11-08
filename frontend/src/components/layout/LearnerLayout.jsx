import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";
import { navItemVisible } from "../../modules/institutionModules";
import InstitutionWorkspace from "../common/InstitutionWorkspace";
import ModuleAccess from "../common/ModuleAccess";
import NotificationBell from "./NotificationBell";
import WorkspaceBanner from "./WorkspaceBanner";
import logo from "../../assets/skynet-logo.png";
import "./DashboardLayout.css";
import "./LearnerLayout.css";

/** Student portal frame: a top bar with the main learning links, like a course site, and the rest in the profile menu. */
export default function LearnerLayout({ mainItems, menuItems, children }) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const menu = useRef(null);
  const modules = useQuery({ queryKey: ["teaching", user.id, "/api/institution/modules"], queryFn: () => apiRequest("/api/institution/modules"), refetchInterval: 30000 });
  const visible = items => items.filter(item => navItemVisible(item.path, modules.data?.modules));

  useEffect(() => {
    if (!menuOpen) return undefined;
    const close = event => { if (event.key === "Escape" || (event.type === "mousedown" && !menu.current?.contains(event.target))) setMenuOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [menuOpen]);

  const link = item => <NavLink key={item.path} to={item.path} onClick={() => setMobileOpen(false)} className={({ isActive }) => `learner-nav__link${isActive ? " learner-nav__link--active" : ""}`}>{item.label}</NavLink>;
  return <div className="learner-shell">
    <a className="dashboard-skip-link" href="#workspace-main">Skip to content</a>
    <header className="learner-bar">
      <div className="learner-bar__inner">
        <Link to="/student/dashboard" className="learner-bar__brand"><img src={logo} alt="Skynet" /></Link>
        <nav className="learner-nav" aria-label="Main">{visible(mainItems).map(link)}</nav>
        <div className="learner-bar__tools">
          <NotificationBell />
          <MessagesButton />
          <div className="learner-menu" ref={menu}>
            <button type="button" className="learner-menu__button" aria-expanded={menuOpen} aria-haspopup="true" onClick={() => setMenuOpen(o => !o)}>
              <span className="learner-menu__avatar" aria-hidden="true">{user.first_name[0]}{user.last_name[0]}</span>
              <span className="learner-menu__name">{user.first_name}</span>
              <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="m6 9 6 6 6-6" /></svg>
            </button>
            {menuOpen && <div className="learner-menu__panel">
              <p className="learner-menu__who"><strong>{user.first_name} {user.last_name}</strong><small>{user.username}</small></p>
              {visible(menuItems).map(item => <Link key={item.path} to={item.path} className="learner-menu__item" onClick={() => setMenuOpen(false)}>{item.label}</Link>)}
              <button type="button" className="learner-menu__item learner-menu__logout" onClick={logout}>Log out</button>
            </div>}
          </div>
          <button type="button" className="learner-bar__toggle" aria-expanded={mobileOpen} aria-controls="learner-mobile-nav" onClick={() => setMobileOpen(o => !o)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}>
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
              {mobileOpen ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}</svg>
          </button>
        </div>
      </div>
      {mobileOpen && <nav id="learner-mobile-nav" className="learner-mobile" aria-label="All pages">
        {visible([...mainItems, ...menuItems]).map(link)}
        <button type="button" className="learner-nav__link" onClick={logout}>Log out</button>
      </nav>}
    </header>
    <WorkspaceBanner />
    <main id="workspace-main" tabIndex={-1} className="learner-content" key={user.id}>
      <InstitutionWorkspace><ModuleAccess>{children}</ModuleAccess></InstitutionWorkspace>
    </main>
  </div>;
}

function MessagesButton() {
  const { user } = useAuth();
  const query = useQuery({ queryKey: ["teaching", user.id, "/api/student/messages"], queryFn: () => apiRequest("/api/student/messages"), refetchInterval: 120000 });
  const unread = query.data?.unread || 0;
  return <Link to="/student/messages" className="notification-bell__button learner-messages" aria-label={unread ? `Messages, ${unread} unread` : "Messages"}>
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round">
      <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z" /></svg>
    {unread > 0 && <span className="notification-bell__count">{unread > 99 ? "99+" : unread}</span>}
  </Link>;
}
