"use client";

import React, { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Zap, Plus, Play, Pause, Trash2, Pencil, BarChart3, RefreshCw,
  Search, ChevronLeft, Save, Users, AlertCircle, CheckCircle, Clock, XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";

const WorkflowBuilder = dynamic(
  () => import("@/components/automations/WorkflowBuilder"),
  { ssr: false, loading: () => (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 400 }}>
      <RefreshCw size={24} color={T.accent} style={{ animation: "spin 1s linear infinite" }} />
    </div>
  )}
);

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface Workflow {
  id: number; name: string; description: string | null; is_active: boolean;
  trigger_type: string; trigger_config_json: string | null; workflow_graph_json: string;
  max_concurrent_runs: number; re_entry_policy: string; active_runs: number;
  created_at: string | null; updated_at: string | null;
}

interface AutomationStats {
  total_workflows: number; active_workflows: number; active_runs: number;
  completed_runs: number; error_runs: number;
}

interface Run {
  id: number; workflow_id: number; contact_id: number; status: string;
  current_node_id: string | null; started_at: string | null;
  completed_at: string | null; error_message: string | null;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Constants & Styles
   ═══════════════════════════════════════════════════════════════════════ */

const TRIGGER_LABELS: Record<string, string> = {
  segment_entry: "Segment-Eintritt", segment_exit: "Segment-Austritt",
  contact_created: "Neuer Kontakt", tag_added: "Tag hinzugefügt",
  tag_removed: "Tag entfernt", lifecycle_change: "Lifecycle-Änderung", manual: "Manuell",
};

const STATUS_MAP: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  active:    { label: "Aktiv",         color: T.success,    bg: T.successDim,  icon: Play },
  waiting:   { label: "Wartend",       color: T.warning,    bg: T.warningDim,  icon: Clock },
  completed: { label: "Abgeschlossen", color: T.info,       bg: T.infoDim,     icon: CheckCircle },
  cancelled: { label: "Abgebrochen",   color: T.textMuted,  bg: T.surfaceAlt,  icon: XCircle },
  error:     { label: "Fehler",        color: T.danger,     bg: T.dangerDim,   icon: AlertCircle },
};

