"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SlidersHorizontal, PlugZap, Bot, UserCircle2, MessageSquare, CreditCard, Palette, ShieldCheck, Cpu } from "lucide-react";

import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";

const tabs = [
  { href: "/settings", label: "Overview", icon: SlidersHorizontal },
  { href: "/settings/account", label: "Account", icon: UserCircle2 },
  { href: "/settings/ai", label: "AI Engine", icon: Cpu },
  { href: "/settings/general", label: "Platform Core", icon: ShieldCheck },
  { href: "/settings/integrations", label: "Integrationen", icon: PlugZap },
  { href: "/settings/prompts", label: "Agent-Config", icon: MessageSquare },
  { href: "/settings/billing", label: "Abonnement", icon: CreditCard },
  { href: "/settings/branding", label: "Branding", icon: Palette },
  { href: "/settings/automation", label: "Automation", icon: Bot },
];

export default function SettingsSubnav() {
  const pathname = usePathname() || "";
  const role = getStoredUser()?.role;
  
  const visibleTabs =
    role === "system_admin"
      ? tabs.filter((tab) => ["/settings", "/settings/account", "/settings/ai", "/settings/general"].includes(tab.href))
      : role === "tenant_admin"
        ? tabs.filter((tab) =>
            ["/settings", "/settings/integrations", "/settings/account", "/settings/prompts", "/settings/billing", "/settings/branding"].includes(tab.href)
          )
        : tabs.filter((tab) => tab.href === "/settings" || tab.href === "/settings/account");

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        padding: 8,
        borderRadius: 12,
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
              padding: "8px 10px",
              borderRadius: 9,
              textDecoration: "none",
              border: `1px solid ${isActive ? `${T.accent}66` : T.border}`,
              background: isActive ? T.accentDim : T.surfaceAlt,
              color: isActive ? T.text : T.textMuted,
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            <Icon size={14} />
            {tab.label}
          </Link>
        );
      })}
    </div>
  );
}
