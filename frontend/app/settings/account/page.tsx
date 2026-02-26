"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  UserCircle2, Lock, Bell, Globe, Save, CheckCircle,
  AlertTriangle, Eye, EyeOff, Building2, Clock, Mail,
  MessageSquare, Gauge, Languages,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";
import { useI18n } from "@/lib/i18n/LanguageContext";
import LanguageSwitcher from "@/components/i18n/LanguageSwitcher";

type ProfileSettings = {
  id: number; email: string; full_name: string; role: string;
  locale: string; timezone: string; notify_email: string;
  notify_telegram: string; compact_mode: string;
};

type TenantPreferences = {
  tenant_display_name: string; tenant_timezone: string;
  tenant_locale: string; tenant_notify_email: string;
  tenant_notify_telegram: string; tenant_escalation_sla_minutes: string;
  tenant_live_refresh_seconds: string;
};

/* ── Styles ── */
const inputStyle: CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  transition: "border-color 0.2s ease",
  boxSizing: "border-box" as const,
};

const sectionTitleStyle: CSSProperties = {
  fontSize: 13, fontWeight: 700, color: T.text,
  letterSpacing: "-0.01em", margin: "0 0 4px",
};

const sectionDescStyle: CSSProperties = {
  fontSize: 12, color: T.textMuted, margin: "0 0 16px", lineHeight: 1.5,
};

