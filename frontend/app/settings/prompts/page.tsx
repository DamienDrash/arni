"use client";

import { useEffect, useState } from "react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";
import { useConfirm } from "@/components/ui/ConfirmModal";

// ── Types ─────────────────────────────────────────────────────────────────

interface PromptConfig {
  studio_name: string;
  studio_short_name: string;
  agent_display_name: string;
  studio_locale: string;
  studio_timezone: string;
  studio_emergency_number: string;
  studio_address: string;
  sales_prices_text: string;
  sales_retention_rules: string;
  medic_disclaimer_text: string;
  persona_bio_text: string;
}

interface AgentTemplate {
  agent: string;
  is_custom: boolean;
  content: string;
  mtime: number;
}

// ── Field metadata ─────────────────────────────────────────────────────────

const FIELD_META: Record<keyof PromptConfig, { label: string; help: string; multiline?: boolean }> = {
  studio_name: { label: "Studio-Name (vollständig)", help: 'z.B. "GetImpulse Berlin"' },
  studio_short_name: { label: "Studio-Kurzname", help: 'z.B. "GetImpulse"' },
  agent_display_name: { label: "Agent-Name", help: 'Name des Assistenten, z.B. "ARIIA"' },
  studio_locale: { label: "Sprache / Locale", help: 'z.B. "de-DE", "en-US"' },
  studio_timezone: { label: "Zeitzone", help: 'IANA-Zeitzone, z.B. "Europe/Berlin"' },
  studio_emergency_number: { label: "Notrufnummer", help: 'z.B. "112" (DE) oder "911" (US)' },
  studio_address: { label: "Studio-Adresse", help: "Adresse für Agent-Antworten (optional)" },
  sales_prices_text: {
    label: "Tarifstruktur (Markdown)",
    help: "Preisliste die der Sales-Agent nutzt",
    multiline: true,
  },
  sales_retention_rules: {
    label: "Retention-Regeln",
    help: "Regeln für den Sales-Agent zur Kundenbindung",
    multiline: true,
  },
  medic_disclaimer_text: {
    label: "Medizinischer Disclaimer",
    help: "Pflicht-Disclaimer der dem Medic-Agent angehängt wird",
    multiline: true,
  },
  persona_bio_text: {
    label: "Agent-Persönlichkeit",
    help: "Charakterbeschreibung / Persona des Assistenten",
    multiline: true,
  },
};

const AGENTS = [
  { id: "persona", label: "Persona (Smalltalk)" },
  { id: "sales", label: "Sales (Retention)" },
  { id: "medic", label: "Medic (Coach)" },
  { id: "router", label: "Router (Intent-Classifier)" },
  { id: "ops", label: "Ops (Buchungen)" },
];

// ── Variables tab ──────────────────────────────────────────────────────────

