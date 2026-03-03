"use client";

import { useUsageMetrics, getUsageBarColor, getUsageColor } from "@/lib/billing-hooks";
import { Card } from "@/components/ui/Card";
import {
  MessageSquare, Users, Cpu, Hash, Link2, Zap,
  AlertTriangle, TrendingUp, Activity, Loader2,
} from "lucide-react";

/* ── Icon Mapping ──────────────────────────────────────────────────────── */

const METRIC_ICONS: Record<string, React.ReactNode> = {
  messages: <MessageSquare size={16} className="text-indigo-400" />,
  members: <Users size={16} className="text-blue-400" />,
  tokens: <Cpu size={16} className="text-purple-400" />,
  channels: <Hash size={16} className="text-green-400" />,
  connectors: <Link2 size={16} className="text-amber-400" />,
  api_calls: <Zap size={16} className="text-yellow-400" />,
};

const METRIC_LABELS: Record<string, string> = {
  messages: "Konversationen",
  members: "Kontakte",
  tokens: "AI-Tokens",
  channels: "Kanäle",
  connectors: "Connectors",
  api_calls: "API-Aufrufe",
};

/* ── Component ─────────────────────────────────────────────────────────── */

interface UsageMetricsPanelProps {
  /** Compact mode for sidebar display */
  compact?: boolean;
}

export function UsageMetricsPanel({ compact = false }: UsageMetricsPanelProps) {
  const { data: metrics, isLoading } = useUsageMetrics();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="animate-spin text-indigo-600" size={24} />
      </div>
    );
  }

  if (!metrics || metrics.length === 0) {
    return null; // Don't render if no V2 metrics available
  }

  if (compact) {
    return (
      <div className="flex flex-col gap-2">
        {metrics.map((m) => (
          <CompactMetricRow key={m.metric_key} metric={m} />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {metrics.map((m) => (
        <MetricCard key={m.metric_key} metric={m} />
      ))}
    </div>
  );
}

/* ── Sub-Components ────────────────────────────────────────────────────── */

function MetricCard({ metric }: { metric: { metric_key: string; current_value: number; soft_limit: number | null; hard_limit: number | null; percentage: number; status: string; unit_label: string } }) {
  const icon = METRIC_ICONS[metric.metric_key] || <Activity size={16} className="text-slate-400" />;
  const label = METRIC_LABELS[metric.metric_key] || metric.metric_key;
  const pct = Math.min(100, metric.percentage);
  const isWarning = metric.status === "warning" || metric.status === "critical";
  const isExceeded = metric.status === "exceeded";

  return (
    <Card className="p-5 bg-white border-slate-200 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            {label}
          </span>
        </div>
        {isExceeded && (
          <span className="flex items-center gap-1 text-[10px] font-bold text-red-500 bg-red-50 px-2 py-0.5 rounded-full">
            <AlertTriangle size={10} /> Limit überschritten
          </span>
        )}
        {isWarning && !isExceeded && (
          <span className="flex items-center gap-1 text-[10px] font-bold text-amber-500 bg-amber-50 px-2 py-0.5 rounded-full">
            <TrendingUp size={10} /> Fast erreicht
          </span>
        )}
      </div>

      <div className="flex items-baseline gap-1 mb-3">
        <span className={`text-2xl font-black ${getUsageColor(pct)}`}>
          {metric.current_value.toLocaleString("de-DE")}
        </span>
        <span className="text-xs text-slate-400">
          / {metric.hard_limit ? metric.hard_limit.toLocaleString("de-DE") : "∞"} {metric.unit_label}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full transition-all duration-1000 rounded-full ${getUsageBarColor(pct)}`}
          style={{ width: `${metric.hard_limit ? pct : 5}%` }}
        />
      </div>

      <div className="flex justify-between items-center">
        <span className="text-[10px] text-slate-400">
          {metric.hard_limit ? `${Math.round(pct)}% verbraucht` : "Flatrate aktiv"}
        </span>
        {metric.soft_limit && metric.current_value >= metric.soft_limit && (
          <span className="text-[10px] text-amber-500 font-semibold">
            Soft-Limit erreicht ({metric.soft_limit.toLocaleString("de-DE")})
          </span>
        )}
      </div>
    </Card>
  );
}

function CompactMetricRow({ metric }: { metric: { metric_key: string; current_value: number; hard_limit: number | null; percentage: number; status: string; unit_label: string } }) {
  const label = METRIC_LABELS[metric.metric_key] || metric.metric_key;
  const pct = Math.min(100, metric.percentage);

  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] font-semibold text-slate-500 w-20 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${getUsageBarColor(pct)}`}
          style={{ width: `${metric.hard_limit ? pct : 5}%` }}
        />
      </div>
      <span className={`text-[10px] font-bold ${getUsageColor(pct)}`}>
        {Math.round(pct)}%
      </span>
    </div>
  );
}

export default UsageMetricsPanel;
