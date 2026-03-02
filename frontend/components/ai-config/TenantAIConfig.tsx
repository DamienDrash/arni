"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  Cpu, Bot, Key, Save, RefreshCcw, Eye, EyeOff, Zap,
  Shield, TrendingUp, Coins, AlertTriangle, CheckCircle2,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";

type TenantConfig = {
  provider_slug: string;
  model: string;
  has_byok: boolean;
};
type AgentOverride = {
  id: number;
  agent_slug: string;
  agent_name: string;
  provider_slug_override: string | null;
  model_override: string | null;
  temperature_override: number | null;
  is_enabled: boolean;
};
type BudgetStatus = {
  tenant_id: number; plan_name: string;
  monthly_token_limit: number | null; monthly_budget_cents: number | null;
  tokens_used: number; budget_used_cents: number;
  tokens_remaining: number | null; budget_remaining_cents: number | null;
  usage_percent: number; is_over_budget: boolean;
};

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("de-DE");
}
function formatCents(cents: number): string { return `€${(cents / 100).toFixed(2)}`; }

export function TenantAIConfig() {
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [agents, setAgents] = useState<AgentOverride[]>([]);
  const [budget, setBudget] = useState<BudgetStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [byokKey, setByokKey] = useState("");
  const [byokProvider, setByokProvider] = useState("openai");
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cRes, aRes, bRes] = await Promise.all([
        apiFetch("/api/v1/tenant/ai/config"),
        apiFetch("/api/v1/tenant/ai/agents"),
        apiFetch("/api/v1/tenant/ai/observability/budget"),
      ]);
      if (cRes.ok) setConfig(await cRes.json());
      if (aRes.ok) setAgents(await aRes.json());
      if (bRes.ok) setBudget(await bRes.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSaveByok = async () => {
    if (!byokKey.trim()) return;
    setSaving(true);
    try {
      const res = await apiFetch("/api/v1/tenant/ai/byok", {
        method: "POST", body: JSON.stringify({ provider_slug: byokProvider, api_key: byokKey }),
      });
      if (res.ok) { setSuccess("BYOK-Key gespeichert!"); setByokKey(""); load(); setTimeout(() => setSuccess(null), 3000); }
    } catch { }
    setSaving(false);
  };

  const handleToggleAgent = async (agentId: number, enabled: boolean) => {
    await apiFetch(`/api/v1/tenant/ai/agents/${agentId}`, {
      method: "PUT", body: JSON.stringify({ is_enabled: enabled }),
    });
    load();
  };

  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, color: T.text, fontSize: 13, outline: "none" };
  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 4, display: "block" };

  if (loading) return <Card style={{ padding: 40, textAlign: "center" }}><span style={{ color: T.textMuted, fontSize: 13 }}>Lade KI-Konfiguration...</span></Card>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Budget Status */}
      {budget && (
        <Card style={{ padding: 20 }}>
          <SectionHeader title="Dein KI-Budget" subtitle={`Plan: ${budget.plan_name}`} />
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 12 }}>
              <span style={{ color: T.textMuted }}>Verbrauch diesen Monat</span>
              <span style={{ color: budget.usage_percent >= 90 ? T.danger : T.text, fontWeight: 700 }}>{budget.usage_percent.toFixed(1)}%</span>
            </div>
            <ProgressBar value={Math.min(budget.usage_percent, 100)} color={budget.usage_percent >= 90 ? T.danger : budget.usage_percent >= 70 ? T.warning : T.success} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 16 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: T.text }}>{formatNumber(budget.tokens_used)}</div>
                <div style={{ fontSize: 10, color: T.textMuted }}>Tokens verbraucht</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: T.text }}>{budget.tokens_remaining != null ? formatNumber(budget.tokens_remaining) : "∞"}</div>
                <div style={{ fontSize: 10, color: T.textMuted }}>Tokens verbleibend</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: T.success }}>{formatCents(budget.budget_used_cents)}</div>
                <div style={{ fontSize: 10, color: T.textMuted }}>Kosten</div>
              </div>
            </div>
            {budget.is_over_budget && (
              <div style={{ marginTop: 12, padding: 10, borderRadius: 8, background: T.dangerDim, display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: T.danger }}>
                <AlertTriangle size={14} /> Budget überschritten! Kontaktiere den Administrator.
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Current Config */}
      {config && (
        <Card style={{ padding: 20 }}>
          <SectionHeader title="Aktive KI-Konfiguration" subtitle="Dein aktueller Provider und Modell" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 16 }}>
            <div style={{ padding: 14, borderRadius: 10, border: `1px solid ${T.border}`, background: T.bg, textAlign: "center" }}>
              <Cpu size={20} color={T.accent} style={{ marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{config.provider_slug}</div>
              <div style={{ fontSize: 10, color: T.textMuted }}>Provider</div>
            </div>
            <div style={{ padding: 14, borderRadius: 10, border: `1px solid ${T.border}`, background: T.bg, textAlign: "center" }}>
              <Zap size={20} color={T.warning} style={{ marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{config.model}</div>
              <div style={{ fontSize: 10, color: T.textMuted }}>Modell</div>
            </div>
            <div style={{ padding: 14, borderRadius: 10, border: `1px solid ${T.border}`, background: T.bg, textAlign: "center" }}>
              <Key size={20} color={config.has_byok ? T.success : T.textDim} style={{ marginBottom: 8 }} />
              <div style={{ fontSize: 14, fontWeight: 700, color: config.has_byok ? T.success : T.textMuted }}>{config.has_byok ? "Eigener Key" : "Platform Key"}</div>
              <div style={{ fontSize: 10, color: T.textMuted }}>API-Schlüssel</div>
            </div>
          </div>
        </Card>
      )}

      {/* BYOK Section */}
      <Card style={{ padding: 20 }}>
        <SectionHeader title="Eigenen API-Key verwenden (BYOK)" subtitle="Bring Your Own Key für direkte Provider-Anbindung" />
        {success && <div style={{ marginTop: 12, padding: 10, borderRadius: 8, background: T.successDim, color: T.success, fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}><CheckCircle2 size={14} />{success}</div>}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 12, marginTop: 16, alignItems: "end" }}>
          <div>
            <label style={labelStyle}>Provider</label>
            <select style={inputStyle} value={byokProvider} onChange={(e) => setByokProvider(e.target.value)}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="gemini">Google Gemini</option>
              <option value="groq">Groq</option>
              <option value="mistral">Mistral</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>API Key</label>
            <div style={{ position: "relative" }}>
              <input style={inputStyle} type={showKey ? "text" : "password"} value={byokKey} onChange={(e) => setByokKey(e.target.value)} placeholder="sk-..." />
              <button onClick={() => setShowKey(!showKey)} style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}>
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <button onClick={handleSaveByok} disabled={saving || !byokKey.trim()} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600, opacity: saving || !byokKey.trim() ? 0.5 : 1, height: 37 }}>
            <Save size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />{saving ? "..." : "Speichern"}
          </button>
        </div>
      </Card>

      {/* Agent Overrides */}
      {agents.length > 0 && (
        <Card style={{ padding: 20 }}>
          <SectionHeader title="Agent-Konfiguration" subtitle="Aktiviere oder deaktiviere einzelne KI-Agenten" />
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 16 }}>
            {agents.map((a) => (
              <div key={a.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Bot size={16} color={a.is_enabled ? T.accent : T.textDim} />
                  <div>
                    <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{a.agent_name}</span>
                    <span style={{ fontSize: 10, color: T.textDim, marginLeft: 8 }}>{a.agent_slug}</span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {a.provider_slug_override && <span style={{ fontSize: 10, color: T.textMuted }}>Provider: {a.provider_slug_override}</span>}
                  {a.model_override && <span style={{ fontSize: 10, color: T.textMuted }}>Model: {a.model_override}</span>}
                  <button
                    onClick={() => handleToggleAgent(a.id, !a.is_enabled)}
                    style={{
                      padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer",
                      border: a.is_enabled ? `1px solid ${T.successDim}` : `1px solid ${T.dangerDim}`,
                      background: a.is_enabled ? T.successDim : T.dangerDim,
                      color: a.is_enabled ? T.success : T.danger,
                    }}
                  >
                    {a.is_enabled ? "Aktiv" : "Deaktiviert"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
