"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown, ChevronUp, Download, Edit3, Filter, Plus, Search, ShoppingBag,
  ShoppingCart, Trash2, Upload, Users, X, Database, Tag, Columns3, Save, Check,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";

/* ─── Types ───────────────────────────────────────────────────────────────── */

type CheckinStats = {
  total_30d?: number; total_90d?: number;
  avg_training_30d_per_week?: number; avg_training_90d_per_week?: number; avg_per_week?: number;
  last_visit?: string; status?: string; source?: string;
  churn_prediction?: { score?: number; risk?: "low" | "medium" | "high"; reasons?: string[] };
};

type PauseInfo = { is_currently_paused?: boolean; pause_until?: string | null; pause_reason?: string | null; paused_days_180?: number };
type ContractInfo = { plan_name: string; status: string; start_date?: string | null; end_date?: string | null };

type Member = {
  id?: number;
  customer_id: number;
  member_number?: string | null;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  phone_number?: string | null;
  email?: string | null;
  gender?: string | null;
  preferred_language?: string | null;
  member_since?: string | null;
  is_paused?: boolean | null;
  pause_info?: PauseInfo | null;
  contract_info?: ContractInfo | null;
  additional_info?: Record<string, string> | null;
  checkin_stats?: CheckinStats | null;
  source?: string;
  source_id?: string | null;
  tags?: string[];
  custom_fields?: Record<string, string>;
  notes?: string | null;
  verified?: boolean;
  chat_sessions?: number;
};

type CustomColumn = {
  id: number; name: string; slug: string;
  field_type: string; options?: string[] | null;
  position: number; is_visible: boolean;
};

/* ─── Source Config ────────────────────────────────────────────────────────── */

const SOURCE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  manual:      { label: "Manuell",      color: T.accent,    icon: "edit" },
  magicline:   { label: "Magicline",    color: "#00D68F",   icon: "database" },
  shopify:     { label: "Shopify",      color: "#96BF48",   icon: "shopping-bag" },
  woocommerce: { label: "WooCommerce",  color: "#9B5C8F",   icon: "shopping-cart" },
  hubspot:     { label: "HubSpot",      color: "#FF7A59",   icon: "users" },
  csv:         { label: "CSV Import",   color: T.info,      icon: "upload" },
  api:         { label: "API",          color: T.warning,    icon: "code" },
};

function SourceBadge({ source }: { source?: string }) {
  const cfg = SOURCE_CONFIG[source || "manual"] || SOURCE_CONFIG.manual;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
      background: `${cfg.color}18`, color: cfg.color, border: `1px solid ${cfg.color}30`,
    }}>
      {cfg.label}
    </span>
  );
}

/* ─── Inline Edit Cell ────────────────────────────────────────────────────── */

function EditableCell({
  value, onSave, type = "text", placeholder = "-",
}: {
  value: string; onSave: (v: string) => void; type?: string; placeholder?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);
  useEffect(() => { setDraft(value); }, [value]);

  if (!editing) {
    return (
      <span
        onClick={() => setEditing(true)}
        style={{ cursor: "pointer", fontSize: 12, color: value ? T.text : T.textDim, minWidth: 40, display: "inline-block" }}
        title="Klicken zum Bearbeiten"
      >
        {value || placeholder}
      </span>
    );
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <input
        ref={inputRef}
        type={type}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") { onSave(draft); setEditing(false); }
          if (e.key === "Escape") { setDraft(value); setEditing(false); }
        }}
        onBlur={() => { if (draft !== value) onSave(draft); setEditing(false); }}
        style={{
          background: T.surfaceAlt, border: `1px solid ${T.accent}`, borderRadius: 4,
          color: T.text, fontSize: 12, padding: "2px 6px", width: 120, outline: "none",
        }}
      />
    </span>
  );
}

/* ─── Add Member Modal ────────────────────────────────────────────────────── */

const EMPTY_MEMBER = {
  first_name: "", last_name: "", email: "", phone_number: "",
  member_number: "", gender: "", preferred_language: "de", notes: "",
};

