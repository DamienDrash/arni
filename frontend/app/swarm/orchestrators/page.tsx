"use client";

import { useCallback, useEffect, useState } from "react";
import { GitBranch, RefreshCw, Play, Pause, XCircle, ChevronDown, ChevronRight, RotateCcw } from "lucide-react";
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
      if (detRes.ok) setSelected(await detRes.json());
      if (vRes.ok) setVersions(await vRes.json());
      setExpandConfig(false);
      setExpandVersions(false);
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

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200, margin: "0 auto" }}>
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
        <button
          onClick={() => void load()}
          style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: T.text }}
        >
          <RefreshCw size={14} /> Reload
        </button>
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

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1.5fr" : "1fr", gap: 20 }}>
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

            {/* State control */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
              <h3 style={{ margin: "0 0 14px", fontSize: 14, fontWeight: 700, color: T.text }}>
                {selected.display_name}
                <span style={{ marginLeft: 8, fontSize: 11, fontWeight: 600, color: STATE_COLORS[selected.state] || T.textDim }}>
                  [{selected.state}]
                </span>
              </h3>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {["ACTIVE", "PAUSED", "DRAINING", "DISABLED"].map((s) => (
                  <button
                    key={s}
                    onClick={() => setStateAction(s === stateAction ? "" : s)}
                    disabled={s === selected.state}
                    style={{
                      padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: s === selected.state ? "default" : "pointer",
                      border: `1px solid ${stateAction === s ? STATE_COLORS[s] || T.accent : T.border}`,
                      background: stateAction === s ? `${STATE_COLORS[s] || T.accent}22` : T.surfaceAlt,
                      color: s === selected.state ? T.textDim : (stateAction === s ? STATE_COLORS[s] || T.accent : T.text),
                      opacity: s === selected.state ? 0.5 : 1,
                    }}
                  >
                    {s === "ACTIVE" && <Play size={10} style={{ marginRight: 4 }} />}
                    {s === "PAUSED" && <Pause size={10} style={{ marginRight: 4 }} />}
                    {s === "DISABLED" && <XCircle size={10} style={{ marginRight: 4 }} />}
                    {s}
                  </button>
                ))}
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

            {/* Config */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <button
                onClick={() => setExpandConfig(!expandConfig)}
                style={{ width: "100%", padding: "14px 18px", background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", color: T.text }}
              >
                <span style={{ fontSize: 13, fontWeight: 600 }}>Konfiguration (v{selected.config_version})</span>
                {expandConfig ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              {expandConfig && (
                <div style={{ padding: "0 18px 16px", borderTop: `1px solid ${T.border}` }}>
                  <pre style={{ margin: "12px 0 0", fontSize: 11, color: T.textDim, background: T.surfaceAlt, padding: 12, borderRadius: 8, overflow: "auto", maxHeight: 300, lineHeight: 1.6 }}>
                    {JSON.stringify(selected.config_current, null, 2)}
                  </pre>
                  {selected.guardrails && Object.keys(selected.guardrails).length > 0 && (
                    <>
                      <p style={{ margin: "12px 0 4px", fontSize: 11, fontWeight: 700, color: T.warning }}>Guardrails</p>
                      <pre style={{ margin: 0, fontSize: 11, color: T.textDim, background: T.surfaceAlt, padding: 12, borderRadius: 8, overflow: "auto", maxHeight: 200, lineHeight: 1.6 }}>
                        {JSON.stringify(selected.guardrails, null, 2)}
                      </pre>
                    </>
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
                <span style={{ fontSize: 13, fontWeight: 600 }}>Versionen ({versions.length})</span>
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
    </div>
  );
}
