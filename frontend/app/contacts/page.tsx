"use client";

import { Fragment, useCallback, useEffect, useMemo, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users, Plus, Upload, Download, Trash2, Search, Filter, MoreHorizontal,
  UserCircle, Loader2, ChevronRight, ChevronLeft, X, Check, Mail, Phone,
  Building2, Tag, Calendar, ArrowUpDown, Eye, Edit3, StickyNote, Activity,
  Star, Clock, TrendingUp, UserPlus, FileSpreadsheet, RefreshCw, Hash,
  ChevronDown, BarChart3, Sparkles, Globe, AlertCircle, Copy, Merge,
  Settings2, Columns3, Shield, MessageSquare, Zap, Target, PieChart,
  Save, RotateCcw, Pin, PinOff, Pencil, ChevronUp, ListFilter,
  AlertTriangle, CheckCircle2, Link2, Layers, FolderOpen,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { usePermissions } from "@/lib/permissions";

// ── Types ────────────────────────────────────────────────────────────────────

type ContactTag = { id: number; name: string; color?: string; description?: string; contact_count?: number };

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
  average_score: number;
  recent_activities_7d: number;
  tag_count: number;
};

type NoteItem = {
  id: number;
  contact_id: number;
  content: string;
  is_pinned: boolean;
  created_by_name?: string;
  created_at: string;
  updated_at: string;
};

type ActivityItem = {
  id: number;
  contact_id: number;
  activity_type: string;
  title: string;
  description?: string;
  metadata?: Record<string, any>;
  performed_by_name?: string;
  created_at: string;
};

type DuplicateMatch = {
  contact: Contact;
  match_reason: string;
  confidence: number;
};

type DuplicateGroup = {
  match_type: string;
  match_value: string;
  confidence: number;
  contacts: Contact[];
};

