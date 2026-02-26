"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ShieldCheck, Search, Download, X, Calendar, Filter,
  User, Activity, Tag, Layers, Clock, Eye, Info,
  ChevronLeft, ChevronRight, BarChart3, FileText, AlertTriangle,
  CheckCircle2, RefreshCw,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/LanguageContext";

/* ── Types ──────────────────────────────────────────────────────────── */
type AuditRow = {
  id: number;
  created_at: string | null;
  actor_email: string | null;
  actor_user_id: number | null;
  action: string;
  category: string;
  target_type: string | null;
  target_id: string | null;
  details: Record<string, unknown> | null;
};

/* ── Styles (Gold-Standard Dark Theme) ──────────────────────────────── */
const statCard: React.CSSProperties = {
  padding: "20px 24px",
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
};
const statIcon = (color: string): React.CSSProperties => ({
  width: 44, height: 44, borderRadius: 12,
  background: `${color}15`,
  display: "flex", alignItems: "center", justifyContent: "center",
  color, flexShrink: 0,
});
const statLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4,
};
const statValue = (color?: string): React.CSSProperties => ({
  fontSize: 24, fontWeight: 800, color: color || T.text, letterSpacing: "-0.02em",
});
const inputBase: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  transition: "border-color 0.2s ease",
};
const filterLabel: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 6,
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6,
};
const selectBase: React.CSSProperties = {
  ...inputBase,
  appearance: "none" as const,
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%235A5C6B' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E")`,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 12px center",
  paddingRight: 36,
  cursor: "pointer",
};
const btnPrimary: React.CSSProperties = {
  border: "none", borderRadius: 10, background: T.accent, color: "#fff",
  padding: "10px 20px", fontSize: 13, fontWeight: 700,
  cursor: "pointer", display: "flex", alignItems: "center", gap: 8,
  transition: "opacity 0.2s", letterSpacing: "0.01em",
};
const btnGhost: React.CSSProperties = {
  border: `1px solid ${T.border}`, borderRadius: 10, background: "transparent",
  color: T.textMuted, padding: "10px 16px", fontSize: 13, fontWeight: 600,
  cursor: "pointer", display: "flex", alignItems: "center", gap: 8,
  transition: "all 0.2s",
};
const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "14px 16px", fontSize: 10, fontWeight: 800,
  color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em",
  borderBottom: `1px solid ${T.border}`, background: T.surfaceAlt,
};
const tdStyle: React.CSSProperties = {
  padding: "14px 16px", borderBottom: `1px solid ${T.border}`,
};
const chipActive: React.CSSProperties = {
  padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700,
  background: T.accentDim, color: T.accent, border: `1px solid ${T.accent}40`,
  cursor: "pointer", transition: "all 0.2s",
};
const chipInactive: React.CSSProperties = {
  padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
  background: T.surfaceAlt, color: T.textMuted, border: `1px solid ${T.border}`,
  cursor: "pointer", transition: "all 0.2s",
};
const modalField: React.CSSProperties = {
  padding: 16, borderRadius: 12, background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
};
const modalLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6, display: "block",
};

const PAGE_SIZE = 50;

