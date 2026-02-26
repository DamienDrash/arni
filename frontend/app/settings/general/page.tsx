"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck, Mail, Lock, History, Save, Send, RefreshCw,
  Server, Trash2, Shield, CheckCircle, AlertTriangle, Eye, EyeOff,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/LanguageContext";

type Setting = { key: string; value: string; description?: string };

const inputStyle: React.CSSProperties = {
  width: "100%", borderRadius: 10, border: `1px solid ${T.border}`,
  background: T.surfaceAlt, color: T.text, fontSize: 13,
  padding: "10px 14px", outline: "none", boxSizing: "border-box" as const,
  transition: "border-color 0.2s ease",
};

const labelStyle: React.CSSProperties = {
  fontSize: 11, color: T.textMuted, textTransform: "uppercase",
  fontWeight: 700, marginBottom: 4, display: "block", letterSpacing: "0.04em",
};

export default function SettingsGeneralPage() {
  const { t } = useI18n();
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showPass, setShowPass] = useState(false);
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";

  const [smtpForm, setSmtpForm] = useState({
    host: "", port: "", user: "", pass: "", fromName: "", fromAddr: "",
  });

  async function fetchData() {
    try {
      const res = await apiFetch("/admin/settings");
      if (res.ok) {
        const data = await res.json() as Setting[];
        setSettings(data);
        const find = (k: string) => data.find(s => s.key === k)?.value || "";
        setSmtpForm({
          host: find("platform_email_smtp_host"),
          port: find("platform_email_smtp_port"),
          user: find("platform_email_smtp_user"),
          pass: find("platform_email_smtp_pass") ? "__REDACTED__" : "",
          fromName: find("platform_email_from_name"),
          fromAddr: find("platform_email_from_addr"),
        });
      }
    } catch (e) { console.error("Fetch failed", e); }
    finally { setLoading(false); }
  }

  useEffect(() => { fetchData(); }, []);

  const updateSetting = async (key: string, value: string) => {
    try {
      const res = await apiFetch(`/admin/settings/${key}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (res.ok) setSettings(prev => prev.map(s => s.key === key ? { ...s, value } : s));
    } catch (e) { console.error("Update failed", e); }
  };

  const saveSmtp = async () => {
    setBusy(true); setError(""); setSaved("");
    const updates = [
      { key: "platform_email_smtp_host", value: smtpForm.host },
      { key: "platform_email_smtp_port", value: smtpForm.port },
      { key: "platform_email_smtp_user", value: smtpForm.user },
      { key: "platform_email_from_name", value: smtpForm.fromName },
      { key: "platform_email_from_addr", value: smtpForm.fromAddr },
    ];
    if (smtpForm.pass !== "__REDACTED__" && smtpForm.pass !== "") {
      updates.push({ key: "platform_email_smtp_pass", value: smtpForm.pass });
    }
    try {
      const res = await apiFetch("/admin/settings", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates.map(u => ({ key: u.key, value: u.value }))),
      });
      if (res.ok) { void fetchData(); setSaved("SMTP-Konfiguration gespeichert"); setTimeout(() => setSaved(""), 3000); }
    } catch (e) { setError("Speichern fehlgeschlagen"); }
    finally { setBusy(false); }
  };

  const sendTestMail = async () => {
    const recipient = prompt(t("settings.general.smtp.testRecipient"), user?.email || "");
    if (!recipient) return;
    setTesting(true);
    try {
      const res = await apiFetch("/admin/platform/email/test", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: smtpForm.host, port: parseInt(smtpForm.port), user: smtpForm.user,
          pass: smtpForm.pass, from_name: smtpForm.fromName,
          from_addr: smtpForm.fromAddr, recipient,
        }),
      });
      const data = await res.json();
      if (data.status === "ok") alert(data.message || t("common.confirmed"));
      else alert(`${t("common.error")}: ${data.error}`);
    } catch (e) { alert(t("ai.errors.connectionError")); }
    finally { setTesting(false); }
  };

  const getS = (key: string) => settings.find(s => s.key === key)?.value || "";

  if (loading) return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SettingsSubnav />
      <div style={{ padding: 40, textAlign: "center", color: T.textMuted, fontSize: 13 }}>{t("common.loading")}</div>
    </div>
  );

  if (!isSystemAdmin) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SettingsSubnav />
        <Card style={{ padding: 24 }}>
          <p style={{ color: T.textMuted, fontSize: 13 }}>Noch keine spezifischen Einstellungen verfügbar.</p>
        </Card>
      </div>
    );
  }

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
          <span style={{ fontSize: 13, color: T.success, fontWeight: 600 }}>{saved}</span>
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

      {/* Privacy & System Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Privacy */}
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "16px 20px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: T.successDim, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Lock size={16} color={T.success} />
            </div>
            <div>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: 0 }}>
                {t("settings.general.privacy.title")}
              </h3>
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                {t("settings.general.privacy.subtitle")}
              </p>
            </div>
          </div>
          <div style={{ padding: 16, display: "grid", gap: 12 }}>
            <SettingRow
              icon={Lock} iconColor={T.success}
              title={t("settings.general.privacy.pii")}
              description={t("settings.general.privacy.piiDesc")}
            >
              <ToggleSwitch
                value={getS("platform_pii_masking_enabled") === "true"}
                label="PII"
                onChange={(v) => updateSetting("platform_pii_masking_enabled", v ? "true" : "false")}
              />
            </SettingRow>
            <SettingRow
              icon={History} iconColor="#3B82F6"
              title={t("settings.general.privacy.retention")}
              description={t("settings.general.privacy.retentionDesc")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="number"
                  style={{ ...inputStyle, width: 70, textAlign: "center", padding: "6px 8px" }}
                  value={getS("platform_data_retention_days") || "90"}
                  onChange={(e) => updateSetting("platform_data_retention_days", e.target.value)}
                />
                <span style={{ fontSize: 11, color: T.textDim }}>{t("common.days")}</span>
              </div>
            </SettingRow>
          </div>
        </Card>

        {/* System */}
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "16px 20px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 10,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: T.dangerDim, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Shield size={16} color={T.danger} />
            </div>
            <div>
              <h3 style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: 0 }}>
                {t("settings.general.system.title")}
              </h3>
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                {t("settings.general.system.subtitle")}
              </p>
            </div>
          </div>
          <div style={{ padding: 16, display: "grid", gap: 12 }}>
            <SettingRow
              icon={Shield} iconColor={T.danger}
              title={t("settings.general.system.maintenance")}
              description={t("settings.general.system.maintenanceDesc")}
            >
              <ToggleSwitch
                value={getS("maintenance_mode") === "true"}
                label="Maintenance"
                onChange={(v) => updateSetting("maintenance_mode", v ? "true" : "false")}
              />
            </SettingRow>
            <SettingRow
              icon={Trash2} iconColor={T.warning}
              title={t("settings.general.system.audit")}
              description={t("settings.general.system.auditDesc")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <input
                  type="number"
                  style={{ ...inputStyle, width: 70, textAlign: "center", padding: "6px 8px" }}
                  value={getS("platform_audit_retention_days") || "365"}
                  onChange={(e) => updateSetting("platform_audit_retention_days", e.target.value)}
                />
                <span style={{ fontSize: 11, color: T.textDim }}>{t("common.days")}</span>
              </div>
            </SettingRow>
          </div>
        </Card>
      </div>

      {/* SMTP Configuration */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: `${T.email}15`, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Mail size={18} color={T.email} />
            </div>
            <div>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>
                {t("settings.general.smtp.title")}
              </h3>
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                {t("settings.general.smtp.subtitle")}
              </p>
            </div>
          </div>
          <div style={{
            padding: "4px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700,
            background: smtpForm.host ? T.successDim : T.warningDim,
            color: smtpForm.host ? T.success : T.warning,
            letterSpacing: "0.04em", textTransform: "uppercase",
          }}>
            {smtpForm.host ? "Konfiguriert" : "Nicht konfiguriert"}
          </div>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.host")}</label>
              <input
                style={inputStyle}
                value={smtpForm.host}
                onChange={e => setSmtpForm({ ...smtpForm, host: e.target.value })}
                placeholder="smtp.postmarkapp.com"
              />
            </div>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.port")}</label>
              <input
                style={inputStyle}
                value={smtpForm.port}
                onChange={e => setSmtpForm({ ...smtpForm, port: e.target.value })}
                placeholder="587"
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.user")}</label>
              <input
                style={inputStyle}
                value={smtpForm.user}
                onChange={e => setSmtpForm({ ...smtpForm, user: e.target.value })}
                placeholder="api-key-username"
              />
            </div>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.pass")}</label>
              <div style={{ position: "relative" }}>
                <input
                  type={showPass ? "text" : "password"}
                  style={{ ...inputStyle, paddingRight: 40 }}
                  value={smtpForm.pass}
                  onChange={e => setSmtpForm({ ...smtpForm, pass: e.target.value })}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(!showPass)}
                  style={{
                    position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", cursor: "pointer", padding: 4,
                  }}
                >
                  {showPass ? <EyeOff size={14} color={T.textDim} /> : <Eye size={14} color={T.textDim} />}
                </button>
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.senderName")}</label>
              <input
                style={inputStyle}
                value={smtpForm.fromName}
                onChange={e => setSmtpForm({ ...smtpForm, fromName: e.target.value })}
                placeholder="ARIIA Platform"
              />
            </div>
            <div>
              <label style={labelStyle}>{t("settings.general.smtp.senderAddr")}</label>
              <input
                style={inputStyle}
                value={smtpForm.fromAddr}
                onChange={e => setSmtpForm({ ...smtpForm, fromAddr: e.target.value })}
                placeholder="noreply@ariia.io"
              />
            </div>
          </div>
        </div>

        <div style={{
          padding: "12px 24px", borderTop: `1px solid ${T.border}`,
          display: "flex", justifyContent: "flex-end", gap: 10,
        }}>
          <button
            onClick={sendTestMail}
            disabled={testing || !smtpForm.host}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "10px 18px", borderRadius: 8,
              background: T.surfaceAlt, color: T.textMuted,
              border: `1px solid ${T.border}`, fontSize: 12,
              fontWeight: 600, cursor: "pointer",
              opacity: (testing || !smtpForm.host) ? 0.5 : 1,
            }}
          >
            {testing ? <RefreshCw size={13} className="animate-spin" /> : <Send size={13} />}
            {t("settings.general.smtp.test")}
          </button>
          <button
            onClick={saveSmtp}
            disabled={busy}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "10px 18px", borderRadius: 8,
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              color: "#fff", border: "none", fontSize: 12,
              fontWeight: 700, cursor: "pointer",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy ? <RefreshCw size={13} className="animate-spin" /> : <Save size={13} />}
            {t("common.save")}
          </button>
        </div>
      </Card>
    </div>
  );
}

/* ── Sub-Components ── */

function SettingRow({ icon: Icon, iconColor, title, description, children }: {
  icon: typeof Lock; iconColor: string; title: string; description: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: 14, borderRadius: 10,
      background: T.surfaceAlt, border: `1px solid ${T.border}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 30, height: 30, borderRadius: 8,
          background: `${iconColor}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={14} color={iconColor} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{title}</div>
          <div style={{ fontSize: 11, color: T.textDim }}>{description}</div>
        </div>
      </div>
      {children}
    </div>
  );
}
