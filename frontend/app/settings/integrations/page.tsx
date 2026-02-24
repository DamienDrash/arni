"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { CheckCircle2, Loader2, MinusCircle, PlugZap, TriangleAlert, QrCode, Globe, X, ExternalLink, ShieldCheck } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { FeatureGate } from "@/components/FeatureGate";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type ConnectorMeta = {
  id: string;
  name: string;
  category: string;
  description: string;
  status: "connected" | "disconnected" | "error";
  icon: string;
  fields: Array<{
    key: string;
    label: string;
    type: string;
    placeholder?: string;
    optional?: boolean;
    depends_on?: string;
  }>;
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "9px 10px",
  borderRadius: 9,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  outline: "none",
};

export default function SettingsIntegrationsPage() {
  const [catalog, setCatalog] = useState<ConnectorMeta[]>([]);
  const [activeConnector, setActiveConnector] = useState<string | null>(null);
  const [config, setConfig] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function fetchCatalog() {
    try {
      const res = await apiFetch("/admin/connector-hub/catalog");
      if (res.ok) setCatalog(await res.json());
    } catch (e) {
      setError("Fehler beim Laden des Katalogs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchCatalog();
  }, []);

  async function loadConfig(id: string) {
    setActiveConnector(id);
    setError("");
    setSuccess("");
    try {
      const res = await apiFetch(`/admin/connector-hub/${id}/config`);
      if (res.ok) setConfig(await res.json());
    } catch (e) {
      setError("Fehler beim Laden der Konfiguration.");
    }
  }

  async function saveConfig() {
    if (!activeConnector) return;
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch(`/admin/connector-hub/${activeConnector}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setSuccess("Konfiguration gespeichert.");
        fetchCatalog();
      } else {
        setError("Speichern fehlgeschlagen.");
      }
    } finally {
      setSaving(false);
    }
  }

  async function testConnector(id: string) {
    setTesting(id);
    try {
      const res = await apiFetch(`/admin/connector-hub/${id}/test`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        alert(`Test erfolgreich: ${data.message || "Verbindung OK"}`);
      } else {
        alert(`Fehler: ${data.detail || "Verbindung fehlgeschlagen"}`);
      }
    } finally {
      setTesting(null);
    }
  }

  const selectedMeta = useMemo(() => catalog.find(c => c.id === activeConnector), [catalog, activeConnector]);

  return (
    <div className="flex flex-col gap-4">
      <SettingsSubnav />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Connector Catalog */}
        <div className="lg:col-span-1 flex flex-col gap-4">
          <SectionHeader title="Connector Hub" subtitle="Verbinde ARIIA mit deinen Tools." />
          
          {loading ? (
            <div className="flex justify-center p-8"><Loader2 className="animate-spin" /></div>
          ) : (
            <div className="flex flex-col gap-2">
              {catalog.map(conn => (
                <button
                  key={conn.id}
                  onClick={() => loadConfig(conn.id)}
                  className={`p-4 rounded-xl border text-left transition-all ${
                    activeConnector === conn.id 
                      ? "bg-indigo-50 border-indigo-200 ring-2 ring-indigo-100" 
                      : "bg-white border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${conn.status === 'connected' ? 'bg-green-100 text-green-600' : 'bg-slate-100 text-slate-500'}`}>
                        <PlugZap size={18} />
                      </div>
                      <span className="font-bold text-slate-900">{conn.name}</span>
                    </div>
                    {conn.status === 'connected' && <CheckCircle2 size={16} className="text-green-500" />}
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-1">{conn.description}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Configuration Form */}
        <div className="lg:col-span-2">
          {activeConnector && selectedMeta ? (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">{selectedMeta.name} Konfiguration</h2>
                  <p className="text-sm text-slate-500">{selectedMeta.description}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => testConnector(activeConnector)}
                    disabled={!!testing}
                    className="px-4 py-2 border border-slate-200 rounded-lg text-sm font-semibold hover:bg-slate-50 flex items-center gap-2"
                  >
                    {testing === activeConnector ? <Loader2 size={14} className="animate-spin" /> : <Activity size={14} />}
                    Testen
                  </button>
                  <button
                    onClick={saveConfig}
                    disabled={saving}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 shadow-md shadow-indigo-100"
                  >
                    {saving ? "Speichere..." : "Speichern"}
                  </button>
                </div>
              </div>

              {error && <div className="mb-4 p-3 bg-red-50 text-red-600 rounded-lg text-sm flex items-center gap-2"><TriangleAlert size={16} /> {error}</div>}
              {success && <div className="mb-4 p-3 bg-green-50 text-green-600 rounded-lg text-sm flex items-center gap-2"><CheckCircle2 size={16} /> {success}</div>}

              <div className="flex flex-col gap-6">
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-100">
                  <input
                    type="checkbox"
                    id="enabled"
                    checked={config.enabled}
                    onChange={e => setConfig({ ...config, enabled: e.target.checked })}
                    className="w-4 h-4 text-indigo-600"
                  />
                  <label htmlFor="enabled" className="text-sm font-bold text-slate-700">Connector aktivieren</label>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {selectedMeta.fields.map(field => {
                    // Simple dependency check
                    if (field.depends_on) {
                      const [k, v] = field.depends_on.split("=");
                      if (config[k] !== v) return null;
                    }

                    return (
                      <div key={field.key} className="flex flex-col gap-1.5">
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">{field.label}</label>
                        {field.type === "select" ? (
                          <select
                            style={inputStyle}
                            value={config[field.key] || ""}
                            onChange={e => setConfig({ ...config, [field.key]: e.target.value })}
                          >
                            <option value="">Wählen...</option>
                            {(field as any).options?.map((opt: string) => (
                              <option key={opt} value={opt}>{opt.toUpperCase()}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type={field.type === "password" ? "password" : "text"}
                            style={inputStyle}
                            placeholder={field.placeholder}
                            value={config[field.key] || ""}
                            onChange={e => setConfig({ ...config, [field.key]: e.target.value })}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-slate-100">
                <h4 className="text-sm font-bold text-slate-900 mb-2 flex items-center gap-2">
                  <BookOpen size={16} className="text-slate-400" /> 
                  Einrichtungsanleitung
                </h4>
                <div className="prose prose-sm max-w-none text-slate-600">
                  <p>Um {selectedMeta.name} zu verbinden, folge bitte den Schritten in unserer Dokumentation.</p>
                  <button className="text-indigo-600 font-semibold flex items-center gap-1 hover:underline">
                    Doku öffnen <ExternalLink size={12} />
                  </button>
                </div>
              </div>
            </Card>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-12 text-center bg-slate-50 rounded-2xl border-2 border-dashed border-slate-200">
              <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center shadow-sm mb-4">
                <PlugZap size={32} className="text-slate-300" />
              </div>
              <h3 className="text-lg font-bold text-slate-400">Kein Connector ausgewählt</h3>
              <p className="text-sm text-slate-400 max-w-xs">Wähle links eine Integration aus, um sie zu konfigurieren.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
