"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GitBranch, RefreshCw, Play, Pause, XCircle, ChevronDown, ChevronRight, RotateCcw, Plus, Trash2, Save, Edit3, Shield } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type OrchestratorRow = {
  id: string;
  name: string;
  display_name: string;
  category: string;
  scope: string;
  state: string;
  config_version: number;
  updated_at: string | null;
};

type OrchestratorDetail = OrchestratorRow & {
  config_current: Record<string, unknown>;
  guardrails: Record<string, unknown> | null;
};

type VersionRow = {
  id: string;
  version: number;
  changed_by: number | null;
  changed_at: string | null;
  rollback_safe: boolean;
  change_summary: string | null;
};

const STATE_COLORS: Record<string, string> = {
  ACTIVE: T.success,
  PAUSED: T.warning,
  DRAINING: T.warning,
  DISABLED: T.danger,
};

const CATEGORY_COLORS: Record<string, string> = {
  SWARM: T.accent,
  CAMPAIGN: "#00b4d8",
  AUTOMATION: "#f77f00",
  SYNC: "#6c757d",
};

const VALID_TRANSITIONS: Record<string, string[]> = {
  ACTIVE: ["PAUSED", "DRAINING", "DISABLED"],
  PAUSED: ["ACTIVE", "DISABLED"],
  DRAINING: ["ACTIVE", "DISABLED"],
  DISABLED: [],
};

// ── Inline JSON editor ──────────────────────────────────────────────────────

function JsonEditor({
  value,
  onChange,
  readOnly = false,
  maxHeight = 300,
}: {
  value: Record<string, unknown>;
  onChange?: (v: Record<string, unknown>) => void;
  readOnly?: boolean;
  maxHeight?: number;
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [err, setErr] = useState("");

  useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setErr("");
  }, [value]);

  const handleChange = (raw: string) => {
    setText(raw);
    try {
      const parsed = JSON.parse(raw);
      setErr("");
      onChange?.(parsed);
    } catch {
      setErr("Ungültiges JSON");
    }
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={(e) => handleChange(e.target.value)}
        readOnly={readOnly}
        spellCheck={false}
        style={{
          width: "100%",
          boxSizing: "border-box",
          minHeight: 120,
          maxHeight,
          resize: "vertical",
          fontFamily: "monospace",
          fontSize: 11,
          lineHeight: 1.6,
          color: T.text,
          background: T.surfaceAlt,
          border: `1px solid ${err ? T.danger : T.border}`,
          borderRadius: 8,
          padding: 12,
          outline: "none",
        }}
      />
      {err && <p style={{ margin: "4px 0 0", fontSize: 11, color: T.danger }}>{err}</p>}
    </div>
  );
}

// ── Create modal ─────────────────────────────────────────────────────────────

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [category, setCategory] = useState("SWARM");
  const [scope, setScope] = useState("SYSTEM");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!name || !displayName) { setErr("Name und Anzeigename sind pflicht"); return; }
    setSaving(true);
    setErr("");
    try {
      const res = await apiFetch("/admin/orchestrators", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, display_name: displayName, category, scope, config }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setErr(e.detail || String(res.status));
      } else {
        onCreated();
        onClose();
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 28, width: "100%", maxWidth: 540, maxHeight: "90vh", overflowY: "auto" }}>
        <h2 style={{ margin: "0 0 20px", fontSize: 16, fontWeight: 700, color: T.text }}>Neuen Orchestrator erstellen</h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Field label="Interner Name (slug)">
            <input
              value={name}
              onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
              placeholder="z.B. my-orchestrator"
              style={inputStyle}
            />
          </Field>

          <Field label="Anzeigename">
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="z.B. My Orchestrator" style={inputStyle} />
          </Field>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <Field label="Kategorie">
              <select value={category} onChange={(e) => setCategory(e.target.value)} style={inputStyle}>
                {["SWARM", "CAMPAIGN", "AUTOMATION", "SYNC"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Scope">
              <select value={scope} onChange={(e) => setScope(e.target.value)} style={inputStyle}>
                <option value="SYSTEM">SYSTEM</option>
                <option value="TENANT">TENANT</option>
              </select>
            </Field>
          </div>

          <Field label="Initialer Config (JSON)">
            <JsonEditor value={config} onChange={setConfig} maxHeight={200} />
          </Field>
        </div>

        {err && <p style={{ margin: "12px 0 0", fontSize: 12, color: T.danger }}>{err}</p>}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ ...btnBase, background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}>
            Abbrechen
          </button>
          <button onClick={() => void submit()} disabled={saving} style={{ ...btnBase, background: T.accent, color: "#fff", border: "none" }}>
            {saving ? "Erstelle…" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{ margin: "0 0 5px", fontSize: 11, fontWeight: 600, color: T.textDim }}>{label}</p>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "8px 10px",
  fontSize: 13,
  color: T.text,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  borderRadius: 8,
  outline: "none",
};

