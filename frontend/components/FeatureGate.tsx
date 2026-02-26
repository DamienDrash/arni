"use client";

import React from "react";
import Link from "next/link";
import { usePermissions } from "@/lib/permissions";
import { Zap, Lock, AlertTriangle, Crown, ArrowRight } from "lucide-react";

/* ── FeatureGate ─────────────────────────────────────────────────────────
   Blocks content if the user's plan does not include the required feature.
   Supports: plan features, role checks, and addon checks.
   ────────────────────────────────────────────────────────────────────── */

interface FeatureGateProps {
  /** Plan feature key, e.g. "advanced_analytics" */
  feature?: string;
  /** Addon slug, e.g. "voice_pipeline" */
  addon?: string;
  /** Allowed roles */
  roles?: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
  /** Render as inline badge instead of full block */
  inline?: boolean;
  /** Custom upgrade message */
  message?: string;
}

export function FeatureGate({
  feature: featureKey,
  addon: addonSlug,
  roles,
  children,
  fallback,
  inline = false,
  message,
}: FeatureGateProps) {
  const { feature, role, hasAddon, plan, loading } = usePermissions();

  if (loading) return null;

  const hasRole = roles ? (role && roles.includes(role)) : true;
  const hasFeature = featureKey ? feature(featureKey) : true;
  const hasRequiredAddon = addonSlug ? hasAddon(addonSlug) : true;

  if (hasRole && hasFeature && hasRequiredAddon) {
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

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border-2 border-dashed border-slate-200 shadow-sm">
      <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mb-6">
        <Crown size={32} />
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-2">Premium Feature</h3>
      <p className="text-slate-500 max-w-md mb-4">
        {message || "Diese Funktion ist in deinem aktuellen Plan nicht enthalten."}
      </p>
      {plan && (
        <p className="text-xs text-slate-400 mb-6">
          Aktueller Plan: <span className="font-semibold text-slate-600">{plan.name}</span>
        </p>
      )}
      <Link
        href="/settings/billing"
        className="inline-flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200"
      >
        Plan upgraden <ArrowRight size={16} />
      </Link>
    </div>
  );
}

/* ── RoleGate ────────────────────────────────────────────────────────── */

export function RoleGate({
  roles,
  children,
  fallback,
}: {
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}) {
  return (
    <FeatureGate roles={roles} fallback={fallback}>
      {children}
    </FeatureGate>
  );
}

/* ── LimitGate ───────────────────────────────────────────────────────────
   Shows a warning banner when a resource is near or over its limit.
   Does NOT block content — just warns.
   ────────────────────────────────────────────────────────────────────── */

interface LimitGateProps {
  resource: "messages" | "members";
  children: React.ReactNode;
}

export function LimitGate({ resource, children }: LimitGateProps) {
  const { isNearLimit, isOverLimit, usagePercent, plan, usage, loading } = usePermissions();

  if (loading) return <>{children}</>;

  const near = isNearLimit(resource);
  const over = isOverLimit(resource);

  if (!near && !over) return <>{children}</>;

  const pct = usagePercent(resource);
  const limit =
    resource === "messages"
      ? plan?.limits?.max_monthly_messages
      : plan?.limits?.max_members;
  const current =
    resource === "messages"
      ? usage?.messages_used
      : usage?.members_count;

  const label = resource === "messages" ? "Nachrichten" : "Kontakte";

  return (
    <>
      <div
        className={`mb-4 p-3 rounded-lg border flex items-start gap-3 text-sm ${
          over
            ? "bg-red-50 border-red-200 text-red-800"
            : "bg-amber-50 border-amber-200 text-amber-800"
        }`}
      >
        <AlertTriangle size={18} className="shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="font-semibold">
            {over ? `${label}-Limit erreicht` : `${label}-Limit fast erreicht`}
          </p>
          <p className="text-xs mt-0.5 opacity-80">
            {current?.toLocaleString("de-DE")} / {limit?.toLocaleString("de-DE")} {label} verwendet ({Math.round(pct)}%)
          </p>
          {over && (
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

/* ── SubscriptionGate ────────────────────────────────────────────────────
   Blocks content if the subscription is in an unhealthy state.
   ────────────────────────────────────────────────────────────────────── */

interface SubscriptionGateProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function SubscriptionGate({ children, fallback }: SubscriptionGateProps) {
  const { subscription, isSubscriptionHealthy, loading } = usePermissions();

  if (loading) return null;

  if (isSubscriptionHealthy()) {
    return <>{children}</>;
  }

  if (fallback) return <>{fallback}</>;

  const statusLabels: Record<string, string> = {
    past_due: "Zahlung überfällig",
    canceled: "Abonnement gekündigt",
    unpaid: "Unbezahlt",
  };

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border-2 border-dashed border-red-200 shadow-sm">
      <div className="w-16 h-16 bg-red-50 text-red-600 rounded-full flex items-center justify-center mb-6">
        <AlertTriangle size={32} />
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-2">
        {statusLabels[subscription?.status || ""] || "Abonnement-Problem"}
      </h3>
      <p className="text-slate-500 max-w-md mb-8">
        Dein Abonnement ist derzeit nicht aktiv. Bitte aktualisiere deine Zahlungsinformationen, um den vollen Zugriff wiederherzustellen.
      </p>
      <Link
        href="/settings/billing"
        className="inline-flex items-center gap-2 px-6 py-2.5 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-colors"
      >
        Zahlungsdaten aktualisieren <ArrowRight size={16} />
      </Link>
    </div>
  );
}
