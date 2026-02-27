"use client";
import React, { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────────────────── */
interface UsageSummary {
  period_days: number;
  total_requests: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_cents: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  error_count: number;
  error_rate: number;
}

interface ModelUsage {
  provider_id: string;
  model_id: string;
  requests: number;
  tokens: number;
  cost_cents: number;
  cost_usd: number;
  avg_latency_ms: number;
}

interface TenantUsage {
  tenant_id: number;
  company_name: string;
  plan_name: string;
  requests: number;
  tokens: number;
  cost_cents: number;
  cost_usd: number;
  avg_latency_ms: number;
}

interface DailyUsage {
  date: string;
  requests: number;
  tokens: number;
  cost_cents: number;
  cost_usd: number;
}

interface ModelCost {
  id: number;
  provider_id: string;
  model_id: string;
  display_name: string | null;
  input_cost_per_million: number;
  output_cost_per_million: number;
  is_active: boolean;
}

interface RecentLog {
  id: number;
  tenant_id: number;
  user_id: string | null;
  agent_name: string | null;
  provider_id: string;
  model_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_cents: number;
  latency_ms: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

/* ── Provider Colors ────────────────────────────────────────────────────────── */
const PROVIDER_COLORS: Record<string, string> = {
  openai: "#10a37f",
  anthropic: "#d4a574",
  gemini: "#4285f4",
  mistral: "#ff7000",
  groq: "#f55036",
  xai: "#1da1f2",
};

const PROVIDER_NAMES: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  gemini: "Google Gemini",
  mistral: "Mistral AI",
  groq: "Groq",
  xai: "xAI (Grok)",
};

/* ── Helper ─────────────────────────────────────────────────────────────────── */
function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(cents: number): string {
  if (cents >= 100) return `$${(cents / 100).toFixed(2)}`;
  return `${cents.toFixed(2)}¢`;
}

/* ── Tabs ────────────────────────────────────────────────────────────────────── */
type Tab = "overview" | "models" | "tenants" | "pricing" | "logs";

export default function LLMCostsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  // Data states
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [modelUsage, setModelUsage] = useState<ModelUsage[]>([]);
  const [tenantUsage, setTenantUsage] = useState<TenantUsage[]>([]);
  const [dailyUsage, setDailyUsage] = useState<DailyUsage[]>([]);
  const [modelCosts, setModelCosts] = useState<ModelCost[]>([]);
  const [recentLogs, setRecentLogs] = useState<RecentLog[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryRes, modelRes, tenantRes, dailyRes, costsRes, logsRes] =
        await Promise.all([
          apiFetch(`/admin/llm/usage-summary?days=${days}`),
          apiFetch(`/admin/llm/usage-by-model?days=${days}`),
          apiFetch(`/admin/llm/usage-by-tenant?days=${days}`),
          apiFetch(`/admin/llm/usage-daily?days=${days}`),
          apiFetch(`/admin/llm/model-costs`),
          apiFetch(`/admin/llm/recent-logs?limit=100`),
        ]);
      if (summaryRes.ok) setSummary(await summaryRes.json());
      if (modelRes.ok) setModelUsage(await modelRes.json());
      if (tenantRes.ok) setTenantUsage(await tenantRes.json());
      if (dailyRes.ok) setDailyUsage(await dailyRes.json());
      if (costsRes.ok) setModelCosts(await costsRes.json());
      if (logsRes.ok) setRecentLogs(await logsRes.json());
    } catch (e) {
      console.error("Failed to fetch LLM data:", e);
    }
    setLoading(false);
  }, [days]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Übersicht" },
    { id: "models", label: "Modelle" },
    { id: "tenants", label: "Tenants" },
    { id: "pricing", label: "Preiskonfiguration" },
    { id: "logs", label: "Request Log" },
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            LLM Kosten & Nutzung
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Echtzeit-Kostenerfassung und Token-Tracking aller KI-Modelle
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-800 dark:border-gray-600"
          >
            <option value={7}>Letzte 7 Tage</option>
            <option value={30}>Letzte 30 Tage</option>
            <option value={90}>Letzte 90 Tage</option>
            <option value={365}>Letztes Jahr</option>
          </select>
          <button
            onClick={fetchData}
            className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
          >
            Aktualisieren
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <>
          {activeTab === "overview" && (
            <OverviewTab
              summary={summary}
              dailyUsage={dailyUsage}
              modelUsage={modelUsage}
            />
          )}
          {activeTab === "models" && <ModelsTab modelUsage={modelUsage} />}
          {activeTab === "tenants" && <TenantsTab tenantUsage={tenantUsage} />}
          {activeTab === "pricing" && (
            <PricingTab modelCosts={modelCosts} onRefresh={fetchData} />
          )}
          {activeTab === "logs" && <LogsTab logs={recentLogs} />}
        </>
      )}
    </div>
  );
}

