"use client";

import { useCallback, useEffect, useState } from "react";
import { Wrench, Plus, Pencil, Trash2, Shield } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { useRouter } from "next/navigation";

type ToolRow = {
  id: string;
  display_name: string;
  description: string | null;
  category: string | null;
  required_integration: string | null;
  min_plan_tier: string;
  config_schema: Record<string, unknown> | null;
  is_system: boolean;
  created_at: string | null;
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
  transition: "all 0.2s ease",
};

export default function SwarmToolsPage() {
  const router = useRouter();
  const user = getStoredUser();
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/admin/swarm/tools");
      if (!res.ok) throw new Error(`Failed to load tools (${res.status})`);
      setTools(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (user?.role !== "system_admin") {
    return <div style={{ padding: 40, color: T.danger }}>Access denied. System admin only.</div>;
  }

  async function deleteTool(id: string) {
    if (!confirm(`Delete tool "${id}"? This cannot be undone.`)) return;
    try {
      const res = await apiFetch(`/admin/swarm/tools/${id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) throw new Error(`Delete failed (${res.status})`);
      setTools((prev) => prev.filter((t) => t.id !== id));
    } catch (e) {
      setError(String(e));
    }
  }

  const tierVariant = (tier: string) =>
    tier === "enterprise" ? "accent" : tier === "pro" ? "warning" : "default";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Wrench size={20} color={T.accent} />
          <span style={{ fontSize: 18, fontWeight: 700, color: T.text }}>Swarm Tool Definitions</span>
        </div>
        <button
          onClick={() => router.push("/swarm/tools/new")}
          style={{ ...btnStyle, background: T.accent, color: "#fff" }}
        >
          <Plus size={14} /> New Tool
        </button>
      </div>

      {error && (
        <Card hover={false} style={{ padding: 12, borderColor: T.danger }}>
          <span style={{ color: T.danger, fontSize: 13 }}>{error}</span>
        </Card>
      )}

      {loading ? (
        <div style={{ color: T.textMuted, fontSize: 13, padding: 20 }}>Loading tools...</div>
      ) : tools.length === 0 ? (
        <Card hover={false} style={{ padding: 32, textAlign: "center" }}>
          <span style={{ color: T.textMuted, fontSize: 13 }}>No tools defined yet.</span>
        </Card>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {/* Header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 2fr 100px 120px 80px 80px 90px",
              gap: 12,
              padding: "8px 16px",
              fontSize: 11,
              fontWeight: 600,
              color: T.textDim,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            <span>ID</span>
            <span>Name</span>
            <span>Category</span>
            <span>Integration</span>
            <span>Tier</span>
            <span>Type</span>
            <span style={{ textAlign: "right" }}>Actions</span>
          </div>
          {tools.map((t) => (
            <Card key={t.id} hover={false} style={{ padding: "12px 16px" }}>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 2fr 100px 120px 80px 80px 90px",
                  gap: 12,
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 600, color: T.accentLight, fontFamily: "monospace" }}>
                  {t.id}
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{t.display_name}</div>
                  {t.description && (
                    <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.description}
                    </div>
                  )}
                </div>
                <Badge variant="default" size="xs">{t.category || "-"}</Badge>
                <span style={{ fontSize: 12, color: T.textMuted }}>{t.required_integration || "-"}</span>
                <Badge variant={tierVariant(t.min_plan_tier)} size="xs">{t.min_plan_tier}</Badge>
                <div>
                  {t.is_system ? (
                    <Badge variant="info" size="xs"><Shield size={10} /> System</Badge>
                  ) : (
                    <Badge variant="default" size="xs">Custom</Badge>
                  )}
                </div>
                <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                  <button
                    onClick={() => router.push(`/swarm/tools/${t.id}/edit`)}
                    style={{ ...btnStyle, padding: "5px 10px", background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}` }}
                    title="Edit"
                  >
                    <Pencil size={13} />
                  </button>
                  {!t.is_system && (
                    <button
                      onClick={() => deleteTool(t.id)}
                      style={{ ...btnStyle, padding: "5px 10px", background: T.dangerDim, color: T.danger, border: `1px solid transparent` }}
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
