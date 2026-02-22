"use client";

import { useEffect, useState } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";

interface Plan {
  name: string;
  slug: string;
  price_monthly_cents: number;
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number;
  whatsapp_enabled: boolean;
  telegram_enabled: boolean;
  sms_enabled: boolean;
  email_channel_enabled: boolean;
  voice_enabled: boolean;
  memory_analyzer_enabled: boolean;
  custom_prompts_enabled: boolean;
}

interface Subscription {
  has_subscription: boolean;
  status: string;
  stripe_subscription_id: string | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  plan: Plan;
}

interface Usage {
  period: { year: number; month: number };
  messages_inbound: number;
  messages_outbound: number;
  messages_total: number;
  messages_limit: number | null;
  messages_pct: number | null;
  active_members: number;
  llm_tokens_used: number;
}

function formatCents(cents: number): string {
  if (cents === 0) return "Kostenlos";
  return `€${(cents / 100).toFixed(2)}/Monat`;
}

function ProgressBar({ value, max }: { value: number; max: number | null }) {
  if (!max) return <span className="text-gray-400 text-xs">Unbegrenzt</span>;
  const pct = Math.min(100, Math.round((value / max) * 100));
  const color = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-yellow-500" : "bg-blue-500";
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{value.toLocaleString()} / {max.toLocaleString()}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function FeatureFlag({ label, enabled }: { label: string; enabled: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <span className="text-sm text-gray-300">{label}</span>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${enabled ? "bg-green-900/50 text-green-400" : "bg-gray-800 text-gray-500"}`}>
        {enabled ? "Aktiv" : "Nicht verfügbar"}
      </span>
    </div>
  );
}

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [subRes, usageRes] = await Promise.all([
          apiFetch("/admin/billing/subscription"),
          apiFetch("/admin/billing/usage"),
        ]);
        if (!subRes.ok) throw new Error(`Subscription: HTTP ${subRes.status}`);
        if (!usageRes.ok) throw new Error(`Usage: HTTP ${usageRes.status}`);
        const [subData, usageData] = await Promise.all([subRes.json(), usageRes.json()]);
        setSub(subData);
        setUsage(usageData);
      } catch (e) {
        setError(`Fehler beim Laden: ${e}`);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="p-8 text-gray-400">Wird geladen...</div>
    </div>
  );

  if (error) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <SettingsSubnav />
        <div className="p-8">
          <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
        </div>
      </div>
    );
  }

  const plan = sub?.plan;
  const MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="max-w-3xl mx-auto p-6 space-y-8" style={{ width: "100%" }}>
      <div>
        <h1 className="text-2xl font-bold text-white">Abonnement & Nutzung</h1>
        <p className="text-gray-400 mt-1 text-sm">Dein aktueller Plan und der Verbrauch diesen Monat.</p>
      </div>

      {/* Current plan */}
      {plan && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{plan.name}</h2>
              <p className="text-gray-400 text-sm">{formatCents(plan.price_monthly_cents)}</p>
            </div>
            <span className={`text-xs font-medium px-3 py-1 rounded-full border ${
              sub?.status === "active" || !sub?.has_subscription
                ? "bg-green-900/40 text-green-400 border-green-700"
                : sub?.status === "trialing"
                ? "bg-blue-900/40 text-blue-400 border-blue-700"
                : "bg-yellow-900/40 text-yellow-400 border-yellow-700"
            }`}>
              {sub?.has_subscription ? sub.status : "Free"}
            </span>
          </div>

          {sub?.trial_ends_at && (
            <div className="text-sm text-blue-400">
              Trial läuft bis: {new Date(sub.trial_ends_at).toLocaleDateString("de-DE")}
            </div>
          )}
          {sub?.current_period_end && (
            <div className="text-sm text-gray-400">
              Nächste Abrechnung: {new Date(sub.current_period_end).toLocaleDateString("de-DE")}
            </div>
          )}

          <div className="pt-2 space-y-0">
            <h3 className="text-sm font-medium text-gray-300 mb-2">Features in diesem Plan</h3>
            <FeatureFlag label="WhatsApp" enabled={plan.whatsapp_enabled} />
            <FeatureFlag label="Telegram" enabled={plan.telegram_enabled} />
            <FeatureFlag label="SMS" enabled={plan.sms_enabled} />
            <FeatureFlag label="E-Mail-Kanal" enabled={plan.email_channel_enabled} />
            <FeatureFlag label="Voice" enabled={plan.voice_enabled} />
            <FeatureFlag label="Memory Analyzer" enabled={plan.memory_analyzer_enabled} />
            <FeatureFlag label="Custom Prompts" enabled={plan.custom_prompts_enabled} />
          </div>
        </div>
      )}

      {/* Usage this month */}
      {usage && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h2 className="text-lg font-semibold text-white">
            Nutzung — {MONTH_NAMES[(usage.period.month - 1)]} {usage.period.year}
          </h2>

          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-300 mb-1">Nachrichten gesamt (Ein + Ausgehend)</p>
              <ProgressBar value={usage.messages_total} max={usage.messages_limit} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">{usage.messages_inbound.toLocaleString()}</p>
                <p className="text-xs text-gray-400 mt-1">Eingehend</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">{usage.messages_outbound.toLocaleString()}</p>
                <p className="text-xs text-gray-400 mt-1">Ausgehend</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">{usage.active_members.toLocaleString()}</p>
                <p className="text-xs text-gray-400 mt-1">Aktive Mitglieder</p>
              </div>
              <div className="bg-gray-800 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">{usage.llm_tokens_used.toLocaleString()}</p>
                <p className="text-xs text-gray-400 mt-1">LLM Tokens</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upgrade hint for starter */}
      {plan?.slug === "starter" && (
        <div className="bg-blue-950/40 border border-blue-800 rounded-xl p-4 text-sm text-blue-300">
          <strong>Upgrade auf Pro:</strong> Unbegrenzte Nachrichten, Telegram, SMS, E-Mail-Kanal, Memory Analyzer und Custom Prompts — für €99/Monat.
          Kontaktiere uns unter <span className="font-mono">support@arni.ai</span> oder richte Stripe in den Integrationseinstellungen ein.
        </div>
      )}
      </div>
    </div>
  );
}