export default function SettingsAccountPage() {
  const { t } = useI18n();
  const role = getStoredUser()?.role;
  const isSystemAdmin = role === "system_admin";
  const isTenantAdmin = role === "tenant_admin";
  const [profile, setProfile] = useState<ProfileSettings | null>(null);
  const [tenantPrefs, setTenantPrefs] = useState<TenantPreferences | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingTenant, setSavingTenant] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function load() {
    setError("");
    const profileRes = await apiFetch("/auth/profile-settings");
    if (!profileRes.ok) { setError(t("ai.errors.loadFailed")); return; }
    setProfile((await profileRes.json()) as ProfileSettings);
    if (isTenantAdmin) {
      const tenantRes = await apiFetch("/admin/tenant-preferences");
      if (tenantRes.ok) setTenantPrefs((await tenantRes.json()) as TenantPreferences);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    setSavingProfile(true); setError("");
    try {
      const body: Record<string, string> = {
        full_name: profile.full_name, locale: profile.locale,
        timezone: profile.timezone, notify_email: profile.notify_email,
        notify_telegram: profile.notify_telegram, compact_mode: profile.compact_mode,
      };
      if (newPassword) {
        body.current_password = currentPassword;
        body.new_password = newPassword;
      }
      const res = await apiFetch("/auth/profile-settings", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || t("ai.errors.saveFailed")); return;
      }
      setSaved(t("common.confirmed"));
      setCurrentPassword(""); setNewPassword("");
      setTimeout(() => setSaved(""), 3000);
    } finally { setSavingProfile(false); }
  }

  async function saveTenantPrefs() {
    if (!tenantPrefs) return;
    setSavingTenant(true); setError("");
    try {
      const res = await apiFetch("/admin/tenant-preferences", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tenantPrefs),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || t("ai.errors.saveFailed")); return;
      }
      setSaved(t("common.confirmed"));
      setTimeout(() => setSaved(""), 3000);
    } finally { setSavingTenant(false); }
  }

  useEffect(() => { void load(); }, []);

  if (!profile) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SettingsSubnav />
        <div style={{ padding: 40, textAlign: "center", color: T.textMuted, fontSize: 13 }}>{t("common.loading")}</div>
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

      {/* Profile Section */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: "#3B82F615", display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <UserCircle2 size={18} color="#3B82F6" />
          </div>
          <div>
            <h2 style={sectionTitleStyle}>{t("settings.account.personalData")}</h2>
            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
              Deine persönlichen Informationen und Anmeldedaten
            </p>
          </div>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <FieldGroup label={t("settings.account.email")} hint={t("settings.account.emailHint")} icon={Mail}>
              <div style={{ ...inputStyle, color: T.textDim, background: T.surface, cursor: "default", userSelect: "all" as const }}>
                {profile.email}
              </div>
            </FieldGroup>
            <FieldGroup label={t("settings.account.fullName")} hint={t("settings.account.fullNameHint")} icon={UserCircle2}>
              <input
                value={profile.full_name ?? ""}
                onChange={(e) => setProfile((p) => (p ? { ...p, full_name: e.target.value } : p))}
                style={inputStyle}
                placeholder={t("settings.account.placeholders.fullName")}
              />
            </FieldGroup>
            <FieldGroup label={t("settings.account.locale")} hint={t("settings.account.localeHint")} icon={Globe}>
              <input
                value={profile.locale ?? ""}
                onChange={(e) => setProfile((p) => (p ? { ...p, locale: e.target.value } : p))}
                style={inputStyle}
                placeholder="de-DE"
              />
            </FieldGroup>
            <FieldGroup label={t("settings.account.timezone")} hint={t("settings.account.timezoneHint")} icon={Clock}>
              <input
                value={profile.timezone ?? ""}
                onChange={(e) => setProfile((p) => (p ? { ...p, timezone: e.target.value } : p))}
                style={inputStyle}
                placeholder="Europe/Berlin"
              />
            </FieldGroup>
          </div>

          {/* Language */}
          <div style={{ marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <Languages size={15} color={T.textMuted} />
              <span style={{ fontSize: 12, fontWeight: 700, color: T.textMuted }}>{t("settings.language")}</span>
            </div>
            <LanguageSwitcher />
            <p style={{ fontSize: 11, color: T.textDim, marginTop: 6 }}>{t("settings.selectLanguage")}</p>
          </div>
        </div>
      </Card>

      {/* Notifications (Tenant users only) */}
      {!isSystemAdmin && (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: T.warningDim, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Bell size={18} color={T.warning} />
            </div>
            <div>
              <h2 style={sectionTitleStyle}>{t("settings.account.notifications")}</h2>
              <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                Benachrichtigungseinstellungen und Darstellung
              </p>
            </div>
          </div>

          <div style={{ padding: 24, display: "grid", gap: 12 }}>
            <NotificationToggle
              icon={Mail} iconColor={T.email}
              label={t("settings.account.emailNotify")}
              description={t("settings.account.emailNotifyDesc")}
              value={(profile.notify_email ?? "false") === "true"}
              onChange={(v) => setProfile((p) => (p ? { ...p, notify_email: v ? "true" : "false" } : p))}
            />
            <NotificationToggle
              icon={MessageSquare} iconColor={T.telegram}
              label={t("settings.account.tgNotify")}
              description={t("settings.account.tgNotifyDesc")}
              value={(profile.notify_telegram ?? "false") === "true"}
              onChange={(v) => setProfile((p) => (p ? { ...p, notify_telegram: v ? "true" : "false" } : p))}
            />
            <NotificationToggle
              icon={Gauge} iconColor={T.accent}
              label={t("settings.account.compactMode")}
              description={t("settings.account.compactModeDesc")}
              value={(profile.compact_mode ?? "false") === "true"}
              onChange={(v) => setProfile((p) => (p ? { ...p, compact_mode: v ? "true" : "false" } : p))}
            />
          </div>
        </Card>
      )}

      {/* Password */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 24px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: T.dangerDim, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <Lock size={18} color={T.danger} />
          </div>
          <div>
            <h2 style={sectionTitleStyle}>{t("settings.account.password.title")}</h2>
            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
              Passwort ändern für zusätzliche Sicherheit
            </p>
          </div>
        </div>

        <div style={{ padding: 24 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <FieldGroup label={t("settings.account.password.current")} hint={t("settings.account.password.currentHint")}>
              <div style={{ position: "relative" }}>
                <input
                  type={showCurrentPw ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 40 }}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPw(!showCurrentPw)}
                  style={{
                    position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", cursor: "pointer", padding: 4,
                  }}
                >
                  {showCurrentPw ? <EyeOff size={14} color={T.textDim} /> : <Eye size={14} color={T.textDim} />}
                </button>
              </div>
            </FieldGroup>
            <FieldGroup label={t("settings.account.password.new")} hint={t("settings.account.password.newHint")}>
              <div style={{ position: "relative" }}>
                <input
                  type={showNewPw ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  style={{ ...inputStyle, paddingRight: 40 }}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPw(!showNewPw)}
                  style={{
                    position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                    background: "none", border: "none", cursor: "pointer", padding: 4,
                  }}
                >
                  {showNewPw ? <EyeOff size={14} color={T.textDim} /> : <Eye size={14} color={T.textDim} />}
                </button>
              </div>
            </FieldGroup>
          </div>
        </div>
      </Card>

      {/* Save Button */}
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={() => void saveProfile()}
          disabled={savingProfile}
          style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "12px 28px", borderRadius: 10,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
            color: "#fff", border: "none", fontSize: 13,
            fontWeight: 700, cursor: "pointer",
            opacity: savingProfile ? 0.6 : 1,
            transition: "opacity 0.2s ease",
          }}
        >
          <Save size={15} />
          {savingProfile ? t("common.loading") : t("common.save")}
        </button>
      </div>

      {/* Tenant Preferences */}
      {isTenantAdmin && tenantPrefs && (
        <>
          <div style={{ height: 1, background: T.border, margin: "8px 0" }} />

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
                <Building2 size={18} color={T.accent} />
              </div>
              <div>
                <h2 style={sectionTitleStyle}>{t("settings.account.studio.title")}</h2>
                <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                  {t("settings.account.studio.subtitle")}
                </p>
              </div>
            </div>

            <div style={{ padding: 24 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div style={{ gridColumn: "span 2" }}>
                  <FieldGroup label={t("settings.account.studio.name")} hint={t("settings.account.studio.nameHint")} icon={Building2}>
                    <input
                      value={tenantPrefs.tenant_display_name}
                      onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_display_name: e.target.value })}
                      style={inputStyle}
                      placeholder={t("settings.account.placeholders.studioName")}
                    />
                  </FieldGroup>
                </div>
                <FieldGroup label={t("settings.account.timezone")} hint={t("settings.account.studio.timezoneHint")} icon={Clock}>
                  <input
                    value={tenantPrefs.tenant_timezone}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_timezone: e.target.value })}
                    style={inputStyle}
                    placeholder="Europe/Berlin"
                  />
                </FieldGroup>
                <FieldGroup label={t("settings.account.locale")} hint={t("settings.account.localeHint")} icon={Globe}>
                  <input
                    value={tenantPrefs.tenant_locale}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_locale: e.target.value })}
                    style={inputStyle}
                    placeholder="de-DE"
                  />
                </FieldGroup>
                <FieldGroup label={t("settings.account.studio.opsEmail")} hint={t("settings.account.studio.opsEmailHint")} icon={Mail}>
                  <input
                    value={tenantPrefs.tenant_notify_email}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_email: e.target.value })}
                    style={inputStyle}
                    placeholder={t("settings.account.placeholders.opsEmail")}
                  />
                </FieldGroup>
                <FieldGroup label={t("settings.account.studio.opsTelegram")} hint={t("settings.account.studio.opsTelegramHint")} icon={MessageSquare}>
                  <input
                    value={tenantPrefs.tenant_notify_telegram}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_telegram: e.target.value })}
                    style={inputStyle}
                    placeholder={t("settings.account.placeholders.opsTelegram")}
                  />
                </FieldGroup>
                <FieldGroup label={t("settings.account.studio.sla")} hint={t("settings.account.studio.slaHint")} icon={Clock}>
                  <input
                    value={tenantPrefs.tenant_escalation_sla_minutes}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_escalation_sla_minutes: e.target.value })}
                    style={inputStyle}
                    placeholder="30"
                  />
                </FieldGroup>
                <FieldGroup label={t("settings.account.studio.refresh")} hint={t("settings.account.studio.refreshHint")} icon={Gauge}>
                  <input
                    value={tenantPrefs.tenant_live_refresh_seconds}
                    onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_live_refresh_seconds: e.target.value })}
                    style={inputStyle}
                    placeholder="10"
                  />
                </FieldGroup>
              </div>
            </div>
          </Card>

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={() => void saveTenantPrefs()}
              disabled={savingTenant}
              style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "12px 28px", borderRadius: 10,
                background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                color: "#fff", border: "none", fontSize: 13,
                fontWeight: 700, cursor: "pointer",
                opacity: savingTenant ? 0.6 : 1,
              }}
            >
              <Save size={15} />
              {savingTenant ? t("common.loading") : "Studio speichern"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Sub-Components ── */

function FieldGroup({ label, hint, icon: Icon, children }: {
  label: string; hint?: string; icon?: typeof Mail; children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {Icon && <Icon size={12} color={T.textDim} />}
        <span style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{label}</span>
      </div>
      {hint && <p style={{ fontSize: 10, color: T.textDim, lineHeight: 1.4, margin: 0 }}>{hint}</p>}
      {children}
    </div>
  );
}

function NotificationToggle({ icon: Icon, iconColor, label, description, value, onChange }: {
  icon: typeof Mail; iconColor: string; label: string; description: string;
  value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "14px 16px", borderRadius: 10,
      background: T.surfaceAlt, border: `1px solid ${T.border}`,
      transition: "border-color 0.2s ease",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: `${iconColor}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon size={15} color={iconColor} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{label}</div>
          <div style={{ fontSize: 11, color: T.textDim, lineHeight: 1.4 }}>{description}</div>
        </div>
      </div>
      <ToggleSwitch value={value} onChange={onChange} label={label} />
    </div>
  );
}
