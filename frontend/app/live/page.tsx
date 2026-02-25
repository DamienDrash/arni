"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import { Activity, MessageSquare, User, Bot, AlertTriangle, Shield, Check, X, RefreshCw, Unplug, Globe, UserPlus, Brain } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { MiniButton } from "@/components/ui/MiniButton";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { Modal } from "@/components/ui/Modal";

type Message = { role: string; content: string; timestamp: string };
type Session = { 
  user_id: string; 
  platform: string; 
  last_active: string; 
  is_active: boolean; 
  user_name?: string; 
  active_token?: string; 
  member_id?: string;
};

export default function LiveMonitorPage() {
  const { t } = useI18n();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [linkModal, setLinkModal] = useState<string | null>(null);
  const [memberIdInput, setMemberIdInput] = useState("");
  const [manualToken, setManualToken] = useState<{ id: string; token: string } | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);

  async function fetchSessions() {
    try {
      const res = await apiFetch("/admin/chats?limit=50");
      if (res.ok) setSessions(await res.json());
    } finally {
      setLoading(false);
    }
  }

  async function fetchHistory(id: string) {
    setLoadingHistory(true);
    try {
      const res = await apiFetch(`/admin/chats/${id}/history`);
      if (res.ok) setHistory(await res.json());
    } finally {
      setLoadingHistory(false);
    }
  }

  useEffect(() => {
    fetchSessions();
    const timer = setInterval(fetchSessions, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (selectedId) fetchHistory(selectedId);
  }, [selectedId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [history]);

  const activeSession = sessions.find(s => s.user_id === selectedId);

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] gap-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center text-indigo-400">
            <Activity size={20} />
          </div>
          <div>
            <h1 className="text-xl font-black text-white uppercase tracking-tight">{t("live.title")}</h1>
            <p className="text-xs text-slate-500 font-medium">{t("live.subtitle")}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 rounded-full border border-emerald-500/20">
          <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
          <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">Live</span>
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        {/* Sidebar */}
        <Card className="w-80 flex flex-col p-0 overflow-hidden border-slate-800/50 bg-slate-900/20 backdrop-blur-sm">
          <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/5">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">{t("live.sessions")}</span>
            <Badge variant="success" size="xs">{sessions.length}</Badge>
          </div>
          <div className="flex-1 overflow-y-auto custom-scrollbar p-2 flex flex-col gap-1">
            {sessions.length === 0 && !loading && (
              <div className="p-8 text-center text-slate-600 text-xs italic">{t("live.noSessions")}</div>
            )}
            {sessions.map(s => (
              <button 
                key={s.user_id}
                onClick={() => setSelectedId(s.user_id)}
                className={`w-full text-left p-3 rounded-xl transition-all border ${
                  selectedId === s.user_id 
                    ? "bg-indigo-600 border-indigo-500 shadow-lg shadow-indigo-600/20" 
                    : "bg-white/5 border-transparent hover:bg-white/10 hover:border-white/10"
                }`}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className={`text-xs font-bold truncate ${selectedId === s.user_id ? "text-white" : "text-slate-300"}`}>
                    {s.user_name || s.user_id.slice(0, 12)}
                  </span>
                  <span className={`text-[9px] font-bold uppercase ${selectedId === s.user_id ? "text-indigo-200" : "text-slate-500"}`}>
                    {s.platform}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] ${selectedId === s.user_id ? "text-indigo-100" : "text-slate-500"}`}>
                    {new Date(s.last_active).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {s.active_token && (
                    <div className="flex items-center gap-1 px-1.5 py-0.5 bg-amber-500/20 rounded-md border border-amber-500/20">
                      <Shield size={8} className="text-amber-500" />
                      <span className="text-[9px] font-black text-amber-500">{s.active_token}</span>
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        </Card>

        {/* Chat Area */}
        <Card className="flex-1 flex flex-col p-0 overflow-hidden border-slate-800/50 bg-slate-950/50">
          {selectedId ? (
            <>
              <div className="p-4 border-b border-white/5 flex items-center justify-between bg-white/5">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-indigo-500 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-inner">
                    {(activeSession?.user_name || "U")[0]}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">{activeSession?.user_name || selectedId}</div>
                    <div className="text-[10px] text-slate-500 uppercase font-black tracking-widest">{activeSession?.platform}</div>
                  </div>
                </div>
                <div className="flex gap-2">
                  {!activeSession?.member_id && (
                    <button onClick={() => setLinkModal(selectedId)} className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 text-slate-300 rounded-lg text-xs font-bold border border-white/10 transition-all">
                      <UserPlus size={14} /> {t("live.handoff.link")}
                    </button>
                  )}
                  {activeSession?.member_id && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 text-emerald-500 rounded-lg text-xs font-bold border border-emerald-500/20">
                      <Check size={14} /> {activeSession.member_id}
                    </div>
                  )}
                </div>
              </div>

              <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar bg-[url('/grid.svg')] bg-repeat bg-center">
                {history.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  return (
                    <div key={idx} className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
                      <div className={`max-w-[80%] group`}>
                        <div className={`flex items-center gap-2 mb-1.5 ${isUser ? "flex-row" : "flex-row-reverse"}`}>
                          <div className={`w-5 h-5 rounded-md flex items-center justify-center ${isUser ? "bg-slate-800 text-slate-400" : "bg-indigo-500/20 text-indigo-400"}`}>
                            {isUser ? <User size={12} /> : <Bot size={12} />}
                          </div>
                          <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
                            {isUser ? (activeSession?.user_name || "User") : "ARIIA AI"}
                          </span>
                          <span className="text-[9px] text-slate-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                            {new Date(msg.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm border ${
                          isUser 
                            ? "bg-slate-900 border-slate-800 text-slate-200 rounded-tl-none" 
                            : "bg-indigo-600 border-indigo-500 text-white rounded-tr-none shadow-indigo-500/10"
                        }`}>
                          {msg.content}
                        </div>
                      </div>
                    </div>
                  );
                })}
                {loadingHistory && (
                  <div className="flex justify-center p-4">
                    <RefreshCw size={20} className="animate-spin text-slate-700" />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-slate-600 gap-4">
              <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center text-slate-700 mb-2 border border-white/5 shadow-inner">
                <MessageSquare size={32} strokeWidth={1.5} />
              </div>
              <p className="text-sm font-medium tracking-tight">{t("live.selectSession")}</p>
            </div>
          )}
        </Card>
      </div>

      <Modal open={!!linkModal} onClose={() => setLinkModal(null)} title={t("live.handoff.link")} subtitle={t("live.handoff.hint")}>
        <div className="p-4 flex flex-col gap-4">
          <div className="relative">
            <Brain className="absolute left-3 top-3 text-slate-500" size={16} />
            <input 
              className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-10 pr-4 py-2.5 text-white outline-none focus:border-indigo-500"
              placeholder={t("live.handoff.placeholder")}
              value={memberIdInput}
              onChange={e => setMemberIdInput(e.target.value)}
            />
          </div>
          <div className="flex justify-end gap-3 mt-2">
            <button onClick={() => setLinkModal(null)} className="px-4 py-2 text-sm font-bold text-slate-400 hover:text-white transition-colors">{t("common.cancel")}</button>
            <button 
              onClick={async () => {
                if (!linkModal || !memberIdInput) return;
                const res = await apiFetch("/admin/tokens", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ member_id: memberIdInput, user_id: linkModal })
                });
                if (res.ok) {
                  const { token } = await res.json();
                  setManualToken({ id: linkModal, token });
                  setLinkModal(null);
                  setMemberIdInput("");
                  fetchSessions();
                }
              }}
              className="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-bold shadow-lg shadow-indigo-500/20"
            >
              Token generieren
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
