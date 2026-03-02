"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  Bot, Plus, Edit3, Trash2, RefreshCcw, Save, X, Settings2,
  ChevronDown, ChevronRight, Cpu, Zap, Shield,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";

type AgentDef = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  agent_type: string;
  default_provider_slug: string | null;
  default_model: string | null;
  default_temperature: number;
  default_max_tokens: number;
  default_prompt_slug: string | null;
  capabilities: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type TenantOverride = {
  id: number;
  tenant_id: number;
  agent_definition_id: number;
  provider_slug_override: string | null;
  model_override: string | null;
  temperature_override: number | null;
  max_tokens_override: number | null;
  prompt_slug_override: string | null;
  is_enabled: boolean;
};

type FormData = {
  slug: string; name: string; description: string; agent_type: string;
  default_provider_slug: string; default_model: string;
  default_temperature: number; default_max_tokens: number;
  default_prompt_slug: string; is_active: boolean;
};

const EMPTY_FORM: FormData = {
  slug: "", name: "", description: "", agent_type: "conversational",
  default_provider_slug: "openai", default_model: "gpt-4o-mini",
  default_temperature: 0.7, default_max_tokens: 500,
  default_prompt_slug: "", is_active: true,
};

const AGENT_ICONS: Record<string, string> = {
  sales: "💼", support: "🎧", ops: "⚙️", router: "🔀",
  greeting: "👋", knowledge: "📚", booking: "📅",
};

