"use client";

import { useBillingEvents } from "@/lib/billing-hooks";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import {
  CreditCard, ArrowUpRight, ArrowDownRight, XCircle, RotateCcw,
  Zap, Package, Clock, Loader2, ScrollText, AlertTriangle,
  CheckCircle2, DollarSign, Receipt,
} from "lucide-react";

/* ── Event Type Config ─────────────────────────────────────────────────── */

const EVENT_CONFIG: Record<string, {
  label: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
}> = {
  subscription_created: {
    label: "Abo erstellt",
    icon: <Package size={14} />,
    color: "text-green-500",
    bgColor: "bg-green-50",
  },
  subscription_upgraded: {
    label: "Upgrade",
    icon: <ArrowUpRight size={14} />,
    color: "text-indigo-500",
    bgColor: "bg-indigo-50",
  },
  subscription_downgraded: {
    label: "Downgrade",
    icon: <ArrowDownRight size={14} />,
    color: "text-amber-500",
    bgColor: "bg-amber-50",
  },
  subscription_canceled: {
    label: "Gekündigt",
    icon: <XCircle size={14} />,
    color: "text-red-500",
    bgColor: "bg-red-50",
  },
  subscription_reactivated: {
    label: "Reaktiviert",
    icon: <RotateCcw size={14} />,
    color: "text-green-500",
    bgColor: "bg-green-50",
  },
  subscription_renewed: {
    label: "Verlängert",
    icon: <CheckCircle2 size={14} />,
    color: "text-green-500",
    bgColor: "bg-green-50",
  },
  payment_succeeded: {
    label: "Zahlung erfolgreich",
    icon: <DollarSign size={14} />,
    color: "text-green-500",
    bgColor: "bg-green-50",
  },
  payment_failed: {
    label: "Zahlung fehlgeschlagen",
    icon: <AlertTriangle size={14} />,
    color: "text-red-500",
    bgColor: "bg-red-50",
  },
  invoice_created: {
    label: "Rechnung erstellt",
    icon: <Receipt size={14} />,
    color: "text-blue-500",
    bgColor: "bg-blue-50",
  },
  plan_created: {
    label: "Plan erstellt",
    icon: <Package size={14} />,
    color: "text-indigo-500",
    bgColor: "bg-indigo-50",
  },
  plan_changed: {
    label: "Plan geändert",
    icon: <Zap size={14} />,
    color: "text-amber-500",
    bgColor: "bg-amber-50",
  },
  usage_limit_warning: {
    label: "Limit-Warnung",
    icon: <AlertTriangle size={14} />,
    color: "text-amber-500",
    bgColor: "bg-amber-50",
  },
  usage_limit_exceeded: {
    label: "Limit überschritten",
    icon: <AlertTriangle size={14} />,
    color: "text-red-500",
    bgColor: "bg-red-50",
  },
};

const DEFAULT_EVENT_CONFIG = {
  label: "Ereignis",
  icon: <Clock size={14} />,
  color: "text-slate-500",
  bgColor: "bg-slate-50",
};

/* ── Component ─────────────────────────────────────────────────────────── */

interface BillingEventLogProps {
  limit?: number;
  compact?: boolean;
}

export function BillingEventLog({ limit = 20, compact = false }: BillingEventLogProps) {
  const { data: events, isLoading } = useBillingEvents(limit);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="animate-spin text-indigo-600" size={24} />
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <Card className="p-8 text-center">
        <ScrollText size={32} className="text-slate-300 mx-auto mb-3" />
        <p className="text-sm text-slate-400">Noch keine Billing-Ereignisse vorhanden.</p>
      </Card>
    );
  }

  if (compact) {
    return (
      <div className="flex flex-col divide-y divide-slate-100">
        {events.slice(0, 5).map((event) => {
          const config = EVENT_CONFIG[event.event_type] || DEFAULT_EVENT_CONFIG;
          return (
            <div key={event.id} className="flex items-center gap-3 py-2.5">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center ${config.bgColor} ${config.color}`}>
                {config.icon}
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-xs font-semibold text-slate-700 truncate block">
                  {config.label}
                </span>
              </div>
              <span className="text-[10px] text-slate-400 whitespace-nowrap">
                {formatRelativeTime(event.created_at)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <Card className="overflow-hidden">
      <div className="p-4 border-b border-slate-100 flex items-center gap-2">
        <ScrollText size={16} className="text-indigo-600" />
        <h3 className="text-sm font-bold text-slate-900">Billing-Verlauf</h3>
        <Badge variant="default" size="xs">{events.length}</Badge>
      </div>
      <div className="divide-y divide-slate-50">
        {events.map((event) => {
          const config = EVENT_CONFIG[event.event_type] || DEFAULT_EVENT_CONFIG;
          return (
            <div key={event.id} className="flex items-start gap-3 p-4 hover:bg-slate-50/50 transition-colors">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${config.bgColor} ${config.color}`}>
                {config.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-sm font-semibold text-slate-900">{config.label}</span>
                  <Badge variant="default" size="xs" className="text-[9px]">
                    {event.event_type}
                  </Badge>
                </div>
                {event.payload && Object.keys(event.payload).length > 0 && (
                  <p className="text-xs text-slate-500 truncate">
                    {formatPayload(event.payload)}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-slate-400">
                    {formatDateTime(event.created_at)}
                  </span>
                  {event.actor_type && (
                    <span className="text-[10px] text-slate-300">
                      von {event.actor_type}{event.actor_id ? ` #${event.actor_id}` : ""}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "gerade eben";
    if (minutes < 60) return `vor ${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `vor ${hours}h`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `vor ${days}T`;
    return formatDateTime(iso);
  } catch {
    return iso;
  }
}

function formatPayload(payload: Record<string, any>): string {
  const parts: string[] = [];
  if (payload.plan_name) parts.push(`Plan: ${payload.plan_name}`);
  if (payload.plan_slug) parts.push(`Slug: ${payload.plan_slug}`);
  if (payload.amount_cents) parts.push(`Betrag: ${(payload.amount_cents / 100).toFixed(2)}€`);
  if (payload.from_plan) parts.push(`Von: ${payload.from_plan}`);
  if (payload.to_plan) parts.push(`Zu: ${payload.to_plan}`);
  if (payload.metric_key) parts.push(`Metrik: ${payload.metric_key}`);
  if (parts.length === 0) {
    return Object.entries(payload)
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${String(v).slice(0, 30)}`)
      .join(", ");
  }
  return parts.join(" · ");
}

export default BillingEventLog;
