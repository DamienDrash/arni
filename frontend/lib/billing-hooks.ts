/**
 * ARIIA Billing V2 – Frontend Hooks & Utilities
 *
 * Provides React hooks for interacting with the V2 billing API,
 * including subscription management, usage metering, and feature gating.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface BillingOverview {
  subscription: {
    id: number;
    plan_slug: string;
    plan_name: string;
    status: string;
    billing_interval: string;
    current_period_start: string | null;
    current_period_end: string | null;
    cancel_at_period_end: boolean;
    trial_end: string | null;
    stripe_subscription_id: string | null;
  } | null;
  plan: {
    slug: string;
    name: string;
    description: string | null;
    tier: string;
    price_monthly_cents: number;
    price_yearly_cents: number;
  } | null;
  usage: {
    messages_used: number;
    messages_limit: number | null;
    members_count: number;
    members_limit: number | null;
    tokens_used: number;
    tokens_limit: number | null;
    channels_used: number;
    channels_limit: number | null;
    connectors_used: number;
    connectors_limit: number | null;
  };
  features: Record<string, boolean>;
  active_addons: Array<{
    slug: string;
    name: string;
    quantity: number;
    status: string;
  }>;
}

export interface UsageMetric {
  metric_key: string;
  current_value: number;
  soft_limit: number | null;
  hard_limit: number | null;
  percentage: number;
  status: "ok" | "warning" | "critical" | "exceeded";
  unit_label: string;
}

export interface BillingEvent {
  id: number;
  event_type: string;
  payload: Record<string, any>;
  actor_type: string;
  actor_id: string | null;
  created_at: string;
}

export interface RevenueMetrics {
  balance_available_cents: number;
  balance_pending_cents: number;
  revenue_30d_cents: number;
  mrr_estimate_cents: number;
  active_subscriptions: number;
  currency: string;
}

export interface SubscriberInfo {
  tenant_id: number;
  tenant_name: string;
  plan_name: string;
  plan_slug: string | null;
  status: string;
  billing_interval: string;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  stripe_subscription_id: string | null;
}

export interface FeatureDefinition {
  id: number;
  key: string;
  name: string;
  description: string | null;
  feature_type: string;
  unit_label: string | null;
  category: string | null;
  created_at: string | null;
}

export interface PlanFeatureEntitlement {
  entitlement_id: number;
  feature_id: number;
  feature_key: string | null;
  feature_name: string | null;
  enabled: boolean;
  soft_limit: number | null;
  hard_limit: number | null;
  config_json: string | null;
}

/* ── Hooks ──────────────────────────────────────────────────────────────── */

/**
 * Hook for the V2 billing overview (subscription, plan, usage, features).
 * Falls back gracefully to V1 data if V2 endpoint is not available.
 */
