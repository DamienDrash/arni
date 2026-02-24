"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import { 
  Download, Search, X, Calendar, Filter, 
  ShieldCheck, User, Activity, Tag, Layers,
  ChevronDown, ChevronUp, Clock, Eye, Info
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";

type AuditRow = {
  id: number;
  created_at: string | null;
  actor_email: string | null;
  action: string;
  category: string;
  target_type: string | null;
  target_id: string | null;
  details_json: string | null;
};

const filterHeaderStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: 11,
  fontWeight: 800,
  color: "#64748B",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 8
};

const customSelectStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid #E2E8F0`,
  background: "#FFFFFF",
  color: "#1E293B",
  fontSize: 13,
  padding: "8px 10px",
  outline: "none",
  appearance: "none",
  backgroundImage: "url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20width%3D%22292.4%22%20height%3D%22292.4%22%3E%3Cpath%20fill%3D%22%2364748B%22%20d%3D%22M287%2069.4a17.6%2017.6%200%200%200-13-7.4H18.4c-5%200-9.3%201.8-12.9%205.4A17.6%2017.6%200%200%200%200%2082.2c0%205%201.8%209.3%205.4%2012.9l128%20127.9c3.6%203.6%207.8%205.4%2012.8%205.4s9.2-1.8%2012.8-5.4L287%2095c3.5-3.5%205.4-7.8%205.4-12.8%200-5-1.9-9.2-5.5-12.8z%22/%3E%3C/svg%3E')",
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 10px top 50%",
  backgroundSize: "10px auto",
};

