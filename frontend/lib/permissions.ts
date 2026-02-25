import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

// Types matching the backend response
export type PlanSlug = 'starter' | 'pro' | 'business' | 'enterprise';

export interface Plan {
  slug: PlanSlug;
  name: string;
  price_monthly_cents: number;
  features: Record<string, boolean>;
  limits: {
    max_members: number | null;
    max_monthly_messages: number | null;
    max_channels: number;
    max_connectors: number;
  };
}

export interface Subscription {
  has_subscription: boolean;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'unpaid';
  current_period_end: string | null;
  trial_ends_at: string | null;
}

export interface Usage {
  messages_used: number;
  messages_inbound: number;
  messages_outbound: number;
  members_count: number;
  llm_tokens_used: number;
}

export interface PermissionsResponse {
  role: 'system_admin' | 'tenant_admin' | 'tenant_user';
  plan: Plan;
  subscription: Subscription;
  usage: Usage;
  pages: Record<string, boolean>;
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

  const feature = (key: string) => {
    if (!data?.plan?.features) return false;
    return !!data.plan.features[key];
  };

  const canPage = (path: string) => {
    if (!data?.pages) return true; // Default open if not specified? Or closed?
    return !!data.pages[path];
  };

  const isNearLimit = (resource: 'messages' | 'members') => {
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
    isNearLimit,
    loading: isLoading,
    reload: refetch,
  };
}
