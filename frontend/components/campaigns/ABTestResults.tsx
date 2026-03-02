"use client";

import React, { useState, useEffect, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { FlaskConical, Trophy, BarChart3, TrendingUp, AlertCircle } from "lucide-react";

interface VariantResult {
  variant_name: string;
  subject: string | null;
  sent: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
  is_winner: boolean;
  confidence_level: number | null;
}

interface ABTestResultsData {
  campaign_id: number;
  metric: string;
  test_percentage: number;
  duration_hours: number;
  auto_send: boolean;
  winner_variant: string | null;
  variants: VariantResult[];
}

interface ABTestResultsProps {
  campaignId: number;
}

const S: Record<string, CSSProperties> = {
  container: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 24,
    marginTop: 16,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 20,
  },
  title: {
    fontSize: 16,
    fontWeight: 600,
    color: T.text,
    margin: 0,
  },
  metaRow: {
    display: "flex",
    gap: 16,
    marginBottom: 20,
    flexWrap: "wrap" as const,
  },
  metaItem: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 12px",
    borderRadius: 8,
    background: T.bg,
    border: `1px solid ${T.border}`,
    fontSize: 13,
    color: T.textMuted,
  },
  chartArea: {
    marginBottom: 24,
  },
  barContainer: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
  },
  barLabel: {
    width: 80,
    fontSize: 13,
    fontWeight: 600,
    color: T.text,
    textAlign: "right" as const,
  },
  barTrack: {
    flex: 1,
    height: 32,
    borderRadius: 8,
    background: T.bg,
    position: "relative" as const,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 8,
    transition: "width 0.6s ease",
    display: "flex",
    alignItems: "center",
    paddingLeft: 10,
  },
  barValue: {
    fontSize: 12,
    fontWeight: 600,
    color: "#fff",
    whiteSpace: "nowrap" as const,
  },
  winnerBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "3px 8px",
    borderRadius: 6,
    background: `${T.success}20`,
    color: T.success,
    fontSize: 11,
    fontWeight: 600,
    marginLeft: 8,
  },
  confidenceBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "6px 12px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 500,
  },
  variantTable: {
    width: "100%",
    borderCollapse: "collapse" as const,
    marginTop: 16,
  },
  th: {
    textAlign: "left" as const,
    padding: "10px 12px",
    fontSize: 12,
    fontWeight: 500,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    borderBottom: `1px solid ${T.border}`,
  },
  td: {
    padding: "12px 12px",
    fontSize: 14,
    color: T.text,
    borderBottom: `1px solid ${T.border}`,
  },
  loading: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 40,
    color: T.textMuted,
    fontSize: 14,
  },
  error: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: 16,
    borderRadius: 8,
    background: T.dangerDim,
    color: T.danger,
    fontSize: 13,
  },
};

const VARIANT_COLORS = ["#6C5CE7", "#00D68F", "#FFAA00", "#FF6B6B"];

export default function ABTestResults({ campaignId }: ABTestResultsProps) {
  const [data, setData] = useState<ABTestResultsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadResults();
  }, [campaignId]);

  const loadResults = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/v2/admin/campaigns/${campaignId}/ab-test`);
      if (res.ok) {
        setData(await res.json());
      } else {
        setError("Ergebnisse konnten nicht geladen werden.");
      }
    } catch (e) {
      setError("Verbindungsfehler.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div style={S.loading}>Lade A/B-Test-Ergebnisse...</div>;
  }

  if (error) {
    return (
      <div style={S.error}>
        <AlertCircle size={16} /> {error}
      </div>
    );
  }

  if (!data || !data.variants.length) {
    return null;
  }

  const metricLabel = data.metric === "open_rate" ? "Öffnungsrate" : "Klickrate";
  const maxRate = Math.max(...data.variants.map((v) =>
    data.metric === "open_rate" ? v.open_rate : v.click_rate
  ));

  const confidence = data.variants.find((v) => v.is_winner)?.confidence_level;
  const confidencePercent = confidence ? Math.round(confidence * 100) : 0;
  const isSignificant = confidencePercent >= 95;

  return (
    <div style={S.container}>
      <div style={S.header}>
        <FlaskConical size={18} color={T.accent} />
        <h3 style={S.title}>A/B-Test Ergebnisse</h3>
      </div>

      {/* Meta Info */}
      <div style={S.metaRow}>
        <span style={S.metaItem}>
          <BarChart3 size={14} /> Metrik: {metricLabel}
        </span>
        <span style={S.metaItem}>
          Testanteil: {data.test_percentage}%
        </span>
        <span style={S.metaItem}>
          Testdauer: {data.duration_hours}h
        </span>
        <span
          style={{
            ...S.confidenceBadge,
            background: isSignificant ? T.successDim : T.warningDim,
            color: isSignificant ? T.success : T.warning,
          }}
        >
          <TrendingUp size={14} />
          Konfidenz: {confidencePercent}%
          {isSignificant ? " (signifikant)" : " (nicht signifikant)"}
        </span>
      </div>

      {/* Bar Chart */}
      <div style={S.chartArea}>
        {data.variants.map((v, idx) => {
          const rate = data.metric === "open_rate" ? v.open_rate : v.click_rate;
          const widthPct = maxRate > 0 ? (rate / maxRate) * 100 : 0;
          const color = VARIANT_COLORS[idx] || T.accent;

          return (
            <div key={v.variant_name} style={S.barContainer}>
              <div style={S.barLabel}>
                Variante {v.variant_name}
                {v.is_winner && (
                  <span style={S.winnerBadge}>
                    <Trophy size={11} /> Gewinner
                  </span>
                )}
              </div>
              <div style={S.barTrack}>
                <div
                  style={{
                    ...S.barFill,
                    width: `${Math.max(widthPct, 5)}%`,
                    background: `linear-gradient(90deg, ${color}, ${color}88)`,
                  }}
                >
                  <span style={S.barValue}>
                    {(rate * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Detail Table */}
      <table style={S.variantTable}>
        <thead>
          <tr>
            <th style={S.th}>Variante</th>
            <th style={S.th}>Betreff</th>
            <th style={S.th}>Gesendet</th>
            <th style={S.th}>Geöffnet</th>
            <th style={S.th}>Geklickt</th>
            <th style={S.th}>Öffnungsrate</th>
            <th style={S.th}>Klickrate</th>
          </tr>
        </thead>
        <tbody>
          {data.variants.map((v, idx) => (
            <tr
              key={v.variant_name}
              style={{
                background: v.is_winner ? `${T.success}08` : "transparent",
              }}
            >
              <td style={S.td}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    fontWeight: 600,
                    color: VARIANT_COLORS[idx],
                  }}
                >
                  {v.variant_name}
                  {v.is_winner && (
                    <Trophy size={13} color={T.success} />
                  )}
                </span>
              </td>
              <td style={{ ...S.td, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                {v.subject || "—"}
              </td>
              <td style={S.td}>{v.sent.toLocaleString("de-DE")}</td>
              <td style={S.td}>{v.opened.toLocaleString("de-DE")}</td>
              <td style={S.td}>{v.clicked.toLocaleString("de-DE")}</td>
              <td style={{ ...S.td, fontWeight: 600 }}>
                {(v.open_rate * 100).toFixed(1)}%
              </td>
              <td style={{ ...S.td, fontWeight: 600 }}>
                {(v.click_rate * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
