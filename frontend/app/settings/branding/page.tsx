"use client";

import { useEffect, useState } from "react";
import {
  Palette, Save, CheckCircle, AlertTriangle, RefreshCw,
  Globe, Mail, Clock, Type, Image, Paintbrush,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";

interface BrandingConfig {
  tenant_display_name: string;
  tenant_logo_url: string;
  tenant_primary_color: string;
  tenant_app_title: string;
  tenant_support_email: string;
  tenant_timezone: string;
  tenant_locale: string;
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  boxSizing: "border-box" as const,
  transition: "border-color 0.2s ease",
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, color: T.textMuted, textTransform: "uppercase",
  fontWeight: 700, marginBottom: 4, display: "block", letterSpacing: "0.04em",
};

export default function BrandingPage() {
  const [config, setConfig] = useState<Partial<BrandingConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const { apiFetch } = require("@/lib/api");
    apiFetch("/admin/tenant-preferences")
      .then((r: Response) => r.json())
      .then((data: Partial<BrandingConfig>) => setConfig(data))
      .catch(() => setError("Fehler beim Laden der Einstellungen."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: keyof BrandingConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true); setError(null);
    try {
      const { apiFetch } = require("@/lib/api");
      const res = await apiFetch("/admin/tenant-preferences", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) { setError(`Speichern fehlgeschlagen: ${e}`); }
    finally { setSaving(false); }
  };

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SettingsSubnav />
      <div style={{ padding: 40, textAlign: "center", color: T.textMuted, fontSize: 13 }}>Wird geladen...</div>
    </div>
  );

  const primaryColor = (config.tenant_primary_color || "#6C5CE7").trim();

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SettingsSubnav />

      {/* Status Messages */}
      {saved && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "12px 16px",
          borderRadius: 10, background: T.successDim, border: `1px solid ${T.success}30`,
        }}>
          <CheckCircle size={16} color={T.success} />
          <span style={{ fontSize: 13, color: T.success, fontWeight: 600 }}>Branding gespeichert</span>
        </div>
      )}
      {error && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "12px 16px",
          borderRadius: 10, background: T.dangerDim, border: `1px solid ${T.danger}30`,
        }}>
          <AlertTriangle size={16} color={T.danger} />
          <span style={{ fontSize: 13, color: T.danger, fontWeight: 600 }}>{error}</span>
        </div>
      )}

      {/* Live Preview */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: `${primaryColor}15`, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <Palette size={18} color={primaryColor} />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>
              Live-Vorschau
            </h2>
            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
              Änderungen werden nach Browser-Reload sichtbar
            </p>
          </div>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{
            padding: 20, borderRadius: 12,
            background: T.bg, border: `1px solid ${T.border}`,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
              {config.tenant_logo_url ? (
                <img
                  src={config.tenant_logo_url}
                  alt="Logo"
                  style={{ height: 36, objectFit: "contain", borderRadius: 6 }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: primaryColor, display: "flex",
                  alignItems: "center", justifyContent: "center",
                  color: "#fff", fontWeight: 800, fontSize: 16,
                }}>
                  {(config.tenant_app_title || "A").charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: T.text }}>
                  {config.tenant_app_title || "ARIIA"}
                </div>
                <div style={{ fontSize: 12, color: T.textMuted }}>
                  {config.tenant_display_name || "Dein Studio"}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 20, height: 20, borderRadius: 6,
                background: primaryColor,
              }} />
              <span style={{ fontSize: 12, color: T.textMuted, fontFamily: "monospace" }}>
                {primaryColor}
              </span>
              <button style={{
                padding: "6px 16px", borderRadius: 8,
                background: primaryColor, color: "#fff",
                border: "none", fontSize: 12, fontWeight: 600,
              }}>
                Beispiel Button
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* Branding Fields */}
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
            <Paintbrush size={18} color={T.accent} />
          </div>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>
              Branding & White-Label
            </h2>
            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
              Passe ARIIA an dein Studio an
            </p>
          </div>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <BrandField icon={Type} label="App-Titel" hint="Wird im Browser-Tab und Sidebar-Header angezeigt">
              <input
                style={inputStyle}
                value={config.tenant_app_title || ""}
                onChange={(e) => handleChange("tenant_app_title", e.target.value)}
                placeholder="ARIIA"
              />
            </BrandField>
            <BrandField icon={Type} label="Studio-Anzeigename" hint="Interner Name für Berichte und E-Mails">
              <input
                style={inputStyle}
                value={config.tenant_display_name || ""}
                onChange={(e) => handleChange("tenant_display_name", e.target.value)}
                placeholder="Dein Studio"
              />
            </BrandField>
            <div style={{ gridColumn: "span 2" }}>
              <BrandField icon={Image} label="Logo-URL" hint="HTTPS-Link zu deinem Logo (empfohlen: SVG oder PNG, 200x50px)">
                <input
                  style={inputStyle}
                  value={config.tenant_logo_url || ""}
                  onChange={(e) => handleChange("tenant_logo_url", e.target.value)}
                  placeholder="https://example.com/logo.svg"
                />
              </BrandField>
            </div>
            <BrandField icon={Paintbrush} label="Primärfarbe" hint="Akzentfarbe für Buttons und aktive Elemente">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="color"
                  value={config.tenant_primary_color || "#6C5CE7"}
                  onChange={(e) => handleChange("tenant_primary_color", e.target.value)}
                  style={{
                    width: 40, height: 40, borderRadius: 8,
                    border: `1px solid ${T.border}`, background: T.surfaceAlt,
                    cursor: "pointer", padding: 2,
                  }}
                />
                <input
                  style={{ ...inputStyle, fontFamily: "monospace" }}
                  value={config.tenant_primary_color || ""}
                  onChange={(e) => handleChange("tenant_primary_color", e.target.value)}
                  placeholder="#6C5CE7"
                />
              </div>
            </BrandField>
            <BrandField icon={Mail} label="Support-E-Mail" hint="Kontakt-E-Mail die Kunden angezeigt wird">
              <input
                style={inputStyle}
                value={config.tenant_support_email || ""}
                onChange={(e) => handleChange("tenant_support_email", e.target.value)}
                placeholder="support@studio.de"
              />
            </BrandField>
            <BrandField icon={Clock} label="Zeitzone" hint="IANA-Zeitzone, z.B. Europe/Berlin">
              <input
                style={inputStyle}
                value={config.tenant_timezone || ""}
                onChange={(e) => handleChange("tenant_timezone", e.target.value)}
                placeholder="Europe/Berlin"
              />
            </BrandField>
            <BrandField icon={Globe} label="Locale" hint="BCP-47, z.B. de-DE oder en-US">
              <input
                style={inputStyle}
                value={config.tenant_locale || ""}
                onChange={(e) => handleChange("tenant_locale", e.target.value)}
                placeholder="de-DE"
              />
            </BrandField>
          </div>
        </div>

        <div style={{
          padding: "12px 24px", borderTop: `1px solid ${T.border}`,
          display: "flex", justifyContent: "flex-end",
        }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "10px 24px", borderRadius: 8,
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              color: "#fff", border: "none", fontSize: 13,
              fontWeight: 700, cursor: "pointer",
              opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
            Branding speichern
          </button>
        </div>
      </Card>
    </div>
  );
}

function BrandField({ icon: Icon, label, hint, children }: {
  icon: typeof Type; label: string; hint: string; children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Icon size={12} color={T.textDim} />
        <span style={labelStyle}>{label}</span>
      </div>
      <p style={{ fontSize: 10, color: T.textDim, margin: "0 0 2px", lineHeight: 1.4 }}>{hint}</p>
      {children}
    </div>
  );
}
