"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Area, AreaChart,
} from "recharts";
import {
  TrendingUp, TrendingDown, DollarSign, Users, Zap, CreditCard,
  ArrowUpRight, ArrowDownRight, RefreshCcw, Download, Coins,
  BarChart3, PieChart as PieChartIcon, Activity,
} from "lucide-react";

import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";

type Overview = {
  mrr_cents: number;
  mrr_formatted: string;
  arr_cents: number;
  arr_formatted: string;
  plan_mrr_cents: number;
  addon_mrr_cents: number;
  token_revenue_cents: number;
  total_subscribers: number;
  paying_subscribers: number;
  free_subscribers: number;
  canceled_total: number;
  total_tenants: number;
  plan_distribution: Record<string, number>;
};

type MonthlyData = {
  year: number;
  month: number;
  label: string;
  mrr_cents: number;
  token_revenue_cents: number;
  messages_inbound: number;
  messages_outbound: number;
  tokens_used: number;
  active_members: number;
  active_subscribers: number;
};

type TenantRevenue = {
  tenant_id: number;
  tenant_name: string;
  tenant_slug: string;
  plan_name: string;
  plan_slug: string | null;
  status: string;
  mrr_cents: number;
  addon_count: number;
  messages_this_month: number;
  tokens_used: number;
  token_limit: number;
  members: number;
};

type TokenAnalytics = {
  current_month_tokens_used: number;
  total_tokens_purchased: number;
  purchase_revenue_cents: number;
  estimated_cost_cents: number;
  margin_cents: number;
  top_consumers: Array<{
    tenant_id: number;
    tenant_name: string;
    plan_name: string;
    tokens_used: number;
    token_limit: number;
    usage_pct: number;
  }>;
};

const COLORS = [T.accent, T.success, T.warning, T.info, T.danger, "#FF85C0", "#69DB7C", "#845EF7"];

function formatCents(cents: number): string {
  return `€${(cents / 100).toLocaleString("de-DE", { minimumFractionDigits: 2 })}`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("de-DE");
}

const CustomTooltipContent = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10,
      padding: "10px 14px", boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    }}>
      <p style={{ fontSize: 11, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>{label}</p>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />
          <span style={{ fontSize: 11, color: T.textMuted }}>{p.name}:</span>
          <span style={{ fontSize: 11, fontWeight: 700, color: T.text }}>{p.value?.toLocaleString("de-DE")}</span>
        </div>
      ))}
    </div>
  );
};

