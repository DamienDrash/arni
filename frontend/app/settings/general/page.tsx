"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type Setting = { key: string; value: string; description?: string };
type AuditRow = {
  id: number;
  created_at: string | null;
  actor_email: string | null;
  action: string;
  category: string;
  target_type: string | null;
  target_id: string | null;
  details_json: string | null;
};

type PendingChange = {
  key: string;
  value: string;
  critical: boolean;
  label: string;
};

const EXCLUDED_KEYS = new Set([
  "member_memory_cron_enabled",
  "member_memory_cron",
  "member_memory_last_run_at",
  "member_memory_last_run_status",
  "member_memory_llm_enabled",
  "member_memory_llm_model",
  "magicline_api_key",
  "magicline_base_url",
  "magicline_tenant_id",
  "telegram_bot_token",
  "telegram_admin_chat_id",
  "telegram_webhook_secret",
  "meta_access_token",
  "meta_app_secret",
  "meta_verify_token",
  "smtp_host",
  "smtp_port",
  "smtp_username",
  "smtp_password",
  "smtp_from_email",
  "smtp_from_name",
  "smtp_use_starttls",
  "verification_email_subject",
  "billing_stripe_enabled",
  "billing_stripe_mode",
  "billing_stripe_publishable_key",
  "billing_stripe_secret_key",
  "billing_stripe_webhook_secret",
  "billing_plans_json",
  "billing_providers_json",
  "billing_default_provider",
]);

const SETTING_LABELS: Record<string, string> = {
  checkin_enabled: "Check-in System aktiv",
  auth_secret: "Auth Secret",
  acp_secret: "ACP Secret",
  cors_allowed_origins: "CORS Allowed Origins",
  auth_transition_mode: "Auth Transition Mode",
  auth_allow_header_fallback: "Auth Header Fallback",
};

const CRITICAL_KEYS = new Set([
  "auth_secret",
  "acp_secret",
  "cors_allowed_origins",
  "auth_transition_mode",
  "auth_allow_header_fallback",
  "openai_api_key",
  "credentials_encryption_key",
]);



function settingGroup(key: string) {
  if (key.includes("auth") || key.includes("secret") || key.includes("cors")) return "Security";
  if (key.includes("checkin") || key.includes("cron") || key.includes("memory") || key.includes("bridge")) return "Runtime";
  if (key.includes("database") || key.includes("qdrant") || key.includes("redis")) return "Data";
  return "Compliance";
}

function riskLevel(key: string): "low" | "medium" | "high" {
  if (CRITICAL_KEYS.has(key) || key.includes("secret") || key.includes("auth")) return "high";
  if (key.includes("url") || key.includes("port") || key.includes("mode")) return "medium";
  return "low";
}

function impactText(key: string) {
  if (key.includes("auth") || key.includes("secret")) return "Login/Access kann direkt beeinflusst werden.";
  if (key.includes("cors")) return "API-Zugriff aus Browsern wird beeinflusst.";
  if (key.includes("checkin")) return "Member-Enrichment und KPI-Berechnung wird verändert.";
  return "Systemverhalten wird global angepasst.";
}

function validateValue(key: string, value: string) {
  const trimmed = value.trim();
  if (trimmed.length === 0) return "Wert darf nicht leer sein.";
  if (key.includes("cron")) {
    const parts = trimmed.split(/\s+/).filter(Boolean);
    if (parts.length !== 5) return "Cron muss 5 Felder haben (m h dom mon dow).";
  }
  if (key.includes("url")) {
    try {
      new URL(trimmed);
    } catch {
      return "Ungültige URL.";
    }
  }
  if (key.includes("port")) {
    const n = Number(trimmed);
    if (!Number.isInteger(n) || n < 1 || n > 65535) return "Port muss zwischen 1 und 65535 liegen.";
  }
  const boolLikeKeys = ["enabled", "active", "allow", "transition", "fallback"];
  if (boolLikeKeys.some((token) => key.includes(token)) && (trimmed === "true" || trimmed === "false")) return "";
  return "";
}

