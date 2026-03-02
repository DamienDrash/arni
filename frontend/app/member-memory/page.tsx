"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  Brain, FileText, Save, RefreshCw, AlertCircle, History, Search,
  Database, ChevronRight, Activity, Clock, Sparkles, Eye, Trash2,
  CheckCircle2, XCircle, BarChart3, Zap, ArrowRight, Info,
  Tag, User, Heart, Calendar, Shield, TrendingDown, MessageSquare,
  Filter, Layers, GitBranch,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { useI18n } from "@/lib/i18n/LanguageContext";

/* ── Types ──────────────────────────────────────────────────────────── */
type MemoryMeta = {
  cron_enabled: boolean;
  cron_expr: string;
  llm_enabled: boolean;
  llm_model: string;
  last_run_at: string;
  last_run_status: string;
  last_run_error: string;
};

type StructuredFact = {
  fact_id: string;
  fact_type: string;
  subject: string;
  predicate: string;
  value: string;
  confidence: number;
  source: string;
  created_at: string;
  updated_at: string;
  decay_score: number;
};

type MemoryTimeline = {
  event_id: string;
  event_type: string;
  summary: string;
  timestamp: string;
  source: string;
};

/* ── Styles ─────────────────────────────────────────────────────────── */
const statCard: React.CSSProperties = {
  padding: "20px 24px",
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
};
const statIcon: (color: string) => React.CSSProperties = (color) => ({
  width: 44, height: 44, borderRadius: 12,
  background: `${color}15`,
  display: "flex", alignItems: "center", justifyContent: "center",
  color, flexShrink: 0,
});
const statLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4,
};
const statValue: (color?: string) => React.CSSProperties = (color) => ({
  fontSize: 24, fontWeight: 800, color: color || T.text, letterSpacing: "-0.02em",
});
const inputBase: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  transition: "border-color 0.2s ease",
};
const btnPrimary: React.CSSProperties = {
  border: "none", borderRadius: 10, background: T.accent, color: "#fff",
  fontWeight: 700, padding: "10px 20px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13,
  transition: "all 0.2s ease",
};
const btnSecondary: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt,
  color: T.text, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
  transition: "all 0.2s ease",
};
const tabBtn: (active: boolean) => React.CSSProperties = (active) => ({
  padding: "10px 20px", borderRadius: 10, border: "none",
  background: active ? T.accentDim : "transparent",
  color: active ? T.accentLight : T.textMuted,
  fontWeight: 600, fontSize: 13, cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 8,
  transition: "all 0.2s ease",
});

/* ── Helpers ────────────────────────────────────────────────────────── */
function getFactIcon(factType: string) {
  switch (factType) {
    case "attribute": return <User size={14} style={{ color: T.info }} />;
    case "preference": return <Heart size={14} style={{ color: T.danger }} />;
    case "relationship": return <GitBranch size={14} style={{ color: T.accent }} />;
    case "event": return <Calendar size={14} style={{ color: T.warning }} />;
    case "sentiment": return <MessageSquare size={14} style={{ color: T.success }} />;
    default: return <Tag size={14} style={{ color: T.textDim }} />;
  }
}

function getFactBadgeVariant(factType: string): "info" | "danger" | "accent" | "warning" | "success" | "default" {
  switch (factType) {
    case "attribute": return "info";
    case "preference": return "danger";
    case "relationship": return "accent";
    case "event": return "warning";
    case "sentiment": return "success";
    default: return "default";
  }
}

