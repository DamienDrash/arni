/**
 * ARIIA – Permission & Feature Gate System (Frontend)
 *
 * Central permission management that combines role-based access control (RBAC)
 * with plan-based feature gating. Loads permissions from the backend once per
 * session and caches them for fast access.
 *
 * Usage:
 *   import { usePermissions } from "@/lib/permissions";
 *   const { can, canPage, feature, plan, usage, loading } = usePermissions();
 *   if (feature("memory_analyzer")) { ... }
 *   if (canPage("/audit")) { ... }
 */

import { useEffect, useState, useCallback, useMemo } from "react";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";

// ── Types ────────────────────────────────────────────────────────────────────

export type AppRole = "system_admin" | "tenant_admin" | "tenant_user";

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
}

export interface PlanLimits {
  max_members: number | null;
  max_monthly_messages: number | null;
  max_channels: number;
}

export interface PlanInfo {
  slug: string;
  name: string;
  price_monthly_cents: number;
  features: PlanFeatures;
  limits: PlanLimits;
}

export interface SubscriptionInfo {
  has_subscription: boolean;
  status: string;
  current_period_end?: string | null;
  trial_ends_at?: string | null;
}

export interface UsageInfo {
  messages_used: number;
  messages_inbound: number;
  messages_outbound: number;
  members_count: number;
  llm_tokens_used: number;
}

export interface Permissions {
  role: AppRole;
  plan: PlanInfo;
  subscription: SubscriptionInfo;
  usage: UsageInfo;
  pages: Record<string, boolean>;
}

// ── Defaults ─────────────────────────────────────────────────────────────────

const DEFAULT_FEATURES: PlanFeatures = {
  whatsapp: true,
  telegram: false,
  sms: false,
  email_channel: false,
  voice: false,
  instagram: false,
  facebook: false,
  google_business: false,
  memory_analyzer: false,
  custom_prompts: false,
  advanced_analytics: false,
  branding: false,
  audit_log: false,
  automation: false,
  api_access: false,
  multi_source_members: false,
};

const DEFAULT_PERMISSIONS: Permissions = {
  role: "tenant_user",
  plan: {
    slug: "starter",
    name: "Starter",
    price_monthly_cents: 0,
    features: DEFAULT_FEATURES,
    limits: { max_members: 500, max_monthly_messages: 1000, max_channels: 1 },
  },
  subscription: { has_subscription: false, status: "free" },
  usage: { messages_used: 0, messages_inbound: 0, messages_outbound: 0, members_count: 0, llm_tokens_used: 0 },
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
    // Listen for session updates (login, impersonation)
    const onSessionUpdate = () => {
      clearPermissionCache();
      load(true);
    };
    window.addEventListener("ariia:session-updated", onSessionUpdate);
    return () => window.removeEventListener("ariia:session-updated", onSessionUpdate);
  }, [load]);

  // ── Helpers ──────────────────────────────────────────────────────────────

  /** Check if a feature is enabled in the current plan */
  const feature = useCallback(
    (key: keyof PlanFeatures): boolean => {
      return permissions.plan.features[key] ?? false;
    },
    [permissions],
  );

  /** Check if a page is accessible for the current user */
  const canPage = useCallback(
    (path: string): boolean => {
      // Public pages always accessible
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

  /** Check if usage is near limit (>80%) */
  const isNearLimit = useCallback(
    (resource: "messages" | "members"): boolean => {
      if (resource === "messages") {
        const max = permissions.plan.limits.max_monthly_messages;
        if (max === null) return false; // unlimited
        return permissions.usage.messages_used >= max * 0.8;
      }
      if (resource === "members") {
        const max = permissions.plan.limits.max_members;
        if (max === null) return false;
        return permissions.usage.members_count >= max * 0.8;
      }
      return false;
    },
    [permissions],
  );

  /** Check if usage has reached the limit */
  const isAtLimit = useCallback(
    (resource: "messages" | "members"): boolean => {
      if (resource === "messages") {
        const max = permissions.plan.limits.max_monthly_messages;
        if (max === null) return false;
        return permissions.usage.messages_used >= max;
      }
      if (resource === "members") {
        const max = permissions.plan.limits.max_members;
        if (max === null) return false;
        return permissions.usage.members_count >= max;
      }
      return false;
    },
    [permissions],
  );

  /** Get the minimum plan required for a feature */
  const requiredPlanFor = useCallback((key: keyof PlanFeatures): string => {
    // Features available in Pro
    const proFeatures: (keyof PlanFeatures)[] = [
      "telegram", "sms", "email_channel", "instagram", "facebook",
      "memory_analyzer", "custom_prompts", "advanced_analytics",
      "branding", "audit_log", "api_access", "multi_source_members",
    ];
    // Features only in Enterprise
    const enterpriseFeatures: (keyof PlanFeatures)[] = [
      "voice", "google_business", "automation",
    ];
    if (enterpriseFeatures.includes(key)) return "Enterprise";
    if (proFeatures.includes(key)) return "Pro";
    return "Starter";
  }, []);

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
    canPage,
    // Plan info
    plan: permissions.plan,
    subscription: permissions.subscription,
    usage: permissions.usage,
    // Limit checks
    isNearLimit,
    isAtLimit,
    requiredPlanFor,
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
