"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Search, Users } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

type CheckinStats = {
  total_30d?: number;
  total_90d?: number;
  avg_training_30d_per_week?: number;
  avg_training_90d_per_week?: number;
  avg_per_week?: number;
  last_visit?: string;
  status?: string;
  source?: string;
  top_category?: string;
  preferred_training_sessions?: string[];
  preferred_training_days?: string[];
  preferred_training_time?: string;
  next_appointment?: { type?: string; title?: string; start?: string; status?: string };
  last_appointment?: { type?: string; title?: string; start?: string; status?: string };
  churn_prediction?: { score?: number; risk?: "low" | "medium" | "high"; reasons?: string[] };
};

type BookingItem = { type?: string; title?: string; start?: string; status?: string };
type RecentBookings = { upcoming?: BookingItem[]; past?: BookingItem[] };

type PauseInfo = {
  is_currently_paused?: boolean;
  pause_until?: string | null;
  pause_reason?: string | null;
  paused_days_180?: number;
  last_pause_end?: string | null;
  last_pause_reason?: string | null;
};

type Member = {
  customer_id: number;
  member_number?: string | null;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone_number?: string | null;
  email?: string | null;
  gender?: string | null;
  preferred_language?: string | null;
  member_since?: string | null;
  is_paused?: boolean | null;
  pause_info?: PauseInfo | null;
  enriched_at?: string | null;
  additional_info?: Record<string, string> | null;
  checkin_stats?: CheckinStats | null;
  recent_bookings?: RecentBookings | null;
  verified?: boolean;
  chat_sessions?: number;
  last_chat_at?: string | null;
};

type ExtendedInfo = {
  goals: string[];
  health: string[];
  limitations: string[];
  motivation: string[];
  other: string[];
};

const LANG_LABELS: Record<string, string> = {
  de: "DE", en: "EN", tr: "TR", ar: "AR", fr: "FR", es: "ES", pl: "PL", ru: "RU",
};
const LANG_COLORS: Record<string, string> = {
  de: T.accent, en: T.info, tr: T.wariiang, ar: T.success, fr: "#E17055",
};
const DAY_LABELS_DE: Record<string, string> = {
  Mon: "Mo", Tue: "Di", Wed: "Mi", Thu: "Do", Fri: "Fr", Sat: "Sa", Sun: "So",
  Monday: "Mo", Tuesday: "Di", Wednesday: "Mi", Thursday: "Do", Friday: "Fr", Saturday: "Sa", Sunday: "So",
};

function formatDayDe(day: string) {
  return DAY_LABELS_DE[day] ?? day;
}

function LangBadge({ lang }: { lang?: string | null }) {
  if (!lang) return <span style={{ color: T.textDim, fontSize: 11 }}>-</span>;
  const label = LANG_LABELS[lang] ?? lang.toUpperCase().slice(0, 2);
  const color = LANG_COLORS[lang] ?? T.textDim;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 7px",
        borderRadius: 5,
        background: `${color}18`,
        color,
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: "0.06em",
        border: `1px solid ${color}30`,
      }}
    >
      {label}
    </span>
  );
}

function derivePrefAndAppointments(m: Member) {
  const stats = m.checkin_stats;
  const rb = m.recent_bookings;
  const upcoming = [...(rb?.upcoming ?? [])].sort((a, b) => Date.parse(a.start || "") - Date.parse(b.start || ""));
  const past = [...(rb?.past ?? [])].sort((a, b) => Date.parse(b.start || "") - Date.parse(a.start || ""));
  const all = [...upcoming, ...past];

  const next = stats?.next_appointment ?? upcoming[0];
  const last =
    stats?.last_appointment ??
    past[0] ??
    (stats?.last_visit
      ? { title: stats.top_category, status: stats.status, start: stats.last_visit, type: "checkin" }
      : undefined);

  const preferredSessions =
    stats?.preferred_training_sessions && stats.preferred_training_sessions.length > 0
      ? stats.preferred_training_sessions
      : (() => {
          const titles = Array.from(new Set(all.map((p) => (p.title || "").trim()).filter(Boolean)));
          if (titles.length > 0) return titles.slice(0, 3);
          return stats?.top_category ? [stats.top_category] : [];
        })();

  const preferredDays =
    stats?.preferred_training_days && stats.preferred_training_days.length > 0
      ? stats.preferred_training_days
      : (() => {
          const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
          const counts: Record<string, number> = {};
          for (const p of all) {
            if (!p.start) continue;
            const day = dayNames[new Date(p.start).getDay()];
            counts[day] = (counts[day] || 0) + 1;
          }
          return Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([d]) => d);
        })();

  const preferredTime =
    stats?.preferred_training_time ??
    (() => {
      const counts = { morning: 0, afternoon: 0, evening: 0 };
      for (const p of all) {
        if (!p.start) continue;
        const h = new Date(p.start).getHours();
        if (h < 12) counts.morning += 1;
        else if (h < 17) counts.afternoon += 1;
        else counts.evening += 1;
      }
      const total = counts.morning + counts.afternoon + counts.evening;
      if (total === 0) return undefined;
      return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
    })();

  return { next, last, preferredSessions, preferredDays, preferredTime };
}

