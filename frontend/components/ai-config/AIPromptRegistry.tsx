"use client";
import React, { useState, useEffect, useCallback } from "react";
import {
  FileText, Plus, ChevronDown, ChevronRight, Rocket, Eye, Edit3,
  Clock, Tag, CheckCircle2, AlertCircle, RefreshCcw, Save, X, Play,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";

type PromptTemplate = {
  id: number; slug: string; name: string; description: string | null;
  category: string; agent_type: string | null; is_active: boolean;
  versions_count: number; active_version: string | null;
  created_at: string; updated_at: string;
};
type PromptVersion = {
  id: number; template_id: number; version: string; content: string;
  variables: string[] | null; change_notes: string | null;
  created_by: string | null; status: string; created_at: string;
};

export function AIPromptRegistry() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [versions, setVersions] = useState<Record<number, PromptVersion[]>>({});
  const [showNewVersion, setShowNewVersion] = useState<number | null>(null);
  const [newContent, setNewContent] = useState("");
  const [changeNotes, setChangeNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ slug: "", name: "", description: "", category: "agent", agent_type: "" });
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testVars, setTestVars] = useState<string>("{}");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/admin/ai/prompts");
      if (res.ok) setTemplates(await res.json());
      else setError("Fehler beim Laden");
    } catch { setError("Netzwerkfehler"); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadVersions = async (templateId: number) => {
    const res = await apiFetch(`/admin/ai/prompts/${templateId}/versions`);
    if (res.ok) {
      const data = await res.json();
      setVersions((prev) => ({ ...prev, [templateId]: data }));
    }
  };

  const toggleExpand = (id: number) => {
    if (expandedId === id) { setExpandedId(null); return; }
    setExpandedId(id);
    if (!versions[id]) loadVersions(id);
  };

  const handleCreateTemplate = async () => {
    setSaving(true);
    const res = await apiFetch("/admin/ai/prompts", { method: "POST", body: JSON.stringify(createForm) });
    if (res.ok) { setShowCreate(false); setCreateForm({ slug: "", name: "", description: "", category: "agent", agent_type: "" }); load(); }
    else { const d = await res.json().catch(() => ({})); setError(d.detail || "Fehler"); }
    setSaving(false);
  };

  const handleCreateVersion = async (templateId: number) => {
    setSaving(true);
    const res = await apiFetch(`/admin/ai/prompts/${templateId}/versions`, {
      method: "POST", body: JSON.stringify({ content: newContent, change_notes: changeNotes }),
    });
    if (res.ok) { setShowNewVersion(null); setNewContent(""); setChangeNotes(""); loadVersions(templateId); load(); }
    else { const d = await res.json().catch(() => ({})); setError(d.detail || "Fehler"); }
    setSaving(false);
  };

  const handlePublish = async (versionId: number, templateId: number) => {
    await apiFetch(`/admin/ai/prompts/versions/${versionId}/publish`, { method: "POST" });
    loadVersions(templateId);
    load();
  };

  const handleDeploy = async (versionId: number, templateId: number) => {
    await apiFetch("/admin/ai/prompts/deploy", {
      method: "POST", body: JSON.stringify({ version_id: versionId, environment: "production" }),
    });
    loadVersions(templateId);
  };

  const handleTest = async () => {
    try {
      const vars = JSON.parse(testVars);
      const res = await apiFetch("/admin/ai/prompts/test", {
        method: "POST", body: JSON.stringify({ content: newContent, variables: vars }),
      });
      if (res.ok) {
        const data = await res.json();
        setTestResult(data.rendered);
      }
    } catch { setTestResult("Fehler: Ungültiges JSON in Variablen"); }
  };

  const inputStyle: React.CSSProperties = { width: "100%", padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, color: T.text, fontSize: 13, outline: "none" };
  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 4, display: "block" };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <SectionHeader title="Prompt Registry" subtitle="Versionierte Prompt-Templates mit Deployment-Pipeline" />
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={load} style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.textMuted, cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <RefreshCcw size={14} />
          </button>
          <button onClick={() => setShowCreate(true)} style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
            <Plus size={14} /> Neues Template
          </button>
        </div>
      </div>

      {error && <div style={{ padding: 12, borderRadius: 8, background: T.dangerDim, color: T.danger, fontSize: 12, marginBottom: 16 }}>{error} <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: T.danger, cursor: "pointer", marginLeft: 8 }}>×</button></div>}

      {/* Create Template Form */}
      {showCreate && (
        <div style={{ padding: 20, borderRadius: 12, border: `1px solid ${T.accent}30`, background: T.surfaceAlt, marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Neues Prompt Template</span>
            <button onClick={() => setShowCreate(false)} style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer" }}><X size={18} /></button>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div><label style={labelStyle}>Slug</label><input style={inputStyle} value={createForm.slug} onChange={(e) => setCreateForm({ ...createForm, slug: e.target.value })} placeholder="z.B. sales/system" /></div>
            <div><label style={labelStyle}>Name</label><input style={inputStyle} value={createForm.name} onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })} placeholder="Sales Agent System Prompt" /></div>
            <div><label style={labelStyle}>Kategorie</label>
              <select style={inputStyle} value={createForm.category} onChange={(e) => setCreateForm({ ...createForm, category: e.target.value })}>
                <option value="agent">Agent</option><option value="persona">Persona</option><option value="greeting">Greeting</option><option value="system">System</option>
              </select>
            </div>
            <div><label style={labelStyle}>Agent-Typ</label><input style={inputStyle} value={createForm.agent_type} onChange={(e) => setCreateForm({ ...createForm, agent_type: e.target.value })} placeholder="z.B. sales" /></div>
            <div style={{ gridColumn: "1 / -1" }}><label style={labelStyle}>Beschreibung</label><input style={inputStyle} value={createForm.description} onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })} /></div>
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
            <button onClick={() => setShowCreate(false)} style={{ padding: "8px 16px", borderRadius: 8, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 12 }}>Abbrechen</button>
            <button onClick={handleCreateTemplate} disabled={saving} style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
              <Save size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />{saving ? "..." : "Erstellen"}
            </button>
          </div>
        </div>
      )}

      {/* Template List */}
      {loading ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textMuted, fontSize: 13 }}>Lade Templates...</div>
      ) : templates.length === 0 ? (
        <div style={{ textAlign: "center", padding: 40, color: T.textDim, fontSize: 13 }}>Keine Prompt Templates vorhanden.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {templates.map((t) => (
            <div key={t.id} style={{ borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt, overflow: "hidden" }}>
              {/* Template Header */}
              <div onClick={() => toggleExpand(t.id)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", cursor: "pointer" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  {expandedId === t.id ? <ChevronDown size={14} color={T.accent} /> : <ChevronRight size={14} color={T.textDim} />}
                  <FileText size={16} color={T.accent} />
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{t.name}</span>
                      <span style={{ fontSize: 10, color: T.textDim, fontFamily: "monospace" }}>{t.slug}</span>
                    </div>
                    <div style={{ display: "flex", gap: 8, marginTop: 2, fontSize: 10, color: T.textMuted }}>
                      <span><Tag size={9} style={{ marginRight: 2, verticalAlign: "middle" }} />{t.category}</span>
                      {t.agent_type && <span>Agent: {t.agent_type}</span>}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Badge variant={t.active_version ? "success" : "warning"}>
                    {t.active_version ? `v${t.active_version}` : "Kein Deploy"}
                  </Badge>
                  <span style={{ fontSize: 10, color: T.textDim }}>{t.versions_count} Version{t.versions_count !== 1 ? "en" : ""}</span>
                </div>
              </div>

              {/* Expanded: Versions */}
              {expandedId === t.id && (
                <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.border}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0 8px" }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: T.textMuted }}>Versionen</span>
                    <button onClick={() => { setShowNewVersion(t.id); setNewContent(versions[t.id]?.[0]?.content || ""); }} style={{ padding: "4px 12px", borderRadius: 6, border: `1px solid ${T.accent}40`, background: T.accentDim, color: T.accent, cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                      <Plus size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />Neue Version
                    </button>
                  </div>

                  {/* New Version Form */}
                  {showNewVersion === t.id && (
                    <div style={{ padding: 16, borderRadius: 10, border: `1px solid ${T.accent}30`, background: T.bg, marginBottom: 12 }}>
                      <label style={labelStyle}>Prompt-Inhalt (Jinja2)</label>
                      <textarea style={{ ...inputStyle, minHeight: 200, fontFamily: "monospace", fontSize: 12, resize: "vertical" }} value={newContent} onChange={(e) => setNewContent(e.target.value)} />
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
                        <div><label style={labelStyle}>Änderungsnotiz</label><input style={inputStyle} value={changeNotes} onChange={(e) => setChangeNotes(e.target.value)} placeholder="Was wurde geändert?" /></div>
                        <div><label style={labelStyle}>Test-Variablen (JSON)</label><input style={inputStyle} value={testVars} onChange={(e) => setTestVars(e.target.value)} placeholder='{"studio_name": "Test"}' /></div>
                      </div>
                      {testResult && <div style={{ marginTop: 12, padding: 12, borderRadius: 8, background: T.surfaceAlt, border: `1px solid ${T.border}`, fontSize: 11, fontFamily: "monospace", whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto", color: T.text }}>{testResult}</div>}
                      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
                        <button onClick={handleTest} style={{ padding: "6px 14px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.info, cursor: "pointer", fontSize: 11 }}>
                          <Play size={12} style={{ marginRight: 4, verticalAlign: "middle" }} />Testen
                        </button>
                        <button onClick={() => setShowNewVersion(null)} style={{ padding: "6px 14px", borderRadius: 6, border: `1px solid ${T.border}`, background: "transparent", color: T.textMuted, cursor: "pointer", fontSize: 11 }}>Abbrechen</button>
                        <button onClick={() => handleCreateVersion(t.id)} disabled={saving} style={{ padding: "6px 16px", borderRadius: 6, border: "none", background: T.accent, color: "#fff", cursor: "pointer", fontSize: 11, fontWeight: 600 }}>
                          {saving ? "..." : "Version erstellen"}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Version List */}
                  {(versions[t.id] || []).map((v) => (
                    <div key={v.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, border: `1px solid ${T.border}`, background: T.bg, marginBottom: 4 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <Badge variant={v.status === "published" ? "success" : "default"}>v{v.version}</Badge>
                        <span style={{ fontSize: 11, color: T.textMuted }}>{v.change_notes || "—"}</span>
                        <span style={{ fontSize: 10, color: T.textDim }}><Clock size={9} style={{ marginRight: 2, verticalAlign: "middle" }} />{new Date(v.created_at).toLocaleDateString("de-DE")}</span>
                      </div>
                      <div style={{ display: "flex", gap: 6 }}>
                        {v.status !== "published" && (
                          <button onClick={() => handlePublish(v.id, t.id)} style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${T.successDim}`, background: "transparent", color: T.success, cursor: "pointer", fontSize: 10 }}>
                            <CheckCircle2 size={11} style={{ marginRight: 3, verticalAlign: "middle" }} />Publish
                          </button>
                        )}
                        <button onClick={() => handleDeploy(v.id, t.id)} style={{ padding: "4px 10px", borderRadius: 6, border: `1px solid ${T.accent}40`, background: T.accentDim, color: T.accent, cursor: "pointer", fontSize: 10 }}>
                          <Rocket size={11} style={{ marginRight: 3, verticalAlign: "middle" }} />Deploy
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