/* ── Overview Tab ───────────────────────────────────────────────────────────── */
function OverviewTab({
  summary,
  dailyUsage,
  modelUsage,
}: {
  summary: UsageSummary | null;
  dailyUsage: DailyUsage[];
  modelUsage: ModelUsage[];
}) {
  if (!summary) return <p className="text-gray-500">Keine Daten verfügbar.</p>;

  const maxDailyCost = Math.max(...dailyUsage.map((d) => d.cost_cents), 1);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Gesamtkosten"
          value={formatCost(summary.total_cost_cents)}
          sub={`${summary.period_days} Tage`}
          color="blue"
        />
        <KPICard
          label="Anfragen"
          value={summary.total_requests.toLocaleString()}
          sub={`Ø ${summary.avg_latency_ms}ms Latenz`}
          color="green"
        />
        <KPICard
          label="Token verbraucht"
          value={formatTokens(summary.total_tokens)}
          sub={`${formatTokens(summary.total_prompt_tokens)} In / ${formatTokens(summary.total_completion_tokens)} Out`}
          color="purple"
        />
        <KPICard
          label="Fehlerrate"
          value={`${summary.error_rate}%`}
          sub={`${summary.error_count} Fehler`}
          color={summary.error_rate > 5 ? "red" : "green"}
        />
      </div>

      {/* Daily Cost Chart (simple bar chart) */}
      {dailyUsage.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Tägliche Kosten
          </h3>
          <div className="flex items-end gap-1 h-40">
            {dailyUsage.map((d, i) => (
              <div
                key={i}
                className="flex-1 group relative"
                title={`${d.date}: ${formatCost(d.cost_cents)} (${d.requests} Anfragen)`}
              >
                <div
                  className="bg-blue-500 hover:bg-blue-600 rounded-t transition-colors w-full"
                  style={{
                    height: `${Math.max((d.cost_cents / maxDailyCost) * 100, 2)}%`,
                  }}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-2">
            <span>{dailyUsage[0]?.date}</span>
            <span>{dailyUsage[dailyUsage.length - 1]?.date}</span>
          </div>
        </div>
      )}

      {/* Top Models */}
      {modelUsage.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
            Top Modelle nach Kosten
          </h3>
          <div className="space-y-3">
            {modelUsage.slice(0, 5).map((m, i) => {
              const maxCost = modelUsage[0]?.cost_cents || 1;
              const pct = (m.cost_cents / maxCost) * 100;
              return (
                <div key={i} className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor:
                        PROVIDER_COLORS[m.provider_id] || "#6b7280",
                    }}
                  />
                  <span className="text-sm font-medium w-48 truncate">
                    {m.model_id}
                  </span>
                  <div className="flex-1 bg-gray-100 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        backgroundColor:
                          PROVIDER_COLORS[m.provider_id] || "#6b7280",
                      }}
                    />
                  </div>
                  <span className="text-sm font-mono w-20 text-right">
                    {formatCost(m.cost_cents)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── KPI Card ───────────────────────────────────────────────────────────────── */
function KPICard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string;
  sub: string;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    blue: "bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800",
    green:
      "bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800",
    purple:
      "bg-purple-50 border-purple-200 dark:bg-purple-900/20 dark:border-purple-800",
    red: "bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800",
  };
  return (
    <div className={`rounded-xl border p-4 ${colorClasses[color] || colorClasses.blue}`}>
      <p className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-2xl font-bold mt-1 text-gray-900 dark:text-white">
        {value}
      </p>
      <p className="text-xs text-gray-500 mt-1">{sub}</p>
    </div>
  );
}

/* ── Models Tab ─────────────────────────────────────────────────────────────── */
function ModelsTab({ modelUsage }: { modelUsage: ModelUsage[] }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Provider
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Modell
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Anfragen
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Token
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Kosten
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Ø Latenz
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
          {modelUsage.map((m, i) => (
            <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
              <td className="px-4 py-3">
                <span
                  className="inline-flex items-center gap-2 px-2 py-1 rounded-full text-xs font-medium text-white"
                  style={{
                    backgroundColor:
                      PROVIDER_COLORS[m.provider_id] || "#6b7280",
                  }}
                >
                  {PROVIDER_NAMES[m.provider_id] || m.provider_id}
                </span>
              </td>
              <td className="px-4 py-3 font-mono text-xs">{m.model_id}</td>
              <td className="px-4 py-3 text-right">
                {m.requests.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right font-mono">
                {formatTokens(m.tokens)}
              </td>
              <td className="px-4 py-3 text-right font-mono font-semibold">
                {formatCost(m.cost_cents)}
              </td>
              <td className="px-4 py-3 text-right text-gray-500">
                {m.avg_latency_ms}ms
              </td>
            </tr>
          ))}
          {modelUsage.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                Noch keine Nutzungsdaten vorhanden.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ── Tenants Tab ────────────────────────────────────────────────────────────── */
function TenantsTab({ tenantUsage }: { tenantUsage: TenantUsage[] }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-700/50">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Tenant
            </th>
            <th className="text-left px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Plan
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Anfragen
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Token
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Kosten
            </th>
            <th className="text-right px-4 py-3 font-medium text-gray-600 dark:text-gray-300">
              Ø Latenz
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
          {tenantUsage.map((t, i) => (
            <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
              <td className="px-4 py-3 font-medium">{t.company_name}</td>
              <td className="px-4 py-3">
                <span className="px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded text-xs">
                  {t.plan_name}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                {t.requests.toLocaleString()}
              </td>
              <td className="px-4 py-3 text-right font-mono">
                {formatTokens(t.tokens)}
              </td>
              <td className="px-4 py-3 text-right font-mono font-semibold">
                {formatCost(t.cost_cents)}
              </td>
              <td className="px-4 py-3 text-right text-gray-500">
                {t.avg_latency_ms}ms
              </td>
            </tr>
          ))}
          {tenantUsage.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                Noch keine Nutzungsdaten vorhanden.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ── Pricing Tab ────────────────────────────────────────────────────────────── */
function PricingTab({
  modelCosts,
  onRefresh,
}: {
  modelCosts: ModelCost[];
  onRefresh: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editInput, setEditInput] = useState(0);
  const [editOutput, setEditOutput] = useState(0);

  const grouped = modelCosts.reduce(
    (acc, c) => {
      if (!acc[c.provider_id]) acc[c.provider_id] = [];
      acc[c.provider_id].push(c);
      return acc;
    },
    {} as Record<string, ModelCost[]>
  );

  const handleSave = async (cost: ModelCost) => {
    await apiFetch("/admin/llm/model-costs", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider_id: cost.provider_id,
        model_id: cost.model_id,
        display_name: cost.display_name,
        input_cost_per_million: editInput,
        output_cost_per_million: editOutput,
        is_active: cost.is_active,
      }),
    });
    setEditingId(null);
    onRefresh();
  };

  return (
    <div className="space-y-6">
      <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
        <p className="text-sm text-amber-800 dark:text-amber-200">
          <strong>Hinweis:</strong> Preise sind in USD-Cent pro 1 Million Token.
          Änderungen wirken sich sofort auf die Kostenberechnung neuer Anfragen
          aus.
        </p>
      </div>

      {Object.entries(grouped).map(([provider, costs]) => (
        <div
          key={provider}
          className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden"
        >
          <div
            className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2"
            style={{
              borderLeftWidth: 4,
              borderLeftColor: PROVIDER_COLORS[provider] || "#6b7280",
            }}
          >
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {PROVIDER_NAMES[provider] || provider}
            </h3>
            <span className="text-xs text-gray-400">
              ({costs.length} Modelle)
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700/50">
              <tr>
                <th className="text-left px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                  Modell
                </th>
                <th className="text-right px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                  Input / 1M Token
                </th>
                <th className="text-right px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                  Output / 1M Token
                </th>
                <th className="text-center px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                  Status
                </th>
                <th className="text-right px-4 py-2 font-medium text-gray-600 dark:text-gray-300">
                  Aktion
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {costs.map((c) => (
                <tr
                  key={c.model_id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/30"
                >
                  <td className="px-4 py-2">
                    <div>
                      <span className="font-mono text-xs">{c.model_id}</span>
                      {c.display_name && (
                        <span className="text-xs text-gray-400 ml-2">
                          ({c.display_name})
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {editingId === c.model_id ? (
                      <input
                        type="number"
                        value={editInput}
                        onChange={(e) => setEditInput(Number(e.target.value))}
                        className="w-20 px-2 py-1 border rounded text-right text-xs"
                      />
                    ) : (
                      `${c.input_cost_per_million}¢`
                    )}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {editingId === c.model_id ? (
                      <input
                        type="number"
                        value={editOutput}
                        onChange={(e) => setEditOutput(Number(e.target.value))}
                        className="w-20 px-2 py-1 border rounded text-right text-xs"
                      />
                    ) : (
                      `${c.output_cost_per_million}¢`
                    )}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        c.is_active
                          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {c.is_active ? "Aktiv" : "Inaktiv"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    {editingId === c.model_id ? (
                      <div className="flex gap-1 justify-end">
                        <button
                          onClick={() => handleSave(c)}
                          className="px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700"
                        >
                          Speichern
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-2 py-1 bg-gray-200 text-gray-700 rounded text-xs hover:bg-gray-300"
                        >
                          Abbrechen
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => {
                          setEditingId(c.model_id);
                          setEditInput(c.input_cost_per_million);
                          setEditOutput(c.output_cost_per_million);
                        }}
                        className="px-2 py-1 text-blue-600 hover:bg-blue-50 rounded text-xs"
                      >
                        Bearbeiten
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}

/* ── Logs Tab ───────────────────────────────────────────────────────────────── */
function LogsTab({ logs }: { logs: RecentLog[] }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 dark:bg-gray-700/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Zeit
              </th>
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Tenant
              </th>
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Agent
              </th>
              <th className="text-left px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Modell
              </th>
              <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                In
              </th>
              <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Out
              </th>
              <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Kosten
              </th>
              <th className="text-right px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Latenz
              </th>
              <th className="text-center px-3 py-2 font-medium text-gray-600 dark:text-gray-300">
                Status
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
            {logs.map((l) => (
              <tr
                key={l.id}
                className={`hover:bg-gray-50 dark:hover:bg-gray-700/30 ${
                  !l.success ? "bg-red-50 dark:bg-red-900/10" : ""
                }`}
              >
                <td className="px-3 py-2 text-gray-500 whitespace-nowrap">
                  {l.created_at
                    ? new Date(l.created_at).toLocaleString("de-DE", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                      })
                    : "-"}
                </td>
                <td className="px-3 py-2">{l.tenant_id}</td>
                <td className="px-3 py-2 text-gray-500">
                  {l.agent_name || "-"}
                </td>
                <td className="px-3 py-2">
                  <span
                    className="inline-block w-2 h-2 rounded-full mr-1"
                    style={{
                      backgroundColor:
                        PROVIDER_COLORS[l.provider_id] || "#6b7280",
                    }}
                  />
                  {l.model_id}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {l.prompt_tokens.toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right font-mono">
                  {l.completion_tokens.toLocaleString()}
                </td>
                <td className="px-3 py-2 text-right font-mono font-semibold">
                  {formatCost(l.total_cost_cents)}
                </td>
                <td className="px-3 py-2 text-right text-gray-500">
                  {l.latency_ms}ms
                </td>
                <td className="px-3 py-2 text-center">
                  {l.success ? (
                    <span className="text-green-500">✓</span>
                  ) : (
                    <span
                      className="text-red-500 cursor-help"
                      title={l.error_message || "Fehler"}
                    >
                      ✗
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {logs.length === 0 && (
              <tr>
                <td
                  colSpan={9}
                  className="px-4 py-8 text-center text-gray-400"
                >
                  Noch keine Log-Einträge vorhanden.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
