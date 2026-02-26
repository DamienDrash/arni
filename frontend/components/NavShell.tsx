"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import { getStoredUser, setStoredUser, type AuthUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/LanguageContext";
import styles from "./NavShell.module.css";

export default function NavShell({ children }: { children: React.ReactNode }) {
    const { t, language } = useI18n();
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

    // DYNAMIC META: Re-evaluates every time the language changes!
    const pageMeta = useMemo(() => ({
        "/": { title: t("common.welcome"), subtitle: "" },
        "/dashboard": { title: t("common.dashboard"), subtitle: "" },
        "/live": { title: t("sidebar.monitor"), subtitle: "" },
        "/members": { title: t("sidebar.members"), subtitle: "" },
        "/tenants": { title: t("sidebar.tenants"), subtitle: "" },
        "/audit": { title: t("sidebar.audit"), subtitle: "" },
        "/settings": { title: t("common.settings"), subtitle: "" },
        "/settings/account": { title: t("settings.account.title"), subtitle: t("settings.account.subtitle") },
        "/settings/general": { title: t("settings.general.title"), subtitle: t("settings.general.subtitle") },
        "/settings/ai": { title: t("settings.aiEngine"), subtitle: "" },
        "/login": { title: t("common.login"), subtitle: "" },
    }), [t, language]); // Dependency on language is CRITICAL

    const currentMeta = useMemo(() => {
        const path = pathname || "/";
        return pageMeta[path as keyof typeof pageMeta] || { title: "ARIIA", subtitle: "" };
    }, [pathname, pageMeta]);

    const [authReady, setAuthReady] = useState(false);
    const [user, setUser] = useState<AuthUser | null>(null);

    useEffect(() => {
        const publicPaths = ["/", "/features", "/pricing", "/login", "/register", "/legal"];
        const isPublic = publicPaths.some(p => (pathname || "/").startsWith(p) && (p !== "/" || (pathname || "/") === "/"));
        
        const cached = getStoredUser();
        if (cached) {
            setUser(cached);
            setAuthReady(true);
        } else if (isPublic) {
            setAuthReady(true);
        } else {
            router.replace("/login");
        }
    }, [router, pathname]);

    if (!authReady) return null;

    const publicPaths = ["/", "/features", "/pricing", "/login", "/register", "/legal"];
    const isPublic = publicPaths.some(p => (pathname || "/").startsWith(p) && (p !== "/" || (pathname || "/") === "/"));

    if (isPublic) {
        return <>{children}</>;
    }

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
                {children}
            </main>
        </div>
    );
}
