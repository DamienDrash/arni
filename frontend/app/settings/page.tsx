"use client";

import Link from "next/link";
import { 
  Building2, Users, ShieldCheck, CreditCard, 
  UserCircle2, Cpu, ScrollText, Mail, Shield, Lock
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";

export default function SettingsOverviewPage() {
  const user = getStoredUser();
  const role = user?.role;
  const isSystemAdmin = role === "system_admin";

  const systemCards = [
    {
      title: "AI Engine",
      subtitle: "Management von LLM-Providern, Modellen und Platform-Keys.",
      href: "/settings/ai",
      icon: Cpu,
      color: T.accent
    },
    {
      title: "Platform Core",
      subtitle: "System-SMTP, Wartungsmodus und globale Datenschutz-Policies.",
      href: "/settings/general",
      icon: ShieldCheck,
      color: T.success
    },
    {
      title: "Tenant Governance",
      subtitle: "Zentrale Steuerung aller Studio-Mandanten und deren Status.",
      href: "/tenants",
      icon: Building2,
      color: T.info
    },
    {
      title: "User Management",
      subtitle: "Plattformweite Verwaltung von Administratoren und Rollen.",
      href: "/users",
      icon: Users,
      color: T.info
    },
    {
      title: "Plans & Billing",
      subtitle: "SaaS-Pläne, Features und Stripe-Konnektoren verwalten.",
      href: "/plans",
      icon: CreditCard,
      color: T.warning
    },
    {
      title: "Audit Log",
      subtitle: "Lückenlose Protokollierung aller System-Aktionen (Compliance).",
      href: "/audit",
      icon: ScrollText,
      color: T.textDim
    },
  ];

  const tenantCards = [
    {
      title: "Integrationen",
      subtitle: "WhatsApp, Telegram und Magicline für dein Studio konfigurieren.",
      href: "/settings/integrations",
      icon: Cpu,
      color: T.accent
    },
    {
      title: "Studio Profil",
      subtitle: "KI-Persönlichkeit, Branding und Studio-Informationen.",
      href: "/settings/branding",
      icon: ShieldCheck,
      color: T.success
    },
    {
      title: "Abonnement",
      subtitle: "Dein gewählter SaaS-Plan und aktuelle Nutzungs-Statistiken.",
      href: "/settings/billing",
      icon: CreditCard,
      color: T.warning
    },
    {
      title: "Mein Account",
      subtitle: "Persönliches Profil, Passwort und Benachrichtigungen.",
      href: "/settings/account",
      icon: UserCircle2,
      color: T.info
    },
  ];

  const visibleCards = isSystemAdmin ? systemCards : tenantCards;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <Card style={{ padding: 24 }}>
        <SectionHeader
          title={isSystemAdmin ? "SaaS Operations Control" : "Studio Einstellungen"}
          subtitle={
            isSystemAdmin
              ? "Zentrales Dashboard für die Steuerung der SaaS-Infrastruktur und Governance."
              : "Verwalte deine Studio-Konfiguration und persönlichen Account-Einstellungen."
          }
        />
        <div
          style={{
            marginTop: 20,
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit,minmax(280px,1fr))",
            gap: 16,
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
                  borderRadius: 16,
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  transition: "all 0.2s ease",
                }}
                className="hover:border-accent hover:bg-base-200"
              >
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: `${item.color}15`, display: "flex", alignItems: "center", justifyContent: "center", color: item.color }}>
                    <Icon size={20} />
                  </div>
                  <span style={{ color: T.text, fontWeight: 700, fontSize: 15 }}>{item.title}</span>
                </div>
                <p style={{ margin: 0, color: T.textMuted, fontSize: 12, lineHeight: 1.6, minHeight: 36 }}>{item.subtitle}</p>
                <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 6, color: T.accent, fontSize: 12, fontWeight: 700 }}>
                  Konfigurieren <span>→</span>
                </div>
              </Link>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
