"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";
import { usePermissions, PLAN_DISPLAY, LLM_MODELS, PlanSlug } from "@/lib/permissions";
import {
  Crown, Zap, AlertTriangle, CheckCircle2, ArrowRight, ExternalLink,
  BarChart3, MessageSquare, Users, Brain, Link2, Cpu, Plus, X,
  TrendingUp, Shield, Sparkles, ChevronDown
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────────── */

interface CatalogPlan {
  slug: string;
  name: string;
  price_monthly_cents: number;
  price_yearly_cents: number | null;
  is_custom_pricing: boolean;
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number | null;
  max_users: number | null;
  max_connectors: number | null;
  max_monthly_llm_tokens: number | null;
  ai_tier: string;
  allowed_llm_models: string[] | null;
  features: string[];
  highlight?: boolean;
  overage: {
    per_conversation_cents: number | null;
    per_user_cents: number | null;
    per_connector_cents: number | null;
    per_channel_cents: number | null;
  };
}

interface CatalogAddon {
  slug: string;
  name: string;
  description: string;
  category: string;
  price_monthly_cents: number;
  is_per_unit: boolean;
  unit_label: string | null;
  min_plan_slug: string | null;
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

const c = {
  bg: "oklch(0.09 0.04 270)",
  card: "oklch(0.12 0.04 270)",
  border: "oklch(0.22 0.04 270)",
  accent: "oklch(0.62 0.22 292)",
  gold: "oklch(0.8 0.16 85)",
  green: "oklch(0.72 0.19 155)",
  red: "oklch(0.65 0.22 25)",
  text: "oklch(0.97 0.005 270)",
  textSub: "oklch(0.75 0.01 270)",
  textMuted: "oklch(0.6 0.015 270)",
};

function formatCents(cents: number): string {
  return `${(cents / 100).toFixed(0)} €`;
}

function formatNumber(n: number | null): string {
  if (n === null) return "Unbegrenzt";
  return n.toLocaleString("de-DE");
}

/* ── Progress Bar ──────────────────────────────────────────────────────── */

function UsageBar({ label, icon: Icon, used, max, unit = "" }: {
  label: string;
  icon: any;
  used: number;
  max: number | null;
  unit?: string;
}) {
  const isUnlimited = max === null;
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((used / (max || 1)) * 100));
  const isWarning = !isUnlimited && pct >= 80;
  const isCritical = !isUnlimited && pct >= 100;

  return (
    <div className="p-4 rounded-xl" style={{ background: "oklch(0.1 0.04 270)", border: `1px solid ${isCritical ? c.red + "40" : isWarning ? c.gold + "40" : c.border}` }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Icon size={14} style={{ color: isCritical ? c.red : isWarning ? c.gold : c.accent }} />
          <span className="text-sm font-medium" style={{ color: c.text }}>{label}</span>
        </div>
        <span className="text-xs" style={{ color: isCritical ? c.red : isWarning ? c.gold : c.textMuted }}>
          {used.toLocaleString("de-DE")}{unit} / {isUnlimited ? "∞" : max!.toLocaleString("de-DE")}{unit}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: "oklch(0.18 0.04 270)" }}>
        <div className="h-full rounded-full transition-all duration-500" style={{
          width: isUnlimited ? "0%" : `${pct}%`,
          background: isCritical ? c.red : isWarning ? c.gold : c.accent,
        }} />
      </div>
      {isCritical && (
        <div className="flex items-center gap-1.5 mt-2">
          <AlertTriangle size={12} style={{ color: c.red }} />
          <span className="text-xs" style={{ color: c.red }}>Limit erreicht — Overage wird berechnet</span>
        </div>
      )}
      {isWarning && !isCritical && (
        <div className="flex items-center gap-1.5 mt-2">
          <AlertTriangle size={12} style={{ color: c.gold }} />
          <span className="text-xs" style={{ color: c.gold }}>{pct}% verbraucht</span>
        </div>
      )}
    </div>
  );
}

/* ── Plan Card ─────────────────────────────────────────────────────────── */