/* ── Component ──────────────────────────────────────────────────────── */
export default function AuditPage() {
  const { t } = useI18n();
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [actorFilter, setActorFilter] = useState("all");
  const [targetTypeFilter, setTargetTypeFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [selectedRow, setSelectedRow] = useState<AuditRow | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [quickFilter, setQuickFilter] = useState<"all" | "security" | "data" | "config">("all");

  /* ── Fetch ── */
  const fetchAudit = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch(`/admin/audit?limit=500&offset=0`);
      if (!res.ok) throw new Error(`Audit load failed (${res.status})`);
      const data = await res.json();
      setRows(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAudit(); }, [fetchAudit]);

  /* ── Derived filter options ── */
  const options = useMemo(() => ({
    categories: Array.from(new Set(rows.map(r => r.category).filter(Boolean))).sort() as string[],
    actions: Array.from(new Set(rows.map(r => r.action).filter(Boolean))).sort() as string[],
    actors: Array.from(new Set(rows.map(r => r.actor_email).filter(Boolean))).sort() as string[],
    targetTypes: Array.from(new Set(rows.map(r => r.target_type).filter(Boolean))).sort() as string[],
  }), [rows]);

  /* ── Filtered + sorted ── */
  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      // Quick filter
      if (quickFilter === "security" && !["auth", "security", "access"].some(k => r.category.toLowerCase().includes(k))) return false;
      if (quickFilter === "data" && !["data", "knowledge", "member", "import", "sync"].some(k => r.category.toLowerCase().includes(k))) return false;
      if (quickFilter === "config" && !["settings", "config", "plan", "billing", "tenant"].some(k => r.category.toLowerCase().includes(k))) return false;

      if (categoryFilter !== "all" && r.category !== categoryFilter) return false;
      if (actionFilter !== "all" && r.action !== actionFilter) return false;
      if (actorFilter !== "all" && (r.actor_email || "system") !== actorFilter) return false;
      if (targetTypeFilter !== "all" && (r.target_type || "") !== targetTypeFilter) return false;

      if (startDate && r.created_at && new Date(r.created_at) < new Date(startDate)) return false;
      if (endDate && r.created_at) {
        const end = new Date(endDate);
        end.setDate(end.getDate() + 1);
        if (new Date(r.created_at) >= end) return false;
      }

      if (!q) return true;
      return (
        (r.actor_email || "").toLowerCase().includes(q) ||
        r.action.toLowerCase().includes(q) ||
        r.category.toLowerCase().includes(q) ||
        (r.target_type || "").toLowerCase().includes(q) ||
        (r.target_id || "").toLowerCase().includes(q) ||
        JSON.stringify(r.details || {}).toLowerCase().includes(q)
      );
    }).sort((a, b) => {
      const at = Date.parse(a.created_at || "");
      const bt = Date.parse(b.created_at || "");
      return sortDir === "desc" ? bt - at : at - bt;
    });
  }, [rows, query, categoryFilter, actionFilter, actorFilter, targetTypeFilter, startDate, endDate, sortDir, quickFilter]);

  /* ── Pagination ── */
  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));
  const pagedRows = filteredRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  useEffect(() => { setPage(0); }, [query, categoryFilter, actionFilter, actorFilter, targetTypeFilter, startDate, endDate, quickFilter]);

  /* ── Stats ── */
  const stats = useMemo(() => {
    const now = new Date();
    const h24 = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const d7 = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const last24h = rows.filter(r => r.created_at && new Date(r.created_at) >= h24).length;
    const last7d = rows.filter(r => r.created_at && new Date(r.created_at) >= d7).length;
    const uniqueActors = new Set(rows.map(r => r.actor_email).filter(Boolean)).size;
    const securityEvents = rows.filter(r => ["auth", "security", "access"].some(k => r.category.toLowerCase().includes(k))).length;
    return { total: rows.length, last24h, last7d, uniqueActors, securityEvents };
  }, [rows]);

  /* ── CSV Export ── */
  function downloadCsv() {
    const header = ["Timestamp", "Actor", "Action", "Category", "Target Type", "Target ID", "Details"];
    const lines = filteredRows.map((r) =>
      [r.created_at, r.actor_email, r.action, r.category, r.target_type, r.target_id, JSON.stringify(r.details || {})]
        .map(v => `"${String(v || "").replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ariia-audit-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  /* ── Clear all filters ── */
  function clearFilters() {
    setCategoryFilter("all");
    setActionFilter("all");
    setActorFilter("all");
    setTargetTypeFilter("all");
    setStartDate("");
    setEndDate("");
    setQuery("");
    setQuickFilter("all");
  }

  const hasActiveFilters = categoryFilter !== "all" || actionFilter !== "all" || actorFilter !== "all" || targetTypeFilter !== "all" || startDate || endDate || query || quickFilter !== "all";

  /* ── Render ── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <SectionHeader
        title={t("audit.title")}
        subtitle={t("audit.subtitle")}
        action={
          <div style={{ display: "flex", gap: 10 }}>
            <button style={btnGhost} onClick={fetchAudit} title="Refresh">
              <RefreshCw size={14} /> {t("audit.refresh") || "Aktualisieren"}
            </button>
            <button style={btnPrimary} onClick={downloadCsv}>
              <Download size={14} /> {t("audit.filters.exportCsv")}
            </button>
          </div>
        }
      />

      {/* Stat Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Gesamt-Einträge</div>
            <div style={statValue()}>{stats.total.toLocaleString("de")}</div>
          </div>
          <div style={statIcon(T.accent)}><FileText size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Letzte 24h</div>
            <div style={statValue(T.success)}>{stats.last24h.toLocaleString("de")}</div>
          </div>
          <div style={statIcon(T.success)}><Clock size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Letzte 7 Tage</div>
            <div style={statValue(T.info)}>{stats.last7d.toLocaleString("de")}</div>
          </div>
          <div style={statIcon(T.info)}><BarChart3 size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Akteure</div>
            <div style={statValue(T.warning)}>{stats.uniqueActors}</div>
          </div>
          <div style={statIcon(T.warning)}><User size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Security Events</div>
            <div style={statValue(T.danger)}>{stats.securityEvents}</div>
          </div>
          <div style={statIcon(T.danger)}><AlertTriangle size={20} /></div>
        </Card>
      </div>

      {/* Quick Filters + Search */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {/* Quick filter chips */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {(["all", "security", "data", "config"] as const).map((f) => (
            <button
              key={f}
              style={quickFilter === f ? chipActive : chipInactive}
              onClick={() => setQuickFilter(f)}
            >
              {f === "all" && "Alle Ereignisse"}
              {f === "security" && <><ShieldCheck size={13} /> Security & Auth</>}
              {f === "data" && <><Layers size={13} /> Daten & Sync</>}
              {f === "config" && <><Activity size={13} /> Konfiguration</>}
            </button>
          ))}
        </div>

        {/* Search + Sort + Filters */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 260, position: "relative" }}>
            <Search size={16} color={T.textDim} style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }} />
            <input
              style={{ ...inputBase, paddingLeft: 42, height: 44 }}
              placeholder={t("audit.search")}
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
          <button
            style={{ ...btnGhost, height: 44 }}
            onClick={() => setSortDir(s => s === "desc" ? "asc" : "desc")}
          >
            <Clock size={14} /> {sortDir === "desc" ? t("audit.sort.newest") : t("audit.sort.oldest")}
          </button>
          {hasActiveFilters && (
            <button style={{ ...btnGhost, height: 44, color: T.danger, borderColor: `${T.danger}40` }} onClick={clearFilters}>
              <X size={14} /> {t("audit.filters.clearFilters")}
            </button>
          )}
        </div>

        {/* Advanced Filters */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
          <div>
            <label style={filterLabel}><Tag size={11} /> {t("audit.filters.category")}</label>
            <select style={selectBase} value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
              <option value="all">{t("audit.filters.allCategories")}</option>
              {options.categories.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label style={filterLabel}><Activity size={11} /> {t("audit.filters.actionType")}</label>
            <select style={selectBase} value={actionFilter} onChange={e => setActionFilter(e.target.value)}>
              <option value="all">{t("audit.filters.allActions")}</option>
              {options.actions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label style={filterLabel}><User size={11} /> {t("audit.filters.initiatedBy")}</label>
            <select style={selectBase} value={actorFilter} onChange={e => setActorFilter(e.target.value)}>
              <option value="all">{t("audit.filters.allUsers")}</option>
              {options.actors.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label style={filterLabel}><Layers size={11} /> Zieltyp</label>
            <select style={selectBase} value={targetTypeFilter} onChange={e => setTargetTypeFilter(e.target.value)}>
              <option value="all">Alle Zieltypen</option>
              {options.targetTypes.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label style={filterLabel}><Calendar size={11} /> {t("audit.filters.from")}</label>
            <input type="date" style={inputBase} value={startDate} onChange={e => setStartDate(e.target.value)} />
          </div>
          <div>
            <label style={filterLabel}><Calendar size={11} /> {t("audit.filters.to")}</label>
            <input type="date" style={inputBase} value={endDate} onChange={e => setEndDate(e.target.value)} />
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card style={{ padding: 16, border: `1px solid ${T.danger}40`, background: T.dangerDim }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, color: T.danger, fontSize: 13 }}>
            <AlertTriangle size={16} /> {error}
          </div>
        </Card>
      )}

      {/* Table */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 800 }}>
            <thead>
              <tr>
                <th style={thStyle}>{t("audit.table.timestamp")}</th>
                <th style={thStyle}>{t("audit.table.actor")}</th>
                <th style={thStyle}>{t("audit.table.operation")}</th>
                <th style={thStyle}>Kategorie</th>
                <th style={thStyle}>{t("audit.table.target")}</th>
                <th style={{ ...thStyle, textAlign: "right" }}>{t("audit.table.details")}</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: 60, textAlign: "center", color: T.textMuted }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                      <RefreshCw size={24} className="animate-spin" style={{ color: T.accent }} />
                      <span style={{ fontSize: 13 }}>{t("audit.table.fetching")}</span>
                    </div>
                  </td>
                </tr>
              ) : pagedRows.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: 60, textAlign: "center", color: T.textMuted }}>
                    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
                      <ShieldCheck size={32} style={{ color: T.textDim }} />
                      <span style={{ fontSize: 14, fontWeight: 600 }}>Keine Audit-Einträge gefunden</span>
                      <span style={{ fontSize: 12, color: T.textDim }}>
                        {hasActiveFilters ? "Versuchen Sie andere Filtereinstellungen." : "Es wurden noch keine Aktionen protokolliert."}
                      </span>
                    </div>
                  </td>
                </tr>
              ) : pagedRows.map((r) => (
                <tr
                  key={r.id}
                  style={{ transition: "background 0.15s", cursor: "pointer" }}
                  onMouseEnter={e => (e.currentTarget.style.background = T.surfaceAlt)}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                  onClick={() => setSelectedRow(r)}
                >
                  <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Clock size={12} color={T.textDim} />
                      <span style={{ fontSize: 12, color: T.textMuted, fontFamily: "var(--font-mono)" }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString("de-DE", {
                          day: "2-digit", month: "2-digit", year: "2-digit",
                          hour: "2-digit", minute: "2-digit", second: "2-digit",
                        }) : "–"}
                      </span>
                    </div>
                  </td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 8,
                        background: r.actor_email ? T.accentDim : T.surfaceAlt,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontSize: 11, fontWeight: 800, color: r.actor_email ? T.accent : T.textDim,
                        flexShrink: 0,
                      }}>
                        {(r.actor_email || "S")[0].toUpperCase()}
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                        {r.actor_email || "System"}
                      </span>
                    </div>
                  </td>
                  <td style={tdStyle}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{r.action}</span>
                  </td>
                  <td style={tdStyle}>
                    <Badge variant={categoryToVariant(r.category)} size="xs">{r.category}</Badge>
                  </td>
                  <td style={tdStyle}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Layers size={12} color={T.textDim} />
                      <span style={{ fontSize: 12, color: T.textMuted }}>{r.target_type || "–"}</span>
                      {r.target_id && (
                        <span style={{
                          fontSize: 10, fontWeight: 700, color: T.accent,
                          background: T.accentDim, padding: "2px 8px", borderRadius: 6,
                          fontFamily: "var(--font-mono)",
                        }}>
                          #{r.target_id}
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ ...tdStyle, textAlign: "right" }}>
                    <button
                      style={{
                        background: "transparent", border: `1px solid ${T.border}`,
                        borderRadius: 8, padding: "5px 12px", cursor: "pointer",
                        display: "inline-flex", alignItems: "center", gap: 6,
                        fontSize: 11, fontWeight: 700, color: T.accent,
                        transition: "all 0.2s",
                      }}
                      onClick={(e) => { e.stopPropagation(); setSelectedRow(r); }}
                    >
                      <Eye size={12} /> Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {filteredRows.length > PAGE_SIZE && (
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 20px", borderTop: `1px solid ${T.border}`,
          }}>
            <span style={{ fontSize: 12, color: T.textMuted }}>
              {filteredRows.length.toLocaleString("de")} Einträge · Seite {page + 1} von {totalPages}
            </span>
            <div style={{ display: "flex", gap: 6 }}>
              <button
                style={{ ...btnGhost, padding: "6px 12px", opacity: page === 0 ? 0.4 : 1 }}
                disabled={page === 0}
                onClick={() => setPage(p => Math.max(0, p - 1))}
              >
                <ChevronLeft size={14} /> Zurück
              </button>
              <button
                style={{ ...btnGhost, padding: "6px 12px", opacity: page >= totalPages - 1 ? 0.4 : 1 }}
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              >
                Weiter <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* Detail Modal */}
      <Modal
        open={!!selectedRow}
        onClose={() => setSelectedRow(null)}
        title={t("audit.modal.title")}
        subtitle={selectedRow ? `${selectedRow.action} · ${selectedRow.created_at ? new Date(selectedRow.created_at).toLocaleString("de-DE") : "–"}` : ""}
        width="min(800px, 95vw)"
      >
        {selectedRow && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Meta Grid */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={modalField}>
                <label style={modalLabel}>{t("audit.modal.actorIdentity")}</label>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>
                  {selectedRow.actor_email || t("audit.filters.systemInternal")}
                </div>
              </div>
              <div style={modalField}>
                <label style={modalLabel}>Aktion</label>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>
                  {selectedRow.action}
                </div>
              </div>
              <div style={modalField}>
                <label style={modalLabel}>Kategorie</label>
                <Badge variant={categoryToVariant(selectedRow.category)} size="xs">
                  {selectedRow.category}
                </Badge>
              </div>
              <div style={modalField}>
                <label style={modalLabel}>{t("audit.modal.targetResource")}</label>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>
                  {selectedRow.target_type || "–"}{selectedRow.target_id ? ` #${selectedRow.target_id}` : ""}
                </div>
              </div>
            </div>

            {/* Details JSON */}
            <div>
              <label style={modalLabel}>{t("audit.modal.changeSummary")}</label>
              <div style={{
                padding: 20, borderRadius: 12,
                background: "#0C0D12", border: `1px solid ${T.border}`,
                color: T.text, fontSize: 12, fontFamily: "var(--font-mono)",
                overflowX: "auto", maxHeight: 400, overflowY: "auto",
                lineHeight: 1.6,
              }}>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                  {formatDetails(selectedRow.details)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ── Helpers ── */
function categoryToVariant(cat: string): "default" | "success" | "warning" | "danger" | "info" | "accent" {
  const c = cat.toLowerCase();
  if (c.includes("security") || c.includes("auth") || c.includes("access")) return "danger";
  if (c.includes("tenant") || c.includes("plan") || c.includes("billing")) return "accent";
  if (c.includes("knowledge") || c.includes("prompt") || c.includes("data")) return "info";
  if (c.includes("settings") || c.includes("config")) return "warning";
  if (c.includes("member") || c.includes("sync") || c.includes("import")) return "success";
  return "default";
}

function formatDetails(details: Record<string, unknown> | null): string {
  if (!details || Object.keys(details).length === 0) return "// Keine Details vorhanden";
  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return String(details);
  }
}
