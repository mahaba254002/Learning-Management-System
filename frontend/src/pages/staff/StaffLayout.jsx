import { Link, Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { STAFF_PAGES, useStaffProfile } from "./staffPages";
import { PageHeading, QueryState } from "../teacher/TeachingUI";
import "../teacher/TeachingWorkspace.css";

export default function StaffLayout() {
  const profile = useStaffProfile();
  const granted = new Set(profile.data?.permissions || []);
  const nav = [{ label: "Dashboard", path: "/staff/dashboard" }, ...STAFF_PAGES.filter(page => granted.has(page.permission))];
  return <DashboardLayout navItems={nav} brandLabel="Staff portal"><Outlet /></DashboardLayout>;
}

export function StaffDashboardPage() {
  const profile = useStaffProfile();
  const data = profile.data;
  const pages = STAFF_PAGES.filter(page => data?.permissions.includes(page.permission));
  return <><PageHeading title={data ? `${data.first_name} ${data.last_name}` : "Staff portal"}>{data?.job_title}{data?.staff_number ? ` · ${data.staff_number}` : ""}</PageHeading>
    <QueryState query={profile} />
    {data && <section className="teaching-panel"><h2>What you can do</h2>
      {pages.length ? <ul>{pages.map(page => <li key={page.path}><Link to={page.path}>{page.label}</Link> · {data.labels[page.permission]}</li>)}</ul>
        : <p>Your administrator has not given you access to any pages yet.</p>}
      <p className="teaching-muted"><Link to="/teacher/change-password">Change password</Link></p>
    </section>}</>;
}

export function RequirePermission({ permission, children }) {
  const profile = useStaffProfile();
  if (!profile.data) return <QueryState query={profile} />;
  if (!profile.data.permissions.includes(permission)) return <p className="form-error" role="alert">You do not have access to this page.</p>;
  return children;
}
