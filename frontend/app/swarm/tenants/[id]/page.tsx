"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bot, Wrench, ToggleLeft, ToggleRight, ChevronDown, ChevronUp, Save } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TenantAgentEntry = {
  id: string;
  display_name: string;
  description: string | null;
  system_prompt: string | null;
  default_tools: string[] | null;
  max_turns: number;
  qa_profile: string | null;
  min_plan_tier: string;
  is_system: boolean;
  tenant_config: {
    is_enabled: boolean;
    system_prompt_override: string | null;
    tool_overrides: string[] | null;
    extra_config: Record<string, unknown> | null;
  } | null;
};

type TenantToolEntry = {
  id: string;
  display_name: string;
  description: string | null;
  category: string | null;
  required_integration: string | null;
  min_plan_tier: string;
  config_schema: Record<string, unknown> | null;
  is_system: boolean;
  tenant_config: {
    is_enabled: boolean;
    config: Record<string, unknown> | null;
  } | null;
};

type AllTools = { id: string; display_name: string; category: string | null }[];

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

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

const tabStyle = (active: boolean): React.CSSProperties => ({
  padding: "10px 20px",
  borderRadius: "10px 10px 0 0",
  border: `1px solid ${active ? T.accent : T.border}`,
  borderBottom: active ? `2px solid ${T.accent}` : `1px solid ${T.border}`,
  background: active ? T.accentDim : T.surface,
  color: active ? T.accentLight : T.textMuted,
  fontWeight: 600,
  fontSize: 13,
  cursor: "pointer",
});

