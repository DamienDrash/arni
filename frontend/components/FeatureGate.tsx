"use client";

import React from "react";
import Link from "next/link";
import { usePermissions } from "@/lib/permissions";
import { Zap, ShieldAlert, Lock } from "lucide-react";

interface FeatureGateProps {
  feature?: string;
  roles?: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
  inline?: boolean;
}

export function FeatureGate({
  feature: featureKey,
  roles,
  children,
  fallback,
  inline = false,
}: FeatureGateProps) {
  const { feature, role, loading } = usePermissions();

  if (loading) return null;

  const hasRole = roles ? (role && roles.includes(role)) : true;
  const hasFeature = featureKey ? feature(featureKey) : true;

  if (hasRole && hasFeature) {
    return <>{children}</>;
  }

  if (fallback) return <>{fallback}</>;

  if (inline) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
        <Lock size={10} /> Premium Feature
      </span>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center p-12 text-center bg-white rounded-xl border-2 border-dashed border-slate-200 shadow-sm">
      <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mb-6">
        <Zap size={32} />
      </div>
      <h3 className="text-xl font-bold text-slate-900 mb-2">Premium Feature</h3>
      <p className="text-slate-500 max-w-md mb-8">
        Diese Funktion ist in deinem aktuellen Plan nicht enthalten. Aktiviere ein Upgrade, um sofortigen Zugriff zu erhalten.
      </p>
      <Link
        href="/settings/billing"
        className="px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200"
      >
        Plan ansehen & Upgrade
      </Link>
    </div>
  );
}

export function RoleGate({ roles, children, fallback }: { roles: string[]; children: React.ReactNode; fallback?: React.ReactNode }) {
  return <FeatureGate roles={roles} fallback={fallback}>{children}</FeatureGate>;
}
