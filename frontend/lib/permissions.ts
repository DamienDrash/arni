/**
 * ARIIA – Permission & Feature Gate System (Frontend)
 *
 * Central permission management that combines role-based access control (RBAC)
 * with plan-based feature gating, LLM model access, connector quotas, add-on
 * management, and usage/overage tracking.
 *
 * Plans: Starter (79€) | Professional (199€) | Business (399€) | Enterprise
 *
 * Usage:
 *   import { usePermissions } from "@/lib/permissions";
 *   const { feature, connector, llm, canPage, plan, usage, addons } = usePermissions();
 *   if (feature("memory_analyzer")) { ... }
 *   if (connector("shopify")) { ... }
 *   if (llm.allowedModels.includes("gpt-4.1")) { ... }
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";

// ── Types ────────────────────────────────────────────────────────────────────

export type AppRole = "system_admin" | "tenant_admin" | "tenant_user";
export type PlanSlug = "starter" | "professional" | "business" | "enterprise";

export interface PlanFeatures {
  whatsapp: boolean;
  telegram: boolean;
  sms: boolean;
  email_channel: boolean;
  voice: boolean;
  instagram: boolean;
  facebook: boolean;
  google_business: boolean;
  memory_analyzer: boolean;
  custom_prompts: boolean;
  advanced_analytics: boolean;
  branding: boolean;
  audit_log: boolean;
  automation: boolean;
  api_access: boolean;
  multi_source_members: boolean;
  churn_prediction: boolean;
  vision_ai: boolean;
  white_label: boolean;
  priority_support: boolean;
  dedicated_support: boolean;
  sla: boolean;
  on_premise_option: boolean;
  custom_llm_keys: boolean;
}

export interface ConnectorAccess {
  manual: boolean;
  api: boolean;
  csv: boolean;
  magicline: boolean;
  shopify: boolean;
  woocommerce: boolean;
  hubspot: boolean;
}

export interface LlmInfo {
  allowed_models: string[];
  default_model: string;
  ai_tier: "basic" | "standard" | "premium" | "unlimited";
  custom_keys_enabled: boolean;
  max_monthly_tokens: number | null;
}

export interface PlanLimits {
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number | null;
  max_users: number | null;
  max_connectors: number | null;
  max_monthly_llm_tokens: number | null;
}

export interface OveragePricing {
  per_conversation_cents: number | null;
  per_user_cents: number | null;
  per_connector_cents: number | null;
  per_channel_cents: number | null;
}

export interface PlanInfo {
  slug: PlanSlug;
  name: string;
  price_monthly_cents: number;
  price_yearly_cents: number | null;
  is_custom_pricing: boolean;
  features: PlanFeatures;
  connectors: ConnectorAccess;
  llm: LlmInfo;
  limits: PlanLimits;
  overage: OveragePricing;
}

export interface SubscriptionInfo {
  has_subscription: boolean;
  status: string;
  billing_interval: "monthly" | "yearly";
  current_period_end?: string | null;
  trial_ends_at?: string | null;
}

export interface UsageInfo {
  messages_used: number;
  messages_inbound: number;
  messages_outbound: number;
  conversations_count: number;
  members_count: number;
  llm_tokens_used: number;
  llm_requests_count: number;
  active_channels_count: number;
  active_connectors_count: number;
  active_users_count: number;
  overage_conversations: number;
  overage_tokens: number;
  overage_billed_cents: number;
}

export interface AddonInfo {
  slug: string;
  quantity: number;
  category: string;
}

export interface Permissions {
  role: AppRole;
  plan: PlanInfo;
  subscription: SubscriptionInfo;
  usage: UsageInfo;
  addons: AddonInfo[];
  pages: Record<string, boolean>;
}

// ── Plan Hierarchy ──────────────────────────────────────────────────────────

export const PLAN_HIERARCHY: PlanSlug[] = ["starter", "professional", "business", "enterprise"];

export const PLAN_DISPLAY: Record<PlanSlug, { name: string; price: string; color: string }> = {
  starter: { name: "Starter", price: "79 €/mo", color: "#6B7280" },
  professional: { name: "Professional", price: "199 €/mo", color: "#3B82F6" },
  business: { name: "Business", price: "399 €/mo", color: "#8B5CF6" },
  enterprise: { name: "Enterprise", price: "Individuell", color: "#F59E0B" },
};

/** Minimum plan required for each feature */
export const FEATURE_MIN_PLAN: Record<string, PlanSlug> = {
  // Pro features
  telegram: "professional",
  sms: "professional",
  email_channel: "professional",
  instagram: "professional",
  facebook: "professional",
  memory_analyzer: "professional",
  custom_prompts: "professional",
  advanced_analytics: "professional",
  branding: "professional",
  audit_log: "professional",
  api_access: "professional",
  multi_source_members: "professional",
  // Business features
  voice: "business",
  google_business: "business",
  automation: "business",
  churn_prediction: "business",
  vision_ai: "business",
  priority_support: "business",
  // Enterprise features
  white_label: "enterprise",
  dedicated_support: "enterprise",
  sla: "enterprise",
  on_premise_option: "enterprise",
  custom_llm_keys: "enterprise",
};

