"use client";

import React, { useState, useEffect, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { FlaskConical, Plus, Trash2, Sparkles } from "lucide-react";

interface Variant {
  id?: number;
  variant_name: string;
  content_subject: string;
  content_body: string;
  content_html: string;
  percentage: number;
}

interface ABTestConfigProps {
  campaignId?: number;
  isEnabled: boolean;
  onToggle: (enabled: boolean) => void;
  variants: Variant[];
  onVariantsChange: (variants: Variant[]) => void;
  testPercentage: number;
  onTestPercentageChange: (pct: number) => void;
  durationHours: number;
  onDurationHoursChange: (hours: number) => void;
  metric: string;
  onMetricChange: (metric: string) => void;
  autoSend: boolean;
  onAutoSendChange: (auto: boolean) => void;
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
    justifyContent: "space-between",
    marginBottom: 20,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  title: {
    fontSize: 16,
    fontWeight: 600,
    color: T.text,
    margin: 0,
  },
  subtitle: {
    fontSize: 13,
    color: T.textMuted,
    margin: 0,
    marginTop: 2,
  },
  toggle: {
    position: "relative" as const,
    width: 44,
    height: 24,
    borderRadius: 12,
    cursor: "pointer",
    transition: "background 0.2s",
    border: "none",
    padding: 0,
  },
  toggleDot: {
    position: "absolute" as const,
    top: 3,
    width: 18,
    height: 18,
    borderRadius: "50%",
    background: "#fff",
    transition: "left 0.2s",
  },
  configGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr 1fr",
    gap: 16,
    marginBottom: 24,
  },
  fieldGroup: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 6,
  },
  label: {
    fontSize: 12,
    fontWeight: 500,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  input: {
    background: T.bg,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    padding: "8px 12px",
    color: T.text,
    fontSize: 14,
    outline: "none",
    width: "100%",
  },
  select: {
    background: T.bg,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    padding: "8px 12px",
    color: T.text,
    fontSize: 14,
    outline: "none",
    width: "100%",
    cursor: "pointer",
  },
  variantsSection: {
    marginTop: 20,
  },
  variantsHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  variantCard: {
    background: T.bg,
    border: `1px solid ${T.border}`,
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
  },
  variantHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  variantBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 10px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
  },
  variantFields: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: 10,
  },
  addBtn: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "8px 14px",
    borderRadius: 8,
    border: `1px dashed ${T.border}`,
    background: "transparent",
    color: T.accentLight,
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  deleteBtn: {
    display: "flex",
    alignItems: "center",
    padding: "6px 8px",
    borderRadius: 6,
    border: "none",
    background: T.dangerDim,
    color: T.danger,
    cursor: "pointer",
    fontSize: 12,
  },
  checkboxRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    marginTop: 4,
  },
};

const VARIANT_COLORS = ["#6C5CE7", "#00D68F", "#FFAA00", "#FF6B6B"];
const VARIANT_LABELS = ["A", "B", "C", "D"];

