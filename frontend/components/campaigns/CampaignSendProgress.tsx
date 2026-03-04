"use client";

import React, { useState, useEffect, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import {
  Send, CheckCircle, AlertCircle, Clock, Loader2,
  BarChart3, RefreshCw, Calendar,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

interface RecipientStats {
  total: number;
  queued: number;
  sent: number;
  delivered: number;
  failed: number;
  opened: number;
  clicked: number;
}

interface CampaignSendProgressProps {
  campaignId: number;
  campaignStatus: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

/* ── Styles ────────────────────────────────────────────────────────── */

const S: Record<string, CSSProperties> = {
  container: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 20,
    marginTop: 16,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  title: {
    fontSize: 15,
    fontWeight: 700,
    color: T.text,
    margin: 0,
  },
  subtitle: {
    fontSize: 12,
    color: T.textMuted,
    margin: 0,
    marginTop: 2,
  },
  refreshBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 12px",
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    background: "transparent",
    color: T.textMuted,
    fontSize: 12,
    cursor: "pointer",
  },
  progressBarContainer: {
    width: "100%",
    height: 10,
    borderRadius: 5,
    background: T.bg,
    overflow: "hidden",
    marginBottom: 16,
    display: "flex",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 12,
  },
  statCard: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    padding: "12px 8px",
    borderRadius: 10,
    background: T.bg,
    border: `1px solid ${T.border}`,
  },
  statValue: {
    fontSize: 20,
    fontWeight: 700,
    color: T.text,
    lineHeight: 1,
  },
  statLabel: {
    fontSize: 11,
    fontWeight: 500,
    color: T.textMuted,
    marginTop: 4,
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
  },
  statusBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 5,
    padding: "4px 10px",
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
  },
};

/* ── Status Badge Helper ──────────────────────────────────────────── */

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { bg: string; color: string; icon: React.ReactNode; label: string }> = {
    draft: { bg: T.bg, color: T.textMuted, icon: <Clock size={12} />, label: "Entwurf" },
    approved: { bg: T.infoDim, color: T.info, icon: <CheckCircle size={12} />, label: "Freigegeben" },
    queued: { bg: T.warningDim, color: T.warning, icon: <Clock size={12} />, label: "In Warteschlange" },
    sending: { bg: T.warningDim, color: T.warning, icon: <Loader2 size={12} />, label: "Wird versendet..." },
    sent: { bg: T.successDim, color: T.success, icon: <CheckCircle size={12} />, label: "Versendet" },
    failed: { bg: T.dangerDim, color: T.danger, icon: <AlertCircle size={12} />, label: "Fehlgeschlagen" },
    ab_testing: { bg: `${T.accent}15`, color: T.accent, icon: <BarChart3 size={12} />, label: "A/B-Test läuft" },
    scheduled: { bg: T.infoDim, color: T.info, icon: <Calendar size={12} />, label: "Geplant" },
  };

  const c = config[status] || config.draft;
  return (
    <span style={{ ...S.statusBadge, background: c.bg, color: c.color }}>
      {c.icon} {c.label}
    </span>
  );
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function CampaignSendProgress({
  campaignId,
  campaignStatus,
  autoRefresh = true,
  refreshInterval = 5000,
}: CampaignSendProgressProps) {
  const [stats, setStats] = useState<RecipientStats | null>(null);
  const [loading, setLoading] = useState(true);

  const isActive = ["queued", "sending", "ab_testing"].includes(campaignStatus);

  const loadStats = async () => {
    try {
      const res = await apiFetch(`/admin/campaigns/${campaignId}/analytics`);
      if (res.ok) {
        const data = await res.json();
        setStats({
          total: data.total_recipients || 0,
          queued: data.queued || 0,
          sent: data.sent || 0,
          delivered: data.delivered || 0,
          failed: data.failed || 0,
          opened: data.unique_opens || 0,
          clicked: data.unique_clicks || 0,
        });
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, [campaignId]);

  useEffect(() => {
    if (!autoRefresh || !isActive) return;
    const interval = setInterval(loadStats, refreshInterval);
    return () => clearInterval(interval);
  }, [campaignId, campaignStatus, autoRefresh, refreshInterval]);

  if (loading || !stats) {
    return null;
  }

  const total = stats.total || 1;
  const sentPct = (stats.sent / total) * 100;
  const failedPct = (stats.failed / total) * 100;
  const queuedPct = (stats.queued / total) * 100;
  const openRate = stats.sent > 0 ? ((stats.opened / stats.sent) * 100).toFixed(1) : "0.0";
  const clickRate = stats.sent > 0 ? ((stats.clicked / stats.sent) * 100).toFixed(1) : "0.0";

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerLeft}>
          <Send size={16} color={T.accent} />
          <div>
            <p style={S.title}>Versandfortschritt</p>
            <p style={S.subtitle}>
              {stats.sent + stats.failed} von {stats.total} verarbeitet
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <StatusBadge status={campaignStatus} />
          <button style={S.refreshBtn} onClick={loadStats}>
            <RefreshCw size={12} /> Aktualisieren
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div style={S.progressBarContainer}>
        {sentPct > 0 && (
          <div
            style={{
              width: `${sentPct}%`,
              height: "100%",
              background: T.success,
              transition: "width 0.5s ease",
            }}
          />
        )}
        {failedPct > 0 && (
          <div
            style={{
              width: `${failedPct}%`,
              height: "100%",
              background: T.danger,
              transition: "width 0.5s ease",
            }}
          />
        )}
        {queuedPct > 0 && (
          <div
            style={{
              width: `${queuedPct}%`,
              height: "100%",
              background: T.warning,
              transition: "width 0.5s ease",
            }}
          />
        )}
      </div>

      {/* Stats Grid */}
      <div style={S.statsGrid}>
        <div style={S.statCard}>
          <span style={{ ...S.statValue, color: T.success }}>{stats.sent}</span>
          <span style={S.statLabel}>Gesendet</span>
        </div>
        <div style={S.statCard}>
          <span style={{ ...S.statValue, color: T.danger }}>{stats.failed}</span>
          <span style={S.statLabel}>Fehlgeschlagen</span>
        </div>
        <div style={S.statCard}>
          <span style={{ ...S.statValue, color: T.info }}>{openRate}%</span>
          <span style={S.statLabel}>Öffnungsrate</span>
        </div>
        <div style={S.statCard}>
          <span style={{ ...S.statValue, color: T.accent }}>{clickRate}%</span>
          <span style={S.statLabel}>Klickrate</span>
        </div>
      </div>
    </div>
  );
}

// Re-export StatusBadge for use in other components
export { StatusBadge };
