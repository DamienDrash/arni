"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { CheckCircle2, Loader2, MinusCircle, PlugZap, TriangleAlert, QrCode, Globe, X } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type IntegrationsConfig = {
  telegram: { bot_token: string; admin_chat_id: string; webhook_secret: string };
  whatsapp: { 
    mode: string;
    meta_verify_token: string; 
    meta_access_token: string; 
    meta_app_secret: string; 
    meta_phone_number_id: string;
    bridge_auth_dir: string 
  };
  magicline: {
    base_url: string;
    api_key: string;
    tenant_id: string;
    auto_sync_enabled: string;
    auto_sync_cron: string;
    last_sync_at: string;
    last_sync_status: string;
    last_sync_error: string;
  };
  smtp: {
    host: string;
    port: string;
    username: string;
    password: string;
    from_email: string;
    from_name: string;
    use_starttls: string;
    verification_subject: string;
  };
  email_channel: {
    enabled: string;
    postmark_server_token: string;
    postmark_inbound_token: string;
    message_stream: string;
    from_email: string;
  };
  sms_channel: {
    enabled: string;
    twilio_account_sid: string;
    twilio_auth_token: string;
    twilio_sms_number: string;
  };
  voice_channel: {
    enabled: string;
    twilio_account_sid: string;
    twilio_auth_token: string;
    twilio_voice_number: string;
    twilio_voice_stream_url: string;
  };
};

