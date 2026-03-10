"use client";

import { useEffect, useState } from "react";
import {
  Sparkles, Save, CheckCircle, AlertTriangle, RefreshCw, Trash2, Plus, Eye, EyeOff,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

interface TenantImageProvider {
  id: string;
  provider_id: string;
  preferred_model: string;
  created_at: string;
  has_api_key: boolean;
}

interface SystemProvider {
  id: string;
  name: string;
  description: string;
  supported_models: string[];
}

interface ProviderForm {
  provider_id: string;
  api_key: string;
  preferred_model: string;
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 10,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  transition: "border-color 0.2s ease",
};

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: T.textMuted,
  textTransform: "uppercase",
  fontWeight: 700,
  marginBottom: 4,
  display: "block",
  letterSpacing: "0.04em",
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: "none",
  cursor: "pointer",
};

export default function ImageProviderPage() {
  const role = getStoredUser()?.role;
  const isSystemAdmin = role === "system_admin";

  const [providers, setProviders] = useState<TenantImageProvider[]>([]);
  const [systemProviders, setSystemProviders] = useState<SystemProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showKeyFor, setShowKeyFor] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const [form, setForm] = useState<ProviderForm>({
    provider_id: "",
    api_key: "",
    preferred_model: "",
  });

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const tenantRes = await apiFetch("/admin/tenant/image-providers");
      if (!tenantRes.ok) throw new Error(`HTTP ${tenantRes.status}`);
      const tenantData = await tenantRes.json();
      setProviders(Array.isArray(tenantData) ? tenantData : (tenantData.providers ?? []));

      if (isSystemAdmin) {
        const sysRes = await apiFetch("/admin/system/image-providers");
        if (sysRes.ok) {
          const sysData = await sysRes.json();
          setSystemProviders(Array.isArray(sysData) ? sysData : (sysData.providers ?? []));
        }
      }
    } catch (e) {
      setError(`Fehler beim Laden: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    if (!form.provider_id.trim()) {
      setError("Bitte einen Provider auswählen.");
      return;
    }
    if (!form.api_key.trim()) {
      setError("API-Key ist erforderlich.");
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const res = await apiFetch("/admin/tenant/image-providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setSaved(true);
      setShowAddForm(false);
      setForm({ provider_id: "", api_key: "", preferred_model: "" });
      setTimeout(() => setSaved(false), 3000);
      await fetchData();
    } catch (e) {
      setError(`Speichern fehlgeschlagen: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    setError(null);
    try {
      const res = await apiFetch(`/admin/tenant/image-providers/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (e) {
      setError(`Entfernen fehlgeschlagen: ${e}`);
    } finally {
      setDeletingId(null);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SettingsSubnav />
        <div style={{ padding: 40, textAlign: "center", color: T.textMuted, fontSize: 13 }}>Wird geladen...</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SettingsSubnav />

      {/* Status messages */}
      {saved && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 16px", borderRadius: 10,
          background: T.successDim, border: `1px solid ${T.success}30`,
        }}>
          <CheckCircle size={16} color={T.success} />
          <span style={{ fontSize: 13, color: T.success, fontWeight: 600 }}>Bild-Provider gespeichert</span>
        </div>
      )}
      {error && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 16px", borderRadius: 10,
          background: T.dangerDim, border: `1px solid ${T.danger}30`,
        }}>
          <AlertTriangle size={16} color={T.danger} />
          <span style={{ fontSize: 13, color: T.danger, fontWeight: 600 }}>{error}</span>
        </div>
      )}

      {/* Configured providers */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: T.accentDim, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <Sparkles size={18} color={T.accent} />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>BYOK Bild-Provider</h2>
            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
              Eigene API-Keys für KI-Bildgenerierung (Bring Your Own Key)
            </p>
          </div>
          <button
            onClick={() => setShowAddForm((prev) => !prev)}
            style={{
              marginLeft: "auto",
              display: "flex", alignItems: "center", gap: 6,
              padding: "8px 16px", borderRadius: 8,
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              border: "none", color: "#fff", fontSize: 12, fontWeight: 700,
              cursor: "pointer",
            }}
          >
            <Plus size={13} />
            Provider hinzufügen
          </button>
        </div>

        {/* Add form */}
        {showAddForm && (
          <div style={{
            padding: 24, borderBottom: `1px solid ${T.border}`,
            background: `${T.accentDim}50`,
          }}>
            <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: "0 0 16px" }}>
              Neuen Provider konfigurieren
            </h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <label style={labelStyle}>Provider</label>
                {isSystemAdmin && systemProviders.length > 0 ? (
                  <select
                    style={selectStyle}
                    value={form.provider_id}
                    onChange={(e) => setForm((prev) => ({ ...prev, provider_id: e.target.value }))}
                  >
                    <option value="">Provider wählen...</option>
                    {systemProviders.map((sp) => (
                      <option key={sp.id} value={sp.id}>{sp.name}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    style={inputStyle}
                    placeholder="z.B. openai, stability, replicate"
                    value={form.provider_id}
                    onChange={(e) => setForm((prev) => ({ ...prev, provider_id: e.target.value }))}
                  />
                )}
              </div>
              <div>
                <label style={labelStyle}>Bevorzugtes Modell</label>
                <input
                  style={inputStyle}
                  placeholder="z.B. dall-e-3, stable-diffusion-xl"
                  value={form.preferred_model}
                  onChange={(e) => setForm((prev) => ({ ...prev, preferred_model: e.target.value }))}
                />
              </div>
              <div style={{ gridColumn: "span 2" }}>
                <label style={labelStyle}>API-Key</label>
                <div style={{ position: "relative" }}>
                  <input
                    type={showKeyFor === "new" ? "text" : "password"}
                    style={{ ...inputStyle, paddingRight: 42 }}
                    placeholder="sk-..."
                    value={form.api_key}
                    onChange={(e) => setForm((prev) => ({ ...prev, api_key: e.target.value }))}
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeyFor(showKeyFor === "new" ? null : "new")}
                    style={{
                      position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
                      background: "none", border: "none", cursor: "pointer", color: T.textMuted,
                      display: "flex", alignItems: "center",
                    }}
                  >
                    {showKeyFor === "new" ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 16 }}>
              <button
                onClick={() => { setShowAddForm(false); setForm({ provider_id: "", api_key: "", preferred_model: "" }); }}
                style={{
                  padding: "9px 18px", borderRadius: 8,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  color: T.textMuted, fontSize: 13, cursor: "pointer",
                }}
              >
                Abbrechen
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "9px 18px", borderRadius: 8,
                  background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                  border: "none", color: "#fff", fontSize: 13, fontWeight: 700,
                  cursor: saving ? "not-allowed" : "pointer",
                  opacity: saving ? 0.6 : 1,
                }}
              >
                {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
                Speichern
              </button>
            </div>
          </div>
        )}

        {/* Providers list */}
        {providers.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center" }}>
            <Sparkles size={40} color={T.textDim} style={{ margin: "0 auto 12px", display: "block" }} />
            <p style={{ fontSize: 14, color: T.textMuted, margin: "0 0 6px", fontWeight: 600 }}>
              Kein Bild-Provider konfiguriert
            </p>
            <p style={{ fontSize: 12, color: T.textDim, margin: 0 }}>
              Füge einen BYOK-Provider hinzu, um KI-Bilder zu generieren
            </p>
          </div>
        ) : (
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            {providers.map((p) => (
              <div
                key={p.id}
                style={{
                  display: "flex", alignItems: "center", gap: 16,
                  padding: "14px 16px", borderRadius: 10,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                }}
              >
                <div style={{
                  width: 36, height: 36, borderRadius: 8,
                  background: T.accentDim, display: "flex",
                  alignItems: "center", justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <Sparkles size={16} color={T.accent} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: 0 }}>{p.provider_id}</p>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                    {p.preferred_model ? `Modell: ${p.preferred_model}` : "Kein Modell spezifiziert"}
                    {" "}
                    &bull;
                    {" "}
                    {p.has_api_key ? (
                      <span style={{ color: T.success }}>API-Key konfiguriert</span>
                    ) : (
                      <span style={{ color: T.warning }}>Kein API-Key</span>
                    )}
                  </p>
                  <p style={{ fontSize: 10, color: T.textDim, margin: "2px 0 0" }}>
                    Hinzugefügt: {new Date(p.created_at).toLocaleDateString("de-DE")}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(p.id)}
                  disabled={deletingId === p.id}
                  title="Entfernen"
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "7px 12px", borderRadius: 7,
                    background: "none", border: `1px solid ${T.border}`,
                    color: T.danger, fontSize: 11, fontWeight: 600,
                    cursor: deletingId === p.id ? "not-allowed" : "pointer",
                    opacity: deletingId === p.id ? 0.5 : 1,
                  }}
                >
                  {deletingId === p.id
                    ? <RefreshCw size={12} style={{ animation: "spin 1s linear infinite" }} />
                    : <Trash2 size={12} />}
                  Entfernen
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