export function useBillingOverview() {
  return useQuery<BillingOverview>({
    queryKey: ["billing-v2-overview"],
    queryFn: async () => {
      // Try V2 endpoint first
      const res = await apiFetch("/admin/billing-v2/overview");
      if (res.ok) return res.json();

      // Fallback to V1 permissions endpoint
      const v1Res = await apiFetch("/admin/permissions");
      if (!v1Res.ok) throw new Error("Failed to load billing data");
      const v1Data = await v1Res.json();

      // Transform V1 data to V2 format
      return {
        subscription: v1Data.subscription
          ? {
              id: 0,
              plan_slug: v1Data.plan?.slug || "starter",
              plan_name: v1Data.plan?.name || "Starter",
              status: v1Data.subscription.status,
              billing_interval: "month",
              current_period_start: null,
              current_period_end: v1Data.subscription.current_period_end,
              cancel_at_period_end: v1Data.subscription.cancel_at_period_end || false,
              trial_end: v1Data.subscription.trial_ends_at,
              stripe_subscription_id: null,
            }
          : null,
        plan: v1Data.plan
          ? {
              slug: v1Data.plan.slug,
              name: v1Data.plan.name,
              description: v1Data.plan.description,
              tier: "starter",
              price_monthly_cents: 0,
              price_yearly_cents: 0,
            }
          : null,
        usage: {
          messages_used: v1Data.usage?.messages_used || 0,
          messages_limit: v1Data.plan?.limits?.max_monthly_messages || null,
          members_count: v1Data.usage?.members_count || 0,
          members_limit: v1Data.plan?.limits?.max_members || null,
          tokens_used: v1Data.usage?.llm_tokens_used || 0,
          tokens_limit: null,
          channels_used: 0,
          channels_limit: v1Data.plan?.limits?.max_channels || null,
          connectors_used: 0,
          connectors_limit: v1Data.plan?.limits?.max_connectors || null,
        },
        features: v1Data.plan?.features || {},
        active_addons: (v1Data.addons || []).map((a: any) => ({
          slug: a.slug,
          name: a.name,
          quantity: a.quantity || 1,
          status: a.status || "active",
        })),
      } as BillingOverview;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes cache
  });
}

/**
 * Hook for detailed usage metrics with V2 metering.
 */
export function useUsageMetrics() {
  return useQuery<UsageMetric[]>({
    queryKey: ["billing-v2-usage-metrics"],
    queryFn: async () => {
      const res = await apiFetch("/admin/billing-v2/usage-metrics");
      if (res.ok) return res.json();
      return []; // Graceful fallback
    },
    staleTime: 60 * 1000, // 1 minute cache
  });
}

/**
 * Hook for billing event history.
 */
export function useBillingEvents(limit = 50) {
  return useQuery<BillingEvent[]>({
    queryKey: ["billing-v2-events", limit],
    queryFn: async () => {
      const res = await apiFetch(`/admin/billing-v2/events?limit=${limit}`);
      if (res.ok) return res.json();
      return [];
    },
    staleTime: 30 * 1000,
  });
}

/**
 * Hook for admin revenue metrics.
 */
export function useRevenueMetrics() {
  return useQuery<RevenueMetrics>({
    queryKey: ["admin-revenue-metrics"],
    queryFn: async () => {
      const res = await apiFetch("/admin/plans/revenue");
      if (res.ok) return res.json();
      throw new Error("Failed to load revenue metrics");
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for admin subscriber list.
 */
export function useSubscribers() {
  return useQuery<SubscriberInfo[]>({
    queryKey: ["admin-subscribers"],
    queryFn: async () => {
      const res = await apiFetch("/admin/plans/subscribers");
      if (res.ok) return res.json();
      return [];
    },
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Hook for V2 feature definitions (admin).
 */
export function useFeatureDefinitions() {
  return useQuery<FeatureDefinition[]>({
    queryKey: ["admin-feature-definitions"],
    queryFn: async () => {
      const res = await apiFetch("/admin/plans/features");
      if (res.ok) return res.json();
      return [];
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook for plan-feature entitlements (admin).
 */
export function usePlanFeatures(planId: number | null) {
  return useQuery<PlanFeatureEntitlement[]>({
    queryKey: ["admin-plan-features", planId],
    queryFn: async () => {
      if (!planId) return [];
      const res = await apiFetch(`/admin/plans/${planId}/features`);
      if (res.ok) return res.json();
      return [];
    },
    enabled: !!planId,
    staleTime: 2 * 60 * 1000,
  });
}

/* ── Mutations ──────────────────────────────────────────────────────────── */

/**
 * Mutation for creating a checkout session.
 */
export function useCheckoutSession() {
  return useMutation({
    mutationFn: async ({
      planSlug,
      billingInterval,
    }: {
      planSlug: string;
      billingInterval: "month" | "year";
    }) => {
      const res = await apiFetch("/admin/billing/checkout-session", {
        method: "POST",
        body: JSON.stringify({
          plan_slug: planSlug,
          billing_interval: billingInterval,
        }),
      });
      if (!res.ok) throw new Error("Checkout failed");
      return res.json();
    },
  });
}

/**
 * Mutation for previewing a plan change.
 */
export function usePreviewPlanChange() {
  return useMutation({
    mutationFn: async ({
      planSlug,
      billingInterval,
    }: {
      planSlug: string;
      billingInterval: "month" | "year";
    }) => {
      const res = await apiFetch("/admin/billing/preview-plan-change", {
        method: "POST",
        body: JSON.stringify({
          plan_slug: planSlug,
          billing_interval: billingInterval,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Fehler" }));
        throw new Error(err.detail || "Preview failed");
      }
      return res.json();
    },
  });
}

/**
 * Mutation for confirming a plan change.
 */
export function useConfirmPlanChange() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      planSlug,
      billingInterval,
    }: {
      planSlug: string;
      billingInterval: "month" | "year";
    }) => {
      const res = await apiFetch("/admin/billing/change-plan", {
        method: "POST",
        body: JSON.stringify({
          plan_slug: planSlug,
          billing_interval: billingInterval,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Fehler" }));
        throw new Error(err.detail || "Plan change failed");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-v2-overview"] });
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
    },
  });
}

/**
 * Mutation for canceling a subscription.
 */
export function useCancelSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/admin/billing/cancel-subscription", {
        method: "POST",
      });
      if (!res.ok) throw new Error("Cancel failed");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-v2-overview"] });
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
    },
  });
}

/**
 * Mutation for reactivating a subscription.
 */
export function useReactivateSubscription() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/admin/billing/reactivate-subscription", {
        method: "POST",
      });
      if (!res.ok) throw new Error("Reactivate failed");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["billing-v2-overview"] });
      queryClient.invalidateQueries({ queryKey: ["permissions"] });
    },
  });
}

/* ── Utility Functions ──────────────────────────────────────────────────── */

/**
 * Format cents to EUR display string.
 */
export function formatEur(cents: number): string {
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(cents / 100);
}

/**
 * Get usage status color based on percentage.
 */
export function getUsageColor(percentage: number): string {
  if (percentage >= 100) return "text-red-500";
  if (percentage >= 90) return "text-red-400";
  if (percentage >= 80) return "text-amber-500";
  return "text-green-500";
}

/**
 * Get usage bar color based on percentage.
 */
export function getUsageBarColor(percentage: number): string {
  if (percentage >= 100) return "bg-red-500";
  if (percentage >= 90) return "bg-red-400";
  if (percentage >= 80) return "bg-amber-500";
  return "bg-indigo-600";
}

/**
 * Get subscription status badge config.
 */
export function getStatusBadge(status: string): {
  label: string;
  variant: "success" | "warning" | "danger" | "info" | "default";
  color: string;
} {
  const map: Record<string, { label: string; variant: "success" | "warning" | "danger" | "info" | "default"; color: string }> = {
    active: { label: "AKTIV", variant: "success", color: "bg-green-500/20 text-green-400 border-green-500/30" },
    trialing: { label: "TESTPHASE", variant: "info", color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
    past_due: { label: "ÜBERFÄLLIG", variant: "warning", color: "bg-amber-500/20 text-amber-400 border-amber-500/30" },
    canceled: { label: "GEKÜNDIGT", variant: "danger", color: "bg-red-500/20 text-red-400 border-red-500/30" },
    unpaid: { label: "UNBEZAHLT", variant: "danger", color: "bg-red-500/20 text-red-400 border-red-500/30" },
    expired: { label: "ABGELAUFEN", variant: "default", color: "bg-slate-500/20 text-slate-400 border-slate-500/30" },
  };
  return map[status] || { label: status.toUpperCase(), variant: "default", color: "bg-slate-500/20 text-slate-400 border-slate-500/30" };
}
