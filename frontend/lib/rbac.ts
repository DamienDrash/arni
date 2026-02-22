export type AppRole = "system_admin" | "tenant_admin" | "tenant_user";

type RoleAccess = {
  exact: string[];
  prefixes: string[];
};

const ROLE_ACCESS: Record<AppRole, RoleAccess> = {
  system_admin: {
    exact: ["/", "/users", "/tenants", "/system-prompt", "/plans", "/audit", "/settings", "/settings/account"],
    prefixes: ["/users/", "/tenants/", "/plans/", "/audit/", "/settings/", "/settings/account/"],
  },
  tenant_admin: {
    exact: [
      "/",
      "/live",
      "/escalations",
      "/analytics",
      "/members",
      "/users",
      "/knowledge",
      "/member-memory",
      "/magicline",
      "/audit",
      "/settings",
      "/settings/integrations",
      "/settings/prompts",
      "/settings/billing",
      "/settings/branding",
      "/settings/account",
    ],
    prefixes: [
      "/live/",
      "/escalations/",
      "/analytics/",
      "/members/",
      "/users/",
      "/knowledge/",
      "/member-memory/",
      "/magicline/",
      "/audit/",
      "/settings/integrations/",
      "/settings/prompts/",
      "/settings/billing/",
      "/settings/branding/",
      "/settings/account/",
    ],
  },
  tenant_user: {
    exact: ["/", "/live", "/escalations", "/analytics", "/magicline", "/settings", "/settings/account"],
    prefixes: ["/live/", "/escalations/", "/analytics/", "/magicline/", "/settings/account/"],
  },
};

export function allowedPrefixesForRole(role: AppRole | undefined): string[] {
  if (!role) return ["/"];
  const access = ROLE_ACCESS[role];
  if (!access) return ["/"];
  return [...access.exact, ...access.prefixes];
}

export function isPathAllowedForRole(role: AppRole | undefined, path: string): boolean {
  const normalized = (path || "/").replace(/\/+$/, "") || "/";
  if (normalized === "/login" || normalized === "/register") return true;
  if (!role) return normalized === "/";
  const access = ROLE_ACCESS[role];
  if (!access) return normalized === "/";

  if (access.exact.includes(normalized)) return true;
  return access.prefixes.some((prefix) => normalized.startsWith(prefix));
}
