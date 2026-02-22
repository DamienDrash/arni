"use client";

import { useEffect, useMemo, useState } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

type Setting = { key: string; value: string; description?: string };
type MemoryStatus = {
  cron_enabled: boolean;
  cron_expr: string;
  llm_enabled: boolean;
  llm_model: string;
  last_run_at: string;
  last_run_status: string;
  last_run_error: string;
};

const AUTO_KEYS = [
  "member_memory_cron_enabled",
  "member_memory_cron",
  "member_memory_llm_enabled",
  "member_memory_llm_model",
  "member_memory_last_run_at",
  "member_memory_last_run_status",
];

export default function SettingsAutomationPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [status, setStatus] = useState<MemoryStatus | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const byKey = useMemo(() => {
    const map = new Map<string, Setting>();
    settings.forEach((s) => map.set(s.key, s));
    return map;
  }, [settings]);

  async function fetchSettings() {
    const [res, statusRes] = await Promise.all([
      apiFetch("/admin/settings"),
      apiFetch("/admin/member-memory/status"),
    ]);
    if (res.ok) {
      const all = (await res.json()) as Setting[];
      setSettings(all.filter((s) => AUTO_KEYS.includes(s.key)));
    }
    if (statusRes.ok) {
      setStatus((await statusRes.json()) as MemoryStatus);
    }
  }

  async function saveSetting(key: string, value: string) {
    setSaving(key);
    try {
      const res = await apiFetch(`/admin/settings/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) return;
      setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)));
      setSaved(key);
      setTimeout(() => setSaved(null), 1800);
    } finally {
      setSaving(null);
    }
  }

  async function runNow() {
    setRunning(true);
    try {
      const res = await apiFetch("/admin/member-memory/analyze-now", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) await fetchSettings();
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void fetchSettings();
    const timer = setInterval(() => void fetchSettings(), 30000);
    return () => clearInterval(timer);
  }, []);

  const cronEnabled = status?.cron_enabled ?? (byKey.get("member_memory_cron_enabled")?.value === "true");
  const llmEnabled = status?.llm_enabled ?? (byKey.get("member_memory_llm_enabled")?.value === "true");
  const cron = status?.cron_expr || byKey.get("member_memory_cron")?.value || "";
  const model = status?.llm_model || byKey.get("member_memory_llm_model")?.value || "";
  const lastRunAt = status?.last_run_at || byKey.get("member_memory_last_run_at")?.value || "";
  const lastRunStatus = status?.last_run_status || byKey.get("member_memory_last_run_status")?.value || "never";
  const lastRunError = status?.last_run_error || "";
  const statusColor = lastRunStatus.startsWith("error") ? T.danger : lastRunStatus === "ok" ? T.success : T.textDim;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />

      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Automation"
          subtitle="Zeitplan und LLM-Extraktion für tägliche Member-Memory Analyse."
          action={
            <button
              onClick={runNow}
              disabled={running}
              style={{
                border: "none",
                borderRadius: 9,
                background: T.accent,
                color: "#071018",
                fontWeight: 700,
                padding: "8px 12px",
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              {running ? "Läuft…" : "Analyse jetzt"}
            </button>
          }
        />

        <div style={{ marginTop: 6, display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
            <Card style={{ padding: 12, background: T.surfaceAlt }}>
              <div style={{ fontSize: 11, color: T.textDim }}>Scheduler</div>
              <div style={{ marginTop: 2, fontSize: 18, fontWeight: 800, color: cronEnabled ? T.success : T.warning }}>
                {cronEnabled ? "Aktiv" : "Pausiert"}
              </div>
            </Card>
            <Card style={{ padding: 12, background: T.surfaceAlt }}>
              <div style={{ fontSize: 11, color: T.textDim }}>LLM</div>
              <div style={{ marginTop: 2, fontSize: 18, fontWeight: 800, color: llmEnabled ? T.success : T.warning }}>
                {llmEnabled ? "Aktiv" : "Deaktiviert"}
              </div>
            </Card>
            <Card style={{ padding: 12, background: T.surfaceAlt }}>
              <div style={{ fontSize: 11, color: T.textDim }}>Last Run</div>
              <div style={{ marginTop: 2, fontSize: 13, fontWeight: 700, color: statusColor }}>
                {lastRunStatus}
              </div>
            </Card>
          </div>

          <Card style={{ padding: 14, background: T.surfaceAlt }}>
            <div style={rowStyle}>
              <div>
                <div style={labelStyle}>Scheduler aktiv</div>
                <div style={hintStyle}>Aktiviert tägliche Ausführung gemäß Cron-Ausdruck.</div>
              </div>
                <div style={controlWrapStyle}>
                  {saved === "member_memory_cron_enabled" && <span style={savedStyle}>Gespeichert</span>}
                <ToggleSwitch
                  value={cronEnabled}
                  label="Scheduler aktiv"
                  onChange={(v) => saveSetting("member_memory_cron_enabled", v ? "true" : "false")}
                />
              </div>
            </div>
            <div style={rowStyle}>
              <div>
                <div style={labelStyle}>Cron Ausdruck (UTC)</div>
                <div style={hintStyle}>Beispiel: `0 2 * * *` für tägliche Ausführung um 02:00 UTC.</div>
              </div>
              <div style={controlWrapStyle}>
                {saved === "member_memory_cron" && <span style={savedStyle}>Gespeichert</span>}
                <input
                  defaultValue={cron}
                  onBlur={(e) => {
                    if (e.target.value !== cron) saveSetting("member_memory_cron", e.target.value);
                  }}
                  disabled={saving === "member_memory_cron"}
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
              {[
                { label: "Täglich 02:00 UTC", value: "0 2 * * *" },
                { label: "Täglich 01:00 UTC", value: "0 1 * * *" },
                { label: "Alle 12h", value: "0 */12 * * *" },
              ].map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() => saveSetting("member_memory_cron", preset.value)}
                  style={{
                    borderRadius: 8,
                    border: `1px solid ${T.border}`,
                    background: T.surface,
                    color: T.text,
                    fontSize: 11,
                    padding: "6px 8px",
                    cursor: "pointer",
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </Card>

          <Card style={{ padding: 14, background: T.surfaceAlt }}>
            <div style={rowStyle}>
              <div>
                <div style={labelStyle}>LLM Extraktion aktiv</div>
                <div style={hintStyle}>Aktiviert die Profilerstellung aus Chatverläufen.</div>
              </div>
              <div style={controlWrapStyle}>
                {saved === "member_memory_llm_enabled" && <span style={savedStyle}>Gespeichert</span>}
                <ToggleSwitch
                  value={llmEnabled}
                  label="LLM Extraktion aktiv"
                  onChange={(v) => saveSetting("member_memory_llm_enabled", v ? "true" : "false")}
                />
              </div>
            </div>
            <div style={rowStyle}>
              <div>
                <div style={labelStyle}>LLM Modell</div>
                <div style={hintStyle}>Fallback-sicheres Modell für die tägliche Analyse.</div>
              </div>
              <div style={controlWrapStyle}>
                {saved === "member_memory_llm_model" && <span style={savedStyle}>Gespeichert</span>}
                <input
                  defaultValue={model}
                  onBlur={(e) => {
                    if (e.target.value !== model) saveSetting("member_memory_llm_model", e.target.value);
                  }}
                  disabled={saving === "member_memory_llm_model"}
                  style={inputStyle}
                />
              </div>
            </div>
          </Card>

          <Card style={{ padding: 14, background: T.surfaceAlt }}>
            <div style={rowStyle}>
              <div>
                <div style={labelStyle}>Last Run</div>
                <div style={hintStyle}>{lastRunAt ? new Date(lastRunAt).toLocaleString("de-DE") : "Noch kein Lauf."}</div>
              </div>
              <div style={{ color: statusColor, fontSize: 12, fontWeight: 700 }}>Status: {lastRunStatus}</div>
            </div>
            {lastRunError && (
              <div style={{ marginTop: 8, fontSize: 12, color: T.danger }}>
                Fehlerdetails: {lastRunError}
              </div>
            )}
          </Card>
        </div>
      </Card>
    </div>
  );
}

const rowStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: 12,
  padding: "8px 0",
};

const labelStyle = { color: T.text, fontSize: 13, fontWeight: 700 };
const hintStyle = { color: T.textMuted, fontSize: 12, marginTop: 2, lineHeight: 1.5 };
const controlWrapStyle = { display: "flex", alignItems: "center", gap: 8 };
const savedStyle = { color: T.success, fontSize: 11, fontWeight: 600 };
const inputStyle = {
  width: 220,
  padding: "7px 10px",
  borderRadius: 8,
  border: `1px solid ${T.border}`,
  background: T.surface,
  color: T.text,
  fontSize: 13,
  outline: "none",
};
