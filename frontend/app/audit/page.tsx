"use client";

import { useEffect, useMemo, useState } from "react";
import { Download, Search, X, Calendar, Filter } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Modal } from "@/components/ui/Modal";
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

  useEffect(() => {
    apiFetch("/auth/audit?limit=300")
      .then(async (res) => {
        if (!res.ok) throw new Error(`Audit load failed (${res.status})`);
        return res.json();
      })
      .then((data) => setRows(Array.isArray(data) ? data : []))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const categoryOptions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.category).filter(Boolean))).sort(),
    [rows],
  );
  const actionOptions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.action).filter(Boolean))).sort(),
    [rows],
  );
  const actorOptions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.actor_email).filter((v): v is string => Boolean(v)))).sort(),
    [rows],
  );
  const targetTypeOptions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.target_type).filter((v): v is string => Boolean(v)))).sort(),
    [rows],
  );
  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const row of rows) counts.set(row.category, (counts.get(row.category) || 0) + 1);
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = rows.filter((r) => {
      if (categoryFilter !== "all" && r.category !== categoryFilter) return false;
      if (actionFilter !== "all" && r.action !== actionFilter) return false;
      if (actorFilter !== "all" && (r.actor_email || "system") !== actorFilter) return false;
      if (targetTypeFilter !== "all" && (r.target_type || "") !== targetTypeFilter) return false;

      if (startDate && r.created_at) {
        if (new Date(r.created_at) < new Date(startDate)) return false;
      }
      if (endDate && r.created_at) {
        // Add 1 day to end date to make it inclusive of the selected day
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
      if (Number.isNaN(at) || Number.isNaN(bt)) return 0;
      return sortDir === "desc" ? bt - at : at - bt;
    });
  }, [rows, query, categoryFilter, actionFilter, actorFilter, targetTypeFilter, startDate, endDate, sortDir]);

  function resetFilters() {
    setQuery("");
    setCategoryFilter("all");
    setActionFilter("all");
    setActorFilter("all");
    setTargetTypeFilter("all");
    setStartDate("");
    setEndDate("");
    setSortDir("desc");
  }

  function downloadCsv() {
    const header = ["id", "created_at", "actor_email", "action", "category", "target_type", "target_id", "details_json"];
    const lines = filteredRows.map((r) =>
      [r.id, r.created_at || "", r.actor_email || "", r.action, r.category, r.target_type || "", r.target_id || "", r.details_json || ""]
        .map((value) => `"${String(value).replaceAll('"', '""')}"`)
        .join(","),
    );
    const csv = [header.join(","), ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `arni-audit-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[300px_1fr] gap-6">
      {/* Sidebar Filters */}
      <Card className="flex flex-col gap-5 p-5 h-fit bg-surfaceAlt border-border border">
        <div className="flex items-center gap-2 font-bold text-lg text-text mb-2">
          <Filter size={18} />
          <span>Governance Filter</span>
        </div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Kategorie</span></label>
          <select className="select select-bordered select-sm w-full" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
            <option value="all">Alle</option>
            {categoryOptions.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Action</span></label>
          <select className="select select-bordered select-sm w-full" value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
            <option value="all">Alle</option>
            {actionOptions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Actor (Benutzer)</span></label>
          <select className="select select-bordered select-sm w-full" value={actorFilter} onChange={(e) => setActorFilter(e.target.value)}>
            <option value="all">Alle</option>
            <option value="system">System</option>
            {actorOptions.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Target Typ</span></label>
          <select className="select select-bordered select-sm w-full" value={targetTypeFilter} onChange={(e) => setTargetTypeFilter(e.target.value)}>
            <option value="all">Alle</option>
            {targetTypeOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="divider my-0 border-border"></div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Zeitraum (Von)</span></label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-textDim pointer-events-none" size={14} />
            <input type="date" className="input input-sm input-bordered w-full pl-9" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
        </div>

        <div className="form-control w-full">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Zeitraum (Bis)</span></label>
          <div className="relative">
            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-textDim pointer-events-none" size={14} />
            <input type="date" className="input input-sm input-bordered w-full pl-9" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
        </div>

        <div className="form-control w-full mt-2">
          <label className="label pt-0 pb-1"><span className="label-text font-semibold text-xs text-textDim uppercase tracking-widest">Sortierung</span></label>
          <select className="select select-bordered select-sm w-full" value={sortDir} onChange={(e) => setSortDir(e.target.value as "desc" | "asc")}>
            <option value="desc">Zeit: Neueste zuerst</option>
            <option value="asc">Zeit: Älteste zuerst</option>
          </select>
        </div>

        <div className="flex flex-col gap-2 mt-4">
          <button type="button" onClick={resetFilters} className="btn btn-ghost border-border btn-sm w-full">
            <X size={14} /> Filter zurücksetzen
          </button>
          <button type="button" onClick={downloadCsv} className="btn btn-primary btn-sm w-full">
            <Download size={14} /> Export CSV
          </button>
        </div>
      </Card>

      {/* Main Table Content */}
      <div className="flex flex-col gap-4 min-w-0">
        {/* Quick Category Chips & Search bar */}
        <div className="flex flex-col xl:flex-row gap-4 justify-between items-start xl:items-center">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setCategoryFilter("all")}
              className={`badge badge-lg cursor-pointer transition-colors ${categoryFilter === "all" ? "badge-primary text-primary-content border-none" : "badge-outline border-border"}`}
            >
              Alle ({rows.length})
            </button>
            {categoryCounts.slice(0, 5).map(([category, count]) => (
              <button
                key={category}
                type="button"
                onClick={() => setCategoryFilter(category)}
                className={`badge badge-lg cursor-pointer transition-colors ${categoryFilter === category ? "badge-primary text-primary-content border-none" : "badge-outline border-border"}`}
              >
                {category} ({count})
              </button>
            ))}
          </div>

          <div className="relative w-full xl:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-textDim" size={16} />
            <input
              type="text"
              className="input input-bordered w-full pl-10"
              placeholder="Suche in Actor, Action, Resource..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>

        <Card className="p-0 overflow-auto flex-1 border border-border shadow-sm">
          {error && <div className="p-4 text-error text-sm">{error}</div>}
          {loading && <div className="p-4 text-textDim text-sm">Lade Audit-Einträge…</div>}

          <table className="table w-full">
            <thead className="bg-surfaceAlt sticky top-0 z-10 text-textDim shadow-sm">
              <tr>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Zeit</th>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Actor</th>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Action</th>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Kategorie</th>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Target</th>
                <th className="font-semibold tracking-wider uppercase text-[11px] py-3">Details</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((r) => (
                <tr key={r.id} className="border-b border-border hover:bg-surfaceAlt/50 transition-colors">
                  <td className="whitespace-nowrap text-sm text-text">{r.created_at ? new Date(r.created_at).toLocaleString("de-DE", { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : "-"}</td>
                  <td className="font-medium text-sm text-text">{r.actor_email || "-"}</td>
                  <td className="text-sm text-text"><span className="badge badge-sm badge-ghost border-border font-medium bg-surface">{r.action}</span></td>
                  <td className="text-sm text-textDim">{r.category}</td>
                  <td className="text-sm text-text">{r.target_type || "-"} <span className="text-textMuted text-xs ml-1">{r.target_id || ""}</span></td>
                  <td className="whitespace-normal max-w-[400px]">
                    <div className="flex flex-col items-start gap-2">
                      {summarizeAuditDetails(r.details_json) && (
                        <div className="text-xs text-textDim truncate w-full">{summarizeAuditDetails(r.details_json)}</div>
                      )}
                      <button
                        type="button"
                        onClick={() => setSelectedRow(r)}
                        className="btn btn-xs btn-outline border-border text-text font-semibold hover:bg-surfaceAlt"
                      >
                        Details & Diff
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && filteredRows.length === 0 && (
                <tr><td colSpan={6} className="p-6 text-center text-textDim text-sm">Keine Audit-Einträge für den aktuellen Filter.</td></tr>
              )}
            </tbody>
          </table>
        </Card>
      </div>

      <Modal
        open={!!selectedRow}
        onClose={() => setSelectedRow(null)}
        title={selectedRow ? `${selectedRow.category} · ${selectedRow.action}` : "Audit Detail"}
        subtitle={selectedRow ? `${selectedRow.created_at ? new Date(selectedRow.created_at).toLocaleString("de-DE") : "-"} · Actor: ${selectedRow.actor_email || "system"}` : ""}
        width="min(820px, 100%)"
      >
        {selectedRow && (
          <div className="grid gap-6 mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-textDim uppercase tracking-widest font-semibold mb-1">Target Resource</div>
                <div className="text-text bg-surfaceAlt p-2 rounded-lg border border-border inline-block px-3">
                  {selectedRow.target_type || "-"} <span className="text-textMuted text-sm ml-2">{selectedRow.target_id || ""}</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-textDim uppercase tracking-widest font-semibold mb-1">Actor ID</div>
                <div className="text-text p-2">{selectedRow.actor_email || "system-internal"}</div>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="text-xs text-textDim uppercase tracking-widest font-semibold">Strukturierter Diff</div>
              <div className="grid gap-3">
                {extractDiffRows(selectedRow.details_json).length === 0 ? (
                  <div className="text-sm text-textDim italic p-4 bg-surfaceAlt rounded-xl border border-border border-dashed">Keine Änderungen bzw. kein strukturierter Diff in den Metadaten verfügbar.</div>
                ) : (
                  <div className="overflow-hidden border border-border rounded-xl">
                    <table className="table table-sm w-full bg-surfaceAlt m-0">
                      <thead className="bg-[#181920] border-b border-border text-textDim">
                        <tr>
                          <th className="w-1/4">Feld</th>
                          <th className="w-3/8 text-error bg-error/10">Alt (Before)</th>
                          <th className="w-3/8 text-success bg-success/10">Neu (After)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractDiffRows(selectedRow.details_json).map((row) => (
                          <tr key={row.key} className="border-b border-border hover:bg-surface">
                            <td className="font-mono text-xs text-textDim">{row.key}</td>
                            <td className="text-sm text-text bg-error/5 break-all">{row.before || <span className="italic opacity-50">null</span>}</td>
                            <td className="text-sm text-text bg-success/5 font-medium break-all">{row.after || <span className="italic opacity-50">null</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <div className="text-xs text-textDim uppercase tracking-widest font-semibold">Raw JSON Payload</div>
              <pre className="m-0 rounded-xl border border-border bg-[#0a0b0f] text-text text-xs leading-relaxed p-4 overflow-auto max-h-[300px]">
                {formatJson(selectedRow.details_json)}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function formatJson(raw: string | null) {
  if (!raw) return "-";
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function summarizeAuditDetails(raw: string | null): string {
  if (!raw) return "";
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const reason = typeof parsed.reason === "string" ? parsed.reason.trim() : "";
    if (reason) return reason;
    const keys = Object.keys(parsed);
    return keys.length ? `Felder: ${keys.slice(0, 4).join(", ")}` : "";
  } catch {
    return raw.length > 120 ? `${raw.slice(0, 117)}...` : raw;
  }
}

function extractDiffRows(raw: string | null): Array<{ key: string; before: string; after: string }> {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const rows: Array<{ key: string; before: string; after: string }> = [];
    const oldValue = parsed.old_value as Record<string, unknown> | string | number | boolean | null | undefined;
    const newValue = parsed.new_value as Record<string, unknown> | string | number | boolean | null | undefined;
    if (oldValue !== undefined || newValue !== undefined) {
      if (typeof oldValue === "object" && oldValue && typeof newValue === "object" && newValue) {
        const keys = new Set([...Object.keys(oldValue), ...Object.keys(newValue)]);
        for (const key of keys) {
          const before = String((oldValue as Record<string, unknown>)[key] ?? "");
          const after = String((newValue as Record<string, unknown>)[key] ?? "");
          if (before !== after) rows.push({ key, before, after });
        }
        return rows.slice(0, 12);
      }
      rows.push({
        key: String(parsed.key || parsed.target_id || "value"),
        before: String(oldValue ?? ""),
        after: String(newValue ?? ""),
      });
      return rows;
    }
    return [];
  } catch {
    return [];
  }
}
