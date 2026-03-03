"use client";

import React from "react";
import Link from "next/link";
import { usePermissions } from "@/lib/permissions";
import { useBillingOverview } from "@/lib/billing-hooks";
import { Crown, ArrowRight, Lock, AlertTriangle, Zap, Shield } from "lucide-react";

/* ── FeatureGateV2 ──────────────────────────────────────────────────────────
   Enhanced feature gate that checks both V1 and V2 feature systems.
   Falls back gracefully to V1 if V2 data is not available.
   ────────────────────────────────────────────────────────────────────── */

interface FeatureGateV2Props {
  /** Feature key to check (works with both V1 and V2 systems) */
  feature?: string;
  /** Addon slug to check */
  addon?: string;
  /** Allowed roles */
  roles?: string[];
  /** Metered resource to check (V2 only) */
  meteredResource?: "messages" | "members" | "tokens" | "channels" | "connectors";
  children: React.ReactNode;
  fallback?: React.ReactNode;
  /** Render as inline badge instead of full block */
  inline?: boolean;
  /** Custom upgrade message */
  message?: string;
  /** Soft gate: show warning but don't block */
  soft?: boolean;
}

export function FeatureGateV2({
  feature: featureKey,
  addon: addonSlug,
  roles,
  meteredResource,
  children,
  fallback,
  inline = false,
  message,
  soft = false,
}: FeatureGateV2Props) {
  const v1 = usePermissions();
  const { data: v2Data } = useBillingOverview();

  if (v1.loading) return null;

  // Role check (V1)
  const hasRole = roles ? (v1.role && roles.includes(v1.role)) : true;

  // Feature check: try V2 first, fallback to V1
  let hasFeature = true;
  if (featureKey) {
    if (v2Data?.features) {
      hasFeature = !!v2Data.features[featureKey];
    } else {
      hasFeature = v1.feature(featureKey);
    }
  }

  // Addon check: try V2 first, fallback to V1
  let hasRequiredAddon = true;
  if (addonSlug) {
    if (v2Data?.active_addons) {
      hasRequiredAddon = v2Data.active_addons.some(
        (a) => a.slug === addonSlug && a.status === "active"
      );
    } else {
      hasRequiredAddon = v1.hasAddon(addonSlug);
    }
  }

  // Metered resource check (V2 only)
  let isWithinLimits = true;
  let usagePercentage = 0;
  if (meteredResource && v2Data?.usage) {
    const usage = v2Data.usage;
    const resourceMap: Record<string, { used: number; limit: number | null }> = {
      messages: { used: usage.messages_used, limit: usage.messages_limit },
      members: { used: usage.members_count, limit: usage.members_limit },
      tokens: { used: usage.tokens_used, limit: usage.tokens_limit },
      channels: { used: usage.channels_used, limit: usage.channels_limit },
      connectors: { used: usage.connectors_used, limit: usage.connectors_limit },
    };
    const res = resourceMap[meteredResource];
    if (res && res.limit) {
      usagePercentage = (res.used / res.limit) * 100;
      isWithinLimits = res.used < res.limit;
    }
  }

  const isAllowed = hasRole && hasFeature && hasRequiredAddon && isWithinLimits;

  // Soft gate: show warning but allow access
  if (soft && !isWithinLimits && usagePercentage >= 80) {
    return (
      <>
        <div className="mb-4 p-3 rounded-lg border flex items-start gap-3 text-sm bg-amber-50 border-amber-200 text-amber-800">
          <AlertTriangle size={18} className="shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">
              {usagePercentage >= 100 ? "Limit erreicht" : "Limit fast erreicht"}
            </p>
            <p className="text-xs mt-0.5 opacity-80">
              {Math.round(usagePercentage)}% des Limits verbraucht.
            </p>
            {usagePercentage >= 100 && (
              <Link
                href="/settings/billing"
                className="inline-flex items-center gap-1 mt-2 text-xs font-semibold underline"
              >
                Plan upgraden <ArrowRight size={12} />
              </Link>
            )}
          </div>
        </div>
        {children}
      </>
    );
  }

  if (isAllowed) {
    return <>{children}</>;
  }

  if (fallback) return <>{fallback}</>;

  if (inline) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
        <Lock size={10} /> Premium
      </span>
    );
  }

  // Full block fallback
  const planName = v2Data?.plan?.name || v1.plan?.name || "Aktueller Plan";

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border-2 border-dashed border-slate-200 shadow-sm">
      <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mb-6">
        <Crown size={32} />
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-2">Premium Feature</h3>
      <p className="text-slate-500 max-w-md mb-4">
        {message || "Diese Funktion ist in deinem aktuellen Plan nicht enthalten."}
      </p>
      <p className="text-xs text-slate-400 mb-6">
        Aktueller Plan: <span className="font-semibold text-slate-600">{planName}</span>
      </p>
      <Link
        href="/settings/billing"
        className="inline-flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200"
      >
        Plan upgraden <ArrowRight size={16} />
      </Link>
    </div>
  );
}

/* ── MeteredGateV2 ──────────────────────────────────────────────────────────
   Specifically for metered resources. Shows usage progress and warns
   when approaching limits.
   ────────────────────────────────────────────────────────────────────── */

interface MeteredGateV2Props {
  resource: "messages" | "members" | "tokens" | "channels" | "connectors";
  children: React.ReactNode;
  /** Block access when limit exceeded (default: false, just warn) */
  hardBlock?: boolean;
}

export function MeteredGateV2({ resource, children, hardBlock = false }: MeteredGateV2Props) {
  return (
    <FeatureGateV2
      meteredResource={resource}
      soft={!hardBlock}
    >
      {children}
    </FeatureGateV2>
  );
}

export default FeatureGateV2;
