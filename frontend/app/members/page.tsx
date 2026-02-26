"use client";

import { Fragment, useCallback, useEffect, useMemo, useState, useRef, type CSSProperties } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users, Plus, Upload, Download, Trash2, Search, Filter, Settings2,
  MoreHorizontal, UserCircle, Database, Loader2, ChevronRight, ChevronLeft,
  CheckCircle2, Circle, ArrowRight, ArrowLeft, FileSpreadsheet, Globe, Plug,
  Dumbbell, ShoppingBag, BarChart3, Zap, Shield, RefreshCw, AlertCircle,
  X, Check, Copy, ExternalLink, HelpCircle, Sparkles, Link2, Terminal,
  CloudUpload, Table2, PenLine, Key, BookOpen, Play, Pause, Edit3, Eye
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { usePermissions } from "@/lib/permissions";
import { FeatureGate } from "@/components/FeatureGate";

// ── Types ────────────────────────────────────────────────────────────────────

type Member = {
  id: number;
  customer_id: number;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone_number?: string | null;
  source: string;
  source_id?: string | null;
  tags?: string[];
  custom_fields?: Record<string, any>;
  member_since?: string;
  is_paused?: boolean;
};

type IntegrationMethod = "manual" | "api" | "platform" | null;
type PlatformId = "magicline" | "shopify" | "hubspot" | "woocommerce" | "salesforce" | "custom_api";

type ConnectorMeta = {
  id: string;
  name: string;
  category: string;
  description: string;
  status: "connected" | "disconnected" | "error";
  icon: string;
  fields: Array<{
    key: string;
    label: string;
    type: string;
    placeholder?: string;
    optional?: boolean;
    depends_on?: string;
    options?: string[];
  }>;
};

// ── Constants ────────────────────────────────────────────────────────────────

const INTEGRATION_METHODS = [
  {
    id: "manual" as IntegrationMethod,
    icon: <PenLine size={24} />,
    color: T.accent,
    features: ["csv_upload", "single_entry", "bulk_edit", "export"],
  },
  {
    id: "api" as IntegrationMethod,
    icon: <Terminal size={24} />,
    color: T.info,
    features: ["rest_api", "webhooks", "realtime_sync", "api_keys"],
  },
  {
    id: "platform" as IntegrationMethod,
    icon: <Plug size={24} />,
    color: T.success,
    features: ["auto_sync", "no_code", "bi_directional", "scheduled"],
  },
] as const;

const PLATFORMS: Array<{
  id: PlatformId;
  name: string;
  icon: React.ReactNode;
  color: string;
  category: string;
  connectorId?: string;
}> = [
  { id: "magicline", name: "Magicline", icon: <Dumbbell size={22} />, color: "#FF6B35", category: "fitness", connectorId: "magicline" },
  { id: "shopify", name: "Shopify", icon: <ShoppingBag size={22} />, color: "#96BF48", category: "ecommerce", connectorId: "shopify" },
  { id: "hubspot", name: "HubSpot", icon: <BarChart3 size={22} />, color: "#FF7A59", category: "crm", connectorId: "hubspot" },
  { id: "woocommerce", name: "WooCommerce", icon: <ShoppingBag size={22} />, color: "#7F54B3", category: "ecommerce", connectorId: "woocommerce" },
  { id: "salesforce", name: "Salesforce", icon: <Globe size={22} />, color: "#00A1E0", category: "crm", connectorId: "salesforce" },
  { id: "custom_api", name: "Custom API", icon: <Terminal size={22} />, color: T.accentLight, category: "developer" },
];

// ── Shared Styles ────────────────────────────────────────────────────────────

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 10,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  fontWeight: 500,
  outline: "none",
  transition: "border-color 0.2s, box-shadow 0.2s",
};

const labelStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: T.textMuted,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  marginBottom: 6,
};

// ── Animation Variants ───────────────────────────────────────────────────────

const fadeSlide = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const } },
  exit: { opacity: 0, y: -12, transition: { duration: 0.25 } },
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.06 } },
};

const staggerItem = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const } },
};

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE COMPONENT
// ══════════════════════════════════════════════════════════════════════════════