function extractExtendedInfo(additionalInfo?: Record<string, string> | null): ExtendedInfo {
  const result: ExtendedInfo = { goals: [], health: [], limitations: [], motivation: [], other: [] };
  if (!additionalInfo) return result;
  for (const [rawKey, rawValue] of Object.entries(additionalInfo)) {
    const key = String(rawKey || "").toLowerCase();
    const value = String(rawValue || "").trim();
    if (!value) continue;
    const valueLc = value.toLowerCase();

    const keySuggestsGoal = key.includes("ziel") || key.includes("goal") || key.includes("objective") || key.includes("trainingsziele");
    const keySuggestsHealth = key.includes("gesund") || key.includes("health") || key.includes("medizin") || key.includes("medical") || key.includes("anamnese");
    const keySuggestsLimitation = key.includes("einschr") || key.includes("verletz") || key.includes("limitation") || key.includes("injur") || key.includes("hinweis");
    const keySuggestsMotivation = key.includes("motiv") || key.includes("why") || key.includes("reason");

    const valueSuggestsGoal = /(fit|stark|muskel|abnehmen|gewicht|aufbau|rück(en)? stärken|leist)/i.test(valueLc);
    const valueSuggestsHealth = /(schmerz|bandscheib|lws|hws|krank|anamnese|rücken|blutdruck|diabetes|op\b|verletz)/i.test(valueLc);
    const valueSuggestsLimitation = /(nicht|vorsicht|einschr|behutsam|problem|verletz|schonend|überlast)/i.test(valueLc);
    const valueSuggestsMotivation = /(motivier|spaß|dranbleiben|ziel|wunsch)/i.test(valueLc);

    if (keySuggestsGoal || valueSuggestsGoal) result.goals.push(value);
    if (keySuggestsHealth || valueSuggestsHealth) result.health.push(value);
    if (keySuggestsLimitation || valueSuggestsLimitation) result.limitations.push(value);
    if (keySuggestsMotivation || valueSuggestsMotivation) result.motivation.push(value);
    if (
      !(keySuggestsGoal || valueSuggestsGoal) &&
      !(keySuggestsHealth || valueSuggestsHealth) &&
      !(keySuggestsLimitation || valueSuggestsLimitation) &&
      !(keySuggestsMotivation || valueSuggestsMotivation)
    ) result.other.push(`${rawKey}: ${value}`);
  }
  return result;
}