function getFactTypeLabel(factType: string): string {
  switch (factType) {
    case "attribute": return "Eigenschaft";
    case "preference": return "Präferenz";
    case "relationship": return "Beziehung";
    case "event": return "Ereignis";
    case "sentiment": return "Stimmung";
    default: return factType;
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "–";
  try {
    return new Date(dateStr).toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return dateStr; }
}

function confidenceColor(score: number): string {
  if (score >= 0.8) return T.success;
  if (score >= 0.5) return T.warning;
  return T.danger;
}

/* ── Component ──────────────────────────────────────────────────────── */
export default function MemberMemoryPage() {
  const { t } = useI18n();

  /* ── State ────────────────────────────────────────────────────────── */
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [baseMtime, setBaseMtime] = useState<number | null>(null);
  const [meta, setMeta] = useState<MemoryMeta | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);

  // New: structured view
  const [activeTab, setActiveTab] = useState<"editor" | "facts" | "timeline">("editor");
  const [facts, setFacts] = useState<StructuredFact[]>([]);
  const [timeline, setTimeline] = useState<MemoryTimeline[]>([]);
  const [factFilter, setFactFilter] = useState("all");
  const [loadingFacts, setLoadingFacts] = useState(false);

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [fRes, mRes] = await Promise.all([
        apiFetch("/admin/member-memory"),
        apiFetch("/admin/member-memory/status"),
      ]);
      if (fRes.ok) setFiles(await fRes.json());
      if (mRes.ok) setMeta(await mRes.json());
    } finally { setLoading(false); }
  }, []);

  const loadFile = useCallback(async (id: string) => {
    setLoadingFile(true); setError(""); setSuccess("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${id}`);
      if (res.ok) {
        const data = await res.json();
        setContent(data.content);
        setBaseMtime(data.mtime);
        setSelectedFile(id);
        setReason("");
      }
    } finally { setLoadingFile(false); }
  }, []);

  const loadFacts = useCallback(async (memberId: string) => {
    setLoadingFacts(true);
    try {
      const res = await apiFetch(`/memory-platform/members/${encodeURIComponent(memberId)}/facts`);
      if (res.ok) setFacts(await res.json());
      else setFacts([]);
    } catch { setFacts([]); }
    setLoadingFacts(false);
  }, []);

  const loadTimeline = useCallback(async (memberId: string) => {
    try {
      const res = await apiFetch(`/memory-platform/members/${encodeURIComponent(memberId)}/timeline`);
      if (res.ok) setTimeline(await res.json());
      else setTimeline([]);
    } catch { setTimeline([]); }
  }, []);

  const saveFile = useCallback(async () => {
    if (!selectedFile || !reason.trim() || reason.length < 8) {
      setError(t("memberMemory.reasonPlaceholder")); return;
    }
    setSaving(true); setError(""); setSuccess("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${selectedFile}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, base_mtime: baseMtime, reason }),
      });
      if (res.ok) {
        const data = await res.json();
        setBaseMtime(data.mtime); setReason("");
        setSuccess("Erfolgreich gespeichert"); setTimeout(() => setSuccess(""), 3000);
      } else {
        const data = await res.json();
        setError(data.detail || "Speichern fehlgeschlagen");
      }
    } finally { setSaving(false); }
  }, [selectedFile, reason, content, baseMtime, t]);

  const runAnalysis = useCallback(async () => {
    setRunning(true); setError("");
    try {
      const res = await apiFetch("/admin/member-memory/analyze-now", { method: "POST" });
      if (res.ok) {
        setSuccess("Analyse erfolgreich gestartet"); setTimeout(() => setSuccess(""), 3000);
        loadData();
      } else setError("Analyse konnte nicht gestartet werden");
    } finally { setRunning(false); }
  }, [loadData]);

  async function deleteFact(factId: string) {
    if (!confirm("Fakt wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/memory-platform/facts/${factId}`, { method: "DELETE" });
      if (res.ok) {
        setFacts((prev) => prev.filter((f) => f.fact_id !== factId));
        setSuccess("Fakt gelöscht"); setTimeout(() => setSuccess(""), 3000);
      }
    } catch { setError("Löschen fehlgeschlagen"); }
  }

  useEffect(() => { loadData(); }, [loadData]);

  // Load facts/timeline when a file is selected and tab changes
  useEffect(() => {
    if (!selectedFile) return;
    const memberId = selectedFile.replace(".md", "");
    if (activeTab === "facts") loadFacts(memberId);
    if (activeTab === "timeline") loadTimeline(memberId);
  }, [selectedFile, activeTab, loadFacts, loadTimeline]);

  /* ── Derived ──────────────────────────────────────────────────────── */
  const filteredFiles = useMemo(() => {
    return files.filter((f) => f.toLowerCase().includes(search.toLowerCase()));
  }, [files, search]);

  const filteredFacts = useMemo(() => {
    if (factFilter === "all") return facts;
    return facts.filter((f) => f.fact_type === factFilter);
  }, [facts, factFilter]);

  const isRunOk = meta?.last_run_status === "ok";
  const isRunError = meta?.last_run_status?.startsWith("error");
  const runStatusColor = isRunOk ? T.success : isRunError ? T.danger : T.textDim;
  const runStatusLabel = isRunOk ? "Erfolgreich" : isRunError ? "Fehler" : (meta?.last_run_status || "Nie ausgeführt");
  const lineCount = content ? content.split("\n").length : 0;
  const wordCount = content ? content.split(/\s+/).filter(Boolean).length : 0;

  /* ── Loading State ────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SectionHeader title={t("memberMemory.title")} subtitle={t("memberMemory.subtitle")} />
        <div style={{ padding: 60, textAlign: "center", color: T.textMuted, fontSize: 13 }}>
          <RefreshCw size={20} style={{ animation: "spin 1s linear infinite", marginBottom: 12 }} />
          <div>Lade Gedächtnisdaten…</div>
        </div>
      </div>
    );
  }

  /* ── Main Render ──────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <SectionHeader
        title={t("memberMemory.title")}
        subtitle={t("memberMemory.subtitle")}
        action={
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={loadData} style={btnSecondary}><RefreshCw size={14} /> Aktualisieren</button>
            <button disabled={running} onClick={runAnalysis} style={{ ...btnPrimary, opacity: running ? 0.6 : 1 }}>
              {running ? <RefreshCw size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Sparkles size={16} />}
              Analyse jetzt starten
            </button>
          </div>
        }
      />

      {/* Alerts */}
      {success && (
        <div style={{ padding: "12px 20px", borderRadius: 12, background: T.successDim, border: `1px solid ${T.success}40`, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.success, fontWeight: 600 }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}
      {error && (
        <div style={{ padding: "12px 20px", borderRadius: 12, background: T.dangerDim, border: `1px solid ${T.danger}40`, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.danger, fontWeight: 600 }}>
          <XCircle size={16} /> {error}
          <button onClick={() => setError("")} style={{ marginLeft: "auto", background: "none", border: "none", color: T.danger, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("memberMemory.files")}</div>
            <div style={statValue()}>{files.length}</div>
          </div>
          <div style={statIcon(T.accent)}><Database size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("memberMemory.scheduler")}</div>
            <div style={statValue(meta?.cron_enabled ? T.success : T.warning)}>
              {meta?.cron_enabled ? "Aktiv" : "Pausiert"}
            </div>
            {meta?.cron_expr && (
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 2, fontFamily: "monospace" }}>{meta.cron_expr}</div>
            )}
          </div>
          <div style={statIcon(meta?.cron_enabled ? T.success : T.warning)}><Clock size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("memberMemory.lastRun")}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: runStatusColor }}>{runStatusLabel}</div>
            {meta?.last_run_at && (
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>{new Date(meta.last_run_at).toLocaleString("de-DE")}</div>
            )}
          </div>
          <div style={statIcon(runStatusColor)}>
            {isRunOk ? <CheckCircle2 size={20} /> : isRunError ? <XCircle size={20} /> : <Activity size={20} />}
          </div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>KI-Modell</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: meta?.llm_enabled ? T.accent : T.textDim }}>
              {meta?.llm_enabled ? (meta.llm_model || "Aktiviert") : "Deaktiviert"}
            </div>
          </div>
          <div style={statIcon(T.accent)}><Brain size={20} /></div>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4" style={{ minHeight: "calc(100vh - 520px)" }}>
        {/* File Browser Sidebar */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "16px 16px 12px", borderBottom: `1px solid ${T.border}`, background: `${T.surface}80` }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Brain size={16} color={T.accent} />
                <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>Gedächtniseinträge</span>
              </div>
              <Badge variant="info" size="xs">{filteredFiles.length}</Badge>
            </div>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
              <input style={{ ...inputBase, paddingLeft: 34, fontSize: 12 }} placeholder="Eintrag suchen…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }} className="custom-scrollbar">
            {filteredFiles.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: T.textDim, fontSize: 12 }}>
                <Brain size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <div>{t("memberMemory.noFiles")}</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredFiles.map((f) => {
                  const isActive = selectedFile === f;
                  const displayName = f.replace(".md", "").replace(/-/g, " ");
                  return (
                    <button key={f} onClick={() => { loadFile(f); setActiveTab("editor"); }} style={{
                      width: "100%", textAlign: "left", padding: "12px 14px", borderRadius: 10,
                      border: `1px solid ${isActive ? `${T.accent}60` : "transparent"}`,
                      background: isActive ? T.accentDim : "transparent",
                      color: isActive ? T.accentLight : T.text,
                      cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
                      transition: "all 0.15s ease",
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                        <FileText size={14} style={{ flexShrink: 0, color: isActive ? T.accent : T.textDim }} />
                        <span style={{ fontSize: 12, fontWeight: isActive ? 700 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", textTransform: "capitalize" }}>{displayName}</span>
                      </div>
                      <ChevronRight size={14} style={{ flexShrink: 0, color: isActive ? T.accent : T.textDim, opacity: isActive ? 1 : 0.3 }} />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        {/* Content Area */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {selectedFile ? (
            <>
              {/* Tab Navigation */}
              <Card style={{ padding: "8px", display: "flex", gap: 4 }}>
                <button style={tabBtn(activeTab === "editor")} onClick={() => setActiveTab("editor")}>
                  <FileText size={16} /> Markdown
                </button>
                <button style={tabBtn(activeTab === "facts")} onClick={() => setActiveTab("facts")}>
                  <Tag size={16} /> Strukturierte Fakten
                  {facts.length > 0 && <Badge variant="accent" size="xs">{facts.length}</Badge>}
                </button>
                <button style={tabBtn(activeTab === "timeline")} onClick={() => setActiveTab("timeline")}>
                  <Clock size={16} /> Timeline
                  {timeline.length > 0 && <Badge variant="info" size="xs">{timeline.length}</Badge>}
                </button>
              </Card>

              {/* ── Tab: Markdown Editor ───────────────────────────────── */}
              {activeTab === "editor" && (
                <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden", flex: 1 }}>
                  <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", background: `${T.surface}80`, flexWrap: "wrap", gap: 10 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 10, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.accent }}>
                        <FileText size={18} />
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{selectedFile.replace(".md", "").replace(/-/g, " ")}</div>
                        <div style={{ fontSize: 10, color: T.textDim, display: "flex", gap: 12, marginTop: 2 }}>
                          <span>{lineCount} Zeilen</span><span>{wordCount} Wörter</span><span>Markdown</span>
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ position: "relative" }}>
                        <History size={12} style={{ position: "absolute", left: 10, top: 10, color: T.textDim }} />
                        <input style={{ ...inputBase, width: 260, paddingLeft: 30, fontSize: 11 }} placeholder={t("memberMemory.reasonPlaceholder")} value={reason} onChange={(e) => setReason(e.target.value)} />
                      </div>
                      <button onClick={() => setPreviewOpen(true)} style={btnSecondary} title="Vorschau"><Eye size={14} /></button>
                      <button onClick={saveFile} disabled={saving || reason.length < 8} style={{ ...btnPrimary, opacity: saving || reason.length < 8 ? 0.4 : 1, padding: "8px 16px" }}>
                        {saving ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={14} />} Speichern
                      </button>
                    </div>
                  </div>
                  <div style={{ flex: 1, position: "relative" }}>
                    {loadingFile && (
                      <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", background: T.surface, zIndex: 2 }}>
                        <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: T.accent }} />
                      </div>
                    )}
                    <textarea
                      style={{ width: "100%", height: "100%", minHeight: 400, background: "transparent", border: "none", outline: "none", padding: "20px 24px", color: T.text, fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontSize: 13, lineHeight: 1.7, resize: "none" }}
                      className="custom-scrollbar" value={content} onChange={(e) => setContent(e.target.value)} spellCheck={false} placeholder="Gedächtnisinhalt wird hier angezeigt…"
                    />
                  </div>
                  <div style={{ padding: "8px 20px", borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", background: `${T.surface}60`, fontSize: 10, color: T.textDim }}>
                    <div style={{ display: "flex", gap: 16 }}><span>Datei: {selectedFile}</span><span>Zeilen: {lineCount}</span><span>Wörter: {wordCount}</span></div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      {reason.length >= 8 ? <Badge variant="success" size="xs">Bereit zum Speichern</Badge> : <Badge variant="warning" size="xs">Änderungsgrund erforderlich (min. 8 Zeichen)</Badge>}
                    </div>
                  </div>
                </Card>
              )}

              {/* ── Tab: Structured Facts ─────────────────────────────── */}
              {activeTab === "facts" && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {/* Fact Filter */}
                  <Card style={{ padding: "12px 20px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <Filter size={14} style={{ color: T.textDim }} />
                    <span style={{ fontSize: 12, color: T.textMuted }}>Typ:</span>
                    {[
                      { key: "all", label: "Alle" },
                      { key: "attribute", label: "Eigenschaften" },
                      { key: "preference", label: "Präferenzen" },
                      { key: "relationship", label: "Beziehungen" },
                      { key: "event", label: "Ereignisse" },
                      { key: "sentiment", label: "Stimmung" },
                    ].map((f) => (
                      <button key={f.key} onClick={() => setFactFilter(f.key)} style={{
                        padding: "4px 12px", borderRadius: 8, border: "none",
                        background: factFilter === f.key ? T.accentDim : T.surfaceAlt,
                        color: factFilter === f.key ? T.accentLight : T.textMuted,
                        fontSize: 11, fontWeight: 600, cursor: "pointer",
                      }}>
                        {f.label}
                      </button>
                    ))}
                    <span style={{ marginLeft: "auto", fontSize: 11, color: T.textDim }}>{filteredFacts.length} Fakt(en)</span>
                  </Card>

                  {/* Facts List */}
                  {loadingFacts ? (
                    <Card style={{ padding: 40, textAlign: "center" }}>
                      <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: T.accent, margin: "0 auto" }} />
                    </Card>
                  ) : filteredFacts.length === 0 ? (
                    <Card style={{ padding: 48, textAlign: "center" }}>
                      <Tag size={48} style={{ color: T.textDim, opacity: 0.3, margin: "0 auto 16px", display: "block" }} />
                      <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>Keine strukturierten Fakten</h3>
                      <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
                        Starten Sie eine Analyse, um Fakten aus den Chatverläufen zu extrahieren
                      </p>
                    </Card>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {filteredFacts.map((fact) => (
                        <Card key={fact.fact_id} style={{ padding: "14px 20px" }}>
                          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
                            <div style={{ display: "flex", gap: 12, flex: 1 }}>
                              <div style={{ ...statIcon(T.surfaceAlt), width: 36, height: 36, borderRadius: 10, flexShrink: 0 }}>
                                {getFactIcon(fact.fact_type)}
                              </div>
                              <div style={{ flex: 1 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                  <Badge variant={getFactBadgeVariant(fact.fact_type)} size="xs">{getFactTypeLabel(fact.fact_type)}</Badge>
                                  <span style={{ fontSize: 11, color: T.textDim }}>{fact.predicate.replace(/_/g, " ")}</span>
                                </div>
                                <div style={{ fontSize: 14, fontWeight: 600, color: T.text, marginBottom: 4 }}>{fact.value}</div>
                                <div style={{ display: "flex", gap: 16, fontSize: 10, color: T.textDim }}>
                                  <span>Konfidenz: <span style={{ color: confidenceColor(fact.confidence), fontWeight: 700 }}>{Math.round(fact.confidence * 100)}%</span></span>
                                  <span>Quelle: {fact.source}</span>
                                  {fact.decay_score < 1 && <span>Decay: <span style={{ color: T.warning }}>{Math.round(fact.decay_score * 100)}%</span></span>}
                                  <span>{formatDate(fact.updated_at)}</span>
                                </div>
                              </div>
                            </div>
                            <button onClick={() => deleteFact(fact.fact_id)} style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4 }} title="Löschen">
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── Tab: Timeline ─────────────────────────────────────── */}
              {activeTab === "timeline" && (
                <Card style={{ padding: 0, overflow: "hidden" }}>
                  <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 10 }}>
                    <Clock size={16} style={{ color: T.accent }} />
                    <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Interaktions-Timeline</span>
                    <Badge variant="info" size="xs">{timeline.length}</Badge>
                  </div>
                  {timeline.length === 0 ? (
                    <div style={{ padding: 48, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                      Keine Timeline-Einträge vorhanden
                    </div>
                  ) : (
                    <div style={{ padding: "16px 20px" }}>
                      {timeline.map((event, i) => (
                        <div key={event.event_id} style={{ display: "flex", gap: 16, paddingBottom: 20, position: "relative" }}>
                          {/* Timeline line */}
                          {i < timeline.length - 1 && (
                            <div style={{ position: "absolute", left: 15, top: 28, bottom: 0, width: 2, background: T.border }} />
                          )}
                          {/* Dot */}
                          <div style={{
                            width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                            background: event.event_type === "conversation" ? T.accentDim : event.event_type === "analysis" ? T.successDim : T.surfaceAlt,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            border: `2px solid ${T.border}`, zIndex: 1,
                          }}>
                            {event.event_type === "conversation" ? <MessageSquare size={14} style={{ color: T.accent }} /> :
                             event.event_type === "analysis" ? <Sparkles size={14} style={{ color: T.success }} /> :
                             <Activity size={14} style={{ color: T.textDim }} />}
                          </div>
                          {/* Content */}
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                              <Badge variant={event.event_type === "conversation" ? "accent" : event.event_type === "analysis" ? "success" : "default"} size="xs">
                                {event.event_type === "conversation" ? "Gespräch" : event.event_type === "analysis" ? "Analyse" : event.event_type}
                              </Badge>
                              <span style={{ fontSize: 11, color: T.textDim }}>{formatDate(event.timestamp)}</span>
                            </div>
                            <div style={{ fontSize: 13, color: T.text, lineHeight: 1.5 }}>{event.summary}</div>
                            <div style={{ fontSize: 10, color: T.textDim, marginTop: 4 }}>Quelle: {event.source}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
              )}
            </>
          ) : (
            /* Empty State */
            <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden", flex: 1 }}>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 48, textAlign: "center" }}>
                <div style={{ width: 72, height: 72, borderRadius: "50%", background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20, border: `1px solid ${T.accent}30` }}>
                  <Brain size={32} color={T.accent} strokeWidth={1.5} />
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 8 }}>{t("memberMemory.selectFile")}</h3>
                <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 360, lineHeight: 1.6 }}>
                  Wählen Sie links einen Gedächtniseintrag aus. Sie können den Markdown-Inhalt bearbeiten, strukturierte Fakten einsehen oder die Interaktions-Timeline durchsuchen.
                </p>
                {files.length > 0 && (
                  <button onClick={() => { loadFile(files[0]); setActiveTab("editor"); }} style={{ ...btnPrimary, marginTop: 20 }}>
                    <ArrowRight size={16} /> Ersten Eintrag öffnen
                  </button>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Info Card */}
      <Card style={{ padding: "16px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={statIcon(T.info)}><Info size={18} /></div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Wie funktioniert das Kontaktgedächtnis?</div>
          <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
            Das Kontaktgedächtnis analysiert automatisch Chatverläufe und extrahiert relevante Informationen über Ihre Kontakte – wie Präferenzen, Interessen, Anliegen und persönliche Details.
            Die neuen strukturierten Fakten bieten eine übersichtliche Darstellung aller extrahierten Informationen mit Konfidenz-Scores und Decay-Werten.
            Die Timeline zeigt chronologisch alle Interaktionen und Analysen. Alle Informationen fließen automatisch in Gespräche und Kampagnenplanungen ein.
          </p>
        </div>
      </Card>

      {/* Preview Modal */}
      <Modal open={previewOpen} onClose={() => setPreviewOpen(false)} title="Vorschau" subtitle={selectedFile || ""} width="min(700px, 90vw)">
        <div style={{ padding: 24, maxHeight: "60vh", overflowY: "auto", fontSize: 13, lineHeight: 1.8, color: T.text, whiteSpace: "pre-wrap", fontFamily: "system-ui, sans-serif" }} className="custom-scrollbar">
          {content || "Kein Inhalt"}
        </div>
      </Modal>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
