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
  Clock,
  CreditCard,
  Crown,
  Database,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Settings,
  Users,
  ShieldCheck,
  Server,
  Zap,
  Megaphone,
  Send,
  AlertCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ElementType } from "react";

interface NavItem {
  name: string;
  href: string;
  icon: ElementType;
  feature?: string;
  badge?: string;
}

import { apiFetch } from "@/lib/api";
import { clearSession, getStoredUser } from "@/lib/auth";
import { isPathAllowedForRole } from "@/lib/rbac";
import { usePermissions } from "@/lib/permissions";
import { useI18n } from "@/lib/i18n/LanguageContext";
import styles from "./Sidebar.module.css";

export default function Sidebar({ appTitle, logoUrl }: { appTitle?: string; logoUrl?: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const [handoffCount, setHandoffCount] = useState(0);
  const { role, canPage, plan, feature, isTrial, trialDaysRemaining, isTrialExpired } = usePermissions();
  
  const tenantSections = [
    {
      title: t("sidebar.sections.operations"),
      items: [
        { name: t("sidebar.dashboard"), href: "/dashboard", icon: LayoutDashboard },
        { name: t("sidebar.monitor"), href: "/live", icon: Activity },
        { name: t("sidebar.escalations"), href: "/escalations", icon: AlertTriangle },
        { name: t("sidebar.analytics"), href: "/analytics", icon: BarChart3, feature: "advanced_analytics" },
      ],
    },
    {
      title: t("sidebar.sections.customers"),
      items: [
        { name: t("sidebar.members"), href: "/members", icon: Users, feature: "multi_source_members" },
        { name: t("sidebar.users"), href: "/users", icon: Users },
      ],
    },
    {
      title: t("sidebar.sections.knowledge"),
      items: [
        { name: t("sidebar.knowledge"), href: "/knowledge", icon: BookOpen },
        { name: t("sidebar.memberMemory"), href: "/member-memory", icon: Brain, feature: "memory_analyzer" },
        { name: t("sidebar.systemPrompt"), href: "/system-prompt", icon: Bot, feature: "custom_prompts" },
      ],
    },
    {
      title: "KAMPAGNEN",
      items: [
        { name: "Kampagnen", href: "/campaigns", icon: Megaphone },
      ],
    },
    {
      title: t("sidebar.sections.studio"),
      items: [
        { name: t("sidebar.sync"), href: "/sync", icon: Database },
        { name: "AI-Modelle", href: "/settings/ai", icon: Bot },
        { name: t("sidebar.billing"), href: "/settings/billing", icon: CreditCard },
        { name: t("sidebar.settings"), href: "/settings", icon: Settings },
      ],
    },
  ];

  const systemSections = [
    {
      title: t("sidebar.sections.governance"),
      items: [
        { name: t("sidebar.dashboard"), href: "/dashboard", icon: LayoutDashboard },
        { name: t("sidebar.tenants"), href: "/tenants", icon: Building2 },
        { name: t("sidebar.users"), href: "/users", icon: Users },
      ],
    },
    {
      title: t("sidebar.sections.system"),
      items: [
        { name: t("sidebar.plans"), href: "/plans", icon: CreditCard },
        { name: "Revenue Analytics", href: "/revenue", icon: BarChart3 },
        { name: t("sidebar.audit"), href: "/audit", icon: ScrollText },
        { name: t("sidebar.settings"), href: "/settings", icon: ShieldCheck },
        { name: t("sidebar.health"), href: "/health", icon: Server },
      ],
    },
  ];

  const user = getStoredUser();
  const isSystemAdmin = role === "system_admin";

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
        .filter((item) => isPathAllowedForRole(role, item.href))
        .filter((item) => canPage(item.href))
        .map((item) => ({
          ...item,
          badge: item.href === "/escalations" && handoffCount > 0 ? String(handoffCount) : undefined,
        })),
    })).filter((section) => section.items.length > 0);
  }, [handoffCount, role, isSystemAdmin, canPage, t]);

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
        <p className={styles.brandSub}>{isSystemAdmin ? t("sidebar.platformControl") : `${t("sidebar.studioDeck")} • ${plan?.name || "..."}`}</p>
      </div>

      <nav className={styles.nav}>
        <div className={styles.quickWrap}>
          <p className={styles.quickTitle}>
            {t("sidebar.quickActions")}
          </p>
          <div className={styles.quickGrid}>
            {[
              ...(isSystemAdmin
                ? [
                    { label: t("sidebar.tenants"), href: "/tenants" },
                    { label: t("sidebar.plans"), href: "/plans" },
                    { label: t("sidebar.settings"), href: "/settings" },
                  ]
                : [
                    { label: t("sidebar.monitor"), href: "/live" },
                    { label: t("sidebar.analytics"), href: "/analytics" },
                    { label: t("sidebar.settings"), href: "/settings" },
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

        {/* Trial Banner */}
        {!isSystemAdmin && isTrial() && (() => {
          const daysLeft = trialDaysRemaining();
          const expired = isTrialExpired();
          const progress = expired ? 100 : Math.max(0, ((14 - daysLeft) / 14) * 100);
          return (
            <div className={`${styles.trialBanner} ${expired ? styles.trialBannerExpired : ""}`}>
              <div className={styles.trialHeader}>
                <div className={`${styles.trialIcon} ${expired ? styles.trialIconExpired : ""}`}>
                  {expired ? <AlertCircle size={14} /> : <Clock size={14} />}
                </div>
                <p className={styles.trialTitle}>
                  {expired ? t("sidebar.trial.expired") : t("sidebar.trial.active")}
                </p>
              </div>
              <p className={styles.trialDays}>
                {expired
                  ? t("sidebar.trial.expiredDesc")
                  : t("sidebar.trial.daysLeft", { days: daysLeft })
                }
              </p>
              <div className={styles.trialProgressWrap}>
                <div
                  className={`${styles.trialProgressBar} ${expired ? styles.trialProgressBarExpired : ""}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
              <Link
                href="/settings/billing"
                className={`${styles.trialUpgradeBtn} ${expired ? styles.trialUpgradeBtnExpired : ""}`}
              >
                <Crown size={12} />
                {t("sidebar.trial.upgrade")}
              </Link>
            </div>
          );
        })()}

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
            <p className={styles.footerRole}>{isSystemAdmin ? t("sidebar.roles.systemAdmin") : (plan?.name?.toUpperCase() || t("sidebar.roles.tenantAdmin"))}</p>
          </div>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className={styles.logout}
            title={t("sidebar.logout")}
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