function PlanCard({ plan, isCurrent, onSelect, loading, yearly }: {
  plan: CatalogPlan;
  isCurrent: boolean;
  onSelect: (slug: string) => void;
  loading: boolean;
  yearly: boolean;
}) {
  const price = yearly && plan.price_yearly_cents ? plan.price_yearly_cents / 12 : plan.price_monthly_cents;
  const isHighlight = plan.highlight;

  return (
    <div className="relative flex flex-col rounded-xl p-5 space-y-4 transition-all hover:scale-[1.01]" style={{
      background: isHighlight ? "oklch(0.13 0.04 270)" : c.card,
      border: `1px solid ${isCurrent ? c.green + "60" : isHighlight ? c.accent + "40" : c.border}`,
      boxShadow: isCurrent ? `0 0 20px ${c.green}15` : isHighlight ? `0 0 20px ${c.accent}10` : "none",
    }}>
      {isCurrent && (
        <div className="absolute -top-3 right-4 flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold" style={{ background: c.green, color: "oklch(0.15 0.04 155)" }}>
          <CheckCircle2 size={11} /> Aktuell
        </div>
      )}
      {isHighlight && !isCurrent && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold" style={{ background: c.accent, color: "white" }}>
          <Sparkles size={11} /> Empfohlen
        </div>
      )}

      <div>
        <h3 className="text-base font-bold" style={{ color: c.text }}>{plan.name}</h3>
        {plan.is_custom_pricing ? (
          <p className="text-2xl font-extrabold mt-1" style={{ color: c.gold }}>Individuell</p>
        ) : (
          <p className="text-2xl font-extrabold mt-1" style={{ color: c.text }}>
            {formatCents(Math.round(price))}
            <span className="text-sm font-normal ml-1" style={{ color: c.textMuted }}>/Monat</span>
          </p>
        )}
      </div>

      <ul className="space-y-1.5 flex-1">
        {plan.features.slice(0, 8).map((f) => (
          <li key={f} className="flex items-start gap-2 text-xs" style={{ color: c.textSub }}>
            <CheckCircle2 size={12} className="shrink-0 mt-0.5" style={{ color: isHighlight ? c.accent : "oklch(0.5 0.12 292)" }} />
            {f}
          </li>
        ))}
        {plan.features.length > 8 && (
          <li className="text-xs" style={{ color: c.textMuted }}>+{plan.features.length - 8} weitere Features</li>
        )}
      </ul>

      {isCurrent ? (
        <div className="text-center text-sm font-medium py-2" style={{ color: c.green }}>Dein aktueller Plan</div>
      ) : plan.is_custom_pricing ? (
        <a href="mailto:enterprise@ariia.ai" className="block w-full py-2.5 rounded-lg text-sm font-semibold text-center transition-all" style={{ background: c.gold, color: "oklch(0.15 0.04 85)" }}>
          Sales kontaktieren
        </a>
      ) : (
        <button onClick={() => onSelect(plan.slug)} disabled={loading}
          className="w-full py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-50"
          style={{ background: isHighlight ? c.accent : "oklch(0.2 0.04 270)", color: "white" }}>
          {loading ? "Wird geladen..." : `Zu ${plan.name} wechseln`}
        </button>
      )}
    </div>
  );
}

/* ── Addon Card ────────────────────────────────────────────────────────── */

