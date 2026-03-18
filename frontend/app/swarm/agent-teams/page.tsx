"use client";

import { useCallback, useEffect, useState } from "react";
import { Cpu, RefreshCw, Plus, Trash2, Save, Edit3, Play, Pause, XCircle, ChevronDown, ChevronRight } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type AgentRow = { id: string; display_name: string; description?: string | null };

type Team = {
  id: string;
  name: string;
  display_name: string;
  description: string | null;
  agent_ids: string[];
  orchestrator_name: string | null;
  state: string;
  updated_at: string | null;
};

const STATE_COLORS: Record<string, string> = {
  ACTIVE: T.success,
  PAUSED: T.warning,
  DISABLED: T.danger,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 5, background: `${color}22`, color }}>
      {label}
    </span>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", boxSizing: "border-box", padding: "8px 10px", fontSize: 13,
  color: T.text, background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, outline: "none",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p style={{ margin: "0 0 5px", fontSize: 11, fontWeight: 600, color: T.textDim }}>{label}</p>
      {children}
    </div>
  );
}

// ── Agent multi-select ────────────────────────────────────────────────────────

function AgentSelector({ all, selected, onChange }: { all: AgentRow[]; selected: string[]; onChange: (ids: string[]) => void }) {
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 200, overflowY: "auto", border: `1px solid ${T.border}`, borderRadius: 8, padding: 8 }}>
      {all.length === 0 && <p style={{ margin: 0, fontSize: 12, color: T.textDim }}>Keine Agents gefunden</p>}
      {all.map((a) => (
        <label key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", padding: "4px 6px", borderRadius: 6, background: selected.includes(a.id) ? T.accentDim : "transparent" }}>
          <input type="checkbox" checked={selected.includes(a.id)} onChange={() => toggle(a.id)} style={{ cursor: "pointer" }} />
          <span style={{ fontSize: 12, color: T.text, fontWeight: selected.includes(a.id) ? 600 : 400 }}>{a.display_name}</span>
          <span style={{ fontSize: 11, color: T.textDim, fontFamily: "monospace" }}>{a.id}</span>
        </label>
      ))}
    </div>
  );
}

// ── Create / Edit modal ───────────────────────────────────────────────────────

