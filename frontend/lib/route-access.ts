import { isPathAllowedForRole, type AppRole } from "@/lib/rbac";

export type RouteAccessState = "available" | "upgrade" | "coming_soon" | "hidden";

export type RouteAccessContext = {
  role: AppRole | undefined;
  canPage: (path: string) => boolean;
  feature: (key: string) => boolean;
};

type RouteRule = {
  match: string;
  dormant?: boolean;
  featureKey?: string;
};

const ROUTE_RULES: RouteRule[] = [
  { match: "/analytics", dormant: true, featureKey: "advanced_analytics" },
  { match: "/member-memory", dormant: true, featureKey: "memory_analyzer" },
  { match: "/system-prompt", dormant: true, featureKey: "custom_prompts" },
  { match: "/settings/prompts", dormant: true, featureKey: "custom_prompts" },
  { match: "/automations", dormant: true, featureKey: "automation" },
  { match: "/settings/automation", dormant: true, featureKey: "automation" },
  { match: "/settings/branding", dormant: true, featureKey: "branding" },
];

function normalizePath(path: string): string {
  return (path || "/").replace(/\/+$/, "") || "/";
}

function matchesRule(path: string, match: string): boolean {
  return path === match || path.startsWith(`${match}/`);
}

export function getRouteAccessState(path: string, context: RouteAccessContext): RouteAccessState {
  const normalized = normalizePath(path);
  if (!isPathAllowedForRole(context.role, normalized)) {
    return "hidden";
  }

  const rule = ROUTE_RULES.find((entry) => matchesRule(normalized, entry.match));
  if (rule?.dormant) {
    return "coming_soon";
  }

  if (context.canPage(normalized)) {
    return "available";
  }

  if (rule?.featureKey && !context.feature(rule.featureKey)) {
    return "upgrade";
  }

  return "hidden";
}

export function isRouteVisible(path: string, context: RouteAccessContext): boolean {
  return getRouteAccessState(path, context) !== "hidden";
}
