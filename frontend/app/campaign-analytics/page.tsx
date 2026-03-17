"use client";

import React, { useEffect, useState, useCallback, CSSProperties } from "react";
import { useRouter } from "next/navigation";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import {
  BarChart3, Send, Eye, MousePointerClick, RefreshCw,
  ChevronDown, ChevronRight, Trophy,
} from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

/* ── Types ─────────────────────────────────────────────────────────── */

interface Campaign {
  id: number;
  name: string;
  channel: string;
  status: "draft" | "scheduled" | "sending" | "sent" | "paused";
  scheduled_at?: string;
  sent_at?: string;
  created_at: string;
}

interface CampaignAnalytics {
  campaign: Campaign;
  summary: {
    total_recipients: number;
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
    bounced: number;
    unsubscribed: number;
  };
  variants: Array<{
    variant_name: string;
    recipients: number;
    sent: number;
    open_rate: number;
    click_rate: number;
    is_winner: boolean;
  }>;
  timeline: Array<{
    date: string;
    sent: number;
    opened: number;
    clicked: number;
  }>;
}

/* ── Styles ────────────────────────────────────────────────────────── */

const S: Record<string, CSSProperties> = {
  page: {
    minHeight: "100vh",
    background: T.bg,
    color: T.text,
    padding: "32px 40px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 32,
  },
  title: {
    fontSize: 28,
    fontWeight: 700,
    color: T.text,
    letterSpacing: "-0.02em",
  },
  subtitle: {
    fontSize: 14,
    color: T.textMuted,
    marginTop: 4,
  },
  refreshBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    color: T.textMuted,
    padding: "8px 14px",
    fontSize: 13,
    cursor: "pointer",
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: 16,
    marginBottom: 32,
  },
  kpiCard: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: "20px 24px",
  },
  kpiLabel: {
    fontSize: 12,
    fontWeight: 500,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    marginBottom: 8,
  },
  kpiValue: {
    fontSize: 28,
    fontWeight: 700,
    color: T.text,
    lineHeight: 1.1,
  },
  card: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 24,
    marginBottom: 32,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: T.text,
    marginBottom: 20,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 14px",
    fontSize: 11,
    fontWeight: 600,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    borderBottom: `1px solid ${T.border}`,
  },
  td: {
    padding: "12px 14px",
    fontSize: 13,
    color: T.text,
    borderBottom: `1px solid ${T.border}`,
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "3px 10px",
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 600,
  },
  loading: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: 400,
    color: T.textMuted,
    fontSize: 15,
  },
  emptyState: {
    textAlign: "center" as const,
    padding: "60px 20px",
    color: T.textMuted,
  },
  error: {
    textAlign: "center" as const,
    padding: "60px 20px",
    color: T.danger,
  },
  variantRow: {
    background: T.surfaceAlt,
  },
};

/* ── Helpers ───────────────────────────────────────────────────────── */

const statusColors: Record<string, { bg: string; color: string }> = {
  draft: { bg: "rgba(138,140,156,0.15)", color: T.textMuted },
  scheduled: { bg: T.infoDim, color: T.info },
  sending: { bg: T.warningDim, color: T.warning },
  sent: { bg: T.successDim, color: T.success },
  paused: { bg: T.dangerDim, color: T.danger },
};