type Setting = { key: string; value: string };
type Provider = "telegram" | "whatsapp" | "magicline" | "smtp" | "email" | "sms" | "voice";
type HealthState = {
  lastAt: string;
  lastStatus: "ok" | "error" | "never";
  lastDetail: string;
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

const emptyHealth: HealthState = { lastAt: "", lastStatus: "never", lastDetail: "" };

function readHealth(rows: Setting[], provider: Provider): HealthState {
  const byKey = new Map(rows.map((r) => [r.key, r.value]));
  const lastAt = byKey.get(`integration_${provider}_last_test_at`) || "";
  const rawStatus = (byKey.get(`integration_${provider}_last_status`) || "never").toLowerCase();
  const lastStatus: HealthState["lastStatus"] = rawStatus === "ok" ? "ok" : rawStatus === "error" ? "error" : "never";
  const lastDetail = byKey.get(`integration_${provider}_last_detail`) || "";
  return { lastAt, lastStatus, lastDetail };
}

export default function SettingsIntegrationsPage() {
  const [integrations, setIntegrations] = useState<IntegrationsConfig | null>(null);
  const [health, setHealth] = useState<Record<Provider, HealthState>>({
    telegram: emptyHealth,
    whatsapp: emptyHealth,
    magicline: emptyHealth,
    smtp: emptyHealth,
    email: emptyHealth,
    sms: emptyHealth,
    voice: emptyHealth,
  });
  const [testing, setTesting] = useState<Provider | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [syncingMagicline, setSyncingMagicline] = useState(false);
  const [magiclineSyncMsg, setMagiclineSyncMsg] = useState("");
  
  // QR State
  const [qrOpen, setQrOpen] = useState(false);
  const [qrUrl, setQrUrl] = useState("");
  const [qrLoading, setQrLoading] = useState(false);
  const [resetingWa, setResetingWa] = useState(false);

  async function fetchIntegrations() {
    setError("");
    const [configRes, settingsRes] = await Promise.all([
      apiFetch("/admin/integrations/config"),
      apiFetch("/admin/settings"),
    ]);
    if (!configRes.ok) {
      setError(`Konfiguration konnte nicht geladen werden (${configRes.status}).`);
      return;
    }
    setIntegrations(await configRes.json());
    if (settingsRes.ok) {
      const rows = (await settingsRes.json()) as Setting[];
      setHealth({
        telegram: readHealth(rows, "telegram"),
        whatsapp: readHealth(rows, "whatsapp"),
        magicline: readHealth(rows, "magicline"),
        smtp: readHealth(rows, "smtp"),
        email: readHealth(rows, "email"),
        sms: readHealth(rows, "sms"),
        voice: readHealth(rows, "voice"),
      });
    }
  }

  async function fetchHealthOnly() {
    const res = await apiFetch("/admin/settings");
    if (res.ok) {
      const rows = (await res.json()) as Setting[];
      setHealth({
        telegram: readHealth(rows, "telegram"),
        whatsapp: readHealth(rows, "whatsapp"),
        magicline: readHealth(rows, "magicline"),
        smtp: readHealth(rows, "smtp"),
        email: readHealth(rows, "email"),
        sms: readHealth(rows, "sms"),
        voice: readHealth(rows, "voice"),
      });
    }
  }

  function updateField(path: string, value: string) {
    setIntegrations((prev) => {
      if (!prev) return prev;
      const next = structuredClone(prev);
      const parts = path.split(".");
      let target: any = next;
      for (let i = 0; i < parts.length - 1; i++) {
        target = target[parts[i]];
      }
      target[parts[parts.length - 1]] = value;
      return next;
    });
  }

  async function saveIntegrations() {
    if (!integrations) return;
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch("/admin/integrations/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(integrations),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || `Speichern fehlgeschlagen (${res.status}).`);
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 1800);
      await fetchIntegrations();
    } finally {
      setSaving(false);
    }
  }

  async function triggerMagiclineSync() {
    setSyncingMagicline(true);
    setMagiclineSyncMsg("Synchronisierung läuft…");
    try {
      const res = await apiFetch("/admin/members/sync", { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setMagiclineSyncMsg(`Fehler: ${(body as { detail?: string }).detail || res.status}`);
        return;
      }
      const data = (await res.json()) as { fetched: number; upserted: number; deleted: number };
      setMagiclineSyncMsg(
        `✓ Sync abgeschlossen — ${data.fetched} geladen, ${data.upserted} aktualisiert, ${data.deleted} gelöscht`
      );
      await fetchIntegrations();
    } catch (e) {
      setMagiclineSyncMsg(`Fehler: ${String(e)}`);
    } finally {
      setSyncingMagicline(false);
    }
  }

  async function testConnector(provider: Provider) {
    if (!integrations) return;
    setTesting(provider);
    setError("");
    try {
      const sectionMap: Record<Provider, keyof IntegrationsConfig> = {
        telegram: "telegram",
        whatsapp: "whatsapp",
        magicline: "magicline",
        smtp: "smtp",
        email: "email_channel",
        sms: "sms_channel",
        voice: "voice_channel"
      };
      const config = integrations[sectionMap[provider]];
      const res = await apiFetch(`/admin/integrations/test/${provider}`, { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ config })
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail || `Test fehlgeschlagen (${res.status}).`);
      }
      await fetchHealthOnly();
    } catch (e) {
      setError(String(e));
      await fetchHealthOnly();
    } finally {
      setTesting(null);
    }
  }

  async function showWhatsAppQr() {
    setQrLoading(true);
    setQrOpen(true);
    
    // We use a timestamp to bypass browser caching for the QR image
    const timestamp = Date.now();
    const secureQrUrl = `/arni/proxy/admin/platform/whatsapp/qr-image?t=${timestamp}`;
    setQrUrl(secureQrUrl);
    
    // Check if the image exists/bridge is reachable via a quick metadata call
    try {
      const res = await apiFetch("/admin/platform/whatsapp/qr");
      if (!res.ok) {
        setError("QR-Code konnte nicht geladen werden.");
      }
    } catch (e) {
      setError("Verbindung zur Bridge fehlgeschlagen.");
    } finally {
      setQrLoading(false);
    }
  }

  async function resetWhatsApp() {
    if (!confirm("Möchtest du die WhatsApp-Sitzung wirklich zurücksetzen? Alle bisherigen Verbindungsversuche werden gelöscht.")) return;
    setResetingWa(true);
    try {
      const res = await apiFetch("/admin/platform/whatsapp/reset", { method: "POST" });
      if (res.ok) {
        alert("Sitzung zurückgesetzt. Das Fenster wird nun geschlossen.");
        setQrOpen(false);
      }
    } catch (e) {
      alert("Fehler beim Zurücksetzen.");
    } finally {
      setResetingWa(false);
    }
  }

  useEffect(() => {
    void fetchIntegrations();
  }, []);

  const healthSummary = useMemo(() => {
    const rows = Object.entries(health) as Array<[Provider, HealthState]>;
    const ok = rows.filter(([, h]) => h.lastStatus === "ok").length;
    const err = rows.filter(([, h]) => h.lastStatus === "error").length;
    return { ok, err, total: rows.length };
  }, [health]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Integrationen"
          subtitle="Sichere Konfiguration, Testläufe und Betriebsstatus pro Connector."
          action={
            <button
              onClick={() => void saveIntegrations()}
              disabled={saving || !integrations}
              style={primaryButtonStyle}
            >
              {saving ? "Speichere…" : "Integrationen speichern"}
            </button>
          }
        />

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10, marginTop: 10 }}>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Erfolgreich getestet</div>
            <div style={{ marginTop: 2, fontSize: 20, fontWeight: 800, color: T.text }}>{healthSummary.ok}/{healthSummary.total}</div>
          </Card>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Fehler</div>
            <div style={{ marginTop: 2, fontSize: 20, fontWeight: 800, color: healthSummary.err > 0 ? T.danger : T.success }}>{healthSummary.err}</div>
          </Card>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Hinweis</div>
            <div style={{ marginTop: 2, fontSize: 12, color: T.textMuted }}>Nach Credential-Änderungen immer Testlauf ausführen.</div>
          </Card>
        </div>

        {saved && <div style={{ color: T.success, fontSize: 12, marginTop: 10 }}>Konfiguration gespeichert.</div>}
        {error && <div style={{ color: T.danger, fontSize: 12, marginTop: 10 }}>{error}</div>}

        {!integrations ? (
          <div style={{ color: T.textMuted, fontSize: 13, marginTop: 12 }}>Laden…</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 12, marginTop: 12 }}>
            <IntegrationCard
              title="Telegram"
              health={health.telegram}
              testing={testing === "telegram"}
              onTest={() => void testConnector("telegram")}
            >
              <Field label="Bot Token" hint="Erhalten via @BotFather">
                <input type="password" style={inputStyle} value={integrations.telegram.bot_token} onChange={(e) => updateField("telegram.bot_token", e.target.value)} placeholder="1234567890:ABC-..." />
              </Field>
              <Field label="Admin Chat ID">
                <input style={inputStyle} value={integrations.telegram.admin_chat_id} onChange={(e) => updateField("telegram.admin_chat_id", e.target.value)} placeholder="-100123456789" />
              </Field>
              <Field label="Webhook Secret">
                <input type="password" style={inputStyle} value={integrations.telegram.webhook_secret} onChange={(e) => updateField("telegram.webhook_secret", e.target.value)} placeholder="my-webhook-secret" />
              </Field>
            </IntegrationCard>

            <IntegrationCard
              title="WhatsApp"
              health={health.whatsapp}
              testing={testing === "whatsapp"}
              onTest={() => void testConnector("whatsapp")}
            >
              <Field label="Anschluss-Modus">
                <select 
                  style={{ ...inputStyle, cursor: "pointer" }} 
                  value={integrations.whatsapp.mode} 
                  onChange={(e) => updateField("whatsapp.mode", e.target.value)}
                >
                  <option value="qr">QR-Code / WhatsApp Web (Bridge)</option>
                  <option value="meta">Meta Business API (Cloud)</option>
                </select>
              </Field>

              {integrations.whatsapp.mode === "qr" ? (
                <div style={{ padding: "12px", borderRadius: 10, background: T.surface, border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", gap: 8 }}>
                   <div style={{ display: "flex", alignItems: "center", gap: 8, color: T.success }}>
                      <QrCode size={16} />
                      <span style={{ fontSize: 13, fontWeight: 700 }}>QR-Modus aktiv</span>
                   </div>
                   <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                     Der Bot verbindet sich als 'WhatsApp Web' Client. 
                   </p>
                   <button onClick={() => void showWhatsAppQr()} className="btn btn-xs btn-outline mt-2 gap-2">
                     <QrCode size={12} /> QR-Code anzeigen
                   </button>
                </div>
              ) : (
                <>
                  <Field label="Phone Number ID">
                    <input style={inputStyle} value={integrations.whatsapp.meta_phone_number_id} onChange={(e) => updateField("whatsapp.meta_phone_number_id", e.target.value)} placeholder="123456789012345" />
                  </Field>
                  <Field label="Meta Verify Token">
                    <input type="password" style={inputStyle} value={integrations.whatsapp.meta_verify_token} onChange={(e) => updateField("whatsapp.meta_verify_token", e.target.value)} placeholder="my-verify-token" />
                  </Field>
                  <Field label="Meta Access Token">
                    <input type="password" style={inputStyle} value={integrations.whatsapp.meta_access_token} onChange={(e) => updateField("whatsapp.meta_access_token", e.target.value)} placeholder="EAAxxxxxxx..." />
                  </Field>
                  <Field label="Meta App Secret">
                    <input type="password" style={inputStyle} value={integrations.whatsapp.meta_app_secret} onChange={(e) => updateField("whatsapp.meta_app_secret", e.target.value)} placeholder="App Secret" />
                  </Field>
                </>
              )}
            </IntegrationCard>

            <IntegrationCard
              title="Magicline"
              health={health.magicline}
              testing={testing === "magicline"}
              onTest={() => void testConnector("magicline")}
            >
              <Field label="API-Basis-URL">
                <input style={inputStyle} value={integrations.magicline.base_url} onChange={(e) => updateField("magicline.base_url", e.target.value)} placeholder="https://mein-studio.open-api.magicline.com" />
              </Field>
              <Field label="API Key">
                <input type="password" style={inputStyle} value={integrations.magicline.api_key} onChange={(e) => updateField("magicline.api_key", e.target.value)} placeholder="••••••••••••••••" />
              </Field>
              <Field label="Magicline Tenant-ID">
                <input style={inputStyle} value={integrations.magicline.tenant_id} onChange={(e) => updateField("magicline.tenant_id", e.target.value)} placeholder="123456" />
              </Field>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <SyncStatus label="Letzter Sync" value={integrations.magicline.last_sync_at ? new Date(integrations.magicline.last_sync_at).toLocaleString("de-DE") : "—"} />
                <SyncStatus label="Status" value={integrations.magicline.last_sync_status || "—"} color={integrations.magicline.last_sync_status === "ok" ? T.success : integrations.magicline.last_sync_status === "error" ? T.danger : undefined} />
              </div>
              <button
                type="button"
                onClick={() => void triggerMagiclineSync()}
                disabled={syncingMagicline}
                style={{ ...testButtonStyle, background: T.accentDim, borderColor: T.accent, color: T.text }}
              >
                {syncingMagicline ? "Sync läuft…" : "↻ Jetzt synchronisieren"}
              </button>
            </IntegrationCard>

            <IntegrationCard
              title="SMTP / E-Mail"
              health={health.smtp}
              testing={testing === "smtp"}
              onTest={() => void testConnector("smtp")}
            >
              <Field label="SMTP Host">
                <input style={inputStyle} value={integrations.smtp.host} onChange={(e) => updateField("smtp.host", e.target.value)} placeholder="smtp.gmail.com" />
              </Field>
              <Field label="SMTP Port">
                <input style={inputStyle} value={integrations.smtp.port} onChange={(e) => updateField("smtp.port", e.target.value)} placeholder="587" />
              </Field>
              <Field label="Benutzername">
                <input style={inputStyle} value={integrations.smtp.username} onChange={(e) => updateField("smtp.username", e.target.value)} placeholder="noreply@mein-studio.de" />
              </Field>
              <Field label="Passwort">
                <input type="password" style={inputStyle} value={integrations.smtp.password} onChange={(e) => updateField("smtp.password", e.target.value)} placeholder="••••••••" />
              </Field>
              <Field label="Absender-E-Mail">
                <input style={inputStyle} value={integrations.smtp.from_email} onChange={(e) => updateField("smtp.from_email", e.target.value)} placeholder="noreply@mein-studio.de" />
              </Field>
            </IntegrationCard>

            <IntegrationCard
              title="E-Mail-Kanal (Postmark)"
              health={health.email}
              testing={testing === "email"}
              onTest={() => void testConnector("email")}
            >
              <Field label="Kanal aktiviert">
                <select style={{ ...inputStyle, cursor: "pointer" }} value={integrations.email_channel.enabled} onChange={(e) => updateField("email_channel.enabled", e.target.value)}>
                  <option value="true">true – aktiviert</option>
                  <option value="false">false – deaktiviert</option>
                </select>
              </Field>
              <Field label="Postmark Server Token">
                <input type="password" style={inputStyle} value={integrations.email_channel.postmark_server_token} onChange={(e) => updateField("email_channel.postmark_server_token", e.target.value)} placeholder="••••••••••••••••" />
              </Field>
              <Field label="Absender-E-Mail">
                <input style={inputStyle} value={integrations.email_channel.from_email} onChange={(e) => updateField("email_channel.from_email", e.target.value)} placeholder="ariia@mein-studio.de" />
              </Field>
            </IntegrationCard>

            <IntegrationCard
              title="SMS-Kanal (Twilio)"
              health={health.sms}
              testing={testing === "sms"}
              onTest={() => void testConnector("sms")}
            >
              <Field label="Kanal aktiviert">
                <select style={{ ...inputStyle, cursor: "pointer" }} value={integrations.sms_channel.enabled} onChange={(e) => updateField("sms_channel.enabled", e.target.value)}>
                  <option value="true">true – aktiviert</option>
                  <option value="false">false – deaktiviert</option>
                </select>
              </Field>
              <Field label="Twilio Account SID">
                <input style={inputStyle} value={integrations.sms_channel.twilio_account_sid} onChange={(e) => updateField("sms_channel.twilio_account_sid", e.target.value)} placeholder="ACxxxxxxxxxx..." />
              </Field>
              <Field label="Twilio Auth Token">
                <input type="password" style={inputStyle} value={integrations.sms_channel.twilio_auth_token} onChange={(e) => updateField("sms_channel.twilio_auth_token", e.target.value)} placeholder="••••••••••••••••" />
              </Field>
              <Field label="Twilio SMS-Nummer">
                <input style={inputStyle} value={integrations.sms_channel.twilio_sms_number} onChange={(e) => updateField("sms_channel.twilio_sms_number", e.target.value)} placeholder="+4915123456789" />
              </Field>
            </IntegrationCard>

            <IntegrationCard
              title="Voice-Kanal (Twilio)"
              health={health.voice}
              testing={testing === "voice"}
              onTest={() => void testConnector("voice")}
            >
              <Field label="Kanal aktiviert">
                <select style={{ ...inputStyle, cursor: "pointer" }} value={integrations.voice_channel.enabled} onChange={(e) => updateField("voice_channel.enabled", e.target.value)}>
                  <option value="true">true – aktiviert</option>
                  <option value="false">false – deaktiviert</option>
                </select>
              </Field>
              <Field label="Twilio Voice-Nummer">
                <input style={inputStyle} value={integrations.voice_channel.twilio_voice_number} onChange={(e) => updateField("voice_channel.twilio_voice_number", e.target.value)} placeholder="+49301234567" />
              </Field>
              <Field label="Stream-URL (Websocket)">
                <input style={inputStyle} value={integrations.voice_channel.twilio_voice_stream_url} onChange={(e) => updateField("voice_channel.twilio_voice_stream_url", e.target.value)} placeholder="wss://deine-domain.de/voice" />
              </Field>
            </IntegrationCard>
          </div>
        )}
      </Card>

      {/* WhatsApp QR Modal */}
      <Modal
        open={qrOpen}
        onClose={() => setQrOpen(false)}
        title="WhatsApp Verbindung herstellen"
        subtitle="Scanne diesen Code mit deinem Smartphone"
        width="min(440px, 100%)"
      >
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 20, padding: "10px 0" }}>
          {qrLoading ? (
            <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
              <Loader2 size={40} className="animate-spin text-accent" />
              <span style={{ fontSize: 13, color: T.textMuted }}>QR-Code wird generiert...</span>
            </div>
          ) : qrUrl ? (
            <>
              <div style={{ padding: 12, background: "white", borderRadius: 16, border: `1px solid ${T.border}`, boxShadow: "0 10px 25px rgba(0,0,0,0.1)", position: "relative", minHeight: 240, display: "flex", alignItems: "center", justifyContent: "center" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img 
                  src={qrUrl} 
                  alt="WhatsApp QR Code" 
                  style={{ width: 240, height: 240 }} 
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                    const p = (e.target as HTMLImageElement).parentElement;
                    if (p) {
                      p.innerHTML = `<div style="text-align:center; padding:20px; color:#64748B; font-size:13px;">
                        <p style="font-weight:700; margin-bottom:10px; color:#EF4444;">Infrastruktur-Fehler</p>
                        <p style="font-size:11px; margin-bottom:15px; line-height:1.5;">Die WhatsApp-Bridge liefert kein Bild.<br/>
                        Grund: Port-Konflikt oder Sitzung noch nicht bereit.</p>
                        <div style="background:#F1F5F9; padding:8px; border-radius:6px; font-family:monospace; font-size:10px; margin-bottom:15px; text-align:left;">
                          Target: 185.209.228.251:3001<br/>
                          Status: Waiting for QR
                        </div>
                        <button onclick="window.location.reload()" style="background:#6C5CE7; color:white; border:none; padding:8px 16px; border-radius:10px; font-size:12px; font-weight:700; cursor:pointer;">
                          Status aktualisieren
                        </button>
                      </div>`;
                    }
                  }}
                />
              </div>
              <p style={{ fontSize: 12, color: T.textMuted, textAlign: "center", lineHeight: 1.6 }}>
                Öffne WhatsApp auf deinem Telefon → Menü oder Einstellungen → Verknüpfte Geräte → Gerät hinzufügen.
              </p>
            </>
          ) : (
            <div style={{ color: T.danger, textAlign: "center", fontSize: 13 }}>
              Fehler beim Laden des QR-Codes. Bitte stelle sicher, dass die Bridge online ist.
            </div>
          )}
          <div style={{ display: "flex", gap: 10, width: "100%", marginTop: 16 }}>
            <button onClick={() => void showWhatsAppQr()} className="btn btn-sm btn-outline flex-1">QR-Code erneuern</button>
            <button onClick={() => setQrOpen(false)} className="btn btn-sm flex-1">Schließen</button>
          </div>
          
          <button 
            onClick={() => void resetWhatsApp()} 
            disabled={resetingWa}
            style={{ border: "none", background: "none", color: T.danger, fontSize: 11, cursor: "pointer", textDecoration: "underline", marginTop: 10 }}
          >
            {resetingWa ? "Setze zurück..." : "Sitzung hart zurücksetzen (bei Problemen)"}
          </button>
        </div>
      </Modal>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{label}</div>
      {hint && <div style={{ fontSize: 10, color: T.textDim, lineHeight: 1.4 }}>{hint}</div>}
      {children}
    </div>
  );
}

