"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  CheckCircle2, Zap, ArrowUpRight, ShieldCheck, HelpCircle,
  Package, CreditCard, LayoutGrid, Info, Plus, Loader2,
  Star, ExternalLink, AlertTriangle, ArrowDownRight, XCircle,
  RotateCcw, Calendar,
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
  display_order?: number;
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
  cancel_at_period_end?: boolean;
  cancellation_effective_date?: string;
  pending_downgrade?: {
    plan_name: string;
    plan_slug: string;
    effective_date: string | null;
  };
  billing_interval?: string;
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

interface PlanChangePreview {
  current_plan: string;
  new_plan: string;
  is_upgrade: boolean;
  proration_amount_cents: number;
  proration_formatted: string;
  effective_date: string;
  message: string;
  current_price_cents: number;
  new_price_cents: number;
  billing_interval: string;
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

  // Plan change dialog state
  const [changePlanDialog, setChangePlanDialog] = useState<{
    open: boolean;
    targetSlug: string;
    preview: PlanChangePreview | null;
    loading: boolean;
    confirming: boolean;
    result: { success: boolean; message: string } | null;
  }>({ open: false, targetSlug: "", preview: null, loading: false, confirming: false, result: null });

  // Cancel dialog state
  const [cancelDialog, setCancelDialog] = useState<{
    open: boolean;
    loading: boolean;
    result: { success: boolean; message: string } | null;
  }>({ open: false, loading: false, result: null });

