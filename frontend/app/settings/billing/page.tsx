"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle2, Zap, ArrowUpRight, ShieldCheck, HelpCircle,
  Package, CreditCard, LayoutGrid, Info, Plus, Loader2,
  Star, ExternalLink, AlertTriangle,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

/* ── Types ──────────────────────────────────────────────────────────────── */

interface PlanPublic {
  slug: string;
  name: string;
  description: string | null;
  price_monthly_cents: number;
  price_yearly_cents: number | null;
  trial_days: number;
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number;
  max_connectors: number;
  features: string[];
  highlight: boolean;
  stripe_price_id: string | null;
}

interface AddonPublic {
  slug: string;
  name: string;
  description: string | null;
  category: string | null;
  icon: string | null;
  price_monthly_cents: number;
  stripe_price_id: string | null;
}

interface SubscriptionInfo {
  has_subscription: boolean;
  status: string;
  current_period_end: string | null;
}

interface PlanInfo {
  slug: string;
  name: string;
  features: Record<string, boolean>;
  limits: {
    max_members: number | null;
    max_monthly_messages: number | null;
    max_channels: number;
    max_connectors: number;
  };
}

interface UsageInfo {
  messages_used: number;
  members_count: number;
}

/* ── Page ───────────────────────────────────────────────────────────────── */