export default function MembersPage() {
  const { t } = useI18n();
  const { feature, plan } = usePermissions();
  const hasPlatformIntegrations = feature("platform_integrations");

  // ── View State ─────────────────────────────────────────────────────────────
  // "hub"       → initial integration method selection
  // "onboarding"→ guided setup wizard
  // "data"      → member data table (after setup or if members exist)
  const [view, setView] = useState<"hub" | "onboarding" | "data">("hub");
  const [selectedMethod, setSelectedMethod] = useState<IntegrationMethod>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformId | null>(null);
  const [onboardingStep, setOnboardingStep] = useState(0);

  // ── Data State ─────────────────────────────────────────────────────────────
  const [members, setMembers] = useState<Member[]>([]);
  const [columns, setColumns] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // ── Modal State ────────────────────────────────────────────────────────────
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [addForm, setAddForm] = useState({ first_name: "", last_name: "", email: "", phone_number: "" });
  const [addSaving, setAddSaving] = useState(false);

  // ── CSV State ──────────────────────────────────────────────────────────────
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploading, setCsvUploading] = useState(false);
  const [csvResult, setCsvResult] = useState<{ status: string; filename?: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Platform Config State ──────────────────────────────────────────────────
  const [platformConfig, setPlatformConfig] = useState<Record<string, string>>({});
  const [configSaving, setConfigSaving] = useState(false);
  const [configTesting, setConfigTesting] = useState(false);
  const [configTestResult, setConfigTestResult] = useState<{ status: string; message: string } | null>(null);
  const [connectorCatalog, setConnectorCatalog] = useState<ConnectorMeta[]>([]);

  // ── Data Fetching ──────────────────────────────────────────────────────────

  const fetchMembers = useCallback(async () => {
    setIsLoading(true);
    try {
      const [mRes, cRes] = await Promise.all([
        apiFetch("/admin/members/"),
        apiFetch("/admin/members/columns/"),
      ]);
      if (mRes.ok) {
        const data = await mRes.json();
        setMembers(data);
        // Auto-switch to data view if members exist
        if (data.length > 0) {
          setView("data");
        }
      }
      if (cRes.ok) setColumns(await cRes.json());
    } catch {
      // Silently handle — show empty state
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchCatalog = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/connector-hub/catalog");
      if (res.ok) setConnectorCatalog(await res.json());
    } catch {
      // best effort
    }
  }, []);

  useEffect(() => {
    fetchMembers();
    fetchCatalog();
  }, [fetchMembers, fetchCatalog]);

  // ── Derived ────────────────────────────────────────────────────────────────

  const filteredMembers = useMemo(() => {
    return members.filter(
      (m) =>
        `${m.first_name} ${m.last_name}`.toLowerCase().includes(query.toLowerCase()) ||
        m.email?.toLowerCase().includes(query.toLowerCase()),
    );
  }, [members, query]);

  const connectedPlatforms: string[] = useMemo(() => {
    return connectorCatalog.filter((c) => c.status === "connected").map((c) => c.id);
  }, [connectorCatalog]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  function selectMethod(method: IntegrationMethod) {
    setSelectedMethod(method);
    setOnboardingStep(0);
    if (method === "manual") {
      // Go directly to data view with manual mode
      setView("data");
    } else {
      setView("onboarding");
    }
  }

  function selectPlatform(platform: PlatformId) {
    setSelectedPlatform(platform);
    setPlatformConfig({});
    setConfigTestResult(null);
    setOnboardingStep(1);
  }

  async function handleAddMember() {
    if (!addForm.first_name || !addForm.last_name) return;
    setAddSaving(true);
    try {
      const res = await apiFetch("/admin/members/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(addForm),
      });
      if (res.ok) {
        setIsAddModalOpen(false);
        setAddForm({ first_name: "", last_name: "", email: "", phone_number: "" });
        fetchMembers();
      }
    } finally {
      setAddSaving(false);
    }
  }

  async function handleCsvUpload() {
    if (!csvFile) return;
    setCsvUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", csvFile);
      const res = await apiFetch("/admin/members/import/csv/", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        const result = await res.json();
        setCsvResult(result);
        setTimeout(() => {
          fetchMembers();
          setCsvFile(null);
          setCsvResult(null);
          setIsImportModalOpen(false);
        }, 2000);
      }
    } finally {
      setCsvUploading(false);
    }
  }

  async function handleCsvExport() {
    try {
      const res = await apiFetch("/admin/members/export/csv/");
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "members_export.csv";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      // best effort
    }
  }

  async function bulkDelete() {
    if (!confirm(t("members.confirmDelete"))) return;
    const res = await apiFetch("/admin/members/bulk/", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: Array.from(selectedIds) }),
    });
    if (res.ok) {
      setSelectedIds(new Set());
      fetchMembers();
    }
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function savePlatformConfig(connectorId: string) {
    setConfigSaving(true);
    try {
      const res = await apiFetch(`/admin/connector-hub/${connectorId}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...platformConfig, enabled: true }),
      });
      if (res.ok) {
        fetchCatalog();
        return true;
      }
      return false;
    } finally {
      setConfigSaving(false);
    }
  }

  async function testPlatformConnection(connectorId: string) {
    setConfigTesting(true);
    setConfigTestResult(null);
    try {
      const res = await apiFetch(`/admin/connector-hub/${connectorId}/test`, {
        method: "POST",
      });
      if (res.ok) {
        const result = await res.json();
        setConfigTestResult(result);
      } else {
        setConfigTestResult({ status: "error", message: "Connection test failed" });
      }
    } catch {
      setConfigTestResult({ status: "error", message: "Network error" });
    } finally {
      setConfigTesting(false);
    }
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // INTEGRATION HUB VIEW
  // ══════════════════════════════════════════════════════════════════════════════

  function renderHub() {
    return (
      <motion.div {...fadeSlide} key="hub" style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Hero Section */}
        <div
          style={{
            position: "relative",
            padding: "40px 32px",
            borderRadius: 20,
            background: `linear-gradient(135deg, ${T.surface} 0%, ${T.surfaceAlt} 100%)`,
            border: `1px solid ${T.border}`,
            overflow: "hidden",
          }}
        >
          {/* Decorative gradient orbs */}
          <div
            style={{
              position: "absolute",
              top: -60,
              right: -40,
              width: 200,
              height: 200,
              borderRadius: "50%",
              background: `radial-gradient(circle, ${T.accentDim} 0%, transparent 70%)`,
              pointerEvents: "none",
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: -80,
              left: -20,
              width: 160,
              height: 160,
              borderRadius: "50%",
              background: `radial-gradient(circle, ${T.infoDim} 0%, transparent 70%)`,
              pointerEvents: "none",
            }}
          />

          <div style={{ position: "relative", zIndex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  background: T.accentDim,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: T.accent,
                }}
              >
                <Users size={22} />
              </div>
              <div>
                <h1
                  style={{
                    fontSize: 22,
                    fontWeight: 800,
                    color: T.text,
                    margin: 0,
                    letterSpacing: "-0.03em",
                  }}
                >
                  {t("members.hub.title")}
                </h1>
                <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>{t("members.hub.subtitle")}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Method Selection Cards */}
        <div>
          <p
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: T.textDim,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              marginBottom: 16,
            }}
          >
            {t("members.hub.chooseMethod")}
          </p>

          <motion.div
            variants={staggerContainer}
            initial="initial"
            animate="animate"
            style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}
          >
            {INTEGRATION_METHODS.map((method) => {
              const isLocked = method.id === "platform" && !hasPlatformIntegrations;
              return (
                <motion.div key={method.id} variants={staggerItem}>
                  <MethodCard
                    method={method}
                    isSelected={selectedMethod === method.id}
                    onSelect={() => !isLocked && selectMethod(method.id)}
                    isLocked={isLocked}
                    t={t}
                  />
                </motion.div>
              );
            })}
          </motion.div>
        </div>

        {/* Quick Stats if members exist */}
        {members.length > 0 && (
          <motion.div {...fadeSlide}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "14px 20px",
                borderRadius: 12,
                background: T.successDim,
                border: `1px solid ${T.success}33`,
              }}
            >
              <CheckCircle2 size={18} color={T.success} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                {t("members.hub.existingData", { count: members.length })}
              </span>
              <button
                onClick={() => setView("data")}
                style={{
                  marginLeft: "auto",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 14px",
                  borderRadius: 8,
                  background: T.success,
                  color: "#fff",
                  fontSize: 12,
                  fontWeight: 700,
                  border: "none",
                  cursor: "pointer",
                }}
              >
                {t("members.hub.viewData")} <ArrowRight size={14} />
              </button>
            </div>
          </motion.div>
        )}

        {/* Connected Integrations */}
        {connectedPlatforms.length > 0 && (
          <div>
            <p
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: T.textDim,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 12,
              }}
            >
              {t("members.hub.activeIntegrations")}
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {connectedPlatforms.map((id) => {
                const platform = PLATFORMS.find((p) => p.connectorId === id);
                if (!platform) return null;
                return (
                  <div
                    key={id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 14px",
                      borderRadius: 10,
                      background: T.surfaceAlt,
                      border: `1px solid ${T.success}44`,
                    }}
                  >
                    <div style={{ color: platform.color }}>{platform.icon}</div>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{platform.name}</span>
                    <Badge variant="success">Connected</Badge>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // ONBOARDING VIEW
  // ══════════════════════════════════════════════════════════════════════════════

  function renderOnboarding() {
    if (selectedMethod === "api") return renderApiOnboarding();
    if (selectedMethod === "platform") return renderPlatformOnboarding();
    return null;
  }

  // ── API Onboarding ─────────────────────────────────────────────────────────

  function renderApiOnboarding() {
    const steps = [
      { title: t("members.onboarding.api.step1Title"), desc: t("members.onboarding.api.step1Desc") },
      { title: t("members.onboarding.api.step2Title"), desc: t("members.onboarding.api.step2Desc") },
      { title: t("members.onboarding.api.step3Title"), desc: t("members.onboarding.api.step3Desc") },
    ];

    return (
      <motion.div {...fadeSlide} key="api-onboarding" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Back + Title */}
        <OnboardingHeader
          title={t("members.onboarding.api.title")}
          subtitle={t("members.onboarding.api.subtitle")}
          onBack={() => { setView("hub"); setSelectedMethod(null); }}
          t={t}
        />

        {/* Step Indicator */}
        <StepIndicator steps={steps} currentStep={onboardingStep} />

        {/* Step Content */}
        <AnimatePresence mode="wait">
          {onboardingStep === 0 && (
            <motion.div {...fadeSlide} key="api-step-0">
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      background: T.infoDim,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: T.info,
                      flexShrink: 0,
                    }}
                  >
                    <BookOpen size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {t("members.onboarding.api.overviewTitle")}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {t("members.onboarding.api.overviewDesc")}
                    </p>
                  </div>
                </div>

                {/* API Endpoint Examples */}
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <ApiEndpointCard method="POST" path="/admin/members" desc={t("members.onboarding.api.endpointCreate")} />
                  <ApiEndpointCard method="POST" path="/admin/members/import/csv" desc={t("members.onboarding.api.endpointImport")} />
                  <ApiEndpointCard method="GET" path="/admin/members" desc={t("members.onboarding.api.endpointList")} />
                  <ApiEndpointCard method="GET" path="/admin/members/export/csv" desc={t("members.onboarding.api.endpointExport")} />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(1)} label={t("members.onboarding.next")} icon={<ArrowRight size={14} />} />
                </div>
              </Card>
            </motion.div>
          )}

          {onboardingStep === 1 && (
            <motion.div {...fadeSlide} key="api-step-1">
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      background: T.warningDim,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: T.warning,
                      flexShrink: 0,
                    }}
                  >
                    <Key size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {t("members.onboarding.api.authTitle")}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {t("members.onboarding.api.authDesc")}
                    </p>
                  </div>
                </div>

                {/* Code Example */}
                <CodeBlock
                  code={`curl -X POST /admin/members \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "first_name": "Max",
    "last_name": "Mustermann",
    "email": "max@example.com"
  }'`}
                />

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(0)} label={t("members.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  <ActionButton onClick={() => setOnboardingStep(2)} label={t("members.onboarding.next")} icon={<ArrowRight size={14} />} />
                </div>
              </Card>
            </motion.div>
          )}

          {onboardingStep === 2 && (
            <motion.div {...fadeSlide} key="api-step-2">
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      background: T.successDim,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: T.success,
                      flexShrink: 0,
                    }}
                  >
                    <Play size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {t("members.onboarding.api.testTitle")}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {t("members.onboarding.api.testDesc")}
                    </p>
                  </div>
                </div>

                <div
                  style={{
                    padding: 20,
                    borderRadius: 12,
                    background: T.surfaceAlt,
                    border: `1px solid ${T.border}`,
                    textAlign: "center",
                  }}
                >
                  <CheckCircle2 size={40} color={T.success} style={{ marginBottom: 12 }} />
                  <p style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                    {t("members.onboarding.api.readyTitle")}
                  </p>
                  <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>
                    {t("members.onboarding.api.readyDesc")}
                  </p>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(1)} label={t("members.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  <ActionButton
                    onClick={() => setView("data")}
                    label={t("members.onboarding.finish")}
                    icon={<ArrowRight size={14} />}
                    variant="success"
                  />
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }

  // ── Platform Onboarding ────────────────────────────────────────────────────

  function renderPlatformOnboarding() {
    const steps = [
      { title: t("members.onboarding.platform.step1Title"), desc: t("members.onboarding.platform.step1Desc") },
      { title: t("members.onboarding.platform.step2Title"), desc: t("members.onboarding.platform.step2Desc") },
      { title: t("members.onboarding.platform.step3Title"), desc: t("members.onboarding.platform.step3Desc") },
      { title: t("members.onboarding.platform.step4Title"), desc: t("members.onboarding.platform.step4Desc") },
    ];

    const activePlatform = PLATFORMS.find((p) => p.id === selectedPlatform);
    const connectorMeta = connectorCatalog.find((c) => c.id === activePlatform?.connectorId);

    return (
      <motion.div {...fadeSlide} key="platform-onboarding" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Back + Title */}
        <OnboardingHeader
          title={t("members.onboarding.platform.title")}
          subtitle={t("members.onboarding.platform.subtitle")}
          onBack={() => {
            if (onboardingStep > 0) {
              setOnboardingStep((s) => s - 1);
            } else {
              setView("hub");
              setSelectedMethod(null);
              setSelectedPlatform(null);
            }
          }}
          t={t}
        />

        {/* Step Indicator */}
        <StepIndicator steps={steps} currentStep={onboardingStep} />

        <AnimatePresence mode="wait">
          {/* Step 0: Platform Selection */}
          {onboardingStep === 0 && (
            <motion.div {...fadeSlide} key="platform-step-0">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
                {PLATFORMS.map((platform) => {
                  const isConnected = connectedPlatforms.includes(platform.connectorId || "");
                  return (
                    <PlatformCard
                      key={platform.id}
                      platform={platform}
                      isSelected={selectedPlatform === platform.id}
                      isConnected={isConnected}
                      onSelect={() => selectPlatform(platform.id)}
                      t={t}
                    />
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* Step 1: Configuration */}
          {onboardingStep === 1 && activePlatform && (
            <motion.div {...fadeSlide} key="platform-step-1">
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      background: `${activePlatform.color}20`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: activePlatform.color,
                    }}
                  >
                    {activePlatform.icon}
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>
                      {t("members.onboarding.platform.configTitle", { name: activePlatform.name })}
                    </h3>
                    <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>
                      {t("members.onboarding.platform.configDesc")}
                    </p>
                  </div>
                </div>

                {/* Dynamic Fields from Connector Meta */}
                {connectorMeta ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    {connectorMeta.fields.map((field) => (
                      <div key={field.key}>
                        <label style={labelStyle}>
                          {field.label}
                          {field.optional && (
                            <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 6 }}>
                              ({t("members.onboarding.platform.optional")})
                            </span>
                          )}
                        </label>
                        {field.type === "select" && field.options ? (
                          <select
                            value={platformConfig[field.key] || ""}
                            onChange={(e) => setPlatformConfig((c) => ({ ...c, [field.key]: e.target.value }))}
                            style={{ ...inputStyle, cursor: "pointer" }}
                          >
                            <option value="">{t("members.onboarding.platform.selectOption")}</option>
                            {field.options.map((opt) => (
                              <option key={opt} value={opt}>
                                {opt}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type={field.type === "password" ? "password" : "text"}
                            value={platformConfig[field.key] || ""}
                            onChange={(e) => setPlatformConfig((c) => ({ ...c, [field.key]: e.target.value }))}
                            placeholder={field.placeholder || ""}
                            style={inputStyle}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  /* Fallback for platforms without connector meta */
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <div
                      style={{
                        padding: 20,
                        borderRadius: 12,
                        background: T.warningDim,
                        border: `1px solid ${T.warning}33`,
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 12,
                      }}
                    >
                      <AlertCircle size={18} color={T.warning} style={{ flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: "0 0 4px" }}>
                          {t("members.onboarding.platform.comingSoon")}
                        </p>
                        <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>
                          {t("members.onboarding.platform.comingSoonDesc", { name: activePlatform.name })}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(0)} label={t("members.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  {connectorMeta && (
                    <ActionButton
                      onClick={() => setOnboardingStep(2)}
                      label={t("members.onboarding.next")}
                      icon={<ArrowRight size={14} />}
                    />
                  )}
                </div>
              </Card>
            </motion.div>
          )}

          {/* Step 2: Test Connection */}
          {onboardingStep === 2 && activePlatform && (
            <motion.div {...fadeSlide} key="platform-step-2">
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: 12,
                      background: T.infoDim,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: T.info,
                      flexShrink: 0,
                    }}
                  >
                    <Zap size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {t("members.onboarding.platform.testTitle")}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {t("members.onboarding.platform.testDesc")}
                    </p>
                  </div>
                </div>

                {/* Connection Test */}
                <div
                  style={{
                    padding: 24,
                    borderRadius: 14,
                    background: T.surfaceAlt,
                    border: `1px solid ${T.border}`,
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 16,
                  }}
                >
                  {configTesting ? (
                    <>
                      <Loader2 size={32} color={T.accent} className="animate-spin" />
                      <p style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{t("members.onboarding.platform.testing")}</p>
                    </>
                  ) : configTestResult ? (
                    <>
                      {configTestResult.status === "ok" ? (
                        <CheckCircle2 size={32} color={T.success} />
                      ) : (
                        <AlertCircle size={32} color={T.danger} />
                      )}
                      <p
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: configTestResult.status === "ok" ? T.success : T.danger,
                        }}
                      >
                        {configTestResult.message}
                      </p>
                    </>
                  ) : (
                    <>
                      <div
                        style={{
                          width: 56,
                          height: 56,
                          borderRadius: 16,
                          background: `${activePlatform.color}20`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: activePlatform.color,
                        }}
                      >
                        {activePlatform.icon}
                      </div>
                      <p style={{ fontSize: 13, color: T.textMuted, textAlign: "center" }}>
                        {t("members.onboarding.platform.testReady")}
                      </p>
                    </>
                  )}

                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      onClick={async () => {
                        const connId = activePlatform.connectorId;
                        if (connId) {
                          await savePlatformConfig(connId);
                          await testPlatformConnection(connId);
                        }
                      }}
                      disabled={configTesting || configSaving}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "10px 20px",
                        borderRadius: 10,
                        background: T.accent,
                        color: "#fff",
                        fontSize: 13,
                        fontWeight: 700,
                        border: "none",
                        cursor: configTesting ? "not-allowed" : "pointer",
                        opacity: configTesting ? 0.6 : 1,
                      }}
                    >
                      {configTesting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                      {t("members.onboarding.platform.runTest")}
                    </button>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(1)} label={t("members.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  <ActionButton
                    onClick={() => setOnboardingStep(3)}
                    label={t("members.onboarding.next")}
                    icon={<ArrowRight size={14} />}
                    disabled={!configTestResult || configTestResult.status !== "ok"}
                  />
                </div>
              </Card>
            </motion.div>
          )}

          {/* Step 3: Complete */}
          {onboardingStep === 3 && activePlatform && (
            <motion.div {...fadeSlide} key="platform-step-3">
              <Card style={{ padding: 28, textAlign: "center" }}>
                <div
                  style={{
                    width: 72,
                    height: 72,
                    borderRadius: 20,
                    background: T.successDim,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    margin: "0 auto 20px",
                  }}
                >
                  <CheckCircle2 size={36} color={T.success} />
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 800, color: T.text, margin: "0 0 8px" }}>
                  {t("members.onboarding.platform.completeTitle")}
                </h3>
                <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 8px", maxWidth: 420, marginLeft: "auto", marginRight: "auto" }}>
                  {t("members.onboarding.platform.completeDesc", { name: activePlatform.name })}
                </p>

                <div
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 16px",
                    borderRadius: 10,
                    background: T.surfaceAlt,
                    border: `1px solid ${T.success}44`,
                    margin: "16px 0 24px",
                  }}
                >
                  <div style={{ color: activePlatform.color }}>{activePlatform.icon}</div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{activePlatform.name}</span>
                  <Badge variant="success">Connected</Badge>
                </div>

                <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
                  <ActionButton
                    onClick={() => {
                      setView("data");
                      fetchMembers();
                    }}
                    label={t("members.onboarding.platform.goToMembers")}
                    icon={<ArrowRight size={14} />}
                    variant="success"
                  />
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // DATA VIEW
  // ══════════════════════════════════════════════════════════════════════════════

  function renderDataView() {
    return (
      <motion.div {...fadeSlide} key="data" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              onClick={() => setView("hub")}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 34,
                height: 34,
                borderRadius: 9,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: T.textMuted,
                cursor: "pointer",
              }}
            >
              <ArrowLeft size={16} />
            </button>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>
                {t("members.title")}
              </h2>
              <p style={{ fontSize: 12, color: T.textMuted, margin: "3px 0 0" }}>{t("members.subtitle")}</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={handleCsvExport}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 9,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: T.textMuted,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Download size={14} /> {t("members.data.export")}
            </button>
            <button
              onClick={() => setIsImportModalOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 9,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: T.textMuted,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <Upload size={14} /> {t("members.data.import")}
            </button>
            <button
              onClick={() => setIsAddModalOpen(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 14px",
                borderRadius: 9,
                background: T.accent,
                border: "none",
                color: "#fff",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              <Plus size={14} /> {t("members.add")}
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          <StatCard label={t("members.stats.total")} value={members.length} color={T.accent} />
          <StatCard label={t("members.stats.manual")} value={members.filter((m) => m.source === "manual").length} color={T.info} />
          <StatCard label={t("members.stats.external")} value={members.filter((m) => m.source !== "manual" && m.source !== "csv").length} color={T.success} />
          <StatCard
            label={t("members.stats.selected")}
            value={selectedIds.size}
            color={T.warning}
            action={
              selectedIds.size > 0 ? (
                <button
                  onClick={bulkDelete}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    padding: "4px 10px",
                    borderRadius: 6,
                    background: T.dangerDim,
                    border: "none",
                    color: T.danger,
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  <Trash2 size={12} /> {t("common.delete")}
                </button>
              ) : undefined
            }
          />
        </div>

        {/* Table */}
        <Card style={{ overflow: "hidden" }}>
          {/* Search Bar */}
          <div
            style={{
              padding: "12px 16px",
              borderBottom: `1px solid ${T.border}`,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div style={{ position: "relative", flex: 1 }}>
              <Search
                size={15}
                style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim }}
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("members.search")}
                style={{
                  ...inputStyle,
                  paddingLeft: 36,
                  background: T.surface,
                }}
              />
            </div>
            <button
              onClick={fetchMembers}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 38,
                height: 38,
                borderRadius: 9,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                color: T.textMuted,
                cursor: "pointer",
              }}
            >
              <RefreshCw size={15} />
            </button>
          </div>

          {/* Table Content */}
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                  <th style={{ padding: "12px 16px", width: 40 }}>
                    <input
                      type="checkbox"
                      onChange={(e) =>
                        setSelectedIds(e.target.checked ? new Set(filteredMembers.map((m) => m.id)) : new Set())
                      }
                      checked={filteredMembers.length > 0 && selectedIds.size === filteredMembers.length}
                      style={{ width: 16, height: 16, accentColor: T.accent, cursor: "pointer" }}
                    />
                  </th>
                  <th style={thStyle}>{t("members.table.member")}</th>
                  <th style={thStyle}>{t("members.table.source")}</th>
                  <th style={thStyle}>{t("members.table.status")}</th>
                  {columns
                    .filter((c: any) => c.is_visible)
                    .map((col: any) => (
                      <th key={col.slug} style={thStyle}>
                        {col.name}
                      </th>
                    ))}
                  <th style={{ ...thStyle, width: 40 }}></th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={10} style={{ padding: 48, textAlign: "center" }}>
                      <Loader2 size={24} color={T.accent} className="animate-spin" style={{ margin: "0 auto 8px", display: "block" }} />
                      <span style={{ fontSize: 13, color: T.textMuted }}>{t("common.loading")}</span>
                    </td>
                  </tr>
                ) : filteredMembers.length === 0 ? (
                  <tr>
                    <td colSpan={10} style={{ padding: 48, textAlign: "center" }}>
                      <Users size={32} color={T.textDim} style={{ margin: "0 auto 12px", display: "block" }} />
                      <span style={{ fontSize: 13, color: T.textMuted }}>{t("members.noMembers")}</span>
                    </td>
                  </tr>
                ) : (
                  filteredMembers.map((m) => (
                    <tr
                      key={m.id}
                      style={{
                        borderBottom: `1px solid ${T.border}`,
                        transition: "background 0.15s",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <td style={{ padding: "12px 16px" }}>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(m.id)}
                          onChange={() => toggleSelect(m.id)}
                          style={{ width: 16, height: 16, accentColor: T.accent, cursor: "pointer" }}
                        />
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <div
                            style={{
                              width: 36,
                              height: 36,
                              borderRadius: 10,
                              background: T.accentDim,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: T.accent,
                              fontSize: 13,
                              fontWeight: 700,
                              flexShrink: 0,
                            }}
                          >
                            {m.first_name?.[0]}
                            {m.last_name?.[0]}
                          </div>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                              {m.first_name} {m.last_name}
                            </div>
                            <div style={{ fontSize: 11, color: T.textDim }}>
                              {m.email || m.phone_number || t("members.noContact")}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        <SourceBadge source={m.source} />
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        {m.is_paused ? (
                          <Badge variant="warning">{t("members.status.paused")}</Badge>
                        ) : (
                          <Badge variant="success">{t("members.status.active")}</Badge>
                        )}
                      </td>
                      {columns
                        .filter((c: any) => c.is_visible)
                        .map((col: any) => (
                          <td key={col.slug} style={{ padding: "12px 16px", fontSize: 13, color: T.textMuted }}>
                            {m.custom_fields?.[col.slug] || "–"}
                          </td>
                        ))}
                      <td style={{ padding: "12px 16px" }}>
                        <button
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            width: 30,
                            height: 30,
                            borderRadius: 7,
                            background: "transparent",
                            border: "none",
                            color: T.textDim,
                            cursor: "pointer",
                            transition: "background 0.15s",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                        >
                          <MoreHorizontal size={16} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Table Footer */}
          {!isLoading && filteredMembers.length > 0 && (
            <div
              style={{
                padding: "10px 16px",
                borderTop: `1px solid ${T.border}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <span style={{ fontSize: 12, color: T.textDim }}>
                {filteredMembers.length} {t("members.data.entries")}
                {selectedIds.size > 0 && ` · ${selectedIds.size} ${t("members.stats.selected")}`}
              </span>
              <div style={{ display: "flex", gap: 6 }}>
                {connectedPlatforms.length > 0 && (
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: T.success }} />
                    <span style={{ fontSize: 11, color: T.textDim }}>
                      {connectedPlatforms.length} {t("members.data.activeSyncs")}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>

        {/* Add Member Modal */}
        <Modal open={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} title={t("members.add")}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <label style={labelStyle}>{t("members.form.firstName")}</label>
                <input
                  value={addForm.first_name}
                  onChange={(e) => setAddForm((f) => ({ ...f, first_name: e.target.value }))}
                  placeholder="Max"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>{t("members.form.lastName")}</label>
                <input
                  value={addForm.last_name}
                  onChange={(e) => setAddForm((f) => ({ ...f, last_name: e.target.value }))}
                  placeholder="Mustermann"
                  style={inputStyle}
                />
              </div>
            </div>
            <div>
              <label style={labelStyle}>{t("members.form.email")}</label>
              <input
                value={addForm.email}
                onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="max@beispiel.de"
                type="email"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>{t("members.form.phone")}</label>
              <input
                value={addForm.phone_number}
                onChange={(e) => setAddForm((f) => ({ ...f, phone_number: e.target.value }))}
                placeholder="+49 170 1234567"
                style={inputStyle}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8 }}>
              <button
                onClick={() => setIsAddModalOpen(false)}
                style={{
                  padding: "9px 18px",
                  borderRadius: 9,
                  background: T.surfaceAlt,
                  border: `1px solid ${T.border}`,
                  color: T.textMuted,
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                {t("common.cancel")}
              </button>
              <button
                onClick={handleAddMember}
                disabled={addSaving || !addForm.first_name || !addForm.last_name}
                style={{
                  padding: "9px 18px",
                  borderRadius: 9,
                  background: T.accent,
                  border: "none",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 700,
                  cursor: addSaving ? "not-allowed" : "pointer",
                  opacity: addSaving || !addForm.first_name || !addForm.last_name ? 0.6 : 1,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {addSaving && <Loader2 size={14} className="animate-spin" />}
                {t("common.save")}
              </button>
            </div>
          </div>
        </Modal>

        {/* CSV Import Modal */}
        <Modal open={isImportModalOpen} onClose={() => setIsImportModalOpen(false)} title={t("members.importTitle")}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {csvResult ? (
              <div
                style={{
                  padding: 32,
                  borderRadius: 14,
                  background: T.successDim,
                  border: `1px solid ${T.success}33`,
                  textAlign: "center",
                }}
              >
                <CheckCircle2 size={36} color={T.success} style={{ marginBottom: 12 }} />
                <p style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 4px" }}>
                  {t("members.import.success")}
                </p>
                <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{csvResult.filename}</p>
              </div>
            ) : (
              <>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const file = e.dataTransfer.files[0];
                    if (file && file.name.endsWith(".csv")) setCsvFile(file);
                  }}
                  style={{
                    padding: 32,
                    borderRadius: 14,
                    border: `2px dashed ${csvFile ? T.success : T.border}`,
                    background: csvFile ? T.successDim : T.surfaceAlt,
                    textAlign: "center",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  <div
                    style={{
                      width: 48,
                      height: 48,
                      borderRadius: 14,
                      background: csvFile ? `${T.success}20` : T.surface,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 12px",
                      color: csvFile ? T.success : T.textDim,
                    }}
                  >
                    {csvFile ? <CheckCircle2 size={24} /> : <CloudUpload size={24} />}
                  </div>
                  {csvFile ? (
                    <>
                      <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: "0 0 4px" }}>{csvFile.name}</p>
                      <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                        {(csvFile.size / 1024).toFixed(1)} KB
                      </p>
                    </>
                  ) : (
                    <>
                      <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: "0 0 4px" }}>
                        {t("members.import.clickOrDrop")}
                      </p>
                      <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>{t("members.import.hint")}</p>
                    </>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    style={{ display: "none" }}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) setCsvFile(file);
                    }}
                  />
                </div>

                <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                  <button
                    onClick={() => {
                      setIsImportModalOpen(false);
                      setCsvFile(null);
                    }}
                    style={{
                      padding: "9px 18px",
                      borderRadius: 9,
                      background: T.surfaceAlt,
                      border: `1px solid ${T.border}`,
                      color: T.textMuted,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    {t("common.cancel")}
                  </button>
                  <button
                    onClick={handleCsvUpload}
                    disabled={!csvFile || csvUploading}
                    style={{
                      padding: "9px 18px",
                      borderRadius: 9,
                      background: T.accent,
                      border: "none",
                      color: "#fff",
                      fontSize: 13,
                      fontWeight: 700,
                      cursor: !csvFile || csvUploading ? "not-allowed" : "pointer",
                      opacity: !csvFile || csvUploading ? 0.6 : 1,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    {csvUploading && <Loader2 size={14} className="animate-spin" />}
                    {t("members.data.import")}
                  </button>
                </div>
              </>
            )}
          </div>
        </Modal>
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════════

  if (isLoading && members.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400 }}>
        <div style={{ textAlign: "center" }}>
          <Loader2 size={28} color={T.accent} className="animate-spin" style={{ margin: "0 auto 12px", display: "block" }} />
          <span style={{ fontSize: 13, color: T.textMuted }}>{t("common.loading")}</span>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <AnimatePresence mode="wait">
        {view === "hub" && renderHub()}
        {view === "onboarding" && renderOnboarding()}
        {view === "data" && renderDataView()}
      </AnimatePresence>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════

const thStyle: CSSProperties = {
  padding: "12px 16px",
  fontSize: 11,
  fontWeight: 600,
  color: T.textDim,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  textAlign: "left",
};

// ── Method Card ──────────────────────────────────────────────────────────────

function MethodCard({
  method,
  isSelected,
  onSelect,
  isLocked = false,
  t,
}: {
  method: (typeof INTEGRATION_METHODS)[number];
  isSelected: boolean;
  onSelect: () => void;
  isLocked?: boolean;
  t: (key: string, vars?: Record<string, any>) => any;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: 24,
        borderRadius: 16,
        background: isLocked ? T.surface : isSelected ? `${method.color}12` : hovered ? T.surfaceAlt : T.surface,
        border: `1px solid ${isLocked ? T.border : isSelected ? `${method.color}55` : hovered ? T.borderLight : T.border}`,
        cursor: isLocked ? "default" : "pointer",
        opacity: isLocked ? 0.65 : 1,
        transition: "all 0.25s ease",
        transform: hovered ? "translateY(-2px)" : "none",
        boxShadow: hovered ? `0 8px 24px rgba(0,0,0,0.2)` : "none",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Subtle gradient overlay */}
      <div
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: 120,
          height: 120,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${method.color}08 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      <div style={{ position: "relative", zIndex: 1 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: 14,
            background: `${method.color}18`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: method.color,
            marginBottom: 16,
          }}
        >
          {method.icon}
        </div>

        <h3 style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
          {t(`members.hub.methods.${method.id}.title`)}
        </h3>
        <p style={{ fontSize: 12, color: T.textMuted, margin: "0 0 16px", lineHeight: 1.5 }}>
          {t(`members.hub.methods.${method.id}.desc`)}
        </p>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {method.features.map((f) => (
            <span
              key={f}
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: "3px 8px",
                borderRadius: 6,
                background: T.surfaceAlt,
                color: T.textMuted,
                border: `1px solid ${T.border}`,
              }}
            >
              {t(`members.hub.features.${f}`)}
            </span>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 18,
            color: isLocked ? T.textDim : method.color,
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {isLocked ? (
            <>
              <Shield size={14} /> {t("members.hub.upgradeRequired")}
            </>
          ) : (
            <>
              {t(`members.hub.methods.${method.id}.cta`)} <ArrowRight size={14} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Platform Card ────────────────────────────────────────────────────────────

function PlatformCard({
  platform,
  isSelected,
  isConnected,
  onSelect,
  t,
}: {
  platform: (typeof PLATFORMS)[number];
  isSelected: boolean;
  isConnected: boolean;
  onSelect: () => void;
  t: (key: string, vars?: Record<string, any>) => any;
}) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: 20,
        borderRadius: 14,
        background: isSelected ? `${platform.color}12` : hovered ? T.surfaceAlt : T.surface,
        border: `1px solid ${isSelected ? `${platform.color}55` : isConnected ? `${T.success}44` : hovered ? T.borderLight : T.border}`,
        cursor: "pointer",
        transition: "all 0.25s ease",
        transform: hovered ? "translateY(-1px)" : "none",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 14,
          background: `${platform.color}18`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: platform.color,
        }}
      >
        {platform.icon}
      </div>
      <div>
        <p style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: "0 0 2px" }}>{platform.name}</p>
        <p style={{ fontSize: 10, color: T.textDim, margin: 0, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {t(`members.platforms.categories.${platform.category}`)}
        </p>
      </div>
      {isConnected && <Badge variant="success">Connected</Badge>}
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  color,
  action,
}: {
  label: string;
  value: number;
  color: string;
  action?: React.ReactNode;
}) {
  return (
    <Card style={{ padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <p
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: T.textDim,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              margin: "0 0 6px",
            }}
          >
            {label}
          </p>
          <span style={{ fontSize: 26, fontWeight: 800, color, letterSpacing: "-0.03em" }}>{value}</span>
        </div>
        {action}
      </div>
    </Card>
  );
}

// ── Source Badge ──────────────────────────────────────────────────────────────

function SourceBadge({ source }: { source: string }) {
  const config: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
    manual: { icon: <PenLine size={11} />, color: T.textMuted, bg: T.surfaceAlt },
    csv: { icon: <FileSpreadsheet size={11} />, color: T.info, bg: T.infoDim },
    magicline: { icon: <Dumbbell size={11} />, color: "#FF6B35", bg: "rgba(255,107,53,0.12)" },
    shopify: { icon: <ShoppingBag size={11} />, color: "#96BF48", bg: "rgba(150,191,72,0.12)" },
    hubspot: { icon: <BarChart3 size={11} />, color: "#FF7A59", bg: "rgba(255,122,89,0.12)" },
    woocommerce: { icon: <ShoppingBag size={11} />, color: "#7F54B3", bg: "rgba(127,84,179,0.12)" },
    salesforce: { icon: <Globe size={11} />, color: "#00A1E0", bg: "rgba(0,161,224,0.12)" },
    api: { icon: <Terminal size={11} />, color: T.accent, bg: T.accentDim },
  };
  const c = config[source] || config.manual;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 10px",
        borderRadius: 6,
        background: c.bg,
        color: c.color,
        fontSize: 11,
        fontWeight: 600,
      }}
    >
      {c.icon} {source}
    </span>
  );
}

// ── Step Indicator ───────────────────────────────────────────────────────────

function StepIndicator({ steps, currentStep }: { steps: Array<{ title: string; desc: string }>; currentStep: number }) {
  return (
    <Card style={{ padding: "16px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
        {steps.map((step, i) => (
          <Fragment key={i}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  background: i <= currentStep ? T.accentDim : T.surfaceAlt,
                  border: `1.5px solid ${i <= currentStep ? T.accent : T.border}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: i <= currentStep ? T.accent : T.textDim,
                  fontSize: 12,
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {i < currentStep ? <Check size={14} /> : i + 1}
              </div>
              <div style={{ minWidth: 0 }}>
                <p
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: i <= currentStep ? T.text : T.textDim,
                    margin: 0,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {step.title}
                </p>
              </div>
            </div>
            {i < steps.length - 1 && (
              <div
                style={{
                  flex: "0 0 32px",
                  height: 2,
                  borderRadius: 1,
                  background: i < currentStep ? T.accent : T.border,
                  margin: "0 4px",
                }}
              />
            )}
          </Fragment>
        ))}
      </div>
    </Card>
  );
}

// ── Onboarding Header ────────────────────────────────────────────────────────

function OnboardingHeader({
  title,
  subtitle,
  onBack,
  t,
}: {
  title: string;
  subtitle: string;
  onBack: () => void;
  t: (key: string) => any;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <button
        onClick={onBack}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 36,
          height: 36,
          borderRadius: 10,
          background: T.surfaceAlt,
          border: `1px solid ${T.border}`,
          color: T.textMuted,
          cursor: "pointer",
          flexShrink: 0,
        }}
      >
        <ArrowLeft size={16} />
      </button>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>{title}</h2>
        <p style={{ fontSize: 12, color: T.textMuted, margin: "3px 0 0" }}>{subtitle}</p>
      </div>
    </div>
  );
}

// ── API Endpoint Card ────────────────────────────────────────────────────────

function ApiEndpointCard({ method, path, desc }: { method: string; path: string; desc: string }) {
  const methodColors: Record<string, string> = {
    GET: T.success,
    POST: T.accent,
    PUT: T.warning,
    DELETE: T.danger,
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 16px",
        borderRadius: 10,
        background: T.surfaceAlt,
        border: `1px solid ${T.border}`,
      }}
    >
      <span
        style={{
          fontSize: 10,
          fontWeight: 800,
          padding: "3px 8px",
          borderRadius: 5,
          background: `${methodColors[method]}18`,
          color: methodColors[method],
          letterSpacing: "0.04em",
          flexShrink: 0,
        }}
      >
        {method}
      </span>
      <code style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: "monospace" }}>{path}</code>
      <span style={{ fontSize: 11, color: T.textDim, marginLeft: "auto" }}>{desc}</span>
    </div>
  );
}

