"use client";

import { Fragment, useCallback, useEffect, useMemo, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users, Plus, Upload, Download, Trash2, Search, Filter, MoreHorizontal,
  UserCircle, Loader2, ChevronRight, ChevronLeft, X, Check, Mail, Phone,
  Building2, Tag, Calendar, ArrowUpDown, Eye, Edit3, StickyNote, Activity,
  Star, Clock, TrendingUp, UserPlus, FileSpreadsheet, RefreshCw, Hash,
  ChevronDown, BarChart3, Sparkles, Globe, AlertCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { usePermissions } from "@/lib/permissions";

// ── Types ────────────────────────────────────────────────────────────────────

type ContactTag = { id: number; name: string; color?: string };

type Contact = {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  job_title?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  preferred_language?: string | null;
  avatar_url?: string | null;
  lifecycle_stage: string;
  source: string;
  source_id?: string | null;
  consent_email?: boolean;
  consent_sms?: boolean;
  consent_phone?: boolean;
  consent_whatsapp?: boolean;
  score: number;
  tags: ContactTag[];
  custom_fields: Record<string, any>;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
};

type ContactListResponse = {
  items: Contact[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

type ContactStats = {
  total: number;
  lifecycle_distribution: Record<string, number>;
  source_distribution: Record<string, number>;
  with_email: number;
  with_phone: number;
  email_coverage: number;
  phone_coverage: number;
};

type NoteItem = {
  id: number;
  contact_id: number;
  content: string;
  is_pinned: boolean;
  created_by_name?: string;
  created_at: string;
};

type ActivityItem = {
  id: number;
  contact_id: number;
  activity_type: string;
  title: string;
  description?: string;
  performed_by_name?: string;
  created_at: string;
};

// ── Constants ────────────────────────────────────────────────────────────────

const LIFECYCLE_STAGES: Record<string, { label: string; color: string; variant: "success" | "info" | "warning" | "danger" | "accent" | "default" }> = {
  subscriber: { label: "Subscriber", color: T.info, variant: "info" },
  lead: { label: "Lead", color: T.warning, variant: "warning" },
  opportunity: { label: "Opportunity", color: T.accent, variant: "accent" },
  customer: { label: "Kunde", color: T.success, variant: "success" },
  churned: { label: "Churned", color: T.danger, variant: "danger" },
  other: { label: "Sonstige", color: T.textMuted, variant: "default" },
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "Manuell",
  csv: "CSV-Import",
  magicline: "Magicline",
  shopify: "Shopify",
  hubspot: "HubSpot",
  api: "API",
  ai_agent: "AI Agent",
  migration: "Migration",
};

const ACTIVITY_ICONS: Record<string, { icon: typeof Activity; color: string }> = {
  created: { icon: UserPlus, color: T.success },
  updated: { icon: Edit3, color: T.info },
  note_added: { icon: StickyNote, color: T.warning },
  tag_added: { icon: Tag, color: T.accent },
  tag_removed: { icon: X, color: T.danger },
  email_sent: { icon: Mail, color: T.email },
  call_logged: { icon: Phone, color: T.phone },
};

// ── Styles ───────────────────────────────────────────────────────────────────

const S = {
  page: { padding: "24px 28px", maxWidth: 1600, margin: "0 auto" } as React.CSSProperties,
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 } as React.CSSProperties,
  statCard: { padding: "16px 18px", borderRadius: 14, border: `1px solid ${T.border}`, background: T.surface } as React.CSSProperties,
  statValue: { fontSize: 26, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" } as React.CSSProperties,
  statLabel: { fontSize: 11, color: T.textMuted, marginTop: 2, fontWeight: 500 } as React.CSSProperties,
  toolbar: { display: "flex", alignItems: "center", gap: 10, marginBottom: 16, flexWrap: "wrap" as const } as React.CSSProperties,
  searchWrap: { position: "relative" as const, flex: 1, minWidth: 260 } as React.CSSProperties,
  searchInput: { width: "100%", padding: "10px 14px 10px 38px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" } as React.CSSProperties,
  searchIcon: { position: "absolute" as const, left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim } as React.CSSProperties,
  filterBtn: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtn: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtnSecondary: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  table: { width: "100%", borderCollapse: "collapse" as const } as React.CSSProperties,
  th: { padding: "10px 14px", fontSize: 11, fontWeight: 700, color: T.textDim, textAlign: "left" as const, borderBottom: `1px solid ${T.border}`, textTransform: "uppercase" as const, letterSpacing: "0.04em" } as React.CSSProperties,
  td: { padding: "12px 14px", fontSize: 13, color: T.text, borderBottom: `1px solid ${T.border}` } as React.CSSProperties,
  tr: { cursor: "pointer", transition: "background 0.15s" } as React.CSSProperties,
  avatar: { width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13, flexShrink: 0 } as React.CSSProperties,
  paginationRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", marginTop: 8 } as React.CSSProperties,
  pageBtn: { display: "flex", alignItems: "center", gap: 4, padding: "7px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, cursor: "pointer" } as React.CSSProperties,
  // Detail panel
  detailPanel: { position: "fixed" as const, top: 0, right: 0, bottom: 0, width: "min(680px, 100vw)", background: T.surface, borderLeft: `1px solid ${T.border}`, zIndex: 70, overflowY: "auto" as const, boxShadow: "-8px 0 40px rgba(0,0,0,0.4)" } as React.CSSProperties,
  detailHeader: { padding: "20px 24px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "flex-start", gap: 16 } as React.CSSProperties,
  detailTabs: { display: "flex", gap: 0, borderBottom: `1px solid ${T.border}`, padding: "0 24px" } as React.CSSProperties,
  detailTab: { padding: "12px 18px", fontSize: 12, fontWeight: 600, color: T.textMuted, cursor: "pointer", borderBottom: "2px solid transparent", transition: "all 0.2s" } as React.CSSProperties,
  detailTabActive: { color: T.accent, borderBottomColor: T.accent } as React.CSSProperties,
  detailContent: { padding: "20px 24px" } as React.CSSProperties,
  fieldRow: { display: "flex", alignItems: "center", padding: "10px 0", borderBottom: `1px solid ${T.border}` } as React.CSSProperties,
  fieldLabel: { width: 140, fontSize: 12, color: T.textDim, fontWeight: 600, flexShrink: 0 } as React.CSSProperties,
  fieldValue: { fontSize: 13, color: T.text, flex: 1 } as React.CSSProperties,
  timelineItem: { display: "flex", gap: 12, padding: "12px 0", borderBottom: `1px solid ${T.border}` } as React.CSSProperties,
  timelineDot: { width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 } as React.CSSProperties,
  noteCard: { padding: "12px 16px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, marginBottom: 10 } as React.CSSProperties,
  // Form
  formGroup: { marginBottom: 16 } as React.CSSProperties,
  formLabel: { display: "block", fontSize: 12, fontWeight: 600, color: T.textMuted, marginBottom: 6 } as React.CSSProperties,
  formInput: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" } as React.CSSProperties,
  formSelect: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", appearance: "none" as const } as React.CSSProperties,
};

// ── Helper Functions ─────────────────────────────────────────────────────────

function getInitials(first: string, last: string): string {
  return `${(first || "?")[0]}${(last || "?")[0]}`.toUpperCase();
}

function getAvatarColor(name: string): string {
  const colors = ["#6C5CE7", "#00D68F", "#FF6B6B", "#4FC3F7", "#FFAA00", "#A29BFE", "#FF754C", "#00BCD4"];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "–";
  try {
    return new Date(dateStr).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch { return "–"; }
}

function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return "–";
  try {
    return new Date(dateStr).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return "–"; }
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "gerade eben";
  if (mins < 60) return `vor ${mins} Min.`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `vor ${days} Tagen`;
  const months = Math.floor(days / 30);
  return `vor ${months} Monaten`;
}

// ── Main Component ───────────────────────────────────────────────────────────

export default function ContactsPage() {
  const { role } = usePermissions();
  const isAdmin = role === "system_admin" || role === "tenant_admin";

  // ── State ──────────────────────────────────────────────────────────────
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [filterLifecycle, setFilterLifecycle] = useState<string>("");
  const [filterSource, setFilterSource] = useState<string>("");
  const [showFilters, setShowFilters] = useState(false);
  const [stats, setStats] = useState<ContactStats | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Detail panel
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [detailTab, setDetailTab] = useState<"overview" | "timeline" | "notes">("overview");
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);

  // Create/Edit form
  const [formData, setFormData] = useState({
    first_name: "", last_name: "", email: "", phone: "", company: "",
    job_title: "", lifecycle_stage: "subscriber", source: "manual",
    gender: "", notes: "",
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  // Note form
  const [newNote, setNewNote] = useState("");

  const searchTimeout = useRef<NodeJS.Timeout | null>(null);

  // ── Data Fetching ──────────────────────────────────────────────────────

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      if (search) params.set("search", search);
      if (filterLifecycle) params.set("lifecycle_stage", filterLifecycle);
      if (filterSource) params.set("source", filterSource);

      const res = await apiFetch(`/api/v2/contacts?${params}`);
      if (res.ok) {
        const data: ContactListResponse = await res.json();
        setContacts(data.items);
        setTotal(data.total);
        setTotalPages(data.total_pages);
      }
    } catch (err) {
      console.error("Failed to fetch contacts", err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, search, filterLifecycle, filterSource]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await apiFetch("/api/v2/contacts/stats");
      if (res.ok) setStats(await res.json());
    } catch { /* best effort */ }
  }, []);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);
  useEffect(() => { fetchStats(); }, [fetchStats]);

  // Debounced search
  const handleSearchChange = (val: string) => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setSearch(val);
      setPage(1);
    }, 350);
  };

  // ── Contact Detail ─────────────────────────────────────────────────────

  const openDetail = async (contact: Contact) => {
    setSelectedContact(contact);
    setDetailTab("overview");
    setLoadingDetail(true);
    try {
      const [actRes, noteRes] = await Promise.all([
        apiFetch(`/api/v2/contacts/${contact.id}/activities?page_size=50`),
        apiFetch(`/api/v2/contacts/${contact.id}/notes`),
      ]);
      if (actRes.ok) {
        const data = await actRes.json();
        setActivities(data.items || []);
      }
      if (noteRes.ok) {
        setNotes(await noteRes.json());
      }
    } catch { /* best effort */ }
    setLoadingDetail(false);
  };

  const closeDetail = () => {
    setSelectedContact(null);
    setActivities([]);
    setNotes([]);
  };

  // ── CRUD Operations ────────────────────────────────────────────────────

  const handleCreate = async () => {
    setFormError("");
    setFormLoading(true);
    try {
      const body: any = { ...formData };
      if (body.notes) {
        body.notes = body.notes;
      }
      if (!body.email) delete body.email;
      if (!body.phone) delete body.phone;
      if (!body.company) delete body.company;
      if (!body.job_title) delete body.job_title;
      if (!body.gender) delete body.gender;

      const res = await apiFetch("/api/v2/contacts", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowCreateModal(false);
        resetForm();
        fetchContacts();
        fetchStats();
      } else {
        const err = await res.json();
        setFormError(err.detail || "Fehler beim Erstellen");
      }
    } catch (e: any) {
      setFormError(e.message || "Netzwerkfehler");
    }
    setFormLoading(false);
  };

  const handleUpdate = async () => {
    if (!selectedContact) return;
    setFormError("");
    setFormLoading(true);
    try {
      const body: any = {};
      if (formData.first_name) body.first_name = formData.first_name;
      if (formData.last_name) body.last_name = formData.last_name;
      if (formData.email) body.email = formData.email;
      if (formData.phone) body.phone = formData.phone;
      if (formData.company) body.company = formData.company;
      if (formData.job_title) body.job_title = formData.job_title;
      if (formData.lifecycle_stage) body.lifecycle_stage = formData.lifecycle_stage;
      if (formData.gender) body.gender = formData.gender;

      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedContact(updated);
        setShowEditModal(false);
        fetchContacts();
      } else {
        const err = await res.json();
        setFormError(err.detail || "Fehler beim Aktualisieren");
      }
    } catch (e: any) {
      setFormError(e.message || "Netzwerkfehler");
    }
    setFormLoading(false);
  };

  const handleDelete = async (ids: number[]) => {
    if (!confirm(`${ids.length} Kontakt(e) wirklich löschen?`)) return;
    try {
      const res = await apiFetch("/api/v2/contacts/bulk-delete", {
        method: "POST",
        body: JSON.stringify({ ids, permanent: false }),
      });
      if (res.ok) {
        setSelectedIds(new Set());
        closeDetail();
        fetchContacts();
        fetchStats();
      }
    } catch { /* best effort */ }
  };

  const handleAddNote = async () => {
    if (!selectedContact || !newNote.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes`, {
        method: "POST",
        body: JSON.stringify({ content: newNote, is_pinned: false }),
      });
      if (res.ok) {
        const note = await res.json();
        setNotes((prev) => [note, ...prev]);
        setNewNote("");
        // Refresh activities
        const actRes = await apiFetch(`/api/v2/contacts/${selectedContact.id}/activities?page_size=50`);
        if (actRes.ok) {
          const data = await actRes.json();
          setActivities(data.items || []);
        }
      }
    } catch { /* best effort */ }
  };

  const handleExport = async () => {
    try {
      const res = await apiFetch("/api/v2/contacts/export/csv");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "contacts_export.csv";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch { /* best effort */ }
  };

  const handleImportCSV = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await apiFetch("/api/v2/contacts/import/csv", {
        method: "POST",
        body: fd,
      });
      if (res.ok) {
        setShowImportModal(false);
        setTimeout(() => { fetchContacts(); fetchStats(); }, 2000);
      }
    } catch { /* best effort */ }
  };

  const resetForm = () => {
    setFormData({ first_name: "", last_name: "", email: "", phone: "", company: "", job_title: "", lifecycle_stage: "subscriber", source: "manual", gender: "", notes: "" });
    setFormError("");
  };

  const openEditModal = () => {
    if (!selectedContact) return;
    setFormData({
      first_name: selectedContact.first_name,
      last_name: selectedContact.last_name,
      email: selectedContact.email || "",
      phone: selectedContact.phone || "",
      company: selectedContact.company || "",
      job_title: selectedContact.job_title || "",
      lifecycle_stage: selectedContact.lifecycle_stage,
      source: selectedContact.source,
      gender: selectedContact.gender || "",
      notes: "",
    });
    setFormError("");
    setShowEditModal(true);
  };

  // ── Selection ──────────────────────────────────────────────────────────

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === contacts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(contacts.map((c) => c.id)));
    }
  };

  // ── Sort ───────────────────────────────────────────────────────────────

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortOrder("desc");
    }
    setPage(1);
  };

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={S.page}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <SectionHeader
        title="Kontakte"
        subtitle={`${total} Kontakte insgesamt`}
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <button style={S.actionBtnSecondary} onClick={handleExport}>
              <Download size={14} /> Export
            </button>
            <button style={S.actionBtnSecondary} onClick={() => setShowImportModal(true)}>
              <Upload size={14} /> Import
            </button>
            {isAdmin && (
              <button style={S.actionBtn} onClick={() => { resetForm(); setShowCreateModal(true); }}>
                <Plus size={14} /> Neuer Kontakt
              </button>
            )}
          </div>
        }
      />

      {/* ── Stats Row ───────────────────────────────────────────────────── */}
      {stats && (
        <div style={S.statsRow}>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Users size={18} style={{ color: T.accent }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.total}</div>
                <div style={S.statLabel}>Gesamt</div>
              </div>
            </div>
          </div>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: T.successDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <TrendingUp size={18} style={{ color: T.success }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.lifecycle_distribution?.customer || 0}</div>
                <div style={S.statLabel}>Kunden</div>
              </div>
            </div>
          </div>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: T.infoDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Mail size={18} style={{ color: T.info }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.email_coverage}%</div>
                <div style={S.statLabel}>E-Mail-Abdeckung</div>
              </div>
            </div>
          </div>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: T.warningDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Phone size={18} style={{ color: T.warning }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.phone_coverage}%</div>
                <div style={S.statLabel}>Telefon-Abdeckung</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <Card style={{ padding: "16px 18px", marginBottom: 16 }}>
        <div style={S.toolbar}>
          <div style={S.searchWrap}>
            <Search size={15} style={S.searchIcon} />
            <input
              style={S.searchInput}
              placeholder="Kontakte durchsuchen (Name, E-Mail, Telefon, Firma)..."
              onChange={(e) => handleSearchChange(e.target.value)}
            />
          </div>
          <button
            style={{ ...S.filterBtn, ...(showFilters ? { borderColor: T.accent, color: T.accent } : {}) }}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter size={14} /> Filter {showFilters ? "▲" : "▼"}
          </button>
          {selectedIds.size > 0 && isAdmin && (
            <button
              style={{ ...S.actionBtnSecondary, color: T.danger, borderColor: T.danger }}
              onClick={() => handleDelete(Array.from(selectedIds))}
            >
              <Trash2 size={14} /> {selectedIds.size} löschen
            </button>
          )}
        </div>

        {/* ── Filter Row ──────────────────────────────────────────────── */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: "hidden", display: "flex", gap: 12, flexWrap: "wrap", paddingTop: 8 }}
            >
              <div>
                <label style={{ fontSize: 11, color: T.textDim, fontWeight: 600, display: "block", marginBottom: 4 }}>Lifecycle-Phase</label>
                <select
                  style={S.formSelect}
                  value={filterLifecycle}
                  onChange={(e) => { setFilterLifecycle(e.target.value); setPage(1); }}
                >
                  <option value="">Alle</option>
                  {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 11, color: T.textDim, fontWeight: 600, display: "block", marginBottom: 4 }}>Quelle</label>
                <select
                  style={S.formSelect}
                  value={filterSource}
                  onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}
                >
                  <option value="">Alle</option>
                  {Object.entries(SOURCE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
              {(filterLifecycle || filterSource) && (
                <button
                  style={{ ...S.filterBtn, marginTop: "auto", color: T.danger }}
                  onClick={() => { setFilterLifecycle(""); setFilterSource(""); setPage(1); }}
                >
                  <X size={14} /> Filter zurücksetzen
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </Card>

      {/* ── Contact Table ───────────────────────────────────────────────── */}
      <Card style={{ overflow: "hidden" }}>
        {loading ? (
          <div style={{ padding: 60, textAlign: "center" }}>
            <Loader2 size={28} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
            <p style={{ color: T.textMuted, fontSize: 13, marginTop: 12 }}>Kontakte werden geladen...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center" }}>
            <Users size={40} style={{ color: T.textDim, marginBottom: 12 }} />
            <p style={{ color: T.textMuted, fontSize: 14, fontWeight: 600 }}>Keine Kontakte gefunden</p>
            <p style={{ color: T.textDim, fontSize: 12, marginTop: 4 }}>Erstellen Sie einen neuen Kontakt oder importieren Sie eine CSV-Datei.</p>
          </div>
        ) : (
          <>
            <div style={{ overflowX: "auto" }}>
              <table style={S.table}>
                <thead>
                  <tr>
                    <th style={{ ...S.th, width: 40 }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.size === contacts.length && contacts.length > 0}
                        onChange={toggleSelectAll}
                        style={{ accentColor: T.accent }}
                      />
                    </th>
                    <th style={S.th}>
                      <button onClick={() => handleSort("last_name")} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "inherit", fontWeight: "inherit", textTransform: "inherit" as any, letterSpacing: "inherit" }}>
                        Kontakt <ArrowUpDown size={12} />
                      </button>
                    </th>
                    <th style={S.th}>E-Mail</th>
                    <th style={S.th}>Telefon</th>
                    <th style={S.th}>Firma</th>
                    <th style={S.th}>
                      <button onClick={() => handleSort("lifecycle_stage")} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "inherit", fontWeight: "inherit", textTransform: "inherit" as any, letterSpacing: "inherit" }}>
                        Status <ArrowUpDown size={12} />
                      </button>
                    </th>
                    <th style={S.th}>Quelle</th>
                    <th style={S.th}>Tags</th>
                    <th style={S.th}>
                      <button onClick={() => handleSort("created_at")} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "inherit", fontWeight: "inherit", textTransform: "inherit" as any, letterSpacing: "inherit" }}>
                        Erstellt <ArrowUpDown size={12} />
                      </button>
                    </th>
                    <th style={{ ...S.th, width: 50 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {contacts.map((c) => {
                    const lc = LIFECYCLE_STAGES[c.lifecycle_stage] || LIFECYCLE_STAGES.other;
                    const avatarBg = getAvatarColor(c.full_name);
                    return (
                      <tr
                        key={c.id}
                        style={{ ...S.tr, background: selectedIds.has(c.id) ? T.accentDim : "transparent" }}
                        onMouseEnter={(e) => { if (!selectedIds.has(c.id)) (e.currentTarget.style.background = T.surfaceAlt); }}
                        onMouseLeave={(e) => { if (!selectedIds.has(c.id)) (e.currentTarget.style.background = "transparent"); }}
                        onClick={() => openDetail(c)}
                      >
                        <td style={S.td} onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={selectedIds.has(c.id)}
                            onChange={() => toggleSelect(c.id)}
                            style={{ accentColor: T.accent }}
                          />
                        </td>
                        <td style={S.td}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ ...S.avatar, background: `${avatarBg}22`, color: avatarBg }}>
                              {getInitials(c.first_name, c.last_name)}
                            </div>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13 }}>{c.full_name}</div>
                              {c.job_title && <div style={{ fontSize: 11, color: T.textDim }}>{c.job_title}</div>}
                            </div>
                          </div>
                        </td>
                        <td style={S.td}>
                          <span style={{ color: c.email ? T.text : T.textDim, fontSize: 12 }}>
                            {c.email || "–"}
                          </span>
                        </td>
                        <td style={S.td}>
                          <span style={{ color: c.phone ? T.text : T.textDim, fontSize: 12 }}>
                            {c.phone || "–"}
                          </span>
                        </td>
                        <td style={S.td}>
                          <span style={{ fontSize: 12 }}>{c.company || "–"}</span>
                        </td>
                        <td style={S.td}>
                          <Badge variant={lc.variant}>{lc.label}</Badge>
                        </td>
                        <td style={S.td}>
                          <span style={{ fontSize: 11, color: T.textMuted }}>{SOURCE_LABELS[c.source] || c.source}</span>
                        </td>
                        <td style={S.td}>
                          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                            {c.tags?.slice(0, 3).map((tag) => (
                              <span key={tag.id} style={{ display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: 10, fontWeight: 600, background: `${tag.color || T.accent}22`, color: tag.color || T.accent }}>
                                {tag.name}
                              </span>
                            ))}
                            {c.tags?.length > 3 && <span style={{ fontSize: 10, color: T.textDim }}>+{c.tags.length - 3}</span>}
                          </div>
                        </td>
                        <td style={S.td}>
                          <span style={{ fontSize: 11, color: T.textDim }}>{formatDate(c.created_at)}</span>
                        </td>
                        <td style={S.td}>
                          <button
                            style={{ background: "none", border: "none", color: T.textDim, cursor: "pointer", padding: 4 }}
                            onClick={(e) => { e.stopPropagation(); openDetail(c); }}
                          >
                            <Eye size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* ── Pagination ──────────────────────────────────────────── */}
            <div style={S.paginationRow}>
              <span style={{ fontSize: 12, color: T.textMuted }}>
                Seite {page} von {totalPages} ({total} Kontakte)
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  style={{ ...S.pageBtn, opacity: page <= 1 ? 0.4 : 1 }}
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft size={14} /> Zurück
                </button>
                <button
                  style={{ ...S.pageBtn, opacity: page >= totalPages ? 0.4 : 1 }}
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Weiter <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* ── Detail Side Panel ───────────────────────────────────────────── */}
      <AnimatePresence>
        {selectedContact && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={closeDetail}
              style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 65 }}
            />
            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              style={S.detailPanel}
            >
              {/* Detail Header */}
              <div style={S.detailHeader}>
                <div style={{ ...S.avatar, width: 52, height: 52, fontSize: 18, background: `${getAvatarColor(selectedContact.full_name)}22`, color: getAvatarColor(selectedContact.full_name) }}>
                  {getInitials(selectedContact.first_name, selectedContact.last_name)}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: T.text }}>{selectedContact.full_name}</div>
                  {selectedContact.job_title && <div style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>{selectedContact.job_title}{selectedContact.company ? ` bei ${selectedContact.company}` : ""}</div>}
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    <Badge variant={LIFECYCLE_STAGES[selectedContact.lifecycle_stage]?.variant || "default"}>
                      {LIFECYCLE_STAGES[selectedContact.lifecycle_stage]?.label || selectedContact.lifecycle_stage}
                    </Badge>
                    <Badge variant="default">Score: {selectedContact.score}</Badge>
                    <Badge variant="default">{SOURCE_LABELS[selectedContact.source] || selectedContact.source}</Badge>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {isAdmin && (
                    <button style={S.actionBtnSecondary} onClick={openEditModal}>
                      <Edit3 size={14} /> Bearbeiten
                    </button>
                  )}
                  <button
                    style={{ ...S.filterBtn, padding: "8px" }}
                    onClick={closeDetail}
                  >
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Detail Tabs */}
              <div style={S.detailTabs}>
                {(["overview", "timeline", "notes"] as const).map((tab) => (
                  <button
                    key={tab}
                    style={{ ...S.detailTab, ...(detailTab === tab ? S.detailTabActive : {}) }}
                    onClick={() => setDetailTab(tab)}
                  >
                    {tab === "overview" ? "Übersicht" : tab === "timeline" ? "Aktivitäten" : "Notizen"}
                  </button>
                ))}
              </div>

              {/* Detail Content */}
              <div style={S.detailContent}>
                {loadingDetail ? (
                  <div style={{ textAlign: "center", padding: 40 }}>
                    <Loader2 size={24} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
                  </div>
                ) : detailTab === "overview" ? (
                  /* ── Overview Tab ──────────────────────────────────────── */
                  <div>
                    <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>Kontaktdaten</h3>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><Mail size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />E-Mail</span>
                      <span style={S.fieldValue}>{selectedContact.email || "–"}</span>
                    </div>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><Phone size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />Telefon</span>
                      <span style={S.fieldValue}>{selectedContact.phone || "–"}</span>
                    </div>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><Building2 size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />Firma</span>
                      <span style={S.fieldValue}>{selectedContact.company || "–"}</span>
                    </div>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><UserCircle size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />Geschlecht</span>
                      <span style={S.fieldValue}>{selectedContact.gender || "–"}</span>
                    </div>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><Calendar size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />Geburtsdatum</span>
                      <span style={S.fieldValue}>{formatDate(selectedContact.date_of_birth)}</span>
                    </div>
                    <div style={S.fieldRow}>
                      <span style={S.fieldLabel}><Globe size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />Sprache</span>
                      <span style={S.fieldValue}>{selectedContact.preferred_language || "de"}</span>
                    </div>

                    <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, marginTop: 24, textTransform: "uppercase", letterSpacing: "0.04em" }}>Einwilligungen (DSGVO)</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      {[
                        { label: "E-Mail", value: selectedContact.consent_email },
                        { label: "SMS", value: selectedContact.consent_sms },
                        { label: "Telefon", value: selectedContact.consent_phone },
                        { label: "WhatsApp", value: selectedContact.consent_whatsapp },
                      ].map((c) => (
                        <div key={c.label} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                          {c.value ? <Check size={14} style={{ color: T.success }} /> : <X size={14} style={{ color: T.danger }} />}
                          <span style={{ fontSize: 12, color: T.text }}>{c.label}</span>
                        </div>
                      ))}
                    </div>

                    {selectedContact.tags?.length > 0 && (
                      <>
                        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, marginTop: 24, textTransform: "uppercase", letterSpacing: "0.04em" }}>Tags</h3>
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {selectedContact.tags.map((tag) => (
                            <span key={tag.id} style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600, background: `${tag.color || T.accent}22`, color: tag.color || T.accent }}>
                              <Tag size={11} /> {tag.name}
                            </span>
                          ))}
                        </div>
                      </>
                    )}

                    {Object.keys(selectedContact.custom_fields || {}).length > 0 && (
                      <>
                        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, marginTop: 24, textTransform: "uppercase", letterSpacing: "0.04em" }}>Benutzerdefinierte Felder</h3>
                        {Object.entries(selectedContact.custom_fields).map(([key, value]) => (
                          <div key={key} style={S.fieldRow}>
                            <span style={S.fieldLabel}>{key}</span>
                            <span style={S.fieldValue}>{String(value)}</span>
                          </div>
                        ))}
                      </>
                    )}

                    <div style={{ marginTop: 24, padding: "12px 16px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: T.textDim }}>
                        <span>Erstellt: {formatDateTime(selectedContact.created_at)}</span>
                        <span>Aktualisiert: {formatDateTime(selectedContact.updated_at)}</span>
                      </div>
                    </div>
                  </div>
                ) : detailTab === "timeline" ? (
                  /* ── Timeline Tab ──────────────────────────────────────── */
                  <div>
                    {activities.length === 0 ? (
                      <div style={{ textAlign: "center", padding: 40, color: T.textDim }}>
                        <Activity size={32} style={{ marginBottom: 8 }} />
                        <p style={{ fontSize: 13 }}>Noch keine Aktivitäten</p>
                      </div>
                    ) : (
                      activities.map((act) => {
                        const ai = ACTIVITY_ICONS[act.activity_type] || { icon: Activity, color: T.textMuted };
                        const Icon = ai.icon;
                        return (
                          <div key={act.id} style={S.timelineItem}>
                            <div style={{ ...S.timelineDot, background: `${ai.color}22`, color: ai.color }}>
                              <Icon size={15} />
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{act.title}</div>
                              {act.description && <div style={{ fontSize: 12, color: T.textMuted, marginTop: 2 }}>{act.description}</div>}
                              <div style={{ fontSize: 11, color: T.textDim, marginTop: 4 }}>
                                {act.performed_by_name && <span>{act.performed_by_name} • </span>}
                                {timeAgo(act.created_at)}
                              </div>
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                ) : (
                  /* ── Notes Tab ─────────────────────────────────────────── */
                  <div>
                    {/* Add Note */}
                    <div style={{ marginBottom: 16 }}>
                      <textarea
                        style={{ ...S.formInput, minHeight: 80, resize: "vertical" }}
                        placeholder="Neue Notiz hinzufügen..."
                        value={newNote}
                        onChange={(e) => setNewNote(e.target.value)}
                      />
                      <button
                        style={{ ...S.actionBtn, marginTop: 8, opacity: newNote.trim() ? 1 : 0.5 }}
                        disabled={!newNote.trim()}
                        onClick={handleAddNote}
                      >
                        <StickyNote size={14} /> Notiz speichern
                      </button>
                    </div>

                    {notes.length === 0 ? (
                      <div style={{ textAlign: "center", padding: 40, color: T.textDim }}>
                        <StickyNote size={32} style={{ marginBottom: 8 }} />
                        <p style={{ fontSize: 13 }}>Noch keine Notizen</p>
                      </div>
                    ) : (
                      notes.map((note) => (
                        <div key={note.id} style={S.noteCard}>
                          {note.is_pinned && (
                            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 6, fontSize: 10, color: T.warning, fontWeight: 600 }}>
                              <Star size={10} /> Angepinnt
                            </div>
                          )}
                          <div style={{ fontSize: 13, color: T.text, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{note.content}</div>
                          <div style={{ fontSize: 11, color: T.textDim, marginTop: 8 }}>
                            {note.created_by_name && <span>{note.created_by_name} • </span>}
                            {timeAgo(note.created_at)}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Create Contact Modal ────────────────────────────────────────── */}
      <Modal
        open={showCreateModal}
        title="Neuen Kontakt erstellen"
        subtitle="Füllen Sie die Kontaktdaten aus"
        onClose={() => setShowCreateModal(false)}
        footer={
          <>
            <button style={S.actionBtnSecondary} onClick={() => setShowCreateModal(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: formLoading ? 0.6 : 1 }} onClick={handleCreate} disabled={formLoading}>
              {formLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Plus size={14} />}
              Erstellen
            </button>
          </>
        }
      >
        <ContactForm formData={formData} setFormData={setFormData} formError={formError} />
      </Modal>

      {/* ── Edit Contact Modal ──────────────────────────────────────────── */}
      <Modal
        open={showEditModal}
        title="Kontakt bearbeiten"
        subtitle={selectedContact?.full_name}
        onClose={() => setShowEditModal(false)}
        footer={
          <>
            <button style={S.actionBtnSecondary} onClick={() => setShowEditModal(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: formLoading ? 0.6 : 1 }} onClick={handleUpdate} disabled={formLoading}>
              {formLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Check size={14} />}
              Speichern
            </button>
          </>
        }
      >
        <ContactForm formData={formData} setFormData={setFormData} formError={formError} isEdit />
      </Modal>

      {/* ── Import Modal ────────────────────────────────────────────────── */}
      <Modal
        open={showImportModal}
        title="Kontakte importieren"
        subtitle="CSV-Datei mit Kontaktdaten hochladen"
        onClose={() => setShowImportModal(false)}
      >
        <div style={{ textAlign: "center", padding: 20 }}>
          <FileSpreadsheet size={48} style={{ color: T.accent, marginBottom: 16 }} />
          <p style={{ fontSize: 13, color: T.text, marginBottom: 8 }}>CSV-Datei auswählen</p>
          <p style={{ fontSize: 11, color: T.textDim, marginBottom: 16 }}>
            Spalten: first_name, last_name, email, phone, company, lifecycle_stage
          </p>
          <input
            type="file"
            accept=".csv"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleImportCSV(file);
            }}
            style={{ fontSize: 12 }}
          />
        </div>
      </Modal>

      {/* ── Spin Animation ──────────────────────────────────────────────── */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Contact Form Sub-Component ───────────────────────────────────────────────

function ContactForm({
  formData,
  setFormData,
  formError,
  isEdit = false,
}: {
  formData: any;
  setFormData: (fn: any) => void;
  formError: string;
  isEdit?: boolean;
}) {
  const update = (field: string, value: string) => setFormData((prev: any) => ({ ...prev, [field]: value }));

  return (
    <div>
      {formError && (
        <div style={{ padding: "10px 14px", borderRadius: 8, background: T.dangerDim, color: T.danger, fontSize: 12, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
          <AlertCircle size={14} /> {formError}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Vorname *</label>
          <input style={S.formInput} value={formData.first_name} onChange={(e) => update("first_name", e.target.value)} placeholder="Max" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Nachname *</label>
          <input style={S.formInput} value={formData.last_name} onChange={(e) => update("last_name", e.target.value)} placeholder="Mustermann" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>E-Mail</label>
          <input style={S.formInput} type="email" value={formData.email} onChange={(e) => update("email", e.target.value)} placeholder="max@example.de" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Telefon</label>
          <input style={S.formInput} value={formData.phone} onChange={(e) => update("phone", e.target.value)} placeholder="+49 170 1234567" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Firma</label>
          <input style={S.formInput} value={formData.company} onChange={(e) => update("company", e.target.value)} placeholder="Firma GmbH" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Position</label>
          <input style={S.formInput} value={formData.job_title} onChange={(e) => update("job_title", e.target.value)} placeholder="Geschäftsführer" />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Lifecycle-Phase</label>
          <select style={S.formSelect} value={formData.lifecycle_stage} onChange={(e) => update("lifecycle_stage", e.target.value)}>
            {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Geschlecht</label>
          <select style={S.formSelect} value={formData.gender} onChange={(e) => update("gender", e.target.value)}>
            <option value="">–</option>
            <option value="male">Männlich</option>
            <option value="female">Weiblich</option>
            <option value="diverse">Divers</option>
          </select>
        </div>
      </div>
      {!isEdit && (
        <div style={S.formGroup}>
          <label style={S.formLabel}>Notiz</label>
          <textarea
            style={{ ...S.formInput, minHeight: 60, resize: "vertical" }}
            value={formData.notes}
            onChange={(e) => update("notes", e.target.value)}
            placeholder="Optionale Notiz zum Kontakt..."
          />
        </div>
      )}
    </div>
  );
}
