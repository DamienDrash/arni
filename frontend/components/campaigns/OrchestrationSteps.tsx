"use client";

import React, { useState, CSSProperties } from "react";
import { T } from "@/lib/tokens";
import {
  Plus, Trash2, ArrowDown, Mail, MessageSquare,
  Smartphone, Send, Clock, Filter
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

export interface OrchestrationStep {
  step_order: number;
  channel: string;
  template_id: number | null;
  content_override_json: string | null;
  wait_hours: number;
  condition_type: string;
}

interface Props {
  steps: OrchestrationStep[];
  onChange: (steps: OrchestrationStep[]) => void;
  templates?: { id: number; name: string; channel: string }[];
}

/* ── Styles ────────────────────────────────────────────────────────── */

const S: Record<string, CSSProperties> = {
  container: {
    display: "flex",
    flexDirection: "column",
    gap: 0,
  },
  stepCard: {
    background: T.surface,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: "18px 20px",
    position: "relative",
  },
  stepHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: T.accentDim,
    color: T.accent,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
  },
  stepTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: T.text,
    marginLeft: 10,
    flex: 1,
  },
  deleteBtn: {
    background: "transparent",
    border: "none",
    color: T.textDim,
    cursor: "pointer",
    padding: 4,
    borderRadius: 6,
  },
  fieldRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: 12,
    marginBottom: 10,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: T.textMuted,
    textTransform: "uppercase" as const,
    letterSpacing: "0.04em",
    marginBottom: 4,
  },
  select: {
    width: "100%",
    background: T.surfaceAlt,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    color: T.text,
    padding: "8px 12px",
    fontSize: 13,
    outline: "none",
  },
  input: {
    width: "100%",
    background: T.surfaceAlt,
    border: `1px solid ${T.border}`,
    borderRadius: 8,
    color: T.text,
    padding: "8px 12px",
    fontSize: 13,
    outline: "none",
  },
  connector: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    padding: "6px 0",
    color: T.textDim,
  },
  connectorLine: {
    width: 2,
    height: 16,
    background: T.border,
  },
  addBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    width: "100%",
    padding: "12px 16px",
    background: T.accentDim,
    border: `1px dashed ${T.accent}`,
    borderRadius: 10,
    color: T.accent,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 8,
  },
};

/* ── Helpers ───────────────────────────────────────────────────────── */

const channelOptions = [
  { value: "email", label: "E-Mail", icon: Mail },
  { value: "whatsapp", label: "WhatsApp", icon: MessageSquare },
  { value: "sms", label: "SMS", icon: Smartphone },
  { value: "telegram", label: "Telegram", icon: Send },
];

const conditionOptions = [
  { value: "always", label: "Immer senden" },
  { value: "if_not_opened", label: "Wenn nicht geöffnet" },
  { value: "if_not_clicked", label: "Wenn nicht geklickt" },
];

/* ── Component ─────────────────────────────────────────────────────── */

export default function OrchestrationSteps({ steps, onChange, templates = [] }: Props) {
  const addStep = () => {
    const newStep: OrchestrationStep = {
      step_order: steps.length + 1,
      channel: "email",
      template_id: null,
      content_override_json: null,
      wait_hours: steps.length === 0 ? 0 : 24,
      condition_type: steps.length === 0 ? "always" : "if_not_opened",
    };
    onChange([...steps, newStep]);
  };

  const removeStep = (index: number) => {
    const updated = steps
      .filter((_, i) => i !== index)
      .map((s, i) => ({ ...s, step_order: i + 1 }));
    onChange(updated);
  };

  const updateStep = (index: number, field: keyof OrchestrationStep, value: any) => {
    const updated = steps.map((s, i) =>
      i === index ? { ...s, [field]: value } : s
    );
    onChange(updated);
  };

  return (
    <div style={S.container}>
      {steps.map((step, idx) => (
        <React.Fragment key={idx}>
          {idx > 0 && (
            <div style={S.connector}>
              <div style={S.connectorLine} />
              <ArrowDown size={14} />
              <div style={S.connectorLine} />
            </div>
          )}
          <div style={S.stepCard}>
            <div style={S.stepHeader}>
              <div style={{ display: "flex", alignItems: "center" }}>
                <div style={S.stepNumber}>{step.step_order}</div>
                <div style={S.stepTitle}>
                  {idx === 0 ? "Erster Versand" : `Folge-Schritt ${step.step_order}`}
                </div>
              </div>
              {steps.length > 1 && (
                <button
                  style={S.deleteBtn}
                  onClick={() => removeStep(idx)}
                  title="Schritt entfernen"
                >
                  <Trash2 size={16} />
                </button>
              )}
            </div>

            <div style={S.fieldRow}>
              {/* Channel */}
              <div>
                <div style={S.label}>Kanal</div>
                <select
                  style={S.select}
                  value={step.channel}
                  onChange={(e) => updateStep(idx, "channel", e.target.value)}
                >
                  {channelOptions.map((ch) => (
                    <option key={ch.value} value={ch.value}>{ch.label}</option>
                  ))}
                </select>
              </div>

              {/* Wait Time */}
              <div>
                <div style={S.label}>
                  <Clock size={10} style={{ marginRight: 4, verticalAlign: "middle" }} />
                  Wartezeit (Stunden)
                </div>
                <input
                  type="number"
                  style={S.input}
                  value={step.wait_hours}
                  min={0}
                  onChange={(e) => updateStep(idx, "wait_hours", parseInt(e.target.value) || 0)}
                  disabled={idx === 0}
                />
              </div>

              {/* Condition */}
              <div>
                <div style={S.label}>
                  <Filter size={10} style={{ marginRight: 4, verticalAlign: "middle" }} />
                  Bedingung
                </div>
                <select
                  style={S.select}
                  value={step.condition_type}
                  onChange={(e) => updateStep(idx, "condition_type", e.target.value)}
                  disabled={idx === 0}
                >
                  {conditionOptions.map((c) => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Template Selection */}
            {templates.length > 0 && (
              <div style={{ marginTop: 4 }}>
                <div style={S.label}>Vorlage (optional)</div>
                <select
                  style={S.select}
                  value={step.template_id || ""}
                  onChange={(e) => updateStep(idx, "template_id", e.target.value ? Number(e.target.value) : null)}
                >
                  <option value="">Standard-Kampagneninhalt</option>
                  {templates
                    .filter((t) => t.channel === step.channel || t.channel === "email")
                    .map((t) => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                </select>
              </div>
            )}
          </div>
        </React.Fragment>
      ))}

      <button style={S.addBtn} onClick={addStep}>
        <Plus size={16} />
        {steps.length === 0 ? "Ersten Schritt hinzufügen" : "Folge-Schritt hinzufügen"}
      </button>

      {steps.length > 1 && (
        <div style={{
          marginTop: 12,
          padding: "10px 14px",
          background: T.infoDim,
          borderRadius: 8,
          fontSize: 12,
          color: T.info,
          lineHeight: 1.5,
        }}>
          <strong>Omnichannel-Sequenz:</strong> Die Kampagne wird in {steps.length} Schritten versendet.
          {steps.filter(s => s.condition_type !== "always").length > 0 && (
            <> Folge-Schritte werden nur ausgelöst, wenn die jeweilige Bedingung erfüllt ist.</>
          )}
        </div>
      )}
    </div>
  );
}
