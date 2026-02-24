"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  CheckCircle2,
  Loader2,
  MinusCircle,
  PlugZap,
  TriangleAlert,
  QrCode,
  Globe,
  X,
  BookOpen,
  ExternalLink,
  ChevronRight,
  AlertTriangle,
  Search,
  RefreshCw,
  Trash2,
  ArrowLeft,
  Info,
  Shield,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

/* ─────────────────────────────────────────────────────────
   Types
   ───────────────────────────────────────────────────────── */

type FieldDef = {
  key: string;
  label: string;
  type: "text" | "password" | "url" | "select" | "toggle" | "readonly";
  placeholder: string;
  hint: string;
  required: boolean;
  options: { value: string; label: string }[] | null;
  default: string;
  sensitive: boolean;
};

type HealthInfo = {
  last_test_at: string;
  status: "ok" | "error" | "never";
  detail: string;
};

type ConnectorItem = {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  color: string;
  supports_test: boolean;
  supports_sync: boolean;
  webhook_path: string;
  docs_url: string;
  is_beta: boolean;
  prerequisites: string[];
  fields: FieldDef[];
  is_configured: boolean;
  health: HealthInfo;
};

type Category = {
  id: string;
  label: string;
  connectors: ConnectorItem[];
};

type SetupStep = {
  step: number;
  title: string;
  description: string;
  url: string;
  image_hint: string;
  warning: string;
};

type SetupDocs = {
  connector_id: string;
  name: string;
  description: string;
  docs_url: string;
  prerequisites: string[];
  steps: SetupStep[];
};

/* ─────────────────────────────────────────────────────────
   Styles
   ───────────────────────────────────────────────────────── */

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "9px 10px",
  borderRadius: 9,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  outline: "none",
  fontFamily: "inherit",
};

const btnBase: CSSProperties = {
  borderRadius: 8,
  border: `1px solid ${T.border}`,
  background: T.surface,
  color: T.text,
  fontSize: 12,
  fontWeight: 600,
  padding: "7px 12px",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  transition: "all 0.15s ease",
};

const btnPrimary: CSSProperties = {
  ...btnBase,
  background: T.accent,
  borderColor: T.accent,
  color: "#071018",
  fontWeight: 700,
};

const btnDanger: CSSProperties = {
  ...btnBase,
  borderColor: T.danger,
  color: T.danger,
};

const CATEGORY_ICONS: Record<string, string> = {
  messaging: "💬",
  email: "📧",
  voice: "📞",
  members: "👥",
  crm: "🔗",
  billing: "💳",
};

/* ─────────────────────────────────────────────────────────
   Main Page
   ───────────────────────────────────────────────────────── */