export default function RevenueAnalyticsPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [monthly, setMonthly] = useState<MonthlyData[]>([]);
  const [tenants, setTenants] = useState<TenantRevenue[]>([]);
  const [tokens, setTokens] = useState<TokenAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "tenants" | "tokens">("overview");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [ovRes, moRes, teRes, toRes] = await Promise.all([
        apiFetch("/admin/revenue/overview"),
        apiFetch("/admin/revenue/monthly?months=12"),
        apiFetch("/admin/revenue/tenants"),
        apiFetch("/admin/revenue/tokens"),
      ]);
      if (ovRes.ok) setOverview(await ovRes.json());
      if (moRes.ok) setMonthly(await moRes.json());
      if (teRes.ok) setTenants(await teRes.json());
      if (toRes.ok) setTokens(await toRes.json());
    } catch (e) {
      console.error("Revenue load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 400, color: T.textDim, fontSize: 13 }}>
        <RefreshCcw size={20} style={{ marginRight: 8, animation: "spin 1s linear infinite" }} />
        Lade Revenue Analytics…
      </div>
    );
  }

  const pieData = overview?.plan_distribution
    ? Object.entries(overview.plan_distribution).map(([name, count]) => ({ name, value: count }))
    : [];

  const mrrData = monthly.map(m => ({
    label: m.label,
    mrr: m.mrr_cents / 100,
    tokens: m.token_revenue_cents / 100,
    total: (m.mrr_cents + m.token_revenue_cents) / 100,
  }));

  const tabs = [
    { id: "overview" as const, label: "Übersicht", icon: BarChart3 },
    { id: "tenants" as const, label: "Tenants", icon: Users },
    { id: "tokens" as const, label: "Token Analytics", icon: Zap },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
            Revenue Analytics
          </h1>
          <p style={{ fontSize: 12, color: T.textMuted, margin: "4px 0 0" }}>
            Umsatzentwicklung, Abonnements und Token-Kosten
          </p>
        </div>
        <button
          onClick={() => void load()}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 14px", borderRadius: 10,
            background: T.accentDim, color: T.accentLight,
            border: `1px solid ${T.accent}33`, fontSize: 12, fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <RefreshCcw size={14} /> Aktualisieren
        </button>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "flex", alignItems: "center", gap: 7,
                padding: "8px 14px", borderRadius: 10,
                background: isActive ? T.accentDim : T.surfaceAlt,
                color: isActive ? T.text : T.textMuted,
                border: `1px solid ${isActive ? `${T.accent}66` : T.border}`,
                fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Icon size={14} /> {tab.label}
            </button>
          );
        })}
      </div>

      {activeTab === "overview" && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                label: "MRR", value: formatCents(overview?.mrr_cents || 0),
                sub: `Plan: ${formatCents(overview?.plan_mrr_cents || 0)} · Add-ons: ${formatCents(overview?.addon_mrr_cents || 0)}`,
                icon: DollarSign, color: T.success,
              },
              {
                label: "ARR", value: formatCents(overview?.arr_cents || 0),
                sub: "Hochrechnung auf 12 Monate",
                icon: TrendingUp, color: T.accent,
              },
              {
                label: "Zahlende Kunden", value: String(overview?.paying_subscribers || 0),
                sub: `${overview?.free_subscribers || 0} Free · ${overview?.canceled_total || 0} Gekündigt`,
                icon: Users, color: T.info,
              },
              {
                label: "Token-Umsatz", value: formatCents(overview?.token_revenue_cents || 0),
                sub: "Zusätzliche Token-Käufe",
                icon: Coins, color: T.warning,
              },
            ].map((kpi, i) => {
              const Icon = kpi.icon;
              return (
                <Card key={i} style={{ padding: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: `${kpi.color}15`, display: "flex",
                      alignItems: "center", justifyContent: "center",
                    }}>
                      <Icon size={18} color={kpi.color} />
                    </div>
                    <span style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {kpi.label}
                    </span>
                  </div>
                  <p style={{ fontSize: 26, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
                    {kpi.value}
                  </p>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: "6px 0 0" }}>{kpi.sub}</p>
                </Card>
              );
            })}
          </div>

          {/* Revenue Chart + Plan Distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card style={{ padding: 24, gridColumn: "span 2" }}>
              <SectionHeader title="Umsatzentwicklung" subtitle="Monatliche Einnahmen (letzte 12 Monate)" />
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={mrrData}>
                  <defs>
                    <linearGradient id="gradMrr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={T.accent} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={T.accent} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradToken" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={T.warning} stopOpacity={0.3} />
                      <stop offset="100%" stopColor={T.warning} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
                  <XAxis dataKey="label" stroke={T.textDim} tick={{ fontSize: 10 }} />
                  <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} tickFormatter={(v) => `€${v}`} />
                  <Tooltip content={<CustomTooltipContent />} />
                  <Area type="monotone" dataKey="mrr" name="Plan MRR" stroke={T.accent} fill="url(#gradMrr)" strokeWidth={2} />
                  <Area type="monotone" dataKey="tokens" name="Token-Umsatz" stroke={T.warning} fill="url(#gradToken)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            <Card style={{ padding: 24 }}>
              <SectionHeader title="Plan-Verteilung" subtitle="Aktive Abonnements" />
              {pieData.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%" cy="50%"
                        innerRadius={50} outerRadius={75}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {pieData.map((_, i) => (
                          <Cell key={i} fill={COLORS[i % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip content={<CustomTooltipContent />} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%" }}>
                    {pieData.map((d, i) => (
                      <div key={d.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <div style={{ width: 10, height: 10, borderRadius: 3, background: COLORS[i % COLORS.length] }} />
                          <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{d.name}</span>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 700, color: T.textMuted }}>{d.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: T.textDim, fontSize: 12 }}>
                  Keine Abonnement-Daten vorhanden
                </div>
              )}
            </Card>
          </div>

          {/* Usage Trend */}
          <Card style={{ padding: 24 }}>
            <SectionHeader title="Nutzungstrend" subtitle="Nachrichten und Token-Verbrauch pro Monat" />
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={monthly}>
                <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
                <XAxis dataKey="label" stroke={T.textDim} tick={{ fontSize: 10 }} />
                <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
                <Tooltip content={<CustomTooltipContent />} />
                <Bar dataKey="messages_inbound" name="Eingehend" fill={T.info} radius={[0, 0, 0, 0]} />
                <Bar dataKey="messages_outbound" name="Ausgehend" fill={T.accent} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}

      {activeTab === "tenants" && (
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Tenant-Übersicht" subtitle="Umsatz und Nutzung pro Tenant" />
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Tenant", "Plan", "Status", "MRR", "Add-ons", "Nachrichten", "Token-Nutzung", "Mitglieder"].map(h => (
                    <th key={h} style={{
                      textAlign: "left", padding: "12px 14px", fontSize: 10, fontWeight: 600,
                      color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em",
                      borderBottom: `1px solid ${T.border}`,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tenants.map((t_row) => {
                  const tokenPct = t_row.token_limit > 0 ? Math.min(100, (t_row.tokens_used / t_row.token_limit) * 100) : 0;
                  return (
                    <tr key={t_row.tenant_id} style={{ borderBottom: `1px solid ${T.border}` }}>
                      <td style={{ padding: "14px" }}>
                        <div>
                          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{t_row.tenant_name}</span>
                          <span style={{ fontSize: 10, color: T.textDim, display: "block" }}>{t_row.tenant_slug}</span>
                        </div>
                      </td>
                      <td style={{ padding: "14px" }}>
                        <Badge variant="accent">{t_row.plan_name}</Badge>
                      </td>
                      <td style={{ padding: "14px" }}>
                        <Badge variant={t_row.status === "active" ? "success" : t_row.status === "trialing" ? "info" : "warning"}>
                          {t_row.status}
                        </Badge>
                      </td>
                      <td style={{ padding: "14px", fontSize: 13, fontWeight: 700, color: T.text }}>
                        {formatCents(t_row.mrr_cents)}
                      </td>
                      <td style={{ padding: "14px", fontSize: 13, color: T.text }}>{t_row.addon_count}</td>
                      <td style={{ padding: "14px", fontSize: 13, color: T.text }}>{formatNumber(t_row.messages_this_month)}</td>
                      <td style={{ padding: "14px" }}>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                            <span style={{ color: T.textMuted }}>{formatNumber(t_row.tokens_used)}</span>
                            <span style={{ color: T.textDim }}>{formatNumber(t_row.token_limit)}</span>
                          </div>
                          <div style={{ width: "100%", height: 4, borderRadius: 2, background: T.surfaceAlt, overflow: "hidden" }}>
                            <div style={{
                              width: `${tokenPct}%`, height: "100%", borderRadius: 2,
                              background: tokenPct > 90 ? T.danger : tokenPct > 70 ? T.warning : T.success,
                              transition: "width 0.6s ease",
                            }} />
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: "14px", fontSize: 13, color: T.text }}>{formatNumber(t_row.members)}</td>
                    </tr>
                  );
                })}
                {tenants.length === 0 && (
                  <tr>
                    <td colSpan={8} style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                      Keine Tenant-Daten vorhanden
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {activeTab === "tokens" && tokens && (
        <>
          {/* Token KPIs */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Token-Verbrauch (Monat)", value: formatNumber(tokens.current_month_tokens_used), icon: Zap, color: T.accent },
              { label: "Gekaufte Tokens", value: formatNumber(tokens.total_tokens_purchased), icon: Coins, color: T.warning },
              { label: "Token-Umsatz", value: formatCents(tokens.purchase_revenue_cents), icon: DollarSign, color: T.success },
              { label: "Geschätzte Marge", value: formatCents(tokens.margin_cents), icon: TrendingUp, color: tokens.margin_cents >= 0 ? T.success : T.danger },
            ].map((kpi, i) => {
              const Icon = kpi.icon;
              return (
                <Card key={i} style={{ padding: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: `${kpi.color}15`, display: "flex",
                      alignItems: "center", justifyContent: "center",
                    }}>
                      <Icon size={18} color={kpi.color} />
                    </div>
                    <span style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {kpi.label}
                    </span>
                  </div>
                  <p style={{ fontSize: 26, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
                    {kpi.value}
                  </p>
                </Card>
              );
            })}
          </div>

          {/* Top Token Consumers */}
          <Card style={{ padding: 24 }}>
            <SectionHeader title="Top Token-Verbraucher" subtitle="Tenants nach Token-Nutzung sortiert" />
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {tokens.top_consumers.map((tc, i) => {
                const pct = tc.usage_pct;
                const barColor = pct > 90 ? T.danger : pct > 70 ? T.warning : T.accent;
                return (
                  <div key={tc.tenant_id} style={{
                    display: "flex", alignItems: "center", gap: 16, padding: "12px 16px",
                    borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8, background: T.accentDim,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 800, color: T.accentLight,
                    }}>
                      {i + 1}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{tc.tenant_name}</span>
                          <Badge variant="default" size="xs">{tc.plan_name}</Badge>
                        </div>
                        <span style={{ fontSize: 12, fontWeight: 600, color: T.textMuted }}>
                          {formatNumber(tc.tokens_used)} / {formatNumber(tc.token_limit)}
                        </span>
                      </div>
                      <div style={{ width: "100%", height: 6, borderRadius: 3, background: T.bg, overflow: "hidden" }}>
                        <div style={{
                          width: `${Math.min(pct, 100)}%`, height: "100%", borderRadius: 3,
                          background: barColor, transition: "width 0.6s ease",
                        }} />
                      </div>
                      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 4 }}>
                        <span style={{ fontSize: 10, fontWeight: 600, color: barColor }}>{pct.toFixed(1)}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {tokens.top_consumers.length === 0 && (
                <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                  Keine Token-Nutzungsdaten vorhanden
                </div>
              )}
            </div>
          </Card>

          {/* Token Usage Trend */}
          <Card style={{ padding: 24 }}>
            <SectionHeader title="Token-Verbrauch über Zeit" subtitle="Monatlicher Token-Verbrauch aller Tenants" />
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={monthly}>
                <defs>
                  <linearGradient id="gradTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={T.accent} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={T.accent} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
                <XAxis dataKey="label" stroke={T.textDim} tick={{ fontSize: 10 }} />
                <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} tickFormatter={formatNumber} />
                <Tooltip content={<CustomTooltipContent />} />
                <Area type="monotone" dataKey="tokens_used" name="Tokens" stroke={T.accent} fill="url(#gradTokens)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </>
      )}
    </div>
  );
}
