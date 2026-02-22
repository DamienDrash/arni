/**
 * Zentrale React Query Hooks für ARIIA API-Calls.
 * Basiert auf dem bestehenden `apiFetch` in lib/api.ts.
 *
 * Verwendung:
 *   const { data, isLoading, error, refetch } = useMembers();
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

// ── Helper ────────────────────────────────────────────────────────────────────

async function fetchJSON<T>(path: string): Promise<T> {
    const res = await apiFetch(path);
    if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`API ${res.status}: ${body || res.statusText}`);
    }
    return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
    const res = await apiFetch(path, {
        method: "POST",
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const errBody = await res.text().catch(() => "");
        throw new Error(`API ${res.status}: ${errBody || res.statusText}`);
    }
    return res.json() as Promise<T>;
}

// ── Query Keys ────────────────────────────────────────────────────────────────

export const QUERY_KEYS = {
    members: ["members"] as const,
    member: (id: number) => ["members", id] as const,
    analytics: ["analytics"] as const,
    dashboardStats: ["dashboard", "stats"] as const,
    liveConversations: ["live", "conversations"] as const,
    auditLogs: ["audit", "logs"] as const,
    tenants: ["tenants"] as const,
    users: ["users"] as const,
    billingStatus: ["billing", "status"] as const,
    settings: (key?: string) => ["settings", key] as const,
} as const;

// ── Members ───────────────────────────────────────────────────────────────────

export function useMembers() {
    return useQuery({
        queryKey: QUERY_KEYS.members,
        queryFn: () => fetchJSON<{ members: unknown[] }>("/admin/members"),
        staleTime: 60_000, // 1min
    });
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export function useAnalytics() {
    return useQuery({
        queryKey: QUERY_KEYS.analytics,
        queryFn: () => fetchJSON<Record<string, unknown>>("/admin/analytics"),
        staleTime: 30_000,
    });
}

export function useDashboardStats() {
    return useQuery({
        queryKey: QUERY_KEYS.dashboardStats,
        queryFn: () => fetchJSON<Record<string, unknown>>("/admin/stats"),
        staleTime: 15_000,
        refetchInterval: 30_000, // auto-refresh alle 30s
    });
}

// ── Live Monitor ──────────────────────────────────────────────────────────────

export function useLiveConversations() {
    return useQuery({
        queryKey: QUERY_KEYS.liveConversations,
        queryFn: () => fetchJSON<{ sessions: unknown[] }>("/admin/sessions?active=true"),
        staleTime: 5_000,
        refetchInterval: 10_000, // live: alle 10s pollen
    });
}

// ── Audit ─────────────────────────────────────────────────────────────────────

export function useAuditLogs(limit = 50) {
    return useQuery({
        queryKey: [...QUERY_KEYS.auditLogs, limit],
        queryFn: () => fetchJSON<{ logs: unknown[] }>(`/admin/audit?limit=${limit}`),
        staleTime: 60_000,
    });
}

// ── Tenants ───────────────────────────────────────────────────────────────────

export function useTenants() {
    return useQuery({
        queryKey: QUERY_KEYS.tenants,
        queryFn: () => fetchJSON<{ tenants: unknown[] }>("/admin/tenants"),
        staleTime: 120_000,
    });
}

// ── Users ─────────────────────────────────────────────────────────────────────

export function useUsers() {
    return useQuery({
        queryKey: QUERY_KEYS.users,
        queryFn: () => fetchJSON<{ users: unknown[] }>("/admin/users"),
        staleTime: 120_000,
    });
}

// ── Branding ──────────────────────────────────────────────────────────────────

export interface BrandingPrefs {
    tenant_app_title?: string;
    tenant_display_name?: string;
    tenant_logo_url?: string;
    tenant_primary_color?: string;
    tenant_support_email?: string;
    tenant_timezone?: string;
    tenant_locale?: string;
}

export function useBranding() {
    return useQuery({
        queryKey: ["branding"],
        queryFn: () => fetchJSON<BrandingPrefs>("/admin/tenant-preferences"),
        staleTime: 300_000, // 5min — ändert sich selten
    });
}

export function useSaveBranding() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (prefs: Partial<BrandingPrefs>) =>
            postJSON<BrandingPrefs>("/admin/tenant-preferences", prefs),
        onSuccess: () => {
            void qc.invalidateQueries({ queryKey: ["branding"] });
        },
    });
}

// ── Billing ───────────────────────────────────────────────────────────────────

export function useBillingStatus() {
    return useQuery({
        queryKey: QUERY_KEYS.billingStatus,
        queryFn: () => fetchJSON<{
            plan: string | null;
            status: string;
            channels: string[];
            stripe_subscription_id?: string;
        }>("/admin/billing/status"),
        staleTime: 300_000, // 5min
    });
}

export function useCheckoutMutation() {
    return useMutation({
        mutationFn: (plan: "starter" | "growth" | "enterprise") =>
            postJSON<{ url: string; session_id: string }>("/admin/billing/checkout", {
                plan,
                success_url: `${window.location.origin}/settings/billing?success=1`,
                cancel_url: `${window.location.origin}/settings/billing?canceled=1`,
            }),
        onSuccess: (data) => {
            window.location.href = data.url;
        },
    });
}
