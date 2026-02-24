"use client";

import { useState, useEffect } from "react";
import { 
  Cpu, Zap, Activity, AlertCircle, CheckCircle2, 
  Shield, Key, RefreshCw, Trash2, Settings2, Plus, 
  Globe, Check
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";

type Provider = {
  id: string;
  name: string;
  base_url: string;
  models: string[];
  health?: "ok" | "error" | "unknown";
  latency?: number;
  error?: string;
};

type Predefined = {
  id: string;
  name: string;
  base_url: string;
  default_models: string[];
};

export function PlatformAiManager() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [predefined, setPredefined] = useState<Predefined[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  
  // Form State
  const [editMode, setEditMode] = useState(false);
  const [selectedPredefinedId, setSelectedPredefinedId] = useState("");
  const [form, setForm] = useState({
    id: "",
    name: "",
    base_url: "",
    api_key: "",
    selectedModels: [] as string[]
  });
  
  const [testResult, setTestResult] = useState<{status: string, latency?: number, error?: string} | null>(null);
  const [busy, setBusy] = useState(false);

  const fetchData = async () => {
    const [resStatus, resPre] = await Promise.all([
      apiFetch("/admin/platform/llm/status"),
      apiFetch("/admin/platform/llm/predefined")
    ]);
    if (resStatus.ok) setProviders(await resStatus.json());
    if (resPre.ok) setPredefined(await resPre.json());
    setLoading(false);
  };

  useEffect(() => {
    void fetchData();
  }, []);

  // When a predefined provider is selected, auto-fill URL and show models
  useEffect(() => {
    if (editMode) return;
    const pre = predefined.find(p => p.id === selectedPredefinedId);
    if (pre) {
      setForm(f => ({
        ...f,
        id: pre.id,
        name: pre.name,
        base_url: pre.base_url,
        selectedModels: [] // Reset selection on provider change
      }));
    }
  }, [selectedPredefinedId, predefined, editMode]);

  const openAdd = () => {
    setEditMode(false);
    setSelectedPredefinedId("");
    setForm({ id: "", name: "", base_url: "", api_key: "", selectedModels: [] });
    setTestResult(null);
    setModalOpen(true);
  };

  const openEdit = (p: Provider) => {
    setEditMode(true);
    setForm({ 
      id: p.id, 
      name: p.name, 
      base_url: p.base_url, 
      api_key: "__REDACTED__", 
      selectedModels: p.models 
    });
    setTestResult(null);
    setModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm(`Provider '${id}' wirklich löschen?`)) return;
    const res = await apiFetch(`/admin/platform/llm/providers/${id}`, { method: "DELETE" });
    if (res.ok) void fetchData();
  };

  const toggleModel = (m: string) => {
    setForm(f => ({
      ...f,
      selectedModels: f.selectedModels.includes(m) 
        ? f.selectedModels.filter(x => x !== m) 
        : [...f.selectedModels, m]
    }));
  };

  const runTest = async () => {
    setBusy(true);
    setTestResult(null);
    const res = await apiFetch("/admin/platform/llm/test-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: form.id,
        name: form.name,
        base_url: form.base_url,
        api_key: form.api_key,
        models: form.selectedModels
      })
    });
    if (res.ok) setTestResult(await res.json());
    else setTestResult({ status: "error", error: "Connection failed" });
    setBusy(false);
  };

  const handleSave = async () => {
    if (form.selectedModels.length === 0) {
      alert("Bitte mindestens ein Modell auswählen.");
      return;
    }
    setBusy(true);
    const res = await apiFetch("/admin/platform/llm/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: form.id,
        name: form.name,
        base_url: form.base_url,
        api_key: form.api_key,
        models: form.selectedModels
      })
    });
    if (res.ok) {
      setModalOpen(false);
      void fetchData();
    }
    setBusy(false);
  };

  const currentPredefined = predefined.find(p => p.id === (editMode ? form.id : selectedPredefinedId));
  const availableModels = currentPredefined?.default_models || [];

  if (loading) return <div style={{ fontSize: 12, color: T.textDim }}>Loading AI configurations...</div>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: 0 }}>AI Engine Infrastructure</h3>
          <p style={{ fontSize: 11, color: T.textMuted, margin: "2px 0 0" }}>Managed platform-wide LLM providers and models.</p>
        </div>
        <button onClick={openAdd} className="btn btn-sm btn-primary gap-2">
          <Plus size={14} /> Add Provider
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
        {providers.map((p) => (
          <Card key={p.id} style={{ padding: 16, background: T.surfaceAlt }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: `${T.accent}15`, display: "flex", alignItems: "center", justifyContent: "center", color: T.accent }}>
                  <Cpu size={18} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{p.name}</div>
                  <div style={{ fontSize: 10, color: T.textDim, fontFamily: "monospace" }}>{p.id}</div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                <button onClick={() => openEdit(p)} className="btn btn-ghost btn-xs px-1 text-muted" title="Setup bearbeiten"><Settings2 size={14}/></button>
                <button onClick={() => handleDelete(p.id)} className="btn btn-ghost btn-xs px-1 text-error" title="Provider löschen"><Trash2 size={14}/></button>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
               <Globe size={12} color={T.textDim} />
               <span style={{ fontSize: 11, color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis" }}>{p.base_url}</span>
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, minHeight: 48 }}>
              {p.models.map(m => (
                <Badge key={m} size="xs" variant="default">{m}</Badge>
              ))}
            </div>

            <div style={{ marginTop: 16, paddingTop: 12, borderTop: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
               <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                 {p.health === "ok" ? (
                   <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                     <CheckCircle2 size={14} color={T.success} />
                     <span style={{ fontSize: 11, fontWeight: 700, color: T.success }}>{p.latency}ms</span>
                   </div>
                 ) : (
                   <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                     <AlertCircle size={14} color={T.danger} />
                     <span style={{ fontSize: 11, color: T.danger }}>Offline</span>
                   </div>
                 )}
               </div>
               <Badge variant="default" size="xs">Platform Key Active</Badge>
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editMode ? `Setup: ${form.name}` : "Connect AI Provider"}
        subtitle="SaaS Infrastructure Governance"
        width="min(640px, 100%)"
      >
        <div style={{ display: "grid", gap: 20 }}>
          {!editMode && (
            <div>
              <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Select Provider Type</span></label>
              <select 
                className="select select-bordered select-sm w-full"
                value={selectedPredefinedId}
                onChange={e => setSelectedPredefinedId(e.target.value)}
              >
                <option value="" disabled>Wähle einen Provider...</option>
                {predefined.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Internal ID</span></label>
              <input 
                className="input input-bordered input-sm w-full bg-base-300" 
                value={form.id} 
                disabled
                placeholder="Auto-generated"
              />
            </div>
            <div>
              <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Display Name</span></label>
              <input 
                className="input input-bordered input-sm w-full" 
                value={form.name} 
                onChange={e => setForm({...form, name: e.target.value})}
              />
            </div>
          </div>

          <div>
            <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Base URL</span></label>
            <input 
              className="input input-bordered input-sm w-full" 
              value={form.base_url} 
              onChange={e => setForm({...form, base_url: e.target.value})}
              placeholder="https://..."
            />
          </div>

          <div>
            <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Platform API Key</span></label>
            <div className="relative">
              <Key size={14} className="absolute left-3 top-2.5 text-muted" />
              <input 
                type="password"
                className="input input-bordered input-sm w-full pl-9" 
                placeholder={editMode ? "•••••••• (Leave empty to keep current)" : "sk-..."}
                value={form.api_key === "__REDACTED__" ? "" : form.api_key} 
                onChange={e => setForm({...form, api_key: e.target.value})}
              />
            </div>
          </div>

          {availableModels.length > 0 && (
            <div>
              <label className="label py-1"><span className="label-text text-xs uppercase font-bold text-muted">Enabled Models</span></label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, padding: 12, borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                {availableModels.map(m => (
                  <label key={m} style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", padding: "4px 0" }}>
                    <div 
                      onClick={() => toggleModel(m)}
                      style={{ 
                        width: 18, height: 18, borderRadius: 4, 
                        border: `2px solid ${form.selectedModels.includes(m) ? T.accent : T.border}`,
                        background: form.selectedModels.includes(m) ? T.accent : "transparent",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        transition: "all 0.1s"
                      }}
                    >
                      {form.selectedModels.includes(m) && <Check size={12} color="#000" strokeWidth={4} />}
                    </div>
                    <span style={{ fontSize: 13, color: form.selectedModels.includes(m) ? T.text : T.textMuted }}>{m}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {testResult && (
            <div style={{ padding: 12, borderRadius: 10, background: testResult.status === "ok" ? `${T.success}10` : `${T.danger}10`, border: `1px solid ${testResult.status === "ok" ? T.success : T.danger}33` }}>
               <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                 {testResult.status === "ok" ? <CheckCircle2 size={16} color={T.success} /> : <AlertCircle size={16} color={T.danger} />}
                 <span style={{ fontSize: 13, fontWeight: 700, color: testResult.status === "ok" ? T.success : T.danger }}>
                   {testResult.status === "ok" ? `Connection Successful (${testResult.latency}ms)` : `Test Failed`}
                 </span>
               </div>
               {testResult.error && <p style={{ fontSize: 11, margin: "4px 0 0", color: T.danger }}>{testResult.error}</p>}
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
            <button onClick={runTest} disabled={busy || !form.base_url} className="btn btn-sm btn-outline gap-2">
              {busy ? <RefreshCw size={14} className="animate-spin" /> : <Activity size={14} />} 
              Test Config
            </button>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setModalOpen(false)} className="btn btn-sm btn-ghost">Cancel</button>
              <button onClick={handleSave} disabled={busy || !form.id} className="btn btn-sm btn-primary px-6">
                {editMode ? "Update Provider" : "Save Provider"}
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
}
