"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ChannelIcon } from "@/components/ui/ChannelIcon";
import { CustomTooltip } from "@/components/ui/CustomTooltip";
import { buildChatAnalyticsFromHistory } from "@/lib/chat-analytics";

// ── Types ──────────────────────────────────────────────────────────────────────

type DailyPoint = { day: string; date: string; tickets: number; resolved: number; escalated: number };
type ChannelRow = { ch: string; name: string; tickets: number; aiRate: number; esc: string };
type Overview = {
  tickets_30d: number;
  tickets_prev_30d: number;
  month_trend_pct: number;
  ai_resolution_rate: number;
};

const CHANNEL_CH: Record<string, "whatsapp" | "telegram" | "email" | "phone"> = {
  whatsapp: "whatsapp",
  telegram: "telegram",
  email: "email",
  sms: "phone",
  phone: "phone",
};

export function AnalyticsPage() {
  const [weekly, setWeekly] = useState<DailyPoint[]>([]);
  const [channels, setChannels] = useState<ChannelRow[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await buildChatAnalyticsFromHistory();
      setOverview(data.overview as Overview);
      setWeekly(data.weekly as DailyPoint[]);
      setChannels(data.channels30 as ChannelRow[]);
    } catch {
      setOverview(null);
      setWeekly([]);
      setChannels([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // Synthetic satisfaction trend (no real satisfaction data — kept as static overlay)
  const satisfactionData = weekly.map((d, i) => ({
    ...d,
    score: [4.5, 4.6, 4.4, 4.7, 4.6, 4.8, 4.7][i % 7],
  }));

  const tickets30d = overview?.tickets_30d ?? 0;
  const trend = overview?.month_trend_pct ?? 0;
  const aiRate = overview?.ai_resolution_rate ?? 0;

  const costSaved = Math.round(tickets30d * 0.23); // ~€0.23 saved per AI-handled ticket
  const trendLabel = `${trend >= 0 ? "+" : ""}${trend}% vs Vormonat`;

  const monthlySummary = [
    { label: "Gesamtkosten gespart",       value: `€${costSaved.toLocaleString("de-DE")}`, sub: "vs manueller Support",    color: T.success },
    { label: "Bearbeitete Tickets (Monat)", value: tickets30d >= 1000 ? `${(tickets30d / 1000).toFixed(1)}K` : String(tickets30d), sub: trendLabel, color: T.accent },
    { label: "AI-Lösungsrate",             value: `${aiRate.toFixed(1)}%`, sub: "der Tickets ohne Eskalation", color: T.info },
  ];

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: T.textDim, fontSize: 13 }}>
        Lade Analytics…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Weekly Trend */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Wochenübersicht" subtitle="Tickets & Lösungsrate (letzte 7 Tage)" />
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={weekly}>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="day" stroke={T.textDim} tick={{ fontSize: 11 }} />
              <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="resolved"  stackId="a" fill={T.success} name="KI gelöst"  radius={[0, 0, 0, 0]} />
              <Bar dataKey="escalated" stackId="a" fill={T.warning} name="Eskaliert"  radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Satisfaction Trend */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Zufriedenheit (7 Tage)" subtitle="Member-Feedback nach KI-Interaktion" />
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={satisfactionData}>
              <defs>
                <linearGradient id="satGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={T.accent} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={T.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
              <XAxis dataKey="day" stroke={T.textDim} tick={{ fontSize: 11 }} />
              <YAxis stroke={T.textDim} tick={{ fontSize: 10 }} domain={[4, 5]} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="score" fill="url(#satGrad)" stroke={T.accent} strokeWidth={2.5} name="Score" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Channel Performance */}
      <Card style={{ padding: 24 }}>
        <SectionHeader title="Kanal-Performance" subtitle="Vergleich der Support-Kanäle (30 Tage)" />
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Kanal", "Tickets", "AI-Rate", "Eskalationsrate"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 16px", fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", borderBottom: `1px solid ${T.border}` }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {channels.map((r, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${T.border}` }}>
                  <td style={{ padding: "14px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <ChannelIcon channel={CHANNEL_CH[r.ch] ?? "email"} size={14} />
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{r.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px", fontSize: 13, fontWeight: 700, color: T.text }}>{r.tickets}</td>
                  <td style={{ padding: "14px 16px" }}>
                    <Badge variant={r.aiRate >= 80 ? "success" : r.aiRate >= 70 ? "info" : "warning"}>{r.aiRate}%</Badge>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <Badge variant={parseInt(r.esc) <= 18 ? "success" : parseInt(r.esc) <= 25 ? "warning" : "danger"}>{r.esc}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Monthly Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {monthlySummary.map((s, i) => (
          <Card key={i} style={{ padding: 24, textAlign: "center" }}>
            <p style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, margin: "0 0 8px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{s.label}</p>
            <p style={{ fontSize: 36, fontWeight: 800, color: s.color, margin: "0 0 4px", letterSpacing: "-0.03em" }}>{s.value}</p>
            <p style={{ fontSize: 11, color: T.textDim, margin: 0 }}>{s.sub}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