function deriveRisk(m: Member): "low" | "medium" | "high" | null {
  const r = m.checkin_stats?.churn_prediction?.risk;
  return r === "low" || r === "medium" || r === "high" ? r : null;
}

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [filterLang, setFilterLang] = useState("all");
  const [filterVerified, setFilterVerified] = useState("all");
  const [filterMemberStatus, setFilterMemberStatus] = useState("all");
  const [filterChurnRisk, setFilterChurnRisk] = useState("all");
  const [filterAppointments, setFilterAppointments] = useState("all");
  const [expandedMemberIds, setExpandedMemberIds] = useState<Set<number>>(new Set());

  const fetchMembers = async (search = "") => {
    setIsLoading(true);
    try {
      const res = await apiFetch(`/admin/members?limit=500${search ? `&search=${encodeURIComponent(search)}` : ""}`);
      if (res.ok) setMembers(await res.json());
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMembers();
  }, []);

  const languageOptions = useMemo(
    () => Array.from(new Set(members.map((m) => (m.preferred_language || "").trim().toLowerCase()).filter(Boolean))).sort(),
    [members],
  );

  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      const lang = (m.preferred_language || "").trim().toLowerCase();
      const risk = deriveRisk(m);
      const derived = derivePrefAndAppointments(m);
      const hasAppointments = Boolean(derived.next || derived.last);

      if (filterLang !== "all" && lang !== filterLang) return false;
      if (filterVerified === "yes" && !m.verified) return false;
      if (filterVerified === "no" && m.verified) return false;
      if (filterMemberStatus === "active" && m.is_paused) return false;
      if (filterMemberStatus === "paused" && !m.is_paused) return false;
      if (filterChurnRisk !== "all" && risk !== filterChurnRisk) return false;
      if (filterAppointments === "yes" && !hasAppointments) return false;
      if (filterAppointments === "no" && hasAppointments) return false;
      return true;
    });
  }, [members, filterLang, filterVerified, filterMemberStatus, filterChurnRisk, filterAppointments]);

  const toggleExpanded = (customerId: number) => {
    setExpandedMemberIds((prev) => {
      const next = new Set(prev);
      if (next.has(customerId)) next.delete(customerId);
      else next.add(customerId);
      return next;
    });
  };

  const headers = ["Mitglied", "Aktivität", "Präferenzen", "Termine", "Retention", "Kontakt & Status"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <Card style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Search size={14} color={T.textDim} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") fetchMembers(query);
            }}
            placeholder="Suche: Name, E-Mail, Telefon, Mitgliedsnummer"
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 13, color: T.text }}
          />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
          <select value={filterLang} onChange={(e) => setFilterLang(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Sprache: Alle</option>
            {languageOptions.map((lang) => (
              <option key={lang} value={lang}>Sprache: {lang.toUpperCase()}</option>
            ))}
          </select>
          <select value={filterVerified} onChange={(e) => setFilterVerified(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Verifiziert: Alle</option>
            <option value="yes">Verifiziert: Ja</option>
            <option value="no">Verifiziert: Nein</option>
          </select>
          <select value={filterMemberStatus} onChange={(e) => setFilterMemberStatus(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Mitgliedsstatus: Alle</option>
            <option value="active">Mitgliedsstatus: Aktiv</option>
            <option value="paused">Mitgliedsstatus: Pausiert</option>
          </select>
          <select value={filterChurnRisk} onChange={(e) => setFilterChurnRisk(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Churn: Alle</option>
            <option value="low">Churn: Niedrig</option>
            <option value="medium">Churn: Mittel</option>
            <option value="high">Churn: Hoch</option>
          </select>
          <select value={filterAppointments} onChange={(e) => setFilterAppointments(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Termine: Alle</option>
            <option value="yes">Termine: Vorhanden</option>
            <option value="no">Termine: Keine</option>
          </select>
        </div>
        <div style={{ fontSize: 11, color: T.textDim }}>Ergebnis: {filteredMembers.length} / {members.length}</div>
      </Card>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: T.textMuted, fontSize: 13 }}>Laden...</div>
        ) : filteredMembers.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", background: T.successDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.success }}>
              <Users size={24} />
            </div>
            <p style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>Keine Mitglieder gefunden</p>
            <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>Starte einen Sync oder passe die Suche an.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: T.surfaceAlt }}>
                  {headers.map((h) => (
                    <th key={h} style={{ textAlign: "left", padding: "10px 16px", fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((m) => {
                  const extended = extractExtendedInfo(m.additional_info);
                  const stats = m.checkin_stats;
                  const derived = derivePrefAndAppointments(m);
                  const churn = stats?.churn_prediction;
                  const avg30 = stats?.avg_training_30d_per_week ?? stats?.avg_per_week;
                  const avg90 = stats?.avg_training_90d_per_week ?? stats?.avg_per_week;
                  const isExpanded = expandedMemberIds.has(m.customer_id);

                  return (
                    <Fragment key={m.customer_id}>
                      <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                        <td style={{ padding: "10px 16px", minWidth: 220, verticalAlign: "top" }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{m.first_name} {m.last_name}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{m.member_number ? `#${m.member_number}` : "Keine Mitgliedsnummer"}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Seit: {m.member_since ? new Date(m.member_since).toLocaleDateString("de-DE") : "-"}</div>
                          <div style={{ marginTop: 6 }}><LangBadge lang={m.preferred_language} /></div>
                          <button type="button" onClick={() => toggleExpanded(m.customer_id)} style={{ marginTop: 8, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: T.accent, background: "transparent", border: "none", padding: 0, cursor: "pointer" }}>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />} Details
                          </button>
                        </td>

                        <td style={{ padding: "10px 16px", minWidth: 220, verticalAlign: "top" }}>
                          {stats ? (
                            <>
                              <div style={{ fontSize: 11, color: T.textMuted }}>30d: {stats.total_30d ?? 0} · 90d: {stats.total_90d ?? 0}</div>
                              <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>Ø/Woche 30d: {avg30 ?? "-"} · 90d: {avg90 ?? "-"}</div>
                              <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Letzte Aktivität: {stats.last_visit || "-"} · Quelle: {stats.source || "-"}</div>
                            </>
                          ) : <span style={{ fontSize: 11, color: T.textDim }}>Keine Aktivitätsdaten</span>}
                        </td>

                        <td style={{ padding: "10px 16px", minWidth: 220, verticalAlign: "top" }}>
                          <div style={{ fontSize: 11, color: T.textMuted }}>Sessions: {derived.preferredSessions.join(", ") || "-"}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Tage: {derived.preferredDays.map(formatDayDe).join(", ") || "-"}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Tageszeit: {derived.preferredTime || "-"}</div>
                        </td>

                        <td style={{ padding: "10px 16px", minWidth: 220, verticalAlign: "top" }}>
                          <div style={{ fontSize: 11, color: T.textMuted }}>Nächster Termin: {derived.next?.start ? new Date(derived.next.start).toLocaleString("de-DE") : "-"}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{derived.next?.title || "-"} · {derived.next?.status || "-"}</div>
                          <div style={{ fontSize: 11, color: T.textMuted, marginTop: 6 }}>Letzter Termin: {derived.last?.start ? new Date(derived.last.start).toLocaleString("de-DE") : "-"}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{derived.last?.title || "-"} · {derived.last?.status || "-"}</div>
                        </td>

                        <td style={{ padding: "10px 16px", minWidth: 180, verticalAlign: "top" }}>
                          {churn?.risk === "high" ? <Badge variant="danger" size="xs">Churn Hoch ({churn.score ?? 0})</Badge> : churn?.risk === "medium" ? <Badge variant="wariiang" size="xs">Churn Mittel ({churn.score ?? 0})</Badge> : <Badge variant="success" size="xs">Churn Niedrig ({churn?.score ?? 0})</Badge>}
                          <div style={{ marginTop: 6 }}>{m.verified ? <Badge variant="success" size="xs">Ja ({m.chat_sessions ?? 0})</Badge> : <Badge variant="wariiang" size="xs">Nein</Badge>}</div>
                          {!!churn?.reasons?.length && <div style={{ fontSize: 11, color: T.textDim, marginTop: 6 }}>Gründe: {churn.reasons.slice(0, 2).join(", ")}</div>}
                        </td>

                        <td style={{ padding: "10px 16px", minWidth: 240, verticalAlign: "top" }}>
                          <div style={{ fontSize: 12, color: T.textMuted, whiteSpace: "nowrap" }}>{m.phone_number || "-"}</div>
                          <div style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>{m.email || "-"}</div>
                          <div style={{ marginTop: 6 }}>{m.is_paused ? <Badge variant="wariiang" size="xs">Pausiert</Badge> : <Badge variant="success" size="xs">Aktiv</Badge>}</div>
                          {m.is_paused && (
                            <>
                              <div style={{ fontSize: 11, color: T.textDim, marginTop: 6 }}>Pause bis: {m.pause_info?.pause_until ? new Date(m.pause_info.pause_until).toLocaleDateString("de-DE") : "Offen"}</div>
                              <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Grund: {m.pause_info?.pause_reason || "-"}</div>
                            </>
                          )}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                          <td colSpan={6} style={{ padding: "12px 16px", background: T.surfaceAlt }}>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
                              <div><div style={{ fontSize: 11, color: T.textDim }}>Ziele</div><div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{extended.goals.join(" · ") || "-"}</div></div>
                              <div><div style={{ fontSize: 11, color: T.textDim }}>Gesundheit</div><div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{extended.health.join(" · ") || "-"}</div></div>
                              <div><div style={{ fontSize: 11, color: T.textDim }}>Einschränkungen</div><div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{extended.limitations.join(" · ") || "-"}</div></div>
                              <div><div style={{ fontSize: 11, color: T.textDim }}>Motivation</div><div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{extended.motivation.join(" · ") || "-"}</div></div>
                              <div>
                                <div style={{ fontSize: 11, color: T.textDim }}>Pause-Historie (180 Tage)</div>
                                <div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>
                                  {m.pause_info?.paused_days_180 ?? 0} Tage
                                  {m.pause_info?.last_pause_end ? ` · Letztes Ende: ${new Date(m.pause_info.last_pause_end).toLocaleDateString("de-DE")}` : ""}
                                  {m.pause_info?.last_pause_reason ? ` · Grund: ${m.pause_info.last_pause_reason}` : ""}
                                </div>
                              </div>
                              <div><div style={{ fontSize: 11, color: T.textDim }}>Weitere Infos</div><div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{extended.other.join(" · ") || "-"}</div></div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
