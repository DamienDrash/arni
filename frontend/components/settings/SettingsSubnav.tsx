"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  SlidersHorizontal, PlugZap, Bot, UserCircle2, MessageSquare,
  CreditCard, Palette, ShieldCheck, Cpu,
} from "lucide-react";

import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";
import { useI18n } from "@/lib/i18n/LanguageContext";

export default function SettingsSubnav() {
  const { t } = useI18n();
  const pathname = usePathname() || "";
  const role = getStoredUser()?.role;

  const tabs = [
    { href: "/settings", label: t("settings.overview.title"), icon: SlidersHorizontal },
    { href: "/settings/account", label: t("settings.account.title"), icon: UserCircle2 },
    { href: "/settings/ai", label: t("settings.ai.title"), icon: Cpu },
    { href: "/settings/general", label: t("settings.general.title"), icon: ShieldCheck },
    { href: "/settings/integrations", label: t("settings.integrations.title"), icon: PlugZap },
    { href: "/settings/prompts", label: t("settings.prompts.title"), icon: MessageSquare },
    { href: "/settings/billing", label: t("settings.billing.title"), icon: CreditCard },
    { href: "/settings/branding", label: t("settings.branding"), icon: Palette },
    { href: "/settings/automation", label: t("settings.automation"), icon: Bot },
  ];

  const visibleTabs =
    role === "system_admin"
      ? tabs.filter((tab) => ["/settings", "/settings/account", "/settings/ai", "/settings/general"].includes(tab.href))
      : role === "tenant_admin"
        ? tabs.filter((tab) =>
            ["/settings", "/settings/integrations", "/settings/account", "/settings/prompts", "/settings/billing", "/settings/branding", "/settings/ai"].includes(tab.href)
          )
        : tabs.filter((tab) => tab.href === "/settings" || tab.href === "/settings/account");

  return (
    <div
      style={{
        display: "flex",
        gap: 6,
        flexWrap: "wrap",
        padding: "8px 10px",
        borderRadius: 14,
        border: `1px solid ${T.border}`,
        background: T.surface,
      }}
    >
      {visibleTabs.map((tab) => {
        const isActive =
          pathname === tab.href ||
          (tab.href !== "/settings" && pathname.startsWith(`${tab.href}/`));
        const Icon = tab.icon;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 7,
              padding: "8px 12px",
              borderRadius: 10,
              textDecoration: "none",
              border: isActive ? `1px solid ${T.accent}50` : "1px solid transparent",
              background: isActive
                ? `linear-gradient(135deg, ${T.accentDim}, rgba(108,92,231,0.08))`
                : "transparent",
              color: isActive ? T.text : T.textMuted,
              fontSize: 12,
              fontWeight: isActive ? 700 : 600,
              transition: "all 0.2s ease",
              position: "relative",
            }}
          >
            <Icon size={14} color={isActive ? T.accent : T.textDim} />
            {tab.label}
            {isActive && (
              <div style={{
                position: "absolute", bottom: -1, left: "50%",
                transform: "translateX(-50%)",
                width: 16, height: 2, borderRadius: 1,
                background: T.accent,
              }} />
            )}
          </Link>
        );
      })}
    </div>
  );
}
