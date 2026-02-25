"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { T } from "@/lib/tokens";
import {
  CreditCard, Layers3, RefreshCw, Plus, Trash2, Puzzle, Loader2,
  Sparkles, Wand2, ChevronDown, ChevronUp, ArrowUpDown, Globe,
  Eye, EyeOff, Star, Zap, Shield, Check, X as XIcon, Save,
  Download, Upload, AlertTriangle, Settings2, Hash, MessageSquare,
  Users, Link2, Brain, Bot, BarChart3, Palette, ScrollText, Cpu,
  Phone, Mail, Instagram, Facebook, Radio, MapPin,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";

/* ── Types ──────────────────────────────────────────────────────────────── */

type PlanFull = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  stripe_product_id: string | null;
  stripe_price_id: string | null;
  stripe_price_yearly_id: string | null;
  price_monthly_cents: number;
  price_yearly_cents: number | null;
  trial_days: number;
  display_order: number;
  is_highlighted: boolean;
  is_active: boolean;
  is_public: boolean;
  features_json: string | null;
  features_display: string[];
  // Limits
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number;
  max_connectors: number;
  ai_tier: string;
  monthly_tokens: number;
  // Channel toggles
  whatsapp_enabled: boolean;
  telegram_enabled: boolean;
  sms_enabled: boolean;
  email_channel_enabled: boolean;
  voice_enabled: boolean;
  instagram_enabled: boolean;
  facebook_enabled: boolean;
  google_business_enabled: boolean;
  // Feature toggles
  memory_analyzer_enabled: boolean;
  custom_prompts_enabled: boolean;
  advanced_analytics_enabled: boolean;
  branding_enabled: boolean;
  audit_log_enabled: boolean;
  automation_enabled: boolean;
  api_access_enabled: boolean;
  multi_source_members_enabled: boolean;
  churn_prediction_enabled: boolean;
  vision_ai_enabled: boolean;
  white_label_enabled: boolean;
  sla_guarantee_enabled: boolean;
  on_premise_enabled: boolean;
  // Overage
  overage_conversation_cents: number;
  overage_user_cents: number;
  overage_connector_cents: number;
  overage_channel_cents: number;
  // Timestamps
  created_at: string | null;
  updated_at: string | null;
};

type AddonFull = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  category: string | null;
  icon: string | null;
  price_monthly_cents: number;
  stripe_product_id: string | null;
  stripe_price_id: string | null;
  features_json: string | null;
  features_display: string[];
  is_active: boolean;
  display_order: number;
  created_at: string | null;
  updated_at: string | null;
};

type StripeConnectors = {
  stripe: {
    enabled: boolean;
    mode: string;
    publishable_key: string;
    secret_key: string;
    webhook_secret: string;
  };
};

type SyncResult = {
  status: string;
  result?: any;
  plans?: any;
  addons?: any;
  plans_pushed?: number;
  addons_pushed?: number;
};

/* ── Styles ─────────────────────────────────────────────────────────────── */

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 13,
  padding: "10px 12px",
  outline: "none",
};

const labelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 800,
  color: T.textDim,
  textTransform: "uppercase" as const,
  letterSpacing: "0.08em",
  marginBottom: 4,
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 800,
  color: T.textMuted,
  textTransform: "uppercase" as const,
  letterSpacing: "0.1em",
  padding: "12px 0 8px",
  borderBottom: `1px solid ${T.border}`,
  marginBottom: 12,
};

const btnPrimary: React.CSSProperties = {
  padding: "12px 20px",
  background: T.accent,
  color: "#fff",
  borderRadius: 12,
  border: "none",
  fontWeight: 800,
  fontSize: 11,
  textTransform: "uppercase" as const,
  letterSpacing: "0.1em",
  cursor: "pointer",
  transition: "all 0.2s",
};

const btnSecondary: React.CSSProperties = {
  padding: "10px 16px",
  background: "rgba(255,255,255,0.05)",
  color: T.text,
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  fontWeight: 700,
  fontSize: 11,
  cursor: "pointer",
  transition: "all 0.2s",
};

const btnDanger: React.CSSProperties = {
  padding: "10px 16px",
  background: "rgba(255,107,107,0.08)",
  color: T.danger,
  borderRadius: 10,
  border: `1px solid rgba(255,107,107,0.2)`,
  fontWeight: 700,
  fontSize: 11,
  cursor: "pointer",
  transition: "all 0.2s",
};

/* ── Helpers ────────────────────────────────────────────────────────────── */

function formatEur(cents: number): string {
  return (cents / 100).toFixed(2).replace(".", ",") + " €";
}

function emptyPlan(): Partial<PlanFull> {
  return {
    name: "", slug: "", description: "", price_monthly_cents: 0,
    price_yearly_cents: null, trial_days: 0, display_order: 0,
    is_highlighted: false, is_active: true, is_public: true,
    features_json: "[]",
    max_members: 500, max_monthly_messages: 500, max_channels: 1,
    max_connectors: 0, ai_tier: "basic", monthly_tokens: 100000,
    whatsapp_enabled: true, telegram_enabled: false, sms_enabled: false,
    email_channel_enabled: false, voice_enabled: false, instagram_enabled: false,
    facebook_enabled: false, google_business_enabled: false,
    memory_analyzer_enabled: false, custom_prompts_enabled: false,
    advanced_analytics_enabled: false, branding_enabled: false,
    audit_log_enabled: false, automation_enabled: false, api_access_enabled: false,
    multi_source_members_enabled: false, churn_prediction_enabled: false,
    vision_ai_enabled: false, white_label_enabled: false,
    sla_guarantee_enabled: false, on_premise_enabled: false,
    overage_conversation_cents: 5, overage_user_cents: 1500,
    overage_connector_cents: 4900, overage_channel_cents: 2900,
  };
}

