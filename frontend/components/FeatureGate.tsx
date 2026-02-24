"use client";

/**
 * ARIIA – Feature Gate & Upgrade Prompt Components
 *
 * Enterprise-grade components for plan-based feature gating with
 * beautiful upgrade prompts that guide users to the right plan.
 *
 * Usage:
 *   <FeatureGate feature="memory_analyzer">
 *     <MemberMemoryPage />
 *   </FeatureGate>
 *
 *   <FeatureGate feature="voice" fallback={<CustomFallback />}>
 *     <VoiceSettings />
 *   </FeatureGate>
 */

import { type ReactNode } from "react";
import { usePermissions, type PlanFeatures } from "@/lib/permissions";
import { T } from "@/lib/tokens";
import {
  Lock,
  Sparkles,
  ArrowUpRight,
  Crown,
  Zap,
  Shield,
  TrendingUp,
  MessageSquare,
  Users,
  BarChart3,
  Palette,
  ClipboardList,
  Bot,
  Code,
  Database,
} from "lucide-react";

// ── Feature Metadata ─────────────────────────────────────────────────────────

interface FeatureMeta {
  label: string;
  description: string;
  icon: typeof Lock;
  benefits: string[];
}

const FEATURE_META: Record<keyof PlanFeatures, FeatureMeta> = {
  whatsapp: {
    label: "WhatsApp",
    description: "WhatsApp-Nachrichten empfangen und beantworten.",
    icon: MessageSquare,
    benefits: ["Automatische Antworten", "Media-Support", "Gruppen-Nachrichten"],
  },
  telegram: {
    label: "Telegram",
    description: "Telegram-Bot für automatisierte Kundenkommunikation.",
    icon: MessageSquare,
    benefits: ["Bot-Integration", "Inline-Keyboards", "Rich Media"],
  },
  sms: {
    label: "SMS",
    description: "SMS-Nachrichten über Twilio senden und empfangen.",
    icon: MessageSquare,
    benefits: ["Weltweiter Versand", "Automatische Antworten", "Kampagnen"],
  },
  email_channel: {
    label: "E-Mail-Kanal",
    description: "E-Mail als vollwertigen Kommunikationskanal nutzen.",
    icon: MessageSquare,
    benefits: ["Eingehende E-Mails", "Automatische Antworten", "Templates"],
  },
  voice: {
    label: "Voice / Telefonie",
    description: "KI-gestützte Telefonate mit Echtzeit-Spracherkennung.",
    icon: MessageSquare,
    benefits: ["Echtzeit-Transkription", "KI-Antworten", "Anruf-Routing"],
  },
  instagram: {
    label: "Instagram DM",
    description: "Instagram Direct Messages automatisch beantworten.",
    icon: MessageSquare,
    benefits: ["DM-Automatisierung", "Story-Replies", "Quick Replies"],
  },
  facebook: {
    label: "Facebook Messenger",
    description: "Facebook Messenger als Kommunikationskanal.",
    icon: MessageSquare,
    benefits: ["Messenger-Bot", "Postback-Buttons", "Persistent Menu"],
  },
  google_business: {
    label: "Google Business Messages",
    description: "Nachrichten direkt aus Google Maps und der Suche.",
    icon: MessageSquare,
    benefits: ["Google Maps Integration", "Suche-Integration", "Rich Cards"],
  },
  memory_analyzer: {
    label: "Member Memory",
    description: "KI-gestützte Analyse von Mitglieder-Interaktionen und Verhaltensmustern.",
    icon: TrendingUp,
    benefits: ["Verhaltensanalyse", "Churn-Prediction", "Personalisierung", "Sentiment-Tracking"],
  },
  custom_prompts: {
    label: "Custom Prompts",
    description: "Eigene KI-Prompts und Agent-Konfigurationen erstellen.",
    icon: Bot,
    benefits: ["Individuelle Antworten", "Tonalität anpassen", "Branchenspezifisch", "Multi-Agent"],
  },
  advanced_analytics: {
    label: "Advanced Analytics",
    description: "Detaillierte Analysen und Berichte über alle Kanäle.",
    icon: BarChart3,
    benefits: ["Kanalvergleich", "Trend-Analyse", "Export-Funktionen", "Custom Dashboards"],
  },
  branding: {
    label: "Custom Branding",
    description: "Eigenes Logo, Farben und Branding für das Dashboard.",
    icon: Palette,
    benefits: ["Eigenes Logo", "Farbschema", "Custom Domain", "White-Label"],
  },
  audit_log: {
    label: "Audit Log",
    description: "Vollständiges Protokoll aller Aktionen und Änderungen.",
    icon: ClipboardList,
    benefits: ["Compliance", "Nachvollziehbarkeit", "Export", "Filterung"],
  },
  automation: {
    label: "Automation",
    description: "Automatisierte Workflows und geplante Aktionen.",
    icon: Zap,
    benefits: ["Scheduled Tasks", "Trigger-basiert", "Multi-Step", "Conditional Logic"],
  },
  api_access: {
    label: "API-Zugang",
    description: "Programmatischer Zugriff auf alle ARIIA-Funktionen.",
    icon: Code,
    benefits: ["REST API", "Webhooks", "Bulk-Operationen", "Custom Integrationen"],
  },
  multi_source_members: {
    label: "Multi-Source Members",
    description: "Mitglieder aus mehreren Quellen synchronisieren.",
    icon: Database,
    benefits: ["Shopify-Sync", "WooCommerce", "HubSpot", "CSV-Import"],
  },
};

