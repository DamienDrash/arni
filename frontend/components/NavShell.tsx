"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import { getStoredUser } from "@/lib/auth";
import { usePermissions } from "@/lib/permissions";
import { getRouteAccessState } from "@/lib/route-access";
import styles from "./NavShell.module.css";

export default function NavShell({ children }: { children: React.ReactNode }) {
    const [mobileOpen, setMobileOpen] = useState(false);
    const pathname = usePathname();
    const router = useRouter();

    // Close mobile drawer on route change
    useEffect(() => {
        setMobileOpen(false);
    }, [pathname]);

    // Prevent body scroll when mobile drawer is open
    useEffect(() => {
        if (mobileOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [mobileOpen]);

    const toggleMobile = useCallback(() => {
        setMobileOpen((prev) => !prev);
    }, []);

    const closeMobile = useCallback(() => {
        setMobileOpen(false);
    }, []);

    const [authReady, setAuthReady] = useState(false);
    const { role, canPage, feature, loading: permissionsLoading } = usePermissions();

    useEffect(() => {
        const publicPaths = ["/", "/features", "/pricing", "/login", "/register", "/legal", "/impressum", "/datenschutz", "/agb", "/forgot-password", "/reset-password", "/verify-email", "/accept-invitation", "/mfa-verify", "/subscribe", "/unsubscribe", "/optin-confirm"];
        const isPublic = publicPaths.some(p => (pathname || "/").startsWith(p) && (p !== "/" || (pathname || "/") === "/"));

        const cached = getStoredUser();
        if (cached) {
            setAuthReady(true);
        } else if (isPublic) {
            setAuthReady(true);
        } else {
            router.replace("/login");
        }
    }, [router, pathname]);

    if (!authReady) return null;

    const publicPaths = ["/", "/features", "/pricing", "/login", "/register", "/legal", "/impressum", "/datenschutz", "/agb", "/forgot-password", "/reset-password", "/verify-email", "/accept-invitation", "/mfa-verify", "/subscribe", "/unsubscribe", "/optin-confirm"];
    const isPublic = publicPaths.some(p => (pathname || "/").startsWith(p) && (p !== "/" || (pathname || "/") === "/"));

    if (isPublic) {
        return <>{children}</>;
    }

    const routeAccess = permissionsLoading
        ? "available"
        : getRouteAccessState(pathname || "/", { role, canPage, feature });

    useEffect(() => {
        if (routeAccess === "hidden") {
            router.replace("/dashboard");
        }
    }, [routeAccess, router]);

    if (routeAccess === "hidden") return null;

    return (
        <div className={styles.root}>
            {/* Desktop Sidebar – hidden on mobile via CSS */}
            <div className={styles.desktopSidebar}>
                <Sidebar />
            </div>

            {/* Mobile Top Bar – visible only on mobile */}
            <div className={styles.mobileTopbar}>
                <button
                    className={styles.menuButton}
                    onClick={toggleMobile}
                    aria-label="Toggle navigation"
                >
                    {mobileOpen ? <X size={22} /> : <Menu size={22} />}
                </button>
                <span className={styles.brand}>
                    ARIIA<span className={styles.brandDot}>.</span>
                </span>
                <div style={{ width: 34 }} /> {/* Spacer for centering */}
            </div>

            {/* Mobile Backdrop – click to close */}
            {mobileOpen && (
                <div
                    className={styles.mobileBackdrop}
                    onClick={closeMobile}
                    aria-hidden="true"
                />
            )}

            {/* Mobile Drawer – slides in from left */}
            <div
                className={`${styles.mobileDrawer} ${mobileOpen ? styles.mobileDrawerOpen : styles.mobileDrawerClosed}`}
            >
                <Sidebar />
            </div>

            {/* Main Content */}
            <main className={styles.appMain}>
                {routeAccess === "coming_soon" ? (
                    <FeatureStatePanel
                        title="Coming Soon"
                        description="Dieses Modul ist im aktuellen Product Core dormitisiert und wird nach der Modularisierung wieder gezielt aktiviert."
                    />
                ) : routeAccess === "upgrade" ? (
                    <FeatureStatePanel
                        title="Upgrade Required"
                        description="Diese Funktion ist in Ihrer aktuellen Konfiguration nicht freigeschaltet. Nutzen Sie das Billing, um den Zugriff zu erweitern."
                    />
                ) : (
                    children
                )}
            </main>
        </div>
    );
}

function FeatureStatePanel({ title, description }: { title: string; description: string }) {
    return (
        <section className={styles.statePanel}>
            <div className={styles.stateBadge}>{title}</div>
            <h1 className={styles.stateTitle}>{title}</h1>
            <p className={styles.stateText}>{description}</p>
        </section>
    );
}
