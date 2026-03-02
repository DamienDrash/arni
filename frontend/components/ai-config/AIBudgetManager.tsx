"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  Wallet, Edit3, Save, X, RefreshCcw, AlertTriangle, CheckCircle2,
  TrendingUp, Shield, DollarSign, Coins,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";

type BudgetStatus = {
  tenant_id: number;
  plan_name: string;
  monthly_token_limit: number | null;
  monthly_budget_cents: number | null;
  tokens_used: number;
  budget_used_cents: number;
  tokens_remaining: number | null;
  budget_remaining_cents: number | null;
  usage_percent: number;
  is_over_budget: boolean;
  overage_enabled: boolean;
};

type PlanBudget = {
  id: number;
  plan_id: number;
  monthly_token_limit: number | null;
  monthly_budget_cents: number | null;
  max_requests_per_minute: number;
  max_requests_per_day: number;
  allowed_providers: string[];
  allowed_models: string[];
  overage_enabled: boolean;
  overage_rate_per_1k_tokens: number;
};

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("de-DE");
}

function formatCents(cents: number): string {
  return `€${(cents / 100).toFixed(2)}`;
}

export function AIBudgetManager() {
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [planBudgets, setPlanBudgets] = useState<PlanBudget[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editPlan, setEditPlan] = useState<PlanBudget | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [budgetRes, planRes] = await Promise.all([
        apiFetch("/admin/ai/observability/budget/all"),
        apiFetch("/admin/ai/budgets"),
      ]);
      if (budgetRes.ok) setBudgets(await budgetRes.json());
      if (planRes.ok) setPlanBudgets(await planRes.json());
    } catch { setError("Netzwerkfehler"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSavePlan = async () => {
    if (!editPlan) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/admin/ai/budgets/${editPlan.id}`, {
        method: "PUT", body: JSON.stringify(editPlan),
      });
      if (res.ok) { setEditPlan(null); load(); }
      else { const d = await res.json().catch(() => ({})); setError(d.detail || "Fehler"); }
    } catch { setError("Netzwerkfehler"); }
    setSaving(false);
  };

  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, color: T.text, fontSize: 13, outline: "none" };
  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 4, display: "block" };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <SectionHeader title="Budget & Limits" subtitle="Plan-basierte Budgets, Token-Limits und Überschreitungsregeln" />
        <button onClick={load} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <RefreshCcw size={14} /> Aktualisieren
        </button>
      </div>

      {error && <div style={{ padding: 12, borderRadius: 8, background: T.dangerDim, color: T.danger, fontSize: 12, marginBottom: 16 }}>{error}</div>}

      {/* Plan Budget Configuration */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <Shield size={16} color={T.accent} /> Plan-Budget-Konfiguration
        </div>

        {/* Edit Form */}
        {editPlan && (
          <div style={{ padding: 20, borderRadius: 12, border: `1px solid ${T.accent}30`, background: T.surfaceAlt, marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Budget bearbeiten (Plan #{editPlan.plan_id})</span>
              <button onClick={() => setEditPlan(null)} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}><X size={18} /></button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
              <div><label style={labelStyle}>Monatliches Token-Limit</label><input style={inputStyle} type="number" value={editPlan.monthly_token_limit || ""} onChange={(e) => setEditPlan({ ...editPlan, monthly_token_limit: parseInt(e.target.value) || null })} /></div>
              <div><label style={labelStyle}>Monatliches Budget (Cents)</label><input style={inputStyle} type="number" value={editPlan.monthly_budget_cents || ""} onChange={(e) => setEditPlan({ ...editPlan, monthly_budget_cents: parseInt(e.target.value) || null })} /></div>
              <div><label style={labelStyle}>Max Requests/Minute</label><input style={inputStyle} type="number" value={editPlan.max_requests_per_minute} onChange={(e) => setEditPlan({ ...editPlan, max_requests_per_minute: parseInt(e.target.value) || 60 })} /></div>
              <div><label style={labelStyle}>Max Requests/Tag</label><input style={inputStyle} type="number" value={editPlan.max_requests_per_day} onChange={(e) => setEditPlan({ ...editPlan, max_requests_per_day: parseInt(e.target.value) || 10000 })} /></div>
              <div><label style={labelStyle}>Überschreitung erlaubt</label>
                <select style={inputStyle} value={editPlan.overage_enabled ? "true" : "false"} onChange={(e) => setEditPlan({ ...editPlan, overage_enabled: e.target.value === "true" })}>
                  <option value="true">Ja</option><option value="false">Nein</option>
                </select>
              </div>
              <div><label style={labelStyle}>Überschreitungsrate (pro 1K Tokens)</label><input style={inputStyle} type="number" step="0.01" value={editPlan.overage_rate_per_1k_tokens} onChange={(e) => setEditPlan({ ...editPlan, overage_rate_per_1k_tokens: parseFloat(e.target.value) || 0 })} /></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button onClick={() => setEditPlan(null)} style={{ padding: "8px 16px", borderRadius: 8, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 12 }}>Abbrechen</button>
              <button onClick={handleSavePlan} disabled={saving} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                <Save size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />{saving ? "..." : "Speichern"}
              </button>
            </div>
          </div>
        )}

        {planBudgets.length === 0 ? (
          <div style={{ fontSize: 12, color: T.textDim, padding: 16 }}>Keine Plan-Budgets konfiguriert.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
            {planBudgets.map((pb) => (
              <div key={pb.id} style={{ padding: 16, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Plan #{pb.plan_id}</span>
                  <button onClick={() => setEditPlan({ ...pb })} style={{ padding: "4px 8px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer" }}><Edit3 size={12} /></button>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: T.textMuted }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span><Coins size={10} style={{ marginRight: 4, verticalAlign: "middle" }} />Token-Limit</span>
                    <span style={{ color: T.text, fontWeight: 600 }}>{pb.monthly_token_limit ? formatNumber(pb.monthly_token_limit) : "Unbegrenzt"}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span><DollarSign size={10} style={{ marginRight: 4, verticalAlign: "middle" }} />Budget</span>
                    <span style={{ color: T.text, fontWeight: 600 }}>{pb.monthly_budget_cents ? formatCents(pb.monthly_budget_cents) : "Unbegrenzt"}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Rate Limit</span>
                    <span style={{ color: T.text }}>{pb.max_requests_per_minute}/min</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>Überschreitung</span>
                    <Badge variant={pb.overage_enabled ? "success" : "danger"}>{pb.overage_enabled ? "Erlaubt" : "Blockiert"}</Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tenant Budget Status */}
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <TrendingUp size={16} color={T.accent} /> Tenant-Budget-Status (aktueller Monat)
        </div>
        {loading ? (
          <div style={{ textAlign: "center", padding: 40, color: T.textMuted, fontSize: 13 }}>Lade...</div>
        ) : budgets.length === 0 ? (
          <div style={{ fontSize: 12, color: T.textDim, padding: 16 }}>Keine Tenant-Budgets vorhanden.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {budgets.map((b) => {
              const barColor = b.usage_percent >= 90 ? T.danger : b.usage_percent >= 70 ? T.warning : T.success;
              return (
                <div key={b.tenant_id} style={{ padding: 16, borderRadius: 12, border: `1px solid ${b.is_over_budget ? T.danger + "40" : T.border}`, background: T.surfaceAlt }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Tenant #{b.tenant_id}</span>
                      <Badge variant="default">{b.plan_name}</Badge>
                      {b.is_over_budget && <Badge variant="danger"><AlertTriangle size={10} style={{ marginRight: 3 }} />Über Budget</Badge>}
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 700, color: barColor }}>{b.usage_percent.toFixed(1)}%</span>
                  </div>
                  <ProgressBar value={Math.min(b.usage_percent, 100)} color={barColor} />
                  <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8, fontSize: 11, color: T.textMuted }}>
                    <span>Tokens: {formatNumber(b.tokens_used)}{b.monthly_token_limit ? ` / ${formatNumber(b.monthly_token_limit)}` : ""}</span>
                    <span>Kosten: {formatCents(b.budget_used_cents)}{b.monthly_budget_cents ? ` / ${formatCents(b.monthly_budget_cents)}` : ""}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
