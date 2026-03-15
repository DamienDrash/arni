"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Network,
  Plus,
  Play,
  Trash2,
  Save,
  ChevronUp,
  ChevronDown,
  Settings2,
  Wrench,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ChevronDown as Expand,
  AlertCircle,
  Pencil,
  ToggleLeft,
  ToggleRight,
  Copy,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { usePermissions } from "@/lib/permissions";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Step {
  id?: number;
  step_order: number;
  agent_slug: string;
  display_name: string;
  tools_json: string;
  prompt_override: string;
  model_override: string;
  is_optional: boolean;
  _expanded?: boolean;
}

interface Team {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  lead_agent_slug: string | null;
  execution_mode: string;
  input_schema_json: string | null;
  yaml_version: number;
  is_active: boolean;
  is_system: boolean;
  step_count?: number;
  steps?: Step[];
}

interface RunStep {
  name: string;
  status: string;
  duration_ms: number;
  error: string | null;
}

interface Run {
  id: number;
  team_slug: string;
  trigger_source: string;
  success: boolean;
  duration_ms: number | null;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
  steps?: RunStep[];
  output?: Record<string, unknown>;
}

interface AgentDefinition {
  id: number;
  slug: string;
  name: string;
  description: string | null;
}

interface ToolDefinition {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_builtin: boolean;
  is_active: boolean;
}

type SidebarSelection = { type: "team"; slug: string } | { type: "tools" } | null;

type PendingConfirm =
  | { type: "deactivate-team"; slug: string }
  | { type: "activate-team"; slug: string }
  | { type: "delete-tool"; slug: string }
  | null;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function statusBadge(isActive: boolean) {
  return isActive ? (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-green-900/40 px-2 py-0.5 text-xs text-green-400"
      aria-label="Aktiv"
    >
      <CheckCircle2 size={12} aria-hidden="true" /> Aktiv
    </span>
  ) : (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-gray-700/60 px-2 py-0.5 text-xs text-gray-400"
      aria-label="Inaktiv"
    >
      <XCircle size={12} aria-hidden="true" /> Inaktiv
    </span>
  );
}

function runStatusIcon(success: boolean) {
  return success ? (
    <CheckCircle2 size={14} className="text-green-400 shrink-0" aria-label="Erfolgreich" />
  ) : (
    <XCircle size={14} className="text-red-400 shrink-0" aria-label="Fehlgeschlagen" />
  );
}

function fmtMs(ms: number | null) {
  if (ms == null) return "—";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "medium" });
}

