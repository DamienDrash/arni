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
  AlertTriangle, CheckCircle2, Link2, Layers, FolderOpen, ArrowRight,
  GitMerge, Workflow, Database, FileText, MapPin, LayoutGrid, Sliders,
  CircleDot, ArrowLeftRight, ToggleLeft, Type, ListChecks, CalendarDays,
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
  id: number; tenant_id: number; first_name: string; last_name: string; full_name: string;
  email?: string | null; phone?: string | null; company?: string | null; job_title?: string | null;
  date_of_birth?: string | null; gender?: string | null; preferred_language?: string | null;
  avatar_url?: string | null; lifecycle_stage: string; source: string; source_id?: string | null;
  consent_email?: boolean; consent_sms?: boolean; consent_phone?: boolean; consent_whatsapp?: boolean;
  score: number; tags: ContactTag[]; custom_fields: Record<string, any>;
  created_at: string; updated_at: string; deleted_at?: string | null;
};

type ContactListResponse = { items: Contact[]; total: number; page: number; page_size: number; total_pages: number };

type ContactStats = {
  total: number; lifecycle_distribution: Record<string, number>; source_distribution: Record<string, number>;
  with_email: number; with_phone: number; email_coverage: number; phone_coverage: number;
  average_score: number; recent_activities_7d: number; tag_count: number;
};

type NoteItem = { id: number; contact_id: number; content: string; is_pinned: boolean; created_by_id?: number; created_at: string; updated_at: string };
type ActivityItem = { id: number; contact_id: number; activity_type: string; description: string; metadata?: any; created_at: string };
type DuplicateGroup = { match_type: string; match_value: string; confidence: number; contacts: Contact[] };
type Segment = { id: number; name: string; description?: string; filter_json?: any; filter_groups?: any[]; group_connector?: string; is_dynamic: boolean; contact_count: number; created_at: string };
type CustomFieldDef = { id: number; tenant_id: number; field_name: string; field_type: string; field_label: string; is_required: boolean; field_options?: any; display_order: number; created_at: string };

// ── Segment Builder Types ──
type SegmentRule = { field: string; operator: string; value: string };
type SegmentRuleGroup = { connector: "AND" | "OR"; rules: SegmentRule[] };

// ── Import V2 Types ──
type ImportMapping = { csv_column: string; contact_field: string; is_key: boolean };
type ImportPreview = { total_rows: number; columns: string[]; sample_rows: Record<string, string>[]; suggested_mappings: ImportMapping[] };

// ── Lifecycle Config Types ──
type LifecycleConfig = { id?: number; tenant_id?: number; stages: { name: string; label: string; color: string; order: number }[]; transitions: { from_stage: string; to_stage: string; trigger?: string }[] };

// ── Constants ────────────────────────────────────────────────────────────────

const LIFECYCLE_STAGES: Record<string, { label: string; color: string; icon: any }> = {
  subscriber: { label: "Subscriber", color: "#6366f1", icon: UserPlus },
  lead: { label: "Lead", color: "#f59e0b", icon: Target },
  opportunity: { label: "Opportunity", color: "#8b5cf6", icon: Sparkles },
  customer: { label: "Kunde", color: "#10b981", icon: TrendingUp },
  evangelist: { label: "Evangelist", color: "#ec4899", icon: Star },
  churned: { label: "Abgewandert", color: "#ef4444", icon: RotateCcw },
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "Manuell", magicline: "Magicline", import: "Import", api: "API",
  website: "Website", referral: "Empfehlung", social: "Social Media",
};

const SEGMENT_FIELDS = [
  { value: "lifecycle_stage", label: "Lifecycle-Phase", type: "select", options: Object.keys(LIFECYCLE_STAGES) },
  { value: "source", label: "Quelle", type: "select", options: Object.keys(SOURCE_LABELS) },
  { value: "company", label: "Firma", type: "text" },
  { value: "score", label: "Score", type: "number" },
  { value: "email", label: "E-Mail", type: "text" },
  { value: "phone", label: "Telefon", type: "text" },
  { value: "gender", label: "Geschlecht", type: "select", options: ["male", "female", "diverse"] },
  { value: "preferred_language", label: "Sprache", type: "select", options: ["de", "en", "fr", "es"] },
  { value: "tags", label: "Tags", type: "text" },
  { value: "created_at", label: "Erstellt am", type: "date" },
  { value: "consent_email", label: "E-Mail-Einwilligung", type: "boolean" },
  { value: "consent_sms", label: "SMS-Einwilligung", type: "boolean" },
];

const OPERATORS: Record<string, { label: string; value: string }[]> = {
  text: [
    { label: "enthält", value: "contains" }, { label: "ist gleich", value: "equals" },
    { label: "beginnt mit", value: "starts_with" }, { label: "endet mit", value: "ends_with" },
    { label: "ist leer", value: "is_empty" }, { label: "ist nicht leer", value: "is_not_empty" },
  ],
  number: [
    { label: "=", value: "equals" }, { label: ">", value: "greater_than" },
    { label: "<", value: "less_than" }, { label: ">=", value: "greater_equal" },
    { label: "<=", value: "less_equal" }, { label: "zwischen", value: "between" },
  ],
  select: [
    { label: "ist", value: "equals" }, { label: "ist nicht", value: "not_equals" },
    { label: "ist einer von", value: "in" },
  ],
  date: [
    { label: "vor", value: "before" }, { label: "nach", value: "after" },
    { label: "zwischen", value: "between" }, { label: "letzte X Tage", value: "last_days" },
  ],
  boolean: [
    { label: "ist wahr", value: "is_true" }, { label: "ist falsch", value: "is_false" },
  ],
};

const CONTACT_IMPORT_FIELDS = [
  { value: "first_name", label: "Vorname" }, { value: "last_name", label: "Nachname" },
  { value: "email", label: "E-Mail" }, { value: "phone", label: "Telefon" },
  { value: "company", label: "Firma" }, { value: "job_title", label: "Position" },
  { value: "lifecycle_stage", label: "Lifecycle-Phase" }, { value: "source", label: "Quelle" },
  { value: "gender", label: "Geschlecht" }, { value: "date_of_birth", label: "Geburtsdatum" },
  { value: "preferred_language", label: "Sprache" }, { value: "tags", label: "Tags" },
  { value: "__skip__", label: "– Überspringen –" },
];

const CUSTOM_FIELD_TYPES = [
  { value: "text", label: "Text", icon: Type },
  { value: "number", label: "Zahl", icon: Hash },
  { value: "date", label: "Datum", icon: CalendarDays },
  { value: "select", label: "Auswahl", icon: ListChecks },
  { value: "boolean", label: "Ja/Nein", icon: ToggleLeft },
  { value: "url", label: "URL", icon: Link2 },
];

const PAGE_SIZE = 25;

// ── Styles ───────────────────────────────────────────────────────────────────

