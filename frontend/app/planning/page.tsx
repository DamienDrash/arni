"use client";

import React, { useState, useEffect, CSSProperties, useMemo } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import {
  Calendar as CalendarIcon, ChevronLeft, ChevronRight, Clock,
  Mail, MessageSquare, Smartphone, Send, Globe, Eye,
  Plus, Filter, Layers, BarChart3, Zap, FlaskConical,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface CalendarCampaign {
  id: number;
  name: string;
  channel: string;
  status: string;
  type: string;
  scheduled_at: string | null;
  created_at: string;
  is_ab_test?: boolean;
}

interface AutomationItem {
  id: number;
  name: string;
  trigger_type: string;
  is_active: boolean;
  created_at: string;
}

type ViewMode = "month" | "week" | "list";

/* ═══════════════════════════════════════════════════════════════════════════
   Styles
   ═══════════════════════════════════════════════════════════════════════ */

const S: Record<string, any> = {
  page: {
    minHeight: "100vh",
    background: T.bg,
    padding: "32px 40px",
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 28,
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 4,
  },
  title: {
    fontSize: 26,
    fontWeight: 800,
    color: T.text,
    letterSpacing: "-0.02em",
    margin: 0,
  },
  subtitle: {
    fontSize: 14,
    color: T.textMuted,
    margin: 0,
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  viewToggle: {
    display: "flex",
    borderRadius: 10,
    overflow: "hidden",
    border: `1px solid ${T.border}`,
  },
  viewBtn: (active: boolean): CSSProperties => ({
    padding: "8px 16px",
    border: "none",
    background: active ? T.accent : T.surface,
    color: active ? "#fff" : T.textMuted,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    transition: "all 0.15s",
  }),
  addBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "9px 18px",
    borderRadius: 10,
    border: "none",
    background: T.accent,
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
  },
  statsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 16,
    marginBottom: 24,
  },
  statCard: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: "18px 20px",
    display: "flex",
    alignItems: "center",
    gap: 14,
  },
  statIcon: (color: string): CSSProperties => ({
    width: 42,
    height: 42,
    borderRadius: 10,
    background: `${color}15`,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  }),
  statValue: {
    fontSize: 22,
    fontWeight: 800,
    color: T.text,
    lineHeight: 1,
  },
  statLabel: {
    fontSize: 12,
    color: T.textMuted,
    marginTop: 2,
  },
  calendarNav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  navBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: 36,
    height: 36,
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    background: T.surface,
    color: T.textMuted,
    cursor: "pointer",
  },
  monthTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: T.text,
  },
  todayBtn: {
    padding: "6px 14px",
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    background: T.surface,
    color: T.textMuted,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  calendarGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(7, 1fr)",
    gap: 1,
    background: T.border,
    borderRadius: 12,
    overflow: "hidden",
    border: `1px solid ${T.border}`,
  },
  dayHeader: {
    padding: "10px 0",
    textAlign: "center" as const,
    fontSize: 11,
    fontWeight: 700,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    background: T.surface,
  },
  dayCell: (isToday: boolean, isCurrentMonth: boolean): CSSProperties => ({
    minHeight: 100,
    padding: 6,
    background: isToday ? `${T.accent}10` : T.surface,
    opacity: isCurrentMonth ? 1 : 0.4,
    position: "relative" as const,
    cursor: "pointer",
    transition: "background 0.15s",
  }),
  dayNumber: (isToday: boolean): CSSProperties => ({
    fontSize: 12,
    fontWeight: isToday ? 800 : 500,
    color: isToday ? T.accent : T.textMuted,
    marginBottom: 4,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: isToday ? 24 : "auto",
    height: isToday ? 24 : "auto",
    borderRadius: "50%",
    background: isToday ? T.accentDim : "transparent",
  }),
  eventPill: (color: string): CSSProperties => ({
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "2px 6px",
    borderRadius: 4,
    background: `${color}20`,
    color: color,
    fontSize: 10,
    fontWeight: 600,
    marginBottom: 2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
    cursor: "pointer",
  }),
  listContainer: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    overflow: "hidden",
  },
  listHeader: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
    padding: "12px 20px",
    borderBottom: `1px solid ${T.border}`,
    background: T.surfaceAlt,
  },
  listHeaderCell: {
    fontSize: 11,
    fontWeight: 700,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  listRow: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr",
    padding: "14px 20px",
    borderBottom: `1px solid ${T.border}`,
    alignItems: "center",
    transition: "background 0.1s",
    cursor: "pointer",
  },
  listCell: {
    fontSize: 13,
    color: T.text,
  },
  statusBadge: (status: string): CSSProperties => {
    const colors: Record<string, { bg: string; fg: string }> = {
      draft: { bg: T.warningDim, fg: T.warning },
      scheduled: { bg: T.infoDim, fg: T.info },
      sending: { bg: T.accentDim, fg: T.accentLight },
      sent: { bg: T.successDim, fg: T.success },
      paused: { bg: `${T.textDim}20`, fg: T.textDim },
    };
    const c = colors[status] || colors.draft;
    return {
      display: "inline-flex",
      alignItems: "center",
      gap: 4,
      padding: "3px 10px",
      borderRadius: 6,
      background: c.bg,
      color: c.fg,
      fontSize: 11,
      fontWeight: 600,
    };
  },
  channelIcon: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    fontSize: 13,
    color: T.text,
  },
  weekGrid: {
    display: "grid",
    gridTemplateColumns: "60px repeat(7, 1fr)",
    gap: 1,
    background: T.border,
    borderRadius: 12,
    overflow: "hidden",
    border: `1px solid ${T.border}`,
  },
  weekTimeLabel: {
    padding: "8px 4px",
    textAlign: "center" as const,
    fontSize: 10,
    color: T.textDim,
    background: T.surface,
  },
  weekCell: {
    minHeight: 48,
    padding: 4,
    background: T.surface,
    position: "relative" as const,
  },
  sidebar: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 20,
  },
  sidebarTitle: {
    fontSize: 14,
    fontWeight: 700,
    color: T.text,
    marginBottom: 14,
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  automationItem: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 12px",
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    marginBottom: 8,
    background: T.bg,
  },
  automationDot: (active: boolean): CSSProperties => ({
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: active ? T.success : T.textDim,
    flexShrink: 0,
  }),
  filterRow: {
    display: "flex",
    gap: 8,
    marginBottom: 20,
  },
  filterChip: (active: boolean): CSSProperties => ({
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "6px 12px",
    borderRadius: 8,
    border: `1px solid ${active ? T.accent : T.border}`,
    background: active ? T.accentDim : T.surface,
    color: active ? T.accentLight : T.textMuted,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  }),
};