export default function ABTestConfig({
  campaignId,
  isEnabled,
  onToggle,
  variants,
  onVariantsChange,
  testPercentage,
  onTestPercentageChange,
  durationHours,
  onDurationHoursChange,
  metric,
  onMetricChange,
  autoSend,
  onAutoSendChange,
}: ABTestConfigProps) {
  const addVariant = () => {
    if (variants.length >= 4) return;
    const nextLabel = VARIANT_LABELS[variants.length] || `V${variants.length + 1}`;
    onVariantsChange([
      ...variants,
      {
        variant_name: nextLabel,
        content_subject: "",
        content_body: "",
        content_html: "",
        percentage: Math.floor(100 / (variants.length + 1)),
      },
    ]);
  };

  const removeVariant = (idx: number) => {
    if (variants.length <= 2) return;
    const updated = variants.filter((_, i) => i !== idx);
    onVariantsChange(updated);
  };

  const updateVariant = (idx: number, field: keyof Variant, value: string | number) => {
    const updated = [...variants];
    updated[idx] = { ...updated[idx], [field]: value };
    onVariantsChange(updated);
  };

  if (!isEnabled) {
    return (
      <div style={S.container}>
        <div style={S.header}>
          <div style={S.headerLeft}>
            <FlaskConical size={18} color={T.accent} />
            <div>
              <p style={S.title}>A/B-Test</p>
              <p style={S.subtitle}>Verschiedene Varianten testen und den Gewinner automatisch versenden</p>
            </div>
          </div>
          <button
            style={{ ...S.toggle, background: T.border }}
            onClick={() => onToggle(true)}
          >
            <div style={{ ...S.toggleDot, left: 3 }} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ ...S.container, borderColor: T.accent }}>
      <div style={S.header}>
        <div style={S.headerLeft}>
          <FlaskConical size={18} color={T.accent} />
          <div>
            <p style={S.title}>A/B-Test aktiviert</p>
            <p style={S.subtitle}>Konfiguriere die Testvarianten und Parameter</p>
          </div>
        </div>
        <button
          style={{ ...S.toggle, background: T.accent }}
          onClick={() => onToggle(false)}
        >
          <div style={{ ...S.toggleDot, left: 23 }} />
        </button>
      </div>

      {/* Test Configuration */}
      <div style={S.configGrid}>
        <div style={S.fieldGroup}>
          <label style={S.label}>Testanteil (%)</label>
          <input
            type="number"
            min={5}
            max={50}
            value={testPercentage}
            onChange={(e) => onTestPercentageChange(parseInt(e.target.value) || 20)}
            style={S.input}
          />
        </div>
        <div style={S.fieldGroup}>
          <label style={S.label}>Testdauer (Stunden)</label>
          <input
            type="number"
            min={1}
            max={72}
            value={durationHours}
            onChange={(e) => onDurationHoursChange(parseInt(e.target.value) || 4)}
            style={S.input}
          />
        </div>
        <div style={S.fieldGroup}>
          <label style={S.label}>Gewinner-Metrik</label>
          <select
            value={metric}
            onChange={(e) => onMetricChange(e.target.value)}
            style={S.select}
          >
            <option value="open_rate">Öffnungsrate</option>
            <option value="click_rate">Klickrate</option>
          </select>
        </div>
        <div style={S.fieldGroup}>
          <label style={S.label}>&nbsp;</label>
          <div style={S.checkboxRow}>
            <input
              type="checkbox"
              checked={autoSend}
              onChange={(e) => onAutoSendChange(e.target.checked)}
              style={{ accentColor: T.accent }}
            />
            <span style={{ fontSize: 13, color: T.text }}>Auto-Versand</span>
          </div>
        </div>
      </div>

      {/* Variants */}
      <div style={S.variantsSection}>
        <div style={S.variantsHeader}>
          <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>
            Varianten ({variants.length}/4)
          </span>
          {variants.length < 4 && (
            <button style={S.addBtn} onClick={addVariant}>
              <Plus size={14} /> Variante hinzufügen
            </button>
          )}
        </div>

        {variants.map((v, idx) => (
          <div key={idx} style={S.variantCard}>
            <div style={S.variantHeader}>
              <span
                style={{
                  ...S.variantBadge,
                  background: `${VARIANT_COLORS[idx]}20`,
                  color: VARIANT_COLORS[idx],
                }}
              >
                <Sparkles size={13} />
                Variante {v.variant_name}
              </span>
              {variants.length > 2 && (
                <button style={S.deleteBtn} onClick={() => removeVariant(idx)}>
                  <Trash2 size={13} />
                </button>
              )}
            </div>
            <div style={S.variantFields}>
              <div style={S.fieldGroup}>
                <label style={S.label}>Betreffzeile</label>
                <input
                  type="text"
                  value={v.content_subject}
                  onChange={(e) => updateVariant(idx, "content_subject", e.target.value)}
                  placeholder={`Betreffzeile für Variante ${v.variant_name}...`}
                  style={S.input}
                />
              </div>
              <div style={S.fieldGroup}>
                <label style={S.label}>Inhalt (Kurztext)</label>
                <textarea
                  value={v.content_body}
                  onChange={(e) => updateVariant(idx, "content_body", e.target.value)}
                  placeholder={`Inhalt für Variante ${v.variant_name}...`}
                  rows={3}
                  style={{ ...S.input, resize: "vertical" as const, fontFamily: "inherit" }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