function TeamModal({
  allAgents,
  initial,
  onClose,
  onSaved,
}: {
  allAgents: AgentRow[];
  initial?: Team;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = !!initial;
  const [name, setName] = useState(initial?.name ?? "");
  const [displayName, setDisplayName] = useState(initial?.display_name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [agentIds, setAgentIds] = useState<string[]>(initial?.agent_ids ?? []);
  const [orchestratorName, setOrchestratorName] = useState(initial?.orchestrator_name ?? "");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const submit = async () => {
    if (!displayName) { setErr("Anzeigename ist pflicht"); return; }
    if (!isEdit && !name) { setErr("Interner Name ist pflicht"); return; }
    setSaving(true);
    setErr("");
    try {
      const url = isEdit ? `/admin/agent-teams/${initial!.name}` : "/admin/agent-teams";
      const method = isEdit ? "PATCH" : "POST";
      const body = isEdit
        ? { display_name: displayName, description: description || null, agent_ids: agentIds, orchestrator_name: orchestratorName || null }
        : { name, display_name: displayName, description: description || null, agent_ids: agentIds, orchestrator_name: orchestratorName || null };
      const res = await apiFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setErr(e.detail || String(res.status));
      } else {
        onSaved();
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
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16, padding: 28, width: "100%", maxWidth: 560, maxHeight: "90vh", overflowY: "auto" }}>
        <h2 style={{ margin: "0 0 20px", fontSize: 16, fontWeight: 700, color: T.text }}>
          {isEdit ? `Team bearbeiten: ${initial!.display_name}` : "Neues Agent-Team erstellen"}
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {!isEdit && (
            <Field label="Interner Name (slug)">
              <input
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
                placeholder="z.B. sales-team"
                style={inputStyle}
              />
            </Field>
          )}
          <Field label="Anzeigename">
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="z.B. Sales Team" style={inputStyle} />
          </Field>
          <Field label="Beschreibung">
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional" rows={2}
              style={{ ...inputStyle, resize: "vertical", lineHeight: 1.5 }} />
          </Field>
          <Field label="Agents auswählen">
            <AgentSelector all={allAgents} selected={agentIds} onChange={setAgentIds} />
          </Field>
          <Field label="Orchestrator (optional)">
            <input value={orchestratorName} onChange={(e) => setOrchestratorName(e.target.value)} placeholder="z.B. swarm-orchestrator" style={inputStyle} />
          </Field>
        </div>

        {err && <p style={{ margin: "12px 0 0", fontSize: 12, color: T.danger }}>{err}</p>}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 20 }}>
          <button onClick={onClose} style={{ padding: "7px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}>
            Abbrechen
          </button>
          <button onClick={() => void submit()} disabled={saving} style={{ padding: "7px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", background: T.accent, color: "#fff", border: "none" }}>
            {saving ? "Speichern…" : isEdit ? "Speichern" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AgentTeamsPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [allAgents, setAllAgents] = useState<AgentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Team | null>(null);
  const [expandAgents, setExpandAgents] = useState(false);
  const [toast, setToast] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [saving, setSaving] = useState(false);

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3000); };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [tRes, aRes] = await Promise.all([
        apiFetch("/admin/agent-teams"),
        apiFetch("/admin/swarm/agents"),
      ]);
      if (tRes.ok) setTeams(await tRes.json());
      if (aRes.ok) setAllAgents(await aRes.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const selectTeam = (t: Team) => {
    setSelected(t);
    setExpandAgents(false);
    setConfirmDelete(false);
  };

  const setState = async (state: string) => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/agent-teams/${selected.name}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); showToast(`Fehler: ${e.detail || res.status}`); }
      else {
        showToast(`State → ${state}`);
        await load();
        const fresh = teams.find((t) => t.name === selected.name);
        if (fresh) setSelected({ ...fresh, state });
      }
    } finally { setSaving(false); }
  };

  const deleteTeam = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/agent-teams/${selected.name}`, { method: "DELETE" });
      if (!res.ok) { const e = await res.json().catch(() => ({})); showToast(`Fehler: ${e.detail || res.status}`); }
      else { showToast(`"${selected.display_name}" gelöscht`); setSelected(null); await load(); }
    } finally { setSaving(false); setConfirmDelete(false); }
  };

  const agentMap = Object.fromEntries(allAgents.map((a) => [a.id, a]));

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1300, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: T.accentDim, borderRadius: 10, padding: 8 }}>
            <Cpu size={20} color={T.accent} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: T.text }}>Swarm Agent Teams</h1>
            <p style={{ margin: 0, fontSize: 13, color: T.textDim }}>{teams.length} Teams · System Admin only</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button onClick={() => void load()} style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: T.text }}>
            <RefreshCw size={14} /> Reload
          </button>
          <button onClick={() => setShowCreate(true)} style={{ background: T.accent, border: "none", borderRadius: 8, padding: "7px 14px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#fff", fontWeight: 600 }}>
            <Plus size={14} /> Neu
          </button>
        </div>
      </div>

      {toast && (
        <div style={{ background: T.accentDim, color: T.accent, border: `1px solid ${T.accent}40`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13, fontWeight: 600 }}>{toast}</div>
      )}
      {error && (
        <div style={{ background: "rgba(255,107,107,0.1)", color: T.danger, border: `1px solid ${T.danger}30`, borderRadius: 8, padding: "10px 16px", marginBottom: 20, fontSize: 13 }}>{error}</div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: selected ? "360px 1fr" : "1fr", gap: 20 }}>
        {/* List */}
        <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>Laden…</div>
          ) : teams.length === 0 ? (
            <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>
              <p style={{ margin: "0 0 12px" }}>Noch keine Teams vorhanden.</p>
              <button onClick={() => setShowCreate(true)} style={{ background: T.accent, border: "none", borderRadius: 8, padding: "7px 16px", cursor: "pointer", fontSize: 13, color: "#fff", fontWeight: 600 }}>
                Erstes Team erstellen
              </button>
            </div>
          ) : (
            teams.map((t) => (
              <div
                key={t.id}
                onClick={() => selectTeam(t)}
                style={{ padding: "14px 18px", borderBottom: `1px solid ${T.border}`, cursor: "pointer", background: selected?.name === t.name ? T.accentDim : "transparent", transition: "background 0.15s" }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text }}>{t.display_name}</p>
                    <p style={{ margin: "2px 0 0", fontSize: 11, color: T.textDim, fontFamily: "monospace" }}>{t.name}</p>
                  </div>
                  <Badge label={t.state} color={STATE_COLORS[t.state] || T.textDim} />
                </div>
                <p style={{ margin: "5px 0 0", fontSize: 11, color: T.textDim }}>
                  {t.agent_ids.length} Agents{t.orchestrator_name ? ` · ${t.orchestrator_name}` : ""}
                  {t.updated_at ? ` · ${new Date(t.updated_at).toLocaleDateString("de-DE")}` : ""}
                </p>
              </div>
            ))
          )}
        </div>

        {/* Detail */}
        {selected && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Header card */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: 20 }}>
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: T.text }}>{selected.display_name}</h3>
                  <p style={{ margin: "3px 0 0", fontSize: 11, fontFamily: "monospace", color: T.textDim }}>{selected.name}</p>
                  {selected.description && <p style={{ margin: "6px 0 0", fontSize: 12, color: T.textDim }}>{selected.description}</p>}
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <Badge label={selected.state} color={STATE_COLORS[selected.state] || T.textDim} />
                    {selected.orchestrator_name && <Badge label={selected.orchestrator_name} color={T.accent} />}
                    <Badge label={`${selected.agent_ids.length} Agents`} color={T.textDim} />
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    onClick={() => setShowEdit(true)}
                    style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text }}
                  >
                    <Edit3 size={13} /> Bearbeiten
                  </button>
                  {confirmDelete ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 12, color: T.danger, fontWeight: 600 }}>Sicher?</span>
                      <button onClick={() => void deleteTeam()} disabled={saving} style={{ padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: "pointer", border: "none", background: T.danger, color: "#fff" }}>Ja</button>
                      <button onClick={() => setConfirmDelete(false)} style={{ padding: "5px 10px", borderRadius: 6, fontSize: 12, cursor: "pointer", border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text }}>Nein</button>
                    </div>
                  ) : (
                    <button onClick={() => setConfirmDelete(true)} style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 12px", borderRadius: 8, fontSize: 12, cursor: "pointer", border: `1px solid ${T.danger}40`, background: "rgba(255,107,107,0.08)", color: T.danger }}>
                      <Trash2 size={13} /> Löschen
                    </button>
                  )}
                </div>
              </div>

              {/* State control */}
              <p style={{ margin: "0 0 8px", fontSize: 11, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.05em" }}>State</p>
              <div style={{ display: "flex", gap: 8 }}>
                {(["ACTIVE", "PAUSED", "DISABLED"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => s !== selected.state && void setState(s)}
                    disabled={saving || s === selected.state}
                    style={{
                      padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                      cursor: s === selected.state ? "default" : "pointer",
                      border: `1px solid ${s === selected.state ? STATE_COLORS[s] : T.border}`,
                      background: s === selected.state ? `${STATE_COLORS[s]}22` : T.surfaceAlt,
                      color: s === selected.state ? STATE_COLORS[s] : T.text,
                      opacity: s === selected.state ? 1 : 0.8,
                    }}
                  >
                    {s === "ACTIVE" && <Play size={10} style={{ marginRight: 4 }} />}
                    {s === "PAUSED" && <Pause size={10} style={{ marginRight: 4 }} />}
                    {s === "DISABLED" && <XCircle size={10} style={{ marginRight: 4 }} />}
                    {s}
                    {s === selected.state && <span style={{ marginLeft: 4, fontSize: 9, opacity: 0.7 }}>●</span>}
                  </button>
                ))}
              </div>
            </div>

            {/* Agent members */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <button
                onClick={() => setExpandAgents(!expandAgents)}
                style={{ width: "100%", padding: "14px 18px", background: "transparent", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", color: T.text }}
              >
                <span style={{ fontSize: 13, fontWeight: 600 }}>Team-Mitglieder ({selected.agent_ids.length})</span>
                {expandAgents ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
              {expandAgents && (
                <div style={{ borderTop: `1px solid ${T.border}`, padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
                  {selected.agent_ids.length === 0 ? (
                    <p style={{ margin: 0, fontSize: 13, color: T.textDim }}>Keine Agents zugewiesen</p>
                  ) : (
                    selected.agent_ids.map((id) => {
                      const agent = agentMap[id];
                      return (
                        <div key={id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: T.surfaceAlt, borderRadius: 8 }}>
                          <div style={{ width: 28, height: 28, borderRadius: 8, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            <Cpu size={14} color={T.accent} />
                          </div>
                          <div>
                            <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: T.text }}>{agent?.display_name || id}</p>
                            <p style={{ margin: 0, fontSize: 11, fontFamily: "monospace", color: T.textDim }}>{id}</p>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <TeamModal allAgents={allAgents} onClose={() => setShowCreate(false)} onSaved={() => void load()} />
      )}
      {showEdit && selected && (
        <TeamModal allAgents={allAgents} initial={selected} onClose={() => setShowEdit(false)} onSaved={async () => { await load(); const fresh = teams.find((t) => t.name === selected.name); if (fresh) setSelected(fresh); }} />
      )}
    </div>
  );
}
