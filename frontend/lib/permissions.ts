import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

// Types matching the backend response
export type PlanSlug = string; // Dynamic slugs from DB

export interface Plan {
  slug: PlanSlug;
  name: string;
  description: string | null;
  features: Record<string, boolean>;
  limits: {
    max_members: number | null;
    max_monthly_messages: number | null;
    max_channels: number;
    max_connectors: number;
  };
  ai_tier: string;
  features_display: string[];
}

export interface Subscription {
  has_subscription: boolean;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'unpaid' | 'expired';
  current_period_end: string | null;
  trial_ends_at: string | null;
  is_trial: boolean;
}

export interface Usage {
  messages_used: number;
  messages_inbound: number;
  messages_outbound: number;
  members_count: number;
  llm_tokens_used: number;
}

export interface ActiveAddon {
  slug: string;
  name: string;
  description: string | null;
  category: string | null;
  quantity: number;
  status: string;
  features?: string[];
}

export interface Overage {
  conversation_cents: number;
  user_cents: number;
  connector_cents: number;
  channel_cents: number;
}

export interface PermissionsResponse {
  role: 'system_admin' | 'tenant_admin' | 'tenant_user';
  plan: Plan;
  subscription: Subscription;
  usage: Usage;
  pages: Record<string, boolean>;
  addons: ActiveAddon[];
  overage: Overage | null;
}

// Hook
export function usePermissions() {
  const { data, isLoading, refetch } = useQuery<PermissionsResponse>({
    queryKey: ['permissions'],
    queryFn: async () => {
      const res = await apiFetch('/admin/permissions');
      if (!res.ok) throw new Error('Failed to load permissions');
      return res.json();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes cache
  });

  const role = data?.role;
  const isSystemAdmin = role === 'system_admin';
  const isTenantAdmin = role === 'tenant_admin';
  const isTenantUser = role === 'tenant_user';

  /**
   * Check if a feature is available (from plan or addons).
   */
  const feature = (key: string): boolean => {
    if (!data?.plan?.features) return false;
    return !!data.plan.features[key];
  };

  /**
   * Check if a page is accessible.
   */
  const canPage = (path: string): boolean => {
    if (!data?.pages) return true;
    return !!data.pages[path];
  };

  /**
   * Check if a resource is near its limit (>80%).
   */
  const isNearLimit = (resource: 'messages' | 'members'): boolean => {
    if (!data?.plan?.limits || !data?.usage) return false;
    if (resource === 'messages') {
      const max = data.plan.limits.max_monthly_messages;
      if (!max) return false;
      return data.usage.messages_used / max > 0.8;
    }
    if (resource === 'members') {
      const max = data.plan.limits.max_members;
      if (!max) return false;
      return data.usage.members_count / max > 0.8;
    }
    return false;
  };

  /**
   * Check if a resource has exceeded its limit.
   */
  const isOverLimit = (resource: 'messages' | 'members'): boolean => {
    if (!data?.plan?.limits || !data?.usage) return false;
    if (resource === 'messages') {
      const max = data.plan.limits.max_monthly_messages;
      if (!max) return false;
      return data.usage.messages_used >= max;
    }
    if (resource === 'members') {
      const max = data.plan.limits.max_members;
      if (!max) return false;
      return data.usage.members_count >= max;
    }
    return false;
  };

  /**
   * Get usage percentage for a resource.
   */
  const usagePercent = (resource: 'messages' | 'members'): number => {
    if (!data?.plan?.limits || !data?.usage) return 0;
    if (resource === 'messages') {
      const max = data.plan.limits.max_monthly_messages;
      if (!max) return 0;
      return Math.min(100, (data.usage.messages_used / max) * 100);
    }
    if (resource === 'members') {
      const max = data.plan.limits.max_members;
      if (!max) return 0;
      return Math.min(100, (data.usage.members_count / max) * 100);
    }
    return 0;
  };

  /**
   * Check if the tenant has a specific addon active.
   */
  const hasAddon = (slug: string): boolean => {
    if (!data?.addons) return false;
    return data.addons.some(a => a.slug === slug && a.status === 'active');
  };

  /**
   * Check if subscription is in a problematic state.
   */
  const isSubscriptionHealthy = (): boolean => {
    if (!data?.subscription) return true;
    return ['active', 'trialing'].includes(data.subscription.status);
  };

  /**
   * Check if the tenant is currently in a trial period.
   */
  const isTrial = (): boolean => {
    return data?.subscription?.is_trial === true;
  };

  /**
   * Get the number of days remaining in the trial.
   * Returns 0 if not in trial or trial has expired.
   */
  const trialDaysRemaining = (): number => {
    if (!data?.subscription?.trial_ends_at) return 0;
    const end = new Date(data.subscription.trial_ends_at);
    const now = new Date();
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return Math.max(0, diff);
  };

  /**
   * Check if the trial has expired.
   */
  const isTrialExpired = (): boolean => {
    if (!data?.subscription?.is_trial) return false;
    return trialDaysRemaining() <= 0;
  };

  return {
    role,
    isSystemAdmin,
    isTenantAdmin,
    isTenantUser,
    feature,
    canPage,
    plan: data?.plan,
    usage: data?.usage,
    subscription: data?.subscription,
    addons: data?.addons || [],
    overage: data?.overage || null,
    isNearLimit,
    isOverLimit,
    usagePercent,
    hasAddon,
    isSubscriptionHealthy,
    isTrial,
    trialDaysRemaining,
    isTrialExpired,
    loading: isLoading,
    reload: refetch,
  };
}