export default function BillingPage() {
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [currentPlan, setCurrentPlan] = useState<PlanInfo | null>(null);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [plans, setPlans] = useState<PlanPublic[]>([]);
  const [addons, setAddons] = useState<AddonPublic[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [billingInterval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const searchParams = useSearchParams();

  async function loadData() {
    try {
      const [pRes, permRes, addonRes] = await Promise.all([
        apiFetch("/admin/billing/plans"),
        apiFetch("/admin/permissions"),
        apiFetch("/admin/plans/public/addons"),
      ]);

      if (pRes.ok) setPlans(await pRes.json());
      if (addonRes.ok) setAddons(await addonRes.json());

      if (permRes.ok) {
        const data = await permRes.json();
        setSubscription(data.subscription);
        setCurrentPlan(data.plan);
        setUsage({
          messages_used: data.usage.messages_used,
          members_count: data.usage.members_count,
        });
      }
    } finally {
      setLoading(false);
    }
  }

  // Verify Stripe session on return from checkout
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    const isCheckout = searchParams.get("checkout") === "success";

    if (sessionId && isCheckout) {
      (async () => {
        try {
          const res = await apiFetch("/admin/billing/verify-session", {
            method: "POST",
            body: JSON.stringify({ session_id: sessionId }),
          });
          if (res.ok) {
            const data = await res.json();
            if (data.plan_activated) {
              // Plan was activated – reload data to reflect new plan
              await loadData();
              return;
            }
          }
        } catch (e) {
          console.error("verify-session failed", e);
        }
        // Fallback: just load data normally
        loadData();
      })();
    } else {
      loadData();
    }
  }, []);

  const handleUpgrade = async (slug: string) => {
    setCheckoutLoading(slug);
    try {
      const res = await apiFetch("/admin/billing/checkout-session", {
        method: "POST",
        body: JSON.stringify({ plan_slug: slug }),
      });
      if (res.ok) {
        const { url } = await res.json();
        window.location.href = url;
      }
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handleAddonCheckout = async (addon: AddonPublic) => {
    if (!addon.stripe_price_id) return;
    setCheckoutLoading(addon.slug);
    try {
      const res = await apiFetch("/admin/billing/addon-checkout", {
        method: "POST",
        body: JSON.stringify({
          addon_slug: addon.slug,
          price_id: addon.stripe_price_id,
          quantity: 1,
        }),
      });
      if (res.ok) {
        const { url } = await res.json();
        window.location.href = url;
      }
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    const res = await apiFetch("/admin/billing/customer-portal", { method: "POST" });
    if (res.ok) {
      const { url } = await res.json();
      window.location.href = url;
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <SettingsSubnav />
        <div className="p-12 text-center flex flex-col items-center gap-4">
          <Loader2 className="animate-spin text-indigo-600" size={32} />
          <span className="text-sm text-slate-400">Lade Billing-Daten...</span>
        </div>
      </div>
    );
  }

  const hasYearlyPlans = plans.some(p => p.price_yearly_cents != null && p.price_yearly_cents > 0);

  return (
    <div className="flex flex-col gap-6">
      <SettingsSubnav />

      <SectionHeader
        title="Abonnement & Nutzung"
        subtitle="Verwalte deinen SaaS-Plan, Add-ons und überwache deinen Verbrauch."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left Column ── */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Current Plan Card */}
          <Card className="p-6 bg-slate-900 border-slate-800 text-white relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10"><Package size={120} /></div>
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="success" className="bg-green-500/20 text-green-400 border-green-500/30">
                  {subscription?.status?.toUpperCase() || "AKTIV"}
                </Badge>
                {currentPlan?.slug && currentPlan.slug !== "starter" && (
                  <Badge className="bg-indigo-500 text-white border-none flex items-center gap-1">
                    <Zap size={10} fill="currentColor" /> {currentPlan.name}
                  </Badge>
                )}
              </div>
              <h2 className="text-3xl font-black mb-1">{currentPlan?.name || "Starter Plan"}</h2>
              <p className="text-slate-400 text-sm">
                {subscription?.current_period_end
                  ? `Nächste Abrechnung am ${new Date(subscription.current_period_end).toLocaleDateString("de-DE")}`
                  : "Kein aktives Abonnement"}
              </p>

              <div className="mt-8 flex gap-4">
                <button
                  onClick={handlePortal}
                  className="px-4 py-2 bg-white text-slate-900 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-slate-100 transition-colors"
                >
                  Stripe Portal <ExternalLink size={14} />
                </button>
              </div>
            </div>
          </Card>

          {/* Usage Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UsageCard
              label="Konversationen"
              used={usage?.messages_used || 0}
              limit={currentPlan?.limits?.max_monthly_messages ?? null}
              unit="Nachr."
            />
            <UsageCard
              label="Kontakte"
              used={usage?.members_count || 0}
              limit={currentPlan?.limits?.max_members ?? null}
              unit="Mitgl."
            />
          </div>

          {/* Dynamic Add-ons */}
          {addons.length > 0 && (
            <div className="flex flex-col gap-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <LayoutGrid size={20} className="text-indigo-600" /> Verfügbare Add-ons
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {addons.map(a => (
                  <div
                    key={a.slug}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-200 transition-colors flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-slate-900">{a.name}</span>
                        <span className="text-xs font-bold text-indigo-600">
                          +{(a.price_monthly_cents / 100).toFixed(0)}€/mtl.
                        </span>
                      </div>
                      {a.description && (
                        <p className="text-xs text-slate-500 leading-relaxed">{a.description}</p>
                      )}
                      {a.category && (
                        <Badge variant="default" size="xs" className="mt-2">{a.category}</Badge>
                      )}
                    </div>
                    <button
                      onClick={() => handleAddonCheckout(a)}
                      disabled={!a.stripe_price_id || checkoutLoading === a.slug}
                      className="mt-4 text-xs font-bold text-slate-400 hover:text-indigo-600 flex items-center gap-1 transition-colors disabled:opacity-50"
                    >
                      {checkoutLoading === a.slug ? "Wird geladen..." : "Hinzufügen"} <Plus size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── Right Column: Plan Comparison ── */}
        <div className="flex flex-col gap-4">
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <ArrowUpRight size={20} className="text-indigo-600" /> Plan wechseln
          </h3>

          {/* Billing Interval Toggle */}
          {hasYearlyPlans && (
            <div className="flex gap-1 p-1 bg-slate-100 rounded-lg">
              <button
                onClick={() => setBillingInterval("monthly")}
                className={`flex-1 py-2 rounded-md text-xs font-bold transition-all ${
                  billingInterval === "monthly"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                Monatlich
              </button>
              <button
                onClick={() => setBillingInterval("yearly")}
                className={`flex-1 py-2 rounded-md text-xs font-bold transition-all ${
                  billingInterval === "yearly"
                    ? "bg-white text-slate-900 shadow-sm"
                    : "text-slate-500 hover:text-slate-700"
                }`}
              >
                Jährlich
                <span className="ml-1 text-green-600 text-[10px]">spare bis zu 20%</span>
              </button>
            </div>
          )}

          <div className="flex flex-col gap-3">
            {plans.map(p => {
              const isCurrent = currentPlan?.slug === p.slug;
              const price = billingInterval === "yearly" && p.price_yearly_cents
                ? p.price_yearly_cents
                : p.price_monthly_cents;
              const priceLabel = billingInterval === "yearly" && p.price_yearly_cents
                ? `${(p.price_yearly_cents / 100).toFixed(0)}€/Jahr`
                : p.price_monthly_cents === 0
                  ? "Individuell"
                  : `${(p.price_monthly_cents / 100).toFixed(0)}€/Mo`;

              return (
                <button
                  key={p.slug}
                  onClick={() => !isCurrent && handleUpgrade(p.slug)}
                  disabled={isCurrent || !!checkoutLoading}
                  className={`p-4 rounded-xl border text-left transition-all relative ${
                    isCurrent
                      ? "bg-slate-50 border-slate-200 cursor-default"
                      : p.highlight
                        ? "bg-white border-indigo-200 hover:shadow-lg hover:shadow-indigo-50 ring-1 ring-indigo-100"
                        : "bg-white border-slate-200 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-50"
                  }`}
                >
                  {p.highlight && !isCurrent && (
                    <div className="absolute -top-2.5 right-3 bg-indigo-600 text-white text-[9px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                      <Star size={8} fill="currentColor" /> Empfohlen
                    </div>
                  )}
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-slate-900">{p.name}</span>
                    {isCurrent ? (
                      <Badge variant="success">Aktuell</Badge>
                    ) : (
                      <span className="text-sm font-black text-indigo-600">{priceLabel}</span>
                    )}
                  </div>
                  {p.description && (
                    <p className="text-[11px] text-slate-400 mb-2">{p.description}</p>
                  )}
                  <div className="flex flex-col gap-1">
                    {(p.features || []).slice(0, 4).map((f, i) => (
                      <div key={i} className="text-xs text-slate-500 flex items-center gap-1.5">
                        <CheckCircle2 size={10} className="text-green-500 shrink-0" /> {f}
                      </div>
                    ))}
                  </div>
                  {p.trial_days > 0 && !isCurrent && (
                    <div className="mt-2 text-[10px] text-amber-600 font-bold flex items-center gap-1">
                      <ShieldCheck size={10} /> {p.trial_days} Tage kostenlos testen
                    </div>
                  )}
                  {!isCurrent && (
                    <div className="mt-3 text-xs font-bold text-indigo-600 flex items-center gap-1">
                      {checkoutLoading === p.slug ? "Wird geladen..." : "Jetzt auswählen"} <ArrowUpRight size={12} />
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <Card className="p-4 bg-indigo-50 border-indigo-100">
            <div className="flex gap-3">
              <Info className="text-indigo-600 shrink-0" size={18} />
              <div className="text-xs text-indigo-900 leading-relaxed">
                <strong>Nutzungsbasierte Abrechnung:</strong> Überschreitungen der Inklusiv-Limits werden automatisch am Monatsende über Stripe abgerechnet.
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-Components ─────────────────────────────────────────────────────── */

function UsageCard({ label, used, limit, unit }: {
  label: string; used: number; limit: number | null; unit: string;
}) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  const isWarning = pct > 80;
  const isDanger = pct > 95;

  return (
    <Card className="p-5 bg-white border-slate-200">
      <div className="flex justify-between items-center mb-4">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{label}</span>
        <span className={`text-xs font-bold ${isDanger ? "text-red-600" : isWarning ? "text-amber-600" : "text-slate-900"}`}>
          {used.toLocaleString("de-DE")} / {limit ? limit.toLocaleString("de-DE") : "∞"} {unit}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full transition-all duration-1000 ${
            isDanger ? "bg-red-500" : isWarning ? "bg-amber-500" : "bg-indigo-600"
          }`}
          style={{ width: `${limit ? pct : 5}%` }}
        />
      </div>
      <div className="flex justify-between items-center">
        <div className="text-[10px] text-slate-400">
          {limit ? `${Math.round(pct)}% verbraucht` : "Flatrate aktiv"}
        </div>
        {isWarning && limit && (
          <div className="flex items-center gap-1 text-[10px] text-amber-600 font-bold">
            <AlertTriangle size={10} /> Limit fast erreicht
          </div>
        )}
      </div>
    </Card>
  );
}
