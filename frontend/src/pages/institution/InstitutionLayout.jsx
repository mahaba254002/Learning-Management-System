import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { institutionNavItems } from "./institutionNavItems";

export default function InstitutionLayout() {
    return (
        <DashboardLayout navItems={institutionNavItems}>
            <Outlet />
        </DashboardLayout>
    );
}