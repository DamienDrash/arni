"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Building2, Bot, MapPin, TrendingUp, HeartPulse, Calendar,
  AlertTriangle, ChevronDown, ChevronRight, Save, RotateCcw,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { apiFetch } from "@/lib/api";
import { useConfirm } from "@/components/ui/ConfirmModal";

// ── Types ─────────────────────────────────────────────────────────────────

interface VariableSchema {
  key: string;
  label: string;
  help: string;
  category: string;
  multiline: boolean;
  default: string;
}

interface CategorySchema {
  id: string;
  label: string;
  description: string;
  icon: string;
}

interface AgentTemplate {
  agent: string;
  is_custom: boolean;
  content: string;
  mtime: number;
}

// ── Icon mapping ──────────────────────────────────────────────────────────

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Building2, Bot, MapPin, TrendingUp, HeartPulse, Calendar, AlertTriangle,
};

// ── Agent definitions ─────────────────────────────────────────────────────

const AGENTS = [
  { id: "persona", label: "Persona", desc: "Smalltalk & Persönlichkeit", color: "blue" },
  { id: "concierge", label: "Concierge", desc: "FAQ & Allgemeine Infos", color: "emerald" },
  { id: "sales", label: "Sales", desc: "Preise & Retention", color: "amber" },
  { id: "medic", label: "Health", desc: "Gesundheitsberatung", color: "red" },
  { id: "booking", label: "Booking", desc: "Termine & Buchungen", color: "violet" },
  { id: "ops", label: "Operations", desc: "Systemoperationen", color: "cyan" },
  { id: "escalation", label: "Eskalation", desc: "Weiterleitung an Menschen", color: "orange" },
  { id: "router", label: "Router", desc: "Intent-Klassifizierung", color: "gray" },
];

// ── Variables tab (schema-driven) ─────────────────────────────────────────

function VariablesTab() {
  const [config, setConfig] = useState<Record<string, string>>({});
  const [schema, setSchema] = useState<{ categories: CategorySchema[]; variables: VariableSchema[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(["business", "agent"]));

  useEffect(() => {
    Promise.all([
      apiFetch("/admin/prompt-config").then((r) => r.json()),
      apiFetch("/admin/prompt-config/schema").then((r) => r.json()).catch(() => null),
    ])
      .then(([configData, schemaData]) => {
        setConfig(configData as Record<string, string>);
        if (schemaData) {
          setSchema(schemaData);
        } else {
          // Fallback: generate schema from config keys
          setSchema(null);
        }
      })
      .catch(() => setError("Fehler beim Laden der Konfiguration."))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (key: string, value: string) => {
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

  const toggleCategory = (catId: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(catId)) next.delete(catId);
      else next.add(catId);
      return next;
    });
  };

  if (loading) return <div className="p-8 text-gray-400">Konfiguration wird geladen...</div>;

  // Group variables by category
  const categories = schema?.categories ?? [
    { id: "business", label: "Unternehmen", description: "Grundlegende Informationen", icon: "Building2" },
    { id: "agent", label: "Agent-Identität", description: "Name und Persönlichkeit", icon: "Bot" },
    { id: "contact", label: "Kontakt & Standort", description: "Kontaktdaten und Adresse", icon: "MapPin" },
    { id: "sales", label: "Sales & Retention", description: "Preise und Kundenbindung", icon: "TrendingUp" },
    { id: "health", label: "Gesundheit & Sicherheit", description: "Disclaimer und Beratungsregeln", icon: "HeartPulse" },
    { id: "booking", label: "Buchung & Termine", description: "Buchungsanweisungen", icon: "Calendar" },
    { id: "escalation", label: "Eskalation", description: "Weiterleitung an Menschen", icon: "AlertTriangle" },
  ];

  const variables = schema?.variables ?? Object.keys(config).map((key) => ({
    key,
    label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    help: "",
    category: "business",
    multiline: (config[key] ?? "").length > 100,
    default: "",
  }));

  const variablesByCategory = categories.map((cat) => ({
    ...cat,
    vars: variables.filter((v) => v.category === cat.id),
  })).filter((cat) => cat.vars.length > 0);

  return (
    <div className="space-y-4">
      <p className="text-gray-400 text-sm">
        Diese Variablen werden in alle Agent-Templates als{" "}
        <code className="text-blue-400 bg-gray-800 px-1 rounded">{"{{ variable }}"}</code>{" "}
        eingesetzt. Änderungen sind sofort aktiv.
      </p>

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
      )}

      <div className="space-y-3">
        {variablesByCategory.map((cat) => {
          const IconComp = ICON_MAP[cat.icon] ?? Building2;
          const isExpanded = expandedCategories.has(cat.id);
          const filledCount = cat.vars.filter((v) => (config[v.key] ?? "").trim().length > 0).length;

          return (
            <div key={cat.id} className="border border-gray-800 rounded-lg overflow-hidden">
              {/* Category header */}
              <button
                onClick={() => toggleCategory(cat.id)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-gray-900/50 hover:bg-gray-900 transition-colors text-left"
              >
                <IconComp className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-200">{cat.label}</span>
                  <span className="text-xs text-gray-500 ml-2">{cat.description}</span>
                </div>
                <span className="text-xs text-gray-500 tabular-nums">
                  {filledCount}/{cat.vars.length}
                </span>
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-gray-500" />
                )}
              </button>

              {/* Category fields */}
              {isExpanded && (
                <div className="px-4 py-4 space-y-4 border-t border-gray-800">
                  {cat.vars.map((v) => (
                    <div key={v.key} className="space-y-1">
                      <label className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-200">{v.label}</span>
                        <code className="text-[10px] text-gray-600 bg-gray-800 px-1 rounded">{v.key}</code>
                      </label>
                      {v.help && <p className="text-xs text-gray-500">{v.help}</p>}
                      {v.multiline ? (
                        <textarea
                          rows={5}
                          value={config[v.key] ?? ""}
                          onChange={(e) => handleChange(v.key, e.target.value)}
                          placeholder={v.default || undefined}
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono placeholder:text-gray-600"
                        />
                      ) : (
                        <input
                          type="text"
                          value={config[v.key] ?? ""}
                          onChange={(e) => handleChange(v.key, e.target.value)}
                          placeholder={v.default || undefined}
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-600"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-4 pt-4 border-t border-gray-800">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Save className="w-4 h-4" />
          {saving ? "Speichern..." : "Alle Variablen speichern"}
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

  const loadTemplate = useCallback(async (agent: string) => {
    setLoading(true);
    setError(null);
    setSaved(false);
    try {
      const res = await apiFetch(`/admin/prompts/agent/${agent}`);
      if (!res.ok) {
        if (res.status === 404) {
          // New agent without template yet
          setTemplate({ agent, is_custom: false, content: `# ${agent}/system.j2\n\n# Dieses Template wurde noch nicht erstellt.\n# Erstelle es hier oder nutze das System-Default.`, mtime: 0 });
          setEditContent("");
          return;
        }
        throw new Error(`HTTP ${res.status}`);
      }
      const data: AgentTemplate = await res.json();
      setTemplate(data);
      setEditContent(data.content);
    } catch (e) {
      setError(`Fehler beim Laden des Templates: ${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTemplate(selectedAgent);
  }, [selectedAgent, loadTemplate]);

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
    const isConfirmed = await confirm(
      `Möchtest du das Custom-Template für '${selectedAgent}' wirklich löschen und zum Standard zurückkehren?`
    );
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

  const agentMeta = AGENTS.find((a) => a.id === selectedAgent);

  return (
    <div className="space-y-4">
      <p className="text-gray-400 text-sm">
        Jinja2-System-Prompts pro Agent anpassen. Verwende{" "}
        <code className="text-blue-400 bg-gray-800 px-1 rounded">{"{{ variable }}"}</code>{" "}
        für Platzhalter aus dem Variablen-Tab.
      </p>

      {/* Agent selector - grid layout */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {AGENTS.map((a) => (
          <button
            key={a.id}
            onClick={() => setSelectedAgent(a.id)}
            className={`flex flex-col items-start px-3 py-2 text-left rounded-lg border transition-all ${
              selectedAgent === a.id
                ? "bg-blue-600/20 border-blue-500 ring-1 ring-blue-500/50"
                : "bg-gray-900 border-gray-800 hover:border-gray-700"
            }`}
          >
            <span className={`text-sm font-medium ${selectedAgent === a.id ? "text-blue-300" : "text-gray-200"}`}>
              {a.label}
            </span>
            <span className="text-[10px] text-gray-500 mt-0.5">{a.desc}</span>
          </button>
        ))}
      </div>

      {/* Status badge */}
      {template && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 font-mono">{agentMeta?.id}/system.j2</span>
          <span className="text-gray-700">|</span>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              template.is_custom
                ? "bg-yellow-900/50 text-yellow-300 border border-yellow-700"
                : "bg-gray-800 text-gray-400 border border-gray-700"
            }`}
          >
            {template.is_custom ? "Custom Override" : "System-Default"}
          </span>
          {template.is_custom && (
            <button
              onClick={handleReset}
              disabled={resetting}
              className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
            >
              <RotateCcw className="w-3 h-3" />
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
            rows={28}
            value={editContent}
            onChange={(e) => {
              setEditContent(e.target.value);
              setSaved(false);
            }}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 text-sm text-gray-100 font-mono leading-relaxed focus:outline-none focus:ring-2 focus:ring-blue-500"
            spellCheck={false}
          />

          <div className="space-y-2">
            <input
              type="text"
              placeholder="Änderungsgrund (min. 8 Zeichen) — z.B. 'Tonalität angepasst'"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Save className="w-4 h-4" />
              {saving ? "Speichern..." : "Template speichern"}
            </button>
            {saved && (
              <span className="text-green-400 text-sm">
                Gespeichert. Agent nutzt das Custom-Template ab sofort.
              </span>
            )}
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
            Personalisiere das Verhalten deines KI-Assistenten — von Variablen bis hin zu vollständigen Jinja2-Prompt-Templates.
          </p>
        </div>

        {/* Tab navigation */}
        <div className="flex gap-1 border-b border-gray-800">
          {(["variables", "templates"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab
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
