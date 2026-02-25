"use client";

import { useEffect, useState, useMemo } from "react";
import { Brain, FileText, Save, RefreshCw, AlertCircle, ShieldCheck, History, Search, Plus, Trash2, Database, ChevronRight, Check } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { useI18n } from "@/lib/i18n/LanguageContext";

type MemoryMeta = {
  cron_enabled: boolean;
  cron_expr: string;
  llm_enabled: boolean;
  llm_model: string;
  last_run_at: string;
  last_run_status: string;
  last_run_error: string;
};

export default function MemberMemoryPage() {
  const { t } = useI18n();
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedId] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [baseMtime, setBaseMtime] = useState<number | null>(null);
  const [meta, setMeta] = useState<MemoryMeta | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [reason, setReason] = useState("");

  async function loadData() {
    setLoading(true);
    try {
      const [fRes, mRes] = await Promise.all([
        apiFetch("/admin/member-memory"),
        apiFetch("/admin/member-memory/status")
      ]);
      if (fRes.ok) setFiles(await fRes.json());
      if (mRes.ok) setMeta(await mRes.json());
    } finally {
      setLoading(false);
    }
  }

  async function loadFile(id: string) {
    setLoadingFile(true);
    setError("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${id}`);
      if (res.ok) {
        const data = await res.json();
        setContent(data.content);
        setBaseMtime(data.mtime);
        setSelectedId(id);
        setReason("");
      }
    } finally {
      setLoadingFile(false);
    }
  }

  async function saveFile() {
    if (!selectedFile || !reason.trim() || reason.length < 8) {
      setError(t("memberMemory.reasonPlaceholder"));
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch(`/admin/member-memory/file/${selectedFile}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, base_mtime: baseMtime, reason })
      });
      if (res.ok) {
        const data = await res.json();
        setBaseMtime(data.mtime);
        setReason("");
        alert(t("common.confirmed"));
      } else {
        const data = await res.json();
        setError(data.detail || t("ai.errors.saveFailed"));
      }
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  const filteredFiles = useMemo(() => {
    return files.filter(f => f.toLowerCase().includes(search.toLowerCase()));
  }, [files, search]);

  const runColor = meta?.last_run_status === "ok" ? T.success : meta?.last_run_status.startsWith("error") ? T.danger : T.textDim;

  if (loading) return <div className="p-12 text-center text-slate-500 font-medium">{t("common.loading")}</div>;

  return (
    <div className="flex flex-col gap-6">
      <SectionHeader 
        title={t("memberMemory.title")} 
        subtitle={t("memberMemory.subtitle")}
        action={
          <button 
            disabled={running}
            onClick={async () => {
              setRunning(true);
              const res = await apiFetch("/admin/member-memory/analyze-now", { method: "POST" });
              if (res.ok) { alert(t("common.confirmed")); loadData(); }
              setRunning(false);
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-bold flex items-center gap-2 transition-all shadow-lg shadow-indigo-500/20"
          >
            {running ? <RefreshCw size={16} className="animate-spin" /> : <Brain size={16} />}
            Analyse jetzt starten
          </button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-4 flex items-center justify-between border-slate-800/50 bg-slate-900/20">
          <div><div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{t("memberMemory.files")}</div><div className="text-2xl font-black text-white">{files.length}</div></div>
          <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center text-indigo-400"><FileText size={20} /></div>
        </Card>
        <Card className="p-4 flex items-center justify-between border-slate-800/50 bg-slate-900/20">
          <div><div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{t("memberMemory.scheduler")}</div><div className={`text-sm font-bold ${meta?.cron_enabled ? "text-emerald-400" : "text-amber-400"}`}>{meta?.cron_enabled ? t("common.active") : t("common.paused")}</div></div>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${meta?.cron_enabled ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"}`}><RefreshCw size={20} /></div>
        </Card>
        <Card className="p-4 flex items-center justify-between border-slate-800/50 bg-slate-900/20">
          <div><div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{t("memberMemory.lastRun")}</div><div className="text-xs font-bold text-white" style={{ color: runColor }}>{meta?.last_run_status || t("common.never")}</div></div>
          <div className="w-10 h-10 bg-slate-800 rounded-xl flex items-center justify-center text-slate-400"><History size={20} /></div>
        </Card>
      </div>

      <div className="flex gap-6 h-[600px]">
        {/* Sidebar */}
        <Card className="w-80 flex flex-col p-0 overflow-hidden border-slate-800/50 bg-slate-900/20">
          <div className="p-4 border-b border-white/5 bg-white/5">
            <div className="relative">
              <Search className="absolute left-3 top-2.5 text-slate-500" size={14} />
              <input 
                className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-9 pr-4 py-2 text-xs text-white outline-none focus:border-indigo-500"
                placeholder={t("common.search")}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
            {filteredFiles.map(f => (
              <button 
                key={f}
                onClick={() => loadFile(f)}
                className={`w-full text-left px-4 py-3 rounded-xl text-xs font-bold transition-all flex items-center justify-between group ${
                  selectedFile === f ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20" : "text-slate-400 hover:bg-white/5"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Database size={14} className={selectedFile === f ? "text-indigo-200" : "text-slate-600"} />
                  <span className="truncate">{f.replace('.md', '')}</span>
                </div>
                <ChevronRight size={14} className={`transition-transform ${selectedFile === f ? "translate-x-0" : "-translate-x-2 opacity-0 group-hover:opacity-100 group-hover:translate-x-0"}`} />
              </button>
            ))}
            {filteredFiles.length === 0 && <div className="p-8 text-center text-slate-600 text-xs italic">{t("memberMemory.noFiles")}</div>}
          </div>
        </Card>

        {/* Editor Area */}
        <Card className="flex-1 flex flex-col p-0 overflow-hidden border-slate-800/50 bg-slate-950/50">
          {selectedFile ? (
            <>
              <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/5">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-indigo-500/20 rounded-lg flex items-center justify-center text-indigo-400"><FileText size={16} /></div>
                  <div>
                    <div className="text-xs font-bold text-white">{selectedFile}</div>
                    <div className="text-[9px] text-slate-500 font-black uppercase tracking-widest">Markdown Context</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="relative w-64">
                    <History className="absolute left-2.5 top-2 text-slate-500" size={12} />
                    <input 
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-[10px] text-white outline-none focus:border-indigo-500"
                      placeholder={t("memberMemory.reasonPlaceholder")}
                      value={reason}
                      onChange={e => setReason(e.target.value)}
                    />
                  </div>
                  <button 
                    onClick={saveFile}
                    disabled={saving || reason.length < 8}
                    className="flex items-center gap-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-indigo-500/20 disabled:opacity-30 transition-all"
                  >
                    {saving ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
                    {t("common.save")}
                  </button>
                </div>
              </div>
              <textarea 
                className="flex-1 bg-transparent p-6 text-slate-300 font-mono text-sm outline-none resize-none custom-scrollbar"
                value={content}
                onChange={e => setContent(e.target.value)}
                spellCheck={false}
              />
              {error && <div className="p-3 bg-red-500/10 border-t border-red-500/20 text-red-400 text-[10px] font-bold flex items-center gap-2 px-6"><AlertCircle size={14} /> {error}</div>}
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-slate-700 gap-4">
              <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center text-slate-700 mb-2 border border-white/5 shadow-inner">
                <Brain size={32} strokeWidth={1.5} />
              </div>
              <p className="text-sm font-medium tracking-tight">{t("memberMemory.selectFile")}</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
