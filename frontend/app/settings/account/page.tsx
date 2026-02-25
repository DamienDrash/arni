"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";
import { useI18n } from "@/lib/i18n/LanguageContext";
import LanguageSwitcher from "@/components/i18n/LanguageSwitcher";

type ProfileSettings = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  locale: string;
  timezone: string;
  notify_email: string;
  notify_telegram: string;
  compact_mode: string;
};

type TenantPreferences = {
  tenant_display_name: string;
  tenant_timezone: string;
  tenant_locale: string;
  tenant_notify_email: string;
  tenant_notify_telegram: string;
  tenant_escalation_sla_minutes: string;
  tenant_live_refresh_seconds: string;
};

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "9px 10px",
  borderRadius: 9,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: "#FFFFFF",
  fontSize: 13,
  outline: "none",
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
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  async function load() {
    setError("");
    const profileRes = await apiFetch("/auth/profile-settings");
    if (!profileRes.ok) {
      setError(t("ai.errors.loadFailed"));
      return;
    }
    setProfile((await profileRes.json()) as ProfileSettings);
    if (isTenantAdmin) {
      const tenantRes = await apiFetch("/admin/tenant-preferences");
      if (tenantRes.ok) setTenantPrefs((await tenantRes.json()) as TenantPreferences);
    }
  }

  async function saveProfile() {
    if (!profile) return;
    setSavingProfile(true);
    setError("");
    try {
      const body: Record<string, string> = {
        full_name: profile.full_name,
        locale: profile.locale,
        timezone: profile.timezone,
        notify_email: profile.notify_email,
        notify_telegram: profile.notify_telegram,
        compact_mode: profile.compact_mode,
      };
      if (newPassword) {
        body.current_password = currentPassword;
        body.new_password = newPassword;
      }
      const res = await apiFetch("/auth/profile-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || t("ai.errors.saveFailed"));
        return;
      }
      setSaved(t("common.confirmed"));
      setCurrentPassword("");
      setNewPassword("");
      setTimeout(() => setSaved(""), 1800);
    } finally {
      setSavingProfile(false);
    }
  }

  async function saveTenantPrefs() {
    if (!tenantPrefs) return;
    setSavingTenant(true);
    setError("");
    try {
      const res = await apiFetch("/admin/tenant-preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tenantPrefs),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        setError(payload?.detail || t("ai.errors.saveFailed"));
        return;
      }
      setSaved(t("common.confirmed"));
      setTimeout(() => setSaved(""), 1800);
    } finally {
      setSavingTenant(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const profileReady = useMemo(() => !!profile, [profile]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      <Card style={{ padding: 24 }}>
        <SectionHeader title={t("settings.account.title")} subtitle={t("settings.account.subtitle")} />
        {saved && <div style={{ marginTop: 8, fontSize: 12, color: T.success }}>{saved}</div>}
        {error && <div style={{ marginTop: 8, fontSize: 12, color: T.danger }}>{error}</div>}

        {!profileReady ? (
          <div style={{ marginTop: 12, color: T.textMuted, fontSize: 13 }}>{t("common.loading")}</div>
        ) : (
          <div style={{ marginTop: 12, display: "grid", gap: 12 }}>

            <Card style={{ padding: 14, background: T.surfaceAlt }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 10, letterSpacing: "0.04em", textTransform: "uppercase" }}>{t("settings.account.personalData")}</div>
              <div style={{ display: "grid", gap: 10 }}>
                <AccountField label={t("settings.account.email")} hint={t("settings.account.emailHint")}>
                  <div style={{ ...inputStyle, color: T.textMuted, background: T.surface, cursor: "default", userSelect: "all" as const }}>
                    {profile?.email ?? ""}
                  </div>
                </AccountField>
                <AccountField label={t("settings.account.fullName")} hint={t("settings.account.fullNameHint")}>
                  <input
                    value={profile?.full_name ?? ""}
                    onChange={(e) => setProfile((prev) => (prev ? { ...prev, full_name: e.target.value } : prev))}
                    style={inputStyle}
                    placeholder={t("settings.account.placeholders.fullName")}
                  />
                </AccountField>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <AccountField label={t("settings.account.locale")} hint={t("settings.account.localeHint")}>
                    <input
                      value={profile?.locale ?? ""}
                      onChange={(e) => setProfile((prev) => (prev ? { ...prev, locale: e.target.value } : prev))}
                      style={inputStyle}
                      placeholder={t("settings.account.placeholders.locale")}
                    />
                  </AccountField>
                  <AccountField label={t("settings.account.timezone")} hint={t("settings.account.timezoneHint")}>
                    <input
                      value={profile?.timezone ?? ""}
                      onChange={(e) => setProfile((prev) => (prev ? { ...prev, timezone: e.target.value } : prev))}
                      style={inputStyle}
                      placeholder={t("settings.account.placeholders.timezone")}
                    />
                  </AccountField>
                </div>

                {!isSystemAdmin && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{t("settings.account.notifications")}</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 6 }}>
                      <ToggleRow
                        label={t("settings.account.emailNotify")}
                        description={t("settings.account.emailNotifyDesc")}
                        value={(profile?.notify_email ?? "false") === "true"}
                        onChange={(v) => setProfile((prev) => (prev ? { ...prev, notify_email: v ? "true" : "false" } : prev))}
                      />
                      <ToggleRow
                        label={t("settings.account.tgNotify")}
                        description={t("settings.account.tgNotifyDesc")}
                        value={(profile?.notify_telegram ?? "false") === "true"}
                        onChange={(v) => setProfile((prev) => (prev ? { ...prev, notify_telegram: v ? "true" : "false" } : prev))}
                      />
                      <ToggleRow
                        label={t("settings.account.compactMode")}
                        description={t("settings.account.compactModeDesc")}
                        value={(profile?.compact_mode ?? "false") === "true"}
                        onChange={(v) => setProfile((prev) => (prev ? { ...prev, compact_mode: v ? "true" : "false" } : prev))}
                      />
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{t("settings.language")}</div>
                  <div style={{ marginTop: 6 }}>
                    <LanguageSwitcher />
                    <p style={{ fontSize: 11, color: T.textDim, marginTop: 6 }}>{t("settings.selectLanguage")}</p>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 10, letterSpacing: "0.04em", textTransform: "uppercase" }}>{t("settings.account.password.title")}</div>
                <div style={{ display: "grid", gap: 10 }}>
                  <AccountField label={t("settings.account.password.current")} hint={t("settings.account.password.currentHint")}>
                    <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} style={inputStyle} placeholder={t("settings.account.placeholders.password")} />
                  </AccountField>
                  <AccountField label={t("settings.account.password.new")} hint={t("settings.account.password.newHint")}>
                    <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} placeholder={t("settings.account.placeholders.password")} />
                  </AccountField>
                </div>
              </div>

              <button type="button" onClick={() => void saveProfile()} disabled={savingProfile} style={primaryButtonStyle}>
                {savingProfile ? t("common.loading") : t("common.save")}
              </button>
            </Card>

            {isTenantAdmin && tenantPrefs && (
              <Card style={{ padding: 14, background: T.surfaceAlt }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4, letterSpacing: "0.04em", textTransform: "uppercase" }}>{t("settings.account.studio.title")}</div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 12 }}>{t("settings.account.studio.subtitle")}</div>
                <div style={{ display: "grid", gap: 10 }}>
                  <AccountField label={t("settings.account.studio.name")} hint={t("settings.account.studio.nameHint")}>
                    <input value={tenantPrefs.tenant_display_name} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_display_name: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.studioName")} />
                  </AccountField>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <AccountField label={t("settings.account.timezone")} hint={t("settings.account.studio.timezoneHint")}>
                      <input value={tenantPrefs.tenant_timezone} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_timezone: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.timezone")} />
                    </AccountField>
                    <AccountField label={t("settings.account.locale")} hint={t("settings.account.studio.localeHint")}>
                      <input value={tenantPrefs.tenant_locale} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_locale: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.locale")} />
                    </AccountField>
                  </div>
                  <AccountField label={t("settings.account.studio.opsEmail")} hint={t("settings.account.studio.opsEmailHint")}>
                    <input value={tenantPrefs.tenant_notify_email} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_email: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.opsEmail")} />
                  </AccountField>
                  <AccountField label={t("settings.account.studio.opsTelegram")} hint={t("settings.account.studio.opsTelegramHint")}>
                    <input value={tenantPrefs.tenant_notify_telegram} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_telegram: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.opsTelegram")} />
                  </AccountField>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <AccountField label={t("settings.account.studio.sla")} hint={t("settings.account.studio.slaHint")}>
                      <input value={tenantPrefs.tenant_escalation_sla_minutes} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_escalation_sla_minutes: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.sla")} />
                    </AccountField>
                    <AccountField label={t("settings.account.studio.refresh")} hint={t("settings.account.studio.refreshHint")}>
                      <input value={tenantPrefs.tenant_live_refresh_seconds} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_live_refresh_seconds: e.target.value })} style={inputStyle} placeholder={t("settings.account.placeholders.refresh")} />
                    </AccountField>
                  </div>
                </div>
                <button type="button" onClick={() => void saveTenantPrefs()} disabled={savingTenant} style={primaryButtonStyle}>
                  {savingTenant ? t("common.loading") : t("common.save")}
                </button>
              </Card>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

const primaryButtonStyle: CSSProperties = {
  marginTop: 12,
  border: "none",
  borderRadius: 9,
  background: T.accent,
  color: "#071018",
  fontWeight: 700,
  padding: "8px 12px",
  fontSize: 12,
  cursor: "pointer",
};

function AccountField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>{label}</div>
      {hint && <div style={{ fontSize: 10, color: T.textDim, lineHeight: 1.4 }}>{hint}</div>}
      {children}
    </div>
  );
}

function ToggleRow({ label, description, value, onChange }: { label: string; description: string; value: boolean; onChange: (v: boolean) => void }) {
  const { t } = useI18n();
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 10px", borderRadius: 8, background: T.surface, border: `1px solid ${T.border}` }}>
      <ToggleSwitch value={value} onChange={onChange} label={label} />
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{label}</div>
        <div style={{ fontSize: 11, color: T.textDim, lineHeight: 1.45 }}>{description}</div>
      </div>
    </div>
  );
}