  async function loadData() {
    try {
      const [pRes, permRes, addonRes, subRes] = await Promise.all([
        apiFetch("/admin/billing/plans"),
        apiFetch("/admin/permissions"),
        apiFetch("/admin/plans/public/addons"),
        apiFetch("/admin/billing/subscription"),
      ]);

      if (pRes.ok) setPlans(await pRes.json());
      if (addonRes.ok) setAddons(await addonRes.json());

      if (subRes.ok) {
        const subData = await subRes.json();
        setSubscription(subData);
      }

      if (permRes.ok) {
        const data = await permRes.json();
        if (!subscription) setSubscription(data.subscription);
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
              await loadData();
              return;
            }
          }
        } catch (e) {
          console.error("verify-session failed", e);
        }
        loadData();
      })();
    } else {
      loadData();
    }
  }, []);

  /* ── Plan Change Handlers ── */

  const handleSelectPlan = async (slug: string) => {
    const targetPlan = plans.find(p => p.slug === slug);
    if (!targetPlan) return;

    // If no active subscription, go to checkout (new subscription)
    if (!subscription?.has_subscription || !subscription?.status || subscription.status === "canceled") {
      handleNewCheckout(slug);
      return;
    }

    // Enterprise plan → contact sales
    if (slug === "enterprise" || (!targetPlan.stripe_price_id && targetPlan.price_monthly_cents === 0 && slug !== "trial")) {
      window.open("mailto:sales@ariia.ai?subject=Enterprise Plan Anfrage", "_blank");
      return;
    }

    // Existing subscription → preview plan change
    setChangePlanDialog({ open: true, targetSlug: slug, preview: null, loading: true, confirming: false, result: null });

    try {
      const res = await apiFetch("/admin/billing/preview-plan-change", {
        method: "POST",
        body: JSON.stringify({
          plan_slug: slug,
          billing_interval: billingInterval === "yearly" ? "year" : "month",
        }),
      });
      if (res.ok) {
        const preview = await res.json();
        setChangePlanDialog(prev => ({ ...prev, preview, loading: false }));
      } else {
        const err = await res.json().catch(() => ({ detail: "Fehler beim Laden der Vorschau" }));
        setChangePlanDialog(prev => ({
          ...prev, loading: false,
          result: { success: false, message: err.detail || "Fehler beim Laden der Vorschau" },
        }));
      }
    } catch {
      setChangePlanDialog(prev => ({
        ...prev, loading: false,
        result: { success: false, message: "Netzwerkfehler" },
      }));
    }
  };

  const handleConfirmPlanChange = async () => {
    setChangePlanDialog(prev => ({ ...prev, confirming: true }));
    try {
      const res = await apiFetch("/admin/billing/change-plan", {
        method: "POST",
        body: JSON.stringify({
          plan_slug: changePlanDialog.targetSlug,
          billing_interval: billingInterval === "yearly" ? "year" : "month",
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setChangePlanDialog(prev => ({
          ...prev, confirming: false,
          result: { success: true, message: data.message },
        }));
        // Reload data after 2 seconds
        setTimeout(() => {
          setChangePlanDialog({ open: false, targetSlug: "", preview: null, loading: false, confirming: false, result: null });
          loadData();
        }, 2500);
      } else {
        setChangePlanDialog(prev => ({
          ...prev, confirming: false,
          result: { success: false, message: data.detail || data.message || "Fehler beim Plan-Wechsel" },
        }));
      }
    } catch {
      setChangePlanDialog(prev => ({
        ...prev, confirming: false,
        result: { success: false, message: "Netzwerkfehler" },
      }));
    }
  };

  const handleNewCheckout = async (slug: string) => {
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

  /* ── Cancel / Reactivate ── */

  const handleCancelSubscription = async () => {
    setCancelDialog(prev => ({ ...prev, loading: true }));
    try {
      const res = await apiFetch("/admin/billing/cancel-subscription", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.success) {
        setCancelDialog(prev => ({
          ...prev, loading: false,
          result: { success: true, message: data.message },
        }));
        setTimeout(() => {
          setCancelDialog({ open: false, loading: false, result: null });
          loadData();
        }, 3000);
      } else {
        setCancelDialog(prev => ({
          ...prev, loading: false,
          result: { success: false, message: data.detail || "Fehler bei der Kündigung" },
        }));
      }
    } catch {
      setCancelDialog(prev => ({
        ...prev, loading: false,
        result: { success: false, message: "Netzwerkfehler" },
      }));
    }
  };

  const handleReactivate = async () => {
    try {
      const res = await apiFetch("/admin/billing/reactivate-subscription", { method: "POST" });
      if (res.ok) {
        loadData();
      }
    } catch (e) {
      console.error("reactivate failed", e);
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
  const isCanceled = subscription?.cancel_at_period_end;
  const hasPendingDowngrade = subscription?.pending_downgrade;

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
                <Badge variant="success" className={`${
                  isCanceled
                    ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
                    : "bg-green-500/20 text-green-400 border-green-500/30"
                }`}>
                  {isCanceled ? "GEKÜNDIGT" : subscription?.status?.toUpperCase() || "AKTIV"}
                </Badge>
                {currentPlan?.slug && currentPlan.slug !== "starter" && (
                  <Badge className="bg-indigo-500 text-white border-none flex items-center gap-1">
                    <Zap size={10} fill="currentColor" /> {currentPlan.name}
                  </Badge>
                )}
              </div>
              <h2 className="text-3xl font-black mb-1">{currentPlan?.name || "Starter Plan"}</h2>

              {/* Cancellation notice */}
              {isCanceled && subscription?.cancellation_effective_date && (
                <div className="mt-2 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                  <p className="text-amber-300 text-sm flex items-center gap-2">
                    <Calendar size={14} />
                    Ihr Abonnement endet am <strong>{subscription.cancellation_effective_date}</strong>.
                    Danach wird es nicht erneuert.
                  </p>
                </div>
              )}

              {/* Pending downgrade notice */}
              {hasPendingDowngrade && (
                <div className="mt-2 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                  <p className="text-blue-300 text-sm flex items-center gap-2">
                    <ArrowDownRight size={14} />
                    Downgrade auf <strong>{hasPendingDowngrade.plan_name}</strong> geplant
                    {hasPendingDowngrade.effective_date && ` am ${hasPendingDowngrade.effective_date}`}.
                  </p>
                </div>
              )}

              {!isCanceled && !hasPendingDowngrade && (
                <p className="text-slate-400 text-sm">
                  {subscription?.current_period_end
                    ? `Nächste Abrechnung am ${new Date(subscription.current_period_end).toLocaleDateString("de-DE")}`
                    : "Kein aktives Abonnement"}
                </p>
              )}

              <div className="mt-8 flex gap-4 flex-wrap">
                <button
                  onClick={handlePortal}
                  className="px-4 py-2 bg-white text-slate-900 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-slate-100 transition-colors"
                >
                  Stripe Portal <ExternalLink size={14} />
                </button>

                {isCanceled ? (
                  <button
                    onClick={handleReactivate}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-green-700 transition-colors"
                  >
                    <RotateCcw size={14} /> Abo reaktivieren
                  </button>
                ) : subscription?.has_subscription && subscription?.status === "active" && (
                  <button
                    onClick={() => setCancelDialog({ open: true, loading: false, result: null })}
                    className="px-4 py-2 bg-transparent border border-red-500/30 text-red-400 rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-red-500/10 transition-colors"
                  >
                    <XCircle size={14} /> Abo kündigen
                  </button>
                )}
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
            <div className="flex bg-slate-100 rounded-lg p-1">
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
              const currentPlanOrder = plans.find(pl => pl.slug === currentPlan?.slug)?.display_order ?? 0;
              const isDowngrade = (p.display_order ?? 0) < currentPlanOrder;
              const isUpgrade = (p.display_order ?? 0) > currentPlanOrder;
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
                  onClick={() => !isCurrent && handleSelectPlan(p.slug)}
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
                    <div className={`mt-3 text-xs font-bold flex items-center gap-1 ${
                      isDowngrade ? "text-amber-600" : "text-indigo-600"
                    }`}>
                      {checkoutLoading === p.slug ? (
                        "Wird geladen..."
                      ) : isDowngrade ? (
                        <><ArrowDownRight size={12} /> Downgrade</>
                      ) : (
                        <><ArrowUpRight size={12} /> {isUpgrade ? "Upgrade" : "Jetzt auswählen"}</>
                      )}
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
                <strong>Plan-Wechsel:</strong> Upgrades werden sofort wirksam mit anteiliger Berechnung.
                Downgrades werden zum Ende des aktuellen Abrechnungszeitraums wirksam.
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Plan Change Confirmation Dialog ── */}
      {changePlanDialog.open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => !changePlanDialog.confirming && setChangePlanDialog(prev => ({ ...prev, open: false }))}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6" onClick={e => e.stopPropagation()}>
            {changePlanDialog.loading ? (
              <div className="flex flex-col items-center gap-4 py-8">
                <Loader2 className="animate-spin text-indigo-600" size={32} />
                <p className="text-sm text-slate-500">Berechne Kosten...</p>
              </div>
            ) : changePlanDialog.result ? (
              <div className="flex flex-col items-center gap-4 py-6">
                {changePlanDialog.result.success ? (
                  <CheckCircle2 className="text-green-500" size={48} />
                ) : (
                  <AlertTriangle className="text-red-500" size={48} />
                )}
                <p className={`text-sm text-center ${changePlanDialog.result.success ? "text-green-700" : "text-red-700"}`}>
                  {changePlanDialog.result.message}
                </p>
                {!changePlanDialog.result.success && (
                  <button
                    onClick={() => setChangePlanDialog(prev => ({ ...prev, open: false }))}
                    className="mt-2 px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
                  >
                    Schließen
                  </button>
                )}
              </div>
            ) : changePlanDialog.preview ? (
              <>
                <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
                  {changePlanDialog.preview.is_upgrade ? (
                    <><ArrowUpRight className="text-green-600" size={20} /> Plan Upgrade</>
                  ) : (
                    <><ArrowDownRight className="text-amber-600" size={20} /> Plan Downgrade</>
                  )}
                </h3>

                <div className="space-y-4">
                  {/* Plan comparison */}
                  <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                    <div className="flex-1 text-center">
                      <p className="text-xs text-slate-400">Aktuell</p>
                      <p className="font-bold text-slate-900">{changePlanDialog.preview.current_plan}</p>
                      <p className="text-xs text-slate-500">{(changePlanDialog.preview.current_price_cents / 100).toFixed(0)}€/Mo</p>
                    </div>
                    <div className="text-slate-300">→</div>
                    <div className="flex-1 text-center">
                      <p className="text-xs text-slate-400">Neu</p>
                      <p className="font-bold text-indigo-600">{changePlanDialog.preview.new_plan}</p>
                      <p className="text-xs text-slate-500">{(changePlanDialog.preview.new_price_cents / 100).toFixed(0)}€/Mo</p>
                    </div>
                  </div>

                  {/* Proration info */}
                  {changePlanDialog.preview.is_upgrade && changePlanDialog.preview.proration_amount_cents > 0 && (
                    <div className="p-3 bg-green-50 border border-green-100 rounded-lg">
                      <p className="text-sm text-green-800 flex items-center gap-2">
                        <CreditCard size={14} />
                        Anteilige Berechnung: <strong>{changePlanDialog.preview.proration_formatted}</strong>
                      </p>
                    </div>
                  )}

                  {/* Effective date */}
                  <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
                    <p className="text-sm text-blue-800 flex items-center gap-2">
                      <Calendar size={14} />
                      Wirksam: <strong>{changePlanDialog.preview.effective_date}</strong>
                    </p>
                  </div>

                  {/* Message */}
                  <p className="text-xs text-slate-500 leading-relaxed">
                    {changePlanDialog.preview.message}
                  </p>
                </div>

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => setChangePlanDialog(prev => ({ ...prev, open: false }))}
                    className="flex-1 px-4 py-2.5 text-sm font-bold text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Abbrechen
                  </button>
                  <button
                    onClick={handleConfirmPlanChange}
                    disabled={changePlanDialog.confirming}
                    className={`flex-1 px-4 py-2.5 text-sm font-bold text-white rounded-lg transition-colors ${
                      changePlanDialog.preview.is_upgrade
                        ? "bg-green-600 hover:bg-green-700"
                        : "bg-amber-600 hover:bg-amber-700"
                    } disabled:opacity-50`}
                  >
                    {changePlanDialog.confirming ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="animate-spin" size={14} /> Wird verarbeitet...
                      </span>
                    ) : changePlanDialog.preview.is_upgrade ? (
                      "Upgrade bestätigen"
                    ) : (
                      "Downgrade bestätigen"
                    )}
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* ── Cancel Subscription Dialog ── */}
      {cancelDialog.open && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => !cancelDialog.loading && setCancelDialog(prev => ({ ...prev, open: false }))}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6" onClick={e => e.stopPropagation()}>
            {cancelDialog.result ? (
              <div className="flex flex-col items-center gap-4 py-6">
                {cancelDialog.result.success ? (
                  <CheckCircle2 className="text-green-500" size={48} />
                ) : (
                  <AlertTriangle className="text-red-500" size={48} />
                )}
                <p className={`text-sm text-center ${cancelDialog.result.success ? "text-slate-700" : "text-red-700"}`}>
                  {cancelDialog.result.message}
                </p>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                    <XCircle className="text-red-600" size={20} />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">Abonnement kündigen</h3>
                    <p className="text-xs text-slate-500">Diese Aktion kann rückgängig gemacht werden</p>
                  </div>
                </div>

                <div className="space-y-3 mb-6">
                  <p className="text-sm text-slate-600 leading-relaxed">
                    Ihr Abonnement wird zum <strong>Ende des aktuellen Abrechnungszeitraums</strong> gekündigt.
                    Bis dahin behalten Sie vollen Zugriff auf alle Funktionen.
                  </p>
                  {subscription?.current_period_end && (
                    <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg">
                      <p className="text-sm text-amber-800 flex items-center gap-2">
                        <Calendar size={14} />
                        Aktiv bis: <strong>{new Date(subscription.current_period_end).toLocaleDateString("de-DE")}</strong>
                      </p>
                    </div>
                  )}
                  <p className="text-xs text-slate-400">
                    Sie können die Kündigung jederzeit vor dem Ablaufdatum rückgängig machen.
                  </p>
                </div>

                <div className="flex gap-3">
                  <button
                    onClick={() => setCancelDialog(prev => ({ ...prev, open: false }))}
                    className="flex-1 px-4 py-2.5 text-sm font-bold text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Behalten
                  </button>
                  <button
                    onClick={handleCancelSubscription}
                    disabled={cancelDialog.loading}
                    className="flex-1 px-4 py-2.5 text-sm font-bold text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                  >
                    {cancelDialog.loading ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="animate-spin" size={14} /> Wird verarbeitet...
                      </span>
                    ) : (
                      "Abo kündigen"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
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
