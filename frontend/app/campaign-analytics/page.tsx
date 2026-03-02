"use client";

import React, { useEffect, useState, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import {
  BarChart3, TrendingUp, Send, Eye, MousePointerClick,
  AlertTriangle, ArrowUpRight, ArrowDownRight, RefreshCw,
  Mail, MessageSquare, Smartphone, ChevronDown
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

interface OverviewData {
  period_days: number;
  total_campaigns: number;
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_failed: number;
  total_conversions: number;
  total_conversion_value: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  conversion_rate: number;
}

interface FunnelStage {
  stage: string;
  count: number;
  rate: number;
}

interface FunnelData {
  campaign_id: number;
  campaign_name: string;
  funnel: FunnelStage[];
  bounced: number;
  unsubscribed: number;
  total_recipients: number;
}

interface CampaignRow {
  id: number;
  name: string;
  channel: string;
  sent_at: string | null;
  stats_total: number;
  stats_sent: number;
  stats_delivered: number;
  stats_opened: number;
  stats_clicked: number;
  stats_failed: number;
  open_rate: number;
  click_rate: number;
}

interface ChannelData {
  channel: string;
  campaigns: number;
  sent: number;
  delivered: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
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
  controls: {
    display: "flex",
    gap: 12,
    alignItems: "center",
  },
  select: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    color: T.text,
    padding: "8px 14px",
    fontSize: 13,
    cursor: "pointer",
    outline: "none",
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
  kpiRate: {
    fontSize: 13,
    fontWeight: 500,
    marginTop: 6,
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: T.text,
    marginBottom: 16,
  },
  row: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 24,
    marginBottom: 32,
  },
  card: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 24,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 600,
    color: T.text,
    marginBottom: 20,
  },
  // Funnel
  funnelBar: {
    marginBottom: 12,
  },
  funnelLabel: {
    display: "flex",
    justifyContent: "space-between",
    marginBottom: 4,
    fontSize: 13,
  },
  funnelTrack: {
    height: 28,
    background: T.surfaceAlt,
    borderRadius: 6,
    overflow: "hidden",
    position: "relative" as const,
  },
  funnelFill: {
    height: "100%",
    borderRadius: 6,
    transition: "width 0.6s ease",
    display: "flex",
    alignItems: "center",
    paddingLeft: 8,
    fontSize: 11,
    fontWeight: 600,
    color: "#fff",
  },
  // Channel comparison
  channelRow: {
    display: "flex",
    alignItems: "center",
    padding: "14px 0",
    borderBottom: `1px solid ${T.border}`,
  },
  channelIcon: {
    width: 36,
    height: 36,
    borderRadius: 8,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
  },
  channelName: {
    fontSize: 14,
    fontWeight: 600,
    color: T.text,
    flex: 1,
  },
  channelStat: {
    fontSize: 13,
    color: T.textMuted,
    width: 80,
    textAlign: "right" as const,
  },
  // Table
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
};

/* ── Helpers ───────────────────────────────────────────────────────── */

const channelConfig: Record<string, { icon: any; color: string; label: string }> = {
  email: { icon: Mail, color: T.email, label: "E-Mail" },
  whatsapp: { icon: MessageSquare, color: T.whatsapp, label: "WhatsApp" },
  sms: { icon: Smartphone, color: T.warning, label: "SMS" },
  telegram: { icon: Send, color: T.telegram, label: "Telegram" },
};

const funnelColors = [T.accent, T.accentLight, T.success, T.info, T.warning];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toLocaleString("de-DE");
}