/* ═══════════════════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════════════ */

const CHANNEL_MAP: Record<string, { icon: typeof Mail; color: string; label: string }> = {
  email: { icon: Mail, color: T.email, label: "E-Mail" },
  whatsapp: { icon: MessageSquare, color: T.whatsapp, label: "WhatsApp" },
  sms: { icon: Smartphone, color: T.warning, label: "SMS" },
  telegram: { icon: Send, color: T.telegram, label: "Telegram" },
  multi: { icon: Globe, color: T.accentLight, label: "Multi" },
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Entwurf",
  scheduled: "Geplant",
  sending: "Wird gesendet",
  sent: "Gesendet",
  paused: "Pausiert",
};

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"];

function getDaysInMonth(year: number, month: number): Date[] {
  const days: Date[] = [];
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  // Fill from Monday before first day
  let start = new Date(firstDay);
  const dayOfWeek = start.getDay() === 0 ? 6 : start.getDay() - 1; // Monday=0
  start.setDate(start.getDate() - dayOfWeek);

  // Fill 42 cells (6 weeks)
  for (let i = 0; i < 42; i++) {
    days.push(new Date(start));
    start.setDate(start.getDate() + 1);
  }
  return days;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function getWeekDays(date: Date): Date[] {
  const days: Date[] = [];
  const d = new Date(date);
  const dayOfWeek = d.getDay() === 0 ? 6 : d.getDay() - 1;
  d.setDate(d.getDate() - dayOfWeek);
  for (let i = 0; i < 7; i++) {
    days.push(new Date(d));
    d.setDate(d.getDate() + 1);
  }
  return days;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════════════════ */

export default function PlanningPage() {
  const [view, setView] = useState<ViewMode>("month");
  const [currentDate, setCurrentDate] = useState(new Date());
  const [campaigns, setCampaigns] = useState<CalendarCampaign[]>([]);
  const [automations, setAutomations] = useState<AutomationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterChannel, setFilterChannel] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);

  const today = new Date();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [campRes, autoRes] = await Promise.all([
        apiFetch("/v2/admin/campaigns/calendar").catch(() => null),
        apiFetch("/admin/automations").catch(() => null),
      ]);
      if (campRes?.ok) setCampaigns(await campRes.json());
      if (autoRes?.ok) {
        const data = await autoRes.json();
        setAutomations(Array.isArray(data) ? data : data.items || []);
      }
    } catch {}
    setLoading(false);
  };

  /* ─── Filtered Campaigns ──────────────────────────────────────────── */

  const filtered = useMemo(() => {
    let result = campaigns;
    if (filterChannel) result = result.filter((c) => c.channel === filterChannel);
    if (filterStatus) result = result.filter((c) => c.status === filterStatus);
    return result;
  }, [campaigns, filterChannel, filterStatus]);

  /* ─── Stats ───────────────────────────────────────────────────────── */

  const stats = useMemo(() => {
    const scheduled = campaigns.filter((c) => c.status === "scheduled").length;
    const sent = campaigns.filter((c) => c.status === "sent").length;
    const draft = campaigns.filter((c) => c.status === "draft").length;
    const activeAuto = automations.filter((a) => a.is_active).length;
    return { scheduled, sent, draft, activeAuto };
  }, [campaigns, automations]);

  /* ─── Calendar Days ───────────────────────────────────────────────── */

  const calendarDays = useMemo(
    () => getDaysInMonth(currentDate.getFullYear(), currentDate.getMonth()),
    [currentDate]
  );

  const weekDays = useMemo(() => getWeekDays(currentDate), [currentDate]);

  const getCampaignsForDay = (date: Date) =>
    filtered.filter((c) => {
      const d = c.scheduled_at ? new Date(c.scheduled_at) : new Date(c.created_at);
      return isSameDay(d, date);
    });

  /* ─── Navigation ──────────────────────────────────────────────────── */

  const navigate = (dir: number) => {
    const d = new Date(currentDate);
    if (view === "month") d.setMonth(d.getMonth() + dir);
    else if (view === "week") d.setDate(d.getDate() + dir * 7);
    setCurrentDate(d);
  };

  const goToday = () => setCurrentDate(new Date());

  /* ─── Render ──────────────────────────────────────────────────────── */

  const renderChannelIcon = (channel: string, size = 14) => {
    const ch = CHANNEL_MAP[channel] || CHANNEL_MAP.email;
    const Icon = ch.icon;
    return <Icon size={size} color={ch.color} />;
  };

  const renderMonthView = () => (
    <div style={S.calendarGrid}>
      {WEEKDAYS.map((d) => (
        <div key={d} style={S.dayHeader}>{d}</div>
      ))}
      {calendarDays.map((day, idx) => {
        const isCurrentMonth = day.getMonth() === currentDate.getMonth();
        const isToday_ = isSameDay(day, today);
        const dayCampaigns = getCampaignsForDay(day);

        return (
          <div key={idx} style={S.dayCell(isToday_, isCurrentMonth)}>
            <div style={S.dayNumber(isToday_)}>{day.getDate()}</div>
            {dayCampaigns.slice(0, 3).map((c) => {
              const ch = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
              return (
                <div key={c.id} style={S.eventPill(ch.color)} title={c.name}>
                  {renderChannelIcon(c.channel, 10)}
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</span>
                </div>
              );
            })}
            {dayCampaigns.length > 3 && (
              <div style={{ fontSize: 10, color: T.textDim, paddingLeft: 4 }}>
                +{dayCampaigns.length - 3} weitere
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  const renderWeekView = () => {
    const hours = Array.from({ length: 12 }, (_, i) => i + 8); // 08:00 - 19:00
    return (
      <div style={S.weekGrid}>
        {/* Header */}
        <div style={{ ...S.dayHeader, borderBottom: `1px solid ${T.border}` }}>&nbsp;</div>
        {weekDays.map((d, i) => (
          <div key={i} style={{ ...S.dayHeader, borderBottom: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 11, color: T.textMuted }}>{WEEKDAYS[i]}</div>
            <div style={{
              fontSize: 16, fontWeight: isSameDay(d, today) ? 800 : 500,
              color: isSameDay(d, today) ? T.accent : T.text,
            }}>
              {d.getDate()}
            </div>
          </div>
        ))}
        {/* Time Slots */}
        {hours.map((h) => (
          <React.Fragment key={h}>
            <div style={S.weekTimeLabel}>{`${h}:00`}</div>
            {weekDays.map((d, di) => {
              const dayCampaigns = getCampaignsForDay(d).filter((c) => {
                const cDate = c.scheduled_at ? new Date(c.scheduled_at) : new Date(c.created_at);
                return cDate.getHours() === h;
              });
              return (
                <div key={di} style={S.weekCell}>
                  {dayCampaigns.map((c) => {
                    const ch = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
                    return (
                      <div key={c.id} style={S.eventPill(ch.color)} title={c.name}>
                        {renderChannelIcon(c.channel, 10)}
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{c.name}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
    );
  };

  const renderListView = () => (
    <div style={S.listContainer}>
      <div style={S.listHeader}>
        <span style={S.listHeaderCell}>Kampagne</span>
        <span style={S.listHeaderCell}>Kanal</span>
        <span style={S.listHeaderCell}>Status</span>
        <span style={S.listHeaderCell}>Typ</span>
        <span style={S.listHeaderCell}>Geplant für</span>
      </div>
      {filtered.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: T.textMuted, fontSize: 14 }}>
          Keine Kampagnen gefunden
        </div>
      ) : (
        filtered
          .sort((a, b) => {
            const da = a.scheduled_at || a.created_at;
            const db = b.scheduled_at || b.created_at;
            return new Date(db).getTime() - new Date(da).getTime();
          })
          .map((c) => {
            const ch = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
            const Icon = ch.icon;
            return (
              <div
                key={c.id}
                style={S.listRow}
                onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <span style={{ ...S.listCell, fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                  {c.name}
                  {c.is_ab_test && (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: "2px 6px", borderRadius: 4, background: T.accentDim, color: T.accentLight, fontSize: 10, fontWeight: 700 }}>
                      <FlaskConical size={10} /> A/B
                    </span>
                  )}
                </span>
                <span style={S.channelIcon}>
                  <Icon size={14} color={ch.color} /> {ch.label}
                </span>
                <span>
                  <span style={S.statusBadge(c.status)}>
                    {STATUS_LABELS[c.status] || c.status}
                  </span>
                </span>
                <span style={{ ...S.listCell, color: T.textMuted }}>
                  {c.type === "broadcast" ? "Broadcast" : c.type === "triggered" ? "Trigger" : c.type}
                </span>
                <span style={{ ...S.listCell, color: T.textMuted, fontSize: 12 }}>
                  {c.scheduled_at
                    ? new Date(c.scheduled_at).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })
                    : "—"}
                </span>
              </div>
            );
          })
      )}
    </div>
  );

  /* ─── Main Layout ─────────────────────────────────────────────────── */

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <h1 style={S.title}>Planung & Kalender</h1>
          <p style={S.subtitle}>Übersicht aller geplanten Kampagnen und aktiven Automations</p>
        </div>
        <div style={S.headerRight}>
          <div style={S.viewToggle}>
            {(["month", "week", "list"] as ViewMode[]).map((v) => (
              <button key={v} style={S.viewBtn(view === v)} onClick={() => setView(v)}>
                {v === "month" ? "Monat" : v === "week" ? "Woche" : "Liste"}
              </button>
            ))}
          </div>
          <a href="/campaigns" style={{ ...S.addBtn, textDecoration: "none" }}>
            <Plus size={14} /> Neue Kampagne
          </a>
        </div>
      </div>

      {/* Stats */}
      <div style={S.statsRow}>
        <div style={S.statCard}>
          <div style={S.statIcon(T.info)}>
            <Clock size={20} color={T.info} />
          </div>
          <div>
            <div style={S.statValue}>{stats.scheduled}</div>
            <div style={S.statLabel}>Geplant</div>
          </div>
        </div>
        <div style={S.statCard}>
          <div style={S.statIcon(T.success)}>
            <Mail size={20} color={T.success} />
          </div>
          <div>
            <div style={S.statValue}>{stats.sent}</div>
            <div style={S.statLabel}>Gesendet</div>
          </div>
        </div>
        <div style={S.statCard}>
          <div style={S.statIcon(T.warning)}>
            <Layers size={20} color={T.warning} />
          </div>
          <div>
            <div style={S.statValue}>{stats.draft}</div>
            <div style={S.statLabel}>Entwürfe</div>
          </div>
        </div>
        <div style={S.statCard}>
          <div style={S.statIcon(T.accent)}>
            <Zap size={20} color={T.accent} />
          </div>
          <div>
            <div style={S.statValue}>{stats.activeAuto}</div>
            <div style={S.statLabel}>Aktive Automations</div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div style={S.filterRow}>
        <button
          style={S.filterChip(!filterChannel && !filterStatus)}
          onClick={() => { setFilterChannel(null); setFilterStatus(null); }}
        >
          Alle
        </button>
        {Object.entries(CHANNEL_MAP).map(([key, val]) => (
          <button
            key={key}
            style={S.filterChip(filterChannel === key)}
            onClick={() => setFilterChannel(filterChannel === key ? null : key)}
          >
            <val.icon size={12} /> {val.label}
          </button>
        ))}
        <div style={{ width: 1, background: T.border, margin: "0 4px" }} />
        {Object.entries(STATUS_LABELS).map(([key, label]) => (
          <button
            key={key}
            style={S.filterChip(filterStatus === key)}
            onClick={() => setFilterStatus(filterStatus === key ? null : key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 20 }}>
        <div>
          {/* Calendar Navigation */}
          {(view === "month" || view === "week") && (
            <div style={S.calendarNav}>
              <button style={S.navBtn} onClick={() => navigate(-1)}>
                <ChevronLeft size={16} />
              </button>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span style={S.monthTitle}>
                  {view === "month"
                    ? `${MONTHS[currentDate.getMonth()]} ${currentDate.getFullYear()}`
                    : `KW ${Math.ceil((currentDate.getDate() - currentDate.getDay() + 7) / 7)} – ${MONTHS[currentDate.getMonth()]} ${currentDate.getFullYear()}`}
                </span>
                <button style={S.todayBtn} onClick={goToday}>Heute</button>
              </div>
              <button style={S.navBtn} onClick={() => navigate(1)}>
                <ChevronRight size={16} />
              </button>
            </div>
          )}

          {/* View Content */}
          {loading ? (
            <div style={{ padding: 60, textAlign: "center", color: T.textMuted }}>
              Lade Planungsdaten...
            </div>
          ) : view === "month" ? (
            renderMonthView()
          ) : view === "week" ? (
            renderWeekView()
          ) : (
            renderListView()
          )}
        </div>

        {/* Sidebar */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Active Automations */}
          <div style={S.sidebar}>
            <div style={S.sidebarTitle}>
              <Zap size={16} color={T.accent} /> Aktive Automations
            </div>
            {automations.filter((a) => a.is_active).length === 0 ? (
              <div style={{ fontSize: 13, color: T.textDim, padding: "8px 0" }}>
                Keine aktiven Automations
              </div>
            ) : (
              automations
                .filter((a) => a.is_active)
                .slice(0, 8)
                .map((a) => (
                  <div key={a.id} style={S.automationItem}>
                    <div style={S.automationDot(a.is_active)} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {a.name}
                      </div>
                      <div style={{ fontSize: 11, color: T.textDim }}>
                        {a.trigger_type === "segment_enter" ? "Segment-Eintritt" : a.trigger_type === "segment_exit" ? "Segment-Austritt" : a.trigger_type}
                      </div>
                    </div>
                  </div>
                ))
            )}
          </div>

          {/* Upcoming Campaigns */}
          <div style={S.sidebar}>
            <div style={S.sidebarTitle}>
              <CalendarIcon size={16} color={T.info} /> Nächste Kampagnen
            </div>
            {campaigns
              .filter((c) => c.status === "scheduled" && c.scheduled_at)
              .sort((a, b) => new Date(a.scheduled_at!).getTime() - new Date(b.scheduled_at!).getTime())
              .slice(0, 5)
              .map((c) => {
                const ch = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
                return (
                  <div key={c.id} style={S.automationItem}>
                    {renderChannelIcon(c.channel, 14)}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: 11, color: T.textDim }}>
                        {new Date(c.scheduled_at!).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>
                  </div>
                );
              })}
            {campaigns.filter((c) => c.status === "scheduled").length === 0 && (
              <div style={{ fontSize: 13, color: T.textDim, padding: "8px 0" }}>
                Keine geplanten Kampagnen
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