// ── Code Block ───────────────────────────────────────────────────────────────

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <div
      style={{
        position: "relative",
        borderRadius: 12,
        background: "#0D0E14",
        border: `1px solid ${T.border}`,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 14px",
          borderBottom: `1px solid ${T.border}`,
        }}
      >
        <div style={{ display: "flex", gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#FF5F57" }} />
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#FEBC2E" }} />
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#28C840" }} />
        </div>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "3px 8px",
            borderRadius: 5,
            background: "transparent",
            border: `1px solid ${T.border}`,
            color: T.textDim,
            fontSize: 10,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        style={{
          padding: 16,
          margin: 0,
          fontSize: 12,
          lineHeight: 1.6,
          color: T.text,
          fontFamily: "monospace",
          overflowX: "auto",
        }}
      >
        {code}
      </pre>
    </div>
  );
}

// ── Action Button ────────────────────────────────────────────────────────────

function ActionButton({
  onClick,
  label,
  icon,
  variant = "primary",
  iconPosition = "right",
  disabled = false,
}: {
  onClick: () => void;
  label: string;
  icon?: React.ReactNode;
  variant?: "primary" | "ghost" | "success";
  iconPosition?: "left" | "right";
  disabled?: boolean;
}) {
  const styles: Record<string, CSSProperties> = {
    primary: {
      background: T.accent,
      color: "#fff",
      border: "none",
    },
    ghost: {
      background: T.surfaceAlt,
      color: T.textMuted,
      border: `1px solid ${T.border}`,
    },
    success: {
      background: T.success,
      color: "#fff",
      border: "none",
    },
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "9px 18px",
        borderRadius: 9,
        fontSize: 13,
        fontWeight: 700,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        flexDirection: iconPosition === "left" ? "row-reverse" : "row",
        ...styles[variant],
      }}
    >
      {label} {icon}
    </button>
  );
}