// ── FeatureGate Component ────────────────────────────────────────────────────

interface FeatureGateProps {
  /** The feature key to check */
  feature: keyof PlanFeatures;
  /** Content to show when feature is available */
  children: ReactNode;
  /** Optional custom fallback when feature is not available */
  fallback?: ReactNode;
  /** If true, show a compact inline badge instead of full upgrade prompt */
  inline?: boolean;
}

export function FeatureGate({ feature: featureKey, children, fallback, inline }: FeatureGateProps) {
  const { feature, loading, plan } = usePermissions();

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 40 }}>
        <div style={{ width: 20, height: 20, border: `2px solid ${T.border}`, borderTopColor: T.accent, borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
      </div>
    );
  }

  if (feature(featureKey)) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  if (inline) {
    return <InlineUpgradeBadge feature={featureKey} />;
  }

  return <UpgradePrompt feature={featureKey} currentPlan={plan.name} />;
}

// ── RoleGate Component ───────────────────────────────────────────────────────

interface RoleGateProps {
  /** Minimum role required */
  roles: Array<"system_admin" | "tenant_admin" | "tenant_user">;
  children: ReactNode;
  fallback?: ReactNode;
}

export function RoleGate({ roles, children, fallback }: RoleGateProps) {
  const { role, loading } = usePermissions();

  if (loading) return null;

  if (roles.includes(role)) {
    return <>{children}</>;
  }

  return fallback ? <>{fallback}</> : <AccessDenied />;
}

// ── PageGuard Component ──────────────────────────────────────────────────────

interface PageGuardProps {
  /** The page path to check */
  page: string;
  /** Optional feature required for this page */
  feature?: keyof PlanFeatures;
  children: ReactNode;
}

export function PageGuard({ page, feature: featureKey, children }: PageGuardProps) {
  const { canPage, feature, loading, role, plan } = usePermissions();

  if (loading) {
    return <PageLoadingSkeleton />;
  }

  if (!canPage(page)) {
    return <AccessDenied />;
  }

  if (featureKey && !feature(featureKey)) {
    return <UpgradePrompt feature={featureKey} currentPlan={plan.name} />;
  }

  return <>{children}</>;
}

// ── UsageBanner Component ────────────────────────────────────────────────────

interface UsageBannerProps {
  resource: "messages" | "members";
}