function AddMemberModal({
  open, onClose, onCreated,
}: {
  open: boolean; onClose: () => void; onCreated: () => void;
}) {
  const [form, setForm] = useState({ ...EMPTY_MEMBER });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.first_name.trim() || !form.last_name.trim()) {
      setError("Vor- und Nachname sind Pflichtfelder");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch("/admin/members", {
        method: "POST",
        body: JSON.stringify({ ...form, source: "manual" }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Fehler beim Anlegen");
      }
      setForm({ ...EMPTY_MEMBER });
      onCreated();
      onClose();
    } catch (e: any) {
      setError(e.message || "Unbekannter Fehler");
    } finally {
      setSaving(false);
    }
  };

  const fieldStyle = {
    background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8,
    color: T.text, fontSize: 13, padding: "10px 12px", width: "100%", outline: "none",
  };
  const labelStyle = { fontSize: 11, fontWeight: 600, color: T.textDim, marginBottom: 4, display: "block" as const };

  return (
    <Modal
      open={open}
      title="Neues Mitglied anlegen"
      subtitle="Manuell ein neues Mitglied zur Datenbank hinzufügen"
      onClose={onClose}
      width="min(560px, 100%)"
      footer={
        <>
          <button type="button" onClick={onClose} style={{ ...fieldStyle, width: "auto", cursor: "pointer", padding: "8px 16px" }}>Abbrechen</button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            style={{
              background: T.accent, color: "#fff", border: "none", borderRadius: 8,
              padding: "8px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer", opacity: saving ? 0.6 : 1,
            }}
          >
            {saving ? "Speichern..." : "Mitglied anlegen"}
          </button>
        </>
      }
    >
      {error && <div style={{ background: T.dangerDim, color: T.danger, padding: "8px 12px", borderRadius: 8, fontSize: 12, marginBottom: 12 }}>{error}</div>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div><label style={labelStyle}>Vorname *</label><input value={form.first_name} onChange={(e) => set("first_name", e.target.value)} style={fieldStyle} placeholder="Max" /></div>
        <div><label style={labelStyle}>Nachname *</label><input value={form.last_name} onChange={(e) => set("last_name", e.target.value)} style={fieldStyle} placeholder="Mustermann" /></div>
        <div><label style={labelStyle}>E-Mail</label><input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} style={fieldStyle} placeholder="max@example.com" /></div>
        <div><label style={labelStyle}>Telefon</label><input value={form.phone_number} onChange={(e) => set("phone_number", e.target.value)} style={fieldStyle} placeholder="+49 170 1234567" /></div>
        <div><label style={labelStyle}>Mitgliedsnummer</label><input value={form.member_number} onChange={(e) => set("member_number", e.target.value)} style={fieldStyle} placeholder="Optional" /></div>
        <div>
          <label style={labelStyle}>Geschlecht</label>
          <select value={form.gender} onChange={(e) => set("gender", e.target.value)} style={fieldStyle}>
            <option value="">-</option>
            <option value="MALE">Männlich</option>
            <option value="FEMALE">Weiblich</option>
            <option value="DIVERSE">Divers</option>
          </select>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <label style={labelStyle}>Notizen</label>
          <textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={2} style={{ ...fieldStyle, resize: "vertical" }} placeholder="Optionale Notizen..." />
        </div>
      </div>
    </Modal>
  );
}

/* ─── CSV Import Modal ────────────────────────────────────────────────────── */

