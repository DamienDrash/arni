"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { useRouter } from "next/navigation";
import { Save, ArrowLeft } from "lucide-react";

type ToolFormData = {
  id: string;
  display_name: string;
  description: string;
  category: string;
  required_integration: string;
  min_plan_tier: string;
  config_schema: string; // JSON string for editing
  is_system: boolean;
};

const INTEGRATIONS = [
  "",
  "magicline",
  "calendly",
  "shopify",
  "odoo",
  "stripe",
  "notion",
  "slack",
  "whatsapp",
  "telegram",
  "email",
];

const CATEGORIES = [
  "booking",
  "crm",
  "knowledge",
  "media",
  "social",
  "analytics",
  "billing",
  "communication",
  "erp",
  "other",
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

export default function ToolForm({ toolId }: { toolId?: string }) {
  const router = useRouter();
  const isEdit = !!toolId;
  const [form, setForm] = useState<ToolFormData>({
    id: "",
    display_name: "",
    description: "",
    category: "other",
    required_integration: "",
    min_plan_tier: "starter",
    config_schema: "{}",
    is_system: false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(isEdit);
  const [schemaError, setSchemaError] = useState("");

  const loadTool = useCallback(async () => {
    if (!toolId) return;
    setLoading(true);
    try {
      const res = await apiFetch(`/admin/swarm/tools/${toolId}`);
      if (!res.ok) throw new Error(`Tool not found (${res.status})`);
      const data = await res.json();
      setForm({
        id: data.id,
        display_name: data.display_name,
        description: data.description || "",
        category: data.category || "other",
        required_integration: data.required_integration || "",
        min_plan_tier: data.min_plan_tier,
        config_schema: data.config_schema ? JSON.stringify(data.config_schema, null, 2) : "{}",
        is_system: data.is_system,
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [toolId]);

  useEffect(() => { void loadTool(); }, [loadTool]);

  function update<K extends keyof ToolFormData>(key: K, val: ToolFormData[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function validateSchema(val: string) {
    update("config_schema", val);
    try {
      JSON.parse(val);
      setSchemaError("");
    } catch {
      setSchemaError("Invalid JSON");
    }
  }

  async function save() {
    setError("");
    if (!form.display_name.trim()) { setError("Display name is required"); return; }
    if (!isEdit && !form.id.trim()) { setError("ID is required"); return; }

    let parsedSchema: Record<string, unknown> | null = null;
    try {
      const parsed = JSON.parse(form.config_schema);
      if (parsed && typeof parsed === "object" && Object.keys(parsed).length > 0) {
        parsedSchema = parsed;
      }
    } catch {
      setError("Config schema must be valid JSON");
      return;
    }

    setSaving(true);
    try {
      const payload = isEdit
        ? {
            display_name: form.display_name,
            description: form.description || null,
            category: form.category || null,
            required_integration: form.required_integration || null,
            min_plan_tier: form.min_plan_tier,
            config_schema: parsedSchema,
          }
        : {
            id: form.id,
            display_name: form.display_name,
            description: form.description || null,
            category: form.category || null,
            required_integration: form.required_integration || null,
            min_plan_tier: form.min_plan_tier,
            config_schema: parsedSchema,
            is_system: false,
          };

      const url = isEdit ? `/admin/swarm/tools/${toolId}` : "/admin/swarm/tools";
      const method = isEdit ? "PATCH" : "POST";
      const res = await apiFetch(url, { method, body: JSON.stringify(payload) });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Save failed (${res.status})`);
      }
      router.push("/swarm/tools");
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <div style={{ color: T.textMuted, padding: 20 }}>Loading...</div>;

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 800 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          onClick={() => router.push("/swarm/tools")}
          style={{ ...btnStyle, background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}
        >
          <ArrowLeft size={14} /> Back
        </button>
        <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>
          {isEdit ? `Edit Tool: ${toolId}` : "New Tool"}
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
              <label style={labelStyle}>Tool ID (slug, cannot be changed later)</label>
              <input
                style={inputStyle}
                value={form.id}
                onChange={(e) => update("id", e.target.value.replace(/[^a-z0-9_-]/g, ""))}
                placeholder="e.g. odoo_crm, knowledge_search"
                maxLength={64}
              />
            </div>
          )}

          <div>
            <label style={labelStyle}>Display Name</label>
            <input style={inputStyle} value={form.display_name} onChange={(e) => update("display_name", e.target.value)} placeholder="e.g. Odoo CRM Lookup" />
          </div>

          <div>
            <label style={labelStyle}>Description</label>
            <textarea style={{ ...inputStyle, minHeight: 60, resize: "vertical" }} value={form.description} onChange={(e) => update("description", e.target.value)} placeholder="What does this tool do?" />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Category</label>
              <select style={inputStyle} value={form.category} onChange={(e) => update("category", e.target.value)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Required Integration</label>
              <select style={inputStyle} value={form.required_integration} onChange={(e) => update("required_integration", e.target.value)}>
                {INTEGRATIONS.map((i) => (
                  <option key={i} value={i}>{i || "(none)"}</option>
                ))}
              </select>
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

          {/* Config Schema JSON Editor */}
          <div>
            <label style={labelStyle}>
              Config Schema (JSON)
              <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 8, fontSize: 11 }}>
                Defines tenant-level configuration fields for this tool
              </span>
            </label>
            <textarea
              style={{
                ...inputStyle,
                minHeight: 160,
                resize: "vertical",
                fontFamily: "monospace",
                fontSize: 12,
                borderColor: schemaError ? T.danger : T.border,
              }}
              value={form.config_schema}
              onChange={(e) => validateSchema(e.target.value)}
              placeholder='{"type": "object", "properties": {"api_key": {"type": "string"}, "endpoint_url": {"type": "string"}}}'
            />
            {schemaError && (
              <span style={{ fontSize: 11, color: T.danger, marginTop: 4, display: "block" }}>{schemaError}</span>
            )}
          </div>
        </div>
      </Card>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button
          onClick={() => router.push("/swarm/tools")}
          style={{ ...btnStyle, background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}
        >
          Cancel
        </button>
        <button
          onClick={save}
          disabled={saving || !!schemaError}
          style={{ ...btnStyle, background: T.accent, color: "#fff", opacity: saving ? 0.6 : 1 }}
        >
          <Save size={14} /> {saving ? "Saving..." : "Save Tool"}
        </button>
      </div>
    </div>
  );
}
