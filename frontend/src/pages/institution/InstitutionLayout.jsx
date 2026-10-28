import { Outlet } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { institutionNavItems } from "./institutionNavItems";
import { useAcademicNavigation } from '../../hooks/useAcademicNavigation';

export default function InstitutionLayout() {
    const nav = useAcademicNavigation(institutionNavItems);
    return (
        <DashboardLayout navItems={nav}>
            <Outlet />
        </DashboardLayout>
    );
}