/** LLM model display names and tiers */
export const LLM_MODELS: Record<string, { name: string; tier: string; description: string }> = {
  "gpt-4.1-nano": { name: "GPT-4.1 Nano", tier: "basic", description: "Schnell & kostengünstig" },
  "gpt-4.1-mini": { name: "GPT-4.1 Mini", tier: "standard", description: "Ausgewogen" },
  "gpt-4.1": { name: "GPT-4.1", tier: "premium", description: "Höchste Qualität" },
  "gemini-2.5-flash": { name: "Gemini 2.5 Flash", tier: "premium", description: "Schnell & leistungsstark" },
};

// ── Defaults ─────────────────────────────────────────────────────────────────

const DEFAULT_FEATURES: PlanFeatures = {
  whatsapp: true, telegram: false, sms: false, email_channel: false,
  voice: false, instagram: false, facebook: false, google_business: false,
  memory_analyzer: false, custom_prompts: false, advanced_analytics: false,
  branding: false, audit_log: false, automation: false, api_access: false,
  multi_source_members: false, churn_prediction: false, vision_ai: false,
  white_label: false, priority_support: false, dedicated_support: false,
  sla: false, on_premise_option: false, custom_llm_keys: false,
};

const DEFAULT_CONNECTORS: ConnectorAccess = {
  manual: true, api: true, csv: true,
  magicline: false, shopify: false, woocommerce: false, hubspot: false,
};

const DEFAULT_PERMISSIONS: Permissions = {
  role: "tenant_user",
  plan: {
    slug: "starter",
    name: "Starter",
    price_monthly_cents: 7900,
    price_yearly_cents: 75840,
    is_custom_pricing: false,
    features: DEFAULT_FEATURES,
    connectors: DEFAULT_CONNECTORS,
    llm: {
      allowed_models: ["gpt-4.1-nano"],
      default_model: "gpt-4.1-nano",
      ai_tier: "basic",
      custom_keys_enabled: false,
      max_monthly_tokens: 100_000,
    },
    limits: {
      max_members: 500,
      max_monthly_messages: 500,
      max_channels: 1,
      max_users: 1,
      max_connectors: 0,
      max_monthly_llm_tokens: 100_000,
    },
    overage: {
      per_conversation_cents: 5,
      per_user_cents: 1500,
      per_connector_cents: null,
      per_channel_cents: 2900,
    },
  },
  subscription: { has_subscription: false, status: "free", billing_interval: "monthly" },
  usage: {
    messages_used: 0, messages_inbound: 0, messages_outbound: 0,
    conversations_count: 0, members_count: 0, llm_tokens_used: 0,
    llm_requests_count: 0, active_channels_count: 0, active_connectors_count: 0,
    active_users_count: 0, overage_conversations: 0, overage_tokens: 0,
    overage_billed_cents: 0,
  },
  addons: [],
  pages: {},
};

// ── Cache ────────────────────────────────────────────────────────────────────

const CACHE_KEY = "ariia_permissions";
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

interface CachedPermissions {
  data: Permissions;
  timestamp: number;
}

function getCached(): Permissions | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const cached: CachedPermissions = JSON.parse(raw);
    if (Date.now() - cached.timestamp > CACHE_TTL) {
      window.sessionStorage.removeItem(CACHE_KEY);
      return null;
    }
    return cached.data;
  } catch {
    return null;
  }
}

function setCache(data: Permissions): void {
  if (typeof window === "undefined") return;
  try {
    const cached: CachedPermissions = { data, timestamp: Date.now() };
    window.sessionStorage.setItem(CACHE_KEY, JSON.stringify(cached));
  } catch {
    // ignore quota errors
  }
}