const JINJA_HINTS = ["{{ studio_name }}", "{{ persona_name }}", "{{ prices }}", "{{ qa_feedback }}"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TenantSwarmConfigPage() {
  const params = useParams();
  const tenantId = Number(params?.id);
  const user = getStoredUser();

  const [tab, setTab] = useState<"agents" | "tools">("agents");
  const [agents, setAgents] = useState<TenantAgentEntry[]>([]);
  const [tools, setTools] = useState<TenantToolEntry[]>([]);
  const [allTools, setAllTools] = useState<AllTools>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [expandedTool, setExpandedTool] = useState<string | null>(null);

  // Local edits for agents
  const [agentOverrides, setAgentOverrides] = useState<
    Record<string, { system_prompt_override: string; tool_overrides: string[] }>
  >({});
  // Local edits for tools
  const [toolConfigs, setToolConfigs] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [aRes, tRes, allTRes] = await Promise.all([
        apiFetch(`/admin/swarm/tenants/${tenantId}/agents`),
        apiFetch(`/admin/swarm/tenants/${tenantId}/tools`),
        apiFetch("/admin/swarm/tools"),
      ]);
      if (!aRes.ok) throw new Error(`Agent load failed (${aRes.status})`);
      if (!tRes.ok) throw new Error(`Tool load failed (${tRes.status})`);
      const agentData = (await aRes.json()) as TenantAgentEntry[];
      const toolData = (await tRes.json()) as TenantToolEntry[];
      setAgents(agentData);
      setTools(toolData);
      if (allTRes.ok) setAllTools(await allTRes.json());

      // Initialize local state from existing configs
      const ao: typeof agentOverrides = {};
      for (const a of agentData) {
        ao[a.id] = {
          system_prompt_override: a.tenant_config?.system_prompt_override || "",
          tool_overrides: a.tenant_config?.tool_overrides || a.default_tools || [],
        };
      }
      setAgentOverrides(ao);

      const tc: Record<string, string> = {};
      for (const t of toolData) {
        tc[t.id] = t.tenant_config?.config ? JSON.stringify(t.tenant_config.config, null, 2) : "{}";
      }
      setToolConfigs(tc);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => { void load(); }, [load]);

  if (user?.role !== "system_admin") {
    return <div style={{ padding: 40, color: T.danger }}>Access denied. System admin only.</div>;
  }

  // --- Agent toggle ---
  async function toggleAgent(agentId: string, currentEnabled: boolean) {
    setSaving(agentId);
    try {
      const res = await apiFetch(`/admin/swarm/tenants/${tenantId}/agents/${agentId}/configure`, {
        method: "POST",
        body: JSON.stringify({ is_enabled: !currentEnabled }),
      });
      if (!res.ok) throw new Error(`Toggle failed (${res.status})`);
      setAgents((prev) =>
        prev.map((a) =>
          a.id === agentId
            ? {
                ...a,
                tenant_config: {
                  ...(a.tenant_config || { system_prompt_override: null, tool_overrides: null, extra_config: null }),
                  is_enabled: !currentEnabled,
                },
              }
            : a,
        ),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(null);
    }
  }

  // --- Save agent config ---
  async function saveAgentConfig(agentId: string) {
    const override = agentOverrides[agentId];
    if (!override) return;
    setSaving(agentId);
    try {
      const res = await apiFetch(`/admin/swarm/tenants/${tenantId}/agents/${agentId}/configure`, {
        method: "POST",
        body: JSON.stringify({
          system_prompt_override: override.system_prompt_override || null,
          tool_overrides: override.tool_overrides.length > 0 ? override.tool_overrides : null,
        }),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(null);
    }
  }

  // --- Tool toggle ---
  async function toggleTool(toolId: string, currentEnabled: boolean) {
    setSaving(toolId);
    try {
      const res = await apiFetch(`/admin/swarm/tenants/${tenantId}/tools/${toolId}/configure`, {
        method: "POST",
        body: JSON.stringify({ is_enabled: !currentEnabled }),
      });
      if (!res.ok) throw new Error(`Toggle failed (${res.status})`);
      setTools((prev) =>
        prev.map((t) =>
          t.id === toolId
            ? {
                ...t,
                tenant_config: {
                  ...(t.tenant_config || { config: null }),
                  is_enabled: !currentEnabled,
                },
              }
            : t,
        ),
      );
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(null);
    }
  }

  // --- Save tool config ---
  async function saveToolConfig(toolId: string) {
    const raw = toolConfigs[toolId];
    let parsed: Record<string, unknown> | null = null;
    try {
      const p = JSON.parse(raw || "{}");
      if (p && typeof p === "object" && Object.keys(p).length > 0) parsed = p;
    } catch {
      setError("Invalid JSON in tool config");
      return;
    }
    setSaving(toolId);
    try {
      const res = await apiFetch(`/admin/swarm/tenants/${tenantId}/tools/${toolId}/configure`, {
        method: "POST",
        body: JSON.stringify({ config: parsed }),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(null);
    }
  }

  // --- Render config form from config_schema ---
  function renderConfigFields(toolId: string, schema: Record<string, unknown> | null) {
    if (!schema) return <span style={{ fontSize: 12, color: T.textDim }}>No config schema defined for this tool.</span>;
    const props = (schema as { properties?: Record<string, { type?: string; description?: string }> }).properties;
    if (!props) return <span style={{ fontSize: 12, color: T.textDim }}>No properties in schema.</span>;

    let currentConfig: Record<string, unknown> = {};
    try {
      currentConfig = JSON.parse(toolConfigs[toolId] || "{}");
    } catch { /* ignore */ }

    return (
      <div style={{ display: "grid", gap: 10 }}>
        {Object.entries(props).map(([key, prop]) => {
          const val = (currentConfig[key] as string) || "";
          const isSensitive = key.toLowerCase().includes("key") || key.toLowerCase().includes("secret") || key.toLowerCase().includes("password") || key.toLowerCase().includes("token");
          return (
            <div key={key}>
              <label style={labelStyle}>
                {key}
                {prop.description && <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 6, fontSize: 11 }}>{prop.description}</span>}
              </label>
              <input
                style={inputStyle}
                type={isSensitive ? "password" : "text"}
                value={val}
                onChange={(e) => {
                  const updated = { ...currentConfig, [key]: e.target.value };
                  setToolConfigs((prev) => ({ ...prev, [toolId]: JSON.stringify(updated, null, 2) }));
                }}
                placeholder={prop.type || "string"}
              />
            </div>
          );
        })}
      </div>
    );
  }

  const isEnabled = (cfg: { is_enabled: boolean } | null) => cfg?.is_enabled ?? false;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>Swarm Config — Tenant #{tenantId}</span>
      </div>

      {error && (
        <Card hover={false} style={{ padding: 12, borderColor: T.danger }}>
          <span style={{ color: T.danger, fontSize: 13 }}>{error}</span>
          <button onClick={() => setError("")} style={{ marginLeft: 8, color: T.textDim, background: "none", border: "none", cursor: "pointer", fontSize: 11 }}>dismiss</button>
        </Card>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4 }}>
        <button style={tabStyle(tab === "agents")} onClick={() => setTab("agents")}>
          <Bot size={14} style={{ marginRight: 4, verticalAlign: "middle" }} /> Agents
        </button>
        <button style={tabStyle(tab === "tools")} onClick={() => setTab("tools")}>
          <Wrench size={14} style={{ marginRight: 4, verticalAlign: "middle" }} /> Tools
        </button>
      </div>

      {loading ? (
        <div style={{ color: T.textMuted, fontSize: 13, padding: 20 }}>Loading configuration...</div>
      ) : tab === "agents" ? (
        /* ===== AGENTS TAB ===== */
        <div style={{ display: "grid", gap: 8 }}>
          {agents.map((a) => {
            const enabled = isEnabled(a.tenant_config);
            const expanded = expandedAgent === a.id;
            return (
              <Card key={a.id} hover={false} style={{ padding: 0, overflow: "hidden" }}>
                {/* Header row */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    cursor: "pointer",
                  }}
                  onClick={() => setExpandedAgent(expanded ? null : a.id)}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{a.display_name}</span>
                    <Badge variant={enabled ? "success" : "default"} size="xs">{enabled ? "Enabled" : "Disabled"}</Badge>
                    {a.is_system && <Badge variant="info" size="xs">System</Badge>}
                    <Badge variant="default" size="xs">{a.min_plan_tier}</Badge>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleAgent(a.id, enabled); }}
                      style={{ background: "none", border: "none", cursor: "pointer", color: enabled ? T.success : T.textDim }}
                      disabled={saving === a.id}
                    >
                      {enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>
                    {expanded ? <ChevronUp size={16} color={T.textDim} /> : <ChevronDown size={16} color={T.textDim} />}
                  </div>
                </div>

                {/* Expanded config */}
                {expanded && (
                  <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.border}` }}>
                    <div style={{ display: "grid", gap: 12, paddingTop: 12 }}>
                      <div>
                        <label style={labelStyle}>
                          System Prompt Override (Jinja2)
                          <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 8, fontSize: 11 }}>
                            {JINJA_HINTS.join(", ")}
                          </span>
                        </label>
                        <textarea
                          style={{ ...inputStyle, minHeight: 120, resize: "vertical", fontFamily: "monospace", fontSize: 12 }}
                          value={agentOverrides[a.id]?.system_prompt_override || ""}
                          onChange={(e) =>
                            setAgentOverrides((prev) => ({
                              ...prev,
                              [a.id]: { ...prev[a.id], system_prompt_override: e.target.value },
                            }))
                          }
                          placeholder="Leave empty to use default system prompt"
                        />
                      </div>

                      {/* Tool overrides */}
                      <div>
                        <label style={labelStyle}>Tool Overrides (replaces default tools for this tenant)</label>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {allTools.map((t) => {
                            const checked = (agentOverrides[a.id]?.tool_overrides || []).includes(t.id);
                            return (
                              <label
                                key={t.id}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: 4,
                                  padding: "3px 8px",
                                  borderRadius: 6,
                                  border: `1px solid ${checked ? T.accent : T.border}`,
                                  background: checked ? T.accentDim : T.surfaceAlt,
                                  cursor: "pointer",
                                  fontSize: 11,
                                  color: checked ? T.accentLight : T.textMuted,
                                }}
                              >
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={() => {
                                    setAgentOverrides((prev) => {
                                      const cur = prev[a.id]?.tool_overrides || [];
                                      return {
                                        ...prev,
                                        [a.id]: {
                                          ...prev[a.id],
                                          tool_overrides: checked ? cur.filter((x) => x !== t.id) : [...cur, t.id],
                                        },
                                      };
                                    });
                                  }}
                                  style={{ display: "none" }}
                                />
                                {t.display_name}
                              </label>
                            );
                          })}
                        </div>
                      </div>

                      <div style={{ display: "flex", justifyContent: "flex-end" }}>
                        <button
                          onClick={() => saveAgentConfig(a.id)}
                          disabled={saving === a.id}
                          style={{ ...btnStyle, background: T.accent, color: "#fff", opacity: saving === a.id ? 0.6 : 1 }}
                        >
                          <Save size={14} /> {saving === a.id ? "Saving..." : "Save Config"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
          {agents.length === 0 && (
            <Card hover={false} style={{ padding: 32, textAlign: "center" }}>
              <span style={{ color: T.textMuted, fontSize: 13 }}>No agents defined.</span>
            </Card>
          )}
        </div>
      ) : (
        /* ===== TOOLS TAB ===== */
        <div style={{ display: "grid", gap: 8 }}>
          {tools.map((t) => {
            const enabled = isEnabled(t.tenant_config);
            const expanded = expandedTool === t.id;
            return (
              <Card key={t.id} hover={false} style={{ padding: 0, overflow: "hidden" }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    cursor: "pointer",
                  }}
                  onClick={() => setExpandedTool(expanded ? null : t.id)}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{t.display_name}</span>
                    <Badge variant={enabled ? "success" : "default"} size="xs">{enabled ? "Enabled" : "Disabled"}</Badge>
                    {t.category && <Badge variant="default" size="xs">{t.category}</Badge>}
                    {t.required_integration && <Badge variant="info" size="xs">{t.required_integration}</Badge>}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleTool(t.id, enabled); }}
                      style={{ background: "none", border: "none", cursor: "pointer", color: enabled ? T.success : T.textDim }}
                      disabled={saving === t.id}
                    >
                      {enabled ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                    </button>
                    {expanded ? <ChevronUp size={16} color={T.textDim} /> : <ChevronDown size={16} color={T.textDim} />}
                  </div>
                </div>

                {expanded && enabled && (
                  <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.border}` }}>
                    <div style={{ display: "grid", gap: 12, paddingTop: 12 }}>
                      {/* Render config from schema if available */}
                      {t.config_schema ? (
                        renderConfigFields(t.id, t.config_schema)
                      ) : (
                        <div>
                          <label style={labelStyle}>Config (JSON)</label>
                          <textarea
                            style={{ ...inputStyle, minHeight: 100, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
                            value={toolConfigs[t.id] || "{}"}
                            onChange={(e) => setToolConfigs((prev) => ({ ...prev, [t.id]: e.target.value }))}
                          />
                        </div>
                      )}

                      <div style={{ display: "flex", justifyContent: "flex-end" }}>
                        <button
                          onClick={() => saveToolConfig(t.id)}
                          disabled={saving === t.id}
                          style={{ ...btnStyle, background: T.accent, color: "#fff", opacity: saving === t.id ? 0.6 : 1 }}
                        >
                          <Save size={14} /> {saving === t.id ? "Saving..." : "Save Config"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
          {tools.length === 0 && (
            <Card hover={false} style={{ padding: 32, textAlign: "center" }}>
              <span style={{ color: T.textMuted, fontSize: 13 }}>No tools defined.</span>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