function CsvImportModal({
  open, onClose, onImported,
}: {
  open: boolean; onClose: () => void; onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await apiFetch("/admin/members/import/csv", { method: "POST", body: formData });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Import fehlgeschlagen");
      }
      const data = await res.json();
      setResult(data);
      onImported();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Modal open={open} title="CSV Import" subtitle="Mitglieder aus einer CSV-Datei importieren" onClose={() => { onClose(); setFile(null); setResult(null); setError(""); }} width="min(520px, 100%)">
      {!result ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
            style={{
              border: `2px dashed ${T.border}`, borderRadius: 12, padding: 32, textAlign: "center",
              cursor: "pointer", background: T.surfaceAlt, transition: "border-color 0.2s",
            }}
          >
            <Upload size={24} color={T.textDim} style={{ margin: "0 auto 8px" }} />
            <div style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>{file ? file.name : "CSV-Datei hierher ziehen oder klicken"}</div>
            <div style={{ fontSize: 11, color: T.textDim, marginTop: 4 }}>Unterstützt: .csv (UTF-8, Semikolon oder Komma-getrennt)</div>
            <input ref={inputRef} type="file" accept=".csv" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ display: "none" }} />
          </div>
          <div style={{ fontSize: 11, color: T.textDim }}>
            Erkannte Spalten: <strong>Vorname/first_name</strong>, <strong>Nachname/last_name</strong>, E-Mail, Telefon, Mitgliedsnummer, Geschlecht, Sprache, Notizen.
            Zusätzliche Spalten werden als Custom Fields importiert.
          </div>
          {error && <div style={{ background: T.dangerDim, color: T.danger, padding: "8px 12px", borderRadius: 8, fontSize: 12 }}>{error}</div>}
          <button
            type="button" onClick={upload} disabled={!file || uploading}
            style={{
              background: T.accent, color: "#fff", border: "none", borderRadius: 8,
              padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer",
              opacity: (!file || uploading) ? 0.5 : 1, alignSelf: "flex-end",
            }}
          >
            {uploading ? "Importiere..." : "Importieren"}
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Check size={20} color={T.success} />
            <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Import abgeschlossen</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
            <div style={{ background: T.successDim, borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: T.success }}>{result.created}</div>
              <div style={{ fontSize: 10, color: T.textDim }}>Neu erstellt</div>
            </div>
            <div style={{ background: T.infoDim, borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: T.info }}>{result.updated}</div>
              <div style={{ fontSize: 10, color: T.textDim }}>Aktualisiert</div>
            </div>
            <div style={{ background: result.errors > 0 ? T.dangerDim : T.surfaceAlt, borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: result.errors > 0 ? T.danger : T.textDim }}>{result.errors}</div>
              <div style={{ fontSize: 10, color: T.textDim }}>Fehler</div>
            </div>
          </div>
          {result.custom_columns_detected?.length > 0 && (
            <div style={{ fontSize: 11, color: T.textMuted }}>
              Custom Fields erkannt: {result.custom_columns_detected.join(", ")}
            </div>
          )}
          <button
            type="button" onClick={() => { onClose(); setFile(null); setResult(null); }}
            style={{ background: T.accent, color: "#fff", border: "none", borderRadius: 8, padding: "10px 20px", fontSize: 13, fontWeight: 600, cursor: "pointer", alignSelf: "flex-end" }}
          >
            Schließen
          </button>
        </div>
      )}
    </Modal>
  );
}

/* ─── Custom Columns Modal ────────────────────────────────────────────────── */

function CustomColumnsModal({
  open, onClose, columns, onRefresh,
}: {
  open: boolean; onClose: () => void; columns: CustomColumn[]; onRefresh: () => void;
}) {
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("text");
  const [saving, setSaving] = useState(false);

  const addColumn = async () => {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await apiFetch("/admin/members/columns", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), field_type: newType }),
      });
      setNewName("");
      setNewType("text");
      onRefresh();
    } catch { /* ignore */ }
    setSaving(false);
  };

  const deleteColumn = async (id: number) => {
    await apiFetch(`/admin/members/columns/${id}`, { method: "DELETE" });
    onRefresh();
  };

  const fieldStyle = {
    background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8,
    color: T.text, fontSize: 13, padding: "8px 10px", outline: "none",
  };

  return (
    <Modal open={open} title="Eigene Spalten verwalten" subtitle="Definiere zusätzliche Felder für deine Mitglieder" onClose={onClose} width="min(520px, 100%)">
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Existing columns */}
        {columns.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {columns.map((c) => (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", background: T.surfaceAlt, borderRadius: 8 }}>
                <span style={{ flex: 1, fontSize: 13, color: T.text, fontWeight: 600 }}>{c.name}</span>
                <Badge variant="default" size="xs">{c.field_type}</Badge>
                <button type="button" onClick={() => deleteColumn(c.id)} style={{ background: "transparent", border: "none", cursor: "pointer", color: T.danger, padding: 4 }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
        {columns.length === 0 && (
          <div style={{ fontSize: 12, color: T.textDim, textAlign: "center", padding: 16 }}>Noch keine eigenen Spalten definiert.</div>
        )}

        {/* Add new */}
        <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 12, display: "flex", gap: 8, alignItems: "flex-end" }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 11, fontWeight: 600, color: T.textDim, display: "block", marginBottom: 4 }}>Spaltenname</label>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="z.B. Schuhgröße" style={{ ...fieldStyle, width: "100%" }}
              onKeyDown={(e) => { if (e.key === "Enter") addColumn(); }}
            />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: T.textDim, display: "block", marginBottom: 4 }}>Typ</label>
            <select value={newType} onChange={(e) => setNewType(e.target.value)} style={{ ...fieldStyle, minWidth: 90 }}>
              <option value="text">Text</option>
              <option value="number">Zahl</option>
              <option value="date">Datum</option>
              <option value="boolean">Ja/Nein</option>
            </select>
          </div>
          <button
            type="button" onClick={addColumn} disabled={saving || !newName.trim()}
            style={{
              background: T.accent, color: "#fff", border: "none", borderRadius: 8,
              padding: "8px 14px", fontSize: 13, fontWeight: 600, cursor: "pointer",
              opacity: (saving || !newName.trim()) ? 0.5 : 1, whiteSpace: "nowrap",
            }}
          >
            <Plus size={14} style={{ marginRight: 4, verticalAlign: "middle" }} />Hinzufügen
          </button>
        </div>
      </div>
    </Modal>
  );
}