type Segment = {
  id: number;
  name: string;
  description?: string;
  filter_json?: Record<string, any>;
  is_dynamic: boolean;
  contact_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type ColumnConfig = {
  key: string;
  label: string;
  visible: boolean;
  width?: number;
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
  email_sent: { icon: Mail, color: T.email || T.info },
  email_received: { icon: Mail, color: T.success },
  call: { icon: Phone, color: T.phone || T.warning },
  meeting: { icon: Users, color: T.accent },
  merge: { icon: Merge, color: T.info },
  lifecycle_change: { icon: TrendingUp, color: T.accent },
  campaign_sent: { icon: Zap, color: T.warning },
  campaign_opened: { icon: Eye, color: T.success },
  campaign_clicked: { icon: Link2, color: T.accent },
  import: { icon: Upload, color: T.info },
  chat_message: { icon: MessageSquare, color: T.info },
  custom: { icon: Sparkles, color: T.accent },
};

const DEFAULT_COLUMNS: ColumnConfig[] = [
  { key: "name", label: "Kontakt", visible: true },
  { key: "email", label: "E-Mail", visible: true },
  { key: "phone", label: "Telefon", visible: true },
  { key: "company", label: "Firma", visible: true },
  { key: "lifecycle_stage", label: "Status", visible: true },
  { key: "source", label: "Quelle", visible: true },
  { key: "tags", label: "Tags", visible: true },
  { key: "score", label: "Score", visible: false },
  { key: "gender", label: "Geschlecht", visible: false },
  { key: "created_at", label: "Erstellt", visible: true },
];

// ── Styles ───────────────────────────────────────────────────────────────────

const S = {
  page: { padding: "24px 28px", maxWidth: 1600, margin: "0 auto" } as React.CSSProperties,
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 20 } as React.CSSProperties,
  statCard: { padding: "14px 16px", borderRadius: 14, border: `1px solid ${T.border}`, background: T.surface } as React.CSSProperties,
  statValue: { fontSize: 24, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" } as React.CSSProperties,
  statLabel: { fontSize: 11, color: T.textMuted, marginTop: 2, fontWeight: 500 } as React.CSSProperties,
  toolbar: { display: "flex", alignItems: "center", gap: 10, marginBottom: 0, flexWrap: "wrap" as const } as React.CSSProperties,
  searchWrap: { position: "relative" as const, flex: 1, minWidth: 240 } as React.CSSProperties,
  searchInput: { width: "100%", padding: "10px 14px 10px 38px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" } as React.CSSProperties,
  searchIcon: { position: "absolute" as const, left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim } as React.CSSProperties,
  filterBtn: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtn: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtnSecondary: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtnDanger: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: `1px solid ${T.danger}`, background: "transparent", color: T.danger, fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  actionBtnSuccess: { display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10, border: "none", background: T.success, color: "#fff", fontSize: 12, fontWeight: 600, cursor: "pointer" } as React.CSSProperties,
  table: { width: "100%", borderCollapse: "collapse" as const } as React.CSSProperties,
  th: { padding: "10px 14px", fontSize: 11, fontWeight: 700, color: T.textDim, textAlign: "left" as const, borderBottom: `1px solid ${T.border}`, textTransform: "uppercase" as const, letterSpacing: "0.04em" } as React.CSSProperties,
  td: { padding: "12px 14px", fontSize: 13, color: T.text, borderBottom: `1px solid ${T.border}` } as React.CSSProperties,
  tr: { cursor: "pointer", transition: "background 0.15s" } as React.CSSProperties,
  avatar: { width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 13, flexShrink: 0 } as React.CSSProperties,
  paginationRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 0", marginTop: 8 } as React.CSSProperties,
  pageBtn: { display: "flex", alignItems: "center", gap: 4, padding: "7px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, fontSize: 12, cursor: "pointer" } as React.CSSProperties,
  // Detail panel
  detailPanel: { position: "fixed" as const, top: 0, right: 0, bottom: 0, width: "min(720px, 100vw)", background: T.surface, borderLeft: `1px solid ${T.border}`, zIndex: 70, overflowY: "auto" as const, boxShadow: "-8px 0 40px rgba(0,0,0,0.4)" } as React.CSSProperties,
  detailHeader: { padding: "20px 24px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "flex-start", gap: 16 } as React.CSSProperties,
  detailTabs: { display: "flex", gap: 0, borderBottom: `1px solid ${T.border}`, padding: "0 24px" } as React.CSSProperties,
  detailTab: { padding: "12px 16px", fontSize: 12, fontWeight: 600, color: T.textMuted, cursor: "pointer", borderBottom: "2px solid transparent", transition: "all 0.2s" } as React.CSSProperties,
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
  // Bulk action bar
  bulkBar: { display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", borderRadius: 10, background: `${T.accent}15`, border: `1px solid ${T.accent}40`, marginBottom: 12 } as React.CSSProperties,
  // Tag chip
  tagChip: { display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600 } as React.CSSProperties,
  // Inline edit
  inlineInput: { padding: "4px 8px", borderRadius: 6, border: `1px solid ${T.accent}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", width: "100%" } as React.CSSProperties,
  // Dropdown
  dropdown: { position: "absolute" as const, top: "100%", right: 0, marginTop: 4, minWidth: 200, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, boxShadow: "0 8px 32px rgba(0,0,0,0.3)", zIndex: 80, overflow: "hidden" } as React.CSSProperties,
  dropdownItem: { display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", fontSize: 12, color: T.text, cursor: "pointer", transition: "background 0.15s", border: "none", background: "none", width: "100%", textAlign: "left" as const } as React.CSSProperties,
  // Segment sidebar
  segmentSidebar: { padding: "12px 16px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", transition: "background 0.15s", fontSize: 13 } as React.CSSProperties,
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

function confidenceLabel(conf: number): string {
  if (conf >= 0.9) return "Sehr hoch";
  if (conf >= 0.7) return "Hoch";
  if (conf >= 0.5) return "Mittel";
  return "Niedrig";
}

function matchReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    email_exact: "Gleiche E-Mail",
    phone_exact: "Gleiche Telefonnummer",
    name_exact: "Gleicher Name",
    name_partial: "Ähnlicher Name",
  };
  return labels[reason] || reason;
}


// ══════════════════════════════════════════════════════════════════════════════
// ── Main Component ───────────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

export default function ContactsPage() {
  const { role } = usePermissions();
  const isAdmin = role === "system_admin" || role === "tenant_admin";

  // ── State ──────────────────────────────────────────────────────────────
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [stats, setStats] = useState<ContactStats | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [filterLifecycle, setFilterLifecycle] = useState<string>("");
  const [filterSource, setFilterSource] = useState<string>("");
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterHasEmail, setFilterHasEmail] = useState<string>("");
  const [filterHasPhone, setFilterHasPhone] = useState<string>("");
  const [filterScoreMin, setFilterScoreMin] = useState<string>("");
  const [filterScoreMax, setFilterScoreMax] = useState<string>("");
  const [filterCompany, setFilterCompany] = useState<string>("");

  // Columns
  const [columns, setColumns] = useState<ColumnConfig[]>(DEFAULT_COLUMNS);
  const [showColumnPicker, setShowColumnPicker] = useState(false);

  // Detail panel
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [detailTab, setDetailTab] = useState<"overview" | "timeline" | "notes" | "tags">("overview");
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState<Record<string, any>>({});

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showDuplicatesModal, setShowDuplicatesModal] = useState(false);
  const [showSegmentsPanel, setShowSegmentsPanel] = useState(false);
  const [showMergeModal, setShowMergeModal] = useState(false);

  // Bulk operations
  const [bulkAction, setBulkAction] = useState<string>("");
  const [bulkLifecycle, setBulkLifecycle] = useState("");
  const [bulkAddTags, setBulkAddTags] = useState("");
  const [bulkRemoveTags, setBulkRemoveTags] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);

  // Create/Edit form
  const [formData, setFormData] = useState({
    first_name: "", last_name: "", email: "", phone: "", company: "",
    job_title: "", lifecycle_stage: "subscriber", source: "manual",
    gender: "", notes: "", date_of_birth: "", preferred_language: "de",
    consent_email: false, consent_sms: false, consent_phone: false, consent_whatsapp: false,
    tags: "" as string,
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formDuplicates, setFormDuplicates] = useState<DuplicateMatch[]>([]);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);

  // Note form
  const [newNote, setNewNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingNoteContent, setEditingNoteContent] = useState("");

  // Tags
  const [allTags, setAllTags] = useState<ContactTag[]>([]);
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#6C5CE7");

  // Duplicates
  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [duplicatesLoading, setDuplicatesLoading] = useState(false);

  // Segments
  const [segments, setSegments] = useState<Segment[]>([]);
  const [activeSegment, setActiveSegment] = useState<Segment | null>(null);
  const [newSegmentName, setNewSegmentName] = useState("");
  const [newSegmentDesc, setNewSegmentDesc] = useState("");

  // Merge
  const [mergeTarget, setMergeTarget] = useState<Contact | null>(null);
  const [mergeFieldsFromSecondary, setMergeFieldsFromSecondary] = useState<string[]>([]);

  // Activity creation
  const [showAddActivity, setShowAddActivity] = useState(false);
  const [newActivityType, setNewActivityType] = useState("custom");
  const [newActivityTitle, setNewActivityTitle] = useState("");
  const [newActivityDesc, setNewActivityDesc] = useState("");

  const searchTimeout = useRef<NodeJS.Timeout | null>(null);

  // ── Active filter count ───────────────────────────────────────────────
  const activeFilterCount = [filterLifecycle, filterSource, filterHasEmail, filterHasPhone, filterScoreMin, filterScoreMax, filterCompany].filter(Boolean).length + filterTags.length;

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
      if (filterTags.length > 0) params.set("tags", filterTags.join(","));
      if (filterHasEmail === "yes") params.set("has_email", "true");
      if (filterHasEmail === "no") params.set("has_email", "false");
      if (filterHasPhone === "yes") params.set("has_phone", "true");
      if (filterHasPhone === "no") params.set("has_phone", "false");
      if (filterScoreMin) params.set("score_min", filterScoreMin);
      if (filterScoreMax) params.set("score_max", filterScoreMax);
      if (filterCompany) params.set("company", filterCompany);

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
  }, [page, pageSize, sortBy, sortOrder, search, filterLifecycle, filterSource, filterTags, filterHasEmail, filterHasPhone, filterScoreMin, filterScoreMax, filterCompany]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await apiFetch("/api/v2/contacts/stats");
      if (res.ok) setStats(await res.json());
    } catch { /* best effort */ }
  }, []);

  const fetchTags = useCallback(async () => {
    try {
      const res = await apiFetch("/api/v2/contacts/tags");
      if (res.ok) setAllTags(await res.json());
    } catch { /* best effort */ }
  }, []);

  const fetchSegments = useCallback(async () => {
    try {
      const res = await apiFetch("/api/v2/contacts/segments");
      if (res.ok) {
        const data = await res.json();
        setSegments(data.items || []);
      }
    } catch { /* best effort */ }
  }, []);

  useEffect(() => { fetchContacts(); }, [fetchContacts]);
  useEffect(() => { fetchStats(); fetchTags(); fetchSegments(); }, [fetchStats, fetchTags, fetchSegments]);

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
    setIsEditing(false);
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

  const refreshDetail = async () => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}`);
      if (res.ok) {
        const updated = await res.json();
        setSelectedContact(updated);
        // Also refresh activities
        const actRes = await apiFetch(`/api/v2/contacts/${updated.id}/activities?page_size=50`);
        if (actRes.ok) {
          const data = await actRes.json();
          setActivities(data.items || []);
        }
      }
    } catch { /* best effort */ }
  };

  const closeDetail = () => {
    setSelectedContact(null);
    setActivities([]);
    setNotes([]);
    setIsEditing(false);
  };

  // ── Inline Edit ────────────────────────────────────────────────────────

  const startInlineEdit = () => {
    if (!selectedContact) return;
    setEditData({
      first_name: selectedContact.first_name,
      last_name: selectedContact.last_name,
      email: selectedContact.email || "",
      phone: selectedContact.phone || "",
      company: selectedContact.company || "",
      job_title: selectedContact.job_title || "",
      lifecycle_stage: selectedContact.lifecycle_stage,
      gender: selectedContact.gender || "",
      date_of_birth: selectedContact.date_of_birth || "",
      preferred_language: selectedContact.preferred_language || "de",
      consent_email: selectedContact.consent_email || false,
      consent_sms: selectedContact.consent_sms || false,
      consent_phone: selectedContact.consent_phone || false,
      consent_whatsapp: selectedContact.consent_whatsapp || false,
    });
    setIsEditing(true);
  };

  const saveInlineEdit = async () => {
    if (!selectedContact) return;
    try {
      const body: any = {};
      Object.entries(editData).forEach(([key, val]) => {
        const orig = (selectedContact as any)[key];
        if (val !== orig && val !== (orig || "")) {
          body[key] = val || null;
        }
      });
      if (Object.keys(body).length === 0) {
        setIsEditing(false);
        return;
      }
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedContact(updated);
        setIsEditing(false);
        fetchContacts();
        fetchStats();
        // Refresh activities
        const actRes = await apiFetch(`/api/v2/contacts/${updated.id}/activities?page_size=50`);
        if (actRes.ok) {
          const data = await actRes.json();
          setActivities(data.items || []);
        }
      }
    } catch { /* best effort */ }
  };

  const cancelInlineEdit = () => {
    setIsEditing(false);
    setEditData({});
  };

  // ── CRUD Operations ────────────────────────────────────────────────────

  const checkDuplicatesBeforeCreate = async () => {
    setFormDuplicates([]);
    setShowDuplicateWarning(false);
    try {
      const params = new URLSearchParams();
      if (formData.email) params.set("email", formData.email);
      if (formData.phone) params.set("phone", formData.phone);
      if (formData.first_name) params.set("first_name", formData.first_name);
      if (formData.last_name) params.set("last_name", formData.last_name);

      const res = await apiFetch(`/api/v2/contacts/duplicates/check?${params}`);
      if (res.ok) {
        const data = await res.json();
        if (data.has_duplicates && data.duplicates.length > 0) {
          setFormDuplicates(data.duplicates);
          setShowDuplicateWarning(true);
          return true; // has duplicates
        }
      }
    } catch { /* best effort */ }
    return false;
  };

  const handleCreate = async (force = false) => {
    setFormError("");
    if (!force) {
      const hasDupes = await checkDuplicatesBeforeCreate();
      if (hasDupes) return;
    }
    setFormLoading(true);
    try {
      const body: any = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        lifecycle_stage: formData.lifecycle_stage,
        source: formData.source,
        preferred_language: formData.preferred_language,
        consent_email: formData.consent_email,
        consent_sms: formData.consent_sms,
        consent_phone: formData.consent_phone,
        consent_whatsapp: formData.consent_whatsapp,
      };
      if (formData.email) body.email = formData.email;
      if (formData.phone) body.phone = formData.phone;
      if (formData.company) body.company = formData.company;
      if (formData.job_title) body.job_title = formData.job_title;
      if (formData.gender) body.gender = formData.gender;
      if (formData.date_of_birth) body.date_of_birth = formData.date_of_birth;
      if (formData.notes) body.notes = formData.notes;
      if (formData.tags) body.tags = formData.tags.split(",").map((t: string) => t.trim()).filter(Boolean);

      const res = await apiFetch("/api/v2/contacts", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowCreateModal(false);
        setShowDuplicateWarning(false);
        setFormDuplicates([]);
        resetForm();
        fetchContacts();
        fetchStats();
        fetchTags();
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

  // ── Bulk Operations ────────────────────────────────────────────────────

  const handleBulkUpdate = async () => {
    if (selectedIds.size === 0) return;
    setBulkLoading(true);
    try {
      const body: any = { ids: Array.from(selectedIds) };
      if (bulkLifecycle) body.lifecycle_stage = bulkLifecycle;
      if (bulkAddTags) body.add_tags = bulkAddTags.split(",").map(t => t.trim()).filter(Boolean);
      if (bulkRemoveTags) body.remove_tags = bulkRemoveTags.split(",").map(t => t.trim()).filter(Boolean);

      const res = await apiFetch("/api/v2/contacts/bulk-update", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setShowBulkModal(false);
        setSelectedIds(new Set());
        setBulkLifecycle("");
        setBulkAddTags("");
        setBulkRemoveTags("");
        fetchContacts();
        fetchStats();
        fetchTags();
      }
    } catch { /* best effort */ }
    setBulkLoading(false);
  };

  // ── Notes ──────────────────────────────────────────────────────────────

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
        refreshDetail();
      }
    } catch { /* best effort */ }
  };

  const handleUpdateNote = async (noteId: number) => {
    if (!editingNoteContent.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/notes/${noteId}`, {
        method: "PUT",
        body: JSON.stringify({ content: editingNoteContent }),
      });
      if (res.ok) {
        const updated = await res.json();
        setNotes((prev) => prev.map(n => n.id === noteId ? updated : n));
        setEditingNoteId(null);
        setEditingNoteContent("");
      }
    } catch { /* best effort */ }
  };

  const handleDeleteNote = async (noteId: number) => {
    if (!confirm("Notiz wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/notes/${noteId}`, { method: "DELETE" });
      if (res.ok) {
        setNotes((prev) => prev.filter(n => n.id !== noteId));
      }
    } catch { /* best effort */ }
  };

  const handleTogglePin = async (noteId: number, currentPinned: boolean) => {
    try {
      const res = await apiFetch(`/api/v2/contacts/notes/${noteId}`, {
        method: "PUT",
        body: JSON.stringify({ is_pinned: !currentPinned }),
      });
      if (res.ok) {
        const updated = await res.json();
        setNotes((prev) => prev.map(n => n.id === noteId ? updated : n));
      }
    } catch { /* best effort */ }
  };

  // ── Tags on Contact ────────────────────────────────────────────────────

  const handleAddTagToContact = async (tagName: string) => {
    if (!selectedContact || !tagName.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/tags`, {
        method: "POST",
        body: JSON.stringify({ tag_name: tagName, color: newTagColor }),
      });
      if (res.ok) {
        refreshDetail();
        fetchTags();
        setNewTagName("");
      }
    } catch { /* best effort */ }
  };

  const handleRemoveTagFromContact = async (tagName: string) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/tags/${encodeURIComponent(tagName)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        refreshDetail();
        fetchTags();
      }
    } catch { /* best effort */ }
  };

  // ── Activities ─────────────────────────────────────────────────────────

  const handleAddActivity = async () => {
    if (!selectedContact || !newActivityTitle.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/activities`, {
        method: "POST",
        body: JSON.stringify({
          activity_type: newActivityType,
          title: newActivityTitle,
          description: newActivityDesc || undefined,
        }),
      });
      if (res.ok) {
        const act = await res.json();
        setActivities((prev) => [act, ...prev]);
        setShowAddActivity(false);
        setNewActivityTitle("");
        setNewActivityDesc("");
        setNewActivityType("custom");
      }
    } catch { /* best effort */ }
  };

  // ── Duplicates ─────────────────────────────────────────────────────────

  const fetchDuplicateGroups = async () => {
    setDuplicatesLoading(true);
    try {
      const res = await apiFetch("/api/v2/contacts/duplicates?page_size=50");
      if (res.ok) {
        const data = await res.json();
        setDuplicateGroups(data.groups || []);
      }
    } catch { /* best effort */ }
    setDuplicatesLoading(false);
  };

  // ── Merge ──────────────────────────────────────────────────────────────

  const handleMerge = async () => {
    if (!selectedContact || !mergeTarget) return;
    try {
      const res = await apiFetch("/api/v2/contacts/merge", {
        method: "POST",
        body: JSON.stringify({
          primary_id: selectedContact.id,
          secondary_id: mergeTarget.id,
          fields_from_secondary: mergeFieldsFromSecondary,
        }),
      });
      if (res.ok) {
        const merged = await res.json();
        setSelectedContact(merged);
        setShowMergeModal(false);
        setMergeTarget(null);
        setMergeFieldsFromSecondary([]);
        fetchContacts();
        fetchStats();
      }
    } catch { /* best effort */ }
  };

  // ── Segments ───────────────────────────────────────────────────────────

  const handleCreateSegment = async () => {
    if (!newSegmentName.trim()) return;
    const filterJson: Record<string, any> = {};
    if (filterLifecycle) filterJson.lifecycle_stage = filterLifecycle;
    if (filterSource) filterJson.source = filterSource;
    if (filterTags.length > 0) filterJson.tags = filterTags;
    if (filterCompany) filterJson.company = filterCompany;

    try {
      const res = await apiFetch("/api/v2/contacts/segments", {
        method: "POST",
        body: JSON.stringify({
          name: newSegmentName,
          description: newSegmentDesc || undefined,
          filter_json: Object.keys(filterJson).length > 0 ? filterJson : undefined,
          is_dynamic: true,
        }),
      });
      if (res.ok) {
        setNewSegmentName("");
        setNewSegmentDesc("");
        fetchSegments();
      }
    } catch { /* best effort */ }
  };

  const handleDeleteSegment = async (segmentId: number) => {
    if (!confirm("Segment wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/segments/${segmentId}`, { method: "DELETE" });
      if (res.ok) {
        if (activeSegment?.id === segmentId) setActiveSegment(null);
        fetchSegments();
      }
    } catch { /* best effort */ }
  };

  // ── Export / Import ────────────────────────────────────────────────────

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
        setTimeout(() => { fetchContacts(); fetchStats(); fetchTags(); }, 2000);
      }
    } catch { /* best effort */ }
  };

  const resetForm = () => {
    setFormData({
      first_name: "", last_name: "", email: "", phone: "", company: "",
      job_title: "", lifecycle_stage: "subscriber", source: "manual",
      gender: "", notes: "", date_of_birth: "", preferred_language: "de",
      consent_email: false, consent_sms: false, consent_phone: false, consent_whatsapp: false,
      tags: "",
    });
    setFormError("");
    setFormDuplicates([]);
    setShowDuplicateWarning(false);
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
      date_of_birth: selectedContact.date_of_birth || "",
      preferred_language: selectedContact.preferred_language || "de",
      consent_email: selectedContact.consent_email || false,
      consent_sms: selectedContact.consent_sms || false,
      consent_phone: selectedContact.consent_phone || false,
      consent_whatsapp: selectedContact.consent_whatsapp || false,
      tags: selectedContact.tags?.map(t => t.name).join(", ") || "",
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

  // ── Reset Filters ─────────────────────────────────────────────────────

  const resetFilters = () => {
    setFilterLifecycle("");
    setFilterSource("");
    setFilterTags([]);
    setFilterHasEmail("");
    setFilterHasPhone("");
    setFilterScoreMin("");
    setFilterScoreMax("");
    setFilterCompany("");
    setActiveSegment(null);
    setPage(1);
  };

  // ── Column Toggle ─────────────────────────────────────────────────────

  const toggleColumn = (key: string) => {
    setColumns(prev => prev.map(c => c.key === key ? { ...c, visible: !c.visible } : c));
  };

  const visibleColumns = columns.filter(c => c.visible);


  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div style={S.page}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <SectionHeader
        title="Kontakte"
        subtitle={`${total} Kontakte insgesamt${activeSegment ? ` • Segment: ${activeSegment.name}` : ""}`}
        action={
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button style={S.actionBtnSecondary} onClick={() => { fetchDuplicateGroups(); setShowDuplicatesModal(true); }}>
              <Copy size={14} /> Duplikate
            </button>
            <button style={S.actionBtnSecondary} onClick={() => setShowSegmentsPanel(!showSegmentsPanel)}>
              <Layers size={14} /> Segmente
            </button>
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
                <div style={S.statLabel}>E-Mail</div>
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
                <div style={S.statLabel}>Telefon</div>
              </div>
            </div>
          </div>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: `${T.accent}15`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <BarChart3 size={18} style={{ color: T.accent }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.average_score?.toFixed(0) || 0}</div>
                <div style={S.statLabel}>Ø Score</div>
              </div>
            </div>
          </div>
          <div style={S.statCard}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: `${T.success}15`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Activity size={18} style={{ color: T.success }} />
              </div>
              <div>
                <div style={S.statValue}>{stats.recent_activities_7d || 0}</div>
                <div style={S.statLabel}>Aktivitäten (7T)</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Segments Panel ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {showSegmentsPanel && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            style={{ overflow: "hidden", marginBottom: 16 }}
          >
            <Card style={{ padding: 0 }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Layers size={16} style={{ color: T.accent }} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Segmente</span>
                  <Badge variant="default">{segments.length}</Badge>
                </div>
                <button style={{ ...S.filterBtn, padding: "6px 10px" }} onClick={() => setShowSegmentsPanel(false)}>
                  <X size={14} />
                </button>
              </div>
              {segments.length === 0 ? (
                <div style={{ padding: 20, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                  Noch keine Segmente erstellt. Setzen Sie Filter und speichern Sie sie als Segment.
                </div>
              ) : (
                <div style={{ maxHeight: 200, overflowY: "auto" }}>
                  {segments.map(seg => (
                    <div
                      key={seg.id}
                      style={{
                        ...S.segmentSidebar,
                        background: activeSegment?.id === seg.id ? T.accentDim : "transparent",
                      }}
                      onClick={() => {
                        if (activeSegment?.id === seg.id) {
                          setActiveSegment(null);
                          resetFilters();
                        } else {
                          setActiveSegment(seg);
                          // Apply segment filters
                          if (seg.filter_json) {
                            if (seg.filter_json.lifecycle_stage) setFilterLifecycle(seg.filter_json.lifecycle_stage);
                            if (seg.filter_json.source) setFilterSource(seg.filter_json.source);
                            if (seg.filter_json.tags) setFilterTags(seg.filter_json.tags);
                            if (seg.filter_json.company) setFilterCompany(seg.filter_json.company);
                          }
                          setPage(1);
                        }
                      }}
                    >
                      <FolderOpen size={14} style={{ color: activeSegment?.id === seg.id ? T.accent : T.textDim }} />
                      <span style={{ flex: 1, fontWeight: activeSegment?.id === seg.id ? 700 : 500, color: activeSegment?.id === seg.id ? T.accent : T.text }}>{seg.name}</span>
                      <Badge variant="default">{seg.contact_count}</Badge>
                      {isAdmin && (
                        <button
                          style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: T.textDim }}
                          onClick={(e) => { e.stopPropagation(); handleDeleteSegment(seg.id); }}
                        >
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {isAdmin && (
                <div style={{ padding: "12px 18px", borderTop: `1px solid ${T.border}`, display: "flex", gap: 8 }}>
                  <input
                    style={{ ...S.formInput, flex: 1, padding: "7px 10px" }}
                    placeholder="Neues Segment..."
                    value={newSegmentName}
                    onChange={(e) => setNewSegmentName(e.target.value)}
                  />
                  <button
                    style={{ ...S.actionBtn, opacity: newSegmentName.trim() ? 1 : 0.5, padding: "7px 12px" }}
                    disabled={!newSegmentName.trim()}
                    onClick={handleCreateSegment}
                  >
                    <Plus size={14} /> Speichern
                  </button>
                </div>
              )}
            </Card>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bulk Actions Bar ────────────────────────────────────────────── */}
      <AnimatePresence>
        {selectedIds.size > 0 && isAdmin && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
          >
            <div style={S.bulkBar}>
              <CheckCircle2 size={16} style={{ color: T.accent }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.accent }}>{selectedIds.size} ausgewählt</span>
              <div style={{ flex: 1 }} />
              <button style={{ ...S.actionBtnSecondary, padding: "6px 12px" }} onClick={() => setShowBulkModal(true)}>
                <Edit3 size={13} /> Bulk-Bearbeiten
              </button>
              <button style={{ ...S.actionBtnDanger, padding: "6px 12px" }} onClick={() => handleDelete(Array.from(selectedIds))}>
                <Trash2 size={13} /> Löschen
              </button>
              <button style={{ ...S.filterBtn, padding: "6px 10px" }} onClick={() => setSelectedIds(new Set())}>
                <X size={13} /> Abbrechen
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

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
            style={{ ...S.filterBtn, ...(showFilters || activeFilterCount > 0 ? { borderColor: T.accent, color: T.accent } : {}) }}
            onClick={() => setShowFilters(!showFilters)}
          >
            <ListFilter size={14} /> Filter {activeFilterCount > 0 && <Badge variant="accent">{activeFilterCount}</Badge>} {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          <div style={{ position: "relative" }}>
            <button
              style={S.filterBtn}
              onClick={() => setShowColumnPicker(!showColumnPicker)}
            >
              <Columns3 size={14} /> Spalten
            </button>
            {showColumnPicker && (
              <div style={S.dropdown}>
                <div style={{ padding: "10px 14px", borderBottom: `1px solid ${T.border}`, fontSize: 12, fontWeight: 700, color: T.textMuted }}>Sichtbare Spalten</div>
                {columns.map(col => (
                  <label
                    key={col.key}
                    style={{ ...S.dropdownItem, cursor: "pointer" }}
                    onClick={() => toggleColumn(col.key)}
                  >
                    <input
                      type="checkbox"
                      checked={col.visible}
                      onChange={() => toggleColumn(col.key)}
                      style={{ accentColor: T.accent }}
                    />
                    {col.label}
                  </label>
                ))}
                <div style={{ padding: "8px 14px", borderTop: `1px solid ${T.border}` }}>
                  <button style={{ ...S.filterBtn, width: "100%", justifyContent: "center", padding: "6px" }} onClick={() => setShowColumnPicker(false)}>
                    Schließen
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Extended Filter Row ──────────────────────────────────────── */}
        <AnimatePresence>
          {showFilters && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              style={{ overflow: "hidden", paddingTop: 12 }}
            >
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                <div>
                  <label style={S.formLabel}>Lifecycle-Phase</label>
                  <select style={S.formSelect} value={filterLifecycle} onChange={(e) => { setFilterLifecycle(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Quelle</label>
                  <select style={S.formSelect} value={filterSource} onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    {Object.entries(SOURCE_LABELS).map(([key, label]) => (
                      <option key={key} value={key}>{label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>E-Mail vorhanden</label>
                  <select style={S.formSelect} value={filterHasEmail} onChange={(e) => { setFilterHasEmail(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    <option value="yes">Ja</option>
                    <option value="no">Nein</option>
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Telefon vorhanden</label>
                  <select style={S.formSelect} value={filterHasPhone} onChange={(e) => { setFilterHasPhone(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    <option value="yes">Ja</option>
                    <option value="no">Nein</option>
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Firma</label>
                  <input style={S.formInput} placeholder="Firma filtern..." value={filterCompany} onChange={(e) => { setFilterCompany(e.target.value); setPage(1); }} />
                </div>
                <div>
                  <label style={S.formLabel}>Score min</label>
                  <input style={S.formInput} type="number" placeholder="0" value={filterScoreMin} onChange={(e) => { setFilterScoreMin(e.target.value); setPage(1); }} />
                </div>
                <div>
                  <label style={S.formLabel}>Score max</label>
                  <input style={S.formInput} type="number" placeholder="100" value={filterScoreMax} onChange={(e) => { setFilterScoreMax(e.target.value); setPage(1); }} />
                </div>
                <div>
                  <label style={S.formLabel}>Tags</label>
                  <select
                    style={S.formSelect}
                    value=""
                    onChange={(e) => {
                      if (e.target.value && !filterTags.includes(e.target.value)) {
                        setFilterTags(prev => [...prev, e.target.value]);
                        setPage(1);
                      }
                    }}
                  >
                    <option value="">Tag hinzufügen...</option>
                    {allTags.filter(t => !filterTags.includes(t.name)).map(t => (
                      <option key={t.id} value={t.name}>{t.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              {filterTags.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                  {filterTags.map(tag => (
                    <span key={tag} style={{ ...S.tagChip, background: `${T.accent}22`, color: T.accent }}>
                      <Tag size={10} /> {tag}
                      <button style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 0, marginLeft: 4 }} onClick={() => setFilterTags(prev => prev.filter(t => t !== tag))}>
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                {activeFilterCount > 0 && (
                  <button style={{ ...S.filterBtn, color: T.danger }} onClick={resetFilters}>
                    <RotateCcw size={12} /> Filter zurücksetzen
                  </button>
                )}
                {activeFilterCount > 0 && isAdmin && (
                  <button style={{ ...S.filterBtn, color: T.accent }} onClick={() => setShowSegmentsPanel(true)}>
                    <Save size={12} /> Als Segment speichern
                  </button>
                )}
              </div>
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
                    {visibleColumns.map(col => (
                      <th key={col.key} style={S.th}>
                        {["name", "lifecycle_stage", "created_at", "score"].includes(col.key) ? (
                          <button
                            onClick={() => handleSort(col.key === "name" ? "last_name" : col.key)}
                            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", display: "flex", alignItems: "center", gap: 4, fontSize: "inherit", fontWeight: "inherit", textTransform: "inherit" as any, letterSpacing: "inherit" }}
                          >
                            {col.label} <ArrowUpDown size={12} />
                          </button>
                        ) : col.label}
                      </th>
                    ))}
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
                        {visibleColumns.map(col => (
                          <td key={col.key} style={S.td}>
                            {col.key === "name" && (
                              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <div style={{ ...S.avatar, background: `${avatarBg}22`, color: avatarBg }}>
                                  {getInitials(c.first_name, c.last_name)}
                                </div>
                                <div>
                                  <div style={{ fontWeight: 600, fontSize: 13 }}>{c.full_name}</div>
                                  {c.job_title && <div style={{ fontSize: 11, color: T.textDim }}>{c.job_title}</div>}
                                </div>
                              </div>
                            )}
                            {col.key === "email" && (
                              <span style={{ color: c.email ? T.text : T.textDim, fontSize: 12 }}>
                                {c.email || "–"}
                              </span>
                            )}
                            {col.key === "phone" && (
                              <span style={{ color: c.phone ? T.text : T.textDim, fontSize: 12 }}>
                                {c.phone || "–"}
                              </span>
                            )}
                            {col.key === "company" && (
                              <span style={{ fontSize: 12 }}>{c.company || "–"}</span>
                            )}
                            {col.key === "lifecycle_stage" && (
                              <Badge variant={lc.variant}>{lc.label}</Badge>
                            )}
                            {col.key === "source" && (
                              <span style={{ fontSize: 12, color: T.textMuted }}>{SOURCE_LABELS[c.source] || c.source}</span>
                            )}
                            {col.key === "tags" && (
                              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                                {(c.tags || []).slice(0, 3).map(tag => (
                                  <span key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}22`, color: tag.color || T.accent }}>
                                    {tag.name}
                                  </span>
                                ))}
                                {(c.tags || []).length > 3 && (
                                  <span style={{ ...S.tagChip, background: T.surfaceAlt, color: T.textDim }}>+{c.tags.length - 3}</span>
                                )}
                              </div>
                            )}
                            {col.key === "score" && (
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <div style={{ width: 40, height: 4, borderRadius: 2, background: T.border, overflow: "hidden" }}>
                                  <div style={{ width: `${c.score}%`, height: "100%", borderRadius: 2, background: c.score >= 70 ? T.success : c.score >= 40 ? T.warning : T.danger }} />
                                </div>
                                <span style={{ fontSize: 12, fontWeight: 600 }}>{c.score}</span>
                              </div>
                            )}
                            {col.key === "gender" && (
                              <span style={{ fontSize: 12 }}>{c.gender === "male" ? "M" : c.gender === "female" ? "W" : c.gender === "diverse" ? "D" : "–"}</span>
                            )}
                            {col.key === "created_at" && (
                              <span style={{ fontSize: 12, color: T.textMuted }}>{formatDate(c.created_at)}</span>
                            )}
                          </td>
                        ))}
                        <td style={S.td} onClick={(e) => e.stopPropagation()}>
                          <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4 }} onClick={() => openDetail(c)}>
                            <Eye size={14} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div style={S.paginationRow}>
              <span style={{ fontSize: 12, color: T.textMuted, paddingLeft: 14 }}>
                Seite {page} von {totalPages} ({total} Kontakte)
              </span>
              <div style={{ display: "flex", gap: 6, paddingRight: 14 }}>
                <button style={{ ...S.pageBtn, opacity: page <= 1 ? 0.4 : 1 }} disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  <ChevronLeft size={14} /> Zurück
                </button>
                <button style={{ ...S.pageBtn, opacity: page >= totalPages ? 0.4 : 1 }} disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
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
                  <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                    <Badge variant={LIFECYCLE_STAGES[selectedContact.lifecycle_stage]?.variant || "default"}>
                      {LIFECYCLE_STAGES[selectedContact.lifecycle_stage]?.label || selectedContact.lifecycle_stage}
                    </Badge>
                    <Badge variant="default">Score: {selectedContact.score}</Badge>
                    <Badge variant="default">{SOURCE_LABELS[selectedContact.source] || selectedContact.source}</Badge>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  {isAdmin && !isEditing && (
                    <button style={S.actionBtnSecondary} onClick={startInlineEdit}>
                      <Pencil size={14} /> Bearbeiten
                    </button>
                  )}
                  {isEditing && (
                    <>
                      <button style={S.actionBtnSuccess} onClick={saveInlineEdit}>
                        <Save size={14} /> Speichern
                      </button>
                      <button style={S.actionBtnSecondary} onClick={cancelInlineEdit}>
                        <X size={14} />
                      </button>
                    </>
                  )}
                  <button style={{ ...S.filterBtn, padding: "8px" }} onClick={closeDetail}>
                    <X size={16} />
                  </button>
                </div>
              </div>

              {/* Detail Tabs */}
              <div style={S.detailTabs}>
                {(["overview", "timeline", "notes", "tags"] as const).map((tab) => (
                  <button
                    key={tab}
                    style={{ ...S.detailTab, ...(detailTab === tab ? S.detailTabActive : {}) }}
                    onClick={() => setDetailTab(tab)}
                  >
                    {tab === "overview" ? "Übersicht" : tab === "timeline" ? "Aktivitäten" : tab === "notes" ? "Notizen" : "Tags"}
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
                    {[
                      { icon: UserCircle, label: "Vorname", key: "first_name", value: selectedContact.first_name },
                      { icon: UserCircle, label: "Nachname", key: "last_name", value: selectedContact.last_name },
                      { icon: Mail, label: "E-Mail", key: "email", value: selectedContact.email },
                      { icon: Phone, label: "Telefon", key: "phone", value: selectedContact.phone },
                      { icon: Building2, label: "Firma", key: "company", value: selectedContact.company },
                      { icon: UserCircle, label: "Position", key: "job_title", value: selectedContact.job_title },
                      { icon: UserCircle, label: "Geschlecht", key: "gender", value: selectedContact.gender },
                      { icon: Calendar, label: "Geburtsdatum", key: "date_of_birth", value: selectedContact.date_of_birth },
                      { icon: Globe, label: "Sprache", key: "preferred_language", value: selectedContact.preferred_language },
                    ].map(field => {
                      const Icon = field.icon;
                      return (
                        <div key={field.key} style={S.fieldRow}>
                          <span style={S.fieldLabel}><Icon size={13} style={{ marginRight: 6, verticalAlign: "middle" }} />{field.label}</span>
                          {isEditing && !["date_of_birth"].includes(field.key) ? (
                            field.key === "gender" ? (
                              <select
                                style={{ ...S.inlineInput, width: "auto" }}
                                value={editData[field.key] || ""}
                                onChange={(e) => setEditData(prev => ({ ...prev, [field.key]: e.target.value }))}
                              >
                                <option value="">–</option>
                                <option value="male">Männlich</option>
                                <option value="female">Weiblich</option>
                                <option value="diverse">Divers</option>
                              </select>
                            ) : field.key === "preferred_language" ? (
                              <select
                                style={{ ...S.inlineInput, width: "auto" }}
                                value={editData[field.key] || "de"}
                                onChange={(e) => setEditData(prev => ({ ...prev, [field.key]: e.target.value }))}
                              >
                                <option value="de">Deutsch</option>
                                <option value="en">Englisch</option>
                                <option value="fr">Französisch</option>
                                <option value="es">Spanisch</option>
                              </select>
                            ) : (
                              <input
                                style={S.inlineInput}
                                value={editData[field.key] || ""}
                                onChange={(e) => setEditData(prev => ({ ...prev, [field.key]: e.target.value }))}
                              />
                            )
                          ) : (
                            <span style={S.fieldValue}>
                              {field.key === "gender" ? (field.value === "male" ? "Männlich" : field.value === "female" ? "Weiblich" : field.value === "diverse" ? "Divers" : "–") :
                               field.key === "date_of_birth" ? formatDate(field.value) :
                               field.value || "–"}
                            </span>
                          )}
                        </div>
                      );
                    })}

                    {isEditing && (
                      <>
                        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, marginTop: 24, textTransform: "uppercase", letterSpacing: "0.04em" }}>Lifecycle</h3>
                        <select
                          style={{ ...S.formSelect, maxWidth: 200 }}
                          value={editData.lifecycle_stage || selectedContact.lifecycle_stage}
                          onChange={(e) => setEditData(prev => ({ ...prev, lifecycle_stage: e.target.value }))}
                        >
                          {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (
                            <option key={key} value={key}>{label}</option>
                          ))}
                        </select>
                      </>
                    )}

                    <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, marginTop: 24, textTransform: "uppercase", letterSpacing: "0.04em" }}>Einwilligungen (DSGVO)</h3>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                      {[
                        { label: "E-Mail", key: "consent_email", value: selectedContact.consent_email },
                        { label: "SMS", key: "consent_sms", value: selectedContact.consent_sms },
                        { label: "Telefon", key: "consent_phone", value: selectedContact.consent_phone },
                        { label: "WhatsApp", key: "consent_whatsapp", value: selectedContact.consent_whatsapp },
                      ].map((c) => (
                        <div
                          key={c.label}
                          style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}`, cursor: isEditing ? "pointer" : "default" }}
                          onClick={() => {
                            if (isEditing) setEditData(prev => ({ ...prev, [c.key]: !prev[c.key] }));
                          }}
                        >
                          {(isEditing ? editData[c.key] : c.value) ? <Check size={14} style={{ color: T.success }} /> : <X size={14} style={{ color: T.danger }} />}
                          <span style={{ fontSize: 12, color: T.text }}>{c.label}</span>
                        </div>
                      ))}
                    </div>

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
                    {/* Add Activity Button */}
                    {isAdmin && (
                      <div style={{ marginBottom: 16 }}>
                        {!showAddActivity ? (
                          <button style={S.actionBtnSecondary} onClick={() => setShowAddActivity(true)}>
                            <Plus size={14} /> Aktivität hinzufügen
                          </button>
                        ) : (
                          <div style={{ padding: 16, borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
                              <div>
                                <label style={S.formLabel}>Typ</label>
                                <select style={S.formSelect} value={newActivityType} onChange={(e) => setNewActivityType(e.target.value)}>
                                  <option value="custom">Benutzerdefiniert</option>
                                  <option value="call">Anruf</option>
                                  <option value="meeting">Meeting</option>
                                  <option value="email_sent">E-Mail gesendet</option>
                                  <option value="email_received">E-Mail empfangen</option>
                                  <option value="chat_message">Chat-Nachricht</option>
                                  <option value="note_added">Notiz</option>
                                </select>
                              </div>
                              <div>
                                <label style={S.formLabel}>Titel *</label>
                                <input style={S.formInput} value={newActivityTitle} onChange={(e) => setNewActivityTitle(e.target.value)} placeholder="Aktivitätstitel..." />
                              </div>
                            </div>
                            <div style={{ marginBottom: 10 }}>
                              <label style={S.formLabel}>Beschreibung</label>
                              <textarea style={{ ...S.formInput, minHeight: 60, resize: "vertical" }} value={newActivityDesc} onChange={(e) => setNewActivityDesc(e.target.value)} placeholder="Optional..." />
                            </div>
                            <div style={{ display: "flex", gap: 8 }}>
                              <button style={{ ...S.actionBtn, opacity: newActivityTitle.trim() ? 1 : 0.5 }} disabled={!newActivityTitle.trim()} onClick={handleAddActivity}>
                                <Check size={14} /> Speichern
                              </button>
                              <button style={S.actionBtnSecondary} onClick={() => { setShowAddActivity(false); setNewActivityTitle(""); setNewActivityDesc(""); }}>
                                Abbrechen
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

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
                ) : detailTab === "notes" ? (
                  /* ── Notes Tab ─────────────────────────────────────────── */
                  <div>
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
                          {editingNoteId === note.id ? (
                            <div>
                              <textarea
                                style={{ ...S.formInput, minHeight: 60, resize: "vertical" }}
                                value={editingNoteContent}
                                onChange={(e) => setEditingNoteContent(e.target.value)}
                              />
                              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                                <button style={{ ...S.actionBtn, padding: "5px 10px" }} onClick={() => handleUpdateNote(note.id)}>
                                  <Check size={12} /> Speichern
                                </button>
                                <button style={{ ...S.actionBtnSecondary, padding: "5px 10px" }} onClick={() => { setEditingNoteId(null); setEditingNoteContent(""); }}>
                                  Abbrechen
                                </button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <div style={{ fontSize: 13, color: T.text, whiteSpace: "pre-wrap", lineHeight: 1.5 }}>{note.content}</div>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8 }}>
                                <div style={{ fontSize: 11, color: T.textDim }}>
                                  {note.created_by_name && <span>{note.created_by_name} • </span>}
                                  {timeAgo(note.created_at)}
                                </div>
                                {isAdmin && (
                                  <div style={{ display: "flex", gap: 4 }}>
                                    <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4 }} onClick={() => handleTogglePin(note.id, note.is_pinned)} title={note.is_pinned ? "Lösen" : "Anpinnen"}>
                                      {note.is_pinned ? <PinOff size={12} /> : <Pin size={12} />}
                                    </button>
                                    <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4 }} onClick={() => { setEditingNoteId(note.id); setEditingNoteContent(note.content); }} title="Bearbeiten">
                                      <Pencil size={12} />
                                    </button>
                                    <button style={{ background: "none", border: "none", cursor: "pointer", color: T.danger, padding: 4 }} onClick={() => handleDeleteNote(note.id)} title="Löschen">
                                      <Trash2 size={12} />
                                    </button>
                                  </div>
                                )}
                              </div>
                            </>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                ) : (
                  /* ── Tags Tab ──────────────────────────────────────────── */
                  <div>
                    <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>Zugewiesene Tags</h3>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
                      {(selectedContact.tags || []).length === 0 ? (
                        <span style={{ fontSize: 13, color: T.textDim }}>Keine Tags zugewiesen</span>
                      ) : (
                        selectedContact.tags.map(tag => (
                          <span key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}22`, color: tag.color || T.accent, padding: "6px 12px" }}>
                            <Tag size={12} /> {tag.name}
                            {isAdmin && (
                              <button
                                style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 0, marginLeft: 6 }}
                                onClick={() => handleRemoveTagFromContact(tag.name)}
                              >
                                <X size={12} />
                              </button>
                            )}
                          </span>
                        ))
                      )}
                    </div>

                    {isAdmin && (
                      <>
                        <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>Tag hinzufügen</h3>
                        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                          <input
                            style={{ ...S.formInput, flex: 1 }}
                            placeholder="Tag-Name..."
                            value={newTagName}
                            onChange={(e) => setNewTagName(e.target.value)}
                            onKeyDown={(e) => { if (e.key === "Enter" && newTagName.trim()) handleAddTagToContact(newTagName); }}
                          />
                          <input
                            type="color"
                            value={newTagColor}
                            onChange={(e) => setNewTagColor(e.target.value)}
                            style={{ width: 40, height: 38, borderRadius: 8, border: `1px solid ${T.border}`, cursor: "pointer" }}
                          />
                          <button
                            style={{ ...S.actionBtn, opacity: newTagName.trim() ? 1 : 0.5 }}
                            disabled={!newTagName.trim()}
                            onClick={() => handleAddTagToContact(newTagName)}
                          >
                            <Plus size={14} />
                          </button>
                        </div>

                        {/* Quick-add from existing tags */}
                        {allTags.length > 0 && (
                          <>
                            <h3 style={{ fontSize: 13, fontWeight: 700, color: T.textMuted, marginBottom: 12, textTransform: "uppercase", letterSpacing: "0.04em" }}>Vorhandene Tags</h3>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              {allTags
                                .filter(t => !(selectedContact.tags || []).some(ct => ct.name === t.name))
                                .map(tag => (
                                  <button
                                    key={tag.id}
                                    style={{ ...S.tagChip, background: `${tag.color || T.accent}15`, color: tag.color || T.accent, cursor: "pointer", border: `1px dashed ${tag.color || T.accent}40`, padding: "5px 10px" }}
                                    onClick={() => handleAddTagToContact(tag.name)}
                                  >
                                    <Plus size={10} /> {tag.name}
                                    {tag.contact_count != null && <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 4 }}>({tag.contact_count})</span>}
                                  </button>
                                ))}
                            </div>
                          </>
                        )}
                      </>
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
        onClose={() => { setShowCreateModal(false); setShowDuplicateWarning(false); setFormDuplicates([]); }}
        footer={
          <>
            <button style={S.actionBtnSecondary} onClick={() => { setShowCreateModal(false); setShowDuplicateWarning(false); }}>Abbrechen</button>
            {showDuplicateWarning ? (
              <button style={{ ...S.actionBtn, background: T.warning }} onClick={() => handleCreate(true)} disabled={formLoading}>
                <AlertTriangle size={14} /> Trotzdem erstellen
              </button>
            ) : (
              <button style={{ ...S.actionBtn, opacity: formLoading ? 0.6 : 1 }} onClick={() => handleCreate(false)} disabled={formLoading}>
                {formLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Plus size={14} />}
                Erstellen
              </button>
            )}
          </>
        }
      >
        {showDuplicateWarning && formDuplicates.length > 0 && (
          <div style={{ padding: "12px 16px", borderRadius: 10, background: `${T.warning}15`, border: `1px solid ${T.warning}40`, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <AlertTriangle size={16} style={{ color: T.warning }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: T.warning }}>Mögliche Duplikate gefunden!</span>
            </div>
            {formDuplicates.map((dup, i) => (
              <div key={i} style={{ padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt, marginBottom: 6, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{dup.contact.full_name}</div>
                  <div style={{ fontSize: 11, color: T.textDim }}>{dup.contact.email || "–"} • {matchReasonLabel(dup.match_reason)}</div>
                </div>
                <Badge variant={dup.confidence >= 0.8 ? "danger" : "warning"}>{confidenceLabel(dup.confidence)}</Badge>
              </div>
            ))}
          </div>
        )}
        <ContactForm formData={formData} setFormData={setFormData} formError={formError} allTags={allTags} />
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
        <ContactForm formData={formData} setFormData={setFormData} formError={formError} isEdit allTags={allTags} />
      </Modal>

      {/* ── Bulk Update Modal ───────────────────────────────────────────── */}
      <Modal
        open={showBulkModal}
        title="Bulk-Bearbeitung"
        subtitle={`${selectedIds.size} Kontakte ausgewählt`}
        onClose={() => setShowBulkModal(false)}
        footer={
          <>
            <button style={S.actionBtnSecondary} onClick={() => setShowBulkModal(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: bulkLoading ? 0.6 : 1 }} onClick={handleBulkUpdate} disabled={bulkLoading}>
              {bulkLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Check size={14} />}
              Anwenden
            </button>
          </>
        }
      >
        <div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Lifecycle-Phase ändern</label>
            <select style={S.formSelect} value={bulkLifecycle} onChange={(e) => setBulkLifecycle(e.target.value)}>
              <option value="">– Nicht ändern –</option>
              {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Tags hinzufügen (kommagetrennt)</label>
            <input style={S.formInput} value={bulkAddTags} onChange={(e) => setBulkAddTags(e.target.value)} placeholder="VIP, Premium, ..." />
          </div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Tags entfernen (kommagetrennt)</label>
            <input style={S.formInput} value={bulkRemoveTags} onChange={(e) => setBulkRemoveTags(e.target.value)} placeholder="Alt, Inaktiv, ..." />
          </div>
          <div style={{ padding: "10px 14px", borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}`, fontSize: 12, color: T.textMuted }}>
            <strong>Hinweis:</strong> Nur ausgefüllte Felder werden geändert. Leere Felder werden übersprungen.
          </div>
        </div>
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
            Spalten: first_name, last_name, email, phone, company, lifecycle_stage, tags
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

      {/* ── Duplicates Modal ────────────────────────────────────────────── */}
      <Modal
        open={showDuplicatesModal}
        title="Duplikat-Erkennung"
        subtitle="Mögliche doppelte Kontakte"
        onClose={() => setShowDuplicatesModal(false)}
      >
        {duplicatesLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Loader2 size={24} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
            <p style={{ color: T.textMuted, fontSize: 13, marginTop: 12 }}>Duplikate werden gesucht...</p>
          </div>
        ) : duplicateGroups.length === 0 ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <CheckCircle2 size={40} style={{ color: T.success, marginBottom: 12 }} />
            <p style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Keine Duplikate gefunden</p>
            <p style={{ fontSize: 12, color: T.textDim, marginTop: 4 }}>Alle Kontakte sind einzigartig.</p>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: 16, padding: "10px 14px", borderRadius: 8, background: `${T.warning}15`, border: `1px solid ${T.warning}40`, display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={16} style={{ color: T.warning }} />
              <span style={{ fontSize: 13, color: T.warning, fontWeight: 600 }}>{duplicateGroups.length} Duplikat-Gruppe(n) gefunden</span>
            </div>
            {duplicateGroups.map((group, gi) => (
              <div key={gi} style={{ marginBottom: 16, padding: 16, borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <Copy size={14} style={{ color: T.warning }} />
                  <span style={{ fontSize: 13, fontWeight: 700 }}>{group.match_type}: {group.match_value}</span>
                  <Badge variant={group.confidence >= 0.8 ? "danger" : "warning"}>{confidenceLabel(group.confidence)}</Badge>
                </div>
                {group.contacts.map(c => (
                  <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", borderRadius: 8, background: T.surface, marginBottom: 6, border: `1px solid ${T.border}` }}>
                    <div style={{ ...S.avatar, width: 30, height: 30, fontSize: 11, background: `${getAvatarColor(c.full_name)}22`, color: getAvatarColor(c.full_name) }}>
                      {getInitials(c.first_name, c.last_name)}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{c.full_name}</div>
                      <div style={{ fontSize: 11, color: T.textDim }}>{c.email || "–"} • {c.phone || "–"}</div>
                    </div>
                    <button style={{ ...S.actionBtnSecondary, padding: "4px 8px" }} onClick={() => openDetail(c)}>
                      <Eye size={12} />
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* ── Spin Animation ──────────────────────────────────────────────── */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// ── Contact Form Sub-Component ───────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════════

function ContactForm({
  formData,
  setFormData,
  formError,
  isEdit = false,
  allTags = [],
}: {
  formData: any;
  setFormData: (fn: any) => void;
  formError: string;
  isEdit?: boolean;
  allTags?: ContactTag[];
}) {
  const update = (field: string, value: any) => setFormData((prev: any) => ({ ...prev, [field]: value }));

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
        <div style={S.formGroup}>
          <label style={S.formLabel}>Geburtsdatum</label>
          <input style={S.formInput} type="date" value={formData.date_of_birth} onChange={(e) => update("date_of_birth", e.target.value)} />
        </div>
        <div style={S.formGroup}>
          <label style={S.formLabel}>Sprache</label>
          <select style={S.formSelect} value={formData.preferred_language} onChange={(e) => update("preferred_language", e.target.value)}>
            <option value="de">Deutsch</option>
            <option value="en">Englisch</option>
            <option value="fr">Französisch</option>
            <option value="es">Spanisch</option>
          </select>
        </div>
      </div>

      {/* DSGVO Consent */}
      <h4 style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, marginTop: 16, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.04em" }}>Einwilligungen (DSGVO)</h4>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 16 }}>
        {[
          { label: "E-Mail-Marketing", key: "consent_email" },
          { label: "SMS-Marketing", key: "consent_sms" },
          { label: "Telefonkontakt", key: "consent_phone" },
          { label: "WhatsApp", key: "consent_whatsapp" },
        ].map(c => (
          <label key={c.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}`, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={formData[c.key] || false}
              onChange={(e) => update(c.key, e.target.checked)}
              style={{ accentColor: T.accent }}
            />
            <span style={{ fontSize: 12, color: T.text }}>{c.label}</span>
          </label>
        ))}
      </div>

      {/* Tags */}
      <div style={S.formGroup}>
        <label style={S.formLabel}>Tags (kommagetrennt)</label>
        <input style={S.formInput} value={formData.tags} onChange={(e) => update("tags", e.target.value)} placeholder="VIP, Premium, Newsletter" />
        {allTags.length > 0 && (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
            {allTags.slice(0, 10).map(tag => (
              <button
                key={tag.id}
                type="button"
                style={{ ...S.tagChip, background: `${tag.color || T.accent}15`, color: tag.color || T.accent, cursor: "pointer", border: "none", padding: "3px 8px" }}
                onClick={() => {
                  const current = formData.tags ? formData.tags.split(",").map((t: string) => t.trim()).filter(Boolean) : [];
                  if (!current.includes(tag.name)) {
                    update("tags", [...current, tag.name].join(", "));
                  }
                }}
              >
                <Plus size={9} /> {tag.name}
              </button>
            ))}
          </div>
        )}
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
