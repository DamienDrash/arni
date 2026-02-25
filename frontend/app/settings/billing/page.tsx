"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Zap, ArrowUpRight, ShieldCheck, HelpCircle, History, Package, CreditCard, LayoutGrid, Info, Plus } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface Plan {
  slug: string;
  name: string;
  price_monthly_cents: number;
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number;
  features: string[];
}

interface Subscription {
  has_subscription: boolean;
  status: string;
  plan: Plan;
  current_period_end?: string;
}

interface Usage {
  messages_used: number;
  messages_limit: number | null;
  members_count: number;
  members_limit: number | null;
}

/* ─── Page ──────────────────────────────────────────────────────────── */

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const searchParams = useSearchParams();

  async function loadData() {
    try {
      const [pRes, sRes, uRes] = await Promise.all([
        apiFetch("/admin/billing/plans"),
        apiFetch("/admin/permissions"), // returns subscription info
        apiFetch("/admin/stats") // using existing stats endpoint
      ]);
      
      if (pRes.ok) setPlans(await pRes.json());
      if (sRes.ok) {
        const data = await sRes.json();
        setSub({
          has_subscription: data.subscription.has_subscription,
          status: data.subscription.status,
          plan: data.plan,
          current_period_end: data.subscription.current_period_end
        });
        setUsage({
          messages_used: data.usage.messages_used,
          messages_limit: data.plan.limits.max_monthly_messages,
          members_count: data.usage.members_count,
          members_limit: data.plan.limits.max_members
        });
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  const handleUpgrade = async (slug: string) => {
    setCheckoutLoading(slug);
    try {
      const res = await apiFetch("/admin/billing/checkout-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_slug: slug })
      });
      if (res.ok) {
        const { url } = await res.json();
        window.location.href = url;
      }
    } finally {
      setCheckoutLoading(null);
    }
  };

  if (loading) return <div className="p-12 text-center">Laden...</div>;

  return (
    <div className="flex flex-col gap-6">
      <SettingsSubnav />

      <SectionHeader 
        title="Abonnement & Nutzung" 
        subtitle="Verwalte deinen SaaS-Plan, Add-ons und überwache deinen Verbrauch."
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Current Plan & Usage */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          <Card className="p-6 bg-slate-900 border-slate-800 text-white relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-10"><Package size={120} /></div>
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-4">
                <Badge variant="success" className="bg-green-500/20 text-green-400 border-green-500/30">
                  {sub?.status.toUpperCase() || 'AKTIV'}
                </Badge>
                {sub?.plan.slug === 'business' && <Badge className="bg-indigo-500 text-white border-none flex items-center gap-1"><Zap size={10} fill="currentColor" /> Business</Badge>}
              </div>
              <h2 className="text-3xl font-black mb-1">{sub?.plan.name || 'Starter Plan'}</h2>
              <p className="text-slate-400 text-sm">
                Nächste Abrechnung am {sub?.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : '—'}
              </p>
              
              <div className="mt-8 flex gap-4">
                <button onClick={() => {}} className="px-4 py-2 bg-white text-slate-900 rounded-lg text-sm font-bold flex items-center gap-2">
                  Zahlungsmethode ändern <ArrowUpRight size={14} />
                </button>
                <button className="px-4 py-2 bg-slate-800 text-white rounded-lg text-sm font-bold border border-slate-700">
                  Rechnungen
                </button>
              </div>
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UsageCard 
              label="Konversationen" 
              used={usage?.messages_used || 0} 
              limit={usage?.messages_limit ?? null} 
              unit="Mtg" 
            />
            <UsageCard 
              label="Mitglieder" 
              used={usage?.members_count || 0} 
              limit={usage?.members_limit ?? null} 
              unit="Mitgl." 
            />
          </div>

          <div className="flex flex-col gap-4">
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <LayoutGrid size={20} className="text-indigo-600" /> Verfügbare Add-ons
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <AddonCard title="Vision AI" price="39€" description="Automatisches Erkennen der Studio-Auslastung via Kamera." />
              <AddonCard title="Voice Pipeline" price="79€" description="KI-Telefonate für Terminbuchungen und Rückrufe." />
              <AddonCard title="Churn Prediction" price="49€" description="KI-basierte Vorhersage von Kündigungsrisiken." />
              <AddonCard title="White-Label" price="149€" description="Eigene Domain und Branding ohne ARIIA-Logo." />
            </div>
          </div>
        </div>

        {/* Right: Plan Comparison / Upgrade */}
        <div className="flex flex-col gap-4">
          <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <ArrowUpRight size={20} className="text-indigo-600" /> Plan wechseln
          </h3>
          <div className="flex flex-col gap-3">
            {plans.map(p => (
              <button
                key={p.slug}
                onClick={() => handleUpgrade(p.slug)}
                disabled={sub?.plan.slug === p.slug || !!checkoutLoading}
                className={`p-4 rounded-xl border text-left transition-all ${
                  sub?.plan.slug === p.slug 
                    ? "bg-slate-50 border-slate-200 cursor-default" 
                    : "bg-white border-slate-200 hover:border-indigo-200 hover:shadow-lg hover:shadow-indigo-50"
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="font-bold text-slate-900">{p.name}</span>
                  {sub?.plan.slug === p.slug ? (
                    <Badge variant="success">Aktuell</Badge>
                  ) : (
                    <span className="text-sm font-black text-indigo-600">
                      {p.price_monthly_cents === 0 ? "Individuell" : `${p.price_monthly_cents / 100}€`}
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  {p.features.slice(0, 3).map(f => (
                    <div key={f} className="text-xs text-slate-500 flex items-center gap-1.5">
                      <CheckCircle2 size={10} className="text-green-500" /> {f}
                    </div>
                  ))}
                </div>
                {sub?.plan.slug !== p.slug && (
                  <div className="mt-4 text-xs font-bold text-indigo-600 flex items-center gap-1">
                    {checkoutLoading === p.slug ? "Wird geladen..." : "Jetzt auswählen"} <ArrowUpRight size={12} />
                  </div>
                )}
              </button>
            ))}
          </div>

          <Card className="p-4 bg-indigo-50 border-indigo-100">
            <div className="flex gap-3">
              <Info className="text-indigo-600 shrink-0" size={18} />
              <div className="text-xs text-indigo-900 leading-relaxed">
                <strong>Nutzungsbasierte Abrechnung:</strong> Überschreitungen der Inklusiv-Limits werden automatisch am Monatsende über Stripe abgerechnet (z.B. 0,05€ pro extra Nachricht).
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function UsageCard({ label, used, limit, unit }: { label: string, used: number, limit: number | null, unit: string }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <Card className="p-5 bg-white border-slate-200">
      <div className="flex justify-between items-center mb-4">
        <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{label}</span>
        <span className="text-xs font-bold text-slate-900">{used} / {limit || '∞'} {unit}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-2">
        <div 
          className={`h-full transition-all duration-1000 ${pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : 'bg-indigo-600'}`} 
          style={{ width: `${limit ? pct : 5}%` }} 
        />
      </div>
      <div className="text-[10px] text-slate-400">{limit ? `${Math.round(pct)}% verbraucht` : 'Flatrate aktiv'}</div>
    </Card>
  );
}

function AddonCard({ title, price, description }: { title: string, price: string, description: string }) {
  return (
    <div className="p-4 rounded-xl border border-slate-200 bg-white hover:border-indigo-200 transition-colors flex flex-col justify-between">
      <div>
        <div className="flex justify-between items-center mb-1">
          <span className="font-bold text-slate-900">{title}</span>
          <span className="text-xs font-bold text-indigo-600">+{price}/mtl.</span>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
      </div>
      <button className="mt-4 text-xs font-bold text-slate-400 hover:text-indigo-600 flex items-center gap-1 transition-colors">
        Hinzufügen <Plus size={12} />
      </button>
    </div>
  );
}
