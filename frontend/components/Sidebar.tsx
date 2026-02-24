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
  Crown,
  Database,
  LayoutDashboard,
  LogOut,
  Palette,
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
import { isPathAllowedForRole, PAGE_FEATURE_REQUIREMENTS } from "@/lib/rbac";
import { usePermissions, type PlanFeatures } from "@/lib/permissions";
import styles from "./Sidebar.module.css";

type NavItem = {
  name: string;
  href: string;
  icon: ElementType;
  badge?: string;
  /** Plan feature required (if any). Item shown but locked if feature not in plan. */
  requiredFeature?: keyof PlanFeatures;
};

const tenantSections: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "Operations",
    items: [
      { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
      { name: "Live Monitor", href: "/live", icon: Activity },
      { name: "Eskalationen", href: "/escalations", icon: AlertTriangle },
      { name: "Analytics", href: "/analytics", icon: BarChart3 },
    ],
  },
  {
    title: "Kunden & Team",
    items: [
      { name: "Mitglieder", href: "/members", icon: Users },
      { name: "Benutzer", href: "/users", icon: Users },
    ],
  },
  {
    title: "Knowledge",
    items: [
      { name: "Wissensbasis", href: "/knowledge", icon: BookOpen },
      { name: "Member Memory", href: "/member-memory", icon: Brain, requiredFeature: "memory_analyzer" },
      { name: "Studio-Prompt", href: "/system-prompt", icon: Bot },
    ],
  },
  {
    title: "Studio",
    items: [
      { name: "Magicline Sync", href: "/magicline", icon: Database },
      { name: "Abonnement", href: "/settings/billing", icon: CreditCard },
      { name: "Automation", href: "/settings/automation", icon: Zap, requiredFeature: "automation" },
      { name: "Branding", href: "/settings/branding", icon: Palette, requiredFeature: "branding" },
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
  const user = getStoredUser();
  const role = user?.role;
  const isSystemAdmin = role === "system_admin";
  const isTenantUser = role === "tenant_user";
  const { feature, plan, usage, isNearLimit, subscription } = usePermissions();

  useEffect(() => {
    if (isSystemAdmin) return;
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
        .filter((item) => isPathAllowedForRole(role, item.href)),
    })).filter((section) => section.items.length > 0);
  }, [role, isSystemAdmin]);

  // Add escalation badge
  const sectionsWithBadges = useMemo(() => {
    return allSections.map((section) => ({
      ...section,
      items: section.items.map((item) => ({
        ...item,
        badge: item.href === "/escalations" && handoffCount > 0 ? String(handoffCount) : undefined,
      })),
    }));
  }, [allSections, handoffCount]);

  const renderItem = (item: NavItem) => {
    const isActive = pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href));
    const Icon = item.icon;
    const isLocked = item.requiredFeature && !feature(item.requiredFeature);

    return (
      <Link
        key={item.href}
        href={isLocked ? "/settings/billing" : item.href}
        className={`${styles.item} ${isActive ? styles.itemActive : ""}`}
        style={isLocked ? { opacity: 0.5 } : undefined}
        title={isLocked ? `Verfügbar ab ${getRequiredPlan(item.requiredFeature!)}` : undefined}
      >
        <Icon size={16} className={`${styles.itemIcon} ${isActive ? styles.itemIconActive : ""}`} />
        <span className={`${styles.itemText} ${isActive ? styles.itemTextActive : ""}`}>
          {item.name}
        </span>
        {isLocked && (
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 2,
            padding: "1px 6px",
            borderRadius: 4,
            background: "rgba(255,170,0,0.12)",
            border: "1px solid rgba(255,170,0,0.2)",
            fontSize: 9,
            fontWeight: 700,
            color: "#FFAA00",
            marginLeft: "auto",
            letterSpacing: "0.02em",
          }}>
            <Crown size={8} />
            PRO
          </span>
        )}
        {item.badge && (
          <span className={styles.itemBadge}>{item.badge}</span>
        )}
      </Link>
    );
  };

  // Plan usage indicator for tenant admins
  const renderPlanIndicator = () => {
    if (isSystemAdmin) return null;

    const planColors: Record<string, string> = {
      starter: "#8B8D9A",
      pro: "#6C5CE7",
      enterprise: "#FFAA00",
    };
    const planColor = planColors[plan.slug] || "#8B8D9A";

    // Usage bar for message limits
    const maxMsgs = plan.limits.max_monthly_messages;
    const msgPercent = maxMsgs ? Math.min(100, Math.round((usage.messages_used / maxMsgs) * 100)) : 0;
    const nearLimit = isNearLimit("messages");

    return (
      <div style={{
        margin: "0 12px 8px",
        padding: "10px 12px",
        borderRadius: 10,
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 700,
            color: planColor,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}>
            {plan.slug === "enterprise" && <Crown size={10} />}
            {plan.name}
          </span>
          {subscription.status === "trialing" && (
            <span style={{
              fontSize: 9,
              fontWeight: 600,
              color: "#4FC3F7",
              background: "rgba(79,195,247,0.12)",
              padding: "1px 6px",
              borderRadius: 4,
            }}>
              TRIAL
            </span>
          )}
        </div>
        {maxMsgs && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "#8B8D9A", marginBottom: 3 }}>
              <span>Nachrichten</span>
              <span style={{ color: nearLimit ? "#FFAA00" : "#8B8D9A" }}>
                {usage.messages_used.toLocaleString("de-DE")} / {maxMsgs.toLocaleString("de-DE")}
              </span>
            </div>
            <div style={{ width: "100%", height: 3, borderRadius: 2, background: "rgba(255,255,255,0.06)" }}>
              <div style={{
                width: `${msgPercent}%`,
                height: "100%",
                borderRadius: 2,
                background: nearLimit ? "#FFAA00" : planColor,
                transition: "width 0.3s ease",
              }} />
            </div>
          </div>
        )}
        {!maxMsgs && (
          <div style={{ fontSize: 10, color: "#5A5C6B" }}>
            Unbegrenzte Nachrichten
          </div>
        )}
      </div>
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
        <p className={styles.brandSub}>
          {isSystemAdmin ? "Platform Control" : isTenantUser ? "Agent Desk" : "Studio Deck"}
        </p>
      </div>

      {renderPlanIndicator()}

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
                    ...(isTenantUser ? [] : [{ label: "Settings", href: "/settings" }]),
                  ]),
            ]
              .filter((q) => isPathAllowedForRole(role, q.href))
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

        {sectionsWithBadges.map((section) => (
          <div key={section.title} className={styles.section}>
            <p className={styles.sectionLabel}>{section.title}</p>
            {section.items.map(renderItem)}
          </div>
        ))}
      </nav>

      <div className={styles.footer}>
        {/* Upgrade CTA for Starter plan */}
        {!isSystemAdmin && plan.slug === "starter" && (
          <Link
            href="/settings/billing"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
              margin: "0 12px 8px",
              padding: "8px 12px",
              borderRadius: 8,
              background: "linear-gradient(135deg, rgba(108,92,231,0.15), rgba(139,92,246,0.15))",
              border: "1px solid rgba(108,92,231,0.3)",
              color: "#A29BFE",
              fontSize: 12,
              fontWeight: 600,
              textDecoration: "none",
              transition: "background 0.15s ease",
            }}
          >
            <Zap size={12} />
            Auf Pro upgraden
          </Link>
        )}
        <div className={styles.footerRow}>
          <div className={styles.avatar} style={{
            background: isSystemAdmin ? TC.dangerDim : TC.accentDim,
            color: isSystemAdmin ? TC.danger : TC.accent,
          }}>
            {isSystemAdmin ? <ShieldCheck size={14} /> : "A"}
          </div>
          <div className={styles.footerMeta}>
            <p className={styles.footerEmail}>
              {user?.email || "Admin"}
            </p>
            <p className={styles.footerRole}>
              {isSystemAdmin
                ? "SYSTEM ADMIN"
                : isTenantUser
                  ? "AGENT"
                  : "ADMIN"}
            </p>
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

// Helper: get required plan name for a feature
function getRequiredPlan(feature: keyof PlanFeatures): string {
  const enterpriseFeatures: (keyof PlanFeatures)[] = ["voice", "google_business", "automation"];
  if (enterpriseFeatures.includes(feature)) return "Enterprise";
  return "Pro";
}

// Minimal colors for avatar style
const TC = {
  accent: "#6C5CE7",
  accentDim: "rgba(108,92,231,0.15)",
  danger: "#FF6B6B",
  dangerDim: "rgba(255,107,107,0.12)",
};
