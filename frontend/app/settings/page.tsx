"use client";

import { useEffect, useState } from "react";
import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { getStoredUser } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { T } from "@/lib/tokens";
import {
  UserCircle2, Cpu, ShieldCheck, PlugZap, MessageSquare,
  CreditCard, Palette, Bot, ArrowRight, Sparkles,
} from "lucide-react";
import Link from "next/link";

export default function SettingsOverviewPage() {
  const { t } = useI18n();
  const role = getStoredUser()?.role;
  const [hovered, setHovered] = useState<string | null>(null);

  const cards = [
    {
      href: "/settings/account",
      title: t("settings.account.title"),
      desc: t("settings.account.subtitle"),
      icon: UserCircle2,
      color: "#3B82F6",
      gradient: "linear-gradient(135deg, #3B82F6, #2563EB)",
      roles: ["system_admin", "tenant_admin", "tenant_user"],
    },
    {
      href: "/settings/ai",
      title: t("settings.ai.title"),
      desc: t("settings.ai.subtitle"),
      icon: Cpu,
      color: "#6C5CE7",
      gradient: "linear-gradient(135deg, #6C5CE7, #5B4BD5)",
      roles: ["system_admin", "tenant_admin"],
    },
    {
      href: "/settings/general",
      title: t("settings.general.title"),
      desc: t("settings.general.subtitle"),
      icon: ShieldCheck,
      color: "#10B981",
      gradient: "linear-gradient(135deg, #10B981, #059669)",
      roles: ["system_admin"],
    },
    {
      href: "/settings/integrations",
      title: t("settings.integrations.title"),
      desc: t("settings.integrations.subtitle"),
      icon: PlugZap,
      color: "#F59E0B",
      gradient: "linear-gradient(135deg, #F59E0B, #D97706)",
      roles: ["tenant_admin"],
    },
    {
      href: "/settings/prompts",
      title: t("settings.prompts.title"),
      desc: t("settings.prompts.subtitle"),
      icon: MessageSquare,
      color: "#EC4899",
      gradient: "linear-gradient(135deg, #EC4899, #DB2777)",
      roles: ["tenant_admin"],
    },
    {
      href: "/settings/billing",
      title: t("settings.billing.title"),
      desc: t("settings.billing.subtitle"),
      icon: CreditCard,
      color: "#6366F1",
      gradient: "linear-gradient(135deg, #6366F1, #4F46E5)",
      roles: ["tenant_admin"],
    },
    {
      href: "/settings/branding",
      title: t("settings.branding"),
      desc: "Logo, Farben und White-Label-Konfiguration anpassen",
      icon: Palette,
      color: "#F472B6",
      gradient: "linear-gradient(135deg, #F472B6, #EC4899)",
      roles: ["tenant_admin"],
    },
  ];

  const visibleCards = cards.filter((c) => c.roles.includes(role || ""));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SettingsSubnav />

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 14,
          background: T.accentDim, display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
          <Sparkles size={22} color={T.accent} />
        </div>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>
            Einstellungen
          </h1>
          <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
            Konfiguriere dein System nach deinen Anforderungen
          </p>
        </div>
      </div>

      {/* Cards Grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 16,
      }}>
        {visibleCards.map((card) => {
          const isHovered = hovered === card.href;
          return (
            <Link key={card.href} href={card.href} style={{ textDecoration: "none" }}>
              <Card
                style={{
                  padding: 0,
                  overflow: "hidden",
                  cursor: "pointer",
                  transition: "all 0.25s ease",
                  transform: isHovered ? "translateY(-2px)" : "none",
                  boxShadow: isHovered ? `0 8px 24px ${card.color}20` : "none",
                  border: isHovered ? `1px solid ${card.color}40` : `1px solid ${T.border}`,
                }}
                onMouseEnter={() => setHovered(card.href)}
                onMouseLeave={() => setHovered(null)}
              >
                {/* Gradient accent bar */}
                <div style={{ height: 3, background: card.gradient }} />

                <div style={{ padding: "20px 20px 18px" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 12,
                      background: `${card.color}12`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      transition: "transform 0.25s ease",
                      transform: isHovered ? "scale(1.1)" : "none",
                    }}>
                      <card.icon size={22} color={card.color} />
                    </div>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: isHovered ? `${card.color}15` : T.surfaceAlt,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      transition: "all 0.25s ease",
                    }}>
                      <ArrowRight size={14} color={isHovered ? card.color : T.textDim} />
                    </div>
                  </div>

                  <h3 style={{
                    fontSize: 15, fontWeight: 700, color: T.text,
                    margin: "14px 0 4px", letterSpacing: "-0.01em",
                  }}>
                    {card.title}
                  </h3>
                  <p style={{
                    fontSize: 12, color: T.textMuted, margin: 0,
                    lineHeight: 1.5, minHeight: 36,
                  }}>
                    {card.desc}
                  </p>
                </div>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
