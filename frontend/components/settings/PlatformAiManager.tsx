"use client";

import React, { useState, useEffect, useMemo } from "react";
import { 
  Cpu, 
  Plus, 
  Trash2, 
  RefreshCcw, 
  ShieldCheck, 
  AlertCircle, 
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Search,
  KeyRound,
  Zap,
  Check,
  X,
  Edit3
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useI18n } from "@/lib/i18n/LanguageContext";

type Provider = {
  id: string;
  name: string;
  base_url: string;
  type: string;
};

type ConfiguredProvider = {
  id: string;
  name: string;
  base_url: string;
  models: string[];
  enabled: boolean;
};

export function PlatformAiManager() {
  const { t } = useI18n();
  const [availableProviders, setAvailableProviders] = useState<Provider[]>([]);
  const [configuredProviders, setConfiguredProviders] = useState<ConfiguredProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: "ok" | "error", latency?: number, detail?: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // UI State
  const [showForm, setShowAdd] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [modelSearch, setModelSearch] = useState("");
  
  // Form State
  const [newProviderId, setNewProviderId] = useState("");
  const [newKey, setNewKey] = useState("");
  const [tempModels, setTempModels] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);

  async function load() {
    setLoading(true);
    try {
      const [availRes, configRes] = await Promise.all([
        apiFetch("/admin/platform/llm/providers/available"),
        apiFetch("/admin/settings")
      ]);
      
      if (availRes.ok) setAvailableProviders(await availRes.json());
      if (configRes.ok) {
        const settings = await configRes.json();
        const providersJson = settings.find((s: any) => s.key === "platform_llm_providers_json")?.value;
        if (providersJson && providersJson !== "__REDACTED__" && providersJson !== "[]") {
          setConfiguredProviders(JSON.parse(providersJson));
        } else {
          setConfiguredProviders([]);
        }
      }
    } catch (e) {
      setError(t("settings.ai.errors.loadFailed") || "Failed to load AI config");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  // AUTO-FETCH LOGIC
  useEffect(() => {
    if (showForm && newProviderId && (newKey === "__REDACTED__" || (newKey.length > 5 && !fetchingModels))) {
      const timer = setTimeout(() => {
        handleFetchModels();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [showForm, newProviderId, newKey === "__REDACTED__"]);

  async function handleFetchModels() {
    if (!newProviderId) return;
    setFetchingModels(true);
    setError(null);
    setTestResult(null);
    
    try {
      const useStored = isEditing && (!newKey || newKey === "__REDACTED__");
      const endpoint = useStored 
        ? "/admin/platform/llm/fetch-models-stored" 
        : "/admin/platform/llm/fetch-models";
        
      const res = await apiFetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(useStored ? { provider_id: newProviderId } : { provider_id: newProviderId, api_key: newKey })
      });
      
      if (!res.ok) {
        const data = await res.json();
        const msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        throw new Error(msg || t("settings.ai.errors.fetchModelsFailed"));
      }
      const models = await res.json();
      setTempModels(models);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setFetchingModels(false);
    }
  }

  async function handleTestConnection() {
    if (!newProviderId || !newKey || selectedModels.length === 0) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch("/admin/platform/llm/test-connection", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          provider_id: newProviderId, 
          api_key: newKey, 
          model: selectedModels[0] 
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        setTestResult({ status: "ok", latency: data.latency_ms });
      } else {
        setTestResult({ status: "error", detail: data.detail });
      }
    } catch (e: any) {
      setTestResult({ status: "error", detail: e.message });
    } finally {
      setTesting(false);
    }
  }

  async function handleSaveProvider() {
    const provider = availableProviders.find(p => p.id === newProviderId);
    if (!provider || selectedModels.length === 0) return;

    const newEntry: ConfiguredProvider = {
      id: provider.id,
      name: provider.name,
      base_url: provider.base_url,
      models: selectedModels,
      enabled: true
    };

    const newList = configuredProviders.some(p => p.id === provider.id)
      ? configuredProviders.map(p => p.id === provider.id ? newEntry : p)
      : [...configuredProviders, newEntry];

    const settingsUpdate = [
      { key: "platform_llm_providers_json", value: JSON.stringify(newList) }
    ];

    if (newKey && newKey !== "__REDACTED__") {
      settingsUpdate.push({ key: `platform_llm_key_${newProviderId}`, value: newKey });
    }

    try {
      const res = await apiFetch("/admin/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settingsUpdate)
      });
      
      if (res.ok) {
        setConfiguredProviders(newList);
        setShowAdd(false);
        setIsEditing(false);
        resetForm();
      } else {
        setError(t("settings.ai.errors.saveFailed") || "Save failed");
      }
    } catch (e) {
      setError(t("settings.ai.errors.connectionError") || "Connection error");
    }
  }

  function resetForm() {
    setNewProviderId("");
    setNewKey("");
    setTempModels([]);
    setSelectedModels([]);
    setTestResult(null);
    setError(null);
    setModelSearch("");
  }

  function startEdit(cp: ConfiguredProvider) {
    setNewProviderId(cp.id);
    setNewKey("__REDACTED__"); 
    setTempModels([]); 
    setSelectedModels(cp.models);
    setIsEditing(true);
    setShowAdd(true);
    setModelSearch("");
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  const filteredModels = useMemo(() => {
    return tempModels.filter(m => m.toLowerCase().includes(modelSearch.toLowerCase()));
  }, [tempModels, modelSearch]);

  if (loading) return <div className="p-8 text-center text-slate-400 font-medium">{t("common.loading")}</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-center">
        <SectionHeader 
          title={t("settings.ai.title")} 
          subtitle={t("settings.ai.subtitle")}
        />
        {!showForm && (
          <button 
            onClick={() => { setShowAdd(true); setIsEditing(false); resetForm(); }}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-bold transition-all shadow-lg shadow-indigo-500/20"
          >
            <Plus size={16} /> {t("settings.ai.addProvider")}
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3 text-red-400 text-sm animate-in fade-in slide-in-from-top-2">
          <AlertCircle size={18} /> {error}
        </div>
      )}

      {showForm && (
        <Card className="p-6 bg-slate-900/50 border-indigo-500/30 ring-1 ring-indigo-500/20 animate-in zoom-in-95 duration-200">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              {isEditing ? <Edit3 className="text-amber-400" size={20} /> : <Plus className="text-indigo-400" size={20} />}
              {isEditing ? t("settings.ai.editProvider") : t("settings.ai.newProvider")}
            </h3>
            <button onClick={() => { setShowAdd(false); setIsEditing(false); resetForm(); }} className="text-slate-500 hover:text-white transition-colors">
              <X size={20} />
            </button>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="flex flex-col gap-5">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-wider">{t("settings.ai.provider")}</label>
                <select 
                  value={newProviderId}
                  disabled={isEditing}
                  onChange={(e) => { setNewProviderId(e.target.value); setTempModels([]); setSelectedModels([]); }}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white outline-none focus:border-indigo-500 disabled:opacity-50 transition-all"
                >
                  <option value="">{t("settings.ai.selectProvider") || "Select Provider"}</option>
                  {availableProviders.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase mb-2 tracking-wider">{t("settings.ai.apiKey") || "API Key"}</label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <KeyRound className="absolute left-3 top-3 text-slate-500" size={16} />
                    <input 
                      type="password"
                      value={newKey === "__REDACTED__" ? "" : newKey}
                      onChange={(e) => setNewKey(e.target.value)}
                      placeholder={newKey === "__REDACTED__" ? "••••••••••••••••" : "sk-..."}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 text-white outline-none focus:border-indigo-500 transition-all"
                    />
                  </div>
                  <button 
                    onClick={handleFetchModels}
                    disabled={(!newKey && !isEditing) || fetchingModels}
                    className={`px-4 rounded-lg transition-all flex items-center justify-center min-w-[50px] ${fetchingModels ? "bg-indigo-600 text-white" : "bg-slate-700 hover:bg-slate-600 text-white"}`}
                    title={t("settings.ai.fetchModels")}
                  >
                    {fetchingModels ? <RefreshCcw size={18} className="animate-spin" /> : <RefreshCcw size={18} />}
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-1.5 ml-1 italic">
                  {isEditing && newKey === "__REDACTED__" 
                    ? t("settings.ai.hints.storedKey") 
                    : t("settings.ai.hints.clickRefresh")}
                </p>
              </div>

              {selectedModels.length > 0 && (
                <div className="p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-xs font-bold text-indigo-300 uppercase tracking-widest">{t("settings.ai.testConnection")}</span>
                    {testResult && (
                      <Badge variant={testResult.status === "ok" ? "success" : "danger"}>
                        {testResult.status === "ok" ? `${testResult.latency}ms` : t("settings.ai.status.error")}
                      </Badge>
                    )}
                  </div>
                  <button 
                    onClick={handleTestConnection}
                    disabled={testing || selectedModels.length === 0}
                    className="w-full py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 rounded-lg text-xs font-bold border border-indigo-500/20 flex items-center justify-center gap-2 transition-all disabled:opacity-30"
                  >
                    {testing ? <RefreshCcw size={14} className="animate-spin" /> : <Zap size={14} />}
                    {testResult?.status === "error" ? t("settings.ai.retry") : t("settings.ai.latencyTest")}
                  </button>
                  {testResult?.detail && <p className="mt-2 text-[10px] text-red-400 leading-tight p-2 bg-red-500/10 rounded">{testResult.detail}</p>}
                </div>
              )}
            </div>

            <div className="flex flex-col">
              <div className="flex justify-between items-end mb-2">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-wider">{t("settings.ai.models")} ({selectedModels.length})</label>
                {tempModels.length > 0 && (
                  <div className="relative w-40">
                    <Search className="absolute left-2 top-1.5 text-slate-500" size={12} />
                    <input 
                      className="w-full bg-slate-800 border border-slate-700 rounded-md pl-7 pr-2 py-1 text-[11px] text-white outline-none focus:border-indigo-500"
                      placeholder={t("members.search")}
                      value={modelSearch}
                      onChange={e => setModelSearch(e.target.value)}
                    />
                  </div>
                )}
              </div>
              <div className="flex-1 bg-slate-800/30 border border-slate-700 rounded-xl overflow-hidden flex flex-col min-h-[250px]">
                {fetchingModels ? (
                  <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
                    <RefreshCcw size={24} className="animate-spin text-indigo-500" />
                    <span className="text-xs font-medium uppercase tracking-widest">{t("settings.ai.status.fetching")}</span>
                  </div>
                ) : tempModels.length > 0 ? (
                  <div className="overflow-y-auto max-h-[300px] p-2 flex flex-col gap-1 custom-scrollbar">
                    {filteredModels.map(model => (
                      <button 
                        key={model}
                        onClick={() => {
                          setSelectedModels(prev => prev.includes(model) ? prev.filter(m => m !== model) : [...prev, model]);
                        }}
                        className={`flex items-center justify-between p-2.5 rounded-lg text-sm transition-all ${
                          selectedModels.includes(model) 
                            ? "bg-indigo-600/20 text-white border border-indigo-500/30" 
                            : "text-slate-400 hover:bg-white/5 border border-transparent"
                        }`}
                      >
                        <span className="truncate font-medium">{model}</span>
                        {selectedModels.includes(model) && <Check size={14} className="text-indigo-400" />}
                      </button>
                    ))}
                    {filteredModels.length === 0 && <div className="p-8 text-center text-slate-500 text-xs italic">{t("settings.ai.noModelsFound")}</div>}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500 text-xs gap-4">
                    <div className="p-4 bg-slate-800/50 rounded-full"><RefreshCcw size={32} className="opacity-20" /></div>
                    <p className="max-w-[200px] italic">{isEditing ? t("settings.ai.hints.refreshNeeded") : t("settings.ai.hints.initialFetch")}</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="mt-8 flex justify-end gap-3 border-t border-slate-800 pt-6">
            <button 
              onClick={handleSaveProvider}
              disabled={selectedModels.length === 0 || !!testing || fetchingModels}
              className="px-8 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold shadow-lg shadow-indigo-500/20 disabled:opacity-50 transition-all active:scale-95"
            >
              {isEditing ? t("common.save") : t("settings.ai.addProvider")}
            </button>
          </div>
        </Card>
      )}

      {/* ── List Section ──────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4">
        {configuredProviders.map(cp => (
          <Card key={cp.id} className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-6 hover:border-slate-700 transition-all group">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-indigo-500/10 rounded-2xl flex items-center justify-center text-indigo-400 group-hover:bg-indigo-500/20 transition-colors"><Cpu size={24} /></div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h4 className="font-bold text-white uppercase tracking-tight">{cp.name}</h4>
                  <Badge variant="success" size="xs">{t("settings.ai.status.configured")}</Badge>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {cp.models.map(m => <span key={m} className="px-2 py-0.5 bg-slate-800 text-slate-400 text-[10px] font-bold rounded-md uppercase tracking-wider border border-slate-700">{m}</span>)}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => startEdit(cp)} className="p-2.5 text-slate-400 hover:text-amber-400 hover:bg-amber-400/10 rounded-lg transition-all" title={t("common.edit")}><Edit3 size={18} /></button>
              <button 
                onClick={async () => {
                  if (confirm(t("settings.ai.confirmDelete"))) {
                    const newList = configuredProviders.filter(p => p.id !== cp.id);
                    await saveProviders(newList);
                  }
                }}
                className="p-2.5 text-slate-400 hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-all" title={t("common.delete")}
              ><Trash2 size={18} /></button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  async function saveProviders(newList: ConfiguredProvider[]) {
    try {
      const res = await apiFetch("/admin/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([{ key: "platform_llm_providers_json", value: JSON.stringify(newList) }])
      });
      if (res.ok) setConfiguredProviders(newList);
    } catch (e) { setError(t("settings.ai.errors.deleteFailed")); }
  }
}