export function clearPermissionCache(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(CACHE_KEY);
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function usePermissions() {
  const [permissions, setPermissions] = useState<Permissions>(() => {
    return getCached() || DEFAULT_PERMISSIONS;
  });
  const [loading, setLoading] = useState(() => !getCached());
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (force = false) => {
    const user = getStoredUser();
    if (!user) return;

    if (!force) {
      const cached = getCached();
      if (cached) {
        setPermissions(cached);
        setLoading(false);
        return;
      }
    }

    setLoading(true);
    try {
      const res = await apiFetch("/admin/permissions");
      if (res.ok) {
        const data: Permissions = await res.json();
        setPermissions(data);
        setCache(data);
        setError(null);
      } else {
        setError("Failed to load permissions");
      }
    } catch (err: any) {
      setError(err?.message || "Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const onSessionUpdate = () => {
      clearPermissionCache();
      load(true);
    };
    window.addEventListener("ariia:session-updated", onSessionUpdate);
    return () => window.removeEventListener("ariia:session-updated", onSessionUpdate);
  }, [load]);

  // ── Feature Checks ──────────────────────────────────────────────────────

  /** Check if a feature is enabled in the current plan or via add-on */
  const feature = useCallback(
    (key: keyof PlanFeatures): boolean => {
      return permissions.plan.features[key] ?? false;
    },
    [permissions],
  );

  /** Check if a connector is available */
  const connector = useCallback(
    (key: keyof ConnectorAccess): boolean => {
      return permissions.plan.connectors[key] ?? false;
    },
    [permissions],
  );

  /** Check if a page is accessible for the current user */
  const canPage = useCallback(
    (path: string): boolean => {
      const publicPaths = ["/", "/login", "/register", "/features", "/pricing", "/impressum", "/datenschutz", "/agb"];
      if (publicPaths.includes(path)) return true;
      return permissions.pages[path] ?? false;
    },
    [permissions],
  );

  /** Check role */
  const isRole = useCallback(
    (role: AppRole): boolean => permissions.role === role,
    [permissions],
  );

  const isSystemAdmin = useMemo(() => permissions.role === "system_admin", [permissions]);
  const isTenantAdmin = useMemo(() => permissions.role === "tenant_admin", [permissions]);
  const isTenantUser = useMemo(() => permissions.role === "tenant_user", [permissions]);

  // ── Limit Checks ────────────────────────────────────────────────────────

  type LimitResource = "messages" | "members" | "llm_tokens" | "channels" | "connectors" | "users";

  const _getUsageAndLimit = useCallback(
    (resource: LimitResource): { used: number; max: number | null } => {
      const u = permissions.usage;
      const l = permissions.plan.limits;
      switch (resource) {
        case "messages": return { used: u.messages_used, max: l.max_monthly_messages };
        case "members": return { used: u.members_count, max: l.max_members };
        case "llm_tokens": return { used: u.llm_tokens_used, max: l.max_monthly_llm_tokens };
        case "channels": return { used: u.active_channels_count, max: l.max_channels };
        case "connectors": return { used: u.active_connectors_count, max: l.max_connectors };
        case "users": return { used: u.active_users_count, max: l.max_users };
        default: return { used: 0, max: null };
      }
    },
    [permissions],
  );

  /** Check if usage is near limit (>80%) */
  const isNearLimit = useCallback(
    (resource: LimitResource): boolean => {
      const { used, max } = _getUsageAndLimit(resource);
      if (max === null) return false;
      return used >= max * 0.8;
    },
    [_getUsageAndLimit],
  );

  /** Check if usage has reached the limit */
  const isAtLimit = useCallback(
    (resource: LimitResource): boolean => {
      const { used, max } = _getUsageAndLimit(resource);
      if (max === null) return false;
      return used >= max;
    },
    [_getUsageAndLimit],
  );

  /** Get usage percentage for a resource */
  const usagePercent = useCallback(
    (resource: LimitResource): number => {
      const { used, max } = _getUsageAndLimit(resource);
      if (max === null || max === 0) return 0;
      return Math.min(100, Math.round((used / max) * 100));
    },
    [_getUsageAndLimit],
  );

  // ── Plan Comparison ─────────────────────────────────────────────────────

  /** Get the minimum plan required for a feature */
  const requiredPlanFor = useCallback((key: string): PlanSlug => {
    return FEATURE_MIN_PLAN[key] || "starter";
  }, []);

  /** Check if current plan is at least the given tier */
  const isPlanAtLeast = useCallback(
    (slug: PlanSlug): boolean => {
      const currentIdx = PLAN_HIERARCHY.indexOf(permissions.plan.slug);
      const requiredIdx = PLAN_HIERARCHY.indexOf(slug);
      return currentIdx >= requiredIdx;
    },
    [permissions],
  );

  /** Check if an add-on is active */
  const hasAddon = useCallback(
    (slug: string): boolean => {
      return permissions.addons.some(a => a.slug === slug);
    },
    [permissions],
  );

  /** Get quantity of an add-on */
  const addonQuantity = useCallback(
    (slug: string): number => {
      const addon = permissions.addons.find(a => a.slug === slug);
      return addon?.quantity ?? 0;
    },
    [permissions],
  );

  // ── LLM Helpers ─────────────────────────────────────────────────────────

  const llm = useMemo(() => permissions.plan.llm, [permissions]);

  return {
    permissions,
    loading,
    error,
    reload: () => load(true),
    // Role checks
    role: permissions.role,
    isSystemAdmin,
    isTenantAdmin,
    isTenantUser,
    isRole,
    // Feature checks
    feature,
    connector,
    canPage,
    // Plan info
    plan: permissions.plan,
    planSlug: permissions.plan.slug as PlanSlug,
    subscription: permissions.subscription,
    usage: permissions.usage,
    addons: permissions.addons,
    llm,
    // Limit checks
    isNearLimit,
    isAtLimit,
    usagePercent,
    // Plan comparison
    requiredPlanFor,
    isPlanAtLeast,
    hasAddon,
    addonQuantity,
  };
}

// ── Page-Feature Mapping (for FeatureGate component) ────────────────────────

/** Maps page paths to the feature they require */
export const PAGE_FEATURE_MAP: Record<string, keyof PlanFeatures> = {
  "/member-memory": "memory_analyzer",
  "/settings/prompts": "custom_prompts",
  "/settings/branding": "branding",
  "/audit": "audit_log",
  "/settings/automation": "automation",
};