/* ─── Main Page ───────────────────────────────────────────────────────────── */

export default function MembersPage() {
  const [members, setMembers] = useState<Member[]>([]);
  const [customColumns, setCustomColumns] = useState<CustomColumn[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  // Filters
  const [filterSource, setFilterSource] = useState("all");
  const [filterLang, setFilterLang] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCsvModal, setShowCsvModal] = useState(false);
  const [showColumnsModal, setShowColumnsModal] = useState(false);

  // Selection for bulk actions
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const fetchMembers = useCallback(async (search?: string) => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams({ limit: "2000" });
      if (search) params.set("search", search);
      const res = await apiFetch(`/admin/members?${params}`);
      if (res.ok) {
        const data = await res.json();
        setMembers(data);
      }
    } catch { /* ignore */ }
    setIsLoading(false);
  }, []);

  const fetchColumns = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/members/columns");
      if (res.ok) setCustomColumns(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchMembers(); fetchColumns(); }, [fetchMembers, fetchColumns]);

  // Inline update
  const updateMemberField = async (memberId: number, field: string, value: string) => {
    try {
      const body: any = {};
      if (field.startsWith("cf:")) {
        body.custom_fields = { [field.slice(3)]: value };
      } else {
        body[field] = value;
      }
      const res = await apiFetch(`/admin/members/${memberId}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setMembers((prev) => prev.map((m) => (m.id === memberId || m.customer_id === updated.customer_id) ? { ...m, ...updated } : m));
      }
    } catch { /* ignore */ }
  };

  const deleteMember = async (memberId: number) => {
    if (!confirm("Mitglied wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/admin/members/${memberId}`, { method: "DELETE" });
      if (res.ok) setMembers((prev) => prev.filter((m) => m.id !== memberId));
    } catch { /* ignore */ }
  };

  const bulkDelete = async () => {
    if (!confirm(`${selectedIds.size} Mitglieder wirklich löschen?`)) return;
    for (const id of selectedIds) {
      try { await apiFetch(`/admin/members/${id}`, { method: "DELETE" }); } catch { /* skip */ }
    }
    setSelectedIds(new Set());
    fetchMembers(query);
  };

  const exportCsv = async () => {
    try {
      const res = await apiFetch("/admin/members/export/csv");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `members_export_${Date.now()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* ignore */ }
  };

  // Derived data
  const languageOptions = useMemo(() => [...new Set(members.map((m) => m.preferred_language).filter(Boolean) as string[])].sort(), [members]);
  const sourceOptions = useMemo(() => [...new Set(members.map((m) => m.source || "magicline"))].sort(), [members]);

  const filteredMembers = useMemo(() => {
    return members.filter((m) => {
      if (filterSource !== "all" && (m.source || "magicline") !== filterSource) return false;
      if (filterLang !== "all" && m.preferred_language !== filterLang) return false;
      if (filterStatus === "active" && m.is_paused) return false;
      if (filterStatus === "paused" && !m.is_paused) return false;
      return true;
    });
  }, [members, filterSource, filterLang, filterStatus]);

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === filteredMembers.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredMembers.map((m) => m.id!).filter(Boolean)));
    }
  };

  const visibleCustomCols = customColumns.filter((c) => c.is_visible);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* ── Header Bar ── */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0 }}>Mitglieder</h1>
          <p style={{ fontSize: 12, color: T.textDim, margin: "4px 0 0" }}>
            {members.length} Mitglieder · {sourceOptions.length} Quelle{sourceOptions.length !== 1 ? "n" : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" onClick={() => setShowColumnsModal(true)} style={{ display: "flex", alignItems: "center", gap: 6, background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, color: T.textMuted, padding: "8px 12px", fontSize: 12, cursor: "pointer" }}>
            <Columns3 size={14} /> Spalten
          </button>
          <button type="button" onClick={() => setShowCsvModal(true)} style={{ display: "flex", alignItems: "center", gap: 6, background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, color: T.textMuted, padding: "8px 12px", fontSize: 12, cursor: "pointer" }}>
            <Upload size={14} /> CSV Import
          </button>
          <button type="button" onClick={exportCsv} style={{ display: "flex", alignItems: "center", gap: 6, background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 8, color: T.textMuted, padding: "8px 12px", fontSize: 12, cursor: "pointer" }}>
            <Download size={14} /> Export
          </button>
          <button
            type="button" onClick={() => setShowAddModal(true)}
            style={{
              display: "flex", alignItems: "center", gap: 6, background: T.accent, border: "none",
              borderRadius: 8, color: "#fff", padding: "8px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer",
            }}
          >
            <Plus size={14} /> Mitglied anlegen
          </button>
        </div>
      </div>

      {/* ── Search & Filters ── */}
      <Card style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Search size={14} color={T.textDim} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") fetchMembers(query); }}
            placeholder="Suche: Name, E-Mail, Telefon, Mitgliedsnummer"
            style={{ flex: 1, background: "transparent", border: "none", outline: "none", fontSize: 13, color: T.text }}
          />
          {query && (
            <button type="button" onClick={() => { setQuery(""); fetchMembers(); }} style={{ background: "transparent", border: "none", cursor: "pointer", color: T.textDim }}>
              <X size={14} />
            </button>
          )}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 8 }}>
          <select value={filterSource} onChange={(e) => setFilterSource(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Quelle: Alle</option>
            {sourceOptions.map((s) => (
              <option key={s} value={s}>Quelle: {SOURCE_CONFIG[s]?.label || s}</option>
            ))}
          </select>
          <select value={filterLang} onChange={(e) => setFilterLang(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Sprache: Alle</option>
            {languageOptions.map((l) => (
              <option key={l} value={l}>Sprache: {l.toUpperCase()}</option>
            ))}
          </select>
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} style={{ background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`, borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
            <option value="all">Status: Alle</option>
            <option value="active">Status: Aktiv</option>
            <option value="paused">Status: Pausiert</option>
          </select>
        </div>
        <div style={{ fontSize: 11, color: T.textDim, display: "flex", justifyContent: "space-between" }}>
          <span>Ergebnis: {filteredMembers.length} / {members.length}</span>
          {selectedIds.size > 0 && (
            <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span>{selectedIds.size} ausgewählt</span>
              <button type="button" onClick={bulkDelete} style={{ background: T.dangerDim, color: T.danger, border: "none", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer", fontWeight: 600 }}>
                <Trash2 size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />Löschen
              </button>
            </span>
          )}
        </div>
      </Card>

      {/* ── Table ── */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        {isLoading ? (
          <div style={{ padding: 48, textAlign: "center", color: T.textMuted, fontSize: 13 }}>Laden...</div>
        ) : filteredMembers.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div style={{ width: 56, height: 56, borderRadius: "50%", background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.accent }}>
              <Users size={24} />
            </div>
            <p style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>Keine Mitglieder gefunden</p>
            <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>Lege manuell Mitglieder an, importiere eine CSV oder verbinde eine Integration.</p>
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: T.surfaceAlt }}>
                  <th style={{ width: 36, padding: "10px 8px", textAlign: "center" }}>
                    <input type="checkbox" checked={selectedIds.size === filteredMembers.length && filteredMembers.length > 0} onChange={selectAll} style={{ cursor: "pointer" }} />
                  </th>
                  {["Mitglied", "Kontakt", "Quelle", "Status", ...visibleCustomCols.map((c) => c.name), "Notizen", ""].map((h, i) => (
                    <th key={`${h}-${i}`} style={{ textAlign: "left", padding: "10px 12px", fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", borderBottom: `1px solid ${T.border}`, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((m) => {
                  const isExpanded = expandedIds.has(m.customer_id);
                  const canDelete = ["manual", "csv", "api"].includes(m.source || "");
                  const colSpan = 7 + visibleCustomCols.length;

                  return (
                    <Fragment key={m.customer_id}>
                      <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                        {/* Checkbox */}
                        <td style={{ padding: "10px 8px", textAlign: "center", verticalAlign: "top" }}>
                          {m.id && <input type="checkbox" checked={selectedIds.has(m.id)} onChange={() => toggleSelect(m.id!)} style={{ cursor: "pointer" }} />}
                        </td>

                        {/* Member Info */}
                        <td style={{ padding: "10px 12px", minWidth: 200, verticalAlign: "top" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <EditableCell value={m.first_name} onSave={(v) => m.id && updateMemberField(m.id, "first_name", v)} />
                            <EditableCell value={m.last_name} onSave={(v) => m.id && updateMemberField(m.id, "last_name", v)} />
                          </div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>
                            {m.member_number ? `#${m.member_number}` : "Keine Nr."}
                            {m.member_since && ` · Seit ${new Date(m.member_since).toLocaleDateString("de-DE")}`}
                          </div>
                          {m.tags && m.tags.length > 0 && (
                            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
                              {m.tags.map((tag) => (
                                <span key={tag} style={{ fontSize: 10, padding: "1px 6px", borderRadius: 4, background: T.accentDim, color: T.accentLight }}>{tag}</span>
                              ))}
                            </div>
                          )}
                          <button type="button" onClick={() => toggleExpanded(m.customer_id)} style={{ marginTop: 6, display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: T.accent, background: "transparent", border: "none", padding: 0, cursor: "pointer" }}>
                            {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />} Details
                          </button>
                        </td>

                        {/* Contact */}
                        <td style={{ padding: "10px 12px", minWidth: 180, verticalAlign: "top" }}>
                          <EditableCell value={m.email || ""} onSave={(v) => m.id && updateMemberField(m.id, "email", v)} type="email" placeholder="Keine E-Mail" />
                          <div style={{ marginTop: 4 }}>
                            <EditableCell value={m.phone_number || ""} onSave={(v) => m.id && updateMemberField(m.id, "phone_number", v)} type="tel" placeholder="Kein Telefon" />
                          </div>
                        </td>

                        {/* Source */}
                        <td style={{ padding: "10px 12px", verticalAlign: "top" }}>
                          <SourceBadge source={m.source} />
                          {m.source_id && <div style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>ID: {m.source_id}</div>}
                        </td>

                        {/* Status */}
                        <td style={{ padding: "10px 12px", verticalAlign: "top" }}>
                          {m.is_paused ? <Badge variant="warning" size="xs">Pausiert</Badge> : <Badge variant="success" size="xs">Aktiv</Badge>}
                          {m.contract_info && (
                            <div style={{ fontSize: 10, color: T.accent, marginTop: 4, fontWeight: 600 }}>{m.contract_info.plan_name}</div>
                          )}
                          {m.verified && <div style={{ marginTop: 4 }}><Badge variant="info" size="xs">Verifiziert ({m.chat_sessions || 0})</Badge></div>}
                        </td>

                        {/* Custom Columns */}
                        {visibleCustomCols.map((col) => (
                          <td key={col.slug} style={{ padding: "10px 12px", verticalAlign: "top" }}>
                            <EditableCell
                              value={(m.custom_fields || {})[col.slug] || ""}
                              onSave={(v) => m.id && updateMemberField(m.id, `cf:${col.slug}`, v)}
                              type={col.field_type === "number" ? "number" : col.field_type === "date" ? "date" : "text"}
                              placeholder="-"
                            />
                          </td>
                        ))}

                        {/* Notes */}
                        <td style={{ padding: "10px 12px", maxWidth: 200, verticalAlign: "top" }}>
                          <EditableCell value={m.notes || ""} onSave={(v) => m.id && updateMemberField(m.id, "notes", v)} placeholder="Keine Notizen" />
                        </td>

                        {/* Actions */}
                        <td style={{ padding: "10px 8px", verticalAlign: "top", whiteSpace: "nowrap" }}>
                          {canDelete && (
                            <button type="button" onClick={() => m.id && deleteMember(m.id)} title="Löschen" style={{ background: "transparent", border: "none", cursor: "pointer", color: T.danger, padding: 4 }}>
                              <Trash2 size={14} />
                            </button>
                          )}
                        </td>
                      </tr>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                          <td colSpan={colSpan} style={{ padding: "12px 16px", background: T.surfaceAlt }}>
                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                              <div>
                                <div style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase" }}>Aktivität</div>
                                {m.checkin_stats ? (
                                  <>
                                    <div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>30d: {m.checkin_stats.total_30d ?? 0} · 90d: {m.checkin_stats.total_90d ?? 0}</div>
                                    <div style={{ fontSize: 11, color: T.textDim }}>Letzte Aktivität: {m.checkin_stats.last_visit || "-"}</div>
                                  </>
                                ) : <div style={{ fontSize: 11, color: T.textDim, marginTop: 4 }}>Keine Daten</div>}
                              </div>
                              {m.checkin_stats?.churn_prediction && (
                                <div>
                                  <div style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase" }}>Churn-Risiko</div>
                                  <div style={{ marginTop: 4 }}>
                                    {m.checkin_stats.churn_prediction.risk === "high"
                                      ? <Badge variant="danger" size="xs">Hoch ({m.checkin_stats.churn_prediction.score})</Badge>
                                      : m.checkin_stats.churn_prediction.risk === "medium"
                                      ? <Badge variant="warning" size="xs">Mittel ({m.checkin_stats.churn_prediction.score})</Badge>
                                      : <Badge variant="success" size="xs">Niedrig ({m.checkin_stats.churn_prediction.score})</Badge>
                                    }
                                  </div>
                                </div>
                              )}
                              {m.contract_info && (
                                <div>
                                  <div style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase" }}>Vertrag</div>
                                  <div style={{ fontSize: 12, color: T.accent, fontWeight: 600, marginTop: 4 }}>{m.contract_info.plan_name}</div>
                                  <div style={{ fontSize: 11, color: T.textDim }}>Status: {m.contract_info.status}</div>
                                </div>
                              )}
                              {m.additional_info && Object.keys(m.additional_info).length > 0 && (
                                <div>
                                  <div style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase" }}>Zusätzliche Infos</div>
                                  <div style={{ marginTop: 4 }}>
                                    {Object.entries(m.additional_info).slice(0, 6).map(([k, v]) => (
                                      <div key={k} style={{ fontSize: 11, color: T.textMuted }}><strong style={{ color: T.text }}>{k}:</strong> {v}</div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {m.custom_fields && Object.keys(m.custom_fields).length > 0 && (
                                <div>
                                  <div style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase" }}>Custom Fields</div>
                                  <div style={{ marginTop: 4 }}>
                                    {Object.entries(m.custom_fields).map(([k, v]) => (
                                      <div key={k} style={{ fontSize: 11, color: T.textMuted }}><strong style={{ color: T.text }}>{k}:</strong> {v}</div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ── Modals ── */}
      <AddMemberModal open={showAddModal} onClose={() => setShowAddModal(false)} onCreated={() => fetchMembers(query)} />
      <CsvImportModal open={showCsvModal} onClose={() => setShowCsvModal(false)} onImported={() => fetchMembers(query)} />
      <CustomColumnsModal open={showColumnsModal} onClose={() => setShowColumnsModal(false)} columns={customColumns} onRefresh={fetchColumns} />
    </div>
  );
}