export function UsageBanner({ resource }: UsageBannerProps) {
  const { isNearLimit, isAtLimit, usage, plan } = usePermissions();

  if (!isNearLimit(resource)) return null;

  const atLimit = isAtLimit(resource);
  const current = resource === "messages" ? usage.messages_used : usage.members_count;
  const max = resource === "messages" ? plan.limits.max_monthly_messages : plan.limits.max_members;
  const label = resource === "messages" ? "Nachrichten" : "Mitglieder";
  const percentage = max ? Math.min(100, Math.round((current / max) * 100)) : 0;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 16px",
        borderRadius: 12,
        border: `1px solid ${atLimit ? T.danger + "44" : T.warning + "44"}`,
        background: atLimit ? T.dangerDim : T.warningDim,
        marginBottom: 16,
      }}
    >
      <div style={{ flex: "0 0 auto" }}>
        {atLimit ? (
          <Shield size={18} style={{ color: T.danger }} />
        ) : (
          <TrendingUp size={18} style={{ color: T.warning }} />
        )}
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: atLimit ? T.danger : T.warning }}>
          {atLimit
            ? `${label}-Limit erreicht (${current.toLocaleString("de-DE")} / ${max?.toLocaleString("de-DE")})`
            : `${label}-Limit fast erreicht (${percentage}%)`}
        </p>
        <p style={{ margin: "2px 0 0", fontSize: 12, color: T.textMuted }}>
          {atLimit
            ? "Upgrade deinen Plan, um weitere " + label + " zu nutzen."
            : `${current.toLocaleString("de-DE")} von ${max?.toLocaleString("de-DE")} ${label} verwendet.`}
        </p>
      </div>
      <div style={{ flex: "0 0 auto" }}>
        {/* Progress bar */}
        <div style={{ width: 80, height: 6, borderRadius: 3, background: T.border }}>
          <div
            style={{
              width: `${percentage}%`,
              height: "100%",
              borderRadius: 3,
              background: atLimit ? T.danger : T.warning,
              transition: "width 0.3s ease",
            }}
          />
        </div>
      </div>
    </div>
  );
}

// ── UpgradePrompt Component ──────────────────────────────────────────────────

interface UpgradePromptProps {
  feature: keyof PlanFeatures;
  currentPlan: string;
}

export function UpgradePrompt({ feature, currentPlan }: UpgradePromptProps) {
  const { requiredPlanFor } = usePermissions();
  const meta = FEATURE_META[feature];
  const requiredPlan = requiredPlanFor(feature);
  const Icon = meta.icon;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        padding: 40,
        textAlign: "center",
      }}
    >
      {/* Glow icon */}
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: 20,
          background: `linear-gradient(135deg, ${T.accentDim}, ${T.infoDim})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 24,
          position: "relative",
        }}
      >
        <Lock size={32} style={{ color: T.accent }} />
        <div
          style={{
            position: "absolute",
            top: -4,
            right: -4,
            width: 24,
            height: 24,
            borderRadius: 12,
            background: T.warning,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Crown size={12} style={{ color: "#000" }} />
        </div>
      </div>

      <h2 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 700, color: T.text }}>
        {meta.label}
      </h2>
      <p style={{ margin: "0 0 24px", fontSize: 14, color: T.textMuted, maxWidth: 480, lineHeight: 1.6 }}>
        {meta.description}
      </p>

      {/* Benefits grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: 8,
          marginBottom: 32,
          maxWidth: 400,
          width: "100%",
        }}
      >
        {meta.benefits.map((benefit) => (
          <div
            key={benefit}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              borderRadius: 8,
              background: T.surfaceAlt,
              border: `1px solid ${T.border}`,
              fontSize: 12,
              color: T.textMuted,
            }}
          >
            <Sparkles size={12} style={{ color: T.accent, flexShrink: 0 }} />
            {benefit}
          </div>
        ))}
      </div>

      {/* Plan badge */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 14px",
          borderRadius: 20,
          background: T.warningDim,
          border: `1px solid ${T.warning}33`,
          fontSize: 12,
          fontWeight: 600,
          color: T.warning,
          marginBottom: 16,
        }}
      >
        <Crown size={12} />
        Verfügbar ab {requiredPlan}
      </div>

      <p style={{ margin: "0 0 20px", fontSize: 12, color: T.textDim }}>
        Dein aktueller Plan: <strong style={{ color: T.textMuted }}>{currentPlan}</strong>
      </p>

      {/* CTA */}
      <a
        href="/settings/billing"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "12px 28px",
          borderRadius: 10,
          background: `linear-gradient(135deg, ${T.accent}, #8B5CF6)`,
          color: "#fff",
          fontSize: 14,
          fontWeight: 600,
          textDecoration: "none",
          transition: "transform 0.15s ease, box-shadow 0.15s ease",
          boxShadow: `0 4px 16px ${T.accent}44`,
        }}
        onMouseEnter={(e) => {
          (e.target as HTMLElement).style.transform = "translateY(-1px)";
        }}
        onMouseLeave={(e) => {
          (e.target as HTMLElement).style.transform = "translateY(0)";
        }}
      >
        Upgrade auf {requiredPlan}
        <ArrowUpRight size={16} />
      </a>
    </div>
  );
}

