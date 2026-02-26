"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Cpu, Plus, Trash2, Star, AlertCircle, CheckCircle2,
  Lock, Zap, ShoppingCart, X, Package, ArrowUpRight,
  RefreshCcw, Sparkles,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ProgressBar } from "@/components/ui/ProgressBar";

type ProviderInfo = {
  id: string;
  name: string;
  models: string[];
  tier: string;
  available: boolean;
  reason: string | null;
  locked_by_plan?: boolean;
};

type LLMConfig = {
  id: number;
  provider_id: string;
  provider_name: string;
  model_id: string;
  is_default: boolean;
  created_at: string | null;
};

type TokenUsage = {
  tokens_used: number;
  tokens_plan_limit: number;
  tokens_purchased: number;
  tokens_total_available: number;
  tokens_remaining: number;
  usage_pct: number;
  is_exhausted: boolean;
  is_unlimited: boolean;
  plan_name: string;
  plan_slug: string;
  token_price_per_1k_cents: number;
};

type TokenPackage = {
  id: string;
  name: string;
  tokens: number;
  price_cents: number;
  price_formatted: string;
  popular: boolean;
};

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("de-DE");
}

const PROVIDER_ICONS: Record<string, string> = {
  openai: "🤖",
  anthropic: "🧠",
  mistral: "🌊",
  groq: "⚡",
  gemini: "💎",
};

export function TenantLLMManager() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [configs, setConfigs] = useState<LLMConfig[]>([]);
  const [tokenUsage, setTokenUsage] = useState<TokenUsage | null>(null);
  const [packages, setPackages] = useState<TokenPackage[]>([]);
  const [planInfo, setPlanInfo] = useState<{ plan_name: string; ai_tier: string; monthly_tokens: number }>({ plan_name: "", ai_tier: "basic", monthly_tokens: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showPurchase, setShowPurchase] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [provRes, confRes, usageRes, pkgRes] = await Promise.all([
        apiFetch("/admin/tenant/llm/providers/available"),
        apiFetch("/admin/tenant/llm/configs"),
        apiFetch("/admin/tenant/llm/token-usage"),
        apiFetch("/admin/tenant/llm/token-packages"),
      ]);

      if (provRes.ok) {
        const data = await provRes.json();
        setProviders(data.providers || []);
        setPlanInfo({ plan_name: data.plan_name, ai_tier: data.ai_tier, monthly_tokens: data.monthly_tokens });
      }
      if (confRes.ok) setConfigs(await confRes.json());
      if (usageRes.ok) setTokenUsage(await usageRes.json());
      if (pkgRes.ok) setPackages(await pkgRes.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function handleAddConfig() {
    if (!selectedProvider || !selectedModel) return;
    setSaving(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/tenant/llm/configs", {
        method: "POST",
        body: JSON.stringify({ provider_id: selectedProvider, model_id: selectedModel }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Fehler beim Speichern");
      }
      setShowAddForm(false);
      setSelectedProvider("");
      setSelectedModel("");
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(configId: number) {
    if (!confirm("Möchten Sie diese Konfiguration wirklich entfernen?")) return;
    try {
      const res = await apiFetch(`/admin/tenant/llm/configs/${configId}`, { method: "DELETE" });
      if (res.ok) await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handleSetDefault(configId: number) {
    try {
      const res = await apiFetch(`/admin/tenant/llm/configs/${configId}/default`, { method: "POST" });
      if (res.ok) await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  async function handlePurchase(packageId: string) {
    setPurchasing(true);
    setError(null);
    try {
      const res = await apiFetch("/admin/tenant/llm/token-purchase", {
        method: "POST",
        body: JSON.stringify({ package_id: packageId }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Kaufvorgang fehlgeschlagen");
      }
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setShowPurchase(false);
        await load();
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPurchasing(false);
    }
  }

  const availableModels = providers.find(p => p.id === selectedProvider)?.models || [];
  const usagePct = tokenUsage?.usage_pct || 0;
  const barColor = usagePct > 90 ? T.danger : usagePct > 70 ? T.warning : T.accent;

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: T.textDim, fontSize: 13 }}>
        <RefreshCcw size={18} style={{ marginRight: 8, animation: "spin 1s linear infinite" }} />
        Lade AI-Konfiguration…
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {error && (
        <div style={{
          padding: "12px 16px", borderRadius: 12,
          background: `${T.danger}10`, border: `1px solid ${T.danger}30`,
          display: "flex", alignItems: "center", gap: 10,
          color: T.danger, fontSize: 13,
        }}>
          <AlertCircle size={16} /> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", cursor: "pointer", background: "none", border: "none", color: T.danger }}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* Token Exhaustion Warning */}
      {tokenUsage?.is_exhausted && !tokenUsage?.is_unlimited && (
        <div style={{
          padding: "16px 20px", borderRadius: 14,
          background: `${T.danger}10`, border: `1px solid ${T.danger}40`,
          display: "flex", alignItems: "center", gap: 14,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 10,
            background: `${T.danger}20`, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <AlertCircle size={20} color={T.danger} />
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 14, fontWeight: 700, color: T.danger, margin: 0 }}>
              Token-Kontingent aufgebraucht
            </p>
            <p style={{ fontSize: 12, color: T.textMuted, margin: "4px 0 0" }}>
              Ihre AI-Kommunikation ist pausiert. Kaufen Sie zusätzliche Tokens oder upgraden Sie Ihren Plan.
            </p>
          </div>
          <button
            onClick={() => setShowPurchase(true)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "10px 18px", borderRadius: 10,
              background: T.danger, color: "#fff",
              border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer",
            }}
          >
            <ShoppingCart size={14} /> Tokens kaufen
          </button>
        </div>
      )}

      {/* Token Usage Card */}
      {tokenUsage && (
        <Card style={{ padding: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
            <SectionHeader
              title="Token-Verbrauch"
              subtitle={`${planInfo.plan_name} Plan · ${tokenUsage.is_unlimited ? "Unbegrenzt" : `${formatNumber(tokenUsage.tokens_total_available)} Tokens verfügbar`}`}
            />
            <button
              onClick={() => setShowPurchase(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 14px", borderRadius: 10,
                background: T.accentDim, color: T.accentLight,
                border: `1px solid ${T.accent}33`, fontSize: 12, fontWeight: 600,
                cursor: "pointer",
              }}
            >
              <ShoppingCart size={14} /> Mehr Tokens
            </button>
          </div>

          {tokenUsage.is_unlimited ? (
            <div style={{
              display: "flex", alignItems: "center", gap: 12, padding: "16px 20px",
              borderRadius: 12, background: `${T.success}10`, border: `1px solid ${T.success}30`,
            }}>
              <Sparkles size={20} color={T.success} />
              <div>
                <p style={{ fontSize: 14, fontWeight: 700, color: T.success, margin: 0 }}>Unbegrenztes Token-Kontingent</p>
                <p style={{ fontSize: 12, color: T.textMuted, margin: "2px 0 0" }}>
                  Ihr Enterprise-Plan beinhaltet unbegrenzte AI-Tokens.
                </p>
              </div>
            </div>
          ) : (
            <>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: T.textMuted }}>
                  {formatNumber(tokenUsage.tokens_used)} verwendet
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: T.textDim }}>
                  {formatNumber(tokenUsage.tokens_remaining)} verbleibend
                </span>
              </div>
              <div style={{ width: "100%", height: 10, borderRadius: 5, background: T.surfaceAlt, overflow: "hidden", marginBottom: 12 }}>
                <div style={{
                  width: `${Math.min(usagePct, 100)}%`, height: "100%", borderRadius: 5,
                  background: barColor,
                  transition: "width 0.8s cubic-bezier(0.4,0,0.2,1)",
                }} />
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div style={{ textAlign: "center", padding: "12px 0" }}>
                  <p style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>Plan-Limit</p>
                  <p style={{ fontSize: 18, fontWeight: 800, color: T.text, margin: 0 }}>{formatNumber(tokenUsage.tokens_plan_limit)}</p>
                </div>
                <div style={{ textAlign: "center", padding: "12px 0" }}>
                  <p style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>Gekauft</p>
                  <p style={{ fontSize: 18, fontWeight: 800, color: T.warning, margin: 0 }}>{formatNumber(tokenUsage.tokens_purchased)}</p>
                </div>
                <div style={{ textAlign: "center", padding: "12px 0" }}>
                  <p style={{ fontSize: 10, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 4px" }}>Verbrauch</p>
                  <p style={{ fontSize: 18, fontWeight: 800, color: barColor, margin: 0 }}>{usagePct.toFixed(1)}%</p>
                </div>
              </div>
            </>
          )}
        </Card>
      )}

      {/* Active LLM Configurations */}
      <Card style={{ padding: 24 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <SectionHeader
            title="AI-Modelle"
            subtitle="Konfigurierte LLM-Provider und Modelle für Ihre Organisation"
          />
          <button
            onClick={() => setShowAddForm(true)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "8px 14px", borderRadius: 10,
              background: T.accent, color: "#fff",
              border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer",
            }}
          >
            <Plus size={14} /> Modell hinzufügen
          </button>
        </div>

        {configs.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {configs.map(cfg => (
              <div key={cfg.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "14px 18px", borderRadius: 12,
                background: T.surfaceAlt, border: `1px solid ${cfg.is_default ? `${T.accent}40` : T.border}`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <div style={{
                    width: 42, height: 42, borderRadius: 12,
                    background: cfg.is_default ? T.accentDim : `${T.textDim}15`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 20,
                  }}>
                    {PROVIDER_ICONS[cfg.provider_id] || "🤖"}
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{cfg.provider_name}</span>
                      {cfg.is_default && <Badge variant="accent" size="xs">Standard</Badge>}
                    </div>
                    <span style={{ fontSize: 12, color: T.textMuted, fontFamily: "monospace" }}>{cfg.model_id}</span>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {!cfg.is_default && (
                    <button
                      onClick={() => handleSetDefault(cfg.id)}
                      title="Als Standard setzen"
                      style={{
                        padding: "6px 10px", borderRadius: 8,
                        background: "transparent", border: `1px solid ${T.border}`,
                        color: T.textMuted, cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                        fontSize: 11, fontWeight: 600,
                      }}
                    >
                      <Star size={12} /> Standard
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(cfg.id)}
                    title="Entfernen"
                    style={{
                      padding: 8, borderRadius: 8,
                      background: "transparent", border: `1px solid ${T.border}`,
                      color: T.textMuted, cursor: "pointer",
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{
            padding: 40, textAlign: "center", borderRadius: 12,
            background: T.surfaceAlt, border: `1px dashed ${T.border}`,
          }}>
            <Cpu size={32} style={{ color: T.textDim, marginBottom: 12 }} />
            <p style={{ fontSize: 14, fontWeight: 600, color: T.textMuted, margin: "0 0 4px" }}>
              Noch keine AI-Modelle konfiguriert
            </p>
            <p style={{ fontSize: 12, color: T.textDim, margin: 0 }}>
              Fügen Sie ein LLM-Modell hinzu, um die AI-Kommunikation zu aktivieren.
            </p>
          </div>
        )}
      </Card>

      {/* Add Model Form */}
      {showAddForm && (
        <Card style={{ padding: 24, border: `1px solid ${T.accent}40` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <Plus size={18} color={T.accent} /> Neues AI-Modell hinzufügen
            </h3>
            <button onClick={() => { setShowAddForm(false); setSelectedProvider(""); setSelectedModel(""); }} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}>
              <X size={18} />
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Provider Selection */}
            <div>
              <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Provider wählen
              </label>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {providers.map(p => {
                  const isSelected = selectedProvider === p.id;
                  const isLocked = p.locked_by_plan;
                  const isUnavailable = !p.available && !isLocked;
                  return (
                    <button
                      key={p.id}
                      onClick={() => {
                        if (isLocked || isUnavailable) return;
                        setSelectedProvider(p.id);
                        setSelectedModel("");
                      }}
                      disabled={isLocked || isUnavailable}
                      style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "12px 16px", borderRadius: 10,
                        background: isSelected ? T.accentDim : T.surfaceAlt,
                        border: `1px solid ${isSelected ? `${T.accent}60` : isLocked ? `${T.warning}30` : T.border}`,
                        cursor: isLocked || isUnavailable ? "not-allowed" : "pointer",
                        opacity: isLocked || isUnavailable ? 0.5 : 1,
                        textAlign: "left",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{ fontSize: 20 }}>{PROVIDER_ICONS[p.id] || "🤖"}</span>
                        <div>
                          <span style={{ fontSize: 13, fontWeight: 700, color: T.text, display: "block" }}>{p.name}</span>
                          <span style={{ fontSize: 10, color: T.textDim }}>
                            {p.models.length} Modelle · {p.tier}
                          </span>
                        </div>
                      </div>
                      {isLocked && <Lock size={14} color={T.warning} />}
                      {isUnavailable && <AlertCircle size={14} color={T.textDim} />}
                      {isSelected && <CheckCircle2 size={16} color={T.accent} />}
                    </button>
                  );
                })}
              </div>
              {providers.some(p => p.locked_by_plan) && (
                <p style={{ fontSize: 10, color: T.warning, marginTop: 8, display: "flex", alignItems: "center", gap: 4 }}>
                  <Lock size={10} /> Einige Provider erfordern einen höheren Plan
                </p>
              )}
            </div>

            {/* Model Selection */}
            <div>
              <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Modell wählen
              </label>
              {selectedProvider ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {availableModels.map(m => {
                    const isSelected = selectedModel === m;
                    const alreadyConfigured = configs.some(c => c.provider_id === selectedProvider && c.model_id === m);
                    return (
                      <button
                        key={m}
                        onClick={() => !alreadyConfigured && setSelectedModel(m)}
                        disabled={alreadyConfigured}
                        style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between",
                          padding: "10px 14px", borderRadius: 8,
                          background: isSelected ? T.accentDim : T.surfaceAlt,
                          border: `1px solid ${isSelected ? `${T.accent}60` : alreadyConfigured ? `${T.success}30` : T.border}`,
                          cursor: alreadyConfigured ? "default" : "pointer",
                          opacity: alreadyConfigured ? 0.6 : 1,
                          textAlign: "left",
                        }}
                      >
                        <span style={{ fontSize: 12, fontWeight: 600, color: T.text, fontFamily: "monospace" }}>{m}</span>
                        {alreadyConfigured && <Badge variant="success" size="xs">Aktiv</Badge>}
                        {isSelected && !alreadyConfigured && <CheckCircle2 size={14} color={T.accent} />}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div style={{
                  padding: 40, textAlign: "center", borderRadius: 10,
                  background: T.surfaceAlt, border: `1px dashed ${T.border}`,
                }}>
                  <p style={{ fontSize: 12, color: T.textDim, margin: 0 }}>
                    Wählen Sie zuerst einen Provider
                  </p>
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 20, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            <button
              onClick={() => { setShowAddForm(false); setSelectedProvider(""); setSelectedModel(""); }}
              style={{
                padding: "8px 16px", borderRadius: 8,
                background: T.surfaceAlt, color: T.textMuted,
                border: `1px solid ${T.border}`, fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}
            >
              Abbrechen
            </button>
            <button
              onClick={handleAddConfig}
              disabled={!selectedProvider || !selectedModel || saving}
              style={{
                padding: "8px 20px", borderRadius: 8,
                background: T.accent, color: "#fff",
                border: "none", fontSize: 12, fontWeight: 700, cursor: "pointer",
                opacity: !selectedProvider || !selectedModel || saving ? 0.5 : 1,
              }}
            >
              {saving ? "Speichern…" : "Modell hinzufügen"}
            </button>
          </div>
        </Card>
      )}

      {/* Token Purchase Modal */}
      {showPurchase && (
        <Card style={{ padding: 24, border: `1px solid ${T.warning}40` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
              <ShoppingCart size={18} color={T.warning} /> Token-Pakete
            </h3>
            <button onClick={() => setShowPurchase(false)} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}>
              <X size={18} />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {packages.map(pkg => (
              <div key={pkg.id} style={{
                padding: "20px", borderRadius: 14,
                background: pkg.popular ? T.accentDim : T.surfaceAlt,
                border: `1px solid ${pkg.popular ? `${T.accent}50` : T.border}`,
                position: "relative",
              }}>
                {pkg.popular && (
                  <div style={{
                    position: "absolute", top: -8, right: 12,
                    padding: "2px 10px", borderRadius: 6,
                    background: T.accent, color: "#fff",
                    fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.08em",
                  }}>
                    Beliebt
                  </div>
                )}
                <p style={{ fontSize: 16, fontWeight: 800, color: T.text, margin: "0 0 4px" }}>{pkg.name}</p>
                <p style={{ fontSize: 11, color: T.textMuted, margin: "0 0 16px" }}>
                  {formatNumber(pkg.tokens)} Tokens
                </p>
                <p style={{ fontSize: 24, fontWeight: 800, color: T.accent, margin: "0 0 16px", letterSpacing: "-0.03em" }}>
                  €{pkg.price_formatted}
                </p>
                <button
                  onClick={() => handlePurchase(pkg.id)}
                  disabled={purchasing}
                  style={{
                    width: "100%", padding: "10px 0", borderRadius: 8,
                    background: pkg.popular ? T.accent : T.surfaceAlt,
                    color: pkg.popular ? "#fff" : T.text,
                    border: pkg.popular ? "none" : `1px solid ${T.border}`,
                    fontSize: 12, fontWeight: 700, cursor: "pointer",
                    opacity: purchasing ? 0.5 : 1,
                  }}
                >
                  {purchasing ? "Wird verarbeitet…" : "Jetzt kaufen"}
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Available Providers Overview */}
      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Verfügbare Provider"
          subtitle={`Ihr ${planInfo.plan_name}-Plan (${planInfo.ai_tier} Tier) bietet Zugang zu folgenden Providern`}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {providers.map(p => {
            const isLocked = p.locked_by_plan;
            const isAvailable = p.available;
            const configCount = configs.filter(c => c.provider_id === p.id).length;
            return (
              <div key={p.id} style={{
                padding: "16px", borderRadius: 12,
                background: T.surfaceAlt,
                border: `1px solid ${isLocked ? `${T.warning}20` : isAvailable ? `${T.success}20` : T.border}`,
                opacity: isLocked ? 0.6 : 1,
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 20 }}>{PROVIDER_ICONS[p.id] || "🤖"}</span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{p.name}</span>
                  </div>
                  {isLocked ? (
                    <Badge variant="warning" size="xs"><Lock size={8} /> Upgrade</Badge>
                  ) : isAvailable ? (
                    <Badge variant="success" size="xs"><CheckCircle2 size={8} /> Verfügbar</Badge>
                  ) : (
                    <Badge variant="default" size="xs">Nicht konfiguriert</Badge>
                  )}
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                  {p.models.slice(0, 3).map(m => (
                    <span key={m} style={{
                      padding: "2px 6px", borderRadius: 4,
                      background: T.bg, fontSize: 9, fontWeight: 600,
                      color: T.textDim, fontFamily: "monospace",
                    }}>{m}</span>
                  ))}
                  {p.models.length > 3 && (
                    <span style={{ fontSize: 9, color: T.textDim, padding: "2px 4px" }}>
                      +{p.models.length - 3} mehr
                    </span>
                  )}
                </div>
                {configCount > 0 && (
                  <p style={{ fontSize: 10, color: T.success, marginTop: 8, fontWeight: 600 }}>
                    {configCount} Modell{configCount > 1 ? "e" : ""} aktiv
                  </p>
                )}
                {isLocked && p.reason && (
                  <p style={{ fontSize: 10, color: T.warning, marginTop: 8 }}>{p.reason}</p>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