function formatDate(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function CampaignAnalyticsPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [campaigns, setCampaigns] = useState<CampaignRow[]>([]);
  const [channels, setChannels] = useState<ChannelData[]>([]);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [selectedCampaignId, setSelectedCampaignId] = useState<number | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (period?: number) => {
    const d = period || days;
    try {
      const [overviewRes, campaignsRes, channelsRes] = await Promise.all([
        apiFetch(`/v2/admin/analytics/overview?days=${d}`),
        apiFetch(`/v2/admin/analytics/campaigns?per_page=50`),
        apiFetch(`/v2/admin/analytics/by-channel?days=${d}`),
      ]);
      setOverview(overviewRes);
      setCampaigns(campaignsRes.campaigns || []);
      setChannels(channelsRes.channels || []);

      // Load funnel for first campaign if available
      const firstCampaign = campaignsRes.campaigns?.[0];
      if (firstCampaign && !selectedCampaignId) {
        setSelectedCampaignId(firstCampaign.id);
        const funnelRes = await apiFetch(`/v2/admin/analytics/funnel?campaign_id=${firstCampaign.id}`);
        setFunnel(funnelRes);
      }
    } catch (err) {
      console.error("Analytics load error:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadFunnel = async (campaignId: number) => {
    setSelectedCampaignId(campaignId);
    try {
      const res = await apiFetch(`/v2/admin/analytics/funnel?campaign_id=${campaignId}`);
      setFunnel(res);
    } catch (err) {
      console.error("Funnel load error:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleDaysChange = (newDays: number) => {
    setDays(newDays);
    setLoading(true);
    loadData(newDays);
  };

  if (loading) {
    return (
      <div style={S.page}>
        <div style={S.loading}>
          <RefreshCw size={20} style={{ marginRight: 8, animation: "spin 1s linear infinite" }} />
          Analytics werden geladen...
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
            Performance-Übersicht der letzten {days} Tage
          </div>
        </div>
        <div style={S.controls}>
          <select
            style={S.select}
            value={days}
            onChange={(e) => handleDaysChange(Number(e.target.value))}
          >
            <option value={7}>Letzte 7 Tage</option>
            <option value={14}>Letzte 14 Tage</option>
            <option value={30}>Letzte 30 Tage</option>
            <option value={90}>Letzte 90 Tage</option>
            <option value={365}>Letztes Jahr</option>
          </select>
          <button
            style={S.refreshBtn}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw size={14} style={refreshing ? { animation: "spin 1s linear infinite" } : {}} />
            Aktualisieren
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {overview && (
        <div style={S.kpiGrid}>
          <KPICard
            label="Gesendet"
            value={formatNumber(overview.total_sent)}
            icon={<Send size={18} />}
            color={T.accent}
          />
          <KPICard
            label="Zugestellt"
            value={formatNumber(overview.total_delivered)}
            rate={overview.delivery_rate}
            icon={<TrendingUp size={18} />}
            color={T.success}
          />
          <KPICard
            label="Geöffnet"
            value={formatNumber(overview.total_opened)}
            rate={overview.open_rate}
            icon={<Eye size={18} />}
            color={T.info}
          />
          <KPICard
            label="Geklickt"
            value={formatNumber(overview.total_clicked)}
            rate={overview.click_rate}
            icon={<MousePointerClick size={18} />}
            color={T.accentLight}
          />
          <KPICard
            label="Conversions"
            value={formatNumber(overview.total_conversions)}
            rate={overview.conversion_rate}
            icon={<ArrowUpRight size={18} />}
            color={T.success}
          />
          <KPICard
            label="Umsatz"
            value={`€${formatNumber(overview.total_conversion_value)}`}
            icon={<BarChart3 size={18} />}
            color={T.warning}
          />
        </div>
      )}

      {/* Funnel + Channel Comparison */}
      <div style={S.row}>
        {/* Funnel */}
        <div style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <div style={S.cardTitle}>Kampagnen-Funnel</div>
            {campaigns.length > 0 && (
              <select
                style={{ ...S.select, fontSize: 12 }}
                value={selectedCampaignId || ""}
                onChange={(e) => loadFunnel(Number(e.target.value))}
              >
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
          {funnel ? (
            <>
              {funnel.funnel.map((stage, i) => (
                <div key={stage.stage} style={S.funnelBar}>
                  <div style={S.funnelLabel}>
                    <span style={{ color: T.text, fontWeight: 500 }}>{stage.stage}</span>
                    <span style={{ color: T.textMuted }}>{formatNumber(stage.count)} ({stage.rate}%)</span>
                  </div>
                  <div style={S.funnelTrack}>
                    <div
                      style={{
                        ...S.funnelFill,
                        width: `${Math.max(stage.rate, 2)}%`,
                        background: funnelColors[i % funnelColors.length],
                      }}
                    >
                      {stage.rate > 10 ? `${stage.rate}%` : ""}
                    </div>
                  </div>
                </div>
              ))}
              {(funnel.bounced > 0 || funnel.unsubscribed > 0) && (
                <div style={{ marginTop: 16, display: "flex", gap: 16 }}>
                  {funnel.bounced > 0 && (
                    <div style={{ ...S.badge, background: T.dangerDim, color: T.danger }}>
                      <AlertTriangle size={12} />
                      {funnel.bounced} Bounced
                    </div>
                  )}
                  {funnel.unsubscribed > 0 && (
                    <div style={{ ...S.badge, background: T.warningDim, color: T.warning }}>
                      <ArrowDownRight size={12} />
                      {funnel.unsubscribed} Abgemeldet
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div style={S.emptyState}>Keine Funnel-Daten verfügbar</div>
          )}
        </div>

        {/* Channel Comparison */}
        <div style={S.card}>
          <div style={S.cardTitle}>Kanal-Vergleich</div>
          {channels.length > 0 ? (
            channels.map((ch) => {
              const cfg = channelConfig[ch.channel] || { icon: Send, color: T.textMuted, label: ch.channel };
              const Icon = cfg.icon;
              return (
                <div key={ch.channel} style={S.channelRow}>
                  <div style={{ ...S.channelIcon, background: `${cfg.color}20` }}>
                    <Icon size={18} style={{ color: cfg.color }} />
                  </div>
                  <div style={S.channelName}>
                    {cfg.label}
                    <div style={{ fontSize: 11, color: T.textMuted, fontWeight: 400 }}>
                      {ch.campaigns} Kampagnen
                    </div>
                  </div>
                  <div style={S.channelStat}>
                    <div style={{ fontWeight: 600, color: T.text }}>{formatNumber(ch.sent)}</div>
                    <div style={{ fontSize: 11 }}>Gesendet</div>
                  </div>
                  <div style={S.channelStat}>
                    <div style={{ fontWeight: 600, color: T.success }}>{ch.open_rate}%</div>
                    <div style={{ fontSize: 11 }}>Öffnungsrate</div>
                  </div>
                  <div style={S.channelStat}>
                    <div style={{ fontWeight: 600, color: T.info }}>{ch.click_rate}%</div>
                    <div style={{ fontSize: 11 }}>Klickrate</div>
                  </div>
                </div>
              );
            })
          ) : (
            <div style={S.emptyState}>Keine Kanal-Daten verfügbar</div>
          )}
        </div>
      </div>

      {/* Campaign Performance Table */}
      <div style={{ ...S.card, marginBottom: 32 }}>
        <div style={S.cardTitle}>Kampagnen-Performance</div>
        {campaigns.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Kampagne</th>
                  <th style={S.th}>Kanal</th>
                  <th style={S.th}>Gesendet am</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Gesendet</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Zugestellt</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Geöffnet</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Geklickt</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Öffnungsrate</th>
                  <th style={{ ...S.th, textAlign: "right" }}>Klickrate</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => {
                  const cfg = channelConfig[c.channel] || { icon: Send, color: T.textMuted, label: c.channel };
                  return (
                    <tr
                      key={c.id}
                      style={{ cursor: "pointer" }}
                      onClick={() => loadFunnel(c.id)}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLElement).style.background = T.surfaceAlt;
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLElement).style.background = "transparent";
                      }}
                    >
                      <td style={{ ...S.td, fontWeight: 600, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.name}
                      </td>
                      <td style={S.td}>
                        <span style={{ ...S.badge, background: `${cfg.color}20`, color: cfg.color }}>
                          {cfg.label}
                        </span>
                      </td>
                      <td style={{ ...S.td, color: T.textMuted }}>{formatDate(c.sent_at)}</td>
                      <td style={{ ...S.td, textAlign: "right" }}>{formatNumber(c.stats_sent || 0)}</td>
                      <td style={{ ...S.td, textAlign: "right" }}>{formatNumber(c.stats_delivered || 0)}</td>
                      <td style={{ ...S.td, textAlign: "right" }}>{formatNumber(c.stats_opened || 0)}</td>
                      <td style={{ ...S.td, textAlign: "right" }}>{formatNumber(c.stats_clicked || 0)}</td>
                      <td style={{ ...S.td, textAlign: "right", color: T.success, fontWeight: 600 }}>
                        {c.open_rate}%
                      </td>
                      <td style={{ ...S.td, textAlign: "right", color: T.info, fontWeight: 600 }}>
                        {c.click_rate}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={S.emptyState}>
            <BarChart3 size={48} style={{ color: T.textDim, marginBottom: 12 }} />
            <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Noch keine Kampagnen versendet</div>
            <div style={{ fontSize: 13, color: T.textDim }}>
              Erstellen und versenden Sie Ihre erste Kampagne, um Analytics-Daten zu sehen.
            </div>
          </div>
        )}
      </div>

      {/* CSS Animation */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

/* ── Sub-Components ────────────────────────────────────────────────── */

function KPICard({
  label, value, rate, icon, color,
}: {
  label: string;
  value: string;
  rate?: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div style={S.kpiCard}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={S.kpiLabel}>{label}</div>
          <div style={S.kpiValue}>{value}</div>
          {rate !== undefined && (
            <div style={{ ...S.kpiRate, color: rate > 0 ? T.success : T.textMuted }}>
              {rate > 0 ? <ArrowUpRight size={14} /> : null}
              {rate}% Rate
            </div>
          )}
        </div>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `${color}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: color,
        }}>
          {icon}
        </div>
      </div>
    </div>
  );
}
