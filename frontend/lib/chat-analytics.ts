import { apiFetch } from "@/lib/api";

type RawSession = {
  user_id: string;
  platform?: string;
  user_name?: string | null;
  last_active?: string;
};

type RawMessage = {
  role: string;
  content: string;
  timestamp: string;
  metadata?: unknown;
};

type NormalizedMessage = {
  role: string;
  content: string;
  timestampMs: number;
  channel: string;
  escalated: boolean;
  confidence: number | null;
  intent: string;
};

const DAY_NAMES_DE = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

function parseMeta(raw: unknown): Record<string, unknown> {
  if (!raw) return {};
  if (typeof raw === "object") return raw as Record<string, unknown>;
  if (typeof raw !== "string") return {};
  try {
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function toTs(value?: string) {
  const ts = value ? Date.parse(value) : NaN;
  return Number.isFinite(ts) ? ts : Date.now();
}

function normalizeHistory(messages: RawMessage[], fallbackChannel: string): NormalizedMessage[] {
  return messages.map((m) => {
    const meta = parseMeta(m.metadata);
    const confidenceRaw = meta.confidence;
    const confidence =
      typeof confidenceRaw === "number"
        ? confidenceRaw
        : typeof confidenceRaw === "string"
          ? Number(confidenceRaw)
          : null;
    const escalatedRaw = meta.escalated;
    const escalated = escalatedRaw === true || escalatedRaw === "true";
    return {
      role: m.role,
      content: m.content || "",
      timestampMs: toTs(m.timestamp),
      channel: String(meta.channel || fallbackChannel || "unknown").toLowerCase(),
      escalated,
      confidence: Number.isFinite(confidence as number) ? (confidence as number) : null,
      intent: String(meta.intent || "unknown"),
    };
  });
}

async function fetchRecentSessions(limit = 220): Promise<RawSession[]> {
  const res = await apiFetch(`/admin/chats?limit=${limit}`);
  if (!res.ok) return [];
  return (await res.json()) as RawSession[];
}

async function fetchHistory(userId: string): Promise<RawMessage[]> {
  const res = await apiFetch(`/admin/chats/${encodeURIComponent(userId)}/history`);
  if (!res.ok) return [];
  return (await res.json()) as RawMessage[];
}

async function mapWithConcurrency<T, R>(items: T[], worker: (item: T) => Promise<R>, concurrency = 12): Promise<R[]> {
  const out: R[] = [];
  let index = 0;
  async function run() {
    while (index < items.length) {
      const i = index;
      index += 1;
      out[i] = await worker(items[i]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, Math.max(1, items.length)) }, () => run()));
  return out;
}

export async function buildChatAnalyticsFromHistory() {
  const sessions = await fetchRecentSessions(220);
  const histories = await mapWithConcurrency(
    sessions,
    async (s) => normalizeHistory(await fetchHistory(s.user_id), s.platform || "unknown"),
    10,
  );

  const now = Date.now();
  const H24 = 24 * 60 * 60 * 1000;
  const D7 = 7 * H24;
  const D30 = 30 * H24;
  const D60 = 60 * H24;

  const allAssistant = histories.flat().filter((m) => m.role === "assistant");
  const in24 = allAssistant.filter((m) => now - m.timestampMs <= H24);
  const in30 = allAssistant.filter((m) => now - m.timestampMs <= D30);
  const in60 = allAssistant.filter((m) => now - m.timestampMs <= D60 && now - m.timestampMs > D30);

  const escal24 = in24.filter((m) => m.escalated).length;
  const conf = in24.map((m) => m.confidence).filter((v): v is number => typeof v === "number");
  const confAvg = conf.length ? (conf.reduce((a, b) => a + b, 0) / conf.length) * 100 : 0;

  const channels24: Record<string, number> = {};
  for (const m of in24) channels24[m.channel] = (channels24[m.channel] || 0) + 1;

  const hourlyMap: Record<number, { aiResolved: number; escalated: number }> = {};
  for (let h = 0; h < 24; h += 1) hourlyMap[h] = { aiResolved: 0, escalated: 0 };
  for (const m of in24) {
    const h = new Date(m.timestampMs).getHours();
    if (m.escalated) hourlyMap[h].escalated += 1;
    else hourlyMap[h].aiResolved += 1;
  }
  const hourly = Object.keys(hourlyMap).map((h) => ({
    hour: `${String(h).padStart(2, "0")}:00`,
    aiResolved: hourlyMap[Number(h)].aiResolved,
    escalated: hourlyMap[Number(h)].escalated,
  }));

  const intentStats: Record<string, { count: number; resolved: number }> = {};
  for (const m of in30) {
    const key = m.intent || "unknown";
    if (!intentStats[key]) intentStats[key] = { count: 0, resolved: 0 };
    intentStats[key].count += 1;
    if (!m.escalated) intentStats[key].resolved += 1;
  }
  const intents = Object.entries(intentStats)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 8)
    .map(([intent, s]) => ({
      intent,
      label: intent.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      count: s.count,
      aiRate: Math.round((s.resolved / Math.max(1, s.count)) * 100),
    }));

  const dailyMap: Record<string, { tickets: number; escalated: number }> = {};
  for (const m of allAssistant) {
    if (now - m.timestampMs > D7) continue;
    const d = new Date(m.timestampMs);
    const key = d.toISOString().slice(0, 10);
    if (!dailyMap[key]) dailyMap[key] = { tickets: 0, escalated: 0 };
    dailyMap[key].tickets += 1;
    if (m.escalated) dailyMap[key].escalated += 1;
  }
  const weekly = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(now - (6 - i) * H24);
    const key = d.toISOString().slice(0, 10);
    const rec = dailyMap[key] || { tickets: 0, escalated: 0 };
    return {
      day: DAY_NAMES_DE[d.getDay()],
      date: key,
      tickets: rec.tickets,
      resolved: rec.tickets - rec.escalated,
      escalated: rec.escalated,
    };
  });

  const channels30Map: Record<string, { tickets: number; resolved: number }> = {};
  for (const m of in30) {
    if (!channels30Map[m.channel]) channels30Map[m.channel] = { tickets: 0, resolved: 0 };
    channels30Map[m.channel].tickets += 1;
    if (!m.escalated) channels30Map[m.channel].resolved += 1;
  }
  const channels30 = Object.entries(channels30Map)
    .sort((a, b) => b[1].tickets - a[1].tickets)
    .map(([ch, v]) => {
      const aiRate = Math.round((v.resolved / Math.max(1, v.tickets)) * 100);
      return {
        ch,
        name: ch.toUpperCase() === "SMS" ? "SMS" : ch[0].toUpperCase() + ch.slice(1),
        tickets: v.tickets,
        aiRate,
        esc: `${100 - aiRate}%`,
      };
    });

  const recentSessions = sessions.slice(0, 10).map((s, idx) => {
    const history = histories[idx] || [];
    const lastUser = [...history].reverse().find((m) => m.role === "user");
    const lastAssistant = [...history].reverse().find((m) => m.role === "assistant");
    const confidence = Math.round(((lastAssistant?.confidence || 0) as number) * 100);
    return {
      id: `T-${String(idx + 1).padStart(4, "0")}`,
      channel: (s.platform || "unknown").toLowerCase(),
      member: s.user_name || s.user_id,
      avatar: (s.user_name || s.user_id).slice(0, 2).toUpperCase(),
      issue: (lastUser?.content || "").slice(0, 120),
      confidence,
      status: lastAssistant?.escalated ? "escalated" : "resolved",
      time: "kürzlich",
      messages: history.length,
    };
  });

  const overview = {
    tickets_24h: in24.length,
    resolved_24h: in24.length - escal24,
    escalated_24h: escal24,
    ai_resolution_rate: Number((((in24.length - escal24) / Math.max(1, in24.length)) * 100).toFixed(1)),
    escalation_rate: Number(((escal24 / Math.max(1, in24.length)) * 100).toFixed(1)),
    confidence_avg: Number(confAvg.toFixed(1)),
    confidence_high_pct: Math.round((conf.filter((c) => c >= 0.9).length / Math.max(1, conf.length)) * 100),
    confidence_low_pct: Math.round((conf.filter((c) => c < 0.5).length / Math.max(1, conf.length)) * 100),
    confidence_distribution: [
      { range: "90–100%", count: conf.filter((c) => c >= 0.9).length },
      { range: "75–89%", count: conf.filter((c) => c >= 0.75 && c < 0.9).length },
      { range: "50–74%", count: conf.filter((c) => c >= 0.5 && c < 0.75).length },
      { range: "<50%", count: conf.filter((c) => c < 0.5).length },
    ],
    channels_24h: channels24,
    tickets_30d: in30.length,
    tickets_prev_30d: in60.length,
    month_trend_pct: Number((((in30.length - in60.length) / Math.max(1, in60.length)) * 100).toFixed(1)),
  };

  return { overview, hourly, intents, weekly, channels30, recentSessions };
}
