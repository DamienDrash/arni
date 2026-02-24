/**
 * ARIIA – Role-Based Access Control (RBAC)
 *
 * Defines which pages each role can access. This is the client-side enforcement
 * layer that works in tandem with the backend permission system.
 *
 * The backend `/admin/permissions` endpoint is the source of truth and includes
 * plan-based feature gating. This file provides fast synchronous checks for
 * navigation guards and sidebar filtering.
 */

export type AppRole = "system_admin" | "tenant_admin" | "tenant_user";

type RoleAccess = {
  exact: string[];
  prefixes: string[];
};

const ROLE_ACCESS: Record<AppRole, RoleAccess> = {
  system_admin: {
    exact: [
      "/", "/dashboard", "/features", "/pricing", "/impressum", "/datenschutz", "/agb",
      "/users", "/tenants", "/system-prompt", "/plans", "/audit",
      "/settings", "/settings/account", "/settings/general", "/settings/ai",
    ],
    prefixes: [
      "/users/", "/tenants/", "/plans/", "/audit/",
      "/settings/", "/settings/account/", "/settings/general/", "/settings/ai/",
    ],
  },
  tenant_admin: {
    exact: [
      "/", "/dashboard", "/features", "/pricing", "/impressum", "/datenschutz", "/agb",
      "/live", "/escalations", "/analytics", "/members", "/users",
      "/knowledge", "/member-memory", "/magicline", "/audit",
      "/settings", "/settings/integrations", "/settings/prompts",
      "/settings/billing", "/settings/branding", "/settings/account",
      "/settings/automation",
    ],
    prefixes: [
      "/live/", "/escalations/", "/analytics/", "/members/", "/users/",
      "/knowledge/", "/member-memory/", "/magicline/", "/audit/",
      "/settings/integrations/", "/settings/prompts/", "/settings/billing/",
      "/settings/branding/", "/settings/account/", "/settings/automation/",
    ],
  },
  tenant_user: {
    exact: [
      "/", "/dashboard", "/features", "/pricing", "/impressum", "/datenschutz", "/agb",
      "/live", "/escalations", "/analytics",
      "/settings", "/settings/account",
    ],
    prefixes: [
      "/live/", "/escalations/", "/analytics/",
      "/settings/account/",
    ],
  },
};

export function allowedPrefixesForRole(role: AppRole | undefined): string[] {
  if (!role) return ["/", "/features", "/pricing", "/impressum", "/datenschutz", "/agb"];
  const access = ROLE_ACCESS[role];
  if (!access) return ["/", "/features", "/pricing", "/impressum", "/datenschutz", "/agb"];
  return [...access.exact, ...access.prefixes];
}

export function isPathAllowedForRole(role: AppRole | undefined, path: string): boolean {
  const normalized = (path || "/").replace(/\/+$/, "") || "/";
  if (
    normalized === "/login" ||
    normalized === "/register" ||
    normalized === "/features" ||
    normalized === "/pricing" ||
    normalized === "/impressum" ||
    normalized === "/datenschutz" ||
    normalized === "/agb"
  )
    return true;
  if (!role) return normalized === "/";
  const access = ROLE_ACCESS[role];
  if (!access) return normalized === "/";

  if (access.exact.includes(normalized)) return true;
  return access.prefixes.some((prefix) => normalized.startsWith(prefix));
}

/**
 * Maps pages to the plan feature they require.
 * Pages not listed here are accessible to any role that has path access.
 */
export const PAGE_FEATURE_REQUIREMENTS: Record<string, string> = {
  "/member-memory": "memory_analyzer",
  "/settings/prompts": "custom_prompts",
  "/settings/branding": "branding",
  "/audit": "audit_log",
  "/settings/automation": "automation",
};
