"use client";

import { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Menu, X } from "lucide-react";
import Sidebar from "./Sidebar";
import { getStoredUser, setStoredUser, type AuthUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { isPathAllowedForRole } from "@/lib/rbac";
import { applyBrandingCSS, type BrandingPrefs } from "@/lib/branding";
import { useI18n } from "@/lib/i18n/LanguageContext";
import styles from "./NavShell.module.css";

export default function NavShell({ children }: { children: React.ReactNode }) {
    const { t } = useI18n();
    const [open, setOpen] = useState(false);

    const pageMeta: Record<string, { title: string; subtitle: string }> = {
        "/": { title: t("common.welcome"), subtitle: "" },
        "/dashboard": { title: t("common.dashboard"), subtitle: t("dashboard.overview") },
        "/live": { title: "Live Monitor | Real-time AI", subtitle: "Echtzeit-Ansicht aktiver Konversationen und Handoffs." },
        "/escalations": { title: "Eskalationen", subtitle: "Offene menschliche Übergaben und Bearbeitungsstatus." },
        "/analytics": { title: "Analytics & Performance", subtitle: "Qualität, Trends und Performance über alle Kanäle." },
        "/members": { title: "Mitgliederverwaltung", subtitle: "Mitgliederdaten, Suche und Enrichment-Status." },
        "/users": { title: "Benutzerverwaltung", subtitle: "Rollen, Tenant-Zuordnung und Zugriffsverwaltung." },
        "/tenants": { title: "Tenants | Multi-Studio", subtitle: "Mandantenstruktur, Wachstum und Governance." },
        "/plans": { title: "Plans & Billing", subtitle: "Produktpläne, Limits und Zahlungsanbieter konfigurieren." },
        "/knowledge": { title: "Wissensbasis (RAG)", subtitle: "Dokumente verwalten und mit der Suche synchronisieren." },
        "/member-memory": { title: "Member Memory", subtitle: "Langzeitkontext je Mitglied einsehen und pflegen." },
        "/system-prompt": { title: "LLM System Prompt", subtitle: "Systemanweisung für den Ops-Agenten zentral steuern." },
        "/magicline": { title: "Magicline Sync", subtitle: "Datenanbindung, Sync-Läufe und Abdeckung." },
        "/audit": { title: "Security Audit Log", subtitle: "Nachvollziehbarkeit aller sicherheitsrelevanten Änderungen." },
        "/settings": { title: t("common.settings"), subtitle: "Systemweite Konfiguration, Integrationen und Automation." },
        "/settings/account": { title: "Settings · Account", subtitle: "Persönliches Profil, Security und Tenant-Präferenzen verwalten." },
        "/settings/general": { title: "Settings · General", subtitle: "Kernparameter und globale Schalter." },
        "/settings/integrations": { title: "Settings · Integrationen", subtitle: "Telegram, WhatsApp, Magicline und SMTP zentral steuern." },
        "/settings/automation": { title: "Settings · Automation", subtitle: "Member-Memory Zeitplan, LLM und Run-Status." },
        "/login": { title: t("common.login"), subtitle: "" },
        "/register": { title: t("common.register"), subtitle: "" },
    };

    const [authReady, setAuthReady] = useState(false);
    const [user, setUser] = useState<AuthUser | null>(() => getStoredUser());
    const [branding, setBranding] = useState<Partial<BrandingPrefs> | null>(null);
    const [leavingGhostMode, setLeavingGhostMode] = useState(false);
    const pathname = usePathname();
    const router = useRouter();
    const isRoot = pathname === "/";
    const isAuthRoute = pathname === "/login" || pathname === "/register";
    const isPublicLanding = pathname === "/features" || pathname === "/pricing" || pathname === "/impressum" || pathname === "/datenschutz" || pathname === "/agb";
    const isPublicRoute = isRoot || isAuthRoute || isPublicLanding;

    const currentMeta =
        pageMeta[pathname || ""] ||
        Object.entries(pageMeta)
            .filter(([route]) => route !== "/" && pathname?.startsWith(`${route}/`))
            .sort((a, b) => b[0].length - a[0].length)[0]?.[1] ||
        { title: "ARIIA", subtitle: "Control Deck" };
    // Prevent body scroll when drawer is open
    useEffect(() => {
        document.body.style.overflow = open ? "hidden" : "";
        return () => { document.body.style.overflow = ""; };
    }, [open]);

    useEffect(() => {
        let cancelled = false;
        const bootstrap = async () => {
            if (isPublicRoute) {
                if (!cancelled) setAuthReady(true);
                return;
            }
            const cached = getStoredUser();
            if (cached) {
                if (!cancelled) {
                    setUser(cached);
                    setAuthReady(true);
                }
                return;
            }
            try {
                const res = await apiFetch("/auth/me");
                if (!res.ok) {
                    if (!cancelled) {
                        setUser(null);
                        setAuthReady(true);
                        router.replace("/login");
                    }
                    return;
                }
                const me = (await res.json()) as AuthUser;
                setStoredUser(me);
                if (!cancelled) {
                    setUser(me);
                    setAuthReady(true);
                }
                // Fire branding fetch (best-effort, non-blocking)
                apiFetch("/admin/tenant-preferences")
                    .then((r) => r.ok ? r.json() : null)
                    .then((data) => {
                        if (data && !cancelled) {
                            setBranding(data as Partial<BrandingPrefs>);
                            applyBrandingCSS(data as Partial<BrandingPrefs>);
                        }
                    })
                    .catch(() => { /* best effort */ });
            } catch {
                if (!cancelled) {
                    setUser(null);
                    setAuthReady(true);
                    router.replace("/login");
                }
            }
        };
        void bootstrap();
        return () => {
            cancelled = true;
        };
    }, [isPublicRoute, router]);

    useEffect(() => {
        const onSessionUpdated = () => setUser(getStoredUser());
        window.addEventListener("ariia:session-updated", onSessionUpdated);
        return () => window.removeEventListener("ariia:session-updated", onSessionUpdated);
    }, []);

    useEffect(() => {
        if (isPublicRoute) return;
        if (!user) return;
        if (!isPathAllowedForRole(user.role, pathname || "/")) {
            router.replace("/");
        }
    }, [isPublicRoute, pathname, router, user]);

    if (isRoot || isPublicLanding) {
        return <main className="min-h-screen overflow-x-hidden">{children}</main>;
    }

    if (isAuthRoute) {
        return <main className="min-h-screen overflow-x-hidden p-4 md:p-8">{children}</main>;
    }

    if (!authReady) {
        return <main className="min-h-screen overflow-x-hidden p-4 md:p-8" />;
    }

    const stopGhostMode = async () => {
        if (!user?.impersonation?.active) return;
        setLeavingGhostMode(true);
        try {
            const res = await apiFetch("/auth/impersonation/stop", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            if (!res.ok) return;
            const data = (await res.json()) as { user?: AuthUser };
            if (data.user) {
                setStoredUser(data.user);
                setUser(data.user);
            } else {
                const meRes = await apiFetch("/auth/me");
                if (meRes.ok) {
                    const me = (await meRes.json()) as AuthUser;
                    setStoredUser(me);
                    setUser(me);
                }
            }
            router.replace("/users");
            router.refresh();
        } finally {
            setLeavingGhostMode(false);
        }
    };

    return (
        <>
            {/* ── Desktop sidebar (fixed, always visible) ─────────────────── */}
            <div className={styles.desktopSidebar}>
                <Sidebar appTitle={branding?.tenant_app_title} logoUrl={branding?.tenant_logo_url} />
            </div>

            {/* ── Mobile: backdrop ─────────────────────────────────────────── */}
            <div
                className={styles.mobileBackdrop}
                style={{ opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none" }}
                data-open={open ? "true" : "false"}
                onClick={() => setOpen(false)}
                aria-hidden="true"
            />

            {/* ── Mobile: slide-in drawer ───────────────────────────────────── */}
            <div
                className={styles.mobileDrawer}
                style={{ transform: open ? "translateX(0)" : "translateX(-100%)" }}
            >
                <Sidebar appTitle={branding?.tenant_app_title} logoUrl={branding?.tenant_logo_url} />
            </div>

            {/* ── Mobile: top bar with hamburger ───────────────────────────── */}
            <div
                className={styles.mobileTopbar}
            >
                <span className={styles.brand}>
                    {branding?.tenant_app_title || "ARIIA"}<span className={styles.brandDot}>.</span>
                </span>
                <button
                    onClick={() => setOpen(v => !v)}
                    aria-label="Navigation öffnen"
                    className={styles.menuButton}
                >
                    {open ? <X size={22} /> : <Menu size={22} />}
                </button>
            </div>

            {/* ── Main content ─────────────────────────────────────────────── */}
            <main className={styles.appMain}>
                {user?.impersonation?.active && (
                    <div className={styles.ghostBanner}>
                        <div className={styles.ghostBannerText}>
                            <strong>Ghost Mode aktiv</strong>
                            <span>
                                Du agierst als {user.email} ({user.role}) im Tenant {user.tenant_slug}.
                            </span>
                        </div>
                        <button
                            type="button"
                            className={styles.ghostBannerExit}
                            onClick={() => void stopGhostMode()}
                            disabled={leavingGhostMode}
                        >
                            {leavingGhostMode ? "Beende..." : "Ghost Mode beenden"}
                        </button>
                    </div>
                )}
                <div className={styles.pageHead}>
                    <h1 className={styles.pageTitle}>{currentMeta.title}</h1>
                    <p className={styles.pageSubtitle}>{currentMeta.subtitle}</p>
                </div>
                {children}
            </main>
        </>
    );
}