const btnBase: React.CSSProperties = {
  padding: "7px 16px",
  borderRadius: 8,
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
};

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SwarmOrchestratorsPage() {
  const [rows, setRows] = useState<OrchestratorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<OrchestratorDetail | null>(null);
  const [versions, setVersions] = useState<VersionRow[]>([]);
  const [expandConfig, setExpandConfig] = useState(false);
  const [expandVersions, setExpandVersions] = useState(false);
  const [stateAction, setStateAction] = useState("");
  const [rollbackTarget, setRollbackTarget] = useState("");
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Config editing
  const [editingConfig, setEditingConfig] = useState(false);
  const [configDraft, setConfigDraft] = useState<Record<string, unknown>>({});
  const [changeSummary, setChangeSummary] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/admin/orchestrators");
      if (!res.ok) throw new Error(`${res.status}`);
      setRows(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const select = async (name: string) => {
    try {
      const [detRes, vRes] = await Promise.all([
        apiFetch(`/admin/orchestrators/${name}`),
        apiFetch(`/admin/orchestrators/${name}/versions`),
      ]);
      if (detRes.ok) {
        const det: OrchestratorDetail = await detRes.json();
        setSelected(det);
        setConfigDraft(det.config_current || {});
      }
      if (vRes.ok) setVersions(await vRes.json());
      setExpandConfig(false);
      setExpandVersions(false);
      setEditingConfig(false);
      setChangeSummary("");
    } catch {
      // ignore
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const applyState = async () => {
    if (!selected || !stateAction) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/orchestrators/${selected.name}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: stateAction }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(`Fehler: ${err.detail || res.status}`);
      } else {
        showToast(`State → ${stateAction}`);
        await load();
        await select(selected.name);
      }
    } finally {
      setSaving(false);
      setStateAction("");
    }
  };

  const applyRollback = async () => {
    if (!selected || !rollbackTarget) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/orchestrators/${selected.name}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_version: Number(rollbackTarget) }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(`Fehler: ${err.detail || res.status}`);
      } else {
        showToast("Rollback erfolgreich");
        await load();
        await select(selected.name);
      }
    } finally {
      setSaving(false);
      setRollbackTarget("");
    }
  };

  const saveConfig = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/orchestrators/${selected.name}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patch: configDraft, change_summary: changeSummary || "Manual config edit" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(`Fehler: ${err.detail || res.status}`);
      } else {
        showToast("Konfiguration gespeichert");
        setEditingConfig(false);
        setChangeSummary("");
        await load();
        await select(selected.name);
      }
    } finally {
      setSaving(false);
    }
  };

  const deleteOrchestrator = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/orchestrators/${selected.name}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(`Fehler: ${err.detail || res.status}`);
      } else {
        showToast(`"${selected.display_name}" gelöscht`);
        setSelected(null);
        setVersions([]);
        await load();
      }
    } finally {
      setSaving(false);
      setConfirmDelete(false);
    }
  };

  const allowedTargets = selected ? VALID_TRANSITIONS[selected.state] ?? [] : [];

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1300, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: T.accentDim, borderRadius: 10, padding: 8 }}>
            <GitBranch size={20} color={T.accent} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>Orchestrator Manager</h1>
            <p style={{ margin: 0, fontSize: 13, color: T.textDim }}>
              {rows.length} Orchestratoren · System Admin only
            </p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => void load()}
            style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: T.text }}
          >
            <RefreshCw size={14} /> Reload
          </button>
          <button
            onClick={() => setShowCreate(true)}
            style={{ background: T.accent, border: "none", borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#fff", fontWeight: 600 }}
          >
            <Plus size={14} /> Neu
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{ background: T.accentDim, color: T.accent, border: `1px solid ${T.accent}40`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13, fontWeight: 600 }}>
          {toast}
        </div>
      )}

      {error && (
        <div style={{ background: "rgba(255,107,107,0.1)", color: T.danger, border: `1px solid ${T.danger}30`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13 }}>
          {error}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: selected ? "380px 1fr" : "1fr", gap: 20 }}>
        {/* Left: Table */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>Laden…</div>
          ) : rows.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>Keine Orchestratoren gefunden</div>
          ) : (
            rows.map((row) => (
              <div
                key={row.id}
                onClick={() => void select(row.name)}
                style={{
                  padding: "14px 18px",
                  borderBottom: `1px solid ${T.border}`,
                  cursor: "pointer",
                  background: selected?.name === row.name ? T.accentDim : "transparent",
                  transition: "background 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text }}>{row.display_name}</p>
                    <p style={{ margin: "2px 0 0", fontSize: 11, color: T.textDim, fontFamily: "monospace" }}>{row.name}</p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5,
                      background: `${CATEGORY_COLORS[row.category] || T.accent}22`,
                      color: CATEGORY_COLORS[row.category] || T.accent,
                    }}>
                      {row.category}
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5,
                      background: `${STATE_COLORS[row.state] || T.textDim}22`,
                      color: STATE_COLORS[row.state] || T.textDim,
                    }}>
                      {row.state}
                    </span>
                  </div>
                </div>
                <p style={{ margin: "4px 0 0", fontSize: 11, color: T.textDim }}>
                  v{row.config_version} · {row.scope}
                  {row.updated_at ? ` · ${new Date(row.updated_at).toLocaleDateString("de-DE")}` : ""}
                </p>
              </div>
            ))
          )}
        </div>

        {/* Right: Detail */}
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Header + delete */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.text }}>
                    {selected.display_name}
                  </h3>
                  <p style={{ margin: "3px 0 0", fontSize: 11, fontFamily: "monospace", color: T.textDim }}>{selected.name}</p>
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5, background: `${CATEGORY_COLORS[selected.category] || T.accent}22`, color: CATEGORY_COLORS[selected.category] || T.accent }}>
                      {selected.category}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5, background: `${STATE_COLORS[selected.state] || T.textDim}22`, color: STATE_COLORS[selected.state] || T.textDim }}>
                      {selected.state}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 5, background: T.surfaceAlt, color: T.textDim }}>
                      {selected.scope}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 7px", borderRadius: 5, background: T.surfaceAlt, color: T.textDim }}>
                      v{selected.config_version}
                    </span>
                  </div>
                </div>
                {confirmDelete ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: T.danger, fontWeight: 600 }}>Sicher löschen?</span>
                    <button
                      onClick={() => void deleteOrchestrator()}
                      disabled={saving}
                      style={{ padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.danger, color: "#fff" }}
                    >
                      Ja, löschen
                    </button>
                    <button
                      onClick={() => setConfirmDelete(false)}
                      style={{ padding: "5px 12px", borderRadius: 6, fontSize: 12, cursor: "pointer", border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text }}
                    >
                      Abbrechen
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(true)}
                    style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${T.danger}40`, background: "rgba(255,107,107,0.08)", color: T.danger }}
                  >
                    <Trash2 size={13} /> Löschen
                  </button>
                )}
              </div>

              {/* State control */}
              <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.05em" }}>State-Transition</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["ACTIVE", "PAUSED", "DRAINING", "DISABLED"].map((s) => {
                  const isAllowed = allowedTargets.includes(s);
                  const isCurrent = s === selected.state;
                  const isSelected = stateAction === s;
                  return (
                    <button
                      key={s}
                      onClick={() => isAllowed && setStateAction(s === stateAction ? "" : s)}
                      disabled={!isAllowed}
                      title={!isAllowed && !isCurrent ? `Transition ${selected.state} → ${s} nicht erlaubt` : undefined}
                      style={{
                        padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                        cursor: isAllowed ? "pointer" : "default",
                        border: `1px solid ${isCurrent ? STATE_COLORS[s] || T.accent : isSelected ? STATE_COLORS[s] || T.accent : T.border}`,
                        background: isCurrent ? `${STATE_COLORS[s] || T.accent}22` : isSelected ? `${STATE_COLORS[s] || T.accent}22` : T.surfaceAlt,
                        color: isCurrent ? STATE_COLORS[s] || T.accent : !isAllowed ? T.textDim : isSelected ? STATE_COLORS[s] || T.accent : T.text,
                        opacity: !isAllowed && !isCurrent ? 0.4 : 1,
                      }}
                    >
                      {s === "ACTIVE" && <Play size={10} style={{ marginRight: 4 }} />}
                      {s === "PAUSED" && <Pause size={10} style={{ marginRight: 4 }} />}
                      {s === "DISABLED" && <XCircle size={10} style={{ marginRight: 4 }} />}
                      {s}
                      {isCurrent && <span style={{ marginLeft: 4, fontSize: 9, opacity: 0.7 }}>●</span>}
                    </button>
                  );
                })}
                {stateAction && (
                  <button
                    onClick={() => void applyState()}
                    disabled={saving}
                    style={{ padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.accent, color: "#fff" }}
                  >
                    {saving ? "…" : "Anwenden"}
                  </button>
                )}
              </div>
            </div>

            {/* Config Editor */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <button
                onClick={() => setExpandConfig(!expandConfig)}
                style={{ width: "100%", padding: "14px 18px", background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", color: T.text }}
              >
                <span style={{ fontSize: 13, fontWeight: 600 }}>Konfiguration (v{selected.config_version})</span>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {expandConfig && (
                    <span
                      onClick={(e) => { e.stopPropagation(); setEditingConfig(!editingConfig); if (editingConfig) setConfigDraft(selected.config_current || {}); }}
                      style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, fontWeight: 600, color: editingConfig ? T.warning : T.accent, cursor: "pointer" }}
                    >
                      <Edit3 size={12} /> {editingConfig ? "Abbrechen" : "Bearbeiten"}
                    </span>
                  )}
                  {expandConfig ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                </div>
              </button>
              {expandConfig && (
                <div style={{ padding: "0 18px 16px", borderTop: `1px solid ${T.border}` }}>
                  <div style={{ marginTop: 12 }}>
                    <JsonEditor
                      value={editingConfig ? configDraft : (selected.config_current || {})}
                      onChange={editingConfig ? setConfigDraft : undefined}
                      readOnly={!editingConfig}
                      maxHeight={350}
                    />
                  </div>

                  {editingConfig && (
                    <div style={{ marginTop: 12 }}>
                      <input
                        value={changeSummary}
                        onChange={(e) => setChangeSummary(e.target.value)}
                        placeholder="Change summary (optional)"
                        style={{ ...inputStyle, marginBottom: 10 }}
                      />
                      <button
                        onClick={() => void saveConfig()}
                        disabled={saving}
                        style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 16px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.success, color: "#fff" }}
                      >
                        <Save size={13} /> {saving ? "Speichern…" : "Config speichern"}
                      </button>
                    </div>
                  )}

                  {/* Guardrails */}
                  {selected.guardrails && Object.keys(selected.guardrails).length > 0 && (
                    <div style={{ marginTop: 16, padding: "12px 14px", borderRadius: 8, background: `${T.warning}11`, border: `1px solid ${T.warning}30` }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <Shield size={13} color={T.warning} />
                        <p style={{ margin: 0, fontSize: 11, fontWeight: 700, color: T.warning }}>Aktive Guardrails</p>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {Object.entries(selected.guardrails).map(([k, v]) => (
                          <div key={k} style={{ display: "flex", justifyContent: "space-between", fontSize: 11, fontFamily: "monospace" }}>
                            <span style={{ color: T.textDim }}>{k}</span>
                            <span style={{ color: T.warning, fontWeight: 600 }}>{JSON.stringify(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Versions + Rollback */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <button
                onClick={() => setExpandVersions(!expandVersions)}
                style={{ width: "100%", padding: "14px 18px", background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", color: T.text }}
              >
                <span style={{ fontSize: 13, fontWeight: 600 }}>Versionshistorie ({versions.length})</span>
                {expandVersions ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              {expandVersions && (
                <div style={{ borderTop: `1px solid ${T.border}` }}>
                  {versions.length === 0 ? (
                    <p style={{ padding: 16, margin: 0, fontSize: 13, color: T.textDim }}>Keine Versionen verfügbar</p>
                  ) : (
                    <>
                      {versions.map((v) => (
                        <div key={v.id} style={{ padding: "10px 18px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div>
                            <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>v{v.version}</span>
                            <span style={{ fontSize: 11, color: T.textDim, marginLeft: 8 }}>{v.change_summary || "—"}</span>
                            <span style={{ fontSize: 11, color: T.textDim, marginLeft: 8 }}>
                              {v.changed_at ? new Date(v.changed_at).toLocaleDateString("de-DE") : ""}
                            </span>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            {!v.rollback_safe && (
                              <span style={{ fontSize: 10, color: T.danger, fontWeight: 600 }}>unsafe</span>
                            )}
                            <input
                              type="radio"
                              name="rollback-version"
                              value={String(v.version)}
                              checked={rollbackTarget === String(v.version)}
                              onChange={(e) => setRollbackTarget(e.target.value)}
                              disabled={!v.rollback_safe}
                              style={{ cursor: v.rollback_safe ? "pointer" : "default" }}
                            />
                          </div>
                        </div>
                      ))}
                      {rollbackTarget && (
                        <div style={{ padding: "12px 18px" }}>
                          <button
                            onClick={() => void applyRollback()}
                            disabled={saving}
                            style={{ display: "flex", alignItems: "center", gap: 6, padding: "7px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.warning, color: "#000" }}
                          >
                            <RotateCcw size={12} />
                            Rollback auf v{rollbackTarget}
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreated={() => void load()}
        />
      )}
    </div>
  );
}