const S: Record<string, React.CSSProperties> = {
  page: { padding: "0 0 40px" },
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12, marginBottom: 16 },
  statCard: { background: T.surface, borderRadius: 14, padding: "16px 18px", border: `1px solid ${T.border}`, transition: "border-color .2s", cursor: "default" },
  statValue: { fontSize: 22, fontWeight: 800, color: T.text, lineHeight: 1.1 },
  statLabel: { fontSize: 11, color: T.textMuted, fontWeight: 600, marginTop: 2 },
  toolbar: { display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" as const },
  searchWrap: { position: "relative" as const, flex: 1, minWidth: 200 },
  searchIcon: { position: "absolute" as const, left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim },
  searchInput: { width: "100%", padding: "10px 12px 10px 36px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" },
  filterBtn: { display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontWeight: 600, cursor: "pointer", transition: "all .15s", whiteSpace: "nowrap" as const },
  actionBtn: { display: "flex", alignItems: "center", gap: 6, padding: "8px 16px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", transition: "opacity .15s", whiteSpace: "nowrap" as const },
  actionBtnSecondary: { display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 12, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" as const },
  actionBtnDanger: { display: "flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10, border: "none", background: T.danger, color: "#fff", fontSize: 12, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" as const },
  tableWrap: { overflowX: "auto" as const },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13 },
  th: { padding: "12px 14px", textAlign: "left" as const, fontWeight: 700, fontSize: 11, color: T.textMuted, textTransform: "uppercase" as const, letterSpacing: "0.04em", borderBottom: `2px solid ${T.border}`, cursor: "pointer", whiteSpace: "nowrap" as const, userSelect: "none" as const },
  td: { padding: "12px 14px", borderBottom: `1px solid ${T.border}`, verticalAlign: "middle" as const },
  avatar: { width: 34, height: 34, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 12, flexShrink: 0 },
  tagChip: { display: "inline-flex", alignItems: "center", gap: 4, padding: "3px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600, whiteSpace: "nowrap" as const },
  pagination: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px" },
  detailPanel: { position: "fixed" as const, top: 0, right: 0, width: 480, height: "100vh", background: T.surface, borderLeft: `1px solid ${T.border}`, zIndex: 1000, display: "flex", flexDirection: "column" as const, boxShadow: "-8px 0 30px rgba(0,0,0,.12)" },
  detailHeader: { padding: "20px 24px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "flex-start", gap: 14 },
  detailBody: { flex: 1, overflowY: "auto" as const, padding: "20px 24px" },
  detailTab: { padding: "10px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer", borderBottom: "2px solid transparent", color: T.textMuted, transition: "all .15s", whiteSpace: "nowrap" as const },
  detailTabActive: { color: T.accent, borderBottomColor: T.accent },
  formGroup: { marginBottom: 14 },
  formLabel: { display: "block", fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 5, textTransform: "uppercase" as const, letterSpacing: "0.04em" },
  formInput: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" },
  formSelect: { width: "100%", padding: "9px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none" },
  dropdown: { position: "absolute" as const, top: "100%", right: 0, marginTop: 6, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, boxShadow: "0 8px 30px rgba(0,0,0,.12)", zIndex: 100, minWidth: 200, maxHeight: 350, overflowY: "auto" as const },
  dropdownItem: { display: "flex", alignItems: "center", gap: 8, padding: "8px 14px", fontSize: 12, color: T.text, cursor: "pointer" },
  bulkBar: { display: "flex", alignItems: "center", gap: 12, padding: "12px 18px", borderRadius: 12, background: T.accentDim, border: `1px solid ${T.accent}30`, marginBottom: 12 },
  segmentSidebar: { display: "flex", alignItems: "center", gap: 10, padding: "10px 18px", cursor: "pointer", transition: "background .15s", borderBottom: `1px solid ${T.border}` },
  // Phase 3 specific styles
  ruleRow: { display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}`, marginBottom: 8 },
  ruleGroupBox: { padding: 16, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surface, marginBottom: 12 },
  connectorBadge: { display: "inline-flex", alignItems: "center", justifyContent: "center", padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 800, cursor: "pointer", transition: "all .15s" },
  wizardStep: { display: "flex", alignItems: "center", gap: 8, padding: "10px 16px", borderRadius: 10, fontSize: 12, fontWeight: 600 },
  wizardStepActive: { background: T.accentDim, color: T.accent, border: `1px solid ${T.accent}40` },
  wizardStepDone: { background: `${T.success}15`, color: T.success, border: `1px solid ${T.success}40` },
  wizardStepPending: { background: T.surfaceAlt, color: T.textDim, border: `1px solid ${T.border}` },
  mappingRow: { display: "grid", gridTemplateColumns: "1fr 40px 1fr 60px", gap: 8, alignItems: "center", padding: "8px 0", borderBottom: `1px solid ${T.border}` },
  previewTable: { width: "100%", borderCollapse: "collapse" as const, fontSize: 11 },
  previewTh: { padding: "8px 10px", textAlign: "left" as const, fontWeight: 700, fontSize: 10, color: T.textMuted, textTransform: "uppercase" as const, borderBottom: `2px solid ${T.border}` },
  previewTd: { padding: "6px 10px", borderBottom: `1px solid ${T.border}`, fontSize: 11, color: T.text, maxWidth: 150, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  mergeCard: { padding: 16, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt, marginBottom: 12 },
  mergeFieldRow: { display: "grid", gridTemplateColumns: "120px 1fr 40px 1fr", gap: 8, alignItems: "center", padding: "6px 0", borderBottom: `1px solid ${T.border}` },
  progressBar: { width: "100%", height: 8, borderRadius: 4, background: T.surfaceAlt, overflow: "hidden" },
  progressFill: { height: "100%", borderRadius: 4, background: T.accent, transition: "width .3s ease" },
};

// ── Helper Functions ─────────────────────────────────────────────────────────

const AVATAR_COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#8b5cf6", "#ef4444", "#06b6d4", "#f97316"];
const getAvatarColor = (name: string) => AVATAR_COLORS[Math.abs([...name].reduce((a, c) => a + c.charCodeAt(0), 0)) % AVATAR_COLORS.length];
const getInitials = (first: string, last: string) => `${first?.[0] || ""}${last?.[0] || ""}`.toUpperCase();
const fmtDate = (d: string) => { try { return new Date(d).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }); } catch { return "–"; } };
const fmtDateTime = (d: string) => { try { return new Date(d).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); } catch { return "–"; } };
const confidenceLabel = (c: number) => c >= 0.9 ? "Sehr hoch" : c >= 0.7 ? "Hoch" : c >= 0.5 ? "Mittel" : "Niedrig";
const matchReasonLabel = (r: string) => ({ email: "E-Mail", phone: "Telefon", name: "Name", name_company: "Name+Firma" }[r] || r);

const ACTIVITY_ICONS: Record<string, any> = {
  email_sent: Mail, email_opened: Mail, call: Phone, meeting: Calendar, note_added: StickyNote,
  tag_added: Tag, tag_removed: Tag, lifecycle_changed: TrendingUp, created: UserPlus,
  updated: Edit3, merged: GitMerge, imported: Upload, default: Activity,
};

const getActivityIcon = (type: string) => ACTIVITY_ICONS[type] || ACTIVITY_ICONS.default;


// ── Main Component ───────────────────────────────────────────────────────────

export default function ContactsPage() {
  const { role } = usePermissions();
  const isAdmin = role === "system_admin" || role === "tenant_admin";
  const searchTimeout = useRef<any>(null);

  // ── State ──────────────────────────────────────────────────────────────
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [filterLifecycle, setFilterLifecycle] = useState("");
  const [filterSource, setFilterSource] = useState("");
  const [filterTags, setFilterTags] = useState<string[]>([]);
  const [filterCompany, setFilterCompany] = useState("");
  const [filterScoreMin, setFilterScoreMin] = useState("");
  const [filterScoreMax, setFilterScoreMax] = useState("");
  const [filterHasEmail, setFilterHasEmail] = useState("");
  const [filterHasPhone, setFilterHasPhone] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");

  // Stats & Tags
  const [stats, setStats] = useState<ContactStats | null>(null);
  const [allTags, setAllTags] = useState<ContactTag[]>([]);

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [detailTab, setDetailTab] = useState<"overview" | "activities" | "notes" | "tags" | "custom">("overview");

  // Detail data
  const [detailNotes, setDetailNotes] = useState<NoteItem[]>([]);
  const [detailActivities, setDetailActivities] = useState<ActivityItem[]>([]);
  const [newNote, setNewNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<number | null>(null);
  const [editingNoteContent, setEditingNoteContent] = useState("");
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("#6366f1");

  // Inline edit
  const [inlineEditing, setInlineEditing] = useState(false);
  const [inlineData, setInlineData] = useState<Record<string, any>>({});

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showDuplicatesModal, setShowDuplicatesModal] = useState(false);
  const [showSegmentsPanel, setShowSegmentsPanel] = useState(false);
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const [showSegmentBuilder, setShowSegmentBuilder] = useState(false);
  const [showMergeWizard, setShowMergeWizard] = useState(false);
  const [showCustomFieldsAdmin, setShowCustomFieldsAdmin] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);

  // Form
  const [formData, setFormData] = useState<any>({
    first_name: "", last_name: "", email: "", phone: "", company: "",
    job_title: "", lifecycle_stage: "subscriber", source: "manual",
    gender: "", notes: "", date_of_birth: "", preferred_language: "de",
    consent_email: false, consent_sms: false, consent_phone: false, consent_whatsapp: false,
    tags: "",
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);
  const [formDuplicates, setFormDuplicates] = useState<any[]>([]);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);

  // Bulk
  const [bulkLifecycle, setBulkLifecycle] = useState("");
  const [bulkAddTags, setBulkAddTags] = useState("");
  const [bulkRemoveTags, setBulkRemoveTags] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);

  // Segments
  const [segments, setSegments] = useState<Segment[]>([]);
  const [activeSegment, setActiveSegment] = useState<Segment | null>(null);
  const [newSegmentName, setNewSegmentName] = useState("");
  const [newSegmentDesc, setNewSegmentDesc] = useState("");

  // Segment Builder
  const [segBuilderGroups, setSegBuilderGroups] = useState<SegmentRuleGroup[]>([{ connector: "AND", rules: [{ field: "lifecycle_stage", operator: "equals", value: "" }] }]);
  const [segBuilderConnector, setSegBuilderConnector] = useState<"AND" | "OR">("AND");
  const [segBuilderName, setSegBuilderName] = useState("");
  const [segBuilderDesc, setSegBuilderDesc] = useState("");
  const [segBuilderPreview, setSegBuilderPreview] = useState<{ count: number; contacts: Contact[] } | null>(null);
  const [segBuilderLoading, setSegBuilderLoading] = useState(false);

  // Duplicates & Merge
  const [duplicateGroups, setDuplicateGroups] = useState<DuplicateGroup[]>([]);
  const [duplicatesLoading, setDuplicatesLoading] = useState(false);
  const [mergeSource, setMergeSource] = useState<Contact | null>(null);
  const [mergeTarget, setMergeTarget] = useState<Contact | null>(null);
  const [mergeFieldChoices, setMergeFieldChoices] = useState<Record<string, "source" | "target">>({});

  // Import V2
  const [importStep, setImportStep] = useState<1 | 2 | 3 | 4>(1);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [importMappings, setImportMappings] = useState<ImportMapping[]>([]);
  const [importProgress, setImportProgress] = useState(0);
  const [importResult, setImportResult] = useState<any>(null);
  const [importLoading, setImportLoading] = useState(false);

  // Export V2
  const [exportFormat, setExportFormat] = useState<"csv" | "xlsx">("csv");
  const [exportSegmentId, setExportSegmentId] = useState<number | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  // Custom Fields
  const [customFields, setCustomFields] = useState<CustomFieldDef[]>([]);
  const [newCfName, setNewCfName] = useState("");
  const [newCfLabel, setNewCfLabel] = useState("");
  const [newCfType, setNewCfType] = useState("text");
  const [newCfRequired, setNewCfRequired] = useState(false);
  const [newCfOptions, setNewCfOptions] = useState("");
  const [editingCfId, setEditingCfId] = useState<number | null>(null);
  const [contactCustomValues, setContactCustomValues] = useState<Record<string, any>>({});

  // Columns
  const [columns, setColumns] = useState([
    { key: "name", label: "Name", visible: true },
    { key: "email", label: "E-Mail", visible: true },
    { key: "phone", label: "Telefon", visible: true },
    { key: "company", label: "Firma", visible: true },
    { key: "lifecycle", label: "Status", visible: true },
    { key: "source", label: "Quelle", visible: true },
    { key: "tags", label: "Tags", visible: true },
    { key: "score", label: "Score", visible: false },
    { key: "created", label: "Erstellt", visible: true },
  ]);

  // ── Active filter count ───────────────────────────────────────────────
  const activeFilterCount = [filterLifecycle, filterSource, filterCompany, filterScoreMin, filterScoreMax, filterHasEmail, filterHasPhone, filterDateFrom, filterDateTo].filter(Boolean).length + filterTags.length;

  // ── Data Fetching ──────────────────────────────────────────────────────

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE), sort_by: sortBy, sort_dir: sortDir });
      if (searchQuery) params.set("search", searchQuery);
      if (filterLifecycle) params.set("lifecycle_stage", filterLifecycle);
      if (filterSource) params.set("source", filterSource);
      if (filterCompany) params.set("company", filterCompany);
      if (filterTags.length > 0) filterTags.forEach(t => params.append("tags", t));
      const res = await apiFetch(`/api/v2/contacts?${params}`);
      if (res.ok) {
        const data: ContactListResponse = await res.json();
        setContacts(data.items);
        setTotal(data.total);
        setTotalPages(data.total_pages);
      }
    } catch { /* best effort */ } finally { setLoading(false); }
  }, [page, searchQuery, sortBy, sortDir, filterLifecycle, filterSource, filterCompany, filterTags]);

  const fetchStats = async () => {
    try { const res = await apiFetch("/api/v2/contacts/stats"); if (res.ok) setStats(await res.json()); } catch {}
  };

  const fetchTags = async () => {
    try { const res = await apiFetch("/api/v2/contacts/tags"); if (res.ok) { const data = await res.json(); setAllTags(data.items || data); } } catch {}
  };

  const fetchSegments = async () => {
    try { const res = await apiFetch("/api/v2/contacts/segments"); if (res.ok) { const data = await res.json(); setSegments(data.items || data); } } catch {}
  };

  const fetchCustomFields = async () => {
    try { const res = await apiFetch("/api/v2/contacts/custom-fields"); if (res.ok) { const data = await res.json(); setCustomFields(data.items || data); } } catch {}
  };

  useEffect(() => { fetchContacts(); }, [fetchContacts]);
  useEffect(() => { fetchStats(); fetchTags(); fetchSegments(); fetchCustomFields(); }, []);

  const handleSearchChange = (val: string) => {
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => { setSearchQuery(val); setPage(1); }, 350);
  };

  // ── Contact Detail ─────────────────────────────────────────────────────

  const openDetail = async (contact: Contact) => {
    setSelectedContact(contact);
    setDetailTab("overview");
    setInlineEditing(false);
    // Fetch notes
    try { const res = await apiFetch(`/api/v2/contacts/${contact.id}/notes`); if (res.ok) { const data = await res.json(); setDetailNotes(data.items || data); } } catch {}
    // Fetch activities
    try { const res = await apiFetch(`/api/v2/contacts/${contact.id}/activities`); if (res.ok) { const data = await res.json(); setDetailActivities(data.items || data); } } catch {}
    // Fetch custom field values
    try { const res = await apiFetch(`/api/v2/contacts/${contact.id}/custom-fields`); if (res.ok) { const data = await res.json(); setContactCustomValues(data.values || data); } } catch {}
  };

  // ── Inline Edit ────────────────────────────────────────────────────────

  const startInlineEdit = () => {
    if (!selectedContact) return;
    setInlineData({
      first_name: selectedContact.first_name, last_name: selectedContact.last_name,
      email: selectedContact.email || "", phone: selectedContact.phone || "",
      company: selectedContact.company || "", job_title: selectedContact.job_title || "",
      lifecycle_stage: selectedContact.lifecycle_stage,
      gender: selectedContact.gender || "", date_of_birth: selectedContact.date_of_birth || "",
      preferred_language: selectedContact.preferred_language || "de",
      consent_email: selectedContact.consent_email || false, consent_sms: selectedContact.consent_sms || false,
      consent_phone: selectedContact.consent_phone || false, consent_whatsapp: selectedContact.consent_whatsapp || false,
    });
    setInlineEditing(true);
  };

  const saveInlineEdit = async () => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}`, {
        method: "PUT", body: JSON.stringify(inlineData),
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedContact(updated);
        setContacts(prev => prev.map(c => c.id === updated.id ? updated : c));
        setInlineEditing(false);
        fetchStats();
      }
    } catch {}
  };

  // ── CRUD Operations ────────────────────────────────────────────────────

  const handleCreate = async (force = false) => {
    if (!formData.first_name.trim() || !formData.last_name.trim()) { setFormError("Vor- und Nachname sind Pflichtfelder."); return; }
    setFormLoading(true);
    try {
      // Duplicate check first
      if (!force) {
        const dupRes = await apiFetch("/api/v2/contacts/duplicates/check", {
          method: "POST", body: JSON.stringify({ email: formData.email || undefined, phone: formData.phone || undefined, first_name: formData.first_name, last_name: formData.last_name }),
        });
        if (dupRes.ok) {
          const dupData = await dupRes.json();
          if (dupData.duplicates && dupData.duplicates.length > 0) {
            setFormDuplicates(dupData.duplicates);
            setShowDuplicateWarning(true);
            setFormLoading(false);
            return;
          }
        }
      }
      const tagNames = formData.tags ? formData.tags.split(",").map((t: string) => t.trim()).filter(Boolean) : [];
      const body: any = {
        first_name: formData.first_name, last_name: formData.last_name,
        email: formData.email || undefined, phone: formData.phone || undefined,
        company: formData.company || undefined, job_title: formData.job_title || undefined,
        lifecycle_stage: formData.lifecycle_stage, source: formData.source,
        gender: formData.gender || undefined, date_of_birth: formData.date_of_birth || undefined,
        preferred_language: formData.preferred_language,
        consent_email: formData.consent_email, consent_sms: formData.consent_sms,
        consent_phone: formData.consent_phone, consent_whatsapp: formData.consent_whatsapp,
        tags: tagNames, notes: formData.notes || undefined,
      };
      const res = await apiFetch("/api/v2/contacts", { method: "POST", body: JSON.stringify(body) });
      if (res.ok) {
        setShowCreateModal(false); setShowDuplicateWarning(false); setFormDuplicates([]);
        resetForm(); fetchContacts(); fetchStats(); fetchTags();
      } else { const err = await res.json().catch(() => null); setFormError(err?.detail || "Fehler beim Erstellen."); }
    } catch { setFormError("Netzwerkfehler."); } finally { setFormLoading(false); }
  };

  const handleUpdate = async () => {
    if (!selectedContact) return;
    setFormLoading(true);
    try {
      const tagNames = formData.tags ? formData.tags.split(",").map((t: string) => t.trim()).filter(Boolean) : undefined;
      const body: any = {
        first_name: formData.first_name, last_name: formData.last_name,
        email: formData.email || undefined, phone: formData.phone || undefined,
        company: formData.company || undefined, job_title: formData.job_title || undefined,
        lifecycle_stage: formData.lifecycle_stage, gender: formData.gender || undefined,
        date_of_birth: formData.date_of_birth || undefined, preferred_language: formData.preferred_language,
        consent_email: formData.consent_email, consent_sms: formData.consent_sms,
        consent_phone: formData.consent_phone, consent_whatsapp: formData.consent_whatsapp,
        tags: tagNames,
      };
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}`, { method: "PUT", body: JSON.stringify(body) });
      if (res.ok) {
        const updated = await res.json();
        setContacts(prev => prev.map(c => c.id === updated.id ? updated : c));
        setSelectedContact(updated);
        setShowEditModal(false); fetchStats(); fetchTags();
      } else { const err = await res.json().catch(() => null); setFormError(err?.detail || "Fehler beim Speichern."); }
    } catch { setFormError("Netzwerkfehler."); } finally { setFormLoading(false); }
  };

  const handleDelete = async (ids: number[]) => {
    if (!confirm(`${ids.length} Kontakt(e) wirklich löschen?`)) return;
    try {
      if (ids.length === 1) {
        await apiFetch(`/api/v2/contacts/${ids[0]}`, { method: "DELETE" });
      } else {
        await apiFetch("/api/v2/contacts/bulk/delete", { method: "POST", body: JSON.stringify({ contact_ids: ids }) });
      }
      setSelectedIds(new Set());
      if (selectedContact && ids.includes(selectedContact.id)) setSelectedContact(null);
      fetchContacts(); fetchStats();
    } catch {}
  };

  // ── Bulk Operations ────────────────────────────────────────────────────

  const handleBulkUpdate = async () => {
    setBulkLoading(true);
    try {
      const body: any = { contact_ids: Array.from(selectedIds) };
      if (bulkLifecycle) body.lifecycle_stage = bulkLifecycle;
      if (bulkAddTags) body.add_tags = bulkAddTags.split(",").map(t => t.trim()).filter(Boolean);
      if (bulkRemoveTags) body.remove_tags = bulkRemoveTags.split(",").map(t => t.trim()).filter(Boolean);
      const res = await apiFetch("/api/v2/contacts/bulk/update", { method: "POST", body: JSON.stringify(body) });
      if (res.ok) {
        setShowBulkModal(false); setSelectedIds(new Set());
        setBulkLifecycle(""); setBulkAddTags(""); setBulkRemoveTags("");
        fetchContacts(); fetchStats(); fetchTags();
      }
    } catch {} finally { setBulkLoading(false); }
  };

  // ── Notes ──────────────────────────────────────────────────────────────

  const handleAddNote = async () => {
    if (!selectedContact || !newNote.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes`, { method: "POST", body: JSON.stringify({ content: newNote }) });
      if (res.ok) { setNewNote(""); const data = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes`); if (data.ok) { const d = await data.json(); setDetailNotes(d.items || d); } }
    } catch {}
  };

  const handleUpdateNote = async (noteId: number) => {
    if (!selectedContact || !editingNoteContent.trim()) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes/${noteId}`, { method: "PUT", body: JSON.stringify({ content: editingNoteContent }) });
      if (res.ok) { setEditingNoteId(null); setEditingNoteContent(""); const data = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes`); if (data.ok) { const d = await data.json(); setDetailNotes(d.items || d); } }
    } catch {}
  };

  const handleDeleteNote = async (noteId: number) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes/${noteId}`, { method: "DELETE" });
      if (res.ok) setDetailNotes(prev => prev.filter(n => n.id !== noteId));
    } catch {}
  };

  const handleTogglePin = async (noteId: number, currentPinned: boolean) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes/${noteId}`, { method: "PUT", body: JSON.stringify({ is_pinned: !currentPinned }) });
      if (res.ok) { const data = await apiFetch(`/api/v2/contacts/${selectedContact.id}/notes`); if (data.ok) { const d = await data.json(); setDetailNotes(d.items || d); } }
    } catch {}
  };

  // ── Tags on Contact ────────────────────────────────────────────────────

  const handleAddTagToContact = async (tagName: string) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/tags`, { method: "POST", body: JSON.stringify({ tag_name: tagName, color: newTagColor }) });
      if (res.ok) {
        const updated = await apiFetch(`/api/v2/contacts/${selectedContact.id}`);
        if (updated.ok) { const c = await updated.json(); setSelectedContact(c); setContacts(prev => prev.map(x => x.id === c.id ? c : x)); }
        setNewTagName(""); fetchTags();
      }
    } catch {}
  };

  const handleRemoveTagFromContact = async (tagName: string) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/tags/${encodeURIComponent(tagName)}`, { method: "DELETE" });
      if (res.ok) {
        const updated = await apiFetch(`/api/v2/contacts/${selectedContact.id}`);
        if (updated.ok) { const c = await updated.json(); setSelectedContact(c); setContacts(prev => prev.map(x => x.id === c.id ? c : x)); }
        fetchTags();
      }
    } catch {}
  };

  // ── Activities ─────────────────────────────────────────────────────────

  const handleAddActivity = async (type: string, description: string) => {
    if (!selectedContact) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/${selectedContact.id}/activities`, { method: "POST", body: JSON.stringify({ activity_type: type, description }) });
      if (res.ok) { const data = await apiFetch(`/api/v2/contacts/${selectedContact.id}/activities`); if (data.ok) { const d = await data.json(); setDetailActivities(d.items || d); } }
    } catch {}
  };

  // ── Duplicates ─────────────────────────────────────────────────────────

  const fetchDuplicateGroups = async () => {
    setDuplicatesLoading(true);
    try { const res = await apiFetch("/api/v2/contacts/duplicates"); if (res.ok) { const data = await res.json(); setDuplicateGroups(data.groups || data); } } catch {}
    finally { setDuplicatesLoading(false); }
  };

  // ── Merge ──────────────────────────────────────────────────────────────

  const initMerge = (source: Contact, target: Contact) => {
    setMergeSource(source);
    setMergeTarget(target);
    const fields = ["first_name", "last_name", "email", "phone", "company", "job_title", "lifecycle_stage", "gender", "date_of_birth", "preferred_language"];
    const choices: Record<string, "source" | "target"> = {};
    fields.forEach(f => { choices[f] = (target as any)[f] ? "target" : "source"; });
    setMergeFieldChoices(choices);
    setShowMergeWizard(true);
    setShowDuplicatesModal(false);
  };

  const executeMerge = async () => {
    if (!mergeSource || !mergeTarget) return;
    try {
      const overrides: Record<string, any> = {};
      Object.entries(mergeFieldChoices).forEach(([field, choice]) => {
        overrides[field] = choice === "source" ? (mergeSource as any)[field] : (mergeTarget as any)[field];
      });
      const res = await apiFetch("/api/v2/contacts/merge", {
        method: "POST",
        body: JSON.stringify({ source_id: mergeSource.id, target_id: mergeTarget.id, field_overrides: overrides }),
      });
      if (res.ok) {
        setShowMergeWizard(false); setMergeSource(null); setMergeTarget(null);
        fetchContacts(); fetchStats();
      }
    } catch {}
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
        method: "POST", body: JSON.stringify({ name: newSegmentName, description: newSegmentDesc || undefined, filter_json: Object.keys(filterJson).length > 0 ? filterJson : undefined, is_dynamic: true }),
      });
      if (res.ok) { setNewSegmentName(""); setNewSegmentDesc(""); fetchSegments(); }
    } catch {}
  };

  const handleDeleteSegment = async (segmentId: number) => {
    if (!confirm("Segment wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/segments/${segmentId}`, { method: "DELETE" });
      if (res.ok) { if (activeSegment?.id === segmentId) setActiveSegment(null); fetchSegments(); }
    } catch {}
  };

  // ── Segment Builder ────────────────────────────────────────────────────

  const addRuleToGroup = (groupIdx: number) => {
    setSegBuilderGroups(prev => prev.map((g, i) => i === groupIdx ? { ...g, rules: [...g.rules, { field: "lifecycle_stage", operator: "equals", value: "" }] } : g));
  };

  const removeRuleFromGroup = (groupIdx: number, ruleIdx: number) => {
    setSegBuilderGroups(prev => prev.map((g, i) => i === groupIdx ? { ...g, rules: g.rules.filter((_, ri) => ri !== ruleIdx) } : g));
  };

  const updateRule = (groupIdx: number, ruleIdx: number, updates: Partial<SegmentRule>) => {
    setSegBuilderGroups(prev => prev.map((g, i) => i === groupIdx ? { ...g, rules: g.rules.map((r, ri) => ri === ruleIdx ? { ...r, ...updates } : r) } : g));
  };

  const addRuleGroup = () => {
    setSegBuilderGroups(prev => [...prev, { connector: "AND", rules: [{ field: "lifecycle_stage", operator: "equals", value: "" }] }]);
  };

  const removeRuleGroup = (groupIdx: number) => {
    if (segBuilderGroups.length <= 1) return;
    setSegBuilderGroups(prev => prev.filter((_, i) => i !== groupIdx));
  };

  const toggleGroupConnector = (groupIdx: number) => {
    setSegBuilderGroups(prev => prev.map((g, i) => i === groupIdx ? { ...g, connector: g.connector === "AND" ? "OR" : "AND" } : g));
  };

  const previewSegment = async () => {
    setSegBuilderLoading(true);
    try {
      const res = await apiFetch("/api/v2/contacts/segments/preview", {
        method: "POST", body: JSON.stringify({ filter_groups: segBuilderGroups, group_connector: segBuilderConnector }),
      });
      if (res.ok) { const data = await res.json(); setSegBuilderPreview(data); }
    } catch {} finally { setSegBuilderLoading(false); }
  };

  const saveSegmentFromBuilder = async () => {
    if (!segBuilderName.trim()) return;
    try {
      const res = await apiFetch("/api/v2/contacts/segments", {
        method: "POST", body: JSON.stringify({
          name: segBuilderName, description: segBuilderDesc || undefined,
          filter_groups: segBuilderGroups, group_connector: segBuilderConnector, is_dynamic: true,
        }),
      });
      if (res.ok) {
        setShowSegmentBuilder(false); setSegBuilderName(""); setSegBuilderDesc("");
        setSegBuilderGroups([{ connector: "AND", rules: [{ field: "lifecycle_stage", operator: "equals", value: "" }] }]);
        setSegBuilderPreview(null); fetchSegments();
      }
    } catch {}
  };

  // ── Import V2 ──────────────────────────────────────────────────────────

  const handleImportUpload = async (file: File) => {
    setImportFile(file);
    setImportLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch("/api/v2/contacts/import/preview", { method: "POST", body: fd });
      if (res.ok) {
        const data: ImportPreview = await res.json();
        setImportPreview(data);
        setImportMappings(data.suggested_mappings || data.columns.map(col => ({ csv_column: col, contact_field: "__skip__", is_key: false })));
        setImportStep(2);
      }
    } catch {} finally { setImportLoading(false); }
  };

  const executeImportV2 = async () => {
    if (!importFile) return;
    setImportLoading(true);
    setImportStep(4);
    setImportProgress(0);
    try {
      const fd = new FormData();
      fd.append("file", importFile);
      fd.append("mappings", JSON.stringify(importMappings));
      const res = await apiFetch("/api/v2/contacts/import/execute", { method: "POST", body: fd });
      if (res.ok) {
        const data = await res.json();
        setImportResult(data);
        setImportProgress(100);
        fetchContacts(); fetchStats(); fetchTags();
      }
    } catch {} finally { setImportLoading(false); }
  };

  // ── Export V2 ──────────────────────────────────────────────────────────

  const handleExportV2 = async () => {
    setExportLoading(true);
    try {
      const params = new URLSearchParams({ format: exportFormat });
      if (exportSegmentId) params.set("segment_id", String(exportSegmentId));
      if (filterLifecycle) params.set("lifecycle_stage", filterLifecycle);
      if (filterSource) params.set("source", filterSource);
      const res = await apiFetch(`/api/v2/contacts/export?${params}`);
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `contacts_export.${exportFormat}`;
        a.click();
        URL.revokeObjectURL(url);
        setShowExportModal(false);
      }
    } catch {} finally { setExportLoading(false); }
  };

  // ── Custom Fields ──────────────────────────────────────────────────────

  const handleCreateCustomField = async () => {
    if (!newCfName.trim() || !newCfLabel.trim()) return;
    try {
      const body: any = { field_name: newCfName, field_label: newCfLabel, field_type: newCfType, is_required: newCfRequired };
      if (newCfType === "select" && newCfOptions) body.field_options = { choices: newCfOptions.split(",").map(o => o.trim()).filter(Boolean) };
      const res = await apiFetch("/api/v2/contacts/custom-fields", { method: "POST", body: JSON.stringify(body) });
      if (res.ok) { setNewCfName(""); setNewCfLabel(""); setNewCfType("text"); setNewCfRequired(false); setNewCfOptions(""); fetchCustomFields(); }
    } catch {}
  };

  const handleDeleteCustomField = async (cfId: number) => {
    if (!confirm("Benutzerdefiniertes Feld wirklich löschen?")) return;
    try {
      const res = await apiFetch(`/api/v2/contacts/custom-fields/${cfId}`, { method: "DELETE" });
      if (res.ok) fetchCustomFields();
    } catch {}
  };

  // ── Selection ──────────────────────────────────────────────────────────

  const toggleSelect = (id: number) => setSelectedIds(prev => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const toggleSelectAll = () => {
    if (selectedIds.size === contacts.length) setSelectedIds(new Set());
    else setSelectedIds(new Set(contacts.map(c => c.id)));
  };

  // ── Sort ───────────────────────────────────────────────────────────────

  const handleSort = (col: string) => {
    const fieldMap: Record<string, string> = { name: "last_name", email: "email", phone: "phone", company: "company", lifecycle: "lifecycle_stage", source: "source", score: "score", created: "created_at" };
    const field = fieldMap[col] || col;
    if (sortBy === field) setSortDir(prev => prev === "asc" ? "desc" : "asc");
    else { setSortBy(field); setSortDir("asc"); }
  };

  // ── Reset Filters ─────────────────────────────────────────────────────

  const resetFilters = () => {
    setFilterLifecycle(""); setFilterSource(""); setFilterTags([]); setFilterCompany("");
    setFilterScoreMin(""); setFilterScoreMax(""); setFilterHasEmail(""); setFilterHasPhone("");
    setFilterDateFrom(""); setFilterDateTo(""); setSearchQuery(""); setPage(1);
  };

  const resetForm = () => {
    setFormData({
      first_name: "", last_name: "", email: "", phone: "", company: "",
      job_title: "", lifecycle_stage: "subscriber", source: "manual",
      gender: "", notes: "", date_of_birth: "", preferred_language: "de",
      consent_email: false, consent_sms: false, consent_phone: false, consent_whatsapp: false, tags: "",
    });
    setFormError(""); setFormDuplicates([]); setShowDuplicateWarning(false);
  };

  const openEditModal = () => {
    if (!selectedContact) return;
    setFormData({
      first_name: selectedContact.first_name, last_name: selectedContact.last_name,
      email: selectedContact.email || "", phone: selectedContact.phone || "",
      company: selectedContact.company || "", job_title: selectedContact.job_title || "",
      lifecycle_stage: selectedContact.lifecycle_stage, source: selectedContact.source,
      gender: selectedContact.gender || "", notes: "", date_of_birth: selectedContact.date_of_birth || "",
      preferred_language: selectedContact.preferred_language || "de",
      consent_email: selectedContact.consent_email || false, consent_sms: selectedContact.consent_sms || false,
      consent_phone: selectedContact.consent_phone || false, consent_whatsapp: selectedContact.consent_whatsapp || false,
      tags: selectedContact.tags?.map(t => t.name).join(", ") || "",
    });
    setFormError(""); setShowEditModal(true);
  };

  // ── Column Toggle ─────────────────────────────────────────────────────

  const toggleColumn = (key: string) => setColumns(prev => prev.map(c => c.key === key ? { ...c, visible: !c.visible } : c));
  const visibleCols = columns.filter(c => c.visible);


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
            {isAdmin && (
              <button style={S.actionBtnSecondary} onClick={() => setShowSegmentBuilder(true)}>
                <Sliders size={14} /> Segment-Builder
              </button>
            )}
            {isAdmin && (
              <button style={S.actionBtnSecondary} onClick={() => setShowCustomFieldsAdmin(true)}>
                <Database size={14} /> Felder
              </button>
            )}
            <button style={S.actionBtnSecondary} onClick={() => setShowExportModal(true)}>
              <Download size={14} /> Export
            </button>
            <button style={S.actionBtnSecondary} onClick={() => { setImportStep(1); setImportFile(null); setImportPreview(null); setImportResult(null); setShowImportModal(true); }}>
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
          {[
            { icon: Users, value: stats.total, label: "Gesamt", bg: T.accentDim, color: T.accent },
            { icon: TrendingUp, value: stats.lifecycle_distribution?.customer || 0, label: "Kunden", bg: T.successDim, color: T.success },
            { icon: Mail, value: `${stats.email_coverage}%`, label: "E-Mail", bg: T.infoDim, color: T.info },
            { icon: Phone, value: `${stats.phone_coverage}%`, label: "Telefon", bg: T.warningDim, color: T.warning },
            { icon: BarChart3, value: stats.average_score?.toFixed(0) || 0, label: "Ø Score", bg: `${T.accent}15`, color: T.accent },
            { icon: Activity, value: stats.recent_activities_7d || 0, label: "Aktivitäten (7T)", bg: `${T.success}15`, color: T.success },
          ].map((s, i) => (
            <div key={i} style={S.statCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: s.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <s.icon size={18} style={{ color: s.color }} />
                </div>
                <div>
                  <div style={S.statValue}>{s.value}</div>
                  <div style={S.statLabel}>{s.label}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Segments Panel ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {showSegmentsPanel && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: "hidden", marginBottom: 16 }}>
            <Card style={{ padding: 0 }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Layers size={16} style={{ color: T.accent }} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Segmente</span>
                  <Badge variant="default">{segments.length}</Badge>
                </div>
                <button style={{ ...S.filterBtn, padding: "6px 10px" }} onClick={() => setShowSegmentsPanel(false)}><X size={14} /></button>
              </div>
              {segments.length === 0 ? (
                <div style={{ padding: 20, textAlign: "center", color: T.textDim, fontSize: 13 }}>Noch keine Segmente erstellt.</div>
              ) : (
                <div style={{ maxHeight: 200, overflowY: "auto" }}>
                  {segments.map(seg => (
                    <div key={seg.id} style={{ ...S.segmentSidebar, background: activeSegment?.id === seg.id ? T.accentDim : "transparent" }}
                      onClick={() => {
                        if (activeSegment?.id === seg.id) { setActiveSegment(null); resetFilters(); }
                        else {
                          setActiveSegment(seg);
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
                        <button style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: T.textDim }} onClick={(e) => { e.stopPropagation(); handleDeleteSegment(seg.id); }}>
                          <Trash2 size={12} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {isAdmin && (
                <div style={{ padding: "12px 18px", borderTop: `1px solid ${T.border}`, display: "flex", gap: 8 }}>
                  <input style={{ ...S.formInput, flex: 1, padding: "7px 10px" }} placeholder="Neues Segment..." value={newSegmentName} onChange={(e) => setNewSegmentName(e.target.value)} />
                  <button style={{ ...S.actionBtn, opacity: newSegmentName.trim() ? 1 : 0.5, padding: "7px 12px" }} disabled={!newSegmentName.trim()} onClick={handleCreateSegment}>
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
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
            <div style={S.bulkBar}>
              <CheckCircle2 size={16} style={{ color: T.accent }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.accent }}>{selectedIds.size} ausgewählt</span>
              <div style={{ flex: 1 }} />
              <button style={{ ...S.actionBtnSecondary, padding: "6px 12px" }} onClick={() => setShowBulkModal(true)}><Edit3 size={13} /> Bulk-Bearbeiten</button>
              <button style={{ ...S.actionBtnDanger, padding: "6px 12px" }} onClick={() => handleDelete(Array.from(selectedIds))}><Trash2 size={13} /> Löschen</button>
              <button style={{ ...S.filterBtn, padding: "6px 10px" }} onClick={() => setSelectedIds(new Set())}><X size={13} /> Abbrechen</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <Card style={{ padding: "16px 18px", marginBottom: 16 }}>
        <div style={S.toolbar}>
          <div style={S.searchWrap}>
            <Search size={15} style={S.searchIcon} />
            <input style={S.searchInput} placeholder="Kontakte durchsuchen (Name, E-Mail, Telefon, Firma)..." onChange={(e) => handleSearchChange(e.target.value)} />
          </div>
          <button style={{ ...S.filterBtn, ...(showFilters || activeFilterCount > 0 ? { borderColor: T.accent, color: T.accent } : {}) }} onClick={() => setShowFilters(!showFilters)}>
            <ListFilter size={14} /> Filter {activeFilterCount > 0 && <Badge variant="accent">{activeFilterCount}</Badge>} {showFilters ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          </button>
          <div style={{ position: "relative" }}>
            <button style={S.filterBtn} onClick={() => setShowColumnPicker(!showColumnPicker)}><Columns3 size={14} /> Spalten</button>
            {showColumnPicker && (
              <div style={S.dropdown}>
                <div style={{ padding: "10px 14px", borderBottom: `1px solid ${T.border}`, fontSize: 12, fontWeight: 700, color: T.textMuted }}>Sichtbare Spalten</div>
                {columns.map(col => (
                  <label key={col.key} style={{ ...S.dropdownItem, cursor: "pointer" }} onClick={() => toggleColumn(col.key)}>
                    <input type="checkbox" checked={col.visible} onChange={() => toggleColumn(col.key)} style={{ accentColor: T.accent }} />
                    {col.label}
                  </label>
                ))}
                <div style={{ padding: "8px 14px", borderTop: `1px solid ${T.border}` }}>
                  <button style={{ ...S.filterBtn, width: "100%", justifyContent: "center", padding: "6px" }} onClick={() => setShowColumnPicker(false)}>Schließen</button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Extended Filter Row ──────────────────────────────────────── */}
        <AnimatePresence>
          {showFilters && (
            <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} style={{ overflow: "hidden", paddingTop: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
                <div>
                  <label style={S.formLabel}>Lifecycle-Phase</label>
                  <select style={S.formSelect} value={filterLifecycle} onChange={(e) => { setFilterLifecycle(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (<option key={key} value={key}>{label}</option>))}
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Quelle</label>
                  <select style={S.formSelect} value={filterSource} onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}>
                    <option value="">Alle</option>
                    {Object.entries(SOURCE_LABELS).map(([key, label]) => (<option key={key} value={key}>{label}</option>))}
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Firma</label>
                  <input style={S.formInput} value={filterCompany} onChange={(e) => { setFilterCompany(e.target.value); setPage(1); }} placeholder="Firma..." />
                </div>
                <div>
                  <label style={S.formLabel}>Tags</label>
                  <select style={S.formSelect} onChange={(e) => { if (e.target.value && !filterTags.includes(e.target.value)) { setFilterTags(prev => [...prev, e.target.value]); setPage(1); } e.target.value = ""; }}>
                    <option value="">Tag wählen...</option>
                    {allTags.map(t => (<option key={t.id} value={t.name}>{t.name}</option>))}
                  </select>
                  {filterTags.length > 0 && (
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                      {filterTags.map(t => (
                        <span key={t} style={{ ...S.tagChip, background: T.accentDim, color: T.accent }}>
                          {t} <button style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 0 }} onClick={() => { setFilterTags(prev => prev.filter(x => x !== t)); setPage(1); }}><X size={10} /></button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <label style={S.formLabel}>Score min</label>
                  <input style={S.formInput} type="number" value={filterScoreMin} onChange={(e) => { setFilterScoreMin(e.target.value); setPage(1); }} placeholder="0" />
                </div>
                <div>
                  <label style={S.formLabel}>Score max</label>
                  <input style={S.formInput} type="number" value={filterScoreMax} onChange={(e) => { setFilterScoreMax(e.target.value); setPage(1); }} placeholder="100" />
                </div>
                <div>
                  <label style={S.formLabel}>E-Mail vorhanden</label>
                  <select style={S.formSelect} value={filterHasEmail} onChange={(e) => { setFilterHasEmail(e.target.value); setPage(1); }}>
                    <option value="">Egal</option><option value="yes">Ja</option><option value="no">Nein</option>
                  </select>
                </div>
                <div>
                  <label style={S.formLabel}>Erstellt von</label>
                  <input style={S.formInput} type="date" value={filterDateFrom} onChange={(e) => { setFilterDateFrom(e.target.value); setPage(1); }} />
                </div>
                <div>
                  <label style={S.formLabel}>Erstellt bis</label>
                  <input style={S.formInput} type="date" value={filterDateTo} onChange={(e) => { setFilterDateTo(e.target.value); setPage(1); }} />
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12, gap: 8 }}>
                <button style={S.filterBtn} onClick={resetFilters}><RotateCcw size={12} /> Filter zurücksetzen</button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </Card>

      {/* ── Contact Table ───────────────────────────────────────────────── */}
      <Card style={{ padding: 0 }}>
        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={{ ...S.th, width: 40 }}>
                  <input type="checkbox" checked={contacts.length > 0 && selectedIds.size === contacts.length} onChange={toggleSelectAll} style={{ accentColor: T.accent }} />
                </th>
                {visibleCols.map(col => (
                  <th key={col.key} style={S.th} onClick={() => handleSort(col.key)}>
                    <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      {col.label}
                      {sortBy === (({ name: "last_name", lifecycle: "lifecycle_stage", created: "created_at" } as any)[col.key] || col.key) && (
                        <ArrowUpDown size={11} style={{ color: T.accent }} />
                      )}
                    </span>
                  </th>
                ))}
                <th style={{ ...S.th, width: 60 }}>Aktion</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={visibleCols.length + 2} style={{ ...S.td, textAlign: "center", padding: 40 }}>
                  <Loader2 size={24} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
                </td></tr>
              ) : contacts.length === 0 ? (
                <tr><td colSpan={visibleCols.length + 2} style={{ ...S.td, textAlign: "center", padding: 40, color: T.textDim }}>
                  Keine Kontakte gefunden.
                </td></tr>
              ) : contacts.map(contact => (
                <tr key={contact.id} style={{ cursor: "pointer", transition: "background .1s" }}
                  onClick={() => openDetail(contact)}
                  onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td style={S.td} onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(contact.id)} onChange={() => toggleSelect(contact.id)} style={{ accentColor: T.accent }} />
                  </td>
                  {visibleCols.map(col => (
                    <td key={col.key} style={S.td}>
                      {col.key === "name" ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div style={{ ...S.avatar, background: `${getAvatarColor(contact.full_name)}22`, color: getAvatarColor(contact.full_name) }}>
                            {getInitials(contact.first_name, contact.last_name)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 700, color: T.text }}>{contact.full_name}</div>
                            {contact.company && <div style={{ fontSize: 11, color: T.textDim }}>{contact.company}</div>}
                          </div>
                        </div>
                      ) : col.key === "email" ? (
                        <span style={{ color: contact.email ? T.text : T.textDim }}>{contact.email || "–"}</span>
                      ) : col.key === "phone" ? (
                        <span style={{ color: contact.phone ? T.text : T.textDim }}>{contact.phone || "–"}</span>
                      ) : col.key === "company" ? (
                        <span style={{ color: contact.company ? T.text : T.textDim }}>{contact.company || "–"}</span>
                      ) : col.key === "lifecycle" ? (
                        <Badge variant={contact.lifecycle_stage === "customer" ? "success" : contact.lifecycle_stage === "churned" ? "danger" : "default"}>
                          {LIFECYCLE_STAGES[contact.lifecycle_stage]?.label || contact.lifecycle_stage}
                        </Badge>
                      ) : col.key === "source" ? (
                        <span style={{ fontSize: 12, color: T.textMuted }}>{SOURCE_LABELS[contact.source] || contact.source}</span>
                      ) : col.key === "tags" ? (
                        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                          {(contact.tags || []).slice(0, 3).map(tag => (
                            <span key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}22`, color: tag.color || T.accent }}>{tag.name}</span>
                          ))}
                          {(contact.tags || []).length > 3 && <span style={{ ...S.tagChip, background: T.surfaceAlt, color: T.textDim }}>+{contact.tags.length - 3}</span>}
                        </div>
                      ) : col.key === "score" ? (
                        <span style={{ fontWeight: 700, color: contact.score >= 70 ? T.success : contact.score >= 40 ? T.warning : T.textDim }}>{contact.score}</span>
                      ) : col.key === "created" ? (
                        <span style={{ fontSize: 12, color: T.textMuted }}>{fmtDate(contact.created_at)}</span>
                      ) : null}
                    </td>
                  ))}
                  <td style={S.td} onClick={(e) => e.stopPropagation()}>
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 6 }} onClick={() => openDetail(contact)}>
                      <Eye size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div style={S.pagination}>
          <span style={{ fontSize: 12, color: T.textMuted }}>
            {total > 0 ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} von ${total}` : "Keine Ergebnisse"}
          </span>
          <div style={{ display: "flex", gap: 6 }}>
            <button style={{ ...S.filterBtn, opacity: page <= 1 ? 0.4 : 1 }} disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /></button>
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const p = totalPages <= 5 ? i + 1 : page <= 3 ? i + 1 : page >= totalPages - 2 ? totalPages - 4 + i : page - 2 + i;
              return (
                <button key={p} style={{ ...S.filterBtn, ...(p === page ? { background: T.accent, color: "#fff", borderColor: T.accent } : {}), minWidth: 34, justifyContent: "center" }} onClick={() => setPage(p)}>
                  {p}
                </button>
              );
            })}
            <button style={{ ...S.filterBtn, opacity: page >= totalPages ? 0.4 : 1 }} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight size={14} /></button>
          </div>
        </div>
      </Card>


      {/* ── Detail Side Panel ───────────────────────────────────────────── */}
      <AnimatePresence>
        {selectedContact && (
          <motion.div initial={{ x: 480 }} animate={{ x: 0 }} exit={{ x: 480 }} transition={{ type: "spring", damping: 25, stiffness: 300 }} style={S.detailPanel}>
            {/* Header */}
            <div style={S.detailHeader}>
              <div style={{ ...S.avatar, width: 48, height: 48, fontSize: 16, background: `${getAvatarColor(selectedContact.full_name)}22`, color: getAvatarColor(selectedContact.full_name) }}>
                {getInitials(selectedContact.first_name, selectedContact.last_name)}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 800, fontSize: 16, color: T.text }}>{selectedContact.full_name}</div>
                {selectedContact.company && <div style={{ fontSize: 12, color: T.textDim, marginTop: 2 }}>{selectedContact.company}{selectedContact.job_title ? ` • ${selectedContact.job_title}` : ""}</div>}
                <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                  <Badge variant={selectedContact.lifecycle_stage === "customer" ? "success" : selectedContact.lifecycle_stage === "churned" ? "danger" : "default"}>
                    {LIFECYCLE_STAGES[selectedContact.lifecycle_stage]?.label || selectedContact.lifecycle_stage}
                  </Badge>
                  <Badge variant="default">Score: {selectedContact.score}</Badge>
                </div>
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {isAdmin && !inlineEditing && (
                  <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 6 }} onClick={startInlineEdit} title="Bearbeiten"><Edit3 size={16} /></button>
                )}
                {isAdmin && !inlineEditing && (
                  <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 6 }} onClick={openEditModal} title="Vollständig bearbeiten"><Settings2 size={16} /></button>
                )}
                <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 6 }} onClick={() => { setSelectedContact(null); setInlineEditing(false); }}><X size={16} /></button>
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: "flex", borderBottom: `1px solid ${T.border}`, overflowX: "auto" }}>
              {(["overview", "activities", "notes", "tags", "custom"] as const).map(tab => (
                <button key={tab} style={{ ...S.detailTab, ...(detailTab === tab ? S.detailTabActive : {}) }} onClick={() => setDetailTab(tab)}>
                  {{ overview: "Übersicht", activities: "Aktivitäten", notes: "Notizen", tags: "Tags", custom: "Felder" }[tab]}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div style={S.detailBody}>
              {/* ── Overview Tab ──────────────────────────────────────────── */}
              {detailTab === "overview" && (
                <div>
                  {inlineEditing ? (
                    <div>
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 14 }}>
                        <button style={{ ...S.filterBtn, padding: "6px 12px" }} onClick={() => setInlineEditing(false)}><X size={12} /> Abbrechen</button>
                        <button style={{ ...S.actionBtn, padding: "6px 12px" }} onClick={saveInlineEdit}><Save size={12} /> Speichern</button>
                      </div>
                      {[
                        { key: "first_name", label: "Vorname" }, { key: "last_name", label: "Nachname" },
                        { key: "email", label: "E-Mail" }, { key: "phone", label: "Telefon" },
                        { key: "company", label: "Firma" }, { key: "job_title", label: "Position" },
                        { key: "gender", label: "Geschlecht" }, { key: "date_of_birth", label: "Geburtsdatum" },
                      ].map(f => (
                        <div key={f.key} style={S.formGroup}>
                          <label style={S.formLabel}>{f.label}</label>
                          {f.key === "gender" ? (
                            <select style={S.formSelect} value={inlineData[f.key] || ""} onChange={(e) => setInlineData(prev => ({ ...prev, [f.key]: e.target.value }))}>
                              <option value="">–</option><option value="male">Männlich</option><option value="female">Weiblich</option><option value="diverse">Divers</option>
                            </select>
                          ) : f.key === "date_of_birth" ? (
                            <input style={S.formInput} type="date" value={inlineData[f.key] || ""} onChange={(e) => setInlineData(prev => ({ ...prev, [f.key]: e.target.value }))} />
                          ) : (
                            <input style={S.formInput} value={inlineData[f.key] || ""} onChange={(e) => setInlineData(prev => ({ ...prev, [f.key]: e.target.value }))} />
                          )}
                        </div>
                      ))}
                      <div style={S.formGroup}>
                        <label style={S.formLabel}>Lifecycle-Phase</label>
                        <select style={S.formSelect} value={inlineData.lifecycle_stage} onChange={(e) => setInlineData(prev => ({ ...prev, lifecycle_stage: e.target.value }))}>
                          {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (<option key={key} value={key}>{label}</option>))}
                        </select>
                      </div>
                      <div style={{ marginTop: 14 }}>
                        <label style={S.formLabel}>DSGVO-Einwilligungen</label>
                        {[
                          { key: "consent_email", label: "E-Mail" }, { key: "consent_sms", label: "SMS" },
                          { key: "consent_phone", label: "Telefon" }, { key: "consent_whatsapp", label: "WhatsApp" },
                        ].map(c => (
                          <label key={c.key} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 12, color: T.text, cursor: "pointer" }}>
                            <input type="checkbox" checked={inlineData[c.key] || false} onChange={(e) => setInlineData(prev => ({ ...prev, [c.key]: e.target.checked }))} style={{ accentColor: T.accent }} />
                            {c.label}
                          </label>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div>
                      {/* Contact Info Grid */}
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
                        {[
                          { icon: Mail, label: "E-Mail", value: selectedContact.email },
                          { icon: Phone, label: "Telefon", value: selectedContact.phone },
                          { icon: Building2, label: "Firma", value: selectedContact.company },
                          { icon: UserCircle, label: "Position", value: selectedContact.job_title },
                          { icon: Globe, label: "Sprache", value: selectedContact.preferred_language?.toUpperCase() },
                          { icon: Calendar, label: "Erstellt", value: fmtDate(selectedContact.created_at) },
                          { icon: Hash, label: "Quelle", value: SOURCE_LABELS[selectedContact.source] || selectedContact.source },
                          { icon: Star, label: "Score", value: String(selectedContact.score) },
                        ].map((item, i) => (
                          <div key={i} style={{ padding: "10px 12px", borderRadius: 8, background: T.surfaceAlt }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                              <item.icon size={12} style={{ color: T.textDim }} />
                              <span style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase" }}>{item.label}</span>
                            </div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: item.value ? T.text : T.textDim }}>{item.value || "–"}</div>
                          </div>
                        ))}
                      </div>

                      {/* DSGVO */}
                      <div style={{ marginBottom: 20 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 8 }}>DSGVO-Einwilligungen</div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {[
                            { key: "consent_email", label: "E-Mail" }, { key: "consent_sms", label: "SMS" },
                            { key: "consent_phone", label: "Telefon" }, { key: "consent_whatsapp", label: "WhatsApp" },
                          ].map(c => (
                            <span key={c.key} style={{
                              ...S.tagChip,
                              background: (selectedContact as any)[c.key] ? `${T.success}15` : `${T.danger}15`,
                              color: (selectedContact as any)[c.key] ? T.success : T.danger,
                            }}>
                              {(selectedContact as any)[c.key] ? <Check size={10} /> : <X size={10} />} {c.label}
                            </span>
                          ))}
                        </div>
                      </div>

                      {/* Tags */}
                      {selectedContact.tags && selectedContact.tags.length > 0 && (
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 8 }}>Tags</div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {selectedContact.tags.map(tag => (
                              <span key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}22`, color: tag.color || T.accent }}>{tag.name}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ── Activities Tab ────────────────────────────────────────── */}
              {detailTab === "activities" && (
                <div>
                  {isAdmin && (
                    <div style={{ marginBottom: 16, padding: 12, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 8 }}>Aktivität hinzufügen</div>
                      <div style={{ display: "flex", gap: 8 }}>
                        {[
                          { type: "call", label: "Anruf", icon: Phone },
                          { type: "email_sent", label: "E-Mail", icon: Mail },
                          { type: "meeting", label: "Meeting", icon: Calendar },
                          { type: "note_added", label: "Notiz", icon: StickyNote },
                        ].map(a => (
                          <button key={a.type} style={{ ...S.filterBtn, padding: "6px 10px", fontSize: 11 }}
                            onClick={() => handleAddActivity(a.type, `${a.label} mit ${selectedContact.full_name}`)}>
                            <a.icon size={12} /> {a.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {detailActivities.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 30, color: T.textDim }}>
                      <Activity size={32} style={{ marginBottom: 8, opacity: 0.3 }} />
                      <div style={{ fontSize: 13 }}>Noch keine Aktivitäten</div>
                    </div>
                  ) : (
                    <div style={{ position: "relative", paddingLeft: 24 }}>
                      <div style={{ position: "absolute", left: 8, top: 0, bottom: 0, width: 2, background: T.border }} />
                      {detailActivities.map(act => {
                        const Icon = getActivityIcon(act.activity_type);
                        return (
                          <div key={act.id} style={{ position: "relative", marginBottom: 16, paddingLeft: 16 }}>
                            <div style={{ position: "absolute", left: -20, top: 4, width: 20, height: 20, borderRadius: 10, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                              <Icon size={10} style={{ color: T.accent }} />
                            </div>
                            <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{act.description}</div>
                            <div style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{fmtDateTime(act.created_at)}</div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* ── Notes Tab ─────────────────────────────────────────────── */}
              {detailTab === "notes" && (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <textarea style={{ ...S.formInput, minHeight: 80, resize: "vertical" }} placeholder="Neue Notiz schreiben..." value={newNote} onChange={(e) => setNewNote(e.target.value)} />
                    <button style={{ ...S.actionBtn, marginTop: 8, opacity: newNote.trim() ? 1 : 0.5 }} disabled={!newNote.trim()} onClick={handleAddNote}>
                      <Plus size={14} /> Notiz speichern
                    </button>
                  </div>
                  {detailNotes.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 30, color: T.textDim }}>
                      <StickyNote size={32} style={{ marginBottom: 8, opacity: 0.3 }} />
                      <div style={{ fontSize: 13 }}>Noch keine Notizen</div>
                    </div>
                  ) : (
                    <div>
                      {[...detailNotes].sort((a, b) => (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0)).map(note => (
                        <div key={note.id} style={{ padding: 12, borderRadius: 10, background: note.is_pinned ? T.accentDim : T.surfaceAlt, border: `1px solid ${note.is_pinned ? `${T.accent}30` : T.border}`, marginBottom: 10 }}>
                          {editingNoteId === note.id ? (
                            <div>
                              <textarea style={{ ...S.formInput, minHeight: 60, resize: "vertical" }} value={editingNoteContent} onChange={(e) => setEditingNoteContent(e.target.value)} />
                              <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                                <button style={{ ...S.actionBtn, padding: "5px 10px", fontSize: 11 }} onClick={() => handleUpdateNote(note.id)}><Save size={11} /> Speichern</button>
                                <button style={{ ...S.filterBtn, padding: "5px 10px", fontSize: 11 }} onClick={() => { setEditingNoteId(null); setEditingNoteContent(""); }}><X size={11} /> Abbrechen</button>
                              </div>
                            </div>
                          ) : (
                            <div>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                <div style={{ fontSize: 13, color: T.text, whiteSpace: "pre-wrap", flex: 1 }}>{note.content}</div>
                                <div style={{ display: "flex", gap: 4, marginLeft: 8 }}>
                                  <button style={{ background: "none", border: "none", cursor: "pointer", color: note.is_pinned ? T.accent : T.textDim, padding: 4 }} onClick={() => handleTogglePin(note.id, note.is_pinned)} title={note.is_pinned ? "Lösen" : "Anheften"}>
                                    {note.is_pinned ? <PinOff size={12} /> : <Pin size={12} />}
                                  </button>
                                  <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4 }} onClick={() => { setEditingNoteId(note.id); setEditingNoteContent(note.content); }} title="Bearbeiten">
                                    <Pencil size={12} />
                                  </button>
                                  <button style={{ background: "none", border: "none", cursor: "pointer", color: T.danger, padding: 4 }} onClick={() => handleDeleteNote(note.id)} title="Löschen">
                                    <Trash2 size={12} />
                                  </button>
                                </div>
                              </div>
                              <div style={{ fontSize: 10, color: T.textDim, marginTop: 6 }}>{fmtDateTime(note.created_at)}</div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── Tags Tab ──────────────────────────────────────────────── */}
              {detailTab === "tags" && (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 8 }}>Zugewiesene Tags</div>
                    {selectedContact.tags && selectedContact.tags.length > 0 ? (
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        {selectedContact.tags.map(tag => (
                          <span key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}22`, color: tag.color || T.accent, paddingRight: 6 }}>
                            {tag.name}
                            {isAdmin && (
                              <button style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: "0 2px", marginLeft: 4 }} onClick={() => handleRemoveTagFromContact(tag.name)}>
                                <X size={10} />
                              </button>
                            )}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: T.textDim }}>Keine Tags zugewiesen.</div>
                    )}
                  </div>
                  {isAdmin && (
                    <div style={{ padding: 14, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 8 }}>Tag hinzufügen</div>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input style={{ ...S.formInput, flex: 1 }} placeholder="Tag-Name..." value={newTagName} onChange={(e) => setNewTagName(e.target.value)} />
                        <input type="color" value={newTagColor} onChange={(e) => setNewTagColor(e.target.value)} style={{ width: 36, height: 36, borderRadius: 8, border: `1px solid ${T.border}`, cursor: "pointer", padding: 2 }} />
                        <button style={{ ...S.actionBtn, padding: "8px 12px", opacity: newTagName.trim() ? 1 : 0.5 }} disabled={!newTagName.trim()} onClick={() => handleAddTagToContact(newTagName)}>
                          <Plus size={14} />
                        </button>
                      </div>
                      {allTags.length > 0 && (
                        <div style={{ marginTop: 10 }}>
                          <div style={{ fontSize: 10, color: T.textDim, marginBottom: 6 }}>Vorhandene Tags:</div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {allTags.filter(t => !selectedContact.tags?.some(ct => ct.name === t.name)).slice(0, 10).map(tag => (
                              <button key={tag.id} style={{ ...S.tagChip, background: `${tag.color || T.accent}15`, color: tag.color || T.accent, cursor: "pointer", border: "none" }} onClick={() => handleAddTagToContact(tag.name)}>
                                <Plus size={10} /> {tag.name}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ── Custom Fields Tab ─────────────────────────────────────── */}
              {detailTab === "custom" && (
                <div>
                  {customFields.length === 0 ? (
                    <div style={{ textAlign: "center", padding: 30, color: T.textDim }}>
                      <Database size={32} style={{ marginBottom: 8, opacity: 0.3 }} />
                      <div style={{ fontSize: 13 }}>Keine benutzerdefinierten Felder konfiguriert.</div>
                      {isAdmin && <div style={{ fontSize: 12, marginTop: 6 }}>Klicke auf "Felder" im Header um welche anzulegen.</div>}
                    </div>
                  ) : (
                    <div>
                      {customFields.map(cf => (
                        <div key={cf.id} style={S.formGroup}>
                          <label style={S.formLabel}>{cf.field_label} {cf.is_required && <span style={{ color: T.danger }}>*</span>}</label>
                          <div style={{ fontSize: 13, color: T.text, padding: "8px 12px", borderRadius: 8, background: T.surfaceAlt }}>
                            {contactCustomValues[cf.field_name] || <span style={{ color: T.textDim }}>–</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Detail Footer */}
            {isAdmin && !inlineEditing && (
              <div style={{ padding: "12px 24px", borderTop: `1px solid ${T.border}`, display: "flex", gap: 8 }}>
                <button style={{ ...S.actionBtnDanger, flex: 1, justifyContent: "center" }} onClick={() => handleDelete([selectedContact.id])}>
                  <Trash2 size={14} /> Kontakt löschen
                </button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>


      {/* ── Create / Edit Modal ─────────────────────────────────────────── */}
      {(showCreateModal || showEditModal) && (
        <Modal title={showCreateModal ? "Neuer Kontakt" : "Kontakt bearbeiten"} onClose={() => { setShowCreateModal(false); setShowEditModal(false); resetForm(); }} size="lg">
          {/* Duplicate Warning */}
          {showDuplicateWarning && formDuplicates.length > 0 && (
            <div style={{ padding: 14, borderRadius: 10, background: `${T.warning}15`, border: `1px solid ${T.warning}40`, marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <AlertTriangle size={16} style={{ color: T.warning }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: T.warning }}>Mögliche Duplikate gefunden!</span>
              </div>
              {formDuplicates.map((dup: any, i: number) => (
                <div key={i} style={{ padding: 8, borderRadius: 8, background: T.surface, marginBottom: 6, fontSize: 12 }}>
                  <strong>{dup.full_name || `${dup.first_name} ${dup.last_name}`}</strong> – {dup.email || dup.phone || ""}
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button style={{ ...S.actionBtn, fontSize: 12 }} onClick={() => handleCreate(true)}>Trotzdem erstellen</button>
                <button style={{ ...S.filterBtn, fontSize: 12 }} onClick={() => { setShowDuplicateWarning(false); setFormDuplicates([]); }}>Abbrechen</button>
              </div>
            </div>
          )}
          {formError && <div style={{ padding: 10, borderRadius: 8, background: `${T.danger}15`, color: T.danger, fontSize: 12, marginBottom: 14 }}>{formError}</div>}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div style={S.formGroup}><label style={S.formLabel}>Vorname *</label><input style={S.formInput} value={formData.first_name} onChange={(e) => setFormData((p: any) => ({ ...p, first_name: e.target.value }))} /></div>
            <div style={S.formGroup}><label style={S.formLabel}>Nachname *</label><input style={S.formInput} value={formData.last_name} onChange={(e) => setFormData((p: any) => ({ ...p, last_name: e.target.value }))} /></div>
            <div style={S.formGroup}><label style={S.formLabel}>E-Mail</label><input style={S.formInput} type="email" value={formData.email} onChange={(e) => setFormData((p: any) => ({ ...p, email: e.target.value }))} /></div>
            <div style={S.formGroup}><label style={S.formLabel}>Telefon</label><input style={S.formInput} value={formData.phone} onChange={(e) => setFormData((p: any) => ({ ...p, phone: e.target.value }))} /></div>
            <div style={S.formGroup}><label style={S.formLabel}>Firma</label><input style={S.formInput} value={formData.company} onChange={(e) => setFormData((p: any) => ({ ...p, company: e.target.value }))} /></div>
            <div style={S.formGroup}><label style={S.formLabel}>Position</label><input style={S.formInput} value={formData.job_title} onChange={(e) => setFormData((p: any) => ({ ...p, job_title: e.target.value }))} /></div>
            <div style={S.formGroup}>
              <label style={S.formLabel}>Lifecycle-Phase</label>
              <select style={S.formSelect} value={formData.lifecycle_stage} onChange={(e) => setFormData((p: any) => ({ ...p, lifecycle_stage: e.target.value }))}>
                {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (<option key={key} value={key}>{label}</option>))}
              </select>
            </div>
            <div style={S.formGroup}>
              <label style={S.formLabel}>Quelle</label>
              <select style={S.formSelect} value={formData.source} onChange={(e) => setFormData((p: any) => ({ ...p, source: e.target.value }))}>
                {Object.entries(SOURCE_LABELS).map(([key, label]) => (<option key={key} value={key}>{label}</option>))}
              </select>
            </div>
            <div style={S.formGroup}>
              <label style={S.formLabel}>Geschlecht</label>
              <select style={S.formSelect} value={formData.gender} onChange={(e) => setFormData((p: any) => ({ ...p, gender: e.target.value }))}>
                <option value="">–</option><option value="male">Männlich</option><option value="female">Weiblich</option><option value="diverse">Divers</option>
              </select>
            </div>
            <div style={S.formGroup}><label style={S.formLabel}>Geburtsdatum</label><input style={S.formInput} type="date" value={formData.date_of_birth} onChange={(e) => setFormData((p: any) => ({ ...p, date_of_birth: e.target.value }))} /></div>
            <div style={S.formGroup}>
              <label style={S.formLabel}>Sprache</label>
              <select style={S.formSelect} value={formData.preferred_language} onChange={(e) => setFormData((p: any) => ({ ...p, preferred_language: e.target.value }))}>
                <option value="de">Deutsch</option><option value="en">English</option><option value="fr">Français</option><option value="es">Español</option>
              </select>
            </div>
            <div style={S.formGroup}><label style={S.formLabel}>Tags (kommagetrennt)</label><input style={S.formInput} value={formData.tags} onChange={(e) => setFormData((p: any) => ({ ...p, tags: e.target.value }))} placeholder="VIP, Premium" /></div>
          </div>
          <div style={{ marginTop: 14 }}>
            <label style={S.formLabel}>DSGVO-Einwilligungen</label>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              {[{ key: "consent_email", label: "E-Mail" }, { key: "consent_sms", label: "SMS" }, { key: "consent_phone", label: "Telefon" }, { key: "consent_whatsapp", label: "WhatsApp" }].map(c => (
                <label key={c.key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, cursor: "pointer" }}>
                  <input type="checkbox" checked={formData[c.key]} onChange={(e) => setFormData((p: any) => ({ ...p, [c.key]: e.target.checked }))} style={{ accentColor: T.accent }} />
                  {c.label}
                </label>
              ))}
            </div>
          </div>
          {showCreateModal && (
            <div style={S.formGroup}>
              <label style={S.formLabel}>Notiz</label>
              <textarea style={{ ...S.formInput, minHeight: 60, resize: "vertical" }} value={formData.notes} onChange={(e) => setFormData((p: any) => ({ ...p, notes: e.target.value }))} placeholder="Optionale Notiz..." />
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            <button style={S.filterBtn} onClick={() => { setShowCreateModal(false); setShowEditModal(false); resetForm(); }}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: formLoading ? 0.6 : 1 }} disabled={formLoading} onClick={showCreateModal ? () => handleCreate(false) : handleUpdate}>
              {formLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Save size={14} />}
              {showCreateModal ? "Erstellen" : "Speichern"}
            </button>
          </div>
        </Modal>
      )}

      {/* ── Bulk Edit Modal ─────────────────────────────────────────────── */}
      {showBulkModal && (
        <Modal title={`${selectedIds.size} Kontakte bearbeiten`} onClose={() => setShowBulkModal(false)}>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Lifecycle-Phase ändern</label>
            <select style={S.formSelect} value={bulkLifecycle} onChange={(e) => setBulkLifecycle(e.target.value)}>
              <option value="">– Nicht ändern –</option>
              {Object.entries(LIFECYCLE_STAGES).map(([key, { label }]) => (<option key={key} value={key}>{label}</option>))}
            </select>
          </div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Tags hinzufügen (kommagetrennt)</label>
            <input style={S.formInput} value={bulkAddTags} onChange={(e) => setBulkAddTags(e.target.value)} placeholder="VIP, Premium" />
          </div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Tags entfernen (kommagetrennt)</label>
            <input style={S.formInput} value={bulkRemoveTags} onChange={(e) => setBulkRemoveTags(e.target.value)} placeholder="Alt, Inaktiv" />
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
            <button style={S.filterBtn} onClick={() => setShowBulkModal(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: bulkLoading ? 0.6 : 1 }} disabled={bulkLoading} onClick={handleBulkUpdate}>
              {bulkLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Check size={14} />} Anwenden
            </button>
          </div>
        </Modal>
      )}

      {/* ── Segment Builder Modal ───────────────────────────────────────── */}
      {showSegmentBuilder && (
        <Modal title="Segment-Builder" onClose={() => setShowSegmentBuilder(false)} size="xl">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
            <div style={S.formGroup}><label style={S.formLabel}>Segment-Name *</label><input style={S.formInput} value={segBuilderName} onChange={(e) => setSegBuilderName(e.target.value)} placeholder="z.B. VIP-Kunden" /></div>
            <div style={S.formGroup}><label style={S.formLabel}>Beschreibung</label><input style={S.formInput} value={segBuilderDesc} onChange={(e) => setSegBuilderDesc(e.target.value)} placeholder="Optional..." /></div>
          </div>

          {/* Group Connector */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: T.textMuted }}>Gruppen verknüpfen mit:</span>
            <button style={{ ...S.connectorBadge, background: segBuilderConnector === "AND" ? T.accentDim : T.surfaceAlt, color: segBuilderConnector === "AND" ? T.accent : T.textDim, border: `1px solid ${segBuilderConnector === "AND" ? T.accent : T.border}` }}
              onClick={() => setSegBuilderConnector(segBuilderConnector === "AND" ? "OR" : "AND")}>
              {segBuilderConnector}
            </button>
          </div>

          {/* Rule Groups */}
          {segBuilderGroups.map((group, gi) => (
            <div key={gi} style={S.ruleGroupBox}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Layers size={14} style={{ color: T.accent }} />
                  <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>Regelgruppe {gi + 1}</span>
                  <button style={{ ...S.connectorBadge, background: group.connector === "AND" ? `${T.accent}15` : `${T.warning}15`, color: group.connector === "AND" ? T.accent : T.warning, border: `1px solid ${group.connector === "AND" ? `${T.accent}40` : `${T.warning}40`}` }}
                    onClick={() => toggleGroupConnector(gi)}>
                    {group.connector}
                  </button>
                </div>
                {segBuilderGroups.length > 1 && (
                  <button style={{ background: "none", border: "none", cursor: "pointer", color: T.danger, padding: 4 }} onClick={() => removeRuleGroup(gi)}><Trash2 size={14} /></button>
                )}
              </div>

              {group.rules.map((rule, ri) => {
                const fieldDef = SEGMENT_FIELDS.find(f => f.value === rule.field);
                const fieldType = fieldDef?.type || "text";
                const ops = OPERATORS[fieldType] || OPERATORS.text;
                return (
                  <div key={ri} style={S.ruleRow}>
                    <select style={{ ...S.formSelect, flex: 2, padding: "6px 8px", fontSize: 12 }} value={rule.field} onChange={(e) => updateRule(gi, ri, { field: e.target.value, operator: "equals", value: "" })}>
                      {SEGMENT_FIELDS.map(f => (<option key={f.value} value={f.value}>{f.label}</option>))}
                    </select>
                    <select style={{ ...S.formSelect, flex: 1.5, padding: "6px 8px", fontSize: 12 }} value={rule.operator} onChange={(e) => updateRule(gi, ri, { operator: e.target.value })}>
                      {ops.map(op => (<option key={op.value} value={op.value}>{op.label}</option>))}
                    </select>
                    {!["is_empty", "is_not_empty", "is_true", "is_false"].includes(rule.operator) && (
                      fieldDef?.options ? (
                        <select style={{ ...S.formSelect, flex: 2, padding: "6px 8px", fontSize: 12 }} value={rule.value} onChange={(e) => updateRule(gi, ri, { value: e.target.value })}>
                          <option value="">Wählen...</option>
                          {fieldDef.options.map((opt: string) => (<option key={opt} value={opt}>{LIFECYCLE_STAGES[opt]?.label || SOURCE_LABELS[opt] || opt}</option>))}
                        </select>
                      ) : (
                        <input style={{ ...S.formInput, flex: 2, padding: "6px 8px", fontSize: 12 }} value={rule.value} onChange={(e) => updateRule(gi, ri, { value: e.target.value })} placeholder="Wert..." type={fieldType === "number" ? "number" : fieldType === "date" ? "date" : "text"} />
                      )
                    )}
                    {group.rules.length > 1 && (
                      <button style={{ background: "none", border: "none", cursor: "pointer", color: T.textDim, padding: 4, flexShrink: 0 }} onClick={() => removeRuleFromGroup(gi, ri)}><X size={14} /></button>
                    )}
                  </div>
                );
              })}
              <button style={{ ...S.filterBtn, padding: "6px 10px", fontSize: 11, marginTop: 4 }} onClick={() => addRuleToGroup(gi)}>
                <Plus size={12} /> Regel hinzufügen
              </button>
            </div>
          ))}

          <button style={{ ...S.actionBtnSecondary, marginBottom: 16 }} onClick={addRuleGroup}>
            <Layers size={14} /> Regelgruppe hinzufügen
          </button>

          {/* Preview */}
          {segBuilderPreview && (
            <div style={{ padding: 14, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}`, marginBottom: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <Eye size={14} style={{ color: T.accent }} />
                <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Vorschau: {segBuilderPreview.count} Kontakte</span>
              </div>
              {segBuilderPreview.contacts.length > 0 && (
                <div style={{ maxHeight: 200, overflowY: "auto" }}>
                  {segBuilderPreview.contacts.slice(0, 10).map(c => (
                    <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: `1px solid ${T.border}` }}>
                      <div style={{ ...S.avatar, width: 24, height: 24, fontSize: 9, background: `${getAvatarColor(c.full_name)}22`, color: getAvatarColor(c.full_name) }}>
                        {getInitials(c.first_name, c.last_name)}
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{c.full_name}</span>
                      <span style={{ fontSize: 11, color: T.textDim }}>{c.email || ""}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            <button style={S.filterBtn} onClick={() => setShowSegmentBuilder(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtnSecondary }} onClick={previewSegment} disabled={segBuilderLoading}>
              {segBuilderLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Eye size={14} />} Vorschau
            </button>
            <button style={{ ...S.actionBtn, opacity: segBuilderName.trim() ? 1 : 0.5 }} disabled={!segBuilderName.trim()} onClick={saveSegmentFromBuilder}>
              <Save size={14} /> Segment speichern
            </button>
          </div>
        </Modal>
      )}

      {/* ── Merge Wizard Modal ──────────────────────────────────────────── */}
      {showMergeWizard && mergeSource && mergeTarget && (
        <Modal title="Kontakte zusammenführen" onClose={() => { setShowMergeWizard(false); setMergeSource(null); setMergeTarget(null); }} size="xl">
          <div style={{ padding: 14, borderRadius: 10, background: `${T.warning}10`, border: `1px solid ${T.warning}30`, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={16} style={{ color: T.warning }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.warning }}>Kontakt A wird in Kontakt B zusammengeführt. Kontakt A wird danach gelöscht.</span>
            </div>
          </div>

          {/* Contact Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 60px 1fr", gap: 16, marginBottom: 20 }}>
            <div style={S.mergeCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <div style={{ ...S.avatar, width: 36, height: 36, fontSize: 12, background: `${getAvatarColor(mergeSource.full_name)}22`, color: getAvatarColor(mergeSource.full_name) }}>
                  {getInitials(mergeSource.first_name, mergeSource.last_name)}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{mergeSource.full_name}</div>
                  <div style={{ fontSize: 11, color: T.textDim }}>Kontakt A (wird gelöscht)</div>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
              <GitMerge size={24} style={{ color: T.accent }} />
            </div>
            <div style={S.mergeCard}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <div style={{ ...S.avatar, width: 36, height: 36, fontSize: 12, background: `${getAvatarColor(mergeTarget.full_name)}22`, color: getAvatarColor(mergeTarget.full_name) }}>
                  {getInitials(mergeTarget.first_name, mergeTarget.last_name)}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{mergeTarget.full_name}</div>
                  <div style={{ fontSize: 11, color: T.accent, fontWeight: 600 }}>Kontakt B (bleibt erhalten)</div>
                </div>
              </div>
            </div>
          </div>

          {/* Field Choices */}
          <div style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 10 }}>Feldauswahl</div>
          {Object.entries(mergeFieldChoices).map(([field, choice]) => {
            const sourceVal = (mergeSource as any)[field] || "–";
            const targetVal = (mergeTarget as any)[field] || "–";
            const label = { first_name: "Vorname", last_name: "Nachname", email: "E-Mail", phone: "Telefon", company: "Firma", job_title: "Position", lifecycle_stage: "Lifecycle", gender: "Geschlecht", date_of_birth: "Geburtsdatum", preferred_language: "Sprache" }[field] || field;
            return (
              <div key={field} style={S.mergeFieldRow}>
                <span style={{ fontSize: 11, fontWeight: 700, color: T.textMuted }}>{label}</span>
                <button style={{ padding: "4px 8px", borderRadius: 6, border: `1px solid ${choice === "source" ? T.accent : T.border}`, background: choice === "source" ? T.accentDim : T.surfaceAlt, color: choice === "source" ? T.accent : T.textDim, fontSize: 11, cursor: "pointer", textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  onClick={() => setMergeFieldChoices(prev => ({ ...prev, [field]: "source" }))}>
                  {field === "lifecycle_stage" ? LIFECYCLE_STAGES[sourceVal]?.label || sourceVal : sourceVal}
                </button>
                <ArrowLeftRight size={14} style={{ color: T.textDim, justifySelf: "center" }} />
                <button style={{ padding: "4px 8px", borderRadius: 6, border: `1px solid ${choice === "target" ? T.accent : T.border}`, background: choice === "target" ? T.accentDim : T.surfaceAlt, color: choice === "target" ? T.accent : T.textDim, fontSize: 11, cursor: "pointer", textAlign: "left", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  onClick={() => setMergeFieldChoices(prev => ({ ...prev, [field]: "target" }))}>
                  {field === "lifecycle_stage" ? LIFECYCLE_STAGES[targetVal]?.label || targetVal : targetVal}
                </button>
              </div>
            );
          })}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            <button style={S.filterBtn} onClick={() => { setShowMergeWizard(false); setMergeSource(null); setMergeTarget(null); }}>Abbrechen</button>
            <button style={S.actionBtn} onClick={executeMerge}><GitMerge size={14} /> Zusammenführen</button>
          </div>
        </Modal>
      )}


      {/* ── Duplicates Modal ────────────────────────────────────────────── */}
      {showDuplicatesModal && (
        <Modal title="Duplikat-Erkennung" onClose={() => setShowDuplicatesModal(false)} size="lg">
          {duplicatesLoading ? (
            <div style={{ textAlign: "center", padding: 40 }}><Loader2 size={24} style={{ color: T.accent, animation: "spin 1s linear infinite" }} /></div>
          ) : duplicateGroups.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: T.textDim }}>
              <CheckCircle2 size={40} style={{ marginBottom: 12, color: T.success, opacity: 0.5 }} />
              <div style={{ fontSize: 14, fontWeight: 600 }}>Keine Duplikate gefunden</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Alle Kontakte sind einzigartig.</div>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 12, color: T.textMuted, marginBottom: 14 }}>{duplicateGroups.length} Duplikat-Gruppen gefunden</div>
              {duplicateGroups.map((group, gi) => (
                <div key={gi} style={{ padding: 14, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}`, marginBottom: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                    <Copy size={14} style={{ color: T.warning }} />
                    <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>
                      {matchReasonLabel(group.match_type)}: {group.match_value}
                    </span>
                    <Badge variant={group.confidence >= 0.9 ? "success" : group.confidence >= 0.7 ? "warning" : "default"}>
                      {confidenceLabel(group.confidence)} ({(group.confidence * 100).toFixed(0)}%)
                    </Badge>
                  </div>
                  {group.contacts.map((contact, ci) => (
                    <div key={contact.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: ci < group.contacts.length - 1 ? `1px solid ${T.border}` : "none" }}>
                      <div style={{ ...S.avatar, width: 28, height: 28, fontSize: 10, background: `${getAvatarColor(contact.full_name)}22`, color: getAvatarColor(contact.full_name) }}>
                        {getInitials(contact.first_name, contact.last_name)}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{contact.full_name}</div>
                        <div style={{ fontSize: 11, color: T.textDim }}>{contact.email || ""} {contact.phone ? `• ${contact.phone}` : ""}</div>
                      </div>
                      <Badge variant="default">{LIFECYCLE_STAGES[contact.lifecycle_stage]?.label || contact.lifecycle_stage}</Badge>
                    </div>
                  ))}
                  {group.contacts.length >= 2 && isAdmin && (
                    <div style={{ marginTop: 10 }}>
                      <button style={{ ...S.actionBtnSecondary, padding: "6px 12px", fontSize: 11 }} onClick={() => initMerge(group.contacts[0], group.contacts[1])}>
                        <GitMerge size={12} /> Zusammenführen
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Modal>
      )}

      {/* ── Import V2 Wizard Modal ──────────────────────────────────────── */}
      {showImportModal && (
        <Modal title="Kontakte importieren" onClose={() => setShowImportModal(false)} size="xl">
          {/* Wizard Steps */}
          <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
            {[
              { step: 1, label: "Datei hochladen", icon: Upload },
              { step: 2, label: "Spalten zuordnen", icon: ArrowLeftRight },
              { step: 3, label: "Vorschau", icon: Eye },
              { step: 4, label: "Import", icon: Check },
            ].map(({ step, label, icon: Icon }) => (
              <div key={step} style={{
                ...S.wizardStep,
                ...(importStep === step ? S.wizardStepActive : importStep > step ? S.wizardStepDone : S.wizardStepPending),
                flex: 1, justifyContent: "center",
              }}>
                <Icon size={14} /> {label}
              </div>
            ))}
          </div>

          {/* Step 1: File Upload */}
          {importStep === 1 && (
            <div style={{ textAlign: "center", padding: 40 }}>
              <div style={{ width: 80, height: 80, borderRadius: 20, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
                <FileSpreadsheet size={36} style={{ color: T.accent }} />
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text, marginBottom: 6 }}>CSV-Datei hochladen</div>
              <div style={{ fontSize: 12, color: T.textDim, marginBottom: 20 }}>Unterstützte Formate: CSV (UTF-8)</div>
              <label style={{ ...S.actionBtn, display: "inline-flex", cursor: "pointer" }}>
                <Upload size={14} /> Datei auswählen
                <input type="file" accept=".csv" style={{ display: "none" }} onChange={(e) => { if (e.target.files?.[0]) handleImportUpload(e.target.files[0]); }} />
              </label>
              {importLoading && <div style={{ marginTop: 16 }}><Loader2 size={24} style={{ color: T.accent, animation: "spin 1s linear infinite" }} /></div>}
            </div>
          )}

          {/* Step 2: Column Mapping */}
          {importStep === 2 && importPreview && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 12 }}>
                {importPreview.total_rows} Zeilen erkannt • {importPreview.columns.length} Spalten
              </div>
              <div style={{ ...S.mappingRow, fontWeight: 700, fontSize: 11, color: T.textMuted, borderBottom: `2px solid ${T.border}` }}>
                <span>CSV-Spalte</span><span></span><span>Kontakt-Feld</span><span>Schlüssel</span>
              </div>
              {importMappings.map((mapping, i) => (
                <div key={i} style={S.mappingRow}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{mapping.csv_column}</span>
                  <ArrowRight size={14} style={{ color: T.textDim, justifySelf: "center" }} />
                  <select style={{ ...S.formSelect, padding: "6px 8px", fontSize: 12 }} value={mapping.contact_field}
                    onChange={(e) => setImportMappings(prev => prev.map((m, mi) => mi === i ? { ...m, contact_field: e.target.value } : m))}>
                    {CONTACT_IMPORT_FIELDS.map(f => (<option key={f.value} value={f.value}>{f.label}</option>))}
                  </select>
                  <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, cursor: "pointer", justifySelf: "center" }}>
                    <input type="checkbox" checked={mapping.is_key}
                      onChange={(e) => setImportMappings(prev => prev.map((m, mi) => mi === i ? { ...m, is_key: e.target.checked } : m))}
                      style={{ accentColor: T.accent }} />
                  </label>
                </div>
              ))}

              {/* Sample Data Preview */}
              {importPreview.sample_rows.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 8 }}>Beispieldaten (erste 3 Zeilen)</div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={S.previewTable}>
                      <thead>
                        <tr>{importPreview.columns.map(col => (<th key={col} style={S.previewTh}>{col}</th>))}</tr>
                      </thead>
                      <tbody>
                        {importPreview.sample_rows.slice(0, 3).map((row, ri) => (
                          <tr key={ri}>{importPreview!.columns.map(col => (<td key={col} style={S.previewTd}>{row[col] || "–"}</td>))}</tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
                <button style={S.filterBtn} onClick={() => setImportStep(1)}>Zurück</button>
                <button style={S.actionBtn} onClick={() => setImportStep(3)}><Eye size={14} /> Vorschau</button>
              </div>
            </div>
          )}

          {/* Step 3: Preview */}
          {importStep === 3 && importPreview && (
            <div>
              <div style={{ padding: 14, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}`, marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 8 }}>Import-Zusammenfassung</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <div style={{ fontSize: 12, color: T.textMuted }}>Datei: <strong style={{ color: T.text }}>{importFile?.name}</strong></div>
                  <div style={{ fontSize: 12, color: T.textMuted }}>Zeilen: <strong style={{ color: T.text }}>{importPreview.total_rows}</strong></div>
                  <div style={{ fontSize: 12, color: T.textMuted }}>Zugeordnete Felder: <strong style={{ color: T.text }}>{importMappings.filter(m => m.contact_field !== "__skip__").length}</strong></div>
                  <div style={{ fontSize: 12, color: T.textMuted }}>Schlüsselfelder: <strong style={{ color: T.text }}>{importMappings.filter(m => m.is_key).length}</strong></div>
                </div>
              </div>

              <div style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, marginBottom: 8 }}>Feld-Zuordnungen</div>
              {importMappings.filter(m => m.contact_field !== "__skip__").map((m, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", fontSize: 12, borderBottom: `1px solid ${T.border}` }}>
                  <span style={{ color: T.textDim, minWidth: 120 }}>{m.csv_column}</span>
                  <ArrowRight size={12} style={{ color: T.accent }} />
                  <span style={{ fontWeight: 600, color: T.text }}>{CONTACT_IMPORT_FIELDS.find(f => f.value === m.contact_field)?.label || m.contact_field}</span>
                  {m.is_key && <Badge variant="accent">Schlüssel</Badge>}
                </div>
              ))}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20 }}>
                <button style={S.filterBtn} onClick={() => setImportStep(2)}>Zurück</button>
                <button style={S.actionBtn} onClick={executeImportV2}><Upload size={14} /> Import starten</button>
              </div>
            </div>
          )}

          {/* Step 4: Progress / Result */}
          {importStep === 4 && (
            <div style={{ textAlign: "center", padding: 30 }}>
              {importResult ? (
                <div>
                  <CheckCircle2 size={48} style={{ color: T.success, marginBottom: 16 }} />
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 8 }}>Import abgeschlossen</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 16 }}>
                    <div style={{ padding: 12, borderRadius: 10, background: `${T.success}15` }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: T.success }}>{importResult.created || 0}</div>
                      <div style={{ fontSize: 11, color: T.textMuted }}>Erstellt</div>
                    </div>
                    <div style={{ padding: 12, borderRadius: 10, background: `${T.info}15` }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: T.info }}>{importResult.updated || 0}</div>
                      <div style={{ fontSize: 11, color: T.textMuted }}>Aktualisiert</div>
                    </div>
                    <div style={{ padding: 12, borderRadius: 10, background: `${T.danger}15` }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: T.danger }}>{importResult.errors || 0}</div>
                      <div style={{ fontSize: 11, color: T.textMuted }}>Fehler</div>
                    </div>
                  </div>
                  <button style={{ ...S.actionBtn, marginTop: 20 }} onClick={() => setShowImportModal(false)}>Schließen</button>
                </div>
              ) : (
                <div>
                  <Loader2 size={36} style={{ color: T.accent, animation: "spin 1s linear infinite", marginBottom: 16 }} />
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.text, marginBottom: 8 }}>Import läuft...</div>
                  <div style={S.progressBar}>
                    <div style={{ ...S.progressFill, width: `${importProgress}%` }} />
                  </div>
                  <div style={{ fontSize: 12, color: T.textDim, marginTop: 8 }}>{importProgress}% abgeschlossen</div>
                </div>
              )}
            </div>
          )}
        </Modal>
      )}

      {/* ── Export V2 Modal ─────────────────────────────────────────────── */}
      {showExportModal && (
        <Modal title="Kontakte exportieren" onClose={() => setShowExportModal(false)}>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Format</label>
            <select style={S.formSelect} value={exportFormat} onChange={(e) => setExportFormat(e.target.value as "csv" | "xlsx")}>
              <option value="csv">CSV</option>
              <option value="xlsx">Excel (XLSX)</option>
            </select>
          </div>
          <div style={S.formGroup}>
            <label style={S.formLabel}>Segment (optional)</label>
            <select style={S.formSelect} value={exportSegmentId || ""} onChange={(e) => setExportSegmentId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Alle Kontakte</option>
              {segments.map(seg => (<option key={seg.id} value={seg.id}>{seg.name} ({seg.contact_count})</option>))}
            </select>
          </div>
          <div style={{ padding: 12, borderRadius: 8, background: T.surfaceAlt, fontSize: 12, color: T.textDim, marginBottom: 14 }}>
            {activeFilterCount > 0 ? `Aktive Filter werden angewendet (${activeFilterCount} Filter aktiv)` : "Alle Kontakte werden exportiert."}
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
            <button style={S.filterBtn} onClick={() => setShowExportModal(false)}>Abbrechen</button>
            <button style={{ ...S.actionBtn, opacity: exportLoading ? 0.6 : 1 }} disabled={exportLoading} onClick={handleExportV2}>
              {exportLoading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Download size={14} />} Exportieren
            </button>
          </div>
        </Modal>
      )}

      {/* ── Custom Fields Admin Modal ───────────────────────────────────── */}
      {showCustomFieldsAdmin && (
        <Modal title="Benutzerdefinierte Felder verwalten" onClose={() => setShowCustomFieldsAdmin(false)} size="lg">
          {/* Existing Fields */}
          {customFields.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 10 }}>Vorhandene Felder</div>
              {customFields.map(cf => {
                const TypeIcon = CUSTOM_FIELD_TYPES.find(t => t.value === cf.field_type)?.icon || Type;
                return (
                  <div key={cf.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", borderRadius: 8, background: T.surfaceAlt, marginBottom: 8, border: `1px solid ${T.border}` }}>
                    <TypeIcon size={16} style={{ color: T.accent }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{cf.field_label}</div>
                      <div style={{ fontSize: 11, color: T.textDim }}>{cf.field_name} • {CUSTOM_FIELD_TYPES.find(t => t.value === cf.field_type)?.label || cf.field_type} {cf.is_required && "• Pflichtfeld"}</div>
                    </div>
                    <button style={{ background: "none", border: "none", cursor: "pointer", color: T.danger, padding: 6 }} onClick={() => handleDeleteCustomField(cf.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Create New Field */}
          <div style={{ padding: 16, borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: T.textMuted, textTransform: "uppercase", marginBottom: 12 }}>Neues Feld erstellen</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div style={S.formGroup}>
                <label style={S.formLabel}>Feldname (intern) *</label>
                <input style={S.formInput} value={newCfName} onChange={(e) => setNewCfName(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))} placeholder="z.B. mitgliedsnummer" />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>Anzeigename *</label>
                <input style={S.formInput} value={newCfLabel} onChange={(e) => setNewCfLabel(e.target.value)} placeholder="z.B. Mitgliedsnummer" />
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>Feldtyp</label>
                <select style={S.formSelect} value={newCfType} onChange={(e) => setNewCfType(e.target.value)}>
                  {CUSTOM_FIELD_TYPES.map(t => (<option key={t.value} value={t.value}>{t.label}</option>))}
                </select>
              </div>
              <div style={S.formGroup}>
                <label style={S.formLabel}>Pflichtfeld</label>
                <label style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 0", fontSize: 12, cursor: "pointer" }}>
                  <input type="checkbox" checked={newCfRequired} onChange={(e) => setNewCfRequired(e.target.checked)} style={{ accentColor: T.accent }} />
                  Ja, dieses Feld ist erforderlich
                </label>
              </div>
            </div>
            {newCfType === "select" && (
              <div style={S.formGroup}>
                <label style={S.formLabel}>Auswahloptionen (kommagetrennt)</label>
                <input style={S.formInput} value={newCfOptions} onChange={(e) => setNewCfOptions(e.target.value)} placeholder="Option 1, Option 2, Option 3" />
              </div>
            )}
            <button style={{ ...S.actionBtn, marginTop: 10, opacity: newCfName.trim() && newCfLabel.trim() ? 1 : 0.5 }} disabled={!newCfName.trim() || !newCfLabel.trim()} onClick={handleCreateCustomField}>
              <Plus size={14} /> Feld erstellen
            </button>
          </div>
        </Modal>
      )}

      {/* ── CSS Keyframes ───────────────────────────────────────────────── */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
