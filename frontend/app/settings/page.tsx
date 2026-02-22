"use client";

import Link from "next/link";
import { Bot, PlugZap, SlidersHorizontal, CreditCard, UserCircle2, Palette } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getStoredUser } from "@/lib/auth";
import { isPathAllowedForRole } from "@/lib/rbac";
import { T } from "@/lib/tokens";

const cards = [
  {
    title: "General Settings",
    subtitle: "Globale Schalter und zentrale Systemparameter.",
    href: "/settings/general",
    icon: SlidersHorizontal,
  },
  {
    title: "Account & Preferences",
    subtitle: "Persönliches Profil, Passwort und Benachrichtigungspräferenzen.",
    href: "/settings/account",
    icon: UserCircle2,
  },
  {
    title: "Integrationen",
    subtitle: "Telegram, WhatsApp, Magicline und SMTP verwalten.",
    href: "/settings/integrations",
    icon: PlugZap,
  },
  {
    title: "Automation",
    subtitle: "Member-Memory Zeitplan, Modell und Run-Status.",
    href: "/settings/automation",
    icon: Bot,
  },
  {
    title: "Abonnement & Nutzung",
    subtitle: "Aktueller Plan, Features und Verbrauch diesen Monat.",
    href: "/settings/billing",
    icon: CreditCard,
  },
  {
    title: "Branding",
    subtitle: "Logo, Primärfarbe und App-Titel deines Studios.",
    href: "/settings/branding",
    icon: Palette,
  },
  {
    title: "Plans-Verwaltung",
    subtitle: "Pläne und Zahlungsanbieter systemweit steuern.",
    href: "/plans",
    icon: CreditCard,
  },
];

export default function SettingsOverviewPage() {
  const role = getStoredUser()?.role;
  const visibleCards = cards.filter((item) => isPathAllowedForRole(role, item.href));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Settings Center"
          subtitle={
            role === "system_admin"
              ? "Globale und systemweite Konfiguration für den Plattformbetrieb."
              : "Tenant-spezifische Steuerung mit rollenbasiertem Zugriff auf relevante Bereiche."
          }
        />
        <div
          style={{
            marginTop: 12,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))",
            gap: 12,
          }}
        >
          {visibleCards.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  textDecoration: "none",
                  border: `1px solid ${T.border}`,
                  background: T.surfaceAlt,
                  borderRadius: 12,
                  padding: 14,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Icon size={15} style={{ color: T.accent }} />
                  <span style={{ color: T.text, fontWeight: 700, fontSize: 13 }}>{item.title}</span>
                </div>
                <p style={{ margin: 0, color: T.textMuted, fontSize: 12, lineHeight: 1.5 }}>{item.subtitle}</p>
                <span style={{ color: T.accent, fontSize: 12, fontWeight: 600 }}>Öffnen</span>
              </Link>
            );
          })}
          {visibleCards.length === 0 && (
            <div style={{ color: T.textMuted, fontSize: 13 }}>
              Für diese Rolle sind derzeit keine zusätzlichen Settings-Module verfügbar.
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