const S: Record<string, React.CSSProperties> = {
  page: { padding: "32px 40px", maxWidth: 1400, margin: "0 auto" },
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12, marginBottom: 24 },
  statCard: { background: T.surface, borderRadius: 14, padding: "16px 18px", border: `1px solid ${T.border}`, transition: "border-color .2s", cursor: "default" },
  statValue: { fontSize: 22, fontWeight: 800, color: T.text, lineHeight: 1.1 },
  statLabel: { fontSize: 11, color: T.textMuted, fontWeight: 600, marginTop: 2 },
  searchWrap: { position: "relative" as const, flex: 1, minWidth: 200 },
  searchIcon: { position: "absolute" as const, left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim },
  searchInput: { width: "100%", padding: "10px 12px 10px 36px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" },
  actionBtn: { display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", transition: "opacity .15s", whiteSpace: "nowrap" as const },
  actionBtnSecondary: { display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" as const },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: { padding: "12px 14px", textAlign: "left" as const, fontWeight: 700, fontSize: 11, color: T.textMuted, textTransform: "uppercase" as const, letterSpacing: "0.04em", borderBottom: `2px solid ${T.border}` },
  td: { padding: "12px 14px", borderBottom: `1px solid ${T.border}`, verticalAlign: "middle" as const },
  formLabel: { display: "block", fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 5, textTransform: "uppercase" as const, letterSpacing: "0.04em" },
  formInput: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" as const },
  formSelect: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" },
  iconBtn: { display: "flex", alignItems: "center", justifyContent: "center", width: 30, height: 30, borderRadius: 8, border: "none", background: "transparent", cursor: "pointer", transition: "background .15s" },
  backBtn: { display: "flex", alignItems: "center", gap: 4, fontSize: 13, color: T.textMuted, background: "none", border: "none", cursor: "pointer", padding: 0, marginBottom: 16 },
  emptyState: { textAlign: "center" as const, padding: 60 },
};

const fmtDate = (d: string | null) => {
  if (!d) return "–";
  try { return new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }); } catch { return "–"; }
};
const fmtDateTime = (d: string | null) => {
  if (!d) return "–";
  try { return new Date(d).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return "–"; }
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
      if (res.ok) { const data = await res.json(); setWorkflows(data.items || []); }
    } catch (e) { console.error("Failed to load workflows", e); }
    setLoading(false);
  }, [search]);

  const loadStats = useCallback(async () => {
    try {
      const res = await apiFetch("/v2/admin/automations/stats");
      if (res.ok) setStats(await res.json());
    } catch (e) { console.error("Failed to load stats", e); }
  }, []);

  const loadRuns = useCallback(async (workflowId: number) => {
    try {
      const res = await apiFetch(`/v2/admin/automations/${workflowId}/runs?limit=100`);
      if (res.ok) { const data = await res.json(); setRuns(data.items || []); }
    } catch (e) { console.error("Failed to load runs", e); }
  }, []);

  useEffect(() => { loadWorkflows(); loadStats(); }, [loadWorkflows, loadStats]);

  /* ─── Actions ───────────────────────────────────────────────────────── */

  const handleCreate = async () => {
    setSaving(true); setError(null);
    try {
      const res = await apiFetch("/v2/admin/automations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: formName, description: formDescription || null, trigger_type: formTriggerType, trigger_config_json: formTriggerConfig || null, workflow_graph_json: JSON.stringify(formGraph), max_concurrent_runs: formMaxRuns, re_entry_policy: formReEntryPolicy }),
      });
      if (res.ok) { setViewMode("list"); loadWorkflows(); loadStats(); }
      else { const data = await res.json(); setError(data.detail || "Fehler beim Erstellen"); }
    } catch (e: any) { setError(e.message); }
    setSaving(false);
  };

  const handleUpdate = async () => {
    if (!selectedWorkflow) return;
    setSaving(true); setError(null);
    try {
      const res = await apiFetch(`/v2/admin/automations/${selectedWorkflow.id}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: formName, description: formDescription || null, trigger_type: formTriggerType, trigger_config_json: formTriggerConfig || null, workflow_graph_json: JSON.stringify(formGraph), max_concurrent_runs: formMaxRuns, re_entry_policy: formReEntryPolicy }),
      });
      if (res.ok) { setViewMode("list"); loadWorkflows(); }
      else { const data = await res.json(); setError(data.detail || "Fehler beim Speichern"); }
    } catch (e: any) { setError(e.message); }
    setSaving(false);
  };

  const handleToggleActive = async (wf: Workflow) => {
    const action = wf.is_active ? "deactivate" : "activate";
    try {
      const res = await apiFetch(`/v2/admin/automations/${wf.id}/${action}`, { method: "POST" });
      if (res.ok) { loadWorkflows(); loadStats(); }
    } catch (e) { console.error("Toggle failed", e); }
  };

  const handleDelete = async (wf: Workflow) => {
    if (!confirm(`Workflow "${wf.name}" wirklich löschen?`)) return;
    try {
      const res = await apiFetch(`/v2/admin/automations/${wf.id}`, { method: "DELETE" });
      if (res.ok) { loadWorkflows(); loadStats(); }
    } catch (e) { console.error("Delete failed", e); }
  };

  const openCreate = () => {
    setFormName(""); setFormDescription(""); setFormTriggerType("segment_entry");
    setFormTriggerConfig("{}"); setFormReEntryPolicy("skip"); setFormMaxRuns(1000);
    setFormGraph({ nodes: [], edges: [] }); setSelectedWorkflow(null); setError(null);
    setViewMode("create");
  };

  const openEdit = (wf: Workflow) => {
    setFormName(wf.name); setFormDescription(wf.description || "");
    setFormTriggerType(wf.trigger_type); setFormTriggerConfig(wf.trigger_config_json || "{}");
    setFormReEntryPolicy(wf.re_entry_policy); setFormMaxRuns(wf.max_concurrent_runs);
    try { setFormGraph(JSON.parse(wf.workflow_graph_json)); } catch { setFormGraph({ nodes: [], edges: [] }); }
    setSelectedWorkflow(wf); setError(null); setViewMode("edit");
  };

  const openRuns = (wf: Workflow) => { setSelectedWorkflow(wf); loadRuns(wf.id); setViewMode("runs"); };

  /* ─── Render: Stats ────────────────────────────────────────────────── */

  const renderStats = () => {
    if (!stats) return null;
    const cards = [
      { label: "Workflows", value: stats.total_workflows, icon: Zap, color: T.accent, bg: T.accentDim },
      { label: "Aktiv", value: stats.active_workflows, icon: Play, color: T.success, bg: T.successDim },
      { label: "Laufende Runs", value: stats.active_runs, icon: RefreshCw, color: T.warning, bg: T.warningDim },
      { label: "Abgeschlossen", value: stats.completed_runs, icon: CheckCircle, color: T.info, bg: T.infoDim },
      { label: "Fehler", value: stats.error_runs, icon: AlertCircle, color: T.danger, bg: T.dangerDim },
    ];
    return (
      <div style={S.statsRow}>
        {cards.map((c) => (
          <div key={c.label} style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: c.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <c.icon size={18} style={{ color: c.color }} />
              </div>
              <div>
                <div style={S.statValue}>{c.value}</div>
                <div style={S.statLabel}>{c.label}</div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  /* ─── Render: List ─────────────────────────────────────────────────── */

  const renderList = () => (
    <>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Zap size={20} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
              Automations
            </h1>
            <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
              Automatisierte Workflows für Kontakt-Aktionen
            </p>
          </div>
        </div>
      </div>

      {renderStats()}

      {/* Toolbar */}
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 20 }}>
        <div style={S.searchWrap}>
          <Search size={14} style={S.searchIcon} />
          <input
            type="text"
            style={S.searchInput}
            placeholder="Workflows durchsuchen..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button style={S.actionBtn} onClick={openCreate}>
          <Plus size={14} /> Neuer Workflow
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
          <RefreshCw size={24} color={T.accent} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      ) : workflows.length === 0 ? (
        <Card style={{ padding: 0 }}>
          <div style={S.emptyState}>
            <Zap size={48} color={T.textDim} style={{ marginBottom: 16 }} />
            <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 6 }}>Keine Workflows vorhanden</div>
            <div style={{ fontSize: 13, color: T.textMuted, marginBottom: 16 }}>Erstellen Sie Ihren ersten Automation-Workflow.</div>
            <button style={S.actionBtn} onClick={openCreate}><Plus size={14} /> Workflow erstellen</button>
          </div>
        </Card>
      ) : (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Name</th>
                <th style={S.th}>Trigger</th>
                <th style={S.th}>Status</th>
                <th style={S.th}>Aktive Runs</th>
                <th style={S.th}>Re-Entry</th>
                <th style={S.th}>Aktualisiert</th>
                <th style={{ ...S.th, textAlign: "right" }}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {workflows.map((wf) => (
                <tr key={wf.id} style={{ transition: "background .15s" }} onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)} onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                  <td style={S.td}>
                    <div style={{ fontWeight: 600, color: T.text }}>{wf.name}</div>
                    {wf.description && <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{wf.description}</div>}
                  </td>
                  <td style={S.td}>
                    <Badge variant="default">{TRIGGER_LABELS[wf.trigger_type] || wf.trigger_type}</Badge>
                  </td>
                  <td style={S.td}>
                    <Badge variant={wf.is_active ? "success" : "default"}>
                      {wf.is_active ? <><Play size={10} /> Aktiv</> : <><Pause size={10} /> Inaktiv</>}
                    </Badge>
                  </td>
                  <td style={{ ...S.td, color: T.textMuted }}>{wf.active_runs}</td>
                  <td style={{ ...S.td, color: T.textMuted, textTransform: "capitalize" }}>{wf.re_entry_policy}</td>
                  <td style={{ ...S.td, color: T.textDim, fontSize: 12 }}>{fmtDate(wf.updated_at)}</td>
                  <td style={{ ...S.td, textAlign: "right" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 2 }}>
                      <button style={S.iconBtn} onClick={() => openRuns(wf)} title="Runs anzeigen"
                        onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                        <BarChart3 size={14} color={T.textMuted} />
                      </button>
                      <button style={S.iconBtn} onClick={() => openEdit(wf)} title="Bearbeiten"
                        onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                        <Pencil size={14} color={T.textMuted} />
                      </button>
                      <button style={S.iconBtn} onClick={() => handleToggleActive(wf)} title={wf.is_active ? "Deaktivieren" : "Aktivieren"}
                        onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                        {wf.is_active ? <Pause size={14} color={T.warning} /> : <Play size={14} color={T.success} />}
                      </button>
                      <button style={S.iconBtn} onClick={() => handleDelete(wf)} title="Löschen"
                        onMouseEnter={(e) => (e.currentTarget.style.background = T.dangerDim)}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                        <Trash2 size={14} color={T.danger} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );

  /* ─── Render: Create / Edit Form ────────────────────────────────────── */

  const renderForm = () => {
    const isEdit = viewMode === "edit";
    return (
      <>
        <button style={S.backBtn} onClick={() => setViewMode("list")}>
          <ChevronLeft size={16} /> Zurück zur Übersicht
        </button>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: T.text, margin: 0 }}>
            {isEdit ? "Workflow bearbeiten" : "Neuer Workflow"}
          </h1>
          <button
            style={{ ...S.actionBtn, opacity: saving || !formName ? 0.5 : 1 }}
            onClick={isEdit ? handleUpdate : handleCreate}
            disabled={saving || !formName}
          >
            <Save size={14} /> {saving ? "Speichern..." : "Speichern"}
          </button>
        </div>

        {error && (
          <div style={{ padding: 12, background: T.dangerDim, border: `1px solid ${T.danger}30`, borderRadius: 10, fontSize: 13, color: T.danger, display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {/* Settings */}
        <Card style={{ padding: 20, marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text, marginBottom: 16 }}>Grundeinstellungen</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <label style={S.formLabel}>Name *</label>
              <input style={S.formInput} type="text" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="z.B. Churn-Prevention Workflow" />
            </div>
            <div>
              <label style={S.formLabel}>Trigger-Typ</label>
              <select style={S.formSelect} value={formTriggerType} onChange={(e) => setFormTriggerType(e.target.value)}>
                {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label style={S.formLabel}>Beschreibung</label>
              <textarea style={{ ...S.formInput, height: 70, resize: "vertical" }} value={formDescription} onChange={(e) => setFormDescription(e.target.value)} placeholder="Optionale Beschreibung des Workflows..." />
            </div>
            <div>
              <label style={S.formLabel}>Re-Entry Policy</label>
              <select style={S.formSelect} value={formReEntryPolicy} onChange={(e) => setFormReEntryPolicy(e.target.value)}>
                <option value="skip">Überspringen (Kontakt bereits im Workflow)</option>
                <option value="restart">Neustart (bestehender Run wird abgebrochen)</option>
                <option value="parallel">Parallel (mehrere Runs erlaubt)</option>
              </select>
            </div>
            <div>
              <label style={S.formLabel}>Trigger-Konfiguration (JSON)</label>
              <input style={{ ...S.formInput, fontFamily: "monospace" }} type="text" value={formTriggerConfig} onChange={(e) => setFormTriggerConfig(e.target.value)} placeholder='{"segment_id": 123}' />
            </div>
          </div>
        </Card>

        {/* Workflow Builder */}
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Workflow-Graph</div>
            <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>Ziehen Sie Knoten aus der Palette und verbinden Sie diese per Drag & Drop.</div>
          </div>
          <div style={{ height: 600, background: T.bg }}>
            <WorkflowBuilder initialGraph={formGraph} onChange={setFormGraph} readOnly={false} />
          </div>
        </Card>
      </>
    );
  };

  /* ─── Render: Runs View ─────────────────────────────────────────────── */

  const renderRuns = () => (
    <>
      <button style={S.backBtn} onClick={() => setViewMode("list")}>
        <ChevronLeft size={16} /> Zurück zur Übersicht
      </button>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: T.text, margin: 0 }}>Runs: {selectedWorkflow?.name}</h1>
          <p style={{ fontSize: 13, color: T.textMuted, margin: "4px 0 0" }}>Alle Durchläufe dieses Workflows</p>
        </div>
        <button style={S.actionBtnSecondary} onClick={() => selectedWorkflow && loadRuns(selectedWorkflow.id)}>
          <RefreshCw size={14} /> Aktualisieren
        </button>
      </div>

      {runs.length === 0 ? (
        <Card style={{ padding: 0 }}>
          <div style={S.emptyState}>
            <Users size={48} color={T.textDim} style={{ marginBottom: 16 }} />
            <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 6 }}>Keine Runs vorhanden</div>
            <div style={{ fontSize: 13, color: T.textMuted }}>Dieser Workflow wurde noch nicht ausgelöst.</div>
          </div>
        </Card>
      ) : (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>Run-ID</th>
                <th style={S.th}>Kontakt-ID</th>
                <th style={S.th}>Status</th>
                <th style={S.th}>Aktueller Knoten</th>
                <th style={S.th}>Gestartet</th>
                <th style={S.th}>Abgeschlossen</th>
                <th style={S.th}>Fehler</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => {
                const sc = STATUS_MAP[run.status] || STATUS_MAP.error;
                const Icon = sc.icon;
                return (
                  <tr key={run.id} style={{ transition: "background .15s" }} onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)} onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}>
                    <td style={{ ...S.td, fontFamily: "monospace", fontSize: 12 }}>#{run.id}</td>
                    <td style={{ ...S.td, color: T.text }}>{run.contact_id}</td>
                    <td style={S.td}>
                      <Badge variant={run.status === "active" ? "success" : run.status === "error" ? "danger" : run.status === "waiting" ? "warning" : run.status === "completed" ? "info" : "default"}>
                        <Icon size={10} /> {sc.label}
                      </Badge>
                    </td>
                    <td style={{ ...S.td, fontFamily: "monospace", fontSize: 11, color: T.textDim }}>{run.current_node_id || "–"}</td>
                    <td style={{ ...S.td, fontSize: 12, color: T.textDim }}>{fmtDateTime(run.started_at)}</td>
                    <td style={{ ...S.td, fontSize: 12, color: T.textDim }}>{fmtDateTime(run.completed_at)}</td>
                    <td style={{ ...S.td, fontSize: 12, color: T.danger, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{run.error_message || "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </>
  );

  /* ─── Main Render ───────────────────────────────────────────────────── */

  return (
    <div style={S.page}>
      {viewMode === "list" && renderList()}
      {(viewMode === "create" || viewMode === "edit") && renderForm()}
      {viewMode === "runs" && renderRuns()}
    </div>
  );
}
