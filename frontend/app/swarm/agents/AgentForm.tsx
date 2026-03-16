"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Save, ArrowLeft } from "lucide-react";

type ToolRow = {
  id: string;
  display_name: string;
  category: string | null;
  required_integration: string | null;
};

type AgentFormData = {
  id: string;
  display_name: string;
  description: string;
  system_prompt: string;
  default_tools: string[];
  max_turns: number;
  qa_profile: string;
  min_plan_tier: string;
  is_system: boolean;
};

const JINJA_HINTS = [
  "{{ studio_name }}",
  "{{ persona_name }}",
  "{{ prices }}",
  "{{ qa_feedback }}",
  "{{ member_name }}",
  "{{ language }}",
];

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 13,
  padding: "10px 12px",
  outline: "none",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: T.textMuted,
  marginBottom: 6,
};

const btnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: 6,
  padding: "8px 16px",
  borderRadius: 10,
  border: "none",
  fontWeight: 600,
  fontSize: 13,
  cursor: "pointer",
};

export default function AgentForm({ agentId }: { agentId?: string }) {
  const router = useRouter();
  const isEdit = !!agentId;
  const [form, setForm] = useState<AgentFormData>({
    id: "",
    display_name: "",
    description: "",
    system_prompt: "",
    default_tools: [],
    max_turns: 5,
    qa_profile: "standard",
    min_plan_tier: "starter",
    is_system: false,
  });
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEdit);

  const loadTools = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/swarm/tools");
      if (res.ok) setTools(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadAgent = useCallback(async () => {
    if (!agentId) return;
    setLoading(true);
    try {
      const res = await apiFetch(`/admin/swarm/agents/${agentId}`);
      if (!res.ok) throw new Error(`Agent not found (${res.status})`);
      const data = await res.json();
      setForm({
        id: data.id,
        display_name: data.display_name,
        description: data.description || "",
        system_prompt: data.system_prompt || "",
        default_tools: data.default_tools || [],
        max_turns: data.max_turns,
        qa_profile: data.qa_profile || "standard",
        min_plan_tier: data.min_plan_tier,
        is_system: data.is_system,
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void loadTools();
    void loadAgent();
  }, [loadTools, loadAgent]);

  function update<K extends keyof AgentFormData>(key: K, val: AgentFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function toggleTool(toolId: string) {
    setForm((prev) => {
      const cur = prev.default_tools;
      return {
        ...prev,
        default_tools: cur.includes(toolId) ? cur.filter((t) => t !== toolId) : [...cur, toolId],
      };
    });
  }

  async function save() {
    setError("");
    if (!form.display_name.trim()) { setError("Display name is required"); return; }
    if (!isEdit && !form.id.trim()) { setError("ID is required"); return; }
    setSaving(true);
    try {
      const payload = isEdit
        ? {
            display_name: form.display_name,
            description: form.description || null,
            system_prompt: form.system_prompt || null,
            default_tools: form.default_tools.length > 0 ? form.default_tools : null,
            max_turns: form.max_turns,
            qa_profile: form.qa_profile || null,
            min_plan_tier: form.min_plan_tier,
          }
        : {
            id: form.id,
            display_name: form.display_name,
            description: form.description || null,
            system_prompt: form.system_prompt || null,
            default_tools: form.default_tools.length > 0 ? form.default_tools : null,
            max_turns: form.max_turns,
            qa_profile: form.qa_profile || null,
            min_plan_tier: form.min_plan_tier,
            is_system: false,
          };

      const url = isEdit ? `/admin/swarm/agents/${agentId}` : "/admin/swarm/agents";
      const method = isEdit ? "PATCH" : "POST";
      const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      router.push("/swarm/agents");
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ color: T.textMuted, padding: 20 }}>Loading...</div>;

  // Group tools by category
  const toolsByCategory: Record<string, ToolRow[]> = {};
  for (const t of tools) {
    const cat = t.category || "other";
    if (!toolsByCategory[cat]) toolsByCategory[cat] = [];
    toolsByCategory[cat].push(t);
  }

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 800 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          onClick={() => router.push("/swarm/agents")}
          style={{ ...btnStyle, background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}
        >
          <ArrowLeft size={14} /> Back
        </button>
        <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>
          {isEdit ? `Edit Agent: ${agentId}` : "New Agent"}
        </span>
      </div>

      {error && (
        <Card hover={false} style={{ padding: 12, borderColor: T.danger }}>
          <span style={{ color: T.danger, fontSize: 13 }}>{error}</span>
        </Card>
      )}

      <Card hover={false} style={{ padding: 20 }}>
        <div style={{ display: "grid", gap: 16 }}>
          {!isEdit && (
            <div>
              <label style={labelStyle}>Agent ID (slug, cannot be changed later)</label>
              <input
                style={inputStyle}
                value={form.id}
                onChange={(e) => update("id", e.target.value.replace(/[^a-z0-9_-]/g, ""))}
                placeholder="e.g. social_media, custom_ops"
                maxLength={64}
              />
            </div>
          )}

          <div>
            <label style={labelStyle}>Display Name</label>
            <input style={inputStyle} value={form.display_name} onChange={(e) => update("display_name", e.target.value)} placeholder="e.g. Social Media Agent" />
          </div>

          <div>
            <label style={labelStyle}>Description</label>
            <textarea style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="Brief description of what this agent does" />
          </div>

          <div>
            <label style={labelStyle}>
              System Prompt (Jinja2)
              <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 8, fontSize: 11 }}>
                Variables: {JINJA_HINTS.join(", ")}
              </span>
            </label>
            <textarea
              style={{ ...inputStyle, minHeight: 180, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
              value={form.system_prompt}
              onChange={(e) => update("system_prompt", e.target.value)}
              placeholder="You are {{ persona_name }}, an AI assistant for {{ studio_name }}..."
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>QA Profile</label>
              <select style={inputStyle} value={form.qa_profile} onChange={(e) => update("qa_profile", e.target.value)}>
                <option value="strict">strict</option>
                <option value="standard">standard</option>
                <option value="off">off</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Max Turns</label>
              <input style={inputStyle} type="number" min={1} max={50} value={form.max_turns} onChange={(e) => update("max_turns", Number(e.target.value))} />
            </div>
            <div>
              <label style={labelStyle}>Min Plan Tier</label>
              <select style={inputStyle} value={form.min_plan_tier} onChange={(e) => update("min_plan_tier", e.target.value)}>
                <option value="starter">Starter</option>
                <option value="pro">Pro</option>
                <option value="enterprise">Enterprise</option>
              </select>
            </div>
          </div>

          {/* Tool Selector */}
          <div>
            <label style={labelStyle}>Default Tools</label>
            <div style={{ display: "grid", gap: 8 }}>
              {Object.entries(toolsByCategory).map(([cat, catTools]) => (
                <div key={cat}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: T.textDim, textTransform: "uppercase", marginBottom: 4 }}>{cat}</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {catTools.map((t) => {
                      const checked = form.default_tools.includes(t.id);
                      return (
                        <label
                          key={t.id}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            padding: "4px 10px",
                            borderRadius: 8,
                            border: `1px solid ${checked ? T.accent : T.border}`,
                            background: checked ? T.accentDim : T.surfaceAlt,
                            cursor: "pointer",
                            fontSize: 12,
                            color: checked ? T.accentLight : T.textMuted,
                            transition: "all 0.15s ease",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleTool(t.id)}
                            style={{ display: "none" }}
                          />
                          {t.display_name}
                          {t.required_integration && (
                            <Badge variant="default" size="xs">{t.required_integration}</Badge>
                          )}
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
              {tools.length === 0 && (
                <span style={{ fontSize: 12, color: T.textDim }}>No tools defined yet.</span>
              )}
            </div>
          </div>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button
          onClick={() => router.push("/swarm/agents")}
          style={{ ...btnStyle, background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}
        >
          Cancel
        </button>
        <button
          onClick={save}
          disabled={saving}
          style={{ ...btnStyle, background: T.accent, color: "#fff", opacity: saving ? 0.6 : 1 }}
        >
          <Save size={14} /> {saving ? "Saving..." : "Save Agent"}
        </button>
      </div>
    </div>
  );
}