function pct(count: number, total: number): string {
  if (total <= 0) return "—";
  return (count / total * 100).toFixed(1) + "%";
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString("de-DE");
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function CampaignAnalyticsPage() {
  const router = useRouter();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<Record<number, CampaignAnalytics>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCampaigns = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns");
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      setCampaigns(data.campaigns ?? data ?? []);
      setError(null);
    } catch {
      setError("Kampagnen konnten nicht geladen werden.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const user = getStoredUser();
    if (!user) { router.replace("/login"); return; }
    if (user.role !== "system_admin" && user.role !== "tenant_admin") {
      router.replace("/login");
      return;
    }
    loadCampaigns();
  }, [router, loadCampaigns]);

  const handleExpand = async (id: number) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    if (analytics[id]) return;
    try {
      const res = await apiFetch(`/admin/campaigns/${id}/analytics`);
      if (!res.ok) return;
      const data: CampaignAnalytics = await res.json();
      setAnalytics((prev) => ({ ...prev, [id]: data }));
    } catch {
      /* silent — row just stays collapsed */
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setAnalytics({});
    setExpanded(null);
    loadCampaigns();
  };

  /* ── Computed summary ───────────────────────────────────────── */
  const summary = React.useMemo(() => {
    const loaded = Object.values(analytics);
    let totalSent = 0, totalOpened = 0, totalClicked = 0;
    loaded.forEach((a) => {
      totalSent += a.summary.sent;
      totalOpened += a.summary.opened;
      totalClicked += a.summary.clicked;
    });
    return {
      totalCampaigns: campaigns.length,
      totalSent,
      avgOpenRate: totalSent > 0 ? (totalOpened / totalSent * 100).toFixed(1) : "—",
      avgClickRate: totalSent > 0 ? (totalClicked / totalSent * 100).toFixed(1) : "—",
    };
  }, [campaigns, analytics]);

  /* ── Merged timeline across all loaded analytics ──────────── */
  const mergedTimeline = React.useMemo(() => {
    const byDate: Record<string, { date: string; sent: number; opened: number; clicked: number }> = {};
    Object.values(analytics).forEach((a) => {
      (a.timeline ?? []).forEach((t) => {
        if (!byDate[t.date]) byDate[t.date] = { date: t.date, sent: 0, opened: 0, clicked: 0 };
        byDate[t.date].sent += t.sent;
        byDate[t.date].opened += t.opened;
        byDate[t.date].clicked += t.clicked;
      });
    });
    return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
  }, [analytics]);

  /* ── Render ─────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div style={S.page}>
        <div style={S.loading}>
          <RefreshCw size={20} style={{ marginRight: 8, animation: "spin 1s linear infinite" }} />
          Analytics werden geladen…
        </div>
        <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div style={S.page}>
        <div style={S.error}>
          <BarChart3 size={48} style={{ color: T.danger, marginBottom: 12 }} />
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={S.header}>
        <div>
          <div style={S.title}>Kampagnen-Analytics</div>
          <div style={S.subtitle}>
            Übersicht aller Kampagnen und deren Performance
          </div>
        </div>
        <button style={S.refreshBtn} onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw size={14} style={refreshing ? { animation: "spin 1s linear infinite" } : {}} />
          Aktualisieren
        </button>
      </div>

      {/* KPI Summary Cards */}
      <div style={S.kpiGrid}>
        <KPICard label="Kampagnen" value={String(summary.totalCampaigns)} icon={<BarChart3 size={18} />} color={T.accent} />
        <KPICard label="Gesendet" value={formatNumber(summary.totalSent)} icon={<Send size={18} />} color={T.info} />
        <KPICard label="Ø Öffnungsrate" value={summary.avgOpenRate === "—" ? "—" : summary.avgOpenRate + "%"} icon={<Eye size={18} />} color={T.success} />
        <KPICard label="Ø Klickrate" value={summary.avgClickRate === "—" ? "—" : summary.avgClickRate + "%"} icon={<MousePointerClick size={18} />} color={T.accentLight} />
      </div>

      {/* Campaign Table */}
      <div style={S.card}>
        <div style={S.cardTitle}>Kampagnen-Performance</div>
        {campaigns.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={{ ...S.th, width: 28 }} />
                  <th style={S.th}>Name</th>
                  <th style={S.th}>Kanal</th>
                  <th style={S.th}>Status</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Gesendet</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Zugestellt %</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Geöffnet %</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Geklickt %</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Bounced %</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => {
                  const isExpanded = expanded === c.id;
                  const a = analytics[c.id];
                  const s = a?.summary;
                  const sc = statusColors[c.status] ?? statusColors.draft;
                  return (
                    <React.Fragment key={c.id}>
                      <tr
                        style={{ cursor: "pointer" }}
                        onClick={() => handleExpand(c.id)}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = T.surfaceAlt; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                      >
                        <td style={{ ...S.td, width: 28, paddingRight: 0 }}>
                          {isExpanded
                            ? <ChevronDown size={14} style={{ color: T.textMuted }} />
                            : <ChevronRight size={14} style={{ color: T.textMuted }} />}
                        </td>
                        <td style={{ ...S.td, fontWeight: 600, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.name}
                        </td>
                        <td style={S.td}>{c.channel}</td>
                        <td style={S.td}>
                          <span style={{ ...S.badge, background: sc.bg, color: sc.color }}>
                            {c.status}
                          </span>
                        </td>
                        <td style={{ ...S.td, textAlign: "right" }}>{s ? formatNumber(s.sent) : "—"}</td>
                        <td style={{ ...S.td, textAlign: "right" }}>{s ? pct(s.delivered, s.sent) : "—"}</td>
                        <td style={{ ...S.td, textAlign: "right", color: T.success, fontWeight: 600 }}>{s ? pct(s.opened, s.sent) : "—"}</td>
                        <td style={{ ...S.td, textAlign: "right", color: T.info, fontWeight: 600 }}>{s ? pct(s.clicked, s.sent) : "—"}</td>
                        <td style={{ ...S.td, textAlign: "right", color: T.danger }}>{s ? pct(s.bounced, s.sent) : "—"}</td>
                      </tr>

                      {/* Expanded: A/B Variant Breakdown */}
                      {isExpanded && a && a.variants.length > 0 && (
                        <>
                          <tr style={S.variantRow}>
                            <td style={{ ...S.td, borderBottom: "none" }} />
                            <td colSpan={8} style={{ ...S.td, borderBottom: "none", paddingTop: 16, paddingBottom: 4, fontSize: 11, fontWeight: 600, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                              A/B-Varianten
                            </td>
                          </tr>
                          {a.variants.map((v) => (
                            <tr key={v.variant_name} style={S.variantRow}>
                              <td style={{ ...S.td, borderBottom: `1px solid ${T.border}` }} />
                              <td style={{ ...S.td, paddingLeft: 28 }}>
                                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                                  {v.variant_name}
                                  {v.is_winner && (
                                    <span style={{ ...S.badge, background: T.successDim, color: T.success, fontSize: 10 }}>
                                      <Trophy size={10} /> Winner
                                    </span>
                                  )}
                                </span>
                              </td>
                              <td style={S.td} />
                              <td style={S.td} />
                              <td style={{ ...S.td, textAlign: "right" }}>{formatNumber(v.sent)}</td>
                              <td style={S.td} />
                              <td style={{ ...S.td, textAlign: "right", color: T.success, fontWeight: 600 }}>{v.open_rate.toFixed(1)}%</td>
                              <td style={{ ...S.td, textAlign: "right", color: T.info, fontWeight: 600 }}>{v.click_rate.toFixed(1)}%</td>
                              <td style={S.td} />
                            </tr>
                          ))}
                        </>
                      )}
                      {isExpanded && a && a.variants.length === 0 && (
                        <tr style={S.variantRow}>
                          <td style={S.td} />
                          <td colSpan={8} style={{ ...S.td, color: T.textDim, fontStyle: "italic" }}>
                            Keine A/B-Varianten für diese Kampagne
                          </td>
                        </tr>
                      )}
                      {isExpanded && !a && (
                        <tr style={S.variantRow}>
                          <td style={S.td} />
                          <td colSpan={8} style={{ ...S.td, color: T.textDim }}>
                            <RefreshCw size={12} style={{ marginRight: 6, animation: "spin 1s linear infinite" }} />
                            Lade Analytics…
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={S.emptyState}>
            <BarChart3 size={48} style={{ color: T.textDim, marginBottom: 12 }} />
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Noch keine Kampagnen</div>
            <div style={{ fontSize: 13, color: T.textDim }}>
              Erstellen und versenden Sie Ihre erste Kampagne, um Analytics-Daten zu sehen.
            </div>
          </div>
        )}
      </div>

      {/* Time-Series Chart */}
      {mergedTimeline.length > 0 && (
        <div style={S.card}>
          <div style={S.cardTitle}>Verlauf (letzte 30 Tage)</div>
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mergedTimeline} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={T.border} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: T.textMuted, fontSize: 11 }}
                  stroke={T.border}
                  tickFormatter={(v: string) => {
                    const d = new Date(v);
                    return `${d.getDate()}.${d.getMonth() + 1}`;
                  }}
                />
                <YAxis tick={{ fill: T.textMuted, fontSize: 11 }} stroke={T.border} />
                <Tooltip
                  contentStyle={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: T.text }}
                  itemStyle={{ color: T.text }}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: T.textMuted }} />
                <Line type="monotone" dataKey="sent" name="Gesendet" stroke={T.accent} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="opened" name="Geöffnet" stroke={T.success} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="clicked" name="Geklickt" stroke={T.info} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* CSS Animation */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ── Sub-Components ────────────────────────────────────────────────── */

function KPICard({ label, value, icon, color }: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div style={S.kpiCard}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={S.kpiLabel}>{label}</div>
          <div style={S.kpiValue}>{value}</div>
        </div>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `${color}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color,
        }}>
          {icon}
        </div>
      </div>
    </div>
  );
}