/** Parse a tools_json string once; returns [] on error. */
function parseToolsJson(toolsJson: string | undefined): string[] {
  if (!toolsJson) return [];
  try { return JSON.parse(toolsJson); } catch { return []; }
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AgentTeamsPage() {
  const { role, feature } = usePermissions();

  // Access guard: tenant_user has no access; feature must be enabled
  if (role === "tenant_user") {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm">
        Kein Zugriff. Agent Teams erfordern mindestens tenant_admin.
      </div>
    );
  }
  if (role && role !== "system_admin" && !feature("agent_teams")) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500 text-sm">
        <Network size={40} className="opacity-20" aria-hidden="true" />
        <p>Agent Teams sind in deinem aktuellen Plan nicht verfügbar.</p>
        <a href="/settings/billing" className="text-violet-400 hover:underline text-xs">Plan upgraden →</a>
      </div>
    );
  }

  const [teams, setTeams] = useState<Team[]>([]);
  const [selection, setSelection] = useState<SidebarSelection>(null);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  // Track original loaded team to detect unsaved changes
  const originalTeamRef = useRef<Team | null>(null);
  const [isDirty, setIsDirty] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tools, setTools] = useState<ToolDefinition[]>([]);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runPayload, setRunPayload] = useState("{}");
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [expandedRuns, setExpandedRuns] = useState<Set<number>>(new Set());
  const [newTeamSlug, setNewTeamSlug] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [showNewTeamForm, setShowNewTeamForm] = useState(false);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [newToolSlug, setNewToolSlug] = useState("");
  const [newToolName, setNewToolName] = useState("");
  const [newToolDesc, setNewToolDesc] = useState("");
  const [toolSaving, setToolSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Inline confirmation instead of window.confirm()
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm>(null);
  // Tool inline edit state
  const [editingTool, setEditingTool] = useState<ToolDefinition | null>(null);
  const [editToolName, setEditToolName] = useState("");
  const [editToolDesc, setEditToolDesc] = useState("");
  // Clone modal state
  const [showCloneModal, setShowCloneModal] = useState(false);
  const [cloneSlug, setCloneSlug] = useState("");
  const [cloneName, setCloneName] = useState("");
  const [cloning, setCloning] = useState(false);
  // Tool usage map: slug → count of team steps referencing it
  const [toolUsage, setToolUsage] = useState<Record<string, number>>({});

  const handleApiError = useCallback(async (res: Response): Promise<string> => {
    if (res.status === 402) return "Feature nicht im aktuellen Plan verfügbar. Bitte upgraden.";
    if (res.status === 403) return "Zugriff verweigert.";
    if (res.status === 401) { window.location.href = "/login"; return ""; }
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    try { return JSON.parse(text)?.detail ?? text; } catch { return text; }
  }, []);

  const loadTeams = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch("/v2/admin/agent-teams/?active_only=false");
      if (!res.ok) { setError(await handleApiError(res)); return; }
      setTeams(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [handleApiError]);

  const loadAgentDefs = useCallback(async () => {
    try {
      const res = await apiFetch("/v2/admin/agent-definitions/");
      if (res.ok) setAgents(await res.json());
    } catch { /* ignore */ }
  }, []);

  // Pre-load tools at mount so step checkboxes work before "Tools" tab is visited
  const loadTools = useCallback(async () => {
    try {
      const res = await apiFetch("/v2/admin/agent-tools/?active_only=false");
      if (res.ok) setTools(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadTeams();
    loadAgentDefs();
    loadTools();
  }, [loadTeams, loadAgentDefs, loadTools]);

  // Load team detail when selection changes
  useEffect(() => {
    if (!selection || selection.type !== "team") {
      setSelectedTeam(null);
      originalTeamRef.current = null;
      setIsDirty(false);
      setRuns([]);
      return;
    }
    const slug = selection.slug;
    const loadDetail = async () => {
      try {
        const [detailRes, runsRes] = await Promise.all([
          apiFetch(`/v2/admin/agent-teams/${slug}/detail`),
          apiFetch(`/v2/admin/agent-teams/${slug}/runs?page_size=10`),
        ]);
        if (detailRes.ok) {
          const data: Team = await detailRes.json();
          if (data.steps) {
            data.steps = data.steps.map((s) => ({ ...s, _expanded: false }));
          }
          setSelectedTeam(data);
          originalTeamRef.current = JSON.parse(JSON.stringify(data));
          setIsDirty(false);
          setRunPayload("{}");
        }
        if (runsRes.ok) {
          const runsData = await runsRes.json();
          setRuns(runsData.items || []);
        }
      } catch { /* ignore */ }
    };
    loadDetail();
  }, [selection]);

  // Refresh tools list + usage summary when Tools section is selected
  useEffect(() => {
    if (!selection || selection.type !== "tools") return;
    setToolsLoading(true);
    Promise.all([
      apiFetch("/v2/admin/agent-tools/?active_only=false"),
      apiFetch("/v2/admin/agent-tools/usage-summary"),
    ])
      .then(async ([toolsRes, usageRes]) => {
        if (toolsRes.ok) setTools(await toolsRes.json());
        if (usageRes.ok) setToolUsage(await usageRes.json());
      })
      .finally(() => setToolsLoading(false));
  }, [selection]);

  // ── Dirty state tracking ──

  function markTeamChange(updated: Team) {
    setSelectedTeam(updated);
    setIsDirty(
      JSON.stringify(updated) !== JSON.stringify(originalTeamRef.current)
    );
  }

  // ── Team editing helpers ──

  function updateStep(idx: number, field: keyof Step, value: unknown) {
    if (!selectedTeam?.steps) return;
    const newSteps = [...selectedTeam.steps];
    newSteps[idx] = { ...newSteps[idx], [field]: value };
    markTeamChange({ ...selectedTeam, steps: newSteps });
  }

  function moveStep(idx: number, dir: -1 | 1) {
    if (!selectedTeam?.steps) return;
    const steps = [...selectedTeam.steps];
    const target = idx + dir;
    if (target < 0 || target >= steps.length) return;
    [steps[idx], steps[target]] = [steps[target], steps[idx]];
    const reordered = steps.map((s, i) => ({ ...s, step_order: i }));
    markTeamChange({ ...selectedTeam, steps: reordered });
  }

  function addStep() {
    if (!selectedTeam) return;
    const steps = selectedTeam.steps || [];
    const newStep: Step = {
      step_order: steps.length,
      agent_slug: agents[0]?.slug || "ops",
      display_name: "",
      tools_json: "[]",
      prompt_override: "",
      model_override: "",
      is_optional: false,
      _expanded: true,
    };
    markTeamChange({ ...selectedTeam, steps: [...steps, newStep] });
  }

  function removeStep(idx: number) {
    if (!selectedTeam?.steps) return;
    const newSteps = selectedTeam.steps
      .filter((_, i) => i !== idx)
      .map((s, i) => ({ ...s, step_order: i }));
    markTeamChange({ ...selectedTeam, steps: newSteps });
  }

  async function cloneTeam() {
    if (!selectedTeam) return;
    setCloning(true);
    setError(null);
    try {
      const res = await apiFetch(`/v2/admin/agent-teams/${selectedTeam.slug}/clone`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_slug: cloneSlug, new_name: cloneName }),
      });
      if (!res.ok) { setError(await handleApiError(res)); return; }
      const newTeam: Team = await res.json();
      setShowCloneModal(false);
      setCloneSlug("");
      setCloneName("");
      await loadTeams();
      setSelection({ type: "team", slug: newTeam.slug });
    } catch (e) {
      setError(String(e));
    } finally {
      setCloning(false);
    }
  }

  async function saveTeam() {
    if (!selectedTeam) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        name: selectedTeam.name,
        description: selectedTeam.description,
        lead_agent_slug: selectedTeam.lead_agent_slug,
        execution_mode: selectedTeam.execution_mode,
        input_schema_json: selectedTeam.input_schema_json,
        is_active: selectedTeam.is_active,
        steps: (selectedTeam.steps || []).map((s) => ({
          step_order: s.step_order,
          agent_slug: s.agent_slug,
          display_name: s.display_name || null,
          tools_json: s.tools_json || "[]",
          prompt_override: s.prompt_override || null,
          model_override: s.model_override || null,
          is_optional: s.is_optional,
        })),
      };
      const res = await apiFetch(`/v2/admin/agent-teams/${selectedTeam.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) { setError(await handleApiError(res)); return; }
      const updated: Team = await res.json();
      const merged = { ...selectedTeam, yaml_version: updated.yaml_version, is_active: updated.is_active };
      setSelectedTeam(merged);
      originalTeamRef.current = JSON.parse(JSON.stringify(merged));
      setIsDirty(false);
      await loadTeams();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function runTeam() {
    if (!selectedTeam) return;
    // Validate payload JSON
    try { JSON.parse(runPayload); setPayloadError(null); } catch (e) {
      setPayloadError("Ungültiges JSON: " + String(e));
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const payload = JSON.parse(runPayload);
      const res = await apiFetch(`/v2/admin/agent-teams/${selectedTeam.slug}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      });
      if (!res.ok) { setError(await handleApiError(res)); return; }
      const runsRes = await apiFetch(`/v2/admin/agent-teams/${selectedTeam.slug}/runs?page_size=10`);
      if (runsRes.ok) {
        const runsData = await runsRes.json();
        setRuns(runsData.items || []);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  async function createTeam() {
    if (!newTeamSlug || !newTeamName) return;
    setSaving(true);
    setError(null);
    const slugToCreate = newTeamSlug;
    try {
      const res = await apiFetch("/v2/admin/agent-teams/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: slugToCreate, name: newTeamName, steps: [] }),
      });
      if (!res.ok) {
        setError(await handleApiError(res));
        return;
      }
      setNewTeamSlug("");
      setNewTeamName("");
      setShowNewTeamForm(false);
      await loadTeams();
      // Auto-navigate to the newly created team
      setSelection({ type: "team", slug: slugToCreate });
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function confirmDeactivateTeam(slug: string) {
    setPendingConfirm(null);
    const res = await apiFetch(`/v2/admin/agent-teams/${slug}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      if (selection?.type === "team" && selection.slug === slug) setSelection(null);
      await loadTeams();
    }
  }

  async function confirmActivateTeam(slug: string) {
    setPendingConfirm(null);
    if (!selectedTeam) return;
    const res = await apiFetch(`/v2/admin/agent-teams/${slug}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: true }),
    });
    if (res.ok) {
      const updated: Team = await res.json();
      const merged = { ...selectedTeam, is_active: updated.is_active };
      setSelectedTeam(merged);
      originalTeamRef.current = JSON.parse(JSON.stringify(merged));
      setIsDirty(false);
      await loadTeams();
    }
  }

  async function createTool() {
    if (!newToolSlug || !newToolName) return;
    setToolSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/v2/admin/agent-tools/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slug: newToolSlug, name: newToolName, description: newToolDesc }),
      });
      if (!res.ok) {
        setError(await handleApiError(res));
        return;
      }
      setNewToolSlug("");
      setNewToolName("");
      setNewToolDesc("");
      const toolsRes = await apiFetch("/v2/admin/agent-tools/?active_only=false");
      if (toolsRes.ok) setTools(await toolsRes.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setToolSaving(false);
    }
  }

  async function saveTool() {
    if (!editingTool) return;
    setToolSaving(true);
    setError(null);
    try {
      const res = await apiFetch(`/v2/admin/agent-tools/${editingTool.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editToolName, description: editToolDesc }),
      });
      if (!res.ok) {
        setError(await handleApiError(res));
        return;
      }
      setEditingTool(null);
      const toolsRes = await apiFetch("/v2/admin/agent-tools/?active_only=false");
      if (toolsRes.ok) setTools(await toolsRes.json());
      await loadTools(); // Keep step checkboxes in sync
    } catch (e) {
      setError(String(e));
    } finally {
      setToolSaving(false);
    }
  }

  async function confirmDeleteTool(slug: string) {
    setPendingConfirm(null);
    setError(null);
    const res = await apiFetch(`/v2/admin/agent-tools/${slug}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      setError(await handleApiError(res));
      return;
    }
    const toolsRes = await apiFetch("/v2/admin/agent-tools/?active_only=false");
    if (toolsRes.ok) setTools(await toolsRes.json());
  }

  async function toggleRunExpand(runId: number) {
    if (expandedRuns.has(runId)) {
      setExpandedRuns((prev) => { const s = new Set(prev); s.delete(runId); return s; });
      return;
    }
    try {
      const res = await apiFetch(`/v2/admin/agent-runs/${runId}`);
      if (res.ok) {
        const detail: Run = await res.json();
        setRuns((prev) => prev.map((r) => (r.id === runId ? { ...r, ...detail } : r)));
      }
    } catch { /* ignore */ }
    setExpandedRuns((prev) => new Set(prev).add(runId));
  }

  // ─── Inline Confirm Dialog ─────────────────────────────────────────────────

  function ConfirmBar() {
    if (!pendingConfirm) return null;
    const isDeactivate = pendingConfirm.type === "deactivate-team";
    const isActivate = pendingConfirm.type === "activate-team";
    const isDeleteTool = pendingConfirm.type === "delete-tool";
    const label = isDeactivate
      ? `Team "${pendingConfirm.slug}" deaktivieren?`
      : isActivate
      ? `Team "${pendingConfirm.slug}" reaktivieren?`
      : `Tool "${pendingConfirm.slug}" löschen?`;
    const confirmLabel = isDeactivate ? "Deaktivieren" : isActivate ? "Reaktivieren" : "Löschen";
    const confirmClass = isDeleteTool || isDeactivate
      ? "bg-red-700 hover:bg-red-600"
      : "bg-green-700 hover:bg-green-600";

    const onConfirm = isDeactivate
      ? () => confirmDeactivateTeam(pendingConfirm.slug)
      : isActivate
      ? () => confirmActivateTeam(pendingConfirm.slug)
      : () => confirmDeleteTool(pendingConfirm.slug);

    return (
      <div
        role="alertdialog"
        aria-label={label}
        className="sticky top-0 z-20 mx-4 mt-4 flex items-center gap-3 rounded bg-yellow-900/40 border border-yellow-700/50 px-4 py-2.5 text-sm text-yellow-200"
      >
        <AlertCircle size={14} aria-hidden="true" />
        <span className="flex-1">{label}</span>
        <button
          onClick={onConfirm}
          className={`${confirmClass} text-white rounded px-3 py-1 text-xs font-medium`}
        >
          {confirmLabel}
        </button>
        <button
          onClick={() => setPendingConfirm(null)}
          className="text-yellow-400 hover:text-white text-xs px-2"
        >
          Abbrechen
        </button>
      </div>
    );
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="flex h-screen bg-[#0f1117] text-gray-100 overflow-hidden">
      {/* LEFT SIDEBAR */}
      <aside className="w-60 shrink-0 border-r border-white/10 flex flex-col bg-[#13161e]" aria-label="Teams Sidebar">
        <div className="px-4 py-4 border-b border-white/10 flex items-center gap-2">
          <Network size={18} className="text-violet-400" aria-hidden="true" />
          <span className="font-semibold text-sm">Agent Teams</span>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {loading && (
            <div className="flex items-center gap-2 px-4 py-3 text-xs text-gray-500" aria-live="polite">
              <Loader2 size={12} className="animate-spin" aria-hidden="true" /> Lade…
            </div>
          )}

          {!loading && teams.length === 0 && (
            <p className="px-4 py-4 text-xs text-gray-600 text-center">
              Noch keine Teams. Klicke unten auf &quot;Neues Team&quot;.
            </p>
          )}

          {teams.map((team) => (
            <button
              key={team.slug}
              onClick={() => setSelection({ type: "team", slug: team.slug })}
              className={`w-full text-left px-4 py-2.5 hover:bg-white/5 transition-colors ${
                selection?.type === "team" && selection.slug === team.slug
                  ? "bg-violet-900/30 border-r-2 border-violet-500"
                  : ""
              }`}
              aria-current={selection?.type === "team" && selection.slug === team.slug ? "page" : undefined}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm truncate font-medium">{team.name}</span>
                {!team.is_active && (
                  <span className="text-xs text-gray-600 ml-1">off</span>
                )}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {team.step_count ?? 0} Steps · {team.execution_mode}
              </div>
            </button>
          ))}
        </div>

        {/* New Team */}
        <div className="border-t border-white/10 p-3">
          {showNewTeamForm ? (
            <div className="space-y-2">
              <input
                className="w-full rounded bg-white/5 border border-white/10 px-2 py-1 text-xs focus:outline-none focus:border-violet-500"
                placeholder="slug (z.B. my-team)"
                value={newTeamSlug}
                onChange={(e) => setNewTeamSlug(e.target.value.replace(/\s/g, "-").toLowerCase())}
                aria-label="Team Slug"
              />
              <input
                className="w-full rounded bg-white/5 border border-white/10 px-2 py-1 text-xs focus:outline-none focus:border-violet-500"
                placeholder="Name"
                value={newTeamName}
                onChange={(e) => setNewTeamName(e.target.value)}
                aria-label="Team Name"
              />
              <div className="flex gap-1">
                <button
                  onClick={createTeam}
                  disabled={saving || !newTeamSlug || !newTeamName}
                  className="flex-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded px-2 py-1 text-xs font-medium"
                >
                  {saving ? "…" : "Erstellen"}
                </button>
                <button
                  onClick={() => setShowNewTeamForm(false)}
                  className="px-2 py-1 text-xs text-gray-400 hover:text-white"
                  aria-label="Abbrechen"
                >
                  ✕
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowNewTeamForm(true)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-white/5 text-xs text-gray-400 hover:text-white"
            >
              <Plus size={14} aria-hidden="true" /> Neues Team
            </button>
          )}
        </div>

        {/* Tools link */}
        <button
          onClick={() => setSelection({ type: "tools" })}
          className={`border-t border-white/10 flex items-center gap-2 px-4 py-3 text-xs hover:bg-white/5 transition-colors ${
            selection?.type === "tools" ? "text-violet-400 bg-violet-900/20" : "text-gray-500"
          }`}
          aria-current={selection?.type === "tools" ? "page" : undefined}
        >
          <Wrench size={14} aria-hidden="true" />
          Tools &amp; Skills
        </button>
      </aside>

      {/* MAIN AREA */}
      <main className="flex-1 overflow-y-auto" role="main">
        {/* Sticky error banner */}
        {error && (
          <div
            role="alert"
            aria-live="assertive"
            className="sticky top-0 z-10 mx-4 mt-4 flex items-center gap-2 rounded bg-red-900/30 border border-red-800/50 px-4 py-2 text-sm text-red-300"
          >
            <AlertCircle size={14} aria-hidden="true" /> {error}
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-white" aria-label="Fehler schließen">✕</button>
          </div>
        )}

        {/* Inline confirm bar */}
        <ConfirmBar />

        {/* Nothing selected */}
        {!selection && (
          <div className="flex flex-col items-center justify-center h-full text-gray-600">
            <Network size={48} className="mb-4 opacity-30" aria-hidden="true" />
            <p className="text-sm">Wähle ein Team aus der Sidebar</p>
          </div>
        )}

        {/* TEAM EDITOR */}
        {selection?.type === "team" && selectedTeam && (
          <div className="p-6 max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-3">
                  <input
                    className="bg-transparent text-xl font-semibold focus:outline-none border-b border-transparent hover:border-white/20 focus:border-violet-500 w-full"
                    value={selectedTeam.name}
                    onChange={(e) => markTeamChange({ ...selectedTeam, name: e.target.value })}
                    aria-label="Team Name"
                  />
                  {statusBadge(selectedTeam.is_active)}
                  {selectedTeam.is_system && (
                    <span className="text-xs text-violet-400 bg-violet-900/30 px-2 py-0.5 rounded-full">System</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>slug: <code className="text-violet-300">{selectedTeam.slug}</code></span>
                  <span>·</span>
                  <span>YAML v{selectedTeam.yaml_version}</span>
                  <span>·</span>
                  <select
                    className="bg-transparent border border-white/10 rounded px-1 py-0.5 text-gray-400 focus:outline-none"
                    value={selectedTeam.execution_mode}
                    onChange={(e) => markTeamChange({ ...selectedTeam, execution_mode: e.target.value })}
                    aria-label="Execution Mode"
                  >
                    <option value="pipeline">pipeline</option>
                    <option value="orchestrator">orchestrator</option>
                  </select>
                </div>
                <input
                  className="w-full bg-transparent text-sm text-gray-400 focus:outline-none border-b border-transparent hover:border-white/20 focus:border-violet-500"
                  placeholder="Beschreibung…"
                  value={selectedTeam.description || ""}
                  onChange={(e) => markTeamChange({ ...selectedTeam, description: e.target.value })}
                  aria-label="Team Beschreibung"
                />
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {/* Clone */}
                <button
                  onClick={() => {
                    setCloneSlug(`${selectedTeam.slug}-copy`);
                    setCloneName(`${selectedTeam.name} (Kopie)`);
                    setShowCloneModal(true);
                  }}
                  className="p-2 rounded hover:bg-violet-900/30 text-gray-500 hover:text-violet-400 transition-colors"
                  aria-label="Team klonen"
                  title="Team klonen"
                >
                  <Copy size={18} />
                </button>
                {/* Enable/Disable toggle */}
                {selectedTeam.is_active ? (
                  <button
                    onClick={() => setPendingConfirm({ type: "deactivate-team", slug: selectedTeam.slug })}
                    className="p-2 rounded hover:bg-red-900/30 text-gray-500 hover:text-red-400 transition-colors"
                    aria-label="Team deaktivieren"
                    title="Team deaktivieren"
                  >
                    <ToggleRight size={18} />
                  </button>
                ) : (
                  <button
                    onClick={() => setPendingConfirm({ type: "activate-team", slug: selectedTeam.slug })}
                    className="p-2 rounded hover:bg-green-900/30 text-gray-500 hover:text-green-400 transition-colors"
                    aria-label="Team reaktivieren"
                    title="Team reaktivieren"
                  >
                    <ToggleLeft size={18} />
                  </button>
                )}
                {/* Save button with dirty indicator */}
                <button
                  onClick={saveTeam}
                  disabled={saving}
                  className={`flex items-center gap-2 disabled:opacity-50 rounded px-3 py-1.5 text-sm font-medium transition-colors ${
                    isDirty
                      ? "bg-amber-600 hover:bg-amber-500"
                      : "bg-violet-600 hover:bg-violet-500"
                  }`}
                  aria-label={isDirty ? "Ungespeicherte Änderungen — Speichern" : "Speichern"}
                  title={isDirty ? "Ungespeicherte Änderungen" : "Gespeichert"}
                >
                  {saving ? (
                    <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                  ) : isDirty ? (
                    <AlertCircle size={14} aria-hidden="true" />
                  ) : (
                    <Save size={14} aria-hidden="true" />
                  )}
                  {isDirty ? "Speichern*" : "Speichern"}
                </button>
              </div>
            </div>

            {/* Lead Agent */}
            <div className="flex items-center gap-3">
              <label htmlFor="lead-agent-select" className="text-xs text-gray-500 w-28 shrink-0">Lead Agent</label>
              {agents.length > 0 ? (
                <select
                  id="lead-agent-select"
                  className="bg-white/5 border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500"
                  value={selectedTeam.lead_agent_slug || ""}
                  onChange={(e) => markTeamChange({ ...selectedTeam, lead_agent_slug: e.target.value || null })}
                >
                  <option value="">— keiner —</option>
                  {agents.map((a) => (
                    <option key={a.slug} value={a.slug}>{a.name} ({a.slug})</option>
                  ))}
                </select>
              ) : (
                <input
                  id="lead-agent-select"
                  className="bg-white/5 border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500"
                  placeholder="agent_slug"
                  value={selectedTeam.lead_agent_slug || ""}
                  onChange={(e) => markTeamChange({ ...selectedTeam, lead_agent_slug: e.target.value || null })}
                  aria-label="Lead Agent Slug"
                />
              )}
            </div>

            {/* Pipeline Steps */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-300">Pipeline Steps</h2>
                <button
                  onClick={addStep}
                  className="flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300"
                  aria-label="Schritt hinzufügen"
                >
                  <Plus size={13} aria-hidden="true" /> Schritt hinzufügen
                </button>
              </div>

              <div className="space-y-2">
                {(selectedTeam.steps || []).map((step, idx) => {
                  // Parse once per step per render — no O(n×m) in inner loops
                  const selectedTools = parseToolsJson(step.tools_json);
                  return (
                    <div key={idx} className="rounded-lg border border-white/10 bg-white/[0.03] overflow-hidden">
                      {/* Step header row */}
                      <div className="flex items-center gap-3 px-3 py-2.5">
                        <span className="text-xs text-gray-600 w-5 text-center font-mono" aria-label={`Schritt ${idx + 1}`}>{idx + 1}</span>

                        {/* Agent selector */}
                        {agents.length > 0 ? (
                          <select
                            className="bg-transparent border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500 flex-1"
                            value={step.agent_slug}
                            onChange={(e) => updateStep(idx, "agent_slug", e.target.value)}
                            aria-label={`Agent für Schritt ${idx + 1}`}
                          >
                            {agents.map((a) => (
                              <option key={a.slug} value={a.slug}>{a.name}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            className="bg-transparent border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500 flex-1"
                            value={step.agent_slug}
                            onChange={(e) => updateStep(idx, "agent_slug", e.target.value)}
                            placeholder="agent_slug"
                            aria-label={`Agent Slug für Schritt ${idx + 1}`}
                          />
                        )}

                        {/* Display name */}
                        <input
                          className="bg-transparent border border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:border-violet-500 w-36"
                          value={step.display_name || ""}
                          onChange={(e) => updateStep(idx, "display_name", e.target.value)}
                          placeholder="Label (optional)"
                          aria-label={`Anzeigename für Schritt ${idx + 1}`}
                        />

                        {/* Tools chips — use pre-parsed selectedTools */}
                        <div className="flex items-center gap-1 flex-wrap" aria-label="Zugewiesene Tools">
                          {tools
                            .filter((t) => selectedTools.includes(t.slug))
                            .map((t) => (
                              <span key={t.slug} className="text-xs bg-violet-900/30 text-violet-300 px-1.5 py-0.5 rounded">
                                {t.slug}
                              </span>
                            ))}
                        </div>

                        {/* Controls */}
                        <div className="flex items-center gap-1 ml-auto shrink-0">
                          <button
                            onClick={() => moveStep(idx, -1)}
                            disabled={idx === 0}
                            className="p-1 text-gray-600 hover:text-white disabled:opacity-30"
                            aria-label={`Schritt ${idx + 1} nach oben verschieben`}
                          >
                            <ChevronUp size={13} aria-hidden="true" />
                          </button>
                          <button
                            onClick={() => moveStep(idx, 1)}
                            disabled={idx === (selectedTeam.steps?.length ?? 1) - 1}
                            className="p-1 text-gray-600 hover:text-white disabled:opacity-30"
                            aria-label={`Schritt ${idx + 1} nach unten verschieben`}
                          >
                            <ChevronDown size={13} aria-hidden="true" />
                          </button>
                          <button
                            onClick={() => updateStep(idx, "_expanded", !step._expanded)}
                            className="p-1 text-gray-500 hover:text-white"
                            aria-label={step._expanded ? `Schritt ${idx + 1} einklappen` : `Schritt ${idx + 1} erweitern`}
                            aria-expanded={step._expanded}
                          >
                            <Settings2 size={13} aria-hidden="true" />
                          </button>
                          <button
                            onClick={() => removeStep(idx)}
                            className="p-1 text-gray-600 hover:text-red-400"
                            aria-label={`Schritt ${idx + 1} entfernen`}
                          >
                            <Trash2 size={13} aria-hidden="true" />
                          </button>
                        </div>
                      </div>

                      {/* Expanded overrides */}
                      {step._expanded && (
                        <div className="px-4 pb-3 pt-1 border-t border-white/5 space-y-2 bg-black/20">
                          {/* Tools checkboxes — selectedTools already parsed above */}
                          <fieldset>
                            <legend className="text-xs text-gray-500 mb-1">Tools</legend>
                            <div className="flex flex-wrap gap-2">
                              {tools.map((t) => {
                                const checked = selectedTools.includes(t.slug);
                                return (
                                  <label key={t.slug} className="flex items-center gap-1 text-xs cursor-pointer">
                                    <input
                                      type="checkbox"
                                      checked={checked}
                                      onChange={(e) => {
                                        const next = e.target.checked
                                          ? [...selectedTools, t.slug]
                                          : selectedTools.filter((s) => s !== t.slug);
                                        updateStep(idx, "tools_json", JSON.stringify(next));
                                      }}
                                      className="accent-violet-500"
                                    />
                                    {t.name}
                                  </label>
                                );
                              })}
                            </div>
                          </fieldset>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-xs text-gray-500 mb-1 block" htmlFor={`model-override-${idx}`}>Model Override</label>
                              <input
                                id={`model-override-${idx}`}
                                className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:border-violet-500"
                                value={step.model_override || ""}
                                onChange={(e) => updateStep(idx, "model_override", e.target.value)}
                                placeholder="gpt-4o (leer = Standard)"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-gray-500 flex items-center gap-2 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={step.is_optional}
                                  onChange={(e) => updateStep(idx, "is_optional", e.target.checked)}
                                  className="accent-violet-500"
                                />
                                Optional (Fehler bricht Pipeline nicht ab)
                              </label>
                            </div>
                          </div>
                          <div>
                            <label className="text-xs text-gray-500 mb-1 block" htmlFor={`prompt-override-${idx}`}>Prompt Override</label>
                            <textarea
                              id={`prompt-override-${idx}`}
                              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:border-violet-500 resize-y min-h-16"
                              value={step.prompt_override || ""}
                              onChange={(e) => updateStep(idx, "prompt_override", e.target.value)}
                              placeholder="System-Prompt für diesen Schritt (leer = Agent-Standard)"
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {(selectedTeam.steps || []).length === 0 && (
                  <div className="text-center py-8 text-gray-600 text-sm border border-dashed border-white/10 rounded-lg">
                    Noch keine Schritte — klicke &quot;Schritt hinzufügen&quot;
                  </div>
                )}
              </div>
            </div>

            {/* Run Panel */}
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Play size={14} className="text-green-400" aria-hidden="true" /> Team ausführen
                </h2>
              </div>
              <div className="flex gap-3">
                <div className="flex-1 space-y-1">
                  <textarea
                    className={`w-full bg-white/5 border rounded px-2 py-1.5 text-xs font-mono focus:outline-none resize-y min-h-16 ${
                      payloadError ? "border-red-600 focus:border-red-500" : "border-white/10 focus:border-violet-500"
                    }`}
                    value={runPayload}
                    onChange={(e) => {
                      setRunPayload(e.target.value);
                      // Live JSON validation
                      try { JSON.parse(e.target.value); setPayloadError(null); }
                      catch { setPayloadError("Ungültiges JSON"); }
                    }}
                    placeholder='{"key": "value"}'
                    aria-label="Run Payload (JSON)"
                    aria-invalid={!!payloadError}
                    aria-describedby={payloadError ? "payload-error" : undefined}
                  />
                  {payloadError && (
                    <p id="payload-error" className="text-xs text-red-400" role="alert">{payloadError}</p>
                  )}
                </div>
                <button
                  onClick={runTeam}
                  disabled={running || !!payloadError}
                  className="flex items-center gap-2 self-start bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded px-3 py-1.5 text-sm font-medium transition-colors"
                  aria-label="Team ausführen"
                >
                  {running ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
                  Starten
                </button>
              </div>
            </div>

            {/* Run History */}
            <div>
              <h2 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                <Clock size={14} aria-hidden="true" /> Letzte Runs
              </h2>
              <div className="space-y-1.5">
                {runs.length === 0 && (
                  <p className="text-xs text-gray-600 text-center py-4">Noch keine Runs für dieses Team</p>
                )}
                {runs.map((run) => (
                  <div key={run.id} className="rounded-lg border border-white/10 bg-white/[0.03] overflow-hidden">
                    <button
                      className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-white/5"
                      onClick={() => toggleRunExpand(run.id)}
                      aria-expanded={expandedRuns.has(run.id)}
                      aria-label={`Run #${run.id} ${run.success ? "erfolgreich" : "fehlgeschlagen"} – Details ${expandedRuns.has(run.id) ? "einklappen" : "anzeigen"}`}
                    >
                      {runStatusIcon(run.success)}
                      <span className="text-xs font-mono text-gray-400">#{run.id}</span>
                      <span className="text-xs text-gray-500">{fmtDate(run.started_at)}</span>
                      <span className="text-xs text-gray-600 ml-auto">{fmtMs(run.duration_ms)}</span>
                      <Expand size={12} className={`text-gray-600 transition-transform ${expandedRuns.has(run.id) ? "rotate-180" : ""}`} aria-hidden="true" />
                    </button>
                    {expandedRuns.has(run.id) && (
                      <div className="border-t border-white/5 px-4 py-3 bg-black/20 text-xs space-y-2">
                        {run.error_message && (
                          <p className="text-red-400" role="alert">{run.error_message}</p>
                        )}
                        {(run.steps || []).length > 0 && (
                          <div className="space-y-1" role="list" aria-label="Pipeline Schritte">
                            {(run.steps || []).map((s, i) => (
                              <div key={i} className="flex items-center gap-2" role="listitem">
                                {s.status === "completed" ? (
                                  <CheckCircle2 size={11} className="text-green-400" aria-label="Abgeschlossen" />
                                ) : s.status === "failed" ? (
                                  <XCircle size={11} className="text-red-400" aria-label="Fehlgeschlagen" />
                                ) : (
                                  <Clock size={11} className="text-gray-500" aria-label="Ausstehend" />
                                )}
                                <span className="text-gray-400">{s.name}</span>
                                <span className="text-gray-600 ml-auto">{fmtMs(s.duration_ms)}</span>
                                {s.error && <span className="text-red-400 ml-2 truncate max-w-xs" title={s.error}>{s.error}</span>}
                              </div>
                            ))}
                          </div>
                        )}
                        {run.output && Object.keys(run.output).length > 0 && (
                          <pre className="bg-black/30 rounded p-2 text-gray-400 overflow-x-auto text-[11px]" aria-label="Run Output">
                            {JSON.stringify(run.output, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TOOLS & SKILLS MANAGER */}
        {selection?.type === "tools" && (
          <div className="p-6 max-w-3xl mx-auto space-y-6">
            <div className="flex items-center gap-2">
              <Wrench size={20} className="text-violet-400" aria-hidden="true" />
              <h1 className="text-lg font-semibold">Tools &amp; Skills</h1>
            </div>

            {toolsLoading ? (
              <div className="flex items-center gap-2 text-gray-500 text-sm" aria-live="polite">
                <Loader2 size={14} className="animate-spin" aria-hidden="true" /> Lade…
              </div>
            ) : (
              <div className="rounded-lg border border-white/10 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/10 bg-white/[0.03]">
                      <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">Slug</th>
                      <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">Name</th>
                      <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">Beschreibung</th>
                      <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">Typ</th>
                      <th className="text-left px-4 py-2.5 text-xs text-gray-500 font-medium">Teams</th>
                      <th className="px-4 py-2.5 text-xs text-gray-500 font-medium text-right">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tools.map((tool) => (
                      <React.Fragment key={tool.slug}>
                        <tr className="border-b border-white/5 hover:bg-white/[0.03]">
                          <td className="px-4 py-2.5 font-mono text-xs text-violet-300">{tool.slug}</td>
                          <td className="px-4 py-2.5 text-gray-200">{tool.name}</td>
                          <td className="px-4 py-2.5 text-gray-500 text-xs max-w-xs truncate" title={tool.description || undefined}>
                            {tool.description || "—"}
                          </td>
                          <td className="px-4 py-2.5">
                            {tool.is_builtin ? (
                              <span className="text-xs text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded">builtin</span>
                            ) : (
                              <span className="text-xs text-gray-400 bg-white/5 px-1.5 py-0.5 rounded">custom</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            {(toolUsage[tool.slug] ?? 0) > 0 ? (
                              <span className="text-xs text-violet-300 bg-violet-900/30 px-1.5 py-0.5 rounded font-mono">
                                {toolUsage[tool.slug]}
                              </span>
                            ) : (
                              <span className="text-xs text-gray-600">—</span>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-1 justify-end">
                              {/* Edit available for custom tools */}
                              {!tool.is_builtin && (
                                <button
                                  onClick={() => {
                                    setEditingTool(tool);
                                    setEditToolName(tool.name);
                                    setEditToolDesc(tool.description || "");
                                  }}
                                  className="p-1 text-gray-600 hover:text-violet-400 transition-colors"
                                  aria-label={`Tool ${tool.slug} bearbeiten`}
                                  title="Bearbeiten"
                                >
                                  <Pencil size={13} aria-hidden="true" />
                                </button>
                              )}
                              {!tool.is_builtin && (
                                <button
                                  onClick={() => setPendingConfirm({ type: "delete-tool", slug: tool.slug })}
                                  className="p-1 text-gray-600 hover:text-red-400 transition-colors"
                                  aria-label={`Tool ${tool.slug} löschen`}
                                  title="Löschen"
                                >
                                  <Trash2 size={13} aria-hidden="true" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                        {/* Inline edit row */}
                        {editingTool?.slug === tool.slug && (
                          <tr className="border-b border-violet-800/40 bg-violet-900/10">
                            <td className="px-4 py-2.5 text-xs text-gray-500 font-mono">{tool.slug}</td>
                            <td className="px-4 py-2.5">
                              <input
                                className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500"
                                value={editToolName}
                                onChange={(e) => setEditToolName(e.target.value)}
                                aria-label="Tool Name bearbeiten"
                                autoFocus
                              />
                            </td>
                            <td className="px-4 py-2.5" colSpan={3}>
                              <input
                                className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm focus:outline-none focus:border-violet-500"
                                value={editToolDesc}
                                onChange={(e) => setEditToolDesc(e.target.value)}
                                placeholder="Beschreibung"
                                aria-label="Tool Beschreibung bearbeiten"
                              />
                            </td>
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-1 justify-end">
                                <button
                                  onClick={saveTool}
                                  disabled={toolSaving || !editToolName}
                                  className="flex items-center gap-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded px-2 py-1 text-xs font-medium"
                                  aria-label="Änderungen speichern"
                                >
                                  {toolSaving ? <Loader2 size={12} className="animate-spin" aria-hidden="true" /> : <Save size={12} aria-hidden="true" />}
                                  Speichern
                                </button>
                                <button
                                  onClick={() => setEditingTool(null)}
                                  className="px-2 py-1 text-xs text-gray-400 hover:text-white"
                                  aria-label="Bearbeiten abbrechen"
                                >
                                  ✕
                                </button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {tools.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-6 text-center text-xs text-gray-600">
                          Keine Tools gefunden.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Create new tool */}
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Neues Tool erstellen</h3>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <input
                  className="bg-white/5 border border-white/10 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-violet-500"
                  placeholder="slug"
                  value={newToolSlug}
                  onChange={(e) => setNewToolSlug(e.target.value.toLowerCase().replace(/\s/g, "-"))}
                  aria-label="Neuer Tool Slug"
                />
                <input
                  className="bg-white/5 border border-white/10 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-violet-500"
                  placeholder="Name"
                  value={newToolName}
                  onChange={(e) => setNewToolName(e.target.value)}
                  aria-label="Neuer Tool Name"
                />
                <input
                  className="bg-white/5 border border-white/10 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-violet-500"
                  placeholder="Beschreibung (optional)"
                  value={newToolDesc}
                  onChange={(e) => setNewToolDesc(e.target.value)}
                  aria-label="Neuer Tool Beschreibung"
                />
              </div>
              <button
                onClick={createTool}
                disabled={toolSaving || !newToolSlug || !newToolName}
                className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded px-3 py-1.5 text-sm font-medium"
              >
                {toolSaving ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
                Tool hinzufügen
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Clone Team Modal */}
      {showCloneModal && selectedTeam && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          role="dialog"
          aria-modal="true"
          aria-label="Team klonen"
          onClick={(e) => { if (e.target === e.currentTarget) setShowCloneModal(false); }}
        >
          <div className="bg-gray-900 border border-white/10 rounded-xl p-6 w-full max-w-md shadow-2xl space-y-4">
            <h2 className="text-base font-semibold">
              Team klonen — <span className="text-violet-300">{selectedTeam.slug}</span>
            </h2>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block" htmlFor="clone-slug">
                  Neuer Slug
                </label>
                <input
                  id="clone-slug"
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-violet-500 font-mono"
                  value={cloneSlug}
                  onChange={(e) => setCloneSlug(e.target.value.toLowerCase().replace(/\s/g, "-"))}
                  placeholder="my-team-copy"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block" htmlFor="clone-name">
                  Neuer Name
                </label>
                <input
                  id="clone-name"
                  className="w-full bg-white/5 border border-white/10 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-violet-500"
                  value={cloneName}
                  onChange={(e) => setCloneName(e.target.value)}
                  placeholder="My Team (Kopie)"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowCloneModal(false)}
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Abbrechen
              </button>
              <button
                onClick={cloneTeam}
                disabled={cloning || !cloneSlug || !cloneName}
                className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded px-4 py-1.5 text-sm font-medium transition-colors"
              >
                {cloning ? (
                  <Loader2 size={14} className="animate-spin" aria-hidden="true" />
                ) : (
                  <Copy size={14} aria-hidden="true" />
                )}
                Klonen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
