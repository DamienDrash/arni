"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
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
  const [satisfaction, setSatisfaction] = useState<{ average: number, total: number } | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await buildChatAnalyticsFromHistory();
      setOverview(data.overview as Overview);
      setWeekly(data.weekly as DailyPoint[]);
      setChannels(data.channels30 as ChannelRow[]);
      setSatisfaction(data.satisfaction);
    } catch {
      setOverview(null);
      setWeekly([]);
      setChannels([]);
      setSatisfaction(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // TODO (M2): Satisfaction scores werden hier gezeigt sobald das MemberFeedback-System
  // implementiert ist (POST /feedback/{session_id} → MemberFeedback-Tabelle).
  // Bis dahin kein Chart anzeigen, um keine Phantomdaten zu produzieren.

  const tickets30d = overview?.tickets_30d ?? 0;
  const trend = overview?.month_trend_pct ?? 0;
  const aiRate = overview?.ai_resolution_rate ?? 0;

  // NOTE: Kosteneinsparung ist eine Schätzung (Industrie-Benchmark: ~€0.23/KI-Ticket).
  // Für exakte Werte: tatsächliche Support-Kosten pro Ticket konfigurierbar machen.
  const COST_PER_TICKET_EUR = 0.23;
  const costSaved = Math.round(tickets30d * aiRate / 100 * COST_PER_TICKET_EUR);
  const trendLabel = `${trend >= 0 ? "+" : ""}${trend}% vs Vormonat`;

  const monthlySummary = [
    { label: "Gesamtkosten gespart", value: `€${costSaved.toLocaleString("de-DE")}`, sub: "vs manueller Support", color: T.success },
    { label: "Bearbeitete Tickets (Monat)", value: tickets30d >= 1000 ? `${(tickets30d / 1000).toFixed(1)}K` : String(tickets30d), sub: trendLabel, color: T.accent },
    { label: "AI-Lösungsrate", value: `${aiRate.toFixed(1)}%`, sub: "der Tickets ohne Eskalation", color: T.info },
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
              <Bar dataKey="resolved" stackId="a" fill={T.success} name="KI gelöst" radius={[0, 0, 0, 0]} />
              <Bar dataKey="escalated" stackId="a" fill={T.warning} name="Eskaliert" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Satisfaction Trend (M2: MemberFeedback-System) */}
        <Card style={{ padding: 24, display: "flex", flexDirection: "column", minHeight: 288 }}>
          <SectionHeader title="Kundenzufriedenheit" subtitle="Feedback nach KI-Interaktionen" />
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, marginTop: 24 }}>
            {!satisfaction || satisfaction.total === 0 ? (
              <>
                <div style={{ fontSize: 32, opacity: 0.3 }}>{loading ? "⏳" : "📊"}</div>
                <p style={{ fontSize: 13, fontWeight: 600, color: T.textMuted, margin: 0 }}>
                  {loading ? "Lade Daten..." : "Noch kein Feedback vorhanden"}
                </p>
                <p style={{ fontSize: 11, color: T.textDim, margin: 0, textAlign: "center", maxWidth: 200 }}>
                  Zufriedenheitswerte werden hier angezeigt, sobald Kunden die Chat-Bot-Sitzungen bewerten.
                </p>
              </>
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                  <div style={{ fontSize: 48, fontWeight: 800, color: T.accent, letterSpacing: "-0.04em", lineHeight: 1 }}>
                    {satisfaction.average.toFixed(1)}
                  </div>
                  <div style={{ fontSize: 36 }}>⭐️</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Durchschnittliche Bewertung</div>
                  <Badge variant="success" size="xs">Basierend auf {satisfaction.total} Bewertungen</Badge>
                </div>
              </>
            )}
          </div>
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
