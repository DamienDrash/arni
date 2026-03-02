"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  BarChart3, RefreshCcw, TrendingUp, Clock, Cpu, Bot,
  DollarSign, Zap, Activity, Calendar,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";

type UsageSummary = {
  period: string; total_requests: number; successful_requests: number;
  failed_requests: number; total_tokens: number; prompt_tokens: number;
  completion_tokens: number; total_cost_cents: number; avg_latency_ms: number;
};
type UsageByModel = {
  model_id: string; provider_slug: string; request_count: number;
  total_tokens: number; total_cost_cents: number; avg_latency_ms: number;
};
type UsageByAgent = {
  agent_name: string; request_count: number; total_tokens: number;
  total_cost_cents: number; avg_latency_ms: number;
};
type DailyUsage = { date: string; requests: number; tokens: number; cost_cents: number; };

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("de-DE");
}
function formatCents(cents: number): string { return `€${(cents / 100).toFixed(2)}`; }

export function AIObservabilityDashboard() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [byModel, setByModel] = useState<UsageByModel[]>([]);
  const [byAgent, setByAgent] = useState<UsageByAgent[]>([]);
  const [daily, setDaily] = useState<DailyUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sRes, mRes, aRes, dRes] = await Promise.all([
        apiFetch("/admin/ai/observability/usage/summary"),
        apiFetch(`/admin/ai/observability/usage/by-model?days=${days}`),
        apiFetch(`/admin/ai/observability/usage/by-agent?days=${days}`),
        apiFetch(`/admin/ai/observability/usage/daily?days=${days}`),
      ]);
      if (sRes.ok) setSummary(await sRes.json());
      if (mRes.ok) setByModel(await mRes.json());
      if (aRes.ok) setByAgent(await aRes.json());
      if (dRes.ok) setDaily(await dRes.json());
    } catch (e) { console.error("Load error", e); }
    setLoading(false);
  }, [days]);

  useEffect(() => { load(); }, [load]);

  const maxDailyReq = Math.max(...daily.map((d) => d.requests), 1);

  const statCardStyle: React.CSSProperties = {
    padding: 16, borderRadius: 12, border: `1px solid ${T.border}`,
    background: T.surfaceAlt, display: "flex", flexDirection: "column", gap: 4,
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <SectionHeader title="AI Observability" subtitle="Echtzeit-Überwachung von Usage, Kosten und Performance" />
        <div style={{ display: "flex", gap: 8 }}>
          <select value={days} onChange={(e) => setDays(parseInt(e.target.value))} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 12, outline: "none" }}>
            <option value={7}>7 Tage</option>
            <option value={30}>30 Tage</option>
            <option value={90}>90 Tage</option>
          </select>
          <button onClick={load} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <RefreshCcw size={14} />
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: T.textMuted, fontSize: 13 }}>Lade Dashboard...</div>
      ) : (
        <>
          {/* KPI Cards */}
          {summary && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textMuted }}>
                  <Activity size={14} color={T.accent} /> Requests
                </div>
                <span style={{ fontSize: 24, fontWeight: 800, color: T.text }}>{formatNumber(summary.total_requests)}</span>
                <div style={{ fontSize: 10, color: T.textDim }}>
                  <span style={{ color: T.success }}>{formatNumber(summary.successful_requests)} OK</span>
                  {summary.failed_requests > 0 && <span style={{ color: T.danger, marginLeft: 8 }}>{formatNumber(summary.failed_requests)} Fehler</span>}
                </div>
              </div>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textMuted }}>
                  <Zap size={14} color={T.warning} /> Tokens
                </div>
                <span style={{ fontSize: 24, fontWeight: 800, color: T.text }}>{formatNumber(summary.total_tokens)}</span>
                <div style={{ fontSize: 10, color: T.textDim }}>
                  Prompt: {formatNumber(summary.prompt_tokens)} | Completion: {formatNumber(summary.completion_tokens)}
                </div>
              </div>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textMuted }}>
                  <DollarSign size={14} color={T.success} /> Kosten
                </div>
                <span style={{ fontSize: 24, fontWeight: 800, color: T.text }}>{formatCents(summary.total_cost_cents)}</span>
                <div style={{ fontSize: 10, color: T.textDim }}>Aktueller Monat ({summary.period})</div>
              </div>
              <div style={statCardStyle}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: T.textMuted }}>
                  <Clock size={14} color={T.info} /> Avg Latenz
                </div>
                <span style={{ fontSize: 24, fontWeight: 800, color: T.text }}>{summary.avg_latency_ms.toFixed(0)}ms</span>
                <div style={{ fontSize: 10, color: T.textDim }}>Durchschnittliche Antwortzeit</div>
              </div>
            </div>
          )}

          {/* Daily Usage Chart (CSS-based bar chart) */}
          {daily.length > 0 && (
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <Calendar size={16} color={T.accent} /> Tägliche Nutzung
              </div>
              <div style={{ padding: 16, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 120 }}>
                  {daily.map((d, i) => {
                    const pct = (d.requests / maxDailyReq) * 100;
                    return (
                      <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                        <div style={{ width: "100%", maxWidth: 20, height: `${Math.max(pct, 2)}%`, background: `linear-gradient(to top, ${T.accent}, ${T.accentLight})`, borderRadius: "3px 3px 0 0", transition: "height 0.3s ease" }} title={`${d.date}: ${d.requests} Requests, ${formatNumber(d.tokens)} Tokens`} />
                      </div>
                    );
                  })}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 9, color: T.textDim }}>
                  <span>{daily[0]?.date}</span>
                  <span>{daily[daily.length - 1]?.date}</span>
                </div>
              </div>
            </div>
          )}

          {/* Usage by Model */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <Cpu size={16} color={T.accent} /> Nutzung nach Modell
              </div>
              {byModel.length === 0 ? (
                <div style={{ fontSize: 12, color: T.textDim, padding: 16 }}>Keine Daten</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {byModel.map((m, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, fontSize: 12 }}>
                      <div>
                        <span style={{ fontWeight: 700, color: T.text }}>{m.model_id}</span>
                        <span style={{ fontSize: 10, color: T.textDim, marginLeft: 6 }}>{m.provider_slug}</span>
                      </div>
                      <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.textMuted }}>
                        <span>{formatNumber(m.request_count)} Req</span>
                        <span>{formatNumber(m.total_tokens)} Tok</span>
                        <span style={{ color: T.success, fontWeight: 600 }}>{formatCents(m.total_cost_cents)}</span>
                        <span>{m.avg_latency_ms.toFixed(0)}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Usage by Agent */}
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <Bot size={16} color={T.accent} /> Nutzung nach Agent
              </div>
              {byAgent.length === 0 ? (
                <div style={{ fontSize: 12, color: T.textDim, padding: 16 }}>Keine Daten</div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {byAgent.map((a, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, fontSize: 12 }}>
                      <span style={{ fontWeight: 700, color: T.text }}>{a.agent_name}</span>
                      <div style={{ display: "flex", gap: 16, fontSize: 11, color: T.textMuted }}>
                        <span>{formatNumber(a.request_count)} Req</span>
                        <span>{formatNumber(a.total_tokens)} Tok</span>
                        <span style={{ color: T.success, fontWeight: 600 }}>{formatCents(a.total_cost_cents)}</span>
                        <span>{a.avg_latency_ms.toFixed(0)}ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