function SyncStatus({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{label}</div>
      <div style={{ fontSize: 12, color: color ?? T.textMuted, padding: "7px 9px", borderRadius: 7, background: T.surface, border: `1px solid ${T.border}`, lineHeight: 1.3 }}>
        {value}
      </div>
    </div>
  );
}

function IntegrationCard({
  title,
  health,
  testing,
  onTest,
  children,
}: {
  title: string;
  health: HealthState;
  testing: boolean;
  onTest: () => void;
  children: React.ReactNode;
}) {
  const statusColor = health.lastStatus === "ok" ? T.success : health.lastStatus === "error" ? T.danger : T.textDim;
  const statusLabel = health.lastStatus === "ok" ? "OK" : health.lastStatus === "error" ? "Fehler" : "Nicht getestet";

  return (
    <Card style={{ padding: 14, background: T.surfaceAlt }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <PlugZap size={14} color={T.accent} />
          <span style={{ fontSize: 12, color: T.textMuted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em" }}>{title}</span>
        </div>
        <button type="button" onClick={onTest} disabled={testing} style={testButtonStyle}>
          {testing ? <Loader2 size={12} className="animate-spin" /> : "Verbindung testen"}
        </button>
      </div>

      <div style={{ display: "grid", gap: 8 }}>
        {children}
      </div>

      <div style={{ marginTop: 10, borderTop: `1px solid ${T.border}`, paddingTop: 10, display: "grid", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: statusColor }}>
          {health.lastStatus === "ok" ? <CheckCircle2 size={13} /> : health.lastStatus === "error" ? <TriangleAlert size={13} /> : <MinusCircle size={13} />}
          <span>{statusLabel}</span>
        </div>
        <div style={{ fontSize: 11, color: T.textDim }}>
          Letzter Test: {health.lastAt ? new Date(health.lastAt).toLocaleString("de-DE") : "noch nie"}
        </div>
        {health.lastDetail && (
          <div style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.45 }}>
            {health.lastDetail}
          </div>
        )}
      </div>
    </Card>
  );
}

const primaryButtonStyle: CSSProperties = {
  border: "none",
  borderRadius: 9,
  background: T.accent,
  color: "#071018",
  fontWeight: 700,
  padding: "8px 12px",
  fontSize: 12,
  cursor: "pointer",
};

const testButtonStyle: CSSProperties = {
  borderRadius: 8,
  border: `1px solid ${T.border}`,
  background: T.surface,
  color: T.text,
  fontSize: 12,
  fontWeight: 600,
  padding: "6px 9px",
  cursor: "pointer",
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
};
