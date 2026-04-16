import test from "node:test";
import assert from "node:assert/strict";

import { getRouteAccessState } from "../lib/route-access";

const tenantContext = {
  role: "tenant_admin" as const,
  canPage: (path: string) => path === "/dashboard" || path === "/settings/billing",
  feature: (key: string) => key === "advanced_analytics",
};

const systemAdminContext = {
  role: "system_admin" as const,
  canPage: (_path: string) => true,
  feature: (_key: string) => true,
};

test("route access contract: dormant routes render as coming soon", () => {
  assert.equal(getRouteAccessState("/analytics", tenantContext), "coming_soon");
  assert.equal(getRouteAccessState("/member-memory", tenantContext), "coming_soon");
  assert.equal(getRouteAccessState("/automations", tenantContext), "coming_soon");
  assert.equal(getRouteAccessState("/system-prompt", systemAdminContext), "coming_soon");
  assert.equal(getRouteAccessState("/settings/branding", systemAdminContext), "coming_soon");
});

test("route access contract: allowed core routes stay available", () => {
  assert.equal(getRouteAccessState("/dashboard", tenantContext), "available");
});

test("route access contract: RBAC-forbidden routes stay hidden", () => {
  assert.equal(getRouteAccessState("/plans", tenantContext), "hidden");
});
