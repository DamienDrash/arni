"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Area, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";
import { MessageSquare, Cpu, Clock, Star, ArrowUpRight, RefreshCw } from "lucide-react";

import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MiniButton } from "@/components/ui/MiniButton";
import { Stat } from "@/components/ui/Stat";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Avatar } from "@/components/ui/Avatar";
import { ChannelIcon } from "@/components/ui/ChannelIcon";
import { CustomTooltip } from "@/components/ui/CustomTooltip";
import { buildChatAnalyticsFromHistory } from "@/lib/chat-analytics";

// ── Types ──────────────────────────────────────────────────────────────────────

type Overview = {
  tickets_24h: number;
  resolved_24h: number;
  escalated_24h: number;
  ai_resolution_rate: number;
  escalation_rate: number;
  confidence_avg: number;
  confidence_high_pct: number;
  confidence_low_pct: number;
  confidence_distribution: { range: string; count: number }[];
  channels_24h: Record<string, number>;
  tickets_30d: number;
  tickets_prev_30d: number;
  month_trend_pct: number;
};

type HourlyPoint = { hour: string; aiResolved: number; escalated: number };
type Intent = { intent: string; label: string; count: number; aiRate: number };
type Session = {
  id: string; channel: string; member: string; avatar: string;
  issue: string; confidence: number; status: string; time: string; messages: number;
};

const CHANNEL_META: Record<string, { name: string; color: string; icon: string; ch: "whatsapp" | "telegram" | "email" | "phone" | "sms" }> = {
  whatsapp: { name: "WhatsApp", color: T.whatsapp, icon: "WA", ch: "whatsapp" },
  telegram: { name: "Telegram", color: T.telegram, icon: "TG", ch: "telegram" },
  email:    { name: "E-Mail",   color: T.email,    icon: "EM", ch: "email" },
  sms:      { name: "SMS",      color: T.warning,  icon: "SM", ch: "phone" },
  phone:    { name: "Telefon",  color: T.phone,    icon: "PH", ch: "phone" },
};

const CONF_COLORS: Record<string, string> = {
  "90–100%": T.success,
  "75–89%":  T.info,
  "50–74%":  T.warning,
  "<50%":    T.danger,
};

