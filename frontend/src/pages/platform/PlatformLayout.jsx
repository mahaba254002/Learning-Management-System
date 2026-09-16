import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { platformNavItems } from "./platformNavItems";

export default function PlatformLayout() {
  return (
    <DashboardLayout navItems={platformNavItems}>
      <Outlet />
    </DashboardLayout>
  );
}