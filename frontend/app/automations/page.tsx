"use client";

import React, { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Zap,
  Plus,
  Play,
  Pause,
  Trash2,
  Eye,
  Pencil,
  BarChart3,
  RefreshCw,
  Search,
  ChevronLeft,
  Save,
  Users,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

// Dynamically import WorkflowBuilder (no SSR)
const WorkflowBuilder = dynamic(
  () => import("@/components/automations/WorkflowBuilder"),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-96"><RefreshCw className="animate-spin" size={24} /></div> }
);

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface Workflow {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  trigger_type: string;
  trigger_config_json: string | null;
  workflow_graph_json: string;
  max_concurrent_runs: number;
  re_entry_policy: string;
  active_runs: number;
  created_at: string | null;
  updated_at: string | null;
}

interface AutomationStats {
  total_workflows: number;
  active_workflows: number;
  active_runs: number;
  completed_runs: number;
  error_runs: number;
}

interface Run {
  id: number;
  workflow_id: number;
  contact_id: number;
  status: string;
  current_node_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Trigger Type Labels
   ═══════════════════════════════════════════════════════════════════════ */

const TRIGGER_LABELS: Record<string, string> = {
  segment_entry: "Segment-Eintritt",
  segment_exit: "Segment-Austritt",
  contact_created: "Neuer Kontakt",
  tag_added: "Tag hinzugefügt",
  tag_removed: "Tag entfernt",
  lifecycle_change: "Lifecycle-Änderung",
  manual: "Manuell",
};

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  active: { label: "Aktiv", color: "text-green-600 bg-green-50", icon: <Play size={12} /> },
  waiting: { label: "Wartend", color: "text-amber-600 bg-amber-50", icon: <Clock size={12} /> },
  completed: { label: "Abgeschlossen", color: "text-blue-600 bg-blue-50", icon: <CheckCircle size={12} /> },
  cancelled: { label: "Abgebrochen", color: "text-gray-600 bg-gray-50", icon: <XCircle size={12} /> },
  error: { label: "Fehler", color: "text-red-600 bg-red-50", icon: <AlertCircle size={12} /> },
};

/* ═══════════════════════════════════════════════════════════════════════════
   Main Page Component
   ═══════════════════════════════════════════════════════════════════════ */

type ViewMode = "list" | "create" | "edit" | "runs";

export default function AutomationsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [stats, setStats] = useState<AutomationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formTriggerType, setFormTriggerType] = useState("segment_entry");
  const [formTriggerConfig, setFormTriggerConfig] = useState("{}");
  const [formReEntryPolicy, setFormReEntryPolicy] = useState("skip");
  const [formMaxRuns, setFormMaxRuns] = useState(1000);
  const [formGraph, setFormGraph] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ─── Data Loading ──────────────────────────────────────────────────── */

  const loadWorkflows = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      const res = await apiFetch(`/v2/admin/automations?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setWorkflows(data.items || []);
      }
    } catch (e) {
      console.error("Failed to load workflows", e);
    }
    setLoading(false);
  }, [search]);

  const loadStats = useCallback(async () => {
    try {
      const res = await apiFetch("/v2/admin/automations/stats");
      if (res.ok) setStats(await res.json());
    } catch (e) {
      console.error("Failed to load stats", e);
    }
  }, []);

  const loadRuns = useCallback(async (workflowId: number) => {
    try {
      const res = await apiFetch(`/v2/admin/automations/${workflowId}/runs?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.items || []);
      }
    } catch (e) {
      console.error("Failed to load runs", e);
    }
  }, []);

  useEffect(() => {
    loadWorkflows();
    loadStats();
  }, [loadWorkflows, loadStats]);

  /* ─── Actions ───────────────────────────────────────────────────────── */

  const handleCreate = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/v2/admin/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formName,
          description: formDescription || null,
          trigger_type: formTriggerType,
          trigger_config_json: formTriggerConfig || null,
          workflow_graph_json: JSON.stringify(formGraph),
          max_concurrent_runs: formMaxRuns,
          re_entry_policy: formReEntryPolicy,
        }),
      });
      if (res.ok) {
        setViewMode("list");
        loadWorkflows();
        loadStats();
      } else {
        const data = await res.json();
        setError(data.detail || "Fehler beim Erstellen");
      }
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleUpdate = async () => {
    if (!selectedWorkflow) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/v2/admin/automations/${selectedWorkflow.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formName,
          description: formDescription || null,
          trigger_type: formTriggerType,
          trigger_config_json: formTriggerConfig || null,
          workflow_graph_json: JSON.stringify(formGraph),
          max_concurrent_runs: formMaxRuns,
          re_entry_policy: formReEntryPolicy,
        }),
      });
      if (res.ok) {
        setViewMode("list");
        loadWorkflows();
      } else {
        const data = await res.json();
        setError(data.detail || "Fehler beim Speichern");
      }
    } catch (e: any) {
      setError(e.message);
    }
    setSaving(false);
  };

  const handleToggleActive = async (wf: Workflow) => {
    const action = wf.is_active ? "deactivate" : "activate";
    try {
      const res = await apiFetch(`/v2/admin/automations/${wf.id}/${action}`, { method: "POST" });
      if (res.ok) {
        loadWorkflows();
        loadStats();
      }
    } catch (e) {
      console.error("Toggle failed", e);
    }
  };

  const handleDelete = async (wf: Workflow) => {
    if (!confirm(`Workflow "${wf.name}" wirklich löschen?`)) return;
    try {
      const res = await apiFetch(`/v2/admin/automations/${wf.id}`, { method: "DELETE" });
      if (res.ok) {
        loadWorkflows();
        loadStats();
      }
    } catch (e) {
      console.error("Delete failed", e);
    }
  };

  const openCreate = () => {
    setFormName("");
    setFormDescription("");
    setFormTriggerType("segment_entry");
    setFormTriggerConfig("{}");
    setFormReEntryPolicy("skip");
    setFormMaxRuns(1000);
    setFormGraph({ nodes: [], edges: [] });
    setSelectedWorkflow(null);
    setError(null);
    setViewMode("create");
  };

  const openEdit = (wf: Workflow) => {
    setFormName(wf.name);
    setFormDescription(wf.description || "");
    setFormTriggerType(wf.trigger_type);
    setFormTriggerConfig(wf.trigger_config_json || "{}");
    setFormReEntryPolicy(wf.re_entry_policy);
    setFormMaxRuns(wf.max_concurrent_runs);
    try {
      setFormGraph(JSON.parse(wf.workflow_graph_json));
    } catch {
      setFormGraph({ nodes: [], edges: [] });
    }
    setSelectedWorkflow(wf);
    setError(null);
    setViewMode("edit");
  };

  const openRuns = (wf: Workflow) => {
    setSelectedWorkflow(wf);
    loadRuns(wf.id);
    setViewMode("runs");
  };

  /* ─── Render: Stats Cards ───────────────────────────────────────────── */

  const renderStats = () => {
    if (!stats) return null;
    const cards = [
      { label: "Workflows gesamt", value: stats.total_workflows, icon: <Zap size={20} />, color: "text-blue-600 bg-blue-50" },
      { label: "Aktive Workflows", value: stats.active_workflows, icon: <Play size={20} />, color: "text-green-600 bg-green-50" },
      { label: "Laufende Runs", value: stats.active_runs, icon: <RefreshCw size={20} />, color: "text-amber-600 bg-amber-50" },
      { label: "Abgeschlossen", value: stats.completed_runs, icon: <CheckCircle size={20} />, color: "text-indigo-600 bg-indigo-50" },
      { label: "Fehler", value: stats.error_runs, icon: <AlertCircle size={20} />, color: "text-red-600 bg-red-50" },
    ];
    return (
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        {cards.map((c) => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${c.color}`}>{c.icon}</div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{c.value}</p>
                <p className="text-xs text-gray-500">{c.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  /* ─── Render: Workflow List ─────────────────────────────────────────── */

  const renderList = () => (
    <div className="space-y-6">
      {renderStats()}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-100 rounded-lg"><Zap size={24} className="text-amber-600" /></div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Automations</h1>
            <p className="text-sm text-gray-500">Automatisierte Workflows für Kontakt-Aktionen</p>
          </div>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          Neuer Workflow
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm"
          placeholder="Workflows durchsuchen..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="animate-spin text-gray-400" size={24} />
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Zap size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-700 mb-2">Keine Workflows vorhanden</h3>
          <p className="text-sm text-gray-500 mb-4">Erstellen Sie Ihren ersten Automation-Workflow.</p>
          <button onClick={openCreate} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={14} className="inline mr-1" /> Workflow erstellen
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Trigger</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Aktive Runs</th>
                <th className="px-4 py-3">Re-Entry</th>
                <th className="px-4 py-3">Aktualisiert</th>
                <th className="px-4 py-3 text-right">Aktionen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {workflows.map((wf) => (
                <tr key={wf.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-gray-900">{wf.name}</p>
                      {wf.description && <p className="text-xs text-gray-500 mt-0.5">{wf.description}</p>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700">
                      {TRIGGER_LABELS[wf.trigger_type] || wf.trigger_type}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${wf.is_active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {wf.is_active ? <><Play size={10} /> Aktiv</> : <><Pause size={10} /> Inaktiv</>}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{wf.active_runs}</td>
                  <td className="px-4 py-3 text-gray-600 capitalize">{wf.re_entry_policy}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {wf.updated_at ? new Date(wf.updated_at).toLocaleDateString("de-DE") : "–"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button onClick={() => openRuns(wf)} className="p-1.5 hover:bg-gray-100 rounded" title="Runs anzeigen">
                        <BarChart3 size={14} className="text-gray-500" />
                      </button>
                      <button onClick={() => openEdit(wf)} className="p-1.5 hover:bg-gray-100 rounded" title="Bearbeiten">
                        <Pencil size={14} className="text-gray-500" />
                      </button>
                      <button onClick={() => handleToggleActive(wf)} className="p-1.5 hover:bg-gray-100 rounded" title={wf.is_active ? "Deaktivieren" : "Aktivieren"}>
                        {wf.is_active ? <Pause size={14} className="text-amber-500" /> : <Play size={14} className="text-green-500" />}
                      </button>
                      <button onClick={() => handleDelete(wf)} className="p-1.5 hover:bg-red-50 rounded" title="Löschen">
                        <Trash2 size={14} className="text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  /* ─── Render: Create / Edit Form ────────────────────────────────────── */

  const renderForm = () => {
    const isEdit = viewMode === "edit";
    return (
      <div className="space-y-6">
        {/* Back Button */}
        <button onClick={() => setViewMode("list")} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
          <ChevronLeft size={16} /> Zurück zur Übersicht
        </button>

        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">
            {isEdit ? "Workflow bearbeiten" : "Neuer Workflow"}
          </h1>
          <button
            onClick={isEdit ? handleUpdate : handleCreate}
            disabled={saving || !formName}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm font-medium"
          >
            <Save size={16} />
            {saving ? "Speichern..." : "Speichern"}
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {/* Settings */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <h2 className="font-semibold text-gray-900">Grundeinstellungen</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Name *</label>
              <input
                type="text"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="z.B. Churn-Prevention Workflow"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Trigger-Typ</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={formTriggerType}
                onChange={(e) => setFormTriggerType(e.target.value)}
              >
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs font-medium text-gray-600 mb-1">Beschreibung</label>
              <textarea
                className="w-full border rounded-lg px-3 py-2 text-sm h-20"
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Optionale Beschreibung des Workflows..."
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Re-Entry Policy</label>
              <select
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={formReEntryPolicy}
                onChange={(e) => setFormReEntryPolicy(e.target.value)}
              >
                <option value="skip">Überspringen (Kontakt bereits im Workflow)</option>
                <option value="restart">Neustart (bestehender Run wird abgebrochen)</option>
                <option value="parallel">Parallel (mehrere Runs erlaubt)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Trigger-Konfiguration (JSON)</label>
              <input
                type="text"
                className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
                value={formTriggerConfig}
                onChange={(e) => setFormTriggerConfig(e.target.value)}
                placeholder='{"segment_id": 123}'
              />
            </div>
          </div>
        </div>

        {/* Workflow Builder */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="font-semibold text-gray-900">Workflow-Graph</h2>
            <p className="text-xs text-gray-500 mt-1">Ziehen Sie Knoten aus der Palette und verbinden Sie diese per Drag & Drop.</p>
          </div>
          <div style={{ height: 600 }}>
            <WorkflowBuilder
              initialGraph={formGraph}
              onChange={setFormGraph}
              readOnly={false}
            />
          </div>
        </div>
      </div>
    );
  };

  /* ─── Render: Runs View ─────────────────────────────────────────────── */

  const renderRuns = () => (
    <div className="space-y-6">
      <button onClick={() => setViewMode("list")} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ChevronLeft size={16} /> Zurück zur Übersicht
      </button>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Runs: {selectedWorkflow?.name}</h1>
          <p className="text-sm text-gray-500 mt-1">Alle Durchläufe dieses Workflows</p>
        </div>
        <button
          onClick={() => selectedWorkflow && loadRuns(selectedWorkflow.id)}
          className="flex items-center gap-2 px-3 py-1.5 border rounded-lg text-sm hover:bg-gray-50"
        >
          <RefreshCw size={14} /> Aktualisieren
        </button>
      </div>

      {runs.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Users size={48} className="mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-700">Keine Runs vorhanden</h3>
          <p className="text-sm text-gray-500">Dieser Workflow wurde noch nicht ausgelöst.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                <th className="px-4 py-3">Run-ID</th>
                <th className="px-4 py-3">Kontakt-ID</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Aktueller Knoten</th>
                <th className="px-4 py-3">Gestartet</th>
                <th className="px-4 py-3">Abgeschlossen</th>
                <th className="px-4 py-3">Fehler</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {runs.map((run) => {
                const sc = STATUS_CONFIG[run.status] || STATUS_CONFIG.error;
                return (
                  <tr key={run.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">#{run.id}</td>
                    <td className="px-4 py-3">{run.contact_id}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${sc.color}`}>
                        {sc.icon} {sc.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{run.current_node_id || "–"}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {run.started_at ? new Date(run.started_at).toLocaleString("de-DE") : "–"}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {run.completed_at ? new Date(run.completed_at).toLocaleString("de-DE") : "–"}
                    </td>
                    <td className="px-4 py-3 text-xs text-red-500 max-w-[200px] truncate">{run.error_message || "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  /* ─── Main Render ───────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-[1400px] mx-auto">
      {viewMode === "list" && renderList()}
      {(viewMode === "create" || viewMode === "edit") && renderForm()}
      {viewMode === "runs" && renderRuns()}
    </div>
  );
}
