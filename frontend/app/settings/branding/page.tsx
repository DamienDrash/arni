"use client";

import { useEffect, useState } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";

interface BrandingConfig {
  tenant_display_name: string;
  tenant_logo_url: string;
  tenant_primary_color: string;
  tenant_app_title: string;
  tenant_support_email: string;
  tenant_timezone: string;
  tenant_locale: string;
}

const FIELDS: Array<{
  key: keyof BrandingConfig;
  label: string;
  help: string;
  type?: "color" | "url" | "email" | "text";
}> = [
  { key: "tenant_app_title", label: "App-Titel", help: "Wird im Browser-Tab und Sidebar-Header angezeigt" },
  { key: "tenant_display_name", label: "Studio-Anzeigename", help: "Interner Name für Berichte und E-Mails" },
  { key: "tenant_logo_url", label: "Logo-URL", help: "HTTPS-Link zu deinem Logo (empfohlen: SVG oder PNG, 200×50px)", type: "url" },
  { key: "tenant_primary_color", label: "Primärfarbe", help: "Akzentfarbe für Buttons und aktive Elemente (Hex)", type: "color" },
  { key: "tenant_support_email", label: "Support-E-Mail", help: "Kontakt-E-Mail die Mitgliedern angezeigt wird", type: "email" },
  { key: "tenant_timezone", label: "Zeitzone", help: "IANA-Zeitzone, z.B. Europe/Berlin" },
  { key: "tenant_locale", label: "Locale", help: "BCP-47, z.B. de-DE oder en-US" },
];

export default function BrandingPage() {
  const [config, setConfig] = useState<Partial<BrandingConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/admin/tenant-preferences")
      .then((r) => r.json())
      .then((data) => setConfig(data as Partial<BrandingConfig>))
      .catch(() => setError("Fehler beim Laden der Einstellungen."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: keyof BrandingConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/tenant-preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(`Speichern fehlgeschlagen: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="p-8 text-gray-400">Wird geladen...</div>
    </div>
  );

  const primaryColor = (config.tenant_primary_color || "#3B82F6").trim();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="max-w-2xl mx-auto p-6 space-y-8" style={{ width: "100%" }}>
      <div>
        <h1 className="text-2xl font-bold text-white">Branding & White-Label</h1>
        <p className="text-gray-400 mt-1 text-sm">
          Passe ARIIA an dein Studio an — Logo, Farbe und App-Titel.
          Änderungen sind nach einem Browser-Reload sichtbar.
        </p>
      </div>

      {/* Live preview */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
        <p className="text-xs text-gray-500 uppercase tracking-widest font-medium">Vorschau</p>
        <div className="flex items-center gap-3">
          {config.tenant_logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={config.tenant_logo_url}
              alt="Logo"
              className="h-8 object-contain rounded"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
              style={{ backgroundColor: primaryColor }}
            >
              {(config.tenant_app_title || "A").charAt(0).toUpperCase()}
            </div>
          )}
          <div>
            <p className="text-sm font-semibold text-white">{config.tenant_app_title || "ARIIA"}</p>
            <p className="text-xs text-gray-400">{config.tenant_display_name || "Dein Studio"}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: primaryColor }} />
          <span className="text-xs text-gray-400 font-mono">{primaryColor}</span>
          <button
            className="text-xs px-3 py-1 rounded-lg text-white font-medium"
            style={{ backgroundColor: primaryColor }}
          >
            Beispiel Button
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <div className="space-y-5">
        {FIELDS.map(({ key, label, help, type }) => (
          <div key={key} className="space-y-1">
            <label className="block text-sm font-medium text-gray-200">{label}</label>
            <p className="text-xs text-gray-500">{help}</p>
            {type === "color" ? (
              <div className="flex items-center gap-3">
                <input
                  type="color"
                  value={config[key] || "#3B82F6"}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className="w-10 h-10 rounded cursor-pointer border border-gray-700 bg-gray-800"
                />
                <input
                  type="text"
                  value={config[key] || ""}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="#3B82F6"
                />
              </div>
            ) : (
              <input
                type={type || "text"}
                value={config[key] || ""}
                onChange={(e) => handleChange(key, e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-4 pt-4 border-t border-gray-800">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saving ? "Speichern..." : "Branding speichern"}
        </button>
        {saved && <span className="text-green-400 text-sm">Gespeichert.</span>}
      </div>
      </div>
    </div>
  );
}
