import test from "node:test";
import assert from "node:assert/strict";

import { allowedPrefixesForRole, isPathAllowedForRole, type AppRole } from "../lib/rbac";

type RoleCase = {
  role: AppRole;
  allowed: string[];
  forbidden: string[];
};

const cases: RoleCase[] = [
  {
    role: "system_admin",
    allowed: ["/", "/users", "/tenants", "/system-prompt", "/plans", "/audit", "/settings", "/settings/general", "/settings/account"],
    forbidden: ["/live", "/escalations", "/analytics", "/members", "/knowledge", "/member-memory", "/magicline"],
  },
  {
    role: "tenant_admin",
    allowed: [
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
    forbidden: ["/tenants", "/plans", "/system-prompt", "/settings/general", "/settings/automation"],
  },
  {
    role: "tenant_user",
    allowed: ["/", "/live", "/escalations", "/analytics", "/magicline", "/settings", "/settings/account"],
    forbidden: [
      "/members",
      "/users",
      "/tenants",
      "/knowledge",
      "/member-memory",
      "/system-prompt",
      "/plans",
      "/audit",
      "/settings/general",
      "/settings/integrations",
      "/settings/prompts",
      "/settings/billing",
      "/settings/branding",
      "/settings/automation",
    ],
  },
];

test("RBAC contract: auth routes stay public", () => {
  for (const role of [undefined, "system_admin", "tenant_admin", "tenant_user"] as const) {
    assert.equal(isPathAllowedForRole(role, "/login"), true);
    assert.equal(isPathAllowedForRole(role, "/register"), true);
  }
});

test("RBAC contract: per-role path matrix", () => {
  for (const entry of cases) {
    for (const path of entry.allowed) {
      assert.equal(
        isPathAllowedForRole(entry.role, path),
        true,
        `${entry.role} should allow ${path}`,
      );
    }
    for (const path of entry.forbidden) {
      assert.equal(
        isPathAllowedForRole(entry.role, path),
        false,
        `${entry.role} should deny ${path}`,
      );
    }
  }
});

test("RBAC contract: role prefix inventory is non-empty", () => {
  for (const role of ["system_admin", "tenant_admin", "tenant_user"] as const) {
    const prefixes = allowedPrefixesForRole(role);
    assert.ok(prefixes.length > 0);
    assert.ok(prefixes.includes("/"));
  }
});
