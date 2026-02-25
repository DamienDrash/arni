"use client";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getStoredUser } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { UserCircle2, Cpu, ShieldCheck, PlugZap, MessageSquare, CreditCard, Palette, Bot } from "lucide-react";
import Link from "next/link";

export default function SettingsOverviewPage() {
  const { t } = useI18n();
  const role = getStoredUser()?.role;

  const cards = [
    { 
      href: "/settings/account", 
      title: t("settings.account.title"), 
      desc: t("settings.account.subtitle"), 
      icon: UserCircle2, 
      color: "#3B82F6",
      roles: ["system_admin", "tenant_admin", "tenant_user"] 
    },
    { 
      href: "/settings/ai", 
      title: t("settings.ai.title"), 
      desc: t("settings.ai.subtitle"), 
      icon: Cpu, 
      color: "#6C5CE7",
      roles: ["system_admin"] 
    },
    { 
      href: "/settings/general", 
      title: t("settings.general.title"), 
      desc: t("settings.general.subtitle"), 
      icon: ShieldCheck, 
      color: "#10B981",
      roles: ["system_admin"] 
    },
    { 
      href: "/settings/integrations", 
      title: t("settings.integrations.title"), 
      desc: t("settings.integrations.subtitle"), 
      icon: PlugZap, 
      color: "#F59E0B",
      roles: ["tenant_admin"] 
    },
    { 
      href: "/settings/prompts", 
      title: t("settings.prompts.title"), 
      desc: t("settings.prompts.subtitle"), 
      icon: MessageSquare, 
      color: "#EC4899",
      roles: ["tenant_admin"] 
    },
    { 
      href: "/settings/billing", 
      title: t("settings.billing.title"), 
      desc: t("settings.billing.subtitle"), 
      icon: CreditCard, 
      color: "#6366F1",
      roles: ["tenant_admin"] 
    },
  ];

  const visibleCards = cards.filter(c => c.roles.includes(role || ""));

  return (
    <div className="flex flex-col gap-6">
      <SettingsSubnav />
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {visibleCards.map((card) => (
          <Link key={card.href} href={card.href}>
            <Card className="p-6 h-full hover:border-slate-300 transition-all group">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform" style={{ background: `${card.color}15`, color: card.color }}>
                <card.icon size={24} />
              </div>
              <h3 className="text-lg font-bold text-slate-900 mb-1">{card.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed mb-4">{card.desc}</p>
              <div className="text-xs font-bold uppercase tracking-widest text-slate-400 group-hover:text-indigo-600 flex items-center gap-2">
                {t("common.edit")} <span className="text-lg">→</span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