export function DashboardPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [hourly, setHourly] = useState<HourlyPoint[]>([]);
  const [intents, setIntents] = useState<Intent[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      const data = await buildChatAnalyticsFromHistory();
      setOverview(data.overview as Overview);
      setHourly(data.hourly as HourlyPoint[]);
      setIntents(data.intents.slice(0, 6) as Intent[]);
      setSessions(data.recentSessions.slice(0, 6) as Session[]);
    } catch {
      setOverview(null);
      setHourly([]);
      setIntents([]);
      setSessions([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // Refresh every 60s
  useEffect(() => {
    const t = setInterval(() => void load(true), 60000);
    return () => clearInterval(t);
  }, [load]);

  const totalTickets24h = overview?.tickets_24h ?? 0;
  const aiResRate = overview?.ai_resolution_rate ?? 0;
  const confAvg = overview?.confidence_avg ?? 0;
  const monthTrend = overview?.month_trend_pct ?? 0;

  const kpis = [
    {
      label: "Tickets (24h)", value: String(totalTickets24h), unit: undefined,
      trend: `${monthTrend >= 0 ? "+" : ""}${monthTrend}%`, trendDir: "up" as const,
      icon: <MessageSquare size={18} />, color: T.info,
    },
    {
      label: "AI Resolution", value: aiResRate.toFixed(1), unit: "%",
      trend: `${aiResRate >= 80 ? "▲" : "▼"} ${aiResRate.toFixed(1)}%`, trendDir: "up" as const,
      icon: <Cpu size={18} />, color: T.success,
    },
    {
      label: "Ø Confidence", value: confAvg.toFixed(0), unit: "%",
      trend: confAvg >= 80 ? "High" : "Mid", trendDir: "up" as const,
      icon: <Clock size={18} />, color: T.warning,
    },
    {
      label: "Tickets (30d)", value: overview ? String(overview.tickets_30d) : "–", unit: undefined,
      trend: `${monthTrend >= 0 ? "+" : ""}${monthTrend}% vs Vormonat`, trendDir: "up" as const,
      icon: <Star size={18} />, color: T.accent,
    },
  ];

  const channelData = overview
    ? Object.entries(overview.channels_24h)
        .sort(([, a], [, b]) => b - a)
        .map(([ch, count]) => ({
          ch,
          name: CHANNEL_META[ch]?.name ?? ch,
          value: count,
          color: CHANNEL_META[ch]?.color ?? T.textDim,
          channelKey: (CHANNEL_META[ch]?.ch ?? "email") as "whatsapp" | "telegram" | "email" | "phone",
        }))
    : [];

  const confDist = (overview?.confidence_distribution ?? []).map((d) => ({
    ...d,
    fill: CONF_COLORS[d.range] ?? T.textDim,
  }));
  const confTotal = confDist.reduce((s, d) => s + d.count, 0);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: T.textDim, fontSize: 13 }}>
        Lade Analytics…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* System Banner */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderRadius: 12, background: T.successDim, border: `1px solid rgba(0,214,143,0.2)` }}>
        <div style={{ width: 8, height: 8, borderRadius: 4, background: T.success, boxShadow: `0 0 8px ${T.success}` }} />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: T.success }}>Alle Systeme online</span>
          <span style={{ fontSize: 12, color: T.textMuted, marginLeft: 16 }}>
            {totalTickets24h} Tickets heute · {overview?.tickets_30d ?? 0} im letzten Monat
          </span>
        </div>
        <Badge variant="success">LIVE</Badge>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => (
          <Card key={i} style={{ padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: `${kpi.color}15`, display: "flex", alignItems: "center", justifyContent: "center", color: kpi.color }}>
                {kpi.icon}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 3, padding: "3px 8px", borderRadius: 6, background: T.successDim }}>
                <ArrowUpRight size={11} color={T.success} />
                <span style={{ fontSize: 11, fontWeight: 600, color: T.success }}>{kpi.trend}</span>
              </div>
            </div>
            <p style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{kpi.label}</p>
            <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
              <span style={{ fontSize: 32, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>{kpi.value}</span>
              {kpi.unit && <span style={{ fontSize: 14, color: T.textMuted, fontWeight: 500 }}>{kpi.unit}</span>}
            </div>
          </Card>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Channel breakdown */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Kanäle" subtitle="Ticket-Verteilung (24h)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {channelData.length === 0 && (
              <div style={{ fontSize: 12, color: T.textDim }}>Keine Daten für die letzten 24h.</div>
            )}
            {channelData.map((ch, i) => {
              const pct = totalTickets24h > 0 ? Math.round((ch.value / totalTickets24h) * 100) : 0;
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <ChannelIcon channel={ch.channelKey} size={18} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{ch.name}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: ch.color }}>
                        {ch.value} <span style={{ color: T.textDim, fontWeight: 400 }}>({pct}%)</span>
                      </span>
                    </div>
                    <ProgressBar value={pct} color={ch.color} height={5} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Resolution Trend */}
        <Card style={{ padding: 24 }} className="lg:col-span-2">
          <SectionHeader title="AI-Lösung vs Eskalation" subtitle="Stündlicher Verlauf (24h)" />
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={hourly.filter((_, i) => i % 2 === 0)}>
              <defs>
                <linearGradient id="aiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={T.success} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={T.success} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="hour" stroke={T.textDim} tick={{ fontSize: 10 }} />
              <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="aiResolved" fill="url(#aiGrad)" stroke={T.success} strokeWidth={2} name="KI gelöst" />
              <Bar dataKey="escalated" fill={T.warning} opacity={0.7} name="Eskaliert" radius={[3, 3, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top Issues */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Top Support-Themen" subtitle="Häufigkeit & AI-Performance (30d)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {intents.slice(0, 6).map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", borderRadius: 10, background: T.surfaceAlt }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: T.textDim, width: 18 }}>#{i + 1}</span>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: T.text, margin: 0 }}>{item.label}</p>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: "2px 0 0" }}>{item.count} Tickets</p>
                </div>
                <Badge variant={item.aiRate >= 90 ? "success" : item.aiRate >= 70 ? "info" : item.aiRate >= 50 ? "warning" : "danger"}>
                  {item.aiRate}% KI
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        {/* Confidence Distribution */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Confidence Score" subtitle="Verteilung der Lösungssicherheit (24h)" />
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 8 }}>
            {confDist.map((item, i) => (
              <div key={i}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{item.range}</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: item.fill }}>
                    {item.count}{" "}
                    <span style={{ color: T.textDim, fontWeight: 400 }}>
                      ({confTotal > 0 ? Math.round((item.count / confTotal) * 100) : 0}%)
                    </span>
                  </span>
                </div>
                <ProgressBar value={item.count} max={Math.max(confTotal, 1)} color={item.fill} height={6} />
              </div>
            ))}
          </div>
          <div style={{ marginTop: 24, padding: 16, borderRadius: 10, background: T.surfaceAlt, display: "flex", justifyContent: "space-around" }}>
            <Stat label="Ø Score"   value={String(overview?.confidence_avg?.toFixed(0) ?? "–")} unit="%" color={T.info} />
            <div style={{ width: 1, background: T.border }} />
            <Stat label="High Conf." value={String(overview?.confidence_high_pct ?? "–")} unit="%" color={T.success} />
            <div style={{ width: 1, background: T.border }} />
            <Stat label="Low Conf."  value={String(overview?.confidence_low_pct ?? "–")}  unit="%" color={T.danger} />
          </div>
        </Card>
      </div>

      {/* Recent Tickets */}
      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Letzte Support-Tickets"
          subtitle="Echtzeit-Monitoring"
          action={
            <MiniButton onClick={() => void load(true)}>
              <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} /> Live
            </MiniButton>
          }
        />
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Ticket", "Kanal", "Mitglied", "Anfrage", "Confidence", "Status", "Zeit"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", borderBottom: `1px solid ${T.border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map((t, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${T.border}` }}>
                  <td style={{ padding: "12px", fontSize: 12, fontWeight: 600, color: T.accentLight, fontFamily: "monospace" }}>{t.id}</td>
                  <td style={{ padding: "12px" }}>
                    <ChannelIcon channel={(CHANNEL_META[t.channel]?.ch ?? "email") as "whatsapp" | "telegram" | "email" | "phone"} size={14} />
                  </td>
                  <td style={{ padding: "12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Avatar initials={t.avatar} size={26} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{t.member}</span>
                    </div>
                  </td>
                  <td style={{ padding: "12px", fontSize: 12, color: T.textMuted, maxWidth: 280, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.issue}</td>
                  <td style={{ padding: "12px" }}>
                    <Badge variant={t.confidence >= 90 ? "success" : t.confidence >= 70 ? "info" : t.confidence >= 50 ? "warning" : "danger"}>{t.confidence}%</Badge>
                  </td>
                  <td style={{ padding: "12px" }}>
                    <Badge variant={t.status === "resolved" ? "success" : t.status === "escalated" ? "danger" : "warning"}>
                      {t.status === "resolved" ? "Gelöst" : t.status === "escalated" ? "Eskaliert" : "Ausstehend"}
                    </Badge>
                  </td>
                  <td style={{ padding: "12px", fontSize: 11, color: T.textDim }}>{t.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