export default function AuditPage() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [query, setQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("all");
  const [actorFilter, setActorFilter] = useState("all");
  const [targetTypeFilter, setTargetTypeFilter] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [selectedRow, setSelectedRow] = useState<AuditRow | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch("/admin/audit?limit=500");
      if (!res.ok) throw new Error(`Audit load failed (${res.status})`);
      const data = await res.json();
      setRows(data.items || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  const options = useMemo(() => ({
    categories: Array.from(new Set(rows.map(r => r.category).filter((v): v is string => Boolean(v)))).sort(),
    actions: Array.from(new Set(rows.map(r => r.action).filter((v): v is string => Boolean(v)))).sort(),
    actors: Array.from(new Set(rows.map(r => r.actor_email).filter((v): v is string => Boolean(v)))).sort(),
    targetTypes: Array.from(new Set(rows.map(r => r.target_type).filter((v): v is string => Boolean(v)))).sort(),
  }), [rows]);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = rows.filter((r) => {
      if (categoryFilter !== "all" && r.category !== categoryFilter) return false;
      if (actionFilter !== "all" && r.action !== actionFilter) return false;
      if (actorFilter !== "all" && (r.actor_email || "system") !== actorFilter) return false;
      if (targetTypeFilter !== "all" && (r.target_type || "") !== targetTypeFilter) return false;

      if (startDate && r.created_at && new Date(r.created_at) < new Date(startDate)) return false;
      if (endDate && r.created_at) {
        const end = new Date(endDate);
        end.setDate(end.getDate() + 1);
        if (new Date(r.created_at) >= end) return false;
      }

      if (!q) return true;
      return (
        String(r.actor_email || "").toLowerCase().includes(q) ||
        String(r.action || "").toLowerCase().includes(q) ||
        String(r.category || "").toLowerCase().includes(q) ||
        String(r.target_type || "").toLowerCase().includes(q) ||
        String(r.target_id || "").toLowerCase().includes(q) ||
        String(r.details_json || "").toLowerCase().includes(q)
      );
    });
    return list.sort((a, b) => {
      const at = Date.parse(a.created_at || "");
      const bt = Date.parse(b.created_at || "");
      return sortDir === "desc" ? bt - at : at - bt;
    });
  }, [rows, query, categoryFilter, actionFilter, actorFilter, targetTypeFilter, startDate, endDate, sortDir]);

  function downloadCsv() {
    const header = ["Timestamp", "Actor", "Action", "Category", "Target", "Details"];
    const lines = filteredRows.map((r) =>
      [r.created_at, r.actor_email, r.action, r.category, `${r.target_type}:${r.target_id}`, r.details_json]
        .map(v => `"${String(v || "").replace(/"/g, '""')}"`)
        .join(",")
    );
    const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ariia-audit-export.csv`;
    link.click();
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 24 }}>
      {/* SaaS Governance Sidebar */}
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <Card style={{ padding: 24, position: "sticky", top: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "#6C5CE715", display: "flex", alignItems: "center", justifyContent: "center", color: "#6C5CE7" }}>
              <ShieldCheck size={18} />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 800, color: "#1E293B", margin: 0 }}>Governance</h2>
              <p style={{ fontSize: 11, color: "#64748B", margin: 0 }}>Compliance & Audit Trail</p>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={filterHeaderStyle}><Tag size={12} /> Category</label>
              <select style={customSelectStyle} value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
                <option value="all">All Categories</option>
                {options.categories.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div>
              <label style={filterHeaderStyle}><Activity size={12} /> Action Type</label>
              <select style={customSelectStyle} value={actionFilter} onChange={e => setActionFilter(e.target.value)}>
                <option value="all">All Actions</option>
                {options.actions.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            <div>
              <label style={filterHeaderStyle}><User size={12} /> Initiated By (Actor)</label>
              <select style={customSelectStyle} value={actorFilter} onChange={e => setActorFilter(e.target.value)}>
                <option value="all">All Users</option>
                <option value="system">System Internal</option>
                {options.actors.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            <div style={{ height: 1, background: "#F1F5F9", margin: "8px 0" }} />

            <div>
              <label style={filterHeaderStyle}><Calendar size={12} /> Time Range</label>
              <div style={{ display: "grid", gap: 8 }}>
                <input type="date" style={inputStyle} value={startDate} onChange={e => setStartDate(e.target.value)} placeholder="From" />
                <input type="date" style={inputStyle} value={endDate} onChange={e => setEndDate(e.target.value)} placeholder="To" />
              </div>
            </div>

            <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
              <button onClick={() => {
                setCategoryFilter("all"); setActionFilter("all"); setActorFilter("all");
                setStartDate(""); setEndDate(""); setQuery("");
              }} className="btn btn-sm btn-ghost gap-2 text-xs">
                <X size={14} /> Clear All Filters
              </button>
              <button onClick={downloadCsv} className="btn btn-sm btn-outline gap-2 text-xs">
                <Download size={14} /> Export CSV
              </button>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Log View */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{ flex: 1, position: "relative" }}>
            <Search size={16} color="#94A3B8" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }} />
            <input 
              style={{ ...inputStyle, paddingLeft: 40, height: 44, fontSize: 14 }}
              placeholder="Search by action, email, or metadata content..."
              value={query}
              onChange={e => setQuery(e.target.value)}
            />
          </div>
          <button onClick={() => setSortDir(s => s === "desc" ? "asc" : "desc")} className="btn h-[44px] bg-white border-slate-200 gap-2">
            <Clock size={16} /> {sortDir === "desc" ? "Newest" : "Oldest"}
          </button>
        </div>

        <Card style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ background: "#F8FAFC", borderBottom: "1px solid #E2E8F0" }}>
              <tr>
                {["Timestamp", "Actor", "Operation", "Target", "Details"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 16px", fontSize: 10, fontWeight: 800, color: "#64748B", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5} style={{ padding: 40, textAlign: "center", color: "#94A3B8" }}>Fetching audit records...</td></tr>
              ) : filteredRows.map(r => (
                <tr key={r.id} style={{ borderBottom: "1px solid #F1F5F9" }} className="hover:bg-slate-50 transition-colors">
                  <td style={{ padding: "14px 16px", fontSize: 12, color: "#64748B", whiteSpace: "nowrap" }}>
                    {r.created_at ? new Date(r.created_at).toLocaleString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit", day: "2-digit", month: "2-digit" }) : "-"}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 24, height: 24, borderRadius: 12, background: "#F1F5F9", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700 }}>
                        {(r.actor_email || "S")[0].toUpperCase()}
                      </div>
                      <span style={{ fontSize: 13, fontWeight: 600, color: "#1E293B" }}>{r.actor_email || "System"}</span>
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                      <Badge variant={categoryToVariant(r.category)} size="xs">{r.action}</Badge>
                      <span style={{ fontSize: 10, color: "#94A3B8", marginLeft: 4 }}>{r.category}</span>
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Layers size={12} color="#94A3B8" />
                      <span style={{ fontSize: 12, color: "#475569" }}>{r.target_type || "N/A"}</span>
                      {r.target_id && <Badge variant="default" size="xs">#{r.target_id}</Badge>}
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right" }}>
                    <button onClick={() => setSelectedRow(r)} className="btn btn-xs btn-ghost gap-1 font-bold text-accent">
                      <Eye size={12} /> View Diff
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>

      <Modal
        open={!!selectedRow}
        onClose={() => setSelectedRow(null)}
        title="Audit Event Details"
        subtitle={selectedRow ? `${selectedRow.action} @ ${selectedRow.created_at}` : ""}
        width="min(800px, 100%)"
      >
        {selectedRow && (
          <div style={{ display: "grid", gap: 20 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
               <div style={{ padding: 16, borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                  <label style={labelStyle}>Actor Identity</label>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#1E293B" }}>{selectedRow.actor_email || "System Internal"}</div>
               </div>
               <div style={{ padding: 16, borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                  <label style={labelStyle}>Target Resource</label>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "#1E293B" }}>{selectedRow.target_type || "None"} ({selectedRow.target_id || "-"})</div>
               </div>
            </div>

            <div>
              <label style={labelStyle}>Change Summary</label>
              <div style={{ padding: 16, borderRadius: 12, background: "#0F172A", color: "#F8FAFC", fontSize: 12, fontFamily: "monospace", overflowX: "auto" }}>
                <pre>{formatJson(selectedRow.details_json)}</pre>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function categoryToVariant(cat: string): "default" | "success" | "warning" | "danger" | "info" | "accent" {
  const c = cat.toLowerCase();
  if (c.includes("security") || c.includes("auth")) return "danger";
  if (c.includes("tenant") || c.includes("plan")) return "accent";
  if (c.includes("knowledge") || c.includes("prompt")) return "info";
  if (c.includes("settings")) return "warning";
  return "default";
}

function formatJson(raw: string | null) {
  if (!raw) return "// No details provided";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid #E2E8F0`,
  background: "#FFFFFF",
  color: "#1E293B",
  fontSize: 13,
  padding: "8px 12px",
  outline: "none",
};

const labelStyle: React.CSSProperties = {
  fontSize: 10,
  fontWeight: 800,
  color: "#94A3B8",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  marginBottom: 4,
  display: "block"
};
