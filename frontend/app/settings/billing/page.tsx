"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface PlanFeature {
  slug: string;
  name: string;
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
  features: string[];
  highlight?: boolean;
}

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

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatCents(cents: number): string {
  if (cents === 0) return "Kostenlos";
  return `€${(cents / 100).toFixed(0)}/Monat`;
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

/* ─── Plan Card ──────────────────────────────────────────────────────────── */

function PlanCard({
  plan,
  current,
  onSelect,
  loading,
}: {
  plan: PlanFeature;
  current: boolean;
  onSelect: (slug: string) => void;
  loading: boolean;
}) {
  return (
    <div
      className={`relative flex flex-col rounded-xl border p-5 space-y-4 transition-all
        ${plan.highlight
          ? "border-blue-600 bg-blue-950/30 shadow-lg shadow-blue-900/20"
          : "border-gray-700 bg-gray-900"}
        ${current ? "ring-2 ring-green-600" : ""}`}
    >
      {plan.highlight && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-xs font-semibold px-3 py-0.5 rounded-full">
          Empfohlen
        </div>
      )}
      {current && (
        <div className="absolute -top-3 right-4 bg-green-600 text-white text-xs font-semibold px-3 py-0.5 rounded-full">
          Aktuell
        </div>
      )}

      <div>
        <h3 className="text-lg font-bold text-white">{plan.name}</h3>
        <p className="text-2xl font-extrabold text-white mt-1">
          {formatCents(plan.price_monthly_cents)}
        </p>
      </div>

      <ul className="space-y-1 flex-1">
        {plan.features.map((f) => (
          <li key={f} className="flex items-center gap-2 text-sm text-gray-300">
            <span className="text-green-400">✓</span>
            {f}
          </li>
        ))}
      </ul>

      {current ? (
        <div className="text-center text-green-400 text-sm font-medium py-2">Dein aktueller Plan</div>
      ) : (
        <button
          onClick={() => onSelect(plan.slug)}
          disabled={loading}
          className={`w-full py-2 rounded-lg text-sm font-semibold transition-all
            ${plan.highlight
              ? "bg-blue-600 hover:bg-blue-500 text-white"
              : "bg-gray-700 hover:bg-gray-600 text-white"}
            disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {loading ? "Wird geladen..." : `Zu ${plan.name} wechseln`}
        </button>
      )}
    </div>
  );
}

/* ─── Main Page ──────────────────────────────────────────────────────────── */

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [catalogPlans, setCatalogPlans] = useState<PlanFeature[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    // Handle Stripe redirect feedback
    const checkout = searchParams.get("checkout");
    if (checkout === "success") {
      setSuccessMsg("🎉 Abonnement erfolgreich aktiviert! Es kann einen Moment dauern, bis der Status aktualisiert wird.");
    }
  }, [searchParams]);

  useEffect(() => {
    const load = async () => {
      try {
        const [subRes, usageRes, plansRes] = await Promise.all([
          apiFetch("/admin/billing/subscription"),
          apiFetch("/admin/billing/usage"),
          apiFetch("/admin/billing/plans"),
        ]);
        if (!subRes.ok) throw new Error(`Subscription: HTTP ${subRes.status}`);
        if (!usageRes.ok) throw new Error(`Usage: HTTP ${usageRes.status}`);
        const [subData, usageData, plansData] = await Promise.all([
          subRes.json(), usageRes.json(), plansRes.ok ? plansRes.json() : [],
        ]);
        setSub(subData);
        setUsage(usageData);
        setCatalogPlans(Array.isArray(plansData) ? plansData : []);
      } catch (e) {
        setError(`Fehler beim Laden: ${e}`);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleCheckout = async (planSlug: string) => {
    setCheckoutLoading(true);
    try {
      const res = await apiFetch("/admin/billing/checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan_slug: planSlug,
          success_url: window.location.origin + "/settings/billing?checkout=success",
          cancel_url: window.location.origin + "/settings/billing?checkout=canceled",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || "Unbekannter Fehler");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (e) {
      setError(`Checkout-Fehler: ${e}`);
      setCheckoutLoading(false);
    }
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await apiFetch("/admin/billing/customer-portal", { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || "Unbekannter Fehler");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (e) {
      setError(`Portal-Fehler: ${e}`);
      setPortalLoading(false);
    }
  };

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="p-8 text-gray-400">Wird geladen...</div>
    </div>
  );

  const plan = sub?.plan;
  const MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const hasStripeSubscription = sub?.has_subscription && sub?.stripe_subscription_id;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="max-w-4xl mx-auto p-6 space-y-8" style={{ width: "100%" }}>

        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-white">Abonnement &amp; Nutzung</h1>
          <p className="text-gray-400 mt-1 text-sm">Dein aktueller Plan und der Verbrauch diesen Monat.</p>
        </div>

        {/* Success / Error banners */}
        {successMsg && (
          <div className="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm">
            {successMsg}
          </div>
        )}
        {error && (
          <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm flex justify-between">
            {error}
            <button onClick={() => setError(null)} className="ml-4 text-red-400 hover:text-red-200">✕</button>
          </div>
        )}

        {/* Current subscription */}
        {plan && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">{plan.name}</h2>
                <p className="text-gray-400 text-sm">{formatCents(plan.price_monthly_cents)}</p>
              </div>
              <span className={`text-xs font-medium px-3 py-1 rounded-full border ${sub?.status === "active" || !sub?.has_subscription
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

            {/* Customer Portal button */}
            {hasStripeSubscription && (
              <div className="pt-2">
                <button
                  onClick={handlePortal}
                  disabled={portalLoading}
                  className="text-sm text-blue-400 hover:text-blue-300 underline disabled:opacity-50"
                >
                  {portalLoading ? "Wird geöffnet..." : "Abonnement verwalten (Stripe Portal) →"}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Usage */}
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

        {/* Plan selection */}
        {catalogPlans.length > 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">Plan wechseln</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {catalogPlans.map((p) => (
                <PlanCard
                  key={p.slug}
                  plan={p}
                  current={plan?.slug === p.slug}
                  onSelect={handleCheckout}
                  loading={checkoutLoading}
                />
              ))}
            </div>
            <p className="text-xs text-gray-500 text-center mt-2">
              Sichere Bezahlung über Stripe. Kündigung jederzeit möglich.
            </p>
          </div>
        )}

        {/* Fallback — kein Stripe konfiguriert */}
        {catalogPlans.length === 0 && plan?.slug === "starter" && (
          <div className="bg-blue-950/40 border border-blue-800 rounded-xl p-4 text-sm text-blue-300">
            <strong>Upgrade verfügbar:</strong> Konfiguriere Stripe in den{" "}
            <a href="/settings/integrations" className="underline hover:text-blue-200">Integrationseinstellungen</a>{" "}
            um direkt upgraden zu können, oder kontaktiere uns unter{" "}
            <span className="font-mono">support@ariia.ai</span>.
          </div>
        )}
      </div>
    </div>
  );
}
