"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { T } from "@/lib/tokens";

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
  color: T.text,
  fontSize: 13,
  outline: "none",
};

export default function SettingsAccountPage() {
  const role = getStoredUser()?.role;
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
      setError(`Profil konnte nicht geladen werden (${profileRes.status}).`);
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
        setError(payload?.detail || `Speichern fehlgeschlagen (${res.status}).`);
        return;
      }
      setSaved("Profil gespeichert");
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
        setError(payload?.detail || `Tenant-Einstellungen fehlgeschlagen (${res.status}).`);
        return;
      }
      setSaved("Tenant Preferences gespeichert");
      setTimeout(() => setSaved(""), 1800);
    } finally {
      setSavingTenant(false);
    }
  }

  /* eslint-disable react-hooks/exhaustive-deps */
  useEffect(() => {
    void load();
  }, []);
  /* eslint-enable react-hooks/exhaustive-deps */

  const profileReady = useMemo(() => !!profile, [profile]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      <Card style={{ padding: 24 }}>
        <SectionHeader title="Account & Preferences" subtitle="Self-Service Profil, Security und persönliche UI/Notification-Einstellungen." />
        {saved && <div style={{ marginTop: 8, fontSize: 12, color: T.success }}>{saved}</div>}
        {error && <div style={{ marginTop: 8, fontSize: 12, color: T.danger }}>{error}</div>}

        {!profileReady ? (
          <div style={{ marginTop: 12, color: T.textMuted, fontSize: 13 }}>Laden…</div>
        ) : (
          <div style={{ marginTop: 12, display: "grid", gap: 12 }}>

            {/* ── Persönliche Daten ──────────────────────────────── */}
            <Card style={{ padding: 14, background: T.surfaceAlt }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 10, letterSpacing: "0.04em", textTransform: "uppercase" }}>Persönliche Daten</div>
              <div style={{ display: "grid", gap: 10 }}>
                <AccountField label="E-Mail-Adresse" hint="Kann nicht geändert werden — kontaktiere einen Admin.">
                  <div style={{ ...inputStyle, color: T.textMuted, background: T.surface, cursor: "default", userSelect: "all" as const }}>
                    {profile?.email ?? ""}
                  </div>
                </AccountField>
                <AccountField label="Vollständiger Name" hint="Wird in Berichten und Audit-Logs angezeigt.">
                  <input
                    value={profile?.full_name ?? ""}
                    onChange={(e) => setProfile((prev) => (prev ? { ...prev, full_name: e.target.value } : prev))}
                    style={inputStyle}
                    placeholder="Max Mustermann"
                  />
                </AccountField>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <AccountField label="Locale" hint="Sprache / Region (BCP-47)">
                    <input
                      value={profile?.locale ?? ""}
                      onChange={(e) => setProfile((prev) => (prev ? { ...prev, locale: e.target.value } : prev))}
                      style={inputStyle}
                      placeholder="de-DE"
                    />
                  </AccountField>
                  <AccountField label="Zeitzone" hint="IANA-Zeitzone">
                    <input
                      value={profile?.timezone ?? ""}
                      onChange={(e) => setProfile((prev) => (prev ? { ...prev, timezone: e.target.value } : prev))}
                      style={inputStyle}
                      placeholder="Europe/Berlin"
                    />
                  </AccountField>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: "0.03em" }}>Benachrichtigungen & UI</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 6 }}>
                    <ToggleRow
                      label="E-Mail-Benachrichtigungen"
                      description="Eskalationsalarme und Systemmeldungen werden an deine registrierte E-Mail-Adresse gesendet."
                      value={(profile?.notify_email ?? "false") === "true"}
                      onChange={(v) => setProfile((prev) => (prev ? { ...prev, notify_email: v ? "true" : "false" } : prev))}
                    />
                    <ToggleRow
                      label="Telegram-Benachrichtigungen"
                      description="Alarme werden an deinen Telegram-Account gesendet. Chat-ID muss unter Studio-Einstellungen hinterlegt sein."
                      value={(profile?.notify_telegram ?? "false") === "true"}
                      onChange={(v) => setProfile((prev) => (prev ? { ...prev, notify_telegram: v ? "true" : "false" } : prev))}
                    />
                    <ToggleRow
                      label="Kompakter Modus"
                      description="Reduziert den Zeilenabstand in Listen und Tabellen — spart Platz auf kleinen Bildschirmen."
                      value={(profile?.compact_mode ?? "false") === "true"}
                      onChange={(v) => setProfile((prev) => (prev ? { ...prev, compact_mode: v ? "true" : "false" } : prev))}
                    />
                  </div>
                </div>
              </div>

              {/* ── Passwort ändern ──────────────────────────────── */}
              <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.border}` }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 10, letterSpacing: "0.04em", textTransform: "uppercase" }}>Passwort ändern</div>
                <div style={{ display: "grid", gap: 10 }}>
                  <AccountField label="Aktuelles Passwort" hint="Nur ausfüllen wenn du das Passwort ändern möchtest.">
                    <input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} style={inputStyle} placeholder="••••••••" />
                  </AccountField>
                  <AccountField label="Neues Passwort" hint="Mindestens 8 Zeichen.">
                    <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} style={inputStyle} placeholder="••••••••" />
                  </AccountField>
                </div>
              </div>

              <button type="button" onClick={() => void saveProfile()} disabled={savingProfile} style={primaryButtonStyle}>
                {savingProfile ? "Speichere…" : "Profil speichern"}
              </button>
            </Card>

            {/* ── Studio-Einstellungen (tenant_admin) ──────────── */}
            {isTenantAdmin && tenantPrefs && (
              <Card style={{ padding: 14, background: T.surfaceAlt }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: T.text, marginBottom: 4, letterSpacing: "0.04em", textTransform: "uppercase" }}>Studio-Einstellungen</div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 12 }}>Globale Standardwerte für diesen Tenant — gelten für alle Nutzer des Studios. Ops-E-Mail und Telegram werden für Eskalationsalarme und Systemmeldungen verwendet.</div>
                <div style={{ display: "grid", gap: 10 }}>
                  <AccountField label="Studio-Anzeigename" hint="Interner Name für Berichte, Audit-Logs und E-Mails.">
                    <input value={tenantPrefs.tenant_display_name} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_display_name: e.target.value })} style={inputStyle} placeholder="Mein Fitness Studio GmbH" />
                  </AccountField>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <AccountField label="Zeitzone" hint="IANA-Zeitzone des Studios">
                      <input value={tenantPrefs.tenant_timezone} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_timezone: e.target.value })} style={inputStyle} placeholder="Europe/Berlin" />
                    </AccountField>
                    <AccountField label="Locale" hint="Sprache für automatische Texte (BCP-47)">
                      <input value={tenantPrefs.tenant_locale} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_locale: e.target.value })} style={inputStyle} placeholder="de-DE" />
                    </AccountField>
                  </div>
                  <AccountField label="Ops-Benachrichtigungs-E-Mail" hint="E-Mail-Adresse für interne Betriebsmeldungen und Eskalationen.">
                    <input value={tenantPrefs.tenant_notify_email} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_email: e.target.value })} style={inputStyle} placeholder="ops@mein-studio.de" />
                  </AccountField>
                  <AccountField label="Ops Telegram Chat-ID" hint="Numerische Telegram-Chat-ID für Ops-Benachrichtigungen.">
                    <input value={tenantPrefs.tenant_notify_telegram} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_notify_telegram: e.target.value })} style={inputStyle} placeholder="-100123456789" />
                  </AccountField>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <AccountField label="Eskalations-SLA (Minuten)" hint="Nach wie vielen Minuten gilt eine Konversation als eskaliert.">
                      <input value={tenantPrefs.tenant_escalation_sla_minutes} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_escalation_sla_minutes: e.target.value })} style={inputStyle} placeholder="15" />
                    </AccountField>
                    <AccountField label="Live-Refresh-Intervall (Sekunden)" hint="Wie oft das Live-Dashboard automatisch aktualisiert wird.">
                      <input value={tenantPrefs.tenant_live_refresh_seconds} onChange={(e) => setTenantPrefs({ ...tenantPrefs, tenant_live_refresh_seconds: e.target.value })} style={inputStyle} placeholder="5" />
                    </AccountField>
                  </div>
                </div>
                <button type="button" onClick={() => void saveTenantPrefs()} disabled={savingTenant} style={primaryButtonStyle}>
                  {savingTenant ? "Speichere…" : "Studio-Einstellungen speichern"}
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