function emptyAddon(): Partial<AddonFull> {
  return {
    slug: "", name: "", description: "", category: "ai",
    icon: "Sparkles", price_monthly_cents: 0, features_json: "[]",
    is_active: true, display_order: 0,
  };
}

/* ── Toggle Row Component ───────────────────────────────────────────────── */

function ToggleRow({ label, value, onChange, icon }: {
  label: string; value: boolean; onChange: (v: boolean) => void; icon?: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "6px 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {icon}
        <span style={{ fontSize: 12, color: T.text, fontWeight: 600 }}>{label}</span>
      </div>
      <ToggleSwitch value={value} onChange={onChange} label={label} />
    </div>
  );
}

/* ── Number Input with Label ────────────────────────────────────────────── */

function NumberField({ label, value, onChange, suffix, nullable }: {
  label: string; value: number | null; onChange: (v: number | null) => void;
  suffix?: string; nullable?: boolean;
}) {
  return (
    <div style={{ flex: 1 }}>
      <div style={labelStyle}>{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <input
          style={{ ...inputStyle, flex: 1 }}
          type="number"
          value={value === null ? "" : value}
          onChange={e => {
            const v = e.target.value;
            if (v === "" && nullable) onChange(null);
            else onChange(Number(v));
          }}
          placeholder={nullable ? "∞ Unbegrenzt" : "0"}
        />
        {suffix && <span style={{ fontSize: 10, color: T.textDim, whiteSpace: "nowrap" }}>{suffix}</span>}
      </div>
    </div>
  );
}

/* ── Tab Component ──────────────────────────────────────────────────────── */

function Tabs({ tabs, active, onChange }: {
  tabs: { id: string; label: string; icon: React.ReactNode }[];
  active: string; onChange: (id: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 2, padding: 4, background: T.surfaceAlt, borderRadius: 10, marginBottom: 16 }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          style={{
            flex: 1, padding: "8px 12px", borderRadius: 8, border: "none",
            background: active === tab.id ? T.accent : "transparent",
            color: active === tab.id ? "#fff" : T.textMuted,
            fontSize: 11, fontWeight: 700, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            transition: "all 0.2s",
          }}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/* ── Main Page ──────────────────────────────────────────────────────────── */

export default function PlansPage() {
  const [plans, setPlans] = useState<PlanFull[]>([]);
  const [addons, setAddons] = useState<AddonFull[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const [activeTab, setActiveTab] = useState<"plans" | "addons" | "stripe">("plans");

  // Stripe Credentials
  const [stripeConfig, setStripeConfig] = useState<StripeConnectors["stripe"] | null>(null);
  const [stripeSaving, setStripeSaving] = useState(false);
  const [stripeTestResult, setStripeTestResult] = useState<string | null>(null);
  const [stripeTestOk, setStripeTestOk] = useState(false);

  // Plan Editor
  const [editPlan, setEditPlan] = useState<Partial<PlanFull> | null>(null);
  const [isNewPlan, setIsNewPlan] = useState(false);
  const [planTab, setPlanTab] = useState("general");
  const [saving, setSaving] = useState(false);

  // Addon Editor
  const [editAddon, setEditAddon] = useState<Partial<AddonFull> | null>(null);
  const [isNewAddon, setIsNewAddon] = useState(false);

  // Features Editor (JSON list of display strings)
  const [featuresText, setFeaturesText] = useState("");

  /* ── Data Loading ──────────────────────────────────────────────────── */

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, aRes, sRes] = await Promise.all([
        apiFetch("/admin/plans"),
        apiFetch("/admin/plans/addons"),
        apiFetch("/admin/billing/connectors"),
      ]);
      if (pRes.ok) setPlans(await pRes.json());
      if (aRes.ok) setAddons(await aRes.json());
      if (sRes.ok) {
        const data = await sRes.json();
        setStripeConfig(data.stripe);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  /* ── Sync Actions ──────────────────────────────────────────────────── */

  async function triggerSync(direction: "both" | "from" | "to") {
    setIsSyncing(true);
    setSyncResult(null);
    try {
      const endpoint = direction === "both" ? "/admin/plans/sync-now"
        : direction === "from" ? "/admin/plans/sync-from-stripe"
        : "/admin/plans/sync-to-stripe";
      const res = await apiFetch(endpoint, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSyncResult(data);
      }
      await loadData();
    } finally {
      setIsSyncing(false);
    }
  }

  async function triggerCleanup() {
    if (!confirm("Alle Pläne ohne Stripe-Anbindung und ohne aktive Abonnements löschen?")) return;
    const res = await apiFetch("/admin/plans/cleanup", { method: "POST" });
    if (res.ok) await loadData();
  }

  /* ── Stripe Credentials ────────────────────────────────────────────── */

  async function saveStripeConfig() {
    if (!stripeConfig) return;
    setStripeSaving(true);
    try {
      const res = await apiFetch("/admin/billing/connectors", {
        method: "PUT",
        body: JSON.stringify({ stripe: stripeConfig }),
      });
      if (res.ok) {
        setStripeTestResult("Gespeichert!");
        setStripeTestOk(true);
        await loadData();
      }
    } finally {
      setStripeSaving(false);
    }
  }

  async function testStripeConnection() {
    setStripeTestResult(null);
    try {
      const res = await apiFetch("/admin/billing/connectors/stripe/test", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setStripeTestResult(`Verbindung OK — Account: ${data.account_id}, Charges: ${data.charges_enabled ? "Ja" : "Nein"}`);
        setStripeTestOk(true);
      } else {
        const err = await res.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        setStripeTestResult(`Fehler: ${err.detail || "Verbindung fehlgeschlagen"}`);
        setStripeTestOk(false);
      }
    } catch {
      setStripeTestResult("Netzwerkfehler");
      setStripeTestOk(false);
    }
  }

  /* ── Plan CRUD ─────────────────────────────────────────────────────── */

  function openPlanEditor(plan?: PlanFull) {
    if (plan) {
      setEditPlan({ ...plan });
      setIsNewPlan(false);
      setFeaturesText(plan.features_json || "[]");
    } else {
      setEditPlan(emptyPlan());
      setIsNewPlan(true);
      setFeaturesText("[]");
    }
    setPlanTab("general");
  }

  async function savePlan() {
    if (!editPlan) return;
    setSaving(true);
    try {
      // Parse features_json
      let parsedFeatures: string[] = [];
      try { parsedFeatures = JSON.parse(featuresText); } catch { /* ignore */ }
      const payload = { ...editPlan, features_json: JSON.stringify(parsedFeatures) };

      const res = isNewPlan
        ? await apiFetch("/admin/plans", { method: "POST", body: JSON.stringify(payload) })
        : await apiFetch(`/admin/plans/${editPlan.id}`, { method: "PATCH", body: JSON.stringify(payload) });

      if (res.ok) {
        setEditPlan(null);
        await loadData();
      } else {
        const err = await res.json().catch(() => ({ detail: "Fehler" }));
        alert(err.detail || "Speichern fehlgeschlagen");
      }
    } finally {
      setSaving(false);
    }
  }

  async function deletePlan(id: number) {
    if (!confirm("Diesen Plan wirklich löschen? Aktive Abonnements verhindern das Löschen.")) return;
    const res = await apiFetch(`/admin/plans/${id}`, { method: "DELETE" });
    if (res.ok) {
      await loadData();
    } else {
      const err = await res.json().catch(() => ({ detail: "Fehler" }));
      alert(err.detail || "Löschen fehlgeschlagen");
    }
  }

  /* ── Addon CRUD ────────────────────────────────────────────────────── */

  function openAddonEditor(addon?: AddonFull) {
    if (addon) {
      setEditAddon({ ...addon });
      setIsNewAddon(false);
    } else {
      setEditAddon(emptyAddon());
      setIsNewAddon(true);
    }
  }

  async function saveAddon() {
    if (!editAddon) return;
    setSaving(true);
    try {
      const res = isNewAddon
        ? await apiFetch("/admin/plans/addons", { method: "POST", body: JSON.stringify(editAddon) })
        : await apiFetch(`/admin/plans/addons/${editAddon.id}`, { method: "PATCH", body: JSON.stringify(editAddon) });

      if (res.ok) {
        setEditAddon(null);
        await loadData();
      } else {
        const err = await res.json().catch(() => ({ detail: "Fehler" }));
        alert(err.detail || "Speichern fehlgeschlagen");
      }
    } finally {
      setSaving(false);
    }
  }

  async function deleteAddon(id: number) {
    if (!confirm("Dieses Add-on wirklich löschen?")) return;
    const res = await apiFetch(`/admin/plans/addons/${id}`, { method: "DELETE" });
    if (res.ok) await loadData();
  }

  /* ── Render ────────────────────────────────────────────────────────── */

  if (loading) {
    return (
      <div style={{ padding: 80, textAlign: "center", color: T.textMuted }}>
        <Loader2 size={32} style={{ animation: "spin 1s linear infinite" }} />
        <p style={{ marginTop: 16, fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Lade Billing-Infrastruktur...
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, paddingBottom: 80 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 900, color: "#fff", textTransform: "uppercase", letterSpacing: "-0.02em" }}>
            Billing Infrastructure
          </h1>
          <p style={{ fontSize: 13, color: T.textMuted, marginTop: 4 }}>
            Pläne, Add-ons und Stripe-Konfiguration zentral verwalten.
          </p>
        </div>
      </div>

      {/* Main Tabs */}
      <Tabs
        active={activeTab}
        onChange={(id) => setActiveTab(id as any)}
        tabs={[
          { id: "plans", label: "Pläne", icon: <Layers3 size={14} /> },
          { id: "addons", label: "Add-ons", icon: <Puzzle size={14} /> },
          { id: "stripe", label: "Stripe Credentials", icon: <CreditCard size={14} /> },
        ]}
      />

      {/* ═══ PLANS TAB ═══ */}
      {activeTab === "plans" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Actions Bar */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button onClick={() => triggerSync("both")} disabled={isSyncing} style={{ ...btnSecondary, display: "flex", alignItems: "center", gap: 6 }}>
              <ArrowUpDown size={14} className={isSyncing ? "animate-spin" : ""} />
              Bidirektionaler Sync
            </button>
            <button onClick={() => triggerSync("from")} disabled={isSyncing} style={{ ...btnSecondary, display: "flex", alignItems: "center", gap: 6 }}>
              <Download size={14} /> Von Stripe holen
            </button>
            <button onClick={() => triggerSync("to")} disabled={isSyncing} style={{ ...btnSecondary, display: "flex", alignItems: "center", gap: 6 }}>
              <Upload size={14} /> Zu Stripe pushen
            </button>
            <button onClick={triggerCleanup} style={{ ...btnDanger, display: "flex", alignItems: "center", gap: 6 }}>
              <Wand2 size={14} /> Cleanup
            </button>
            <div style={{ flex: 1 }} />
            <button onClick={() => openPlanEditor()} style={{ ...btnPrimary, display: "flex", alignItems: "center", gap: 6 }}>
              <Plus size={16} /> Neuer Plan
            </button>
          </div>

          {/* Sync Result Banner */}
          {syncResult && (
            <div style={{
              padding: "12px 16px", borderRadius: 10,
              background: syncResult.status === "ok" ? T.successDim : T.dangerDim,
              border: `1px solid ${syncResult.status === "ok" ? "rgba(0,214,143,0.3)" : "rgba(255,107,107,0.3)"}`,
              fontSize: 12, color: T.text,
            }}>
              <strong>Sync-Ergebnis:</strong> {JSON.stringify(syncResult.result || syncResult, null, 2).slice(0, 300)}
            </div>
          )}

          {/* Plans Grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
            {plans.map(p => (
              <Card key={p.id} style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12, opacity: p.is_active ? 1 : 0.5, position: "relative" }}>
                {/* Highlighted Badge */}
                {p.is_highlighted && (
                  <div style={{
                    position: "absolute", top: -1, right: 20, padding: "4px 12px",
                    background: T.accent, color: "#fff", fontSize: 9, fontWeight: 800,
                    textTransform: "uppercase", letterSpacing: "0.1em", borderRadius: "0 0 8px 8px",
                  }}>
                    <Star size={10} style={{ display: "inline", marginRight: 4 }} /> Empfohlen
                  </div>
                )}

                {/* Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 800, color: "#fff" }}>{p.name}</h3>
                    <code style={{ fontSize: 9, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.1em" }}>{p.slug}</code>
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <Badge variant={p.is_active ? "success" : "danger"} size="xs">{p.is_active ? "Live" : "Inaktiv"}</Badge>
                    {p.is_public && <Badge variant="info" size="xs"><Globe size={8} /> Public</Badge>}
                  </div>
                </div>

                {/* Description */}
                {p.description && (
                  <p style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.4 }}>{p.description}</p>
                )}

                {/* Price */}
                <div>
                  <span style={{ fontSize: 28, fontWeight: 900, color: "#fff" }}>
                    {p.price_monthly_cents === 0 ? "Custom" : formatEur(p.price_monthly_cents)}
                  </span>
                  <span style={{ fontSize: 11, color: T.textDim, marginLeft: 4 }}>/Monat</span>
                  {p.price_yearly_cents != null && p.price_yearly_cents > 0 && (
                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>
                      Jährlich: {formatEur(p.price_yearly_cents)}
                    </div>
                  )}
                </div>

                {/* Limits Summary */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, fontSize: 10, color: T.textMuted }}>
                  <span><Users size={10} style={{ display: "inline", marginRight: 4 }} />{p.max_members === null ? "∞" : p.max_members} Mitglieder</span>
                  <span><MessageSquare size={10} style={{ display: "inline", marginRight: 4 }} />{p.max_monthly_messages === null ? "∞" : p.max_monthly_messages} Nachr./Mo</span>
                  <span><Hash size={10} style={{ display: "inline", marginRight: 4 }} />{p.max_channels} Kanäle</span>
                  <span><Link2 size={10} style={{ display: "inline", marginRight: 4 }} />{p.max_connectors} Connectors</span>
                </div>

                {/* Stripe IDs */}
                <div style={{ fontSize: 9, fontFamily: "monospace", color: T.textDim, padding: 8, background: "rgba(255,255,255,0.02)", borderRadius: 8, border: `1px solid ${T.border}` }}>
                  <div style={{ color: p.stripe_product_id ? T.textDim : T.danger }}>
                    Prod: {p.stripe_product_id || "NICHT VERKNÜPFT"}
                  </div>
                  <div style={{ color: p.stripe_price_id ? T.textDim : T.danger }}>
                    Price: {p.stripe_price_id || "NICHT VERKNÜPFT"}
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <button onClick={() => openPlanEditor(p)} style={{ ...btnSecondary, flex: 1, textAlign: "center" }}>
                    Bearbeiten
                  </button>
                  <button onClick={() => deletePlan(p.id)} style={{ ...btnDanger, padding: "10px 12px" }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </Card>
            ))}
          </div>

          {plans.length === 0 && (
            <div style={{ textAlign: "center", padding: 60, color: T.textMuted }}>
              <Layers3 size={48} style={{ opacity: 0.3, margin: "0 auto 16px" }} />
              <p style={{ fontSize: 14, fontWeight: 700 }}>Keine Pläne vorhanden</p>
              <p style={{ fontSize: 12, marginTop: 4 }}>Erstelle einen neuen Plan oder synchronisiere von Stripe.</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ ADDONS TAB ═══ */}
      {activeTab === "addons" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button onClick={() => openAddonEditor()} style={{ ...btnPrimary, display: "flex", alignItems: "center", gap: 6 }}>
              <Plus size={16} /> Neues Add-on
            </button>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
            {addons.map(a => (
              <Card key={a.id} style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12, opacity: a.is_active ? 1 : 0.5 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{
                      width: 44, height: 44, borderRadius: 14,
                      background: "rgba(108,92,231,0.1)", display: "flex",
                      alignItems: "center", justifyContent: "center", color: T.accent,
                    }}>
                      <Sparkles size={22} />
                    </div>
                    <div>
                      <h4 style={{ fontSize: 14, fontWeight: 800, color: "#fff" }}>{a.name}</h4>
                      <code style={{ fontSize: 9, color: T.textDim }}>{a.slug}</code>
                    </div>
                  </div>
                  <Badge variant={a.is_active ? "success" : "danger"} size="xs">{a.is_active ? "Aktiv" : "Inaktiv"}</Badge>
                </div>

                {a.description && (
                  <p style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.4 }}>{a.description}</p>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 20, fontWeight: 900, color: "#fff" }}>{formatEur(a.price_monthly_cents)}<span style={{ fontSize: 11, color: T.textDim }}>/Mo</span></span>
                  {a.category && <Badge variant="default" size="xs">{a.category}</Badge>}
                </div>

                <div style={{ fontSize: 9, fontFamily: "monospace", color: T.textDim }}>
                  Stripe: {a.stripe_product_id || "—"} / {a.stripe_price_id || "—"}
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => openAddonEditor(a)} style={{ ...btnSecondary, flex: 1, textAlign: "center" }}>Bearbeiten</button>
                  <button onClick={() => deleteAddon(a.id)} style={{ ...btnDanger, padding: "10px 12px" }}><Trash2 size={14} /></button>
                </div>
              </Card>
            ))}
          </div>

          {addons.length === 0 && (
            <div style={{ textAlign: "center", padding: 60, color: T.textMuted }}>
              <Puzzle size={48} style={{ opacity: 0.3, margin: "0 auto 16px" }} />
              <p style={{ fontSize: 14, fontWeight: 700 }}>Keine Add-ons vorhanden</p>
              <p style={{ fontSize: 12, marginTop: 4 }}>Erstelle ein neues Add-on oder synchronisiere von Stripe.</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ STRIPE CREDENTIALS TAB ═══ */}
      {activeTab === "stripe" && stripeConfig && (
        <Card style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: "linear-gradient(135deg, #635BFF, #A259FF)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <CreditCard size={24} color="#fff" />
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>Stripe Konfiguration</h2>
              <p style={{ fontSize: 12, color: T.textMuted }}>API-Schlüssel und Webhook-Konfiguration für die Stripe-Anbindung.</p>
            </div>
          </div>

          {/* Enabled Toggle */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: T.surfaceAlt, borderRadius: 12, border: `1px solid ${T.border}` }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Stripe aktiviert</div>
              <div style={{ fontSize: 11, color: T.textMuted }}>Aktiviert die Stripe-Integration für Abonnements und Zahlungen.</div>
            </div>
            <ToggleSwitch value={stripeConfig.enabled} onChange={v => setStripeConfig({ ...stripeConfig, enabled: v })} label="Stripe aktiviert" />
          </div>

          {/* Mode */}
          <div>
            <div style={labelStyle}>Modus</div>
            <div style={{ display: "flex", gap: 8 }}>
              {["test", "live"].map(mode => (
                <button
                  key={mode}
                  onClick={() => setStripeConfig({ ...stripeConfig, mode })}
                  style={{
                    flex: 1, padding: "10px 16px", borderRadius: 10,
                    border: `1px solid ${stripeConfig.mode === mode ? T.accent : T.border}`,
                    background: stripeConfig.mode === mode ? "rgba(108,92,231,0.1)" : T.surfaceAlt,
                    color: stripeConfig.mode === mode ? T.accent : T.textMuted,
                    fontWeight: 700, fontSize: 12, cursor: "pointer", transition: "all 0.2s",
                    textTransform: "uppercase",
                  }}
                >
                  {mode === "test" ? "🧪 Test-Modus" : "🔴 Live-Modus"}
                </button>
              ))}
            </div>
          </div>

          {/* Keys */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <div style={labelStyle}>Publishable Key</div>
              <input
                style={inputStyle}
                value={stripeConfig.publishable_key}
                onChange={e => setStripeConfig({ ...stripeConfig, publishable_key: e.target.value })}
                placeholder={stripeConfig.mode === "test" ? "pk_test_..." : "pk_live_..."}
              />
            </div>
            <div>
              <div style={labelStyle}>Secret Key</div>
              <input
                style={inputStyle}
                type="password"
                value={stripeConfig.secret_key}
                onChange={e => setStripeConfig({ ...stripeConfig, secret_key: e.target.value })}
                placeholder={stripeConfig.mode === "test" ? "sk_test_..." : "sk_live_..."}
              />
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 4 }}>
                Wird verschlüsselt in der Datenbank gespeichert. Angezeigt als Maske wenn bereits gesetzt.
              </div>
            </div>
            <div>
              <div style={labelStyle}>Webhook Secret</div>
              <input
                style={inputStyle}
                type="password"
                value={stripeConfig.webhook_secret}
                onChange={e => setStripeConfig({ ...stripeConfig, webhook_secret: e.target.value })}
                placeholder="whsec_..."
              />
              <div style={{ fontSize: 10, color: T.textDim, marginTop: 4 }}>
                Webhook-Endpoint: <code style={{ color: T.accent }}>/billing/webhook</code> — Events: checkout.session.completed, customer.subscription.*, invoice.*, product.*, price.*
              </div>
            </div>
          </div>

          {/* Test Result */}
          {stripeTestResult && (
            <div style={{
              padding: "12px 16px", borderRadius: 10,
              background: stripeTestOk ? T.successDim : T.dangerDim,
              border: `1px solid ${stripeTestOk ? "rgba(0,214,143,0.3)" : "rgba(255,107,107,0.3)"}`,
              fontSize: 12, color: T.text,
            }}>
              {stripeTestOk ? <Check size={14} style={{ display: "inline", marginRight: 6 }} /> : <AlertTriangle size={14} style={{ display: "inline", marginRight: 6 }} />}
              {stripeTestResult}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button onClick={testStripeConnection} style={{ ...btnSecondary, display: "flex", alignItems: "center", gap: 6 }}>
              <Zap size={14} /> Verbindung testen
            </button>
            <button onClick={saveStripeConfig} disabled={stripeSaving} style={{ ...btnPrimary, display: "flex", alignItems: "center", gap: 6 }}>
              <Save size={14} /> {stripeSaving ? "Speichert..." : "Speichern"}
            </button>
          </div>
        </Card>
      )}

      {/* ═══ PLAN EDITOR MODAL ═══ */}
      <Modal
        open={editPlan !== null}
        onClose={() => setEditPlan(null)}
        title={isNewPlan ? "Neuen Plan erstellen" : `Plan bearbeiten: ${editPlan?.name || ""}`}
        width="min(960px, 95vw)"
        footer={
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setEditPlan(null)} style={btnSecondary}>Abbrechen</button>
            <button onClick={savePlan} disabled={saving} style={btnPrimary}>
              {saving ? "Speichert..." : isNewPlan ? "Erstellen & Stripe Sync" : "Speichern & Stripe Sync"}
            </button>
          </div>
        }
      >
        {editPlan && (
          <div>
            {/* Sub-Tabs */}
            <Tabs
              active={planTab}
              onChange={setPlanTab}
              tabs={[
                { id: "general", label: "Allgemein", icon: <Settings2 size={12} /> },
                { id: "limits", label: "Limits", icon: <Shield size={12} /> },
                { id: "channels", label: "Kanäle", icon: <Radio size={12} /> },
                { id: "features", label: "Features", icon: <Zap size={12} /> },
                { id: "display", label: "Anzeige", icon: <Eye size={12} /> },
                { id: "overage", label: "Overage", icon: <AlertTriangle size={12} /> },
              ]}
            />

            {/* General Tab */}
            {planTab === "general" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <div style={labelStyle}>Name</div>
                    <input style={inputStyle} value={editPlan.name || ""} onChange={e => setEditPlan({ ...editPlan, name: e.target.value })} placeholder="z.B. Professional" />
                  </div>
                  <div>
                    <div style={labelStyle}>Slug</div>
                    <input style={inputStyle} value={editPlan.slug || ""} onChange={e => setEditPlan({ ...editPlan, slug: e.target.value })} placeholder="z.B. pro" disabled={!isNewPlan} />
                  </div>
                </div>
                <div>
                  <div style={labelStyle}>Beschreibung</div>
                  <textarea
                    style={{ ...inputStyle, minHeight: 60, resize: "vertical" }}
                    value={editPlan.description || ""}
                    onChange={e => setEditPlan({ ...editPlan, description: e.target.value })}
                    placeholder="Kurze Beschreibung für Landing Page und Pricing..."
                  />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
                  <NumberField label="Monatspreis (Cent)" value={editPlan.price_monthly_cents ?? 0} onChange={v => setEditPlan({ ...editPlan, price_monthly_cents: v ?? 0 })} suffix="ct" />
                  <NumberField label="Jahrespreis (Cent)" value={editPlan.price_yearly_cents ?? null} onChange={v => setEditPlan({ ...editPlan, price_yearly_cents: v })} suffix="ct" nullable />
                  <NumberField label="Trial (Tage)" value={editPlan.trial_days ?? 0} onChange={v => setEditPlan({ ...editPlan, trial_days: v ?? 0 })} suffix="Tage" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <div style={labelStyle}>AI Tier</div>
                    <select
                      style={inputStyle}
                      value={editPlan.ai_tier || "basic"}
                      onChange={e => setEditPlan({ ...editPlan, ai_tier: e.target.value })}
                    >
                      <option value="basic">Basic</option>
                      <option value="standard">Standard</option>
                      <option value="premium">Premium</option>
                      <option value="unlimited">Unlimited</option>
                    </select>
                  </div>
                  <NumberField label="Monatliche Tokens" value={editPlan.monthly_tokens ?? 100000} onChange={v => setEditPlan({ ...editPlan, monthly_tokens: v ?? 100000 })} />
                </div>
                <div style={{ display: "flex", gap: 16, padding: "8px 0" }}>
                  <ToggleRow label="Aktiv" value={editPlan.is_active ?? true} onChange={v => setEditPlan({ ...editPlan, is_active: v })} icon={<Check size={14} color={T.success} />} />
                  <ToggleRow label="Öffentlich" value={editPlan.is_public ?? true} onChange={v => setEditPlan({ ...editPlan, is_public: v })} icon={<Globe size={14} color={T.info} />} />
                  <ToggleRow label="Hervorgehoben" value={editPlan.is_highlighted ?? false} onChange={v => setEditPlan({ ...editPlan, is_highlighted: v })} icon={<Star size={14} color={T.warning} />} />
                </div>
              </div>
            )}

            {/* Limits Tab */}
            {planTab === "limits" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <NumberField label="Max Mitglieder" value={editPlan.max_members ?? null} onChange={v => setEditPlan({ ...editPlan, max_members: v })} nullable suffix="(leer = ∞)" />
                <NumberField label="Max Nachrichten/Monat" value={editPlan.max_monthly_messages ?? null} onChange={v => setEditPlan({ ...editPlan, max_monthly_messages: v })} nullable suffix="(leer = ∞)" />
                <NumberField label="Max Kanäle" value={editPlan.max_channels ?? 1} onChange={v => setEditPlan({ ...editPlan, max_channels: v ?? 1 })} />
                <NumberField label="Max Connectors" value={editPlan.max_connectors ?? 0} onChange={v => setEditPlan({ ...editPlan, max_connectors: v ?? 0 })} />
              </div>
            )}

            {/* Channels Tab */}
            {planTab === "channels" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                <ToggleRow label="WhatsApp" value={editPlan.whatsapp_enabled ?? true} onChange={v => setEditPlan({ ...editPlan, whatsapp_enabled: v })} icon={<MessageSquare size={14} color="#25D366" />} />
                <ToggleRow label="Telegram" value={editPlan.telegram_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, telegram_enabled: v })} icon={<MessageSquare size={14} color="#0088CC" />} />
                <ToggleRow label="SMS" value={editPlan.sms_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, sms_enabled: v })} icon={<Phone size={14} color={T.accent} />} />
                <ToggleRow label="E-Mail Kanal" value={editPlan.email_channel_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, email_channel_enabled: v })} icon={<Mail size={14} color={T.danger} />} />
                <ToggleRow label="Voice" value={editPlan.voice_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, voice_enabled: v })} icon={<Phone size={14} color={T.accent} />} />
                <ToggleRow label="Instagram" value={editPlan.instagram_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, instagram_enabled: v })} icon={<Instagram size={14} color="#E4405F" />} />
                <ToggleRow label="Facebook" value={editPlan.facebook_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, facebook_enabled: v })} icon={<Facebook size={14} color="#1877F2" />} />
                <ToggleRow label="Google Business" value={editPlan.google_business_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, google_business_enabled: v })} icon={<MapPin size={14} color="#4285F4" />} />
              </div>
            )}

            {/* Features Tab */}
            {planTab === "features" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div style={sectionTitleStyle}>Feature-Toggles</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                  <ToggleRow label="Memory Analyzer" value={editPlan.memory_analyzer_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, memory_analyzer_enabled: v })} icon={<Brain size={14} />} />
                  <ToggleRow label="Custom Prompts" value={editPlan.custom_prompts_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, custom_prompts_enabled: v })} icon={<Bot size={14} />} />
                  <ToggleRow label="Advanced Analytics" value={editPlan.advanced_analytics_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, advanced_analytics_enabled: v })} icon={<BarChart3 size={14} />} />
                  <ToggleRow label="Branding" value={editPlan.branding_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, branding_enabled: v })} icon={<Palette size={14} />} />
                  <ToggleRow label="Audit Log" value={editPlan.audit_log_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, audit_log_enabled: v })} icon={<ScrollText size={14} />} />
                  <ToggleRow label="Automation" value={editPlan.automation_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, automation_enabled: v })} icon={<Cpu size={14} />} />
                  <ToggleRow label="API Access" value={editPlan.api_access_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, api_access_enabled: v })} icon={<Link2 size={14} />} />
                  <ToggleRow label="Multi-Source Members" value={editPlan.multi_source_members_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, multi_source_members_enabled: v })} icon={<Users size={14} />} />
                  <ToggleRow label="Churn Prediction" value={editPlan.churn_prediction_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, churn_prediction_enabled: v })} icon={<AlertTriangle size={14} />} />
                  <ToggleRow label="Vision AI" value={editPlan.vision_ai_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, vision_ai_enabled: v })} icon={<Eye size={14} />} />
                  <ToggleRow label="White Label" value={editPlan.white_label_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, white_label_enabled: v })} icon={<Shield size={14} />} />
                  <ToggleRow label="SLA Garantie" value={editPlan.sla_guarantee_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, sla_guarantee_enabled: v })} icon={<Shield size={14} />} />
                  <ToggleRow label="On-Premise" value={editPlan.on_premise_enabled ?? false} onChange={v => setEditPlan({ ...editPlan, on_premise_enabled: v })} icon={<Settings2 size={14} />} />
                </div>
              </div>
            )}

            {/* Display Tab */}
            {planTab === "display" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <NumberField label="Sortierung (Display Order)" value={editPlan.display_order ?? 0} onChange={v => setEditPlan({ ...editPlan, display_order: v ?? 0 })} />
                <div>
                  <div style={labelStyle}>Feature-Liste für Anzeige (JSON Array)</div>
                  <textarea
                    style={{ ...inputStyle, minHeight: 120, fontFamily: "monospace", fontSize: 12 }}
                    value={featuresText}
                    onChange={e => setFeaturesText(e.target.value)}
                    placeholder='["WhatsApp", "500 Mitglieder", "Basic AI"]'
                  />
                  <div style={{ fontSize: 10, color: T.textDim, marginTop: 4 }}>
                    JSON-Array mit Strings. Wird auf der Pricing-Seite und im Billing-Bereich angezeigt.
                  </div>
                </div>
              </div>
            )}

            {/* Overage Tab */}
            {planTab === "overage" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <NumberField label="Overage pro Konversation" value={editPlan.overage_conversation_cents ?? 5} onChange={v => setEditPlan({ ...editPlan, overage_conversation_cents: v ?? 5 })} suffix="Cent" />
                <NumberField label="Overage pro User" value={editPlan.overage_user_cents ?? 1500} onChange={v => setEditPlan({ ...editPlan, overage_user_cents: v ?? 1500 })} suffix="Cent" />
                <NumberField label="Overage pro Connector" value={editPlan.overage_connector_cents ?? 4900} onChange={v => setEditPlan({ ...editPlan, overage_connector_cents: v ?? 4900 })} suffix="Cent" />
                <NumberField label="Overage pro Kanal" value={editPlan.overage_channel_cents ?? 2900} onChange={v => setEditPlan({ ...editPlan, overage_channel_cents: v ?? 2900 })} suffix="Cent" />
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* ═══ ADDON EDITOR MODAL ═══ */}
      <Modal
        open={editAddon !== null}
        onClose={() => setEditAddon(null)}
        title={isNewAddon ? "Neues Add-on erstellen" : `Add-on bearbeiten: ${editAddon?.name || ""}`}
        footer={
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setEditAddon(null)} style={btnSecondary}>Abbrechen</button>
            <button onClick={saveAddon} disabled={saving} style={btnPrimary}>
              {saving ? "Speichert..." : isNewAddon ? "Erstellen & Stripe Sync" : "Speichern & Stripe Sync"}
            </button>
          </div>
        }
      >
        {editAddon && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <div style={labelStyle}>Name</div>
                <input style={inputStyle} value={editAddon.name || ""} onChange={e => setEditAddon({ ...editAddon, name: e.target.value })} placeholder="z.B. Voice Pipeline" />
              </div>
              <div>
                <div style={labelStyle}>Slug</div>
                <input style={inputStyle} value={editAddon.slug || ""} onChange={e => setEditAddon({ ...editAddon, slug: e.target.value })} placeholder="z.B. voice_pipeline" disabled={!isNewAddon} />
              </div>
            </div>
            <div>
              <div style={labelStyle}>Beschreibung</div>
              <textarea
                style={{ ...inputStyle, minHeight: 60, resize: "vertical" }}
                value={editAddon.description || ""}
                onChange={e => setEditAddon({ ...editAddon, description: e.target.value })}
                placeholder="Beschreibung des Add-ons..."
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <NumberField label="Monatspreis (Cent)" value={editAddon.price_monthly_cents ?? 0} onChange={v => setEditAddon({ ...editAddon, price_monthly_cents: v ?? 0 })} suffix="ct" />
              <div>
                <div style={labelStyle}>Kategorie</div>
                <select style={inputStyle} value={editAddon.category || "ai"} onChange={e => setEditAddon({ ...editAddon, category: e.target.value })}>
                  <option value="ai">AI</option>
                  <option value="channel">Channel</option>
                  <option value="analytics">Analytics</option>
                  <option value="integration">Integration</option>
                  <option value="security">Security</option>
                </select>
              </div>
              <NumberField label="Sortierung" value={editAddon.display_order ?? 0} onChange={v => setEditAddon({ ...editAddon, display_order: v ?? 0 })} />
            </div>
            <ToggleRow label="Aktiv" value={editAddon.is_active ?? true} onChange={v => setEditAddon({ ...editAddon, is_active: v })} icon={<Check size={14} color={T.success} />} />
          </div>
        )}
      </Modal>
    </div>
  );
}