export default function SettingsGeneralPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [auditRows, setAuditRows] = useState<AuditRow[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingChange | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  const visibleSettings = useMemo(() => settings.filter((s) => !EXCLUDED_KEYS.has(s.key)), [settings]);
  const grouped = useMemo(() => {
    const map = new Map<string, Setting[]>();
    for (const s of visibleSettings) {
      const grp = settingGroup(s.key);
      map.set(grp, [...(map.get(grp) || []), s]);
    }
    return Array.from(map.entries());
  }, [visibleSettings]);

  const recentSettingAudit = useMemo(
    () =>
      auditRows
        .filter((r) => r.action === "setting.update" || r.category === "settings")
        .slice(0, 10),
    [auditRows],
  );

  async function fetchData() {
    const [settingsRes, auditRes] = await Promise.all([apiFetch("/admin/settings"), apiFetch("/auth/audit?limit=250")]);
    if (settingsRes.ok) {
      const rows = (await settingsRes.json()) as Setting[];
      setSettings(rows);
      setDrafts((prev) => {
        const next = { ...prev };
        for (const row of rows) if (!(row.key in next)) next[row.key] = row.value;
        return next;
      });
    }
    if (auditRes.ok) {
      const rows = (await auditRes.json()) as AuditRow[];
      setAuditRows(rows);
    }
  }

  async function saveSetting(key: string, value: string, description?: string) {
    const validation = validateValue(key, value);
    if (validation) {
      setError(`${SETTING_LABELS[key] || key}: ${validation}`);
      return;
    }
    setSaving(key);
    setError("");
    try {
      const res = await apiFetch(`/admin/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value, description: description || undefined }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body?.detail || `Speichern fehlgeschlagen (${res.status}).`);
        return;
      }
      setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)));
      setSaved(key);
      setTimeout(() => setSaved(null), 1800);
      await fetchData();
    } finally {
      setSaving(null);
    }
  }

  function requestSave(setting: Setting, nextValue: string) {
    const isCritical = CRITICAL_KEYS.has(setting.key) || riskLevel(setting.key) === "high";
    setPending({
      key: setting.key,
      value: nextValue,
      critical: isCritical,
      label: SETTING_LABELS[setting.key] || setting.key,
    });
    setReason("");
  }

  async function confirmSave() {
    if (!pending) return;
    if (pending.critical && reason.trim().length < 8) {
      setError("Für kritische Änderungen ist eine Begründung (mind. 8 Zeichen) erforderlich.");
      return;
    }
    await saveSetting(pending.key, pending.value, reason.trim() || undefined);
    setPending(null);
    setReason("");
  }

  useEffect(() => {
    fetchData().finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      <Card style={{ padding: 24 }}>
        <SectionHeader title="Allgemeine Einstellungen" subtitle="Governance-konforme Runtime- und Security-Konfiguration mit Audit-Trail." />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10, marginTop: 10 }}>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Einstellungen</div>
            <div style={{ fontSize: 20, color: T.text, fontWeight: 800 }}>{visibleSettings.length}</div>
          </Card>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Kritisch</div>
            <div style={{ fontSize: 20, color: T.danger, fontWeight: 800 }}>{visibleSettings.filter((s) => riskLevel(s.key) === "high").length}</div>
          </Card>
          <Card style={{ padding: 12, background: T.surfaceAlt }}>
            <div style={{ fontSize: 11, color: T.textDim }}>Audit-Protokoll</div>
            <div style={{ fontSize: 20, color: T.accent, fontWeight: 800 }}>{recentSettingAudit.length}</div>
          </Card>
        </div>

        {error && (
          <div style={{ marginTop: 10, fontSize: 12, color: T.danger, display: "flex", alignItems: "center", gap: 6 }}>
            <AlertTriangle size={14} /> {error}
          </div>
        )}

        {loading ? (
          <div style={{ marginTop: 12, color: T.textMuted, fontSize: 13 }}>Laden…</div>
        ) : (
          <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
            {grouped.map(([group, rows]) => (
              <Card key={group} style={{ padding: 14, background: T.surfaceAlt }}>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>{group}</div>
                <div style={{ display: "grid", gap: 10 }}>
                  {rows.map((s) => {
                    const boolLike = s.value === "true" || s.value === "false";
                    const label = SETTING_LABELS[s.key] ?? s.key;
                    const risk = riskLevel(s.key);
                    const isSaving = saving === s.key;
                    const draft = drafts[s.key] ?? s.value;
                    return (
                      <div key={s.key} style={{ display: "flex", justifyContent: "space-between", gap: 12, borderTop: `1px solid ${T.border}`, paddingTop: 10 }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <div style={{ color: T.text, fontSize: 13, fontWeight: 700 }}>{label}</div>
                            <span className={`badge badge-sm badge-outline font-bold ${risk === "high" ? "badge-error" : risk === "medium" ? "badge-wariiang" : "badge-success"}`}>
                              {risk.toUpperCase()}
                            </span>
                          </div>
                          <div style={{ marginTop: 2, color: T.textMuted, fontSize: 12 }}>{s.description || impactText(s.key)}</div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {saved === s.key && <span style={{ color: T.success, fontSize: 11, fontWeight: 700 }}>Gespeichert</span>}
                          {risk === "high" && <ShieldCheck size={14} color={T.danger} />}
                          {boolLike ? (
                            <ToggleSwitch
                              value={draft === "true"}
                              label={label}
                              onChange={(v) => {
                                const next = v ? "true" : "false";
                                setDrafts((prev) => ({ ...prev, [s.key]: next }));
                                requestSave(s, next);
                              }}
                            />
                          ) : (
                            <input
                              value={draft}
                              onChange={(e) => setDrafts((prev) => ({ ...prev, [s.key]: e.target.value }))}
                              onBlur={() => {
                                if (draft !== s.value) requestSave(s, draft);
                              }}
                              disabled={isSaving}
                              className="input input-sm input-bordered w-[280px]"
                            />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}

            <Card style={{ padding: 14 }}>
              <div style={{ fontSize: 11, color: T.textDim, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Letzte Einstellungs-Änderungen
              </div>
              <div style={{ display: "grid", gap: 8 }}>
                {recentSettingAudit.length === 0 ? (
                  <div style={{ fontSize: 12, color: T.textMuted }}>Noch keine Einstellungs-Audit-Ereignisse vorhanden.</div>
                ) : recentSettingAudit.map((row) => (
                  <div key={row.id} style={{ border: `1px solid ${T.border}`, borderRadius: 10, padding: "8px 10px", background: T.surfaceAlt }}>
                    <div style={{ fontSize: 12, color: T.text, fontWeight: 700 }}>{row.target_id || "setting"} · {row.action}</div>
                    <div style={{ marginTop: 2, fontSize: 11, color: T.textDim }}>
                      {row.created_at ? new Date(row.created_at).toLocaleString("de-DE") : "-"} · {row.actor_email || "system"}
                    </div>
                    {row.details_json && <div style={{ marginTop: 4, fontSize: 11, color: T.textMuted }}>{extractReason(row.details_json)}</div>}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </Card>

      <Modal
        open={!!pending}
        onClose={() => setPending(null)}
        title={pending ? `Änderung bestätigen: ${pending.label}` : "Änderung bestätigen"}
        subtitle={pending?.critical ? "Kritische Änderung: Audit-Reason erforderlich." : "Änderung wird im Audit-Log gespeichert."}
        width="min(720px, 100%)"
      >
        {pending && (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ fontSize: 12, color: T.textMuted }}>
              Schlüssel: <code>{pending.key}</code> · Neuer Wert wird angewendet.
            </div>
            <textarea
              placeholder={pending.critical ? "Grund der Änderung (Pflicht)" : "Optionale Begründung für Audit-Log"}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              style={{
                minHeight: 96,
                borderRadius: 10,
                border: `1px solid ${T.border}`,
                background: T.surfaceAlt,
                color: T.text,
                padding: "10px 12px",
                fontSize: 13,
                outline: "none",
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button onClick={() => setPending(null)} className="btn btn-ghost">Abbrechen</button>
              <button onClick={() => void confirmSave()} className="btn btn-primary">Bestätigen & speichern</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function extractReason(detailsJson: string) {
  try {
    const parsed = JSON.parse(detailsJson) as { reason?: string };
    if (parsed.reason && parsed.reason.trim()) return `Reason: ${parsed.reason}`;
  } catch {
    // ignore parse issues
  }
  return "";
}