export default function SettingsIntegrationsPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  // Active connector detail view
  const [activeConnector, setActiveConnector] = useState<ConnectorItem | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [configLoading, setConfigLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Setup docs drawer
  const [docsOpen, setDocsOpen] = useState(false);
  const [docs, setDocs] = useState<SetupDocs | null>(null);
  const [docsLoading, setDocsLoading] = useState(false);

  // QR Modal (WhatsApp)
  const [qrOpen, setQrOpen] = useState(false);
  const [qrUrl, setQrUrl] = useState("");
  const [qrLoading, setQrLoading] = useState(false);

  /* ── Data Fetching ── */

  const fetchCatalog = useCallback(async () => {
    setError("");
    try {
      const res = await apiFetch("/admin/connector-hub/catalog");
      if (!res.ok) {
        setError(`Katalog konnte nicht geladen werden (${res.status}).`);
        return;
      }
      const data = await res.json();
      setCategories(data.categories || []);
    } catch (e) {
      setError(`Fehler: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCatalog();
  }, [fetchCatalog]);

  const openConnector = useCallback(async (connector: ConnectorItem) => {
    setActiveConnector(connector);
    setConfigLoading(true);
    setTestResult(null);
    setSaved(false);
    setError("");
    try {
      const res = await apiFetch(`/admin/connector-hub/${connector.id}/config`);
      if (res.ok) {
        const data = await res.json();
        setConfigValues(data.values || {});
      }
    } finally {
      setConfigLoading(false);
    }
  }, []);

  const closeConnector = useCallback(() => {
    setActiveConnector(null);
    setConfigValues({});
    setTestResult(null);
    setSaved(false);
    setDocsOpen(false);
    setDocs(null);
    void fetchCatalog();
  }, [fetchCatalog]);

  /* ── Actions ── */

  const saveConfig = useCallback(async () => {
    if (!activeConnector) return;
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch(`/admin/connector-hub/${activeConnector.id}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configValues),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || `Speichern fehlgeschlagen (${res.status}).`);
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } finally {
      setSaving(false);
    }
  }, [activeConnector, configValues]);

  const testConnection = useCallback(async () => {
    if (!activeConnector) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch(`/admin/connector-hub/${activeConnector.id}/test`, { method: "POST" });
      const data = await res.json();
      setTestResult({ ok: data.ok, detail: data.detail || data.error || "" });
    } catch (e) {
      setTestResult({ ok: false, detail: String(e) });
    } finally {
      setTesting(false);
    }
  }, [activeConnector]);

  const deleteConfig = useCallback(async () => {
    if (!activeConnector) return;
    if (!confirm(`Möchtest du die Konfiguration für "${activeConnector.name}" wirklich löschen?`)) return;
    setDeleting(true);
    try {
      await apiFetch(`/admin/connector-hub/${activeConnector.id}/config`, { method: "DELETE" });
      closeConnector();
    } finally {
      setDeleting(false);
    }
  }, [activeConnector, closeConnector]);

  const openDocs = useCallback(async (connectorId: string) => {
    setDocsOpen(true);
    setDocsLoading(true);
    try {
      const res = await apiFetch(`/admin/connector-hub/${connectorId}/setup-docs`);
      if (res.ok) {
        setDocs(await res.json());
      }
    } finally {
      setDocsLoading(false);
    }
  }, []);

  const showWhatsAppQr = useCallback(async () => {
    setQrLoading(true);
    setQrOpen(true);
    const timestamp = Date.now();
    setQrUrl(`/arni/proxy/admin/platform/whatsapp/qr-image?t=${timestamp}`);
    try {
      await apiFetch("/admin/platform/whatsapp/qr");
    } catch { /* ignore */ } finally {
      setQrLoading(false);
    }
  }, []);

  /* ── Filtering ── */

  const filteredCategories = useMemo(() => {
    if (!search.trim()) return categories;
    const q = search.toLowerCase();
    return categories
      .map((cat) => ({
        ...cat,
        connectors: cat.connectors.filter(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.description.toLowerCase().includes(q) ||
            c.id.toLowerCase().includes(q)
        ),
      }))
      .filter((cat) => cat.connectors.length > 0);
  }, [categories, search]);

  /* ── Render ── */

  if (loading) {
    return (
      <div style={{ padding: 32 }}>
        <SettingsSubnav />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10, padding: 60 }}>
          <Loader2 size={20} className="animate-spin" style={{ color: T.accent }} />
          <span style={{ color: T.textMuted, fontSize: 13 }}>Integrationen werden geladen…</span>
        </div>
      </div>
    );
  }

  /* ── Detail View (single connector) ── */
  if (activeConnector) {
    return (
      <div style={{ padding: 32 }}>
        <SettingsSubnav />

        {/* Back button */}
        <button
          onClick={closeConnector}
          style={{ ...btnBase, marginBottom: 16, background: "transparent", border: "none", padding: "4px 0", color: T.textMuted }}
        >
          <ArrowLeft size={14} /> Zurück zur Übersicht
        </button>

        <div style={{ display: "grid", gridTemplateColumns: docsOpen ? "1fr 380px" : "1fr", gap: 16, transition: "all 0.3s ease" }}>
          {/* Main config panel */}
          <Card style={{ padding: 0, overflow: "hidden" }}>
            {/* Header */}
            <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{
                  width: 40, height: 40, borderRadius: 10,
                  background: `${activeConnector.color}20`,
                  border: `1px solid ${activeConnector.color}40`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 14, fontWeight: 800, color: activeConnector.color,
                }}>
                  {activeConnector.icon}
                </div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.text, display: "flex", alignItems: "center", gap: 8 }}>
                    {activeConnector.name}
                    {activeConnector.is_beta && (
                      <span style={{ fontSize: 9, fontWeight: 700, color: T.warning, background: T.warningDim, padding: "2px 6px", borderRadius: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Beta</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>{activeConnector.description}</div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={() => void openDocs(activeConnector.id)} style={{ ...btnBase, color: T.accent, borderColor: T.accent }}>
                  <BookOpen size={13} /> Einrichtungsanleitung
                </button>
                {activeConnector.docs_url && (
                  <a href={activeConnector.docs_url} target="_blank" rel="noopener noreferrer" style={{ ...btnBase, textDecoration: "none" }}>
                    <ExternalLink size={12} /> API Docs
                  </a>
                )}
              </div>
            </div>

            {/* Prerequisites */}
            {activeConnector.prerequisites.length > 0 && (
              <div style={{ padding: "10px 20px", background: T.infoDim, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "flex-start", gap: 8 }}>
                <Info size={14} style={{ color: T.info, marginTop: 1, flexShrink: 0 }} />
                <div style={{ fontSize: 12, color: T.text, lineHeight: 1.5 }}>
                  <strong>Voraussetzungen:</strong> {activeConnector.prerequisites.join(" · ")}
                </div>
              </div>
            )}

            {/* Webhook URL */}
            {activeConnector.webhook_path && (
              <div style={{ padding: "10px 20px", background: T.surfaceAlt, borderBottom: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4 }}>Webhook URL</div>
                <code style={{ fontSize: 12, color: T.accent, background: T.bg, padding: "5px 8px", borderRadius: 6, display: "inline-block", fontFamily: "monospace", border: `1px solid ${T.border}` }}>
                  {"https://{deine-domain}"}{activeConnector.webhook_path}
                </code>
              </div>
            )}

            {/* Config Fields */}
            <div style={{ padding: 20 }}>
              {configLoading ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 20, justifyContent: "center" }}>
                  <Loader2 size={16} className="animate-spin" style={{ color: T.accent }} />
                  <span style={{ fontSize: 12, color: T.textMuted }}>Konfiguration wird geladen…</span>
                </div>
              ) : (
                <div style={{ display: "grid", gap: 14 }}>
                  {activeConnector.fields.map((field) => (
                    <div key={field.key}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <label style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>
                          {field.label}
                          {field.required && <span style={{ color: T.danger, marginLeft: 2 }}>*</span>}
                        </label>
                        {field.sensitive && <Shield size={10} style={{ color: T.textDim }} />}
                      </div>
                      {field.hint && (
                        <div style={{ fontSize: 11, color: T.textDim, lineHeight: 1.4, marginBottom: 4 }}>{field.hint}</div>
                      )}
                      {field.type === "select" && field.options ? (
                        <select
                          style={{ ...inputStyle, cursor: "pointer" }}
                          value={configValues[field.key] || field.default}
                          onChange={(e) => setConfigValues((v) => ({ ...v, [field.key]: e.target.value }))}
                        >
                          {field.options.map((opt) => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                      ) : field.type === "toggle" ? (
                        <select
                          style={{ ...inputStyle, cursor: "pointer" }}
                          value={configValues[field.key] || field.default || "false"}
                          onChange={(e) => setConfigValues((v) => ({ ...v, [field.key]: e.target.value }))}
                        >
                          <option value="true">Aktiviert</option>
                          <option value="false">Deaktiviert</option>
                        </select>
                      ) : (
                        <input
                          type={field.type === "password" ? "password" : "text"}
                          style={inputStyle}
                          value={configValues[field.key] || ""}
                          onChange={(e) => setConfigValues((v) => ({ ...v, [field.key]: e.target.value }))}
                          placeholder={field.placeholder}
                        />
                      )}
                    </div>
                  ))}

                  {/* WhatsApp QR button */}
                  {activeConnector.id === "whatsapp" && (configValues.mode || "qr") === "qr" && (
                    <button onClick={() => void showWhatsAppQr()} style={{ ...btnBase, justifyContent: "center", padding: "10px 16px" }}>
                      <QrCode size={14} /> QR-Code anzeigen & verbinden
                    </button>
                  )}

                  {activeConnector.fields.length === 0 && (
                    <div style={{ fontSize: 13, color: T.textMuted, textAlign: "center", padding: 20 }}>
                      Dieser Connector benötigt keine manuelle Konfiguration.
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Action Bar */}
            <div style={{ padding: "12px 20px", borderTop: `1px solid ${T.border}`, background: T.surfaceAlt, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", gap: 8 }}>
                {activeConnector.fields.length > 0 && (
                  <button onClick={() => void saveConfig()} disabled={saving} style={btnPrimary}>
                    {saving ? <><Loader2 size={12} className="animate-spin" /> Speichern…</> : saved ? <><CheckCircle2 size={12} /> Gespeichert</> : "Konfiguration speichern"}
                  </button>
                )}
                {activeConnector.supports_test && (
                  <button onClick={() => void testConnection()} disabled={testing} style={btnBase}>
                    {testing ? <><Loader2 size={12} className="animate-spin" /> Teste…</> : <><RefreshCw size={12} /> Verbindung testen</>}
                  </button>
                )}
              </div>
              <button onClick={() => void deleteConfig()} disabled={deleting} style={btnDanger}>
                <Trash2 size={12} /> Zurücksetzen
              </button>
            </div>

            {/* Test Result */}
            {testResult && (
              <div style={{
                padding: "10px 20px",
                borderTop: `1px solid ${T.border}`,
                background: testResult.ok ? T.successDim : T.dangerDim,
                display: "flex", alignItems: "center", gap: 8,
              }}>
                {testResult.ok ? <CheckCircle2 size={14} style={{ color: T.success }} /> : <TriangleAlert size={14} style={{ color: T.danger }} />}
                <span style={{ fontSize: 12, color: testResult.ok ? T.success : T.danger, fontWeight: 600 }}>
                  {testResult.detail}
                </span>
              </div>
            )}

            {/* Health Status */}
            {activeConnector.health.status !== "never" && (
              <div style={{ padding: "10px 20px", borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 8 }}>
                {activeConnector.health.status === "ok" ? (
                  <CheckCircle2 size={13} style={{ color: T.success }} />
                ) : (
                  <TriangleAlert size={13} style={{ color: T.danger }} />
                )}
                <span style={{ fontSize: 11, color: T.textMuted }}>
                  Letzter Test: {activeConnector.health.last_test_at ? new Date(activeConnector.health.last_test_at).toLocaleString("de-DE") : "—"}
                  {activeConnector.health.detail && ` — ${activeConnector.health.detail}`}
                </span>
              </div>
            )}

            {error && (
              <div style={{ padding: "10px 20px", borderTop: `1px solid ${T.border}`, background: T.dangerDim, color: T.danger, fontSize: 12 }}>
                {error}
              </div>
            )}
          </Card>

          {/* Setup Docs Sidebar */}
          {docsOpen && (
            <Card style={{ padding: 0, overflow: "hidden", position: "sticky", top: 20, maxHeight: "calc(100vh - 120px)", overflowY: "auto" }}>
              <div style={{ padding: "14px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, background: T.surface, zIndex: 2 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <BookOpen size={14} style={{ color: T.accent }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Einrichtungsanleitung</span>
                </div>
                <button onClick={() => setDocsOpen(false)} style={{ border: "none", background: "none", color: T.textDim, cursor: "pointer", padding: 4 }}>
                  <X size={14} />
                </button>
              </div>

              {docsLoading ? (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: 40 }}>
                  <Loader2 size={16} className="animate-spin" style={{ color: T.accent }} />
                </div>
              ) : docs ? (
                <div style={{ padding: 16 }}>
                  {/* Prerequisites */}
                  {docs.prerequisites.length > 0 && (
                    <div style={{ marginBottom: 16, padding: 10, background: T.warningDim, borderRadius: 8, border: `1px solid rgba(255,170,0,0.2)` }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: T.warning, marginBottom: 4 }}>Voraussetzungen</div>
                      {docs.prerequisites.map((p, i) => (
                        <div key={i} style={{ fontSize: 11, color: T.text, lineHeight: 1.5, paddingLeft: 8 }}>• {p}</div>
                      ))}
                    </div>
                  )}

                  {/* Steps */}
                  <div style={{ display: "grid", gap: 0 }}>
                    {docs.steps.map((step, idx) => (
                      <div key={step.step} style={{ position: "relative", paddingLeft: 28, paddingBottom: idx < docs.steps.length - 1 ? 20 : 0 }}>
                        {/* Timeline line */}
                        {idx < docs.steps.length - 1 && (
                          <div style={{ position: "absolute", left: 11, top: 22, bottom: 0, width: 1, background: T.border }} />
                        )}
                        {/* Step number */}
                        <div style={{
                          position: "absolute", left: 0, top: 0,
                          width: 22, height: 22, borderRadius: "50%",
                          background: T.accentDim, border: `1px solid ${T.accent}`,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 10, fontWeight: 800, color: T.accent,
                        }}>
                          {step.step}
                        </div>
                        {/* Content */}
                        <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4 }}>{step.title}</div>
                        <div style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.6 }}>{step.description}</div>
                        {step.warning && (
                          <div style={{ marginTop: 6, padding: "6px 8px", background: T.warningDim, borderRadius: 6, display: "flex", alignItems: "flex-start", gap: 6 }}>
                            <AlertTriangle size={11} style={{ color: T.warning, marginTop: 1, flexShrink: 0 }} />
                            <span style={{ fontSize: 10, color: T.warning, lineHeight: 1.5 }}>{step.warning}</span>
                          </div>
                        )}
                        {step.url && !step.url.includes("{") && (
                          <a href={step.url} target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: 4, marginTop: 6, fontSize: 11, color: T.accent, textDecoration: "none" }}>
                            <ExternalLink size={10} /> Link öffnen
                          </a>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Official Docs Link */}
                  {docs.docs_url && (
                    <a
                      href={docs.docs_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: "flex", alignItems: "center", gap: 8, marginTop: 20,
                        padding: "10px 12px", borderRadius: 8, background: T.surfaceAlt,
                        border: `1px solid ${T.border}`, textDecoration: "none",
                        fontSize: 12, color: T.text,
                      }}
                    >
                      <Globe size={14} style={{ color: T.accent }} />
                      <div>
                        <div style={{ fontWeight: 700 }}>Offizielle Dokumentation</div>
                        <div style={{ fontSize: 10, color: T.textDim, marginTop: 1 }}>{docs.docs_url}</div>
                      </div>
                      <ExternalLink size={12} style={{ marginLeft: "auto", color: T.textDim }} />
                    </a>
                  )}
                </div>
              ) : (
                <div style={{ padding: 20, textAlign: "center", color: T.textMuted, fontSize: 12 }}>
                  Dokumentation konnte nicht geladen werden.
                </div>
              )}
            </Card>
          )}
        </div>

        {/* WhatsApp QR Modal */}
        <Modal open={qrOpen} onClose={() => setQrOpen(false)} title="WhatsApp Verbindung herstellen" subtitle="Scanne diesen Code mit deinem Smartphone" width="min(440px, 100%)">
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20, padding: "10px 0" }}>
            {qrLoading ? (
              <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
                <Loader2 size={40} className="animate-spin" style={{ color: T.accent }} />
                <span style={{ fontSize: 13, color: T.textMuted }}>QR-Code wird generiert...</span>
              </div>
            ) : qrUrl ? (
              <>
                <div style={{ padding: 12, background: "white", borderRadius: 16, border: `1px solid ${T.border}`, boxShadow: "0 10px 25px rgba(0,0,0,0.1)" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={qrUrl} alt="WhatsApp QR Code" style={{ width: 240, height: 240 }} />
                </div>
                <p style={{ fontSize: 12, color: T.textMuted, textAlign: "center", lineHeight: 1.6 }}>
                  Öffne WhatsApp auf deinem Telefon → Menü oder Einstellungen → Verknüpfte Geräte → Gerät hinzufügen.
                </p>
              </>
            ) : null}
            <div style={{ display: "flex", gap: 10, width: "100%" }}>
              <button onClick={() => void showWhatsAppQr()} style={{ ...btnBase, flex: 1, justifyContent: "center" }}>QR-Code erneuern</button>
              <button onClick={() => setQrOpen(false)} style={{ ...btnPrimary, flex: 1, justifyContent: "center" }}>Schließen</button>
            </div>
          </div>
        </Modal>
      </div>
    );
  }

  /* ── Catalog Overview ── */
  return (
    <div style={{ padding: 32 }}>
      <SettingsSubnav />

      <Card style={{ padding: 20 }}>
        {/* Page Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <SectionHeader
            title="Integrationen"
            subtitle="Verbinde ARIIA mit deinen bestehenden Plattformen und Kommunikationskanälen."
          />
          <div style={{ position: "relative" }}>
            <Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: T.textDim }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Integration suchen…"
              style={{ ...inputStyle, paddingLeft: 32, width: 220 }}
            />
          </div>
        </div>

        {error && (
          <div style={{ padding: "10px 14px", background: T.dangerDim, borderRadius: 8, color: T.danger, fontSize: 12, marginBottom: 16 }}>
            {error}
          </div>
        )}

        {/* Categories */}
        <div style={{ display: "grid", gap: 24 }}>
          {filteredCategories.map((cat) => (
            <div key={cat.id}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                <span style={{ fontSize: 16 }}>{CATEGORY_ICONS[cat.id] || "🔌"}</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.text, letterSpacing: "0.02em" }}>{cat.label}</span>
                <span style={{ fontSize: 11, color: T.textDim }}>({cat.connectors.length})</span>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
                {cat.connectors.map((conn) => (
                  <ConnectorCard
                    key={conn.id}
                    connector={conn}
                    onOpen={() => void openConnector(conn)}
                    onDocs={() => {
                      void openConnector(conn).then(() => openDocs(conn.id));
                    }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        {filteredCategories.length === 0 && !loading && (
          <div style={{ textAlign: "center", padding: 40, color: T.textMuted, fontSize: 13 }}>
            {search ? `Keine Integrationen für "${search}" gefunden.` : "Keine Integrationen verfügbar."}
          </div>
        )}
      </Card>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   Connector Card Component
   ───────────────────────────────────────────────────────── */

function ConnectorCard({
  connector,
  onOpen,
  onDocs,
}: {
  connector: ConnectorItem;
  onOpen: () => void;
  onDocs: () => void;
}) {
  const statusColor =
    connector.health.status === "ok" ? T.success :
    connector.health.status === "error" ? T.danger : T.textDim;

  return (
    <Card
      style={{
        padding: 14,
        background: T.surfaceAlt,
        cursor: "pointer",
        transition: "all 0.15s ease",
        border: `1px solid ${connector.is_configured ? `${connector.color}30` : T.border}`,
      }}
      onClick={onOpen}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {/* Icon */}
          <div style={{
            width: 34, height: 34, borderRadius: 8,
            background: `${connector.color}18`,
            border: `1px solid ${connector.color}30`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 11, fontWeight: 800, color: connector.color,
            flexShrink: 0,
          }}>
            {connector.icon}
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text, display: "flex", alignItems: "center", gap: 6 }}>
              {connector.name}
              {connector.is_beta && (
                <span style={{ fontSize: 8, fontWeight: 700, color: T.warning, background: T.warningDim, padding: "1px 5px", borderRadius: 3, textTransform: "uppercase" }}>Beta</span>
              )}
            </div>
            <div style={{ fontSize: 11, color: T.textDim, lineHeight: 1.4, marginTop: 2 }}>
              {connector.description.length > 80 ? connector.description.slice(0, 80) + "…" : connector.description}
            </div>
          </div>
        </div>
        <ChevronRight size={14} style={{ color: T.textDim, flexShrink: 0, marginTop: 4 }} />
      </div>

      {/* Footer: Status + Docs link */}
      <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          {connector.is_configured ? (
            <>
              {connector.health.status === "ok" ? (
                <CheckCircle2 size={11} style={{ color: T.success }} />
              ) : connector.health.status === "error" ? (
                <TriangleAlert size={11} style={{ color: T.danger }} />
              ) : (
                <CheckCircle2 size={11} style={{ color: T.textDim }} />
              )}
              <span style={{ fontSize: 10, fontWeight: 600, color: statusColor }}>
                {connector.health.status === "ok" ? "Verbunden" : connector.health.status === "error" ? "Fehler" : "Konfiguriert"}
              </span>
            </>
          ) : (
            <>
              <MinusCircle size={11} style={{ color: T.textDim }} />
              <span style={{ fontSize: 10, color: T.textDim }}>Nicht konfiguriert</span>
            </>
          )}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDocs(); }}
          style={{ border: "none", background: "none", color: T.accent, fontSize: 10, cursor: "pointer", display: "flex", alignItems: "center", gap: 3, padding: 0, fontWeight: 600 }}
        >
          <BookOpen size={10} /> Anleitung
        </button>
      </div>
    </Card>
  );
}
