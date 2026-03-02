"use client";

import React, { useState, useEffect, useCallback, useMemo, Fragment } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database, RefreshCw, Plus, Search, Check, CheckCircle2,
  AlertCircle, Loader2, Settings, X, ChevronDown, ChevronRight,
  Play, Pause, Trash2, Clock, TrendingUp, ArrowRight, ArrowLeft,
  Eye, EyeOff, Shield, Zap, Activity, BarChart3, Filter,
  ExternalLink, Copy, HelpCircle, Info, Power, Link2,
  ShoppingBag, Users, Brain, Globe, PlugZap, Sparkles,
  ArrowUpDown, History, Download, Upload, AlertTriangle,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { FeatureGate } from "@/components/FeatureGate";
import { T } from "@/lib/tokens";
import { useI18n } from "@/lib/i18n/LanguageContext";
import {
  useAvailableIntegrations,
  useConfiguredIntegrations,
  useSyncHistory,
  useTestConnection,
  useSaveIntegration,
  useToggleIntegration,
  useDeleteIntegration,
  useRunSync,
  type AvailableIntegration,
  type TenantIntegration,
  type SyncLogEntry,
  type ConfigField,
} from "@/lib/sync-hooks";

// ══════════════════════════════════════════════════════════════════════════════
// CONSTANTS & HELPERS
// ══════════════════════════════════════════════════════════════════════════════

const INTEGRATION_ICONS: Record<string, { icon: React.ReactNode; color: string }> = {
  magicline: { icon: <Activity size={22} />, color: "#00D68F" },
  shopify: { icon: <ShoppingBag size={22} />, color: "#96BF48" },
  woocommerce: { icon: <Globe size={22} />, color: "#7B2D8E" },
  hubspot: { icon: <Users size={22} />, color: "#FF7A59" },
  salesforce: { icon: <Brain size={22} />, color: "#00A1E0" },
  manual: { icon: <Upload size={22} />, color: T.accent },
  api: { icon: <PlugZap size={22} />, color: T.info },
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  connected: { label: "Verbunden", color: T.success, bg: T.successDim },
  configured: { label: "Konfiguriert", color: T.info, bg: T.infoDim },
  syncing: { label: "Synchronisiert...", color: T.warning, bg: T.warningDim },
  error: { label: "Fehler", color: T.danger, bg: T.dangerDim },
  disconnected: { label: "Nicht verbunden", color: T.textDim, bg: "rgba(90,92,107,0.12)" },
};

function getIntegrationVisual(id: string) {
  return INTEGRATION_ICONS[id] || { icon: <Database size={22} />, color: T.accent };
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return "Nie";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Gerade eben";
  if (mins < 60) return `Vor ${mins} Min.`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `Vor ${hours} Std.`;
  const days = Math.floor(hours / 24);
  return `Vor ${days} Tag${days > 1 ? "en" : ""}`;
}

type ViewState = "dashboard" | "marketplace" | "setup" | "detail" | "history";

// ══════════════════════════════════════════════════════════════════════════════
// STYLES
// ══════════════════════════════════════════════════════════════════════════════

