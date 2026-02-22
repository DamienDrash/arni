/**
 * chat-analytics.ts — K1 Backend-seitige Analytics (N+1-Fix)
 *
 * Vorher: bis zu 220 serielle HTTP-Requests (1 pro Chat-Session) vom Browser.
 * Jetzt:  4 parallele Requests gegen aggregierende Backend-Endpoints.
 *
 * Endpoints (alle tenant_id-geschützt via JWT):
 *   GET /admin/analytics/overview
 *   GET /admin/analytics/hourly
 *   GET /admin/analytics/weekly
 *   GET /admin/analytics/intents
 *   GET /admin/chats?limit=6   (recent sessions, bereits vorhanden)
 */

import { apiFetch } from "@/lib/api";

// ── Response-Types (spiegeln Backend-Schemas) ─────────────────────────────────

export type AnalyticsOverview = {
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

export type HourlyPoint = { hour: string; aiResolved: number; escalated: number };
export type WeeklyPoint = { day: string; date: string; tickets: number; resolved: number; escalated: number };
export type IntentRow = { intent: string; label: string; count: number; aiRate: number };
export type SatisfactionData = { average: number; total: number };

type RawSession = {
  user_id: string;
  platform?: string;
  user_name?: string | null;
};

type RecentSession = {
  id: string;
  channel: string;
  member: string;
  avatar: string;
  issue: string;
  confidence: number;
  status: string;
  time: string;
  messages: number;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

async function _get<T>(path: string): Promise<T | null> {
  try {
    const res = await apiFetch(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ── Main Export ───────────────────────────────────────────────────────────────

export async function buildChatAnalyticsFromHistory() {
  // 6 parallel requests instead of 1 + up to 220 sequential ones
  const [overview, hourly, weekly, intents, sessions, satisfaction] = await Promise.all([
    _get<AnalyticsOverview>("/admin/analytics/overview"),
    _get<HourlyPoint[]>("/admin/analytics/hourly"),
    _get<WeeklyPoint[]>("/admin/analytics/weekly"),
    _get<IntentRow[]>("/admin/analytics/intents"),
    _get<RawSession[]>("/admin/chats?limit=6"),
    _get<SatisfactionData>("/admin/analytics/satisfaction"),
  ]);

  // Map recent sessions to the display format expected by DashboardPage
  const recentSessions: RecentSession[] = (sessions ?? []).map((s, idx) => ({
    id: `T-${String(idx + 1).padStart(4, "0")}`,
    channel: (s.platform ?? "unknown").toLowerCase(),
    member: s.user_name ?? s.user_id,
    avatar: (s.user_name ?? s.user_id).slice(0, 2).toUpperCase(),
    issue: "",         // issue text requires individual history fetch — omit for perf
    confidence: 0,     // same — not available without individual fetch
    status: "resolved",
    time: "kürzlich",
    messages: 0,
  }));

  return {
    overview: overview ?? _emptyOverview(),
    hourly: hourly ?? [],
    weekly: weekly ?? [],
    intents: intents ?? [],
    recentSessions,
    // Legacy alias used by DashboardPage
    channels30: (weekly ?? []).length > 0 ? _deriveChannels30(overview) : [],
    satisfaction: satisfaction ?? { average: 0, total: 0 },
  };
}

function _emptyOverview(): AnalyticsOverview {
  return {
    tickets_24h: 0, resolved_24h: 0, escalated_24h: 0,
    ai_resolution_rate: 0, escalation_rate: 0,
    confidence_avg: 0, confidence_high_pct: 0, confidence_low_pct: 0,
    confidence_distribution: [],
    channels_24h: {},
    tickets_30d: 0, tickets_prev_30d: 0, month_trend_pct: 0,
  };
}

function _deriveChannels30(overview: AnalyticsOverview | null) {
  if (!overview) return [];
  // Approximate 30d channel breakdown from 24h data (same relative distribution)
  return Object.entries(overview.channels_24h)
    .sort(([, a], [, b]) => b - a)
    .map(([ch, count]) => {
      const aiRate = overview.ai_resolution_rate;
      return {
        ch,
        name: ch[0].toUpperCase() + ch.slice(1),
        tickets: count,
        aiRate: Math.round(aiRate),
        esc: `${Math.round(100 - aiRate)}%`,
      };
    });
}