function AddonCard({ addon, active, onBuy, loading }: {
  addon: CatalogAddon;
  active: boolean;
  onBuy: (slug: string) => void;
  loading: boolean;
}) {
  const categoryColors: Record<string, string> = {
    ai: "oklch(0.62 0.22 292)",
    communication: "oklch(0.72 0.19 155)",
    platform: "oklch(0.8 0.16 85)",
    members: "oklch(0.65 0.18 200)",
  };
  const color = categoryColors[addon.category] || c.accent;

  return (
    <div className="p-4 rounded-xl flex items-start justify-between gap-3" style={{ background: c.card, border: `1px solid ${active ? color + "40" : c.border}` }}>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold" style={{ color: c.text }}>{addon.name}</span>
          {active && <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${color}15`, color }}>Aktiv</span>}
        </div>
        <p className="text-xs mb-2" style={{ color: c.textMuted }}>{addon.description}</p>
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold" style={{ color }}>{formatCents(addon.price_monthly_cents)}/mo</span>
          {addon.min_plan_slug && (
            <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: "oklch(0.15 0.04 270)", color: c.textMuted }}>
              ab {addon.min_plan_slug}
            </span>
          )}
        </div>
      </div>
      {!active && (
        <button onClick={() => onBuy(addon.slug)} disabled={loading}
          className="shrink-0 p-2 rounded-lg transition-all disabled:opacity-50"
          style={{ background: `${color}15`, color }}>
          <Plus size={16} />
        </button>
      )}
    </div>
  );
}

/* ── Main Page ─────────────────────────────────────────────────────────── */

export default function BillingPage() {
  const { plan: currentPlan, subscription, usage, addons: activeAddons, llm, reload } = usePermissions();
  const [catalogPlans, setCatalogPlans] = useState<CatalogPlan[]>([]);
  const [catalogAddons, setCatalogAddons] = useState<CatalogAddon[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [portalLoading, setPortalLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [yearly, setYearly] = useState(false);
  const [showAllPlans, setShowAllPlans] = useState(false);
  const searchParams = useSearchParams();

  useEffect(() => {
    const checkout = searchParams.get("checkout");
    const addonCheckout = searchParams.get("addon_checkout");
    if (checkout === "success") {
      setSuccessMsg("Abonnement erfolgreich aktiviert! Es kann einen Moment dauern, bis der Status aktualisiert wird.");
      reload();
    }
    if (addonCheckout === "success") {
      setSuccessMsg("Add-on erfolgreich aktiviert!");
      reload();
    }
  }, [searchParams]);

  useEffect(() => {
    const load = async () => {
      try {
        const [plansRes, addonsRes] = await Promise.all([
          apiFetch("/admin/billing/plans"),
          apiFetch("/admin/billing/addons"),
        ]);
        if (plansRes.ok) setCatalogPlans(await plansRes.json());
        if (addonsRes.ok) setCatalogAddons(await addonsRes.json());
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
      // If already subscribed, use change-plan endpoint
      const endpoint = subscription.has_subscription && subscription.status === "active"
        ? "/admin/billing/change-plan"
        : "/admin/billing/checkout-session";
      const body = endpoint.includes("change-plan")
        ? { new_plan_slug: planSlug, billing_interval: yearly ? "yearly" : "monthly" }
        : {
            plan_slug: planSlug,
            billing_interval: yearly ? "yearly" : "monthly",
            success_url: window.location.origin + "/settings/billing?checkout=success",
            cancel_url: window.location.origin + "/settings/billing?checkout=canceled",
          };

      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || "Unbekannter Fehler");
      }
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setSuccessMsg(data.message || "Plan erfolgreich gewechselt!");
        reload();
        setCheckoutLoading(false);
      }
    } catch (e: any) {
      setError(`Fehler: ${e.message}`);
      setCheckoutLoading(false);
    }
  };

  const handleAddonCheckout = async (addonSlug: string) => {
    setCheckoutLoading(true);
    try {
      const res = await apiFetch("/admin/billing/addon-checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          addon_slug: addonSlug,
          quantity: 1,
          success_url: window.location.origin + "/settings/billing?addon_checkout=success",
          cancel_url: window.location.origin + "/settings/billing?addon_checkout=canceled",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(err.detail || "Unbekannter Fehler");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (e: any) {
      setError(`Add-on Fehler: ${e.message}`);
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
    } catch (e: any) {
      setError(`Portal-Fehler: ${e.message}`);
      setPortalLoading(false);
    }
  };

  const planDisplay = PLAN_DISPLAY[currentPlan.slug as PlanSlug] || PLAN_DISPLAY.starter;
  const activeAddonSlugs = activeAddons.map(a => a.slug);

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="p-8" style={{ color: c.textMuted }}>Wird geladen...</div>
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="max-w-5xl mx-auto p-6 space-y-8" style={{ width: "100%" }}>

        {/* ── Header ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: c.text }}>Abonnement & Nutzung</h1>
            <p className="text-sm mt-1" style={{ color: c.textMuted }}>Verwalte deinen Plan, Add-ons und überwache den Verbrauch.</p>
          </div>
          {subscription.has_subscription && (
            <button onClick={handlePortal} disabled={portalLoading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
              style={{ background: "oklch(0.15 0.04 270)", color: c.textSub, border: `1px solid ${c.border}` }}>
              <ExternalLink size={14} /> {portalLoading ? "Öffne..." : "Stripe Portal"}
            </button>
          )}
        </div>

        {/* ── Banners ─────────────────────────────────────────────────── */}
        {successMsg && (
          <div className="flex items-center justify-between rounded-lg px-4 py-3 text-sm" style={{ background: `${c.green}15`, border: `1px solid ${c.green}30`, color: c.green }}>
            <div className="flex items-center gap-2"><CheckCircle2 size={16} /> {successMsg}</div>
            <button onClick={() => setSuccessMsg(null)}><X size={14} /></button>
          </div>
        )}
        {error && (
          <div className="flex items-center justify-between rounded-lg px-4 py-3 text-sm" style={{ background: `${c.red}15`, border: `1px solid ${c.red}30`, color: c.red }}>
            <div className="flex items-center gap-2"><AlertTriangle size={16} /> {error}</div>
            <button onClick={() => setError(null)}><X size={14} /></button>
          </div>
        )}

        {/* ── Current Plan Card ───────────────────────────────────────── */}
        <div className="rounded-xl p-6" style={{ background: c.card, border: `1px solid ${planDisplay.color}30` }}>
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: `${planDisplay.color}15` }}>
                <Crown size={20} style={{ color: planDisplay.color }} />
              </div>
              <div>
                <h2 className="text-lg font-bold" style={{ color: c.text }}>{currentPlan.name}</h2>
                <p className="text-sm" style={{ color: c.textMuted }}>
                  {currentPlan.is_custom_pricing ? "Individuelles Pricing" : `${formatCents(currentPlan.price_monthly_cents)}/Monat`}
                  {currentPlan.price_yearly_cents && !currentPlan.is_custom_pricing && (
                    <span style={{ color: c.textMuted }}> · {formatCents(Math.round(currentPlan.price_yearly_cents / 12))}/Monat jährlich</span>
                  )}
                </p>
              </div>
            </div>
            <span className="text-xs font-medium px-3 py-1 rounded-full" style={{
              background: subscription.status === "active" ? `${c.green}15` : subscription.status === "trialing" ? `${c.accent}15` : `${c.gold}15`,
              color: subscription.status === "active" ? c.green : subscription.status === "trialing" ? c.accent : c.gold,
              border: `1px solid ${subscription.status === "active" ? c.green : subscription.status === "trialing" ? c.accent : c.gold}30`,
            }}>
              {subscription.status === "active" ? "Aktiv" : subscription.status === "trialing" ? "Testphase" : subscription.status === "past_due" ? "Zahlung ausstehend" : subscription.has_subscription ? subscription.status : "Kein Abo"}
            </span>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <div className="p-3 rounded-lg text-center" style={{ background: "oklch(0.1 0.04 270)" }}>
              <p className="text-xs mb-1" style={{ color: c.textMuted }}>Kanäle</p>
              <p className="text-lg font-bold" style={{ color: c.text }}>{usage.active_channels_count} / {currentPlan.limits.max_channels === null ? "∞" : currentPlan.limits.max_channels}</p>
            </div>
            <div className="p-3 rounded-lg text-center" style={{ background: "oklch(0.1 0.04 270)" }}>
              <p className="text-xs mb-1" style={{ color: c.textMuted }}>Users</p>
              <p className="text-lg font-bold" style={{ color: c.text }}>{usage.active_users_count} / {currentPlan.limits.max_users === null ? "∞" : currentPlan.limits.max_users}</p>
            </div>
            <div className="p-3 rounded-lg text-center" style={{ background: "oklch(0.1 0.04 270)" }}>
              <p className="text-xs mb-1" style={{ color: c.textMuted }}>Connectors</p>
              <p className="text-lg font-bold" style={{ color: c.text }}>{usage.active_connectors_count} / {currentPlan.limits.max_connectors === null ? "∞" : currentPlan.limits.max_connectors}</p>
            </div>
            <div className="p-3 rounded-lg text-center" style={{ background: "oklch(0.1 0.04 270)" }}>
              <p className="text-xs mb-1" style={{ color: c.textMuted }}>AI Tier</p>
              <p className="text-lg font-bold capitalize" style={{ color: c.accent }}>{llm.ai_tier}</p>
            </div>
          </div>

          {/* AI Models */}
          <div className="p-3 rounded-lg mb-4" style={{ background: "oklch(0.1 0.04 270)" }}>
            <p className="text-xs font-medium mb-2" style={{ color: c.textMuted }}>Verfügbare AI-Modelle</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(LLM_MODELS).map(([key, model]) => {
                const isAvailable = llm.allowed_models.includes(key);
                return (
                  <span key={key} className="text-xs px-2.5 py-1 rounded-full" style={{
                    background: isAvailable ? `${c.accent}15` : "oklch(0.15 0.04 270)",
                    color: isAvailable ? c.accent : "oklch(0.35 0.02 270)",
                    border: `1px solid ${isAvailable ? c.accent + "30" : "oklch(0.2 0.04 270)"}`,
                  }}>
                    {model.name}
                  </span>
                );
              })}
            </div>
          </div>

          {subscription.current_period_end && (
            <p className="text-xs" style={{ color: c.textMuted }}>
              Nächste Abrechnung: {new Date(subscription.current_period_end).toLocaleDateString("de-DE", { day: "2-digit", month: "long", year: "numeric" })}
            </p>
          )}
          {subscription.trial_ends_at && (
            <p className="text-xs" style={{ color: c.accent }}>
              Testphase endet: {new Date(subscription.trial_ends_at).toLocaleDateString("de-DE", { day: "2-digit", month: "long", year: "numeric" })}
            </p>
          )}
        </div>

        {/* ── Usage ───────────────────────────────────────────────────── */}
        <div>
          <h2 className="text-lg font-bold mb-4" style={{ color: c.text }}>Nutzung diesen Monat</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            <UsageBar label="Konversationen" icon={MessageSquare} used={usage.conversations_count || usage.messages_used} max={currentPlan.limits.max_monthly_messages} />
            <UsageBar label="Mitglieder" icon={Users} used={usage.members_count} max={currentPlan.limits.max_members} />
            <UsageBar label="LLM-Tokens" icon={Brain} used={usage.llm_tokens_used} max={currentPlan.limits.max_monthly_llm_tokens} />
            <UsageBar label="Nachrichten (Ein + Aus)" icon={Zap} used={usage.messages_used} max={currentPlan.limits.max_monthly_messages} />
          </div>

          {/* Overage Info */}
          {(usage.overage_conversations > 0 || usage.overage_tokens > 0) && (
            <div className="mt-3 p-4 rounded-xl" style={{ background: `${c.gold}08`, border: `1px solid ${c.gold}30` }}>
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={14} style={{ color: c.gold }} />
                <span className="text-sm font-medium" style={{ color: c.gold }}>Overage diesen Monat</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {usage.overage_conversations > 0 && (
                  <div className="text-xs" style={{ color: c.textSub }}>
                    +{usage.overage_conversations.toLocaleString()} Konversationen · {formatCents(usage.overage_billed_cents || 0)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Plan Selection ──────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold" style={{ color: c.text }}>Plan wechseln</h2>
            <div className="flex items-center gap-3">
              <span className="text-xs" style={{ color: yearly ? c.textMuted : c.text }}>Monatlich</span>
              <button onClick={() => setYearly(!yearly)} className="relative w-11 h-6 rounded-full transition-colors" style={{ background: yearly ? c.accent : "oklch(0.3 0.04 270)" }}>
                <div className="absolute top-1 w-4 h-4 rounded-full transition-transform" style={{ background: "white", transform: yearly ? "translateX(24px)" : "translateX(4px)" }} />
              </button>
              <span className="text-xs" style={{ color: yearly ? c.text : c.textMuted }}>
                Jährlich <span className="px-1.5 py-0.5 rounded text-xs" style={{ background: c.accentSoft, color: c.accent }}>-20%</span>
              </span>
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {catalogPlans.map((p) => (
              <PlanCard key={p.slug} plan={p} isCurrent={currentPlan.slug === p.slug} onSelect={handleCheckout} loading={checkoutLoading} yearly={yearly} />
            ))}
          </div>
          <p className="text-xs text-center mt-3" style={{ color: c.textMuted }}>
            Sichere Bezahlung über Stripe. Anteilige Abrechnung bei Plan-Wechsel. Kündigung jederzeit.
          </p>
        </div>

        {/* ── Add-ons ─────────────────────────────────────────────────── */}
        {catalogAddons.length > 0 && (
          <div>
            <h2 className="text-lg font-bold mb-4" style={{ color: c.text }}>Add-ons</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {catalogAddons.map((addon) => (
                <AddonCard key={addon.slug} addon={addon} active={activeAddonSlugs.includes(addon.slug)} onBuy={handleAddonCheckout} loading={checkoutLoading} />
              ))}
            </div>
          </div>
        )}

        {/* ── Active Add-ons ──────────────────────────────────────────── */}
        {activeAddons.length > 0 && (
          <div>
            <h2 className="text-lg font-bold mb-4" style={{ color: c.text }}>Aktive Add-ons</h2>
            <div className="grid sm:grid-cols-2 gap-3">
              {activeAddons.map((addon) => (
                <div key={addon.slug} className="p-4 rounded-xl flex items-center justify-between" style={{ background: c.card, border: `1px solid ${c.green}30` }}>
                  <div>
                    <span className="text-sm font-medium" style={{ color: c.text }}>{addon.slug}</span>
                    {addon.quantity > 1 && <span className="text-xs ml-2" style={{ color: c.textMuted }}>×{addon.quantity}</span>}
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${c.green}15`, color: c.green }}>Aktiv</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Fallback ────────────────────────────────────────────────── */}
        {catalogPlans.length === 0 && !subscription.has_subscription && (
          <div className="p-4 rounded-xl text-sm" style={{ background: `${c.accent}08`, border: `1px solid ${c.accent}30`, color: c.accent }}>
            <strong>Upgrade verfügbar:</strong> Konfiguriere Stripe in den{" "}
            <a href="/settings/integrations" className="underline">Integrationseinstellungen</a>{" "}
            um direkt upgraden zu können.
          </div>
        )}
      </div>
    </div>
  );
}