function VariablesTab() {
  const [config, setConfig] = useState<Partial<PromptConfig>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/admin/prompt-config")
      .then((r) => r.json())
      .then((data) => setConfig(data as Partial<PromptConfig>))
      .catch(() => setError("Fehler beim Laden der Konfiguration."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: keyof PromptConfig, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/prompt-config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError("Speichern fehlgeschlagen. Bitte versuche es erneut.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-gray-400">Konfiguration wird geladen...</div>;

  return (
    <div className="space-y-6">
      <p className="text-gray-400 text-sm">
        Diese Platzhalter werden in alle Agent-Templates als{" "}
        <code className="text-blue-400">{"{{ variable }}"}</code> eingesetzt. Änderungen sind sofort aktiv.
      </p>

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <div className="space-y-5">
        {(Object.keys(FIELD_META) as (keyof PromptConfig)[]).map((key) => {
          const meta = FIELD_META[key];
          return (
            <div key={key} className="space-y-1">
              <label className="block text-sm font-medium text-gray-200">{meta.label}</label>
              <p className="text-xs text-gray-500">{meta.help}</p>
              {meta.multiline ? (
                <textarea
                  rows={5}
                  value={config[key] ?? ""}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                />
              ) : (
                <input
                  type="text"
                  value={config[key] ?? ""}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-4 pt-4 border-t border-gray-800">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saving ? "Speichern..." : "Speichern"}
        </button>
        {saved && <span className="text-green-400 text-sm">Gespeichert. Agents nutzen die neuen Werte sofort.</span>}
      </div>
    </div>
  );
}

// ── Templates tab ──────────────────────────────────────────────────────────

function TemplatesTab() {
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0].id);
  const [template, setTemplate] = useState<AgentTemplate | null>(null);
  const [editContent, setEditContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const { confirm, ConfirmComponent } = useConfirm();

  const loadTemplate = async (agent: string) => {
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const res = await apiFetch(`/admin/prompts/agent/${agent}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AgentTemplate = await res.json();
      setTemplate(data);
      setEditContent(data.content);
    } catch (e) {
      setError(`Fehler beim Laden des Templates: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplate(selectedAgent);
  }, [selectedAgent]);

  const handleSave = async () => {
    if (!reason.trim() || reason.trim().length < 8) {
      setError("Bitte gib einen Änderungsgrund an (min. 8 Zeichen).");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/admin/prompts/agent/${selectedAgent}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editContent, base_mtime: template?.mtime, reason }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setTemplate((prev) => prev ? { ...prev, is_custom: true, mtime: data.mtime } : prev);
      setSaved(true);
      setReason("");
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      setError(`Speichern fehlgeschlagen: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    const isConfirmed = await confirm(`Möchtest du das Custom-Template für '${selectedAgent}' wirklich löschen und zum Standard zurückkehren?`);
    if (!isConfirmed) return;
    setResetting(true);
    try {
      await apiFetch(`/admin/prompts/agent/${selectedAgent}`, { method: "DELETE" });
      await loadTemplate(selectedAgent);
    } catch {
      setError("Reset fehlgeschlagen.");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-gray-400 text-sm">
        Jinja2-System-Prompts pro Agent anpassen. Verwende{" "}
        <code className="text-blue-400">{"{{ variable }}"}</code> für Platzhalter aus dem Variables-Tab.
        Ohne Custom-Template wird das System-Default verwendet.
      </p>

      {/* Agent selector */}
      <div className="flex flex-wrap gap-2">
        {AGENTS.map((a) => (
          <button
            key={a.id}
            onClick={() => setSelectedAgent(a.id)}
            className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${selectedAgent === a.id
                ? "bg-blue-600 border-blue-500 text-white"
                : "bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600"
              }`}
          >
            {a.label}
          </button>
        ))}
      </div>

      {/* Status badge */}
      {template && (
        <div className="flex items-center gap-2">
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${template.is_custom ? "bg-yellow-900/50 text-yellow-300 border border-yellow-700" : "bg-gray-800 text-gray-400 border border-gray-700"
              }`}
          >
            {template.is_custom ? "Custom Override aktiv" : "System-Default"}
          </span>
          {template.is_custom && (
            <button
              onClick={handleReset}
              disabled={resetting}
              className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
            >
              {resetting ? "Resetting..." : "Zurücksetzen"}
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-gray-400 text-sm py-4">Template wird geladen...</div>
      ) : (
        <>
          <textarea
            rows={24}
            value={editContent}
            onChange={(e) => { setEditContent(e.target.value); setSaved(false); }}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            spellCheck={false}
          />

          <div className="space-y-2">
            <input
              type="text"
              placeholder="Änderungsgrund (min. 8 Zeichen, wird in Audit-Log gespeichert)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {saving ? "Speichern..." : "Template speichern"}
            </button>
            {saved && <span className="text-green-400 text-sm">Gespeichert. Agent nutzt das Custom-Template ab sofort.</span>}
          </div>
        </>
      )}
      {ConfirmComponent}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

type Tab = "variables" | "templates";

export default function PromptsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("variables");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <div className="max-w-4xl mx-auto p-6 space-y-6" style={{ width: "100%" }}>
        <div>
          <h1 className="text-2xl font-bold text-white">Agent-Konfiguration</h1>
          <p className="text-gray-400 mt-1 text-sm">
            Personalisiere das Verhalten deines Assistenten — von einfachen Variablen bis hin zu vollständigen Jinja2-Prompt-Templates.
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 border-b border-gray-800">
          {(["variables", "templates"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${activeTab === tab
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-300"
                }`}
            >
              {tab === "variables" ? "Variablen" : "Jinja2 Templates"}
            </button>
          ))}
        </div>

        {activeTab === "variables" ? <VariablesTab /> : <TemplatesTab />}
      </div>
    </div>
  );
}
