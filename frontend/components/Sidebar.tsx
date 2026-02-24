"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Building2,
  CreditCard,
  Database,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  Users,
  ShieldCheck,
  Server,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ElementType } from "react";

import { apiFetch } from "@/lib/api";
import { clearSession, getStoredUser } from "@/lib/auth";
import { isPathAllowedForRole } from "@/lib/rbac";
import { usePermissions } from "@/lib/permissions";
import styles from "./Sidebar.module.css";

type NavItem = { name: string; href: string; icon: ElementType; badge?: string; feature?: string };

const tenantSections: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "Operations",
    items: [
      { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { name: "Live Monitor", href: "/live", icon: Activity },
      { name: "Eskalationen", href: "/escalations", icon: AlertTriangle },
      { name: "Analytics", href: "/analytics", icon: BarChart3, feature: "advanced_analytics" },
    ],
  },
  {
    title: "Kunden & Team",
    items: [
      { name: "Mitglieder", href: "/members", icon: Users, feature: "multi_source_members" },
      { name: "Benutzer", href: "/users", icon: Users },
    ],
  },
  {
    title: "Knowledge",
    items: [
      { name: "Wissensbasis", href: "/knowledge", icon: BookOpen },
      { name: "Member Memory", href: "/member-memory", icon: Brain, feature: "memory_analyzer" },
      { name: "Studio-Prompt", href: "/system-prompt", icon: Bot, feature: "custom_prompts" },
    ],
  },
  {
    title: "Studio",
    items: [
      { name: "Sync", href: "/magicline", icon: Database },
      { name: "Abonnement", href: "/settings/billing", icon: CreditCard },
      { name: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

const systemSections: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "Platform Governance",
    items: [
      { name: "SaaS Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { name: "Tenants", href: "/tenants", icon: Building2 },
      { name: "User Management", href: "/users", icon: Users },
    ],
  },
  {
    title: "System & Core",
    items: [
      { name: "Billing Plans", href: "/plans", icon: CreditCard },
      { name: "Audit Log", href: "/audit", icon: ScrollText },
      { name: "Platform Settings", href: "/settings", icon: ShieldCheck },
      { name: "Engine Stats", href: "/health", icon: Server },
    ],
  },
];

export default function Sidebar({ appTitle, logoUrl }: { appTitle?: string; logoUrl?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [handoffCount, setHandoffCount] = useState(0);
  const { role, canPage, plan, feature } = usePermissions();
  const user = getStoredUser();
  const isSystemAdmin = role === "system_admin";

  useEffect(() => {
    if (isSystemAdmin) return; // System admins don't care about single-tenant escalations here
    const run = async () => {
      try {
        const res = await apiFetch("/admin/stats");
        if (!res.ok) return;
        const data = await res.json();
        setHandoffCount(Number(data.active_handoffs || 0));
      } catch {
        // best effort
      }
    };
    run();
    const timer = setInterval(run, 15000);
    return () => clearInterval(timer);
  }, [isSystemAdmin]);

  const allSections = useMemo(() => {
    const baseSections = isSystemAdmin ? systemSections : tenantSections;
    return baseSections.map((section) => ({
      ...section,
      items: section.items
        .filter((item) => isPathAllowedForRole(role, item.href))
        .filter((item) => canPage(item.href))
        .map((item) => ({
          ...item,
          badge: item.href === "/escalations" && handoffCount > 0 ? String(handoffCount) : undefined,
        })),
    })).filter((section) => section.items.length > 0);
  }, [handoffCount, role, isSystemAdmin, canPage]);

  const renderItem = (item: NavItem) => {
    const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
    const Icon = item.icon;
    const isLocked = item.feature && !feature(item.feature);

    return (
      <Link
        key={item.href}
        href={isLocked ? "/settings/billing" : item.href}
        className={`${styles.item} ${isActive ? styles.itemActive : ""} ${isLocked ? styles.itemLocked : ""}`}
      >
        <Icon size={16} className={`${styles.itemIcon} ${isActive ? styles.itemIconActive : ""}`} />
        <span className={`${styles.itemText} ${isActive ? styles.itemTextActive : ""}`}>
          {item.name}
        </span>
        {isLocked && <Zap size={12} className={styles.lockIcon} />}
        {item.badge && !isLocked && (
          <span className={styles.itemBadge}>{item.badge}</span>
        )}
      </Link>
    );
  };

  return (
    <div className={styles.root}>
      <div className={styles.brandWrap}>
        <div className={styles.brandRow}>
          {logoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={logoUrl}
              alt={appTitle || "Logo"}
              className={styles.brandLogo}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <h1 className={styles.brandTitle}>
              {appTitle || "ARIIA"}<span className={styles.brandDot}>.</span>
            </h1>
          )}
        </div>
        <p className={styles.brandSub}>{isSystemAdmin ? "Platform Control" : `Studio Deck • ${plan?.name || "..."}`}</p>
      </div>

      <nav className={styles.nav}>
        <div className={styles.quickWrap}>
          <p className={styles.quickTitle}>
            Quick Actions
          </p>
          <div className={styles.quickGrid}>
            {[
              ...(isSystemAdmin
                ? [
                    { label: "Tenants", href: "/tenants" },
                    { label: "Plans", href: "/plans" },
                    { label: "Settings", href: "/settings" },
                  ]
                : [
                    { label: "Live", href: "/live" },
                    { label: "Analytics", href: "/analytics" },
                    { label: "Settings", href: "/settings" },
                  ]),
            ]
              .filter((q) => isPathAllowedForRole(role, q.href))
              .filter((q) => canPage(q.href))
              .map((q) => (
              <Link
                key={q.href}
                href={q.href}
                className={styles.quickLink}
              >
                {q.label}
              </Link>
            ))}
          </div>
        </div>

        {allSections.map((section) => (
          <div key={section.title} className={styles.section}>
            <p className={styles.sectionLabel}>{section.title}</p>
            {section.items.map(renderItem)}
          </div>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.footerRow}>
          <div className={styles.avatar} style={{ background: isSystemAdmin ? T.dangerDim : T.accentDim, color: isSystemAdmin ? T.danger : T.accent }}>
            {isSystemAdmin ? <ShieldCheck size={14} /> : "A"}
          </div>
          <div className={styles.footerMeta}>
            <p className={styles.footerEmail}>
              {user?.email || "Admin"}
            </p>
            <p className={styles.footerRole}>{isSystemAdmin ? "SYSTEM ADMIN" : (plan?.name?.toUpperCase() || "TENANT ADMIN")}</p>
          </div>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className={styles.logout}
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

// Minimal colors for avatar style hack
const T = {
  accent: "#6C5CE7",
  accentDim: "rgba(108,92,231,0.15)",
  danger: "#FF6B6B",
  dangerDim: "rgba(255,107,107,0.12)",
};
