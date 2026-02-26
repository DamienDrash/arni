"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import {
  Brain, FileText, Save, RefreshCw, AlertCircle, History, Search,
  Database, ChevronRight, Activity, Clock, Sparkles, Eye, Trash2,
  CheckCircle2, XCircle, BarChart3, Zap, ArrowRight, Info,
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

/* ── Styles ─────────────────────────────────────────────────────────── */
const statCard: React.CSSProperties = {
  padding: "20px 24px",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 16,
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

/* ── Component ──────────────────────────────────────────────────────── */
export default function MemberMemoryPage() {
  const { t } = useI18n();
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
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFile = useCallback(async (id: string) => {
    setLoadingFile(true);
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${id}`);
      if (res.ok) {
        const data = await res.json();
        setContent(data.content);
        setBaseMtime(data.mtime);
        setSelectedFile(id);
        setReason("");
      }
    } finally {
      setLoadingFile(false);
    }
  }, []);

  const saveFile = useCallback(async () => {
    if (!selectedFile || !reason.trim() || reason.length < 8) {
      setError(t("memberMemory.reasonPlaceholder"));
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${selectedFile}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, base_mtime: baseMtime, reason }),
      });
      if (res.ok) {
        const data = await res.json();
        setBaseMtime(data.mtime);
        setReason("");
        setSuccess("Erfolgreich gespeichert");
        setTimeout(() => setSuccess(""), 3000);
      } else {
        const data = await res.json();
        setError(data.detail || "Speichern fehlgeschlagen");
      }
    } finally {
      setSaving(false);
    }
  }, [selectedFile, reason, content, baseMtime, t]);

  const runAnalysis = useCallback(async () => {
    setRunning(true);
    setError("");
    try {
      const res = await apiFetch("/admin/member-memory/analyze-now", { method: "POST" });
      if (res.ok) {
        setSuccess("Analyse erfolgreich gestartet");
        setTimeout(() => setSuccess(""), 3000);
        loadData();
      } else {
        setError("Analyse konnte nicht gestartet werden");
      }
    } finally {
      setRunning(false);
    }
  }, [loadData]);

  useEffect(() => { loadData(); }, [loadData]);

  /* ── Derived ──────────────────────────────────────────────────────── */
  const filteredFiles = useMemo(() => {
    return files.filter((f) => f.toLowerCase().includes(search.toLowerCase()));
  }, [files, search]);

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
            <button onClick={loadData} style={btnSecondary}>
              <RefreshCw size={14} /> Aktualisieren
            </button>
            <button
              disabled={running}
              onClick={runAnalysis}
              style={{ ...btnPrimary, opacity: running ? 0.6 : 1 }}
            >
              {running ? <RefreshCw size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Sparkles size={16} />}
              Analyse jetzt starten
            </button>
          </div>
        }
      />

      {/* Status Alerts */}
      {success && (
        <div style={{
          padding: "12px 20px", borderRadius: 12,
          background: T.successDim, border: `1px solid ${T.success}40`,
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.success, fontWeight: 600,
        }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}
      {error && (
        <div style={{
          padding: "12px 20px", borderRadius: 12,
          background: T.dangerDim, border: `1px solid ${T.danger}40`,
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.danger, fontWeight: 600,
        }}>
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
          <div style={statIcon(meta?.cron_enabled ? T.success : T.warning)}>
            <Clock size={20} />
          </div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("memberMemory.lastRun")}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: runStatusColor }}>{runStatusLabel}</div>
            {meta?.last_run_at && (
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>
                {new Date(meta.last_run_at).toLocaleString("de-DE")}
              </div>
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

      {/* Main Content: File Browser + Editor */}
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4" style={{ minHeight: "calc(100vh - 420px)" }}>
        {/* File Browser Sidebar */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{
            padding: "16px 16px 12px", borderBottom: `1px solid ${T.border}`,
            background: `${T.surface}80`,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Brain size={16} color={T.accent} />
                <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>Gedächtniseinträge</span>
              </div>
              <Badge variant="info" size="xs">{filteredFiles.length}</Badge>
            </div>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
              <input
                style={{ ...inputBase, paddingLeft: 34, fontSize: 12 }}
                placeholder="Eintrag suchen…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
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
                    <button
                      key={f}
                      onClick={() => loadFile(f)}
                      style={{
                        width: "100%", textAlign: "left", padding: "12px 14px",
                        borderRadius: 10, border: `1px solid ${isActive ? `${T.accent}60` : "transparent"}`,
                        background: isActive ? T.accentDim : "transparent",
                        color: isActive ? T.accentLight : T.text,
                        cursor: "pointer", display: "flex", alignItems: "center",
                        justifyContent: "space-between", gap: 10,
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                        <FileText size={14} style={{ flexShrink: 0, color: isActive ? T.accent : T.textDim }} />
                        <span style={{
                          fontSize: 12, fontWeight: isActive ? 700 : 500,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          textTransform: "capitalize",
                        }}>
                          {displayName}
                        </span>
                      </div>
                      <ChevronRight size={14} style={{
                        flexShrink: 0, color: isActive ? T.accent : T.textDim,
                        opacity: isActive ? 1 : 0.3,
                        transition: "all 0.15s ease",
                      }} />
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        {/* Editor Area */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selectedFile ? (
            <>
              {/* Editor Header */}
              <div style={{
                padding: "14px 20px",
                borderBottom: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: `${T.surface}80`, flexWrap: "wrap", gap: 10,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 10,
                    background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center",
                    color: T.accent,
                  }}>
                    <FileText size={18} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>
                      {selectedFile.replace(".md", "").replace(/-/g, " ")}
                    </div>
                    <div style={{ fontSize: 10, color: T.textDim, display: "flex", gap: 12, marginTop: 2 }}>
                      <span>{lineCount} Zeilen</span>
                      <span>{wordCount} Wörter</span>
                      <span>Markdown</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ position: "relative" }}>
                    <History size={12} style={{ position: "absolute", left: 10, top: 10, color: T.textDim }} />
                    <input
                      style={{ ...inputBase, width: 260, paddingLeft: 30, fontSize: 11 }}
                      placeholder={t("memberMemory.reasonPlaceholder")}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <button
                    onClick={() => setPreviewOpen(true)}
                    style={btnSecondary}
                    title="Vorschau"
                  >
                    <Eye size={14} />
                  </button>
                  <button
                    onClick={saveFile}
                    disabled={saving || reason.length < 8}
                    style={{
                      ...btnPrimary,
                      opacity: saving || reason.length < 8 ? 0.4 : 1,
                      padding: "8px 16px",
                    }}
                  >
                    {saving ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={14} />}
                    Speichern
                  </button>
                </div>
              </div>

              {/* Editor Body */}
              <div style={{ flex: 1, position: "relative" }}>
                {loadingFile ? (
                  <div style={{
                    position: "absolute", inset: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: T.surface, zIndex: 2,
                  }}>
                    <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: T.accent }} />
                  </div>
                ) : null}
                <textarea
                  style={{
                    width: "100%", height: "100%", minHeight: 400,
                    background: "transparent", border: "none", outline: "none",
                    padding: "20px 24px", color: T.text,
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    fontSize: 13, lineHeight: 1.7, resize: "none",
                  }}
                  className="custom-scrollbar"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  spellCheck={false}
                  placeholder="Gedächtnisinhalt wird hier angezeigt…"
                />
              </div>

              {/* Editor Footer */}
              <div style={{
                padding: "8px 20px", borderTop: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: `${T.surface}60`, fontSize: 10, color: T.textDim,
              }}>
                <div style={{ display: "flex", gap: 16 }}>
                  <span>Datei: {selectedFile}</span>
                  <span>Zeilen: {lineCount}</span>
                  <span>Wörter: {wordCount}</span>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  {reason.length >= 8 ? (
                    <Badge variant="success" size="xs">Bereit zum Speichern</Badge>
                  ) : (
                    <Badge variant="warning" size="xs">Änderungsgrund erforderlich (min. 8 Zeichen)</Badge>
                  )}
                </div>
              </div>
            </>
          ) : (
            /* Empty State */
            <div style={{
              flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", padding: 48, textAlign: "center",
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: "50%",
                background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center",
                marginBottom: 20, border: `1px solid ${T.accent}30`,
              }}>
                <Brain size={32} color={T.accent} strokeWidth={1.5} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 8 }}>
                {t("memberMemory.selectFile")}
              </h3>
              <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 360, lineHeight: 1.6 }}>
                Wählen Sie links einen Gedächtniseintrag aus, um den Inhalt zu bearbeiten.
                Die KI analysiert Chatverläufe und erstellt automatisch Mitgliederprofile.
              </p>
              {files.length > 0 && (
                <button
                  onClick={() => loadFile(files[0])}
                  style={{ ...btnPrimary, marginTop: 20 }}
                >
                  <ArrowRight size={16} /> Ersten Eintrag öffnen
                </button>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Info Card */}
      <Card style={{ padding: "16px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={statIcon(T.info)}>
          <Info size={18} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>
            Wie funktioniert das Mitgliedergedächtnis?
          </div>
          <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
            Das Mitgliedergedächtnis analysiert automatisch Chatverläufe und extrahiert relevante Informationen
            über Ihre Mitglieder – wie Trainingsziele, Vorlieben, Beschwerden und persönliche Details.
            Diese Informationen werden als Markdown-Dateien gespeichert und stehen der KI bei zukünftigen
            Gesprächen als Kontext zur Verfügung. Sie können Einträge manuell bearbeiten oder die automatische
            Analyse jederzeit starten.
          </p>
        </div>
      </Card>

      {/* Preview Modal */}
      <Modal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="Vorschau"
        subtitle={selectedFile || ""}
        width="min(700px, 90vw)"
      >
        <div style={{
          padding: 24, maxHeight: "60vh", overflowY: "auto",
          fontSize: 13, lineHeight: 1.8, color: T.text,
          whiteSpace: "pre-wrap", fontFamily: "system-ui, sans-serif",
        }} className="custom-scrollbar">
          {content || "Kein Inhalt"}
        </div>
      </Modal>
    </div>
  );
}
