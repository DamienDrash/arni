"use client";

import {
  useRevenueMetrics,
  useSubscribers,
  useFeatureDefinitions,
  formatEur,
  getStatusBadge,
} from "@/lib/billing-hooks";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  DollarSign, TrendingUp, Users, CreditCard, Loader2,
  BarChart3, Clock, CheckCircle2, AlertTriangle, ArrowUpRight,
  Package, Activity, Layers3,
} from "lucide-react";

/* ── Revenue Overview Cards ────────────────────────────────────────────── */

export function RevenueOverview() {
  const { data: revenue, isLoading, error } = useRevenueMetrics();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="p-5 animate-pulse">
            <div className="h-4 bg-slate-200 rounded w-20 mb-3" />
            <div className="h-8 bg-slate-200 rounded w-28" />
          </Card>
        ))}
      </div>
    );
  }

  if (error || !revenue) {
    return (
      <Card className="p-6 text-center">
        <AlertTriangle size={24} className="text-amber-500 mx-auto mb-2" />
        <p className="text-sm text-slate-500">Revenue-Daten konnten nicht geladen werden.</p>
        <p className="text-xs text-slate-400 mt-1">Stripe-Verbindung prüfen.</p>
      </Card>
    );
  }

  const cards = [
    {
      label: "MRR (30 Tage)",
      value: formatEur(revenue.mrr_estimate_cents),
      icon: <TrendingUp size={18} className="text-green-500" />,
      bgColor: "bg-green-50",
      change: null,
    },
    {
      label: "Verfügbares Guthaben",
      value: formatEur(revenue.balance_available_cents),
      icon: <DollarSign size={18} className="text-indigo-500" />,
      bgColor: "bg-indigo-50",
      change: null,
    },
    {
      label: "Ausstehend",
      value: formatEur(revenue.balance_pending_cents),
      icon: <Clock size={18} className="text-amber-500" />,
      bgColor: "bg-amber-50",
      change: null,
    },
    {
      label: "Aktive Abonnements",
      value: String(revenue.active_subscriptions),
      icon: <Users size={18} className="text-blue-500" />,
      bgColor: "bg-blue-50",
      change: null,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, i) => (
        <Card key={i} className="p-5 bg-white border-slate-200 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              {card.label}
            </span>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${card.bgColor}`}>
              {card.icon}
            </div>
          </div>
          <div className="text-2xl font-black text-slate-900">{card.value}</div>
        </Card>
      ))}
    </div>
  );
}

/* ── Subscriber Table ──────────────────────────────────────────────────── */

export function SubscriberTable() {
  const { data: subscribers, isLoading } = useSubscribers();

  if (isLoading) {
    return (
      <Card className="p-8 text-center">
        <Loader2 className="animate-spin text-indigo-600 mx-auto" size={24} />
        <p className="text-xs text-slate-400 mt-2">Lade Abonnenten...</p>
      </Card>
    );
  }

  if (!subscribers || subscribers.length === 0) {
    return (
      <Card className="p-8 text-center">
        <Users size={32} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-500">Noch keine aktiven Abonnenten.</p>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900">Aktive Abonnenten</h3>
          <Badge variant="default" size="xs">{subscribers.length}</Badge>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="text-left p-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Tenant</th>
              <th className="text-left p-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Plan</th>
              <th className="text-left p-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Status</th>
              <th className="text-left p-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Intervall</th>
              <th className="text-left p-3 text-xs font-bold text-slate-400 uppercase tracking-wider">Nächste Abrechnung</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {subscribers.map((sub, i) => {
              const badge = getStatusBadge(sub.status);
              return (
                <tr key={i} className="hover:bg-slate-50/50 transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-slate-900">{sub.tenant_name}</div>
                    <div className="text-[10px] text-slate-400">ID: {sub.tenant_id}</div>
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-1.5">
                      <Package size={12} className="text-indigo-500" />
                      <span className="font-medium text-slate-700">{sub.plan_name}</span>
                    </div>
                  </td>
                  <td className="p-3">
                    <Badge variant={badge.variant} size="xs" className={badge.color}>
                      {badge.label}
                    </Badge>
                  </td>
                  <td className="p-3 text-slate-600">
                    {sub.billing_interval === "year" ? "Jährlich" : "Monatlich"}
                  </td>
                  <td className="p-3 text-slate-500 text-xs">
                    {sub.current_period_end
                      ? new Date(sub.current_period_end).toLocaleDateString("de-DE")
                      : "—"}
                    {sub.cancel_at_period_end && (
                      <span className="ml-2 text-[10px] text-red-400 font-semibold">Kündigung geplant</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ── Feature Definitions Table ─────────────────────────────────────────── */

export function FeatureDefinitionsTable() {
  const { data: features, isLoading } = useFeatureDefinitions();

  if (isLoading) {
    return (
      <Card className="p-8 text-center">
        <Loader2 className="animate-spin text-indigo-600 mx-auto" size={24} />
      </Card>
    );
  }

  if (!features || features.length === 0) {
    return (
      <Card className="p-8 text-center">
        <Layers3 size={32} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-500">Keine V2-Features definiert.</p>
        <p className="text-xs text-slate-400 mt-1">Features werden beim nächsten Server-Start automatisch geseedet.</p>
      </Card>
    );
  }

  // Group by category
  const categories = features.reduce((acc, f) => {
    const cat = f.category || "Sonstige";
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(f);
    return acc;
  }, {} as Record<string, typeof features>);

  return (
    <Card className="overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center gap-2">
        <Activity size={16} className="text-indigo-600" />
        <h3 className="text-sm font-bold text-slate-900">V2 Feature-Definitionen</h3>
        <Badge variant="default" size="xs">{features.length}</Badge>
      </div>
      <div className="divide-y divide-slate-100">
        {Object.entries(categories).map(([category, feats]) => (
          <div key={category}>
            <div className="px-4 py-2 bg-slate-50">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                {category}
              </span>
            </div>
            <div className="divide-y divide-slate-50">
              {feats.map((f) => (
                <div key={f.id} className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50/50 transition-colors">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900">{f.name}</span>
                      <code className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                        {f.key}
                      </code>
                    </div>
                    {f.description && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{f.description}</p>
                    )}
                  </div>
                  <Badge variant="default" size="xs">
                    {f.feature_type}
                  </Badge>
                  {f.unit_label && (
                    <span className="text-[10px] text-slate-400">{f.unit_label}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ── Combined Dashboard ────────────────────────────────────────────────── */

export function AdminBillingDashboard() {
  return (
    <div className="flex flex-col gap-6">
      <RevenueOverview />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SubscriberTable />
        <FeatureDefinitionsTable />
      </div>
    </div>
  );
}

export default AdminBillingDashboard;
