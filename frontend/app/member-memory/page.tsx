"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { marked } from "marked";
import TurndownService from "turndown";
import { Brain, FileText, Plus, RefreshCw, Save } from "lucide-react";

import TiptapEditor from "@/components/TiptapEditor";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";

const turndownService = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });

type MemoryStatus = {
  cron_enabled: boolean;
  cron_expr: string;
  llm_enabled: boolean;
  llm_model: string;
  last_run_at: string;
  last_run_status: string;
  last_run_error: string;
};
type FilePayload = { filename: string; content: string; mtime?: number };
type TenantOption = { id: number; slug: string; name: string; is_active: boolean };

export default function MemberMemoryPage() {
  const currentUser = getStoredUser();
  const isSystemAdmin = currentUser?.role === "system_admin";

  const [tenants, setTenants] = useState<TenantOption[]>([]);
  const [selectedTenantSlug, setSelectedTenantSlug] = useState<string>("");

  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [contentHtml, setContentHtml] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [meta, setMeta] = useState<MemoryStatus | null>(null);
  const [loadedMtime, setLoadedMtime] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [changeReason, setChangeReason] = useState("");

  const runColor = (meta?.last_run_status || "").startsWith("error") ? T.danger : (meta?.last_run_status === "ok" ? T.success : T.textDim);
  const selectedExists = useMemo(() => (selectedFile ? files.includes(selectedFile) : false), [files, selectedFile]);

  const slugParam = isSystemAdmin && selectedTenantSlug ? `?tenant_slug=${encodeURIComponent(selectedTenantSlug)}` : "";

  // Load tenant list for system_admin
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

  const fetchFiles = useCallback(async () => {
    setError("");
    const res = await apiFetch(`/admin/member-memory${slugParam}`);
    if (!res.ok) {
      setError(`Dateiliste konnte nicht geladen werden (${res.status}).`);
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

  const fetchStatus = useCallback(async () => {
    const res = await apiFetch(`/admin/member-memory/status${slugParam}`);
    if (!res.ok) return;
    setMeta((await res.json()) as MemoryStatus);
  }, [slugParam]);

  const loadFile = useCallback(async (file: string) => {
    setStatus("Lade…");
    setError("");
    const res = await apiFetch(`/admin/member-memory/file/${file}${slugParam}`);
    if (!res.ok) {
      setStatus("");
      setError(`Datei konnte nicht geladen werden (${res.status}).`);
      return;
    }
    const data = (await res.json()) as FilePayload;
    const html = await marked.parse(data.content || "");
    setContentHtml(html);
    setLoadedMtime(typeof data.mtime === "number" ? data.mtime : null);
    setDirty(false);
    setConflict(false);
    setStatus("Geladen");
  }, [slugParam]);

  const save = useCallback(async (opts?: { force?: boolean; silent?: boolean }) => {
    if (!selectedFile) return;
    const reason = changeReason.trim();
    if (reason.length < 8) {
      if (opts?.silent) return;
      setError("Bitte begründe die Änderung (mind. 8 Zeichen).");
      setStatus("");
      return;
    }
    setStatus(opts?.silent ? "Autosave…" : "Speichere…");
    setError("");
    const markdown = turndownService.turndown(contentHtml || "");
    const res = await apiFetch(`/admin/member-memory/file/${selectedFile}${slugParam}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: markdown, base_mtime: opts?.force ? null : loadedMtime, reason }),
    });
    if (!res.ok) {
      if (res.status === 409) {
        setConflict(true);
        setStatus("Konflikt erkannt");
        setError("Datei wurde zwischenzeitlich geändert. Bitte neu laden oder überschreiben.");
        return;
      }
      setStatus("");
      setError(`Speichern fehlgeschlagen (${res.status}).`);
      return;
    }
    const body = (await res.json().catch(() => ({}))) as { mtime?: number };
    if (typeof body.mtime === "number") setLoadedMtime(body.mtime);
    setDirty(false);
    setConflict(false);
    setStatus(opts?.silent ? "Autosave gespeichert" : "Gespeichert");
    if (!files.includes(selectedFile)) setFiles((prev) => [selectedFile, ...prev]);
  }, [selectedFile, contentHtml, loadedMtime, files, changeReason, slugParam]);

  async function analyzeNow() {
    setAnalyzing(true);
    setStatus("Analyse läuft…");
    setError("");
    try {
      const res = await apiFetch("/admin/member-memory/analyze-now", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || `Analyse fehlgeschlagen (${res.status}).`);
        setStatus("");
        return;
      }
      setStatus("Analyse abgeschlossen");
      await Promise.all([fetchFiles(), fetchStatus()]);
    } finally {
      setAnalyzing(false);
    }
  }

  function createDraftFile() {
    if (!newName.trim()) return;
    const safe = `${newName.trim().replace(/\s+/g, "-").toLowerCase()}${newName.endsWith(".md") ? "" : ".md"}`;
    if (!files.includes(safe)) setFiles((prev) => [safe, ...prev]);
    setSelectedFile(safe);
    setContentHtml("<h1>Neue Member Memory</h1><p>Füge hier langlebigen Kontext ein…</p>");
    setLoadedMtime(null);
    setDirty(true);
    setConflict(false);
    setStatus("Neue Datei als Draft erstellt. Bitte speichern.");
    setNewName("");
  }

  // Reload when tenant selection changes
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
    Promise.all([fetchFiles(), fetchStatus()]).catch(() => setError("Dateiliste konnte nicht geladen werden."));
  }, [fetchFiles, fetchStatus, isSystemAdmin, selectedTenantSlug]);

  useEffect(() => {
    const timer = setInterval(() => void fetchStatus(), 30000);
    return () => clearInterval(timer);
  }, [fetchStatus]);

  useEffect(() => {
    if (!selectedFile || !selectedExists) return;
    loadFile(selectedFile).catch(() => setError("Datei konnte nicht geladen werden."));
  }, [loadFile, selectedExists, selectedFile]);

  useEffect(() => {
    if (!selectedFile || !dirty || conflict) return;
    const timer = setTimeout(() => {
      void save({ silent: true });
    }, 2500);
    return () => clearTimeout(timer);
  }, [conflict, dirty, selectedFile, contentHtml, save]);

  return (
    <div className="grid grid-cols-1 gap-4 min-h-[calc(100svh-12rem)]">

      {/* Tenant selector — system_admin only */}
      {isSystemAdmin && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10 }}>
          <span style={{ fontSize: 12, color: T.textDim, whiteSpace: "nowrap" }}>Tenant ansehen:</span>
          <select
            value={selectedTenantSlug}
            onChange={(e) => setSelectedTenantSlug(e.target.value)}
            style={{ flex: 1, maxWidth: 320, borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "7px 10px", fontSize: 13, cursor: "pointer" }}
          >
            {tenants.map((t) => (
              <option key={t.slug} value={t.slug}>{t.name} ({t.slug})</option>
            ))}
          </select>
          {selectedTenantSlug && (
            <span style={{ fontSize: 11, color: T.textDim }}>Pfad: tenants/{selectedTenantSlug}/members/</span>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
        <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Memory Files</div><div style={{ fontSize: 21, fontWeight: 800, color: T.text }}>{files.length}</div></Card>
        <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Scheduler</div><div style={{ fontSize: 14, fontWeight: 800, color: meta?.cron_enabled ? T.success : T.warning }}>{meta?.cron_enabled ? "Aktiv" : "Pausiert"}</div></Card>
        <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Last Run</div><div style={{ fontSize: 13, fontWeight: 700, color: runColor }}>{meta?.last_run_status || "never"}</div><div style={{ marginTop: 2, fontSize: 11, color: T.textMuted }}>{meta?.last_run_at ? new Date(meta.last_run_at).toLocaleString("de-DE") : "noch nie"}</div></Card>
        <Card style={{ padding: 12, display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
          <button
            onClick={() => void analyzeNow()}
            disabled={analyzing}
            style={{ border: "none", borderRadius: 8, background: T.accent, color: "#061018", fontWeight: 700, padding: "8px 10px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <RefreshCw size={13} /> {analyzing ? "Läuft…" : "Analyse jetzt"}
          </button>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 min-h-[calc(100svh-18rem)]">
        <Card style={{ padding: 14, overflow: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: T.text, marginBottom: 10 }}>
            <Brain size={16} /> <strong>Member Memories</strong>
          </div>

          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="member-id.md"
              style={{ flex: 1, borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "7px 8px", fontSize: 12 }}
            />
            <button onClick={createDraftFile} style={{ border: "none", borderRadius: 8, background: T.accentDim, color: T.text, padding: "0 10px", cursor: "pointer" }}>
              <Plus size={14} />
            </button>
          </div>

          <div style={{ display: "grid", gap: 4 }}>
            {files.length === 0 && !error && <div style={{ fontSize: 12, color: T.textDim }}>Keine Member-Memory Dateien vorhanden.</div>}
            {files.map((f) => (
              <button
                key={f}
                onClick={() => setSelectedFile(f)}
                style={{
                  borderRadius: 8,
                  border: `1px solid ${selectedFile === f ? `${T.accent}55` : T.border}`,
                  background: selectedFile === f ? T.accentDim : T.surfaceAlt,
                  color: T.text,
                  padding: "8px 10px",
                  textAlign: "left",
                  fontSize: 12,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <FileText size={14} />
                {f}
              </button>
            ))}
          </div>
        </Card>

        <Card style={{ padding: 0, display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ color: T.textDim, fontFamily: "monospace", fontSize: 12 }}>{selectedFile || "Datei wählen"}</div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder="Änderungsgrund (mind. 8 Zeichen)"
                style={{ width: 260, borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "7px 8px", fontSize: 12 }}
              />
              <div style={{ color: conflict ? T.warning : dirty ? T.text : T.textDim, fontSize: 12 }}>{conflict ? "Konflikt" : dirty ? "Ungespeichert" : status}</div>
              {conflict && (
                <>
                  <button
                    onClick={() => selectedFile && void loadFile(selectedFile)}
                    style={{ border: `1px solid ${T.border}`, borderRadius: 8, background: T.surfaceAlt, color: T.text, fontWeight: 600, padding: "7px 9px", cursor: "pointer" }}
                  >
                    Reload
                  </button>
                  <button
                    onClick={() => void save({ force: true })}
                    style={{ border: `1px solid ${T.border}`, borderRadius: 8, background: T.surfaceAlt, color: T.text, fontWeight: 600, padding: "7px 9px", cursor: "pointer" }}
                  >
                    Overwrite
                  </button>
                </>
              )}
              <button onClick={() => void save()} disabled={!selectedFile} style={{ border: "none", borderRadius: 8, background: T.accent, color: "#061018", fontWeight: 700, padding: "7px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
                <Save size={13} /> Speichern
              </button>
            </div>
          </div>
          <div style={{ padding: 14, flex: 1 }}>
            {error ? (
              <div style={{ color: T.danger, fontSize: 12 }}>{error}</div>
            ) : selectedFile ? (
              <TiptapEditor
                content={contentHtml}
                onChange={(next) => {
                  setContentHtml(next);
                  setDirty(true);
                }}
              />
            ) : (
              <div style={{ color: T.textDim, fontSize: 13 }}>Bitte links eine Datei auswählen.</div>
            )}
            {meta?.last_run_error && (
              <div style={{ marginTop: 10, fontSize: 12, color: T.danger }}>Analyzer Fehler: {meta.last_run_error}</div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
