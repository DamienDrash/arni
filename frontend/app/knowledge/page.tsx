"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { marked } from "marked";
import TurndownService from "turndown";
import {
  BookOpen, FileText, Plus, RefreshCw, Save, Search, Database,
  ChevronRight, CheckCircle2, XCircle, AlertTriangle, Trash2,
  Info, Sparkles, Eye, Clock, BarChart3, Layers, ArrowRight,
} from "lucide-react";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import TiptapEditor from "@/components/TiptapEditor";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/LanguageContext";

const turndownService = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });

/* ── Types ──────────────────────────────────────────────────────────── */
type KnowledgeStatus = {
  files_count: number;
  vector_count: number;
  last_ingest_at: string;
  last_ingest_status: string;
  last_ingest_error: string;
};
type FilePayload = { filename: string; content: string; mtime?: number };
type TenantOption = { id: number; slug: string; name: string; is_active: boolean };

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

/* ── Component ──────────────────────────────────────────────────────── */
export default function KnowledgePage() {
  const { t } = useI18n();
  const currentUser = getStoredUser();
  const isSystemAdmin = currentUser?.role === "system_admin";

  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [selectedTenantSlug, setSelectedTenantSlug] = useState<string>("");

  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [contentHtml, setContentHtml] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newName, setNewName] = useState("");
  const [reindexing, setReindexing] = useState(false);
  const [meta, setMeta] = useState<KnowledgeStatus | null>(null);
  const [loadedMtime, setLoadedMtime] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [changeReason, setChangeReason] = useState("");
  const [search, setSearch] = useState("");

  const selectedExists = useMemo(() => (selectedFile ? files.includes(selectedFile) : false), [files, selectedFile]);
  const isIngestOk = meta?.last_ingest_status === "ok";
  const isIngestError = (meta?.last_ingest_status || "").startsWith("error");
  const ingestColor = isIngestError ? T.danger : isIngestOk ? T.success : T.textDim;

  const slugParam = isSystemAdmin && selectedTenantSlug ? `?tenant_slug=${encodeURIComponent(selectedTenantSlug)}` : "";

  const filteredFiles = useMemo(() => {
    return files.filter((f) => f.toLowerCase().includes(search.toLowerCase()));
  }, [files, search]);

  /* ── Tenant Selector (System Admin) ───────────────────────────────── */
  useEffect(() => {
    if (!isSystemAdmin) return;
    apiFetch("/auth/tenants").then(async (res) => {
      if (!res.ok) return;
      const data = (await res.json()) as TenantOption[];
      setTenants(data);
      if (data.length > 0 && !selectedTenantSlug) {
        setSelectedTenantSlug(data[0].slug);
      }
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSystemAdmin]);

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const loadMeta = useCallback(async () => {
    const res = await apiFetch(`/admin/knowledge/status${slugParam}`);
    if (!res.ok) return;
    setMeta((await res.json()) as KnowledgeStatus);
  }, [slugParam]);

  const loadFiles = useCallback(async () => {
    setError("");
    const res = await apiFetch(`/admin/knowledge${slugParam}`);
    if (!res.ok) {
      setError(`Fehler beim Laden der Dateien (${res.status}).`);
      setFiles([]);
      setSelectedFile(null);
      return;
    }
    const data = await res.json();
    const next = Array.isArray(data) ? data : [];
    setFiles(next);
    if (!selectedFile && next.length > 0) setSelectedFile(next[0]);
    if (selectedFile && !next.includes(selectedFile)) setSelectedFile(next[0] || null);
  }, [slugParam, selectedFile]);

  const loadFile = useCallback(async (file: string) => {
    setStatus("Lade…");
    setError("");
    const res = await apiFetch(`/admin/knowledge/file/${file}${slugParam}`);
    if (!res.ok) {
      setStatus("");
      setError(`Fehler beim Laden (${res.status}).`);
      return;
    }
    const data = (await res.json()) as FilePayload;
    setContentHtml(await marked.parse(data.content || ""));
    setLoadedMtime(typeof data.mtime === "number" ? data.mtime : null);
    setDirty(false);
    setConflict(false);
    setStatus("Geladen");
  }, [slugParam]);

  /* ── Save ──────────────────────────────────────────────────────────── */
  const save = useCallback(async (opts?: { force?: boolean; silent?: boolean }) => {
    if (!selectedFile) return;
    const reason = changeReason.trim();
    if (reason.length < 8) {
      if (opts?.silent) return;
      setError(t("knowledge.reasonError"));
      setStatus("");
      return;
    }
    setStatus(opts?.silent ? "Auto-Speichern…" : "Speichern…");
    setError("");
    const markdown = turndownService.turndown(contentHtml || "");
    const res = await apiFetch(`/admin/knowledge/file/${selectedFile}${slugParam}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: markdown, base_mtime: opts?.force ? null : loadedMtime, reason }),
    });
    if (!res.ok) {
      if (res.status === 409) {
        setConflict(true);
        setStatus("Konflikt");
        setError("Diese Datei wurde zwischenzeitlich von einer anderen Quelle geändert.");
        return;
      }
      setStatus("");
      setError(`Fehler beim Speichern (${res.status}).`);
      return;
    }
    const body = (await res.json().catch(() => ({}))) as { mtime?: number };
    if (typeof body.mtime === "number") setLoadedMtime(body.mtime);
    setDirty(false);
    setConflict(false);
    if (!opts?.silent) {
      setSuccess("Erfolgreich gespeichert");
      setTimeout(() => setSuccess(""), 3000);
    }
    setStatus(opts?.silent ? "Auto-gespeichert" : "Gespeichert");
    await Promise.all([loadFiles(), loadMeta()]);
  }, [selectedFile, contentHtml, loadedMtime, loadFiles, loadMeta, changeReason, slugParam, t]);

  /* ── Reindex ──────────────────────────────────────────────────────── */
  async function reindexNow() {
    setReindexing(true);
    setStatus("Indiziere…");
    setError("");
    try {
      const res = await apiFetch(`/admin/knowledge/reindex${slugParam}`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || `Fehler (${res.status}).`);
        setStatus("");
        return;
      }
      setSuccess("Neu-Indizierung erfolgreich gestartet");
      setTimeout(() => setSuccess(""), 3000);
      setStatus("Indiziert");
      await Promise.all([loadFiles(), loadMeta()]);
    } finally {
      setReindexing(false);
    }
  }

  /* ── Create Draft ─────────────────────────────────────────────────── */
  function createDraftFile() {
    if (!newName.trim()) return;
    const safe = `${newName.trim().replace(/\s+/g, "-").toLowerCase()}${newName.endsWith(".md") ? "" : ".md"}`;
    if (!files.includes(safe)) setFiles((prev) => [safe, ...prev]);
    setSelectedFile(safe);
    setContentHtml(`<h1>${t("knowledge.newDocument")}</h1><p>${t("knowledge.selectFile")}</p>`);
    setLoadedMtime(null);
    setDirty(true);
    setConflict(false);
    setStatus("Entwurf erstellt");
    setNewName("");
  }

  /* ── Effects ──────────────────────────────────────────────────────── */
  useEffect(() => {
    if (isSystemAdmin && !selectedTenantSlug) return;
    setSelectedFile(null);
    setContentHtml("");
    setMeta(null);
    setFiles([]);
    setDirty(false);
    setConflict(false);
    setStatus("");
    setError("");
  }, [selectedTenantSlug, isSystemAdmin]);

  useEffect(() => {
    if (isSystemAdmin && !selectedTenantSlug) return;
    Promise.all([loadFiles(), loadMeta()]).catch(() => setError("Dateiliste konnte nicht geladen werden."));
  }, [loadFiles, loadMeta, isSystemAdmin, selectedTenantSlug]);

  useEffect(() => {
    const timer = setInterval(() => void loadMeta(), 30000);
    return () => clearInterval(timer);
  }, [loadMeta]);

  useEffect(() => {
    if (!selectedFile || !selectedExists) return;
    loadFile(selectedFile).catch(() => setError("Datei konnte nicht geladen werden."));
  }, [loadFile, selectedFile, selectedExists]);

  useEffect(() => {
    if (!selectedFile || !dirty || conflict) return;
    const timer = setTimeout(() => {
      void save({ silent: true });
    }, 2500);
    return () => clearTimeout(timer);
  }, [conflict, dirty, selectedFile, contentHtml, save]);

  /* ── Render ───────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <SectionHeader
        title={t("knowledge.title")}
        subtitle="Verwalten Sie die Wissensdokumente, die Ihrer KI als Kontext dienen"
        action={
          <div style={{ display: "flex", gap: 10 }}>
            <button onClick={() => void reindexNow()} disabled={reindexing} style={btnSecondary}>
              <RefreshCw size={14} style={reindexing ? { animation: "spin 1s linear infinite" } : {}} />
              {reindexing ? "Indiziere…" : "Neu indizieren"}
            </button>
          </div>
        }
      />

      {/* Tenant Selector (System Admin) */}
      {isSystemAdmin && (
        <Card style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 14 }}>
          <Badge variant="warning" size="xs">System Admin</Badge>
          <span style={{ fontSize: 12, color: T.textMuted }}>Mandant anzeigen:</span>
          <select
            value={selectedTenantSlug}
            onChange={(e) => setSelectedTenantSlug(e.target.value)}
            style={{ ...inputBase, width: "auto", maxWidth: 320, padding: "8px 12px", fontSize: 12 }}
          >
            {tenants.map((t) => (
              <option key={t.slug} value={t.slug}>{t.name} ({t.slug})</option>
            ))}
          </select>
          {selectedTenantSlug && (
            <span style={{ fontSize: 10, color: T.textDim, fontFamily: "monospace" }}>
              Collection: ariia_knowledge_{selectedTenantSlug}
            </span>
          )}
        </Card>
      )}

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
            <div style={statLabel}>{t("knowledge.documents")}</div>
            <div style={statValue()}>{meta?.files_count ?? files.length}</div>
          </div>
          <div style={statIcon(T.accent)}><BookOpen size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("knowledge.indexChunks")}</div>
            <div style={statValue(T.accent)}>{meta?.vector_count ?? 0}</div>
          </div>
          <div style={statIcon(T.info)}><Layers size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>{t("knowledge.lastIngest")}</div>
            <div style={{ fontSize: 14, fontWeight: 700, color: ingestColor }}>
              {isIngestOk ? "Erfolgreich" : isIngestError ? "Fehler" : (meta?.last_ingest_status || "Nie")}
            </div>
            {meta?.last_ingest_at && (
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>
                {new Date(meta.last_ingest_at).toLocaleString("de-DE")}
              </div>
            )}
          </div>
          <div style={statIcon(ingestColor)}>
            {isIngestOk ? <CheckCircle2 size={20} /> : isIngestError ? <XCircle size={20} /> : <Clock size={20} />}
          </div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Status</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: dirty ? T.warning : conflict ? T.danger : T.textMuted }}>
              {conflict ? "Konflikt" : dirty ? "Ungespeichert" : status || "Bereit"}
            </div>
          </div>
          <div style={statIcon(dirty ? T.warning : T.textDim)}>
            <BarChart3 size={20} />
          </div>
        </Card>
      </div>

      {/* Main Content: File Browser + Editor */}
      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-4" style={{ minHeight: "calc(100vh - 480px)" }}>
        {/* File Browser Sidebar */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{
            padding: "16px 16px 12px", borderBottom: `1px solid ${T.border}`,
            background: `${T.surface}80`,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <BookOpen size={16} color={T.accent} />
                <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{t("knowledge.documents")}</span>
              </div>
              <Badge variant="info" size="xs">{files.length}</Badge>
            </div>

            {/* New Document */}
            <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createDraftFile()}
                placeholder={t("knowledge.newDocumentPlaceholder")}
                style={{ ...inputBase, fontSize: 11, flex: 1 }}
              />
              <button onClick={createDraftFile} style={{ ...btnPrimary, padding: "8px 10px" }} title="Neues Dokument">
                <Plus size={14} />
              </button>
            </div>

            {/* Search */}
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
              <input
                style={{ ...inputBase, paddingLeft: 34, fontSize: 11 }}
                placeholder="Dokument suchen…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 8 }} className="custom-scrollbar">
            {filteredFiles.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: T.textDim, fontSize: 12 }}>
                <BookOpen size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <div>{t("knowledge.noDocuments")}</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredFiles.map((f) => {
                  const isActive = selectedFile === f;
                  return (
                    <button
                      key={f}
                      onClick={() => setSelectedFile(f)}
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
                        }}>
                          {f}
                        </span>
                      </div>
                      <ChevronRight size={14} style={{
                        flexShrink: 0, color: isActive ? T.accent : T.textDim,
                        opacity: isActive ? 1 : 0.3,
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
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text, fontFamily: "monospace" }}>
                  {selectedFile || t("knowledge.selectFile")}
                </div>
                <div style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>
                  {dirty ? "Ungespeicherte Änderungen" : status}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder={t("knowledge.reasonPlaceholder")}
                style={{ ...inputBase, width: 240, fontSize: 11 }}
              />

              {conflict && (
                <>
                  <button onClick={() => selectedFile && void loadFile(selectedFile)} style={btnSecondary}>
                    Neu laden
                  </button>
                  <button onClick={() => void save({ force: true })} style={{ ...btnSecondary, borderColor: `${T.warning}60`, color: T.warning }}>
                    Überschreiben
                  </button>
                </>
              )}

              <button
                onClick={() => void save()}
                disabled={!selectedFile}
                style={{
                  ...btnPrimary,
                  opacity: !selectedFile ? 0.4 : 1,
                  padding: "8px 16px",
                }}
              >
                <Save size={14} /> Speichern
              </button>
            </div>
          </div>

          {/* Editor Body */}
          <div style={{ padding: 16, flex: 1, minHeight: 400 }}>
            {error && !selectedFile ? (
              <div style={{ color: T.danger, fontSize: 12, padding: 20 }}>{error}</div>
            ) : selectedFile ? (
              <TiptapEditor
                content={contentHtml}
                onChange={(next) => {
                  setContentHtml(next);
                  setDirty(true);
                }}
              />
            ) : (
              <div style={{
                display: "flex", flexDirection: "column",
                alignItems: "center", justifyContent: "center",
                height: "100%", padding: 48, textAlign: "center",
              }}>
                <div style={{
                  width: 72, height: 72, borderRadius: "50%",
                  background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center",
                  marginBottom: 20, border: `1px solid ${T.accent}30`,
                }}>
                  <BookOpen size={32} color={T.accent} strokeWidth={1.5} />
                </div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 8 }}>
                  Dokument auswählen
                </h3>
                <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 360, lineHeight: 1.6 }}>
                  {t("knowledge.selectFile")}
                </p>
              </div>
            )}
            {meta?.last_ingest_error && (
              <div style={{
                marginTop: 12, padding: "10px 14px", borderRadius: 10,
                background: T.dangerDim, border: `1px solid ${T.danger}30`,
                fontSize: 12, color: T.danger,
              }}>
                <AlertTriangle size={14} style={{ display: "inline", marginRight: 6, verticalAlign: "middle" }} />
                Ingest-Fehler: {meta.last_ingest_error}
              </div>
            )}
          </div>

          {/* Editor Footer */}
          {selectedFile && (
            <div style={{
              padding: "8px 20px", borderTop: `1px solid ${T.border}`,
              display: "flex", alignItems: "center", justifyContent: "space-between",
              background: `${T.surface}60`, fontSize: 10, color: T.textDim,
            }}>
              <span>Datei: {selectedFile}</span>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                {changeReason.trim().length >= 8 ? (
                  <Badge variant="success" size="xs">Bereit zum Speichern</Badge>
                ) : (
                  <Badge variant="warning" size="xs">Änderungsgrund erforderlich (min. 8 Zeichen)</Badge>
                )}
              </div>
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
            Wie funktioniert die Wissensdatenbank?
          </div>
          <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
            Die Wissensdatenbank speichert Dokumente, die der KI als Kontext für Gespräche dienen.
            Dokumente werden in Chunks aufgeteilt und vektorisiert, sodass die KI relevante Informationen
            semantisch abrufen kann. Verwenden Sie den Rich-Text-Editor, um Dokumente zu erstellen und zu bearbeiten.
            Nach dem Speichern wird automatisch eine Neu-Indizierung angestoßen.
          </p>
        </div>
      </Card>
    </div>
  );
}