export function AIAgentRegistry() {
  const [agents, setAgents] = useState<AgentDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [overrides, setOverrides] = useState<Record<number, TenantOverride[]>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/admin/ai/agents");
      if (res.ok) setAgents(await res.json());
      else setError("Fehler beim Laden");
    } catch { setError("Netzwerkfehler"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadOverrides = async (agentId: number) => {
    const res = await apiFetch(`/admin/ai/agents/${agentId}/overrides`);
    if (res.ok) {
      const data = await res.json();
      setOverrides((prev) => ({ ...prev, [agentId]: data }));
    }
  };

  const toggleExpand = (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (!overrides[id]) loadOverrides(id);
  };

  const openCreate = () => { setForm(EMPTY_FORM); setEditId(null); setShowForm(true); };

  const openEdit = (a: AgentDef) => {
    setForm({
      slug: a.slug, name: a.name, description: a.description || "",
      agent_type: a.agent_type,
      default_provider_slug: a.default_provider_slug || "",
      default_model: a.default_model || "",
      default_temperature: a.default_temperature,
      default_max_tokens: a.default_max_tokens,
      default_prompt_slug: a.default_prompt_slug || "",
      is_active: a.is_active,
    });
    setEditId(a.id);
    setShowForm(true);
  };

  const handleSave = async () => {
    setSaving(true);
    const body = { ...form };
    try {
      const res = editId
        ? await apiFetch(`/admin/ai/agents/${editId}`, { method: "PUT", body: JSON.stringify(body) })
        : await apiFetch("/admin/ai/agents", { method: "POST", body: JSON.stringify(body) });
      if (res.ok) { setShowForm(false); load(); }
      else { const d = await res.json().catch(() => ({})); setError(d.detail || "Fehler"); }
    } catch { setError("Netzwerkfehler"); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Agent-Definition wirklich löschen?")) return;
    await apiFetch(`/admin/ai/agents/${id}`, { method: "DELETE" });
    load();
  };

  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, color: T.text, fontSize: 13, outline: "none" };
  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 4, display: "block" };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <SectionHeader title="Agent Registry" subtitle="Zentrale Definition aller KI-Agenten mit Konfigurationsvererbung" />
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <RefreshCcw size={14} />
          </button>
          <button onClick={openCreate} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <Plus size={14} /> Agent hinzufügen
          </button>
        </div>
      </div>

      {error && <div style={{ padding: 12, borderRadius: 8, background: T.dangerDim, color: T.danger, fontSize: 12, marginBottom: 16 }}>{error} <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: T.danger, cursor: "pointer", marginLeft: 8 }}>×</button></div>}

      {/* Create/Edit Form */}
      {showForm && (
        <div style={{ padding: 20, borderRadius: 12, border: `1px solid ${T.accent}30`, background: T.surfaceAlt, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{editId ? "Agent bearbeiten" : "Neuen Agent definieren"}</span>
            <button onClick={() => setShowForm(false)} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}><X size={18} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Slug</label><input style={inputStyle} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="z.B. sales" disabled={!!editId} /></div>
            <div><label style={labelStyle}>Name</label><input style={inputStyle} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Sales Agent" /></div>
            <div><label style={labelStyle}>Agent-Typ</label>
              <select style={inputStyle} value={form.agent_type} onChange={(e) => setForm({ ...form, agent_type: e.target.value })}>
                <option value="conversational">Conversational</option>
                <option value="task">Task</option>
                <option value="router">Router</option>
                <option value="tool">Tool</option>
              </select>
            </div>
            <div><label style={labelStyle}>Standard-Provider</label><input style={inputStyle} value={form.default_provider_slug} onChange={(e) => setForm({ ...form, default_provider_slug: e.target.value })} placeholder="openai" /></div>
            <div><label style={labelStyle}>Standard-Modell</label><input style={inputStyle} value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} placeholder="gpt-4o-mini" /></div>
            <div><label style={labelStyle}>Standard-Prompt-Slug</label><input style={inputStyle} value={form.default_prompt_slug} onChange={(e) => setForm({ ...form, default_prompt_slug: e.target.value })} placeholder="sales/system" /></div>
            <div><label style={labelStyle}>Temperature</label><input style={inputStyle} type="number" step="0.1" min={0} max={2} value={form.default_temperature} onChange={(e) => setForm({ ...form, default_temperature: parseFloat(e.target.value) || 0.7 })} /></div>
            <div><label style={labelStyle}>Max Tokens</label><input style={inputStyle} type="number" min={50} max={16000} value={form.default_max_tokens} onChange={(e) => setForm({ ...form, default_max_tokens: parseInt(e.target.value) || 500 })} /></div>
            <div style={{ gridColumn: "1 / -1" }}><label style={labelStyle}>Beschreibung</label><input style={inputStyle} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
            <button onClick={() => setShowForm(false)} style={{ padding: "8px 16px", borderRadius: 8, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 12 }}>Abbrechen</button>
            <button onClick={handleSave} disabled={saving} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
              <Save size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />{saving ? "..." : "Speichern"}
            </button>
          </div>
        </div>
      )}

      {/* Agent List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textMuted, fontSize: 13 }}>Lade Agenten...</div>
      ) : agents.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textDim, fontSize: 13 }}>Keine Agenten definiert.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {agents.map((a) => (
            <div key={a.id} style={{ borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt, overflow: "hidden" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }} onClick={() => toggleExpand(a.id)}>
                  {expandedId === a.id ? <ChevronDown size={14} color={T.accent} /> : <ChevronRight size={14} color={T.textDim} />}
                  <span style={{ fontSize: 20 }}>{AGENT_ICONS[a.slug] || "🤖"}</span>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{a.name}</span>
                      <Badge variant={a.is_active ? "success" : "danger"}>{a.is_active ? "Aktiv" : "Inaktiv"}</Badge>
                      <span style={{ fontSize: 10, color: T.textDim, fontFamily: "monospace" }}>{a.slug}</span>
                    </div>
                    <div style={{ display: "flex", gap: 12, marginTop: 3, fontSize: 10, color: T.textMuted }}>
                      <span><Cpu size={9} style={{ marginRight: 2, verticalAlign: "middle" }} />{a.default_provider_slug || "—"} / {a.default_model || "—"}</span>
                      <span><Zap size={9} style={{ marginRight: 2, verticalAlign: "middle" }} />Temp: {a.default_temperature}</span>
                      <span><Shield size={9} style={{ marginRight: 2, verticalAlign: "middle" }} />{a.agent_type}</span>
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => openEdit(a)} style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer" }}><Edit3 size={12} /></button>
                  <button onClick={() => handleDelete(a.id)} style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.dangerDim}`, background: "transparent", color: T.danger, cursor: "pointer" }}><Trash2 size={12} /></button>
                </div>
              </div>

              {/* Expanded: Tenant Overrides */}
              {expandedId === a.id && (
                <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.border}` }}>
                  <div style={{ padding: "12px 0 8px", fontSize: 12, fontWeight: 600, color: T.textMuted }}>
                    <Settings2 size={12} style={{ marginRight: 6, verticalAlign: "middle" }} />Tenant-Overrides
                  </div>
                  {(overrides[a.id] || []).length === 0 ? (
                    <div style={{ fontSize: 11, color: T.textDim, padding: 8 }}>Keine Tenant-spezifischen Overrides konfiguriert.</div>
                  ) : (
                    (overrides[a.id] || []).map((o) => (
                      <div key={o.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, marginBottom: 4, fontSize: 11 }}>
                        <div style={{ display: "flex", gap: 12, color: T.textMuted }}>
                          <span>Tenant #{o.tenant_id}</span>
                          {o.provider_slug_override && <span>Provider: {o.provider_slug_override}</span>}
                          {o.model_override && <span>Model: {o.model_override}</span>}
                          {o.temperature_override != null && <span>Temp: {o.temperature_override}</span>}
                        </div>
                        <Badge variant={o.is_enabled ? "success" : "danger"}>{o.is_enabled ? "Aktiv" : "Deaktiviert"}</Badge>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
