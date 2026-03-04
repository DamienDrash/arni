"use client";

import React, { useState, useEffect, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import {
  Activity, Server, Inbox, AlertTriangle,
  CheckCircle2, RefreshCw, Zap,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

interface QueueStats {
  send_queue_length: number;
  dead_letter_queue_length: number;
  analytics_queue_length: number;
  workers_active: boolean;
  last_processed_at: string | null;
  throughput_per_minute: number;
}

/* ── Styles ────────────────────────────────────────────────────────── */

const S: Record<string, CSSProperties> = {
  container: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 20,
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
    gap: 8,
  },
  title: {
    fontSize: 14,
    fontWeight: 700,
    color: T.text,
    margin: 0,
  },
  refreshBtn: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "4px 10px",
    borderRadius: 6,
    border: `1px solid ${T.border}`,
    background: "transparent",
    color: T.textMuted,
    fontSize: 11,
    cursor: "pointer",
  },
  metricsRow: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 10,
  },
  metricCard: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "12px 14px",
    borderRadius: 10,
    background: T.bg,
    border: `1px solid ${T.border}`,
  },
  metricIcon: {
    width: 32,
    height: 32,
    borderRadius: 8,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: 700,
    color: T.text,
    lineHeight: 1,
  },
  metricLabel: {
    fontSize: 11,
    color: T.textMuted,
    marginTop: 2,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
    marginRight: 6,
  },
  alertBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: 8,
    marginTop: 12,
    fontSize: 12,
    fontWeight: 500,
  },
};

/* ── Component ─────────────────────────────────────────────────────── */

export default function CampaignQueueMonitor() {
  const [stats, setStats] = useState<QueueStats | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStats = async () => {
    try {
      const res = await apiFetch("/v2/admin/campaigns/queue-stats");
      if (res.ok) {
        setStats(await res.json());
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !stats) {
    return null;
  }

  const hasDeadLetters = stats.dead_letter_queue_length > 0;

  return (
    <div style={S.container}>
      <div style={S.header}>
        <div style={S.headerLeft}>
          <Activity size={15} color={T.accent} />
          <h4 style={S.title}>Versand-Queue</h4>
          <span style={{
            ...S.statusDot,
            background: stats.workers_active ? T.success : T.danger,
          }} />
          <span style={{ fontSize: 11, color: stats.workers_active ? T.success : T.danger }}>
            {stats.workers_active ? "Aktiv" : "Inaktiv"}
          </span>
        </div>
        <button style={S.refreshBtn} onClick={loadStats}>
          <RefreshCw size={11} />
        </button>
      </div>

      <div style={S.metricsRow}>
        <div style={S.metricCard}>
          <div style={{ ...S.metricIcon, background: T.warningDim }}>
            <Inbox size={16} color={T.warning} />
          </div>
          <div>
            <div style={S.metricValue}>{stats.send_queue_length}</div>
            <div style={S.metricLabel}>Wartend</div>
          </div>
        </div>

        <div style={S.metricCard}>
          <div style={{ ...S.metricIcon, background: T.successDim }}>
            <Zap size={16} color={T.success} />
          </div>
          <div>
            <div style={S.metricValue}>{stats.throughput_per_minute}</div>
            <div style={S.metricLabel}>Pro Minute</div>
          </div>
        </div>

        <div style={S.metricCard}>
          <div style={{ ...S.metricIcon, background: hasDeadLetters ? T.dangerDim : T.bg }}>
            <AlertTriangle size={16} color={hasDeadLetters ? T.danger : T.textDim} />
          </div>
          <div>
            <div style={{ ...S.metricValue, color: hasDeadLetters ? T.danger : T.text }}>
              {stats.dead_letter_queue_length}
            </div>
            <div style={S.metricLabel}>Fehlgeschlagen</div>
          </div>
        </div>
      </div>

      {hasDeadLetters && (
        <div style={{
          ...S.alertBar,
          background: T.dangerDim,
          color: T.danger,
          border: `1px solid rgba(255,107,107,0.2)`,
        }}>
          <AlertTriangle size={14} />
          {stats.dead_letter_queue_length} Nachrichten konnten nach mehreren Versuchen nicht zugestellt werden.
        </div>
      )}
    </div>
  );
}
