"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  Cpu, Plus, Trash2, Edit3, CheckCircle2, XCircle, Eye, EyeOff,
  RefreshCcw, ArrowUpDown, Globe, Key, Zap, Save, X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";

type Provider = {
  id: number;
  slug: string;
  name: string;
  provider_type: string;
  api_base_url: string;
  has_api_key: boolean;
  supported_models: string[];
  default_model: string | null;
  is_active: boolean;
  priority: number;
  max_retries: number;
  timeout_seconds: number;
  created_at: string;
  updated_at: string;
};

type FormData = {
  slug: string;
  name: string;
  provider_type: string;
  api_base_url: string;
  api_key: string;
  supported_models: string;
  default_model: string;
  is_active: boolean;
  priority: number;
  max_retries: number;
  timeout_seconds: number;
};

const EMPTY_FORM: FormData = {
  slug: "", name: "", provider_type: "openai_compatible",
  api_base_url: "", api_key: "", supported_models: "",
  default_model: "", is_active: true, priority: 100,
  max_retries: 2, timeout_seconds: 60,
};

const PROVIDER_ICONS: Record<string, string> = {
  openai: "🤖", anthropic: "🧠", gemini: "💎", groq: "⚡",
  mistral: "🌊", xai: "🔮",
};

export function AIProviderManager() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/ai/providers");
      if (res.ok) setProviders(await res.json());
      else setError("Fehler beim Laden der Provider");
    } catch { setError("Netzwerkfehler"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setEditId(null);
    setShowForm(true);
    setShowKey(false);
  };

  const openEdit = (p: Provider) => {
    setForm({
      slug: p.slug, name: p.name, provider_type: p.provider_type,
      api_base_url: p.api_base_url, api_key: "",
      supported_models: p.supported_models.join(", "),
      default_model: p.default_model || "",
      is_active: p.is_active, priority: p.priority,
      max_retries: p.max_retries, timeout_seconds: p.timeout_seconds,
    });
    setEditId(p.id);
    setShowForm(true);
    setShowKey(false);
  };

  const handleSave = async () => {
    setSaving(true);
    const body: any = {
      ...form,
      supported_models: form.supported_models.split(",").map((s) => s.trim()).filter(Boolean),
    };
    if (!body.api_key) delete body.api_key;
    if (!body.default_model) body.default_model = body.supported_models[0] || null;

    try {
      const res = editId
        ? await apiFetch(`/admin/ai/providers/${editId}`, { method: "PUT", body: JSON.stringify(body) })
        : await apiFetch("/admin/ai/providers", { method: "POST", body: JSON.stringify(body) });
      if (res.ok) {
        setShowForm(false);
        load();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Speichern fehlgeschlagen");
      }
    } catch { setError("Netzwerkfehler"); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Provider wirklich deaktivieren?")) return;
    await apiFetch(`/admin/ai/providers/${id}`, { method: "DELETE" });
    load();
  };

  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "8px 12px", borderRadius: 8,
    border: `1px solid ${T.border}`, background: T.bg,
    color: T.text, fontSize: 13, outline: "none",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: 11, fontWeight: 600, color: T.textMuted,
    marginBottom: 4, display: "block",
  };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <SectionHeader title="LLM Provider Management" subtitle="Zentrale Verwaltung aller KI-Provider und API-Schlüssel" />
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <RefreshCcw size={14} /> Aktualisieren
          </button>
          <button onClick={openCreate} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600 }}>
            <Plus size={14} /> Provider hinzufügen
          </button>
        </div>
      </div>

      {error && <div style={{ padding: 12, borderRadius: 8, background: T.dangerDim, color: T.danger, fontSize: 12, marginBottom: 16 }}>{error}</div>}

      {/* Provider Form */}
      {showForm && (
        <div style={{ padding: 20, borderRadius: 12, border: `1px solid ${T.accent}30`, background: T.surfaceAlt, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{editId ? "Provider bearbeiten" : "Neuen Provider anlegen"}</span>
            <button onClick={() => setShowForm(false)} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}><X size={18} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Slug (eindeutig)</label>
              <input style={inputStyle} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="z.B. openai" disabled={!!editId} />
            </div>
            <div>
              <label style={labelStyle}>Anzeigename</label>
              <input style={inputStyle} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z.B. OpenAI" />
            </div>
            <div>
              <label style={labelStyle}>Provider-Typ</label>
              <select style={inputStyle} value={form.provider_type} onChange={(e) => setForm({ ...form, provider_type: e.target.value })}>
                <option value="openai_compatible">OpenAI-kompatibel</option>
                <option value="gemini">Google Gemini</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>API Base URL</label>
              <input style={inputStyle} value={form.api_base_url} onChange={(e) => setForm({ ...form, api_base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={labelStyle}>API Key {editId && "(leer lassen = bestehenden behalten)"}</label>
              <div style={{ position: "relative" }}>
                <input style={inputStyle} type={showKey ? "text" : "password"} value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-..." />
                <button onClick={() => setShowKey(!showKey)} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}>
                  {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={labelStyle}>Unterstützte Modelle (kommagetrennt)</label>
              <input style={inputStyle} value={form.supported_models} onChange={(e) => setForm({ ...form, supported_models: e.target.value })} placeholder="gpt-4o, gpt-4o-mini, o3-mini" />
            </div>
            <div>
              <label style={labelStyle}>Standard-Modell</label>
              <input style={inputStyle} value={form.default_model} onChange={(e) => setForm({ ...form, default_model: e.target.value })} placeholder="gpt-4o-mini" />
            </div>
            <div>
              <label style={labelStyle}>Priorität (1-999, niedriger = höher)</label>
              <input style={inputStyle} type="number" min={1} max={999} value={form.priority} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 100 })} />
            </div>
            <div>
              <label style={labelStyle}>Max Retries</label>
              <input style={inputStyle} type="number" min={0} max={10} value={form.max_retries} onChange={(e) => setForm({ ...form, max_retries: parseInt(e.target.value) || 2 })} />
            </div>
            <div>
              <label style={labelStyle}>Timeout (Sekunden)</label>
              <input style={inputStyle} type="number" min={5} max={300} value={form.timeout_seconds} onChange={(e) => setForm({ ...form, timeout_seconds: parseInt(e.target.value) || 60 })} />
            </div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
            <button onClick={() => setShowForm(false)} style={{ padding: "8px 16px", borderRadius: 8, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 12 }}>Abbrechen</button>
            <button onClick={handleSave} disabled={saving} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600, opacity: saving ? 0.6 : 1 }}>
              <Save size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />{saving ? "Speichern..." : "Speichern"}
            </button>
          </div>
        </div>
      )}

      {/* Provider List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textMuted, fontSize: 13 }}>Lade Provider...</div>
      ) : providers.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textDim, fontSize: 13 }}>Keine Provider konfiguriert. Klicke auf "Provider hinzufügen".</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {providers.map((p) => (
            <div key={p.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "14px 18px", borderRadius: 12,
              border: `1px solid ${p.is_active ? T.border : T.dangerDim}`,
              background: p.is_active ? T.surfaceAlt : `${T.dangerDim}`,
              transition: "all 0.2s ease",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <span style={{ fontSize: 22 }}>{PROVIDER_ICONS[p.slug] || "🔗"}</span>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{p.name}</span>
                    <Badge variant={p.is_active ? "success" : "danger"}>{p.is_active ? "Aktiv" : "Inaktiv"}</Badge>
                    <span style={{ fontSize: 10, color: T.textDim, fontFamily: "monospace" }}>{p.slug}</span>
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 4, fontSize: 11, color: T.textMuted }}>
                    <span><Globe size={10} style={{ marginRight: 3, verticalAlign: "middle" }} />{p.api_base_url}</span>
                    <span><Key size={10} style={{ marginRight: 3, verticalAlign: "middle" }} />{p.has_api_key ? "Konfiguriert" : "Fehlt"}</span>
                    <span><ArrowUpDown size={10} style={{ marginRight: 3, verticalAlign: "middle" }} />Prio {p.priority}</span>
                    <span><Zap size={10} style={{ marginRight: 3, verticalAlign: "middle" }} />{p.supported_models.length} Modelle</span>
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => openEdit(p)} style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 11 }}>
                  <Edit3 size={12} />
                </button>
                <button onClick={() => handleDelete(p.id)} style={{ padding: "6px 10px", borderRadius: 6, border: `1px solid ${T.dangerDim}`, background: "transparent", color: T.danger, cursor: "pointer", fontSize: 11 }}>
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