const S: Record<string, React.CSSProperties> = {
  page: { padding: "24px 32px", maxWidth: 1400, margin: "0 auto", minHeight: "100vh" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 },
  headerLeft: { display: "flex", flexDirection: "column", gap: 4 },
  title: { fontSize: 24, fontWeight: 700, color: T.text, margin: 0, display: "flex", alignItems: "center", gap: 10 },
  subtitle: { fontSize: 14, color: T.textMuted, margin: 0 },
  headerActions: { display: "flex", gap: 10, alignItems: "center" },
  tabBar: { display: "flex", gap: 2, background: T.surface, borderRadius: 10, padding: 3, marginBottom: 24, border: `1px solid ${T.border}` },
  tab: { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer", border: "none", transition: "all 0.2s", display: "flex", alignItems: "center", gap: 6 },
  tabActive: { background: T.accent, color: "#fff" },
  tabInactive: { background: "transparent", color: T.textMuted },
  statsRow: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 24 },
  statCard: { padding: "16px 20px", borderRadius: 12, border: `1px solid ${T.border}`, background: T.surface },
  statValue: { fontSize: 28, fontWeight: 700, color: T.text, margin: 0 },
  statLabel: { fontSize: 12, color: T.textMuted, marginTop: 2 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 },
  card: { padding: 20, borderRadius: 14, border: `1px solid ${T.border}`, background: T.surface, cursor: "pointer", transition: "all 0.2s" },
  cardHeader: { display: "flex", alignItems: "center", gap: 12, marginBottom: 12 },
  cardIcon: { width: 44, height: 44, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center" },
  cardTitle: { fontSize: 15, fontWeight: 600, color: T.text },
  cardDesc: { fontSize: 13, color: T.textMuted, lineHeight: 1.5 },
  cardFooter: { display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14, paddingTop: 12, borderTop: `1px solid ${T.border}` },
  btn: { padding: "8px 16px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer", border: "none", display: "flex", alignItems: "center", gap: 6, transition: "all 0.2s" },
  btnPrimary: { background: T.accent, color: "#fff" },
  btnSecondary: { background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` },
  btnDanger: { background: T.dangerDim, color: T.danger },
  btnSmall: { padding: "5px 10px", fontSize: 12 },
  badge: { padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 },
  // Setup Wizard
  wizardOverlay: { position: "fixed" as const, inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" },
  wizardPanel: { background: T.bg, borderRadius: 16, border: `1px solid ${T.border}`, width: "100%", maxWidth: 640, maxHeight: "90vh", overflow: "auto", padding: 0 },
  wizardHeader: { padding: "20px 24px", borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" },
  wizardBody: { padding: 24 },
  wizardFooter: { padding: "16px 24px", borderTop: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" },
  fieldGroup: { marginBottom: 16 },
  fieldLabel: { display: "block", fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 6 },
  fieldHelp: { fontSize: 11, color: T.textDim, marginTop: 4 },
  input: { width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 14, outline: "none", boxSizing: "border-box" as const },
  select: { width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontSize: 14, outline: "none", boxSizing: "border-box" as const },
  // Detail View
  detailHeader: { display: "flex", alignItems: "center", gap: 16, marginBottom: 24 },
  detailStats: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 },
  logTable: { width: "100%", borderCollapse: "collapse" as const },
  logTh: { textAlign: "left" as const, padding: "10px 14px", fontSize: 12, fontWeight: 600, color: T.textMuted, borderBottom: `1px solid ${T.border}` },
  logTd: { padding: "10px 14px", fontSize: 13, color: T.text, borderBottom: `1px solid ${T.border}` },
};

// ══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════════════════

export default function ContactSyncPage() {
  const { t } = useI18n();
  const [view, setView] = useState<ViewState>("dashboard");
  const [selectedIntegration, setSelectedIntegration] = useState<AvailableIntegration | null>(null);
  const [selectedConfigured, setSelectedConfigured] = useState<TenantIntegration | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Data hooks
  const { data: available = [], isLoading: loadingAvailable } = useAvailableIntegrations();
  const { data: configured = [], isLoading: loadingConfigured, refetch: refetchConfigured } = useConfiguredIntegrations();
  const { data: history = [], isLoading: loadingHistory } = useSyncHistory(50);

  // Stats
  const stats = useMemo(() => {
    const active = configured.filter(c => c.enabled).length;
    const errors = configured.filter(c => c.last_sync_status === "error").length;
    const totalSynced = history.reduce((sum, h) => sum + (h.records_created || 0) + (h.records_updated || 0), 0);
    const lastSync = configured.reduce((latest, c) => {
      if (!c.last_sync_at) return latest;
      if (!latest) return c.last_sync_at;
      return new Date(c.last_sync_at) > new Date(latest) ? c.last_sync_at : latest;
    }, null as string | null);
    return { active, errors, totalSynced, lastSync };
  }, [configured, history]);

  const handleSetupComplete = useCallback(() => {
    setView("dashboard");
    setSelectedIntegration(null);
    refetchConfigured();
  }, [refetchConfigured]);

  const handleOpenDetail = useCallback((ti: TenantIntegration) => {
    setSelectedConfigured(ti);
    setView("detail");
  }, []);

  const handleBackToDashboard = useCallback(() => {
    setView("dashboard");
    setSelectedConfigured(null);
    setSelectedIntegration(null);
  }, []);

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.headerLeft}>
          <h1 style={S.title}>
            <Database size={24} style={{ color: T.accent }} />
            Contact Sync
          </h1>
          <p style={S.subtitle}>Verwalten Sie Ihre Datenquellen und Synchronisierungen</p>
        </div>
        <div style={S.headerActions}>
          {view !== "dashboard" && (
            <button style={{ ...S.btn, ...S.btnSecondary }} onClick={handleBackToDashboard}>
              <ArrowLeft size={14} /> Zurück
            </button>
          )}
          <button
            style={{ ...S.btn, ...S.btnPrimary }}
            onClick={() => setView("marketplace")}
          >
            <Plus size={14} /> Integration hinzufügen
          </button>
        </div>
      </div>

      {/* Tab Bar */}
      {view === "dashboard" && (
        <div style={S.tabBar}>
          {[
            { key: "dashboard" as ViewState, label: "Übersicht", icon: <BarChart3 size={14} /> },
            { key: "marketplace" as ViewState, label: "Marketplace", icon: <Plus size={14} /> },
            { key: "history" as ViewState, label: "Sync-Verlauf", icon: <History size={14} /> },
          ].map(tab => (
            <button
              key={tab.key}
              style={{ ...S.tab, ...(view === tab.key ? S.tabActive : S.tabInactive) }}
              onClick={() => setView(tab.key)}
            >
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Content */}
      <AnimatePresence mode="wait">
        {view === "dashboard" && (
          <motion.div key="dashboard" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <DashboardView
              configured={configured}
              stats={stats}
              loading={loadingConfigured}
              onOpenDetail={handleOpenDetail}
              onAddNew={() => setView("marketplace")}
              onViewHistory={() => setView("history")}
            />
          </motion.div>
        )}
        {view === "marketplace" && (
          <motion.div key="marketplace" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <MarketplaceView
              available={available}
              configured={configured}
              loading={loadingAvailable}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              onSelect={(integration) => { setSelectedIntegration(integration); setView("setup"); }}
              onBack={handleBackToDashboard}
            />
          </motion.div>
        )}
        {view === "setup" && selectedIntegration && (
          <motion.div key="setup" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <SetupWizard
              integration={selectedIntegration}
              onComplete={handleSetupComplete}
              onCancel={() => { setView("marketplace"); setSelectedIntegration(null); }}
            />
          </motion.div>
        )}
        {view === "detail" && selectedConfigured && (
          <motion.div key="detail" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <IntegrationDetail
              integration={selectedConfigured}
              onBack={handleBackToDashboard}
              onRefresh={refetchConfigured}
            />
          </motion.div>
        )}
        {view === "history" && (
          <motion.div key="history" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <HistoryView
              history={history}
              loading={loadingHistory}
              onBack={handleBackToDashboard}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// DASHBOARD VIEW
// ══════════════════════════════════════════════════════════════════════════════

function DashboardView({
  configured, stats, loading, onOpenDetail, onAddNew, onViewHistory,
}: {
  configured: TenantIntegration[];
  stats: { active: number; errors: number; totalSynced: number; lastSync: string | null };
  loading: boolean;
  onOpenDetail: (ti: TenantIntegration) => void;
  onAddNew: () => void;
  onViewHistory: () => void;
}) {
  const runSync = useRunSync();

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60, color: T.textMuted }}>
        <Loader2 size={32} style={{ animation: "spin 1s linear infinite" }} />
        <p style={{ marginTop: 12 }}>Lade Integrationen...</p>
      </div>
    );
  }

  if (configured.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <div style={{ width: 80, height: 80, borderRadius: 20, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <Database size={36} style={{ color: T.accent }} />
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>Keine Integrationen konfiguriert</h2>
        <p style={{ fontSize: 14, color: T.textMuted, maxWidth: 400, margin: "0 auto 24px" }}>
          Verbinden Sie Ihre externen Systeme, um Kontaktdaten automatisch zu synchronisieren.
        </p>
        <button style={{ ...S.btn, ...S.btnPrimary, margin: "0 auto" }} onClick={onAddNew}>
          <Plus size={14} /> Erste Integration einrichten
        </button>
      </div>
    );
  }

  return (
    <>
      {/* Stats */}
      <div style={S.statsRow}>
        <div style={S.statCard}>
          <p style={{ ...S.statValue, color: T.accent }}>{stats.active}</p>
          <p style={S.statLabel}>Aktive Integrationen</p>
        </div>
        <div style={S.statCard}>
          <p style={{ ...S.statValue, color: stats.errors > 0 ? T.danger : T.success }}>{stats.errors}</p>
          <p style={S.statLabel}>Fehler</p>
        </div>
        <div style={S.statCard}>
          <p style={S.statValue}>{stats.totalSynced.toLocaleString("de-DE")}</p>
          <p style={S.statLabel}>Kontakte synchronisiert</p>
        </div>
        <div style={S.statCard}>
          <p style={{ ...S.statValue, fontSize: 16, paddingTop: 6 }}>{formatTimeAgo(stats.lastSync)}</p>
          <p style={S.statLabel}>Letzter Sync</p>
        </div>
      </div>

      {/* Configured Integrations */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: T.text, margin: 0 }}>Konfigurierte Integrationen</h2>
        <button style={{ ...S.btn, ...S.btnSecondary, ...S.btnSmall }} onClick={onViewHistory}>
          <History size={13} /> Sync-Verlauf
        </button>
      </div>

      <div style={S.grid}>
        {configured.map(ti => {
          const visual = getIntegrationVisual(ti.integration_id);
          const statusCfg = STATUS_CONFIG[ti.status] || STATUS_CONFIG.disconnected;
          return (
            <motion.div
              key={ti.id}
              style={S.card}
              whileHover={{ borderColor: T.accent, transform: "translateY(-2px)" }}
              onClick={() => onOpenDetail(ti)}
            >
              <div style={S.cardHeader}>
                <div style={{ ...S.cardIcon, background: `${visual.color}20`, color: visual.color }}>
                  {visual.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={S.cardTitle}>{ti.display_name}</span>
                    <span style={{ ...S.badge, color: statusCfg.color, background: statusCfg.bg }}>
                      {ti.status === "syncing" && <Loader2 size={10} style={{ animation: "spin 1s linear infinite" }} />}
                      {ti.status === "connected" && <CheckCircle2 size={10} />}
                      {ti.status === "error" && <AlertCircle size={10} />}
                      {statusCfg.label}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: T.textMuted, marginTop: 4 }}>
                    {ti.sync_direction === "inbound" ? "Eingehend" : ti.sync_direction === "outbound" ? "Ausgehend" : "Bidirektional"}
                    {" · "}
                    Alle {ti.sync_interval_minutes} Min.
                  </div>
                </div>
              </div>

              {ti.last_sync_log && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 12 }}>
                  <div style={{ textAlign: "center", padding: "8px 0", borderRadius: 8, background: T.surfaceAlt }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: T.success }}>{ti.last_sync_log.records_created || 0}</div>
                    <div style={{ fontSize: 10, color: T.textDim }}>Erstellt</div>
                  </div>
                  <div style={{ textAlign: "center", padding: "8px 0", borderRadius: 8, background: T.surfaceAlt }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: T.info }}>{ti.last_sync_log.records_updated || 0}</div>
                    <div style={{ fontSize: 10, color: T.textDim }}>Aktualisiert</div>
                  </div>
                  <div style={{ textAlign: "center", padding: "8px 0", borderRadius: 8, background: T.surfaceAlt }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: T.text }}>{ti.last_sync_log.records_fetched || 0}</div>
                    <div style={{ fontSize: 10, color: T.textDim }}>Abgerufen</div>
                  </div>
                </div>
              )}

              <div style={S.cardFooter}>
                <span style={{ fontSize: 12, color: T.textDim }}>
                  <Clock size={11} style={{ marginRight: 4, verticalAlign: "middle" }} />
                  {formatTimeAgo(ti.last_sync_at)}
                </span>
                <div style={{ display: "flex", gap: 6 }}>
                  <button
                    style={{ ...S.btn, ...S.btnSecondary, ...S.btnSmall }}
                    onClick={(e) => { e.stopPropagation(); runSync.mutate({ integrationId: ti.integration_id }); }}
                    disabled={runSync.isPending}
                  >
                    {runSync.isPending ? <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={12} />}
                    Sync
                  </button>
                  <button style={{ ...S.btn, ...S.btnSecondary, ...S.btnSmall }} onClick={(e) => { e.stopPropagation(); onOpenDetail(ti); }}>
                    <Settings size={12} />
                  </button>
                </div>
              </div>
            </motion.div>
          );
        })}

        {/* Add New Card */}
        <motion.div
          style={{ ...S.card, border: `2px dashed ${T.border}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200 }}
          whileHover={{ borderColor: T.accent }}
          onClick={onAddNew}
        >
          <div style={{ width: 48, height: 48, borderRadius: 12, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
            <Plus size={24} style={{ color: T.accent }} />
          </div>
          <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>Integration hinzufügen</span>
          <span style={{ fontSize: 12, color: T.textMuted, marginTop: 4 }}>Neue Datenquelle verbinden</span>
        </motion.div>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// MARKETPLACE VIEW
// ══════════════════════════════════════════════════════════════════════════════

function MarketplaceView({
  available, configured, loading, searchQuery, onSearchChange, onSelect, onBack,
}: {
  available: AvailableIntegration[];
  configured: TenantIntegration[];
  loading: boolean;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelect: (i: AvailableIntegration) => void;
  onBack: () => void;
}) {
  const configuredIds = new Set(configured.map(c => c.integration_id));
  const [filterCategory, setFilterCategory] = useState<string>("all");

  const categories = useMemo(() => {
    const cats = new Set(available.map(a => a.category));
    return ["all", ...Array.from(cats)];
  }, [available]);

  const CATEGORY_LABELS: Record<string, string> = {
    all: "Alle",
    fitness: "Fitness & Studio",
    ecommerce: "E-Commerce",
    crm: "CRM",
    marketing: "Marketing",
    other: "Sonstige",
  };

  const filtered = useMemo(() => {
    return available.filter(a => {
      if (filterCategory !== "all" && a.category !== filterCategory) return false;
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return a.display_name.toLowerCase().includes(q) || a.integration_id.toLowerCase().includes(q) || a.category.toLowerCase().includes(q);
      }
      return true;
    });
  }, [available, filterCategory, searchQuery]);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>Integration Marketplace</h2>
          <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>Wählen Sie eine Integration, um Kontaktdaten zu synchronisieren</p>
        </div>
        <button style={{ ...S.btn, ...S.btnSecondary }} onClick={onBack}>
          <ArrowLeft size={14} /> Zurück
        </button>
      </div>

      {/* Search & Filter */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1, position: "relative" }}>
          <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim }} />
          <input
            style={{ ...S.input, paddingLeft: 36 }}
            placeholder="Integration suchen..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>
        <div style={{ display: "flex", gap: 4, background: T.surface, borderRadius: 8, padding: 3, border: `1px solid ${T.border}` }}>
          {categories.map(cat => (
            <button
              key={cat}
              style={{ ...S.tab, ...S.btnSmall, ...(filterCategory === cat ? S.tabActive : S.tabInactive) }}
              onClick={() => setFilterCategory(cat)}
            >
              {CATEGORY_LABELS[cat] || cat}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: T.textMuted }}>
          <Loader2 size={32} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      ) : (
        <div style={S.grid}>
          {filtered.map(integration => {
            const visual = getIntegrationVisual(integration.integration_id);
            const isConfigured = configuredIds.has(integration.integration_id);
            return (
              <motion.div
                key={integration.integration_id}
                style={{ ...S.card, opacity: isConfigured ? 0.6 : 1 }}
                whileHover={{ borderColor: T.accent, transform: "translateY(-2px)" }}
                onClick={() => !isConfigured && onSelect(integration)}
              >
                <div style={S.cardHeader}>
                  <div style={{ ...S.cardIcon, background: `${visual.color}20`, color: visual.color }}>
                    {visual.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={S.cardTitle}>{integration.display_name}</span>
                      {isConfigured && (
                        <span style={{ ...S.badge, color: T.success, background: T.successDim }}>
                          <Check size={10} /> Konfiguriert
                        </span>
                      )}
                    </div>
                    <span style={{ ...S.badge, color: T.textMuted, background: T.surfaceAlt, marginTop: 4 }}>
                      {CATEGORY_LABELS[integration.category] || integration.category}
                    </span>
                  </div>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                  {integration.supported_sync_directions.map(dir => (
                    <span key={dir} style={{ ...S.badge, fontSize: 10, color: T.textDim, background: T.surfaceAlt }}>
                      {dir === "inbound" ? "↓ Eingehend" : dir === "outbound" ? "↑ Ausgehend" : "↕ Bidirektional"}
                    </span>
                  ))}
                  {integration.supports_webhooks && (
                    <span style={{ ...S.badge, fontSize: 10, color: T.info, background: T.infoDim }}>
                      <Zap size={9} /> Webhooks
                    </span>
                  )}
                  {integration.supports_incremental_sync && (
                    <span style={{ ...S.badge, fontSize: 10, color: T.success, background: T.successDim }}>
                      <TrendingUp size={9} /> Inkrementell
                    </span>
                  )}
                </div>

                {!isConfigured && (
                  <div style={{ ...S.cardFooter, justifyContent: "flex-end" }}>
                    <button style={{ ...S.btn, ...S.btnPrimary, ...S.btnSmall }} onClick={(e) => { e.stopPropagation(); onSelect(integration); }}>
                      Einrichten <ArrowRight size={12} />
                    </button>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SETUP WIZARD
// ══════════════════════════════════════════════════════════════════════════════

function SetupWizard({
  integration, onComplete, onCancel,
}: {
  integration: AvailableIntegration;
  onComplete: () => void;
  onCancel: () => void;
}) {
  const [step, setStep] = useState<"config" | "test" | "options" | "complete">("config");
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});
  const [syncDirection, setSyncDirection] = useState("inbound");
  const [syncInterval, setSyncInterval] = useState(60);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const testConnection = useTestConnection();
  const saveIntegration = useSaveIntegration();

  const schema = integration.config_schema;
  const fields = schema?.fields || [];

  // Initialize defaults
  useEffect(() => {
    const defaults: Record<string, unknown> = {};
    fields.forEach(f => {
      if (f.default_value !== undefined) defaults[f.key] = f.default_value;
    });
    setConfig(defaults);
  }, []);

  const handleFieldChange = (key: string, value: unknown) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleTest = async () => {
    setTestResult(null);
    try {
      const result = await testConnection.mutateAsync({
        integrationId: integration.integration_id,
        config,
      });
      setTestResult(result);
      if (result.success) {
        setTimeout(() => setStep("options"), 1500);
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Verbindungstest fehlgeschlagen" });
    }
  };

  const handleSave = async () => {
    try {
      await saveIntegration.mutateAsync({
        integrationId: integration.integration_id,
        config,
        sync_direction: syncDirection,
        sync_interval_minutes: syncInterval,
        enabled: true,
      });
      setStep("complete");
      setTimeout(onComplete, 2000);
    } catch (err: any) {
      setTestResult({ success: false, message: err.message || "Speichern fehlgeschlagen" });
    }
  };

  const visual = getIntegrationVisual(integration.integration_id);

  const renderField = (field: ConfigField) => {
    const value = config[field.key] ?? "";
    const isPassword = field.type === "password";
    const showPw = showPasswords[field.key];

    return (
      <div key={field.key} style={S.fieldGroup}>
        <label style={S.fieldLabel}>
          {field.label}
          {field.required && <span style={{ color: T.danger }}> *</span>}
        </label>
        {field.type === "select" ? (
          <select
            style={S.select}
            value={String(value)}
            onChange={(e) => handleFieldChange(field.key, e.target.value)}
          >
            <option value="">Bitte wählen...</option>
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        ) : field.type === "toggle" ? (
          <div
            style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
            onClick={() => handleFieldChange(field.key, !value)}
          >
            <div style={{
              width: 40, height: 22, borderRadius: 11, background: value ? T.accent : T.border,
              position: "relative", transition: "all 0.2s",
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: 9, background: "#fff",
                position: "absolute", top: 2, left: value ? 20 : 2, transition: "all 0.2s",
              }} />
            </div>
            <span style={{ fontSize: 13, color: T.text }}>{value ? "Aktiviert" : "Deaktiviert"}</span>
          </div>
        ) : (
          <div style={{ position: "relative" }}>
            <input
              style={S.input}
              type={isPassword && !showPw ? "password" : field.type === "number" ? "number" : "text"}
              placeholder={field.placeholder || ""}
              value={String(value)}
              onChange={(e) => handleFieldChange(field.key, field.type === "number" ? Number(e.target.value) : e.target.value)}
            />
            {isPassword && (
              <button
                style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: T.textDim }}
                onClick={() => setShowPasswords(prev => ({ ...prev, [field.key]: !prev[field.key] }))}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            )}
          </div>
        )}
        {field.help_text && <p style={S.fieldHelp}>{field.help_text}</p>}
      </div>
    );
  };

  return (
    <div style={{ maxWidth: 640, margin: "0 auto" }}>
      {/* Progress */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24 }}>
        {["config", "test", "options", "complete"].map((s, i) => (
          <Fragment key={s}>
            <div style={{
              width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 13, fontWeight: 600,
              background: step === s ? T.accent : (["config", "test", "options", "complete"].indexOf(step) > i ? T.success : T.surfaceAlt),
              color: step === s || ["config", "test", "options", "complete"].indexOf(step) > i ? "#fff" : T.textDim,
            }}>
              {["config", "test", "options", "complete"].indexOf(step) > i ? <Check size={14} /> : i + 1}
            </div>
            {i < 3 && <div style={{ flex: 1, height: 2, background: ["config", "test", "options", "complete"].indexOf(step) > i ? T.success : T.border }} />}
          </Fragment>
        ))}
      </div>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
        <div style={{ ...S.cardIcon, width: 52, height: 52, background: `${visual.color}20`, color: visual.color }}>
          {visual.icon}
        </div>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>{integration.display_name} einrichten</h2>
          <p style={{ fontSize: 13, color: T.textMuted, margin: "4px 0 0" }}>
            {step === "config" && "Geben Sie Ihre Zugangsdaten ein"}
            {step === "test" && "Verbindung wird getestet..."}
            {step === "options" && "Sync-Optionen konfigurieren"}
            {step === "complete" && "Integration erfolgreich eingerichtet!"}
          </p>
        </div>
      </div>

      {/* Step Content */}
      <Card style={{ padding: 24, marginBottom: 20 }}>
        {step === "config" && (
          <>
            {fields.length > 0 ? (
              fields.map(renderField)
            ) : (
              <p style={{ color: T.textMuted, textAlign: "center", padding: 20 }}>
                Diese Integration benötigt keine Konfiguration.
              </p>
            )}
          </>
        )}

        {step === "test" && (
          <div style={{ textAlign: "center", padding: 20 }}>
            {testConnection.isPending && (
              <>
                <Loader2 size={40} style={{ color: T.accent, animation: "spin 1s linear infinite", margin: "0 auto 16px" }} />
                <p style={{ color: T.textMuted }}>Verbindung wird getestet...</p>
              </>
            )}
            {testResult && (
              <>
                <div style={{
                  width: 56, height: 56, borderRadius: "50%", margin: "0 auto 16px",
                  background: testResult.success ? T.successDim : T.dangerDim,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {testResult.success ? <CheckCircle2 size={28} style={{ color: T.success }} /> : <AlertCircle size={28} style={{ color: T.danger }} />}
                </div>
                <p style={{ fontSize: 15, fontWeight: 600, color: testResult.success ? T.success : T.danger }}>
                  {testResult.success ? "Verbindung erfolgreich!" : "Verbindung fehlgeschlagen"}
                </p>
                <p style={{ fontSize: 13, color: T.textMuted, marginTop: 8 }}>{testResult.message}</p>
                {!testResult.success && (
                  <button style={{ ...S.btn, ...S.btnSecondary, margin: "16px auto 0" }} onClick={() => { setStep("config"); setTestResult(null); }}>
                    <ArrowLeft size={14} /> Zurück zur Konfiguration
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {step === "options" && (
          <>
            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>Sync-Richtung</label>
              <select style={S.select} value={syncDirection} onChange={(e) => setSyncDirection(e.target.value)}>
                {integration.supported_sync_directions.map(dir => (
                  <option key={dir} value={dir}>
                    {dir === "inbound" ? "↓ Eingehend (Import)" : dir === "outbound" ? "↑ Ausgehend (Export)" : "↕ Bidirektional"}
                  </option>
                ))}
              </select>
              <p style={S.fieldHelp}>
                {syncDirection === "inbound" && "Kontaktdaten werden von der externen Quelle nach ARIIA importiert."}
                {syncDirection === "outbound" && "Kontaktdaten werden von ARIIA zur externen Quelle exportiert."}
                {syncDirection === "bidirectional" && "Kontaktdaten werden in beide Richtungen synchronisiert."}
              </p>
            </div>
            <div style={S.fieldGroup}>
              <label style={S.fieldLabel}>Sync-Intervall</label>
              <select style={S.select} value={syncInterval} onChange={(e) => setSyncInterval(Number(e.target.value))}>
                <option value={15}>Alle 15 Minuten</option>
                <option value={30}>Alle 30 Minuten</option>
                <option value={60}>Stündlich</option>
                <option value={360}>Alle 6 Stunden</option>
                <option value={720}>Alle 12 Stunden</option>
                <option value={1440}>Täglich</option>
              </select>
              <p style={S.fieldHelp}>Wie oft sollen die Kontaktdaten automatisch synchronisiert werden?</p>
            </div>
          </>
        )}

        {step === "complete" && (
          <div style={{ textAlign: "center", padding: 20 }}>
            <div style={{
              width: 64, height: 64, borderRadius: "50%", margin: "0 auto 16px",
              background: T.successDim, display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <CheckCircle2 size={32} style={{ color: T.success }} />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>
              {integration.display_name} verbunden!
            </h3>
            <p style={{ fontSize: 13, color: T.textMuted }}>
              Die Integration wurde erfolgreich eingerichtet. Die erste Synchronisation wird in Kürze gestartet.
            </p>
          </div>
        )}
      </Card>

      {/* Actions */}
      {step !== "complete" && (
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <button style={{ ...S.btn, ...S.btnSecondary }} onClick={step === "config" ? onCancel : () => setStep(step === "options" ? "config" : "config")}>
            {step === "config" ? "Abbrechen" : <><ArrowLeft size={14} /> Zurück</>}
          </button>
          {step === "config" && (
            <button style={{ ...S.btn, ...S.btnPrimary }} onClick={() => { setStep("test"); handleTest(); }}>
              Verbindung testen <ArrowRight size={14} />
            </button>
          )}
          {step === "options" && (
            <button
              style={{ ...S.btn, ...S.btnPrimary }}
              onClick={handleSave}
              disabled={saveIntegration.isPending}
            >
              {saveIntegration.isPending ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Check size={14} />}
              Speichern & Aktivieren
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// INTEGRATION DETAIL VIEW
// ══════════════════════════════════════════════════════════════════════════════

function IntegrationDetail({
  integration, onBack, onRefresh,
}: {
  integration: TenantIntegration;
  onBack: () => void;
  onRefresh: () => void;
}) {
  const visual = getIntegrationVisual(integration.integration_id);
  const statusCfg = STATUS_CONFIG[integration.status] || STATUS_CONFIG.disconnected;

  const runSync = useRunSync();
  const toggleIntegration = useToggleIntegration();
  const deleteIntegration = useDeleteIntegration();
  const { data: history = [] } = useSyncHistory(20);

  const integrationHistory = history.filter(h => h.integration_id === integration.integration_id);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleToggle = async () => {
    await toggleIntegration.mutateAsync({
      integrationId: integration.integration_id,
      enabled: !integration.enabled,
    });
    onRefresh();
  };

  const handleDelete = async () => {
    await deleteIntegration.mutateAsync(integration.integration_id);
    onBack();
  };

  const handleSync = async (mode?: string) => {
    await runSync.mutateAsync({ integrationId: integration.integration_id, syncMode: mode });
    onRefresh();
  };

  return (
    <>
      {/* Header */}
      <div style={S.detailHeader}>
        <div style={{ ...S.cardIcon, width: 56, height: 56, background: `${visual.color}20`, color: visual.color }}>
          {visual.icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: 0 }}>{integration.display_name}</h2>
            <span style={{ ...S.badge, color: statusCfg.color, background: statusCfg.bg }}>
              {statusCfg.label}
            </span>
          </div>
          <p style={{ fontSize: 13, color: T.textMuted, margin: "4px 0 0" }}>
            {integration.sync_direction === "inbound" ? "Eingehend" : integration.sync_direction === "outbound" ? "Ausgehend" : "Bidirektional"}
            {" · Intervall: "}{integration.sync_interval_minutes} Min.
            {integration.last_sync_at && ` · Letzter Sync: ${formatTimeAgo(integration.last_sync_at)}`}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            style={{ ...S.btn, ...S.btnSecondary }}
            onClick={handleToggle}
            disabled={toggleIntegration.isPending}
          >
            <Power size={14} /> {integration.enabled ? "Deaktivieren" : "Aktivieren"}
          </button>
          <button
            style={{ ...S.btn, ...S.btnPrimary }}
            onClick={() => handleSync()}
            disabled={runSync.isPending}
          >
            {runSync.isPending ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Play size={14} />}
            Jetzt synchronisieren
          </button>
          <button style={{ ...S.btn, ...S.btnDanger }} onClick={() => setShowDeleteConfirm(true)}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Last Sync Message */}
      {integration.last_sync_message && (
        <div style={{
          padding: "12px 16px", borderRadius: 10, marginBottom: 20,
          background: integration.last_sync_status === "error" ? T.dangerDim : T.successDim,
          border: `1px solid ${integration.last_sync_status === "error" ? T.danger : T.success}30`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          {integration.last_sync_status === "error" ? <AlertCircle size={16} style={{ color: T.danger }} /> : <CheckCircle2 size={16} style={{ color: T.success }} />}
          <span style={{ fontSize: 13, color: T.text }}>{integration.last_sync_message}</span>
        </div>
      )}

      {/* Sync Actions */}
      <div style={{ display: "flex", gap: 10, marginBottom: 24 }}>
        <button style={{ ...S.btn, ...S.btnSecondary }} onClick={() => handleSync("full")} disabled={runSync.isPending}>
          <Download size={14} /> Full Sync
        </button>
        <button style={{ ...S.btn, ...S.btnSecondary }} onClick={() => handleSync("incremental")} disabled={runSync.isPending}>
          <TrendingUp size={14} /> Inkrementeller Sync
        </button>
      </div>

      {/* Sync History Table */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: T.text, margin: 0 }}>Sync-Verlauf</h3>
          <span style={{ fontSize: 12, color: T.textDim }}>{integrationHistory.length} Einträge</span>
        </div>
        {integrationHistory.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: T.textMuted }}>
            <History size={32} style={{ marginBottom: 8, opacity: 0.5 }} />
            <p>Noch keine Synchronisierungen durchgeführt.</p>
          </div>
        ) : (
          <table style={S.logTable}>
            <thead>
              <tr>
                <th style={S.logTh}>Status</th>
                <th style={S.logTh}>Modus</th>
                <th style={S.logTh}>Abgerufen</th>
                <th style={S.logTh}>Erstellt</th>
                <th style={S.logTh}>Aktualisiert</th>
                <th style={S.logTh}>Fehler</th>
                <th style={S.logTh}>Dauer</th>
                <th style={S.logTh}>Ausgelöst</th>
                <th style={S.logTh}>Zeitpunkt</th>
              </tr>
            </thead>
            <tbody>
              {integrationHistory.map((log, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : T.surfaceAlt }}>
                  <td style={S.logTd}>
                    <span style={{
                      ...S.badge,
                      color: log.status === "success" ? T.success : T.danger,
                      background: log.status === "success" ? T.successDim : T.dangerDim,
                    }}>
                      {log.status === "success" ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
                      {log.status === "success" ? "Erfolg" : "Fehler"}
                    </span>
                  </td>
                  <td style={S.logTd}>{log.sync_mode === "full" ? "Vollständig" : "Inkrementell"}</td>
                  <td style={S.logTd}>{log.records_fetched}</td>
                  <td style={{ ...S.logTd, color: T.success }}>{log.records_created}</td>
                  <td style={{ ...S.logTd, color: T.info }}>{log.records_updated}</td>
                  <td style={{ ...S.logTd, color: log.records_failed > 0 ? T.danger : T.textDim }}>{log.records_failed}</td>
                  <td style={S.logTd}>{formatDuration(log.duration_ms)}</td>
                  <td style={S.logTd}>
                    <span style={{ ...S.badge, color: T.textMuted, background: T.surfaceAlt }}>
                      {log.triggered_by === "manual" ? "Manuell" : log.triggered_by === "scheduler" ? "Geplant" : "Webhook"}
                    </span>
                  </td>
                  <td style={{ ...S.logTd, fontSize: 12, color: T.textDim }}>{formatTimeAgo(log.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <Modal open={showDeleteConfirm} title="Integration entfernen" onClose={() => setShowDeleteConfirm(false)} width="420px">
          <div style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
              <div style={{ width: 44, height: 44, borderRadius: 10, background: T.dangerDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <AlertTriangle size={22} style={{ color: T.danger }} />
              </div>
              <div>
                <p style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>
                  {integration.display_name} wirklich entfernen?
                </p>
                <p style={{ fontSize: 12, color: T.textMuted, margin: "4px 0 0" }}>
                  Alle Zugangsdaten und Konfigurationen werden gelöscht. Bereits synchronisierte Kontakte bleiben erhalten.
                </p>
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button style={{ ...S.btn, ...S.btnSecondary }} onClick={() => setShowDeleteConfirm(false)}>Abbrechen</button>
              <button
                style={{ ...S.btn, ...S.btnDanger }}
                onClick={handleDelete}
                disabled={deleteIntegration.isPending}
              >
                {deleteIntegration.isPending ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Trash2 size={14} />}
                Endgültig entfernen
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// HISTORY VIEW
// ══════════════════════════════════════════════════════════════════════════════

function HistoryView({
  history, loading, onBack,
}: {
  history: SyncLogEntry[];
  loading: boolean;
  onBack: () => void;
}) {
  const [filterIntegration, setFilterIntegration] = useState<string>("all");

  const integrationIds = useMemo(() => {
    const ids = new Set(history.map(h => h.integration_id));
    return ["all", ...Array.from(ids)];
  }, [history]);

  const filtered = filterIntegration === "all" ? history : history.filter(h => h.integration_id === filterIntegration);

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>Sync-Verlauf</h2>
          <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>{filtered.length} Synchronisierungen</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <select
            style={{ ...S.select, width: 200 }}
            value={filterIntegration}
            onChange={(e) => setFilterIntegration(e.target.value)}
          >
            {integrationIds.map(id => (
              <option key={id} value={id}>{id === "all" ? "Alle Integrationen" : id}</option>
            ))}
          </select>
          <button style={{ ...S.btn, ...S.btnSecondary }} onClick={onBack}>
            <ArrowLeft size={14} /> Zurück
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60, color: T.textMuted }}>
          <Loader2 size={32} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      ) : (
        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={S.logTable}>
            <thead>
              <tr>
                <th style={S.logTh}>Integration</th>
                <th style={S.logTh}>Status</th>
                <th style={S.logTh}>Modus</th>
                <th style={S.logTh}>Abgerufen</th>
                <th style={S.logTh}>Erstellt</th>
                <th style={S.logTh}>Aktualisiert</th>
                <th style={S.logTh}>Fehler</th>
                <th style={S.logTh}>Dauer</th>
                <th style={S.logTh}>Ausgelöst</th>
                <th style={S.logTh}>Zeitpunkt</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((log, i) => {
                const visual = getIntegrationVisual(log.integration_id);
                return (
                  <tr key={i} style={{ background: i % 2 === 0 ? "transparent" : T.surfaceAlt }}>
                    <td style={S.logTd}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ ...S.cardIcon, width: 28, height: 28, borderRadius: 6, background: `${visual.color}20`, color: visual.color }}>
                          {visual.icon}
                        </div>
                        <span style={{ fontSize: 13, fontWeight: 500 }}>{log.integration_id}</span>
                      </div>
                    </td>
                    <td style={S.logTd}>
                      <span style={{
                        ...S.badge,
                        color: log.status === "success" ? T.success : T.danger,
                        background: log.status === "success" ? T.successDim : T.dangerDim,
                      }}>
                        {log.status === "success" ? <CheckCircle2 size={10} /> : <AlertCircle size={10} />}
                        {log.status === "success" ? "Erfolg" : "Fehler"}
                      </span>
                    </td>
                    <td style={S.logTd}>{log.sync_mode === "full" ? "Vollständig" : "Inkrementell"}</td>
                    <td style={S.logTd}>{log.records_fetched}</td>
                    <td style={{ ...S.logTd, color: T.success }}>{log.records_created}</td>
                    <td style={{ ...S.logTd, color: T.info }}>{log.records_updated}</td>
                    <td style={{ ...S.logTd, color: log.records_failed > 0 ? T.danger : T.textDim }}>{log.records_failed}</td>
                    <td style={S.logTd}>{formatDuration(log.duration_ms)}</td>
                    <td style={S.logTd}>
                      <span style={{ ...S.badge, color: T.textMuted, background: T.surfaceAlt }}>
                        {log.triggered_by === "manual" ? "Manuell" : log.triggered_by === "scheduler" ? "Geplant" : "Webhook"}
                      </span>
                    </td>
                    <td style={{ ...S.logTd, fontSize: 12, color: T.textDim }}>{formatTimeAgo(log.started_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: T.textMuted }}>
              <History size={32} style={{ marginBottom: 8, opacity: 0.5 }} />
              <p>Keine Synchronisierungen gefunden.</p>
            </div>
          )}
        </Card>
      )}
    </>
  );
}