// ── InlineUpgradeBadge ───────────────────────────────────────────────────────

function InlineUpgradeBadge({ feature }: { feature: keyof PlanFeatures }) {
  const { requiredPlanFor } = usePermissions();
  const requiredPlan = requiredPlanFor(feature);

  return (
    <a
      href="/settings/billing"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "3px 10px",
        borderRadius: 6,
        background: T.warningDim,
        border: `1px solid ${T.warning}33`,
        fontSize: 11,
        fontWeight: 600,
        color: T.warning,
        textDecoration: "none",
        cursor: "pointer",
      }}
    >
      <Crown size={10} />
      {requiredPlan}
    </a>
  );
}

// ── AccessDenied Component ───────────────────────────────────────────────────

function AccessDenied() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        padding: 40,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 80,
          height: 80,
          borderRadius: 20,
          background: T.dangerDim,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 24,
        }}
      >
        <Shield size={32} style={{ color: T.danger }} />
      </div>
      <h2 style={{ margin: "0 0 8px", fontSize: 22, fontWeight: 700, color: T.text }}>
        Zugriff verweigert
      </h2>
      <p style={{ margin: 0, fontSize: 14, color: T.textMuted, maxWidth: 400, lineHeight: 1.6 }}>
        Du hast keine Berechtigung, auf diese Seite zuzugreifen.
        Kontaktiere deinen Administrator, wenn du Zugang benötigst.
      </p>
      <a
        href="/dashboard"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 24px",
          borderRadius: 10,
          background: T.surfaceAlt,
          border: `1px solid ${T.border}`,
          color: T.text,
          fontSize: 13,
          fontWeight: 600,
          textDecoration: "none",
          marginTop: 24,
        }}
      >
        Zum Dashboard
      </a>
    </div>
  );
}

// ── PageLoadingSkeleton ──────────────────────────────────────────────────────

function PageLoadingSkeleton() {
  return (
    <div style={{ padding: 32 }}>
      <div style={{ width: 200, height: 24, borderRadius: 6, background: T.surfaceAlt, marginBottom: 16 }} />
      <div style={{ width: "100%", height: 12, borderRadius: 4, background: T.surfaceAlt, marginBottom: 8 }} />
      <div style={{ width: "80%", height: 12, borderRadius: 4, background: T.surfaceAlt, marginBottom: 8 }} />
      <div style={{ width: "60%", height: 12, borderRadius: 4, background: T.surfaceAlt, marginBottom: 24 }} />
      <div style={{ width: "100%", height: 200, borderRadius: 12, background: T.surfaceAlt }} />
    </div>
  );
}
