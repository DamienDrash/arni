"use client";

import { useEffect, useState, useRef, useMemo, useCallback } from "react";
import {
  Activity, MessageSquare, User, Bot, Shield, Check, X, RefreshCw,
  UserPlus, Brain, Search, ChevronRight, Phone, Mail, Hash,
  CheckCircle2, XCircle, Link2, Unlink, Send, AlertTriangle,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/LanguageContext";
import { getStoredUser } from "@/lib/auth";

/* ── Types ──────────────────────────────────────────────────────────── */
type Message = { role: string; content: string; timestamp: string; metadata?: string };
type Session = {
  user_id: string;
  platform: string;
  last_active: string;
  is_active: boolean;
  user_name?: string;
  active_token?: string;
  member_id?: string;
  phone_number?: string;
  email?: string;
};
type MemberResult = {
  id: number;
  customer_id: number;
  member_number?: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone_number?: string;
};

/* ── Styles ─────────────────────────────────────────────────────────── */
const statCard: React.CSSProperties = {
  padding: "20px 24px",
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
};
const statIcon: (color: string) => React.CSSProperties = (color) => ({
  width: 44, height: 44, borderRadius: 12,
  background: `${color}15`,
  display: "flex", alignItems: "center", justifyContent: "center",
  color, flexShrink: 0,
});
const statLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4,
};
const statValue: (color?: string) => React.CSSProperties = (color) => ({
  fontSize: 24, fontWeight: 800, color: color || T.text, letterSpacing: "-0.02em",
});
const inputBase: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  transition: "border-color 0.2s ease",
};
const btnPrimary: React.CSSProperties = {
  border: "none", borderRadius: 10, background: T.accent, color: "#fff",
  fontWeight: 700, padding: "10px 20px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13,
  transition: "all 0.2s ease",
};
const btnSecondary: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt,
  color: T.text, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
  transition: "all 0.2s ease",
};

/* ── Platform Badge ─────────────────────────────────────────────────── */
function PlatformBadge({ platform }: { platform: string }) {
  const colors: Record<string, string> = {
    whatsapp: T.whatsapp, telegram: T.telegram, email: T.email, phone: T.phone,
  };
  const color = colors[platform] || T.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, textTransform: "uppercase",
      letterSpacing: "0.08em", color, background: `${color}15`,
      padding: "2px 8px", borderRadius: 6, border: `1px solid ${color}30`,
    }}>
      {platform}
    </span>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */
export default function LiveMonitorPage() {
  const { t } = useI18n();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [search, setSearch] = useState("");

  // Link Member Modal
  const [linkModal, setLinkModal] = useState<string | null>(null);
  const [memberSearch, setMemberSearch] = useState("");
  const [memberResults, setMemberResults] = useState<MemberResult[]>([]);
  const [searchingMembers, setSearchingMembers] = useState(false);
  const [linkError, setLinkError] = useState("");
  const [linkSuccess, setLinkSuccess] = useState("");

  // Intervention
  const [interventionText, setInterventionText] = useState("");
  const [sending, setSending] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/chats?limit=50");
      if (res.ok) setSessions(await res.json());
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async (id: string) => {
    setLoadingHistory(true);
    try {
      const res = await apiFetch(`/admin/chats/${id}/history`);
      if (res.ok) setHistory(await res.json());
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const searchMembers = useCallback(async (query: string) => {
    if (!query.trim()) { setMemberResults([]); return; }
    setSearchingMembers(true);
    try {
      const res = await apiFetch(`/admin/members/search-for-link?q=${encodeURIComponent(query)}`);
      if (res.ok) setMemberResults(await res.json());
    } finally {
      setSearchingMembers(false);
    }
  }, []);

  const linkMember = useCallback(async (userId: string, memberId: string) => {
    setLinkError("");
    try {
      const res = await apiFetch(`/admin/chats/${userId}/link-member`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: memberId }),
      });
      if (res.ok) {
        setLinkSuccess(`Mitglied ${memberId} erfolgreich verknüpft`);
        setLinkModal(null);
        setMemberSearch("");
        setMemberResults([]);
        fetchSessions();
        setTimeout(() => setLinkSuccess(""), 4000);
      } else {
        const data = await res.json().catch(() => ({}));
        setLinkError(data.detail || "Verknüpfung fehlgeschlagen");
      }
    } catch {
      setLinkError("Fehler bei der Verknüpfung");
    }
  }, [fetchSessions]);

  const unlinkMember = useCallback(async (userId: string) => {
    try {
      const res = await apiFetch(`/admin/chats/${userId}/link-member`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: null }),
      });
      if (res.ok) {
        setLinkSuccess("Verknüpfung aufgehoben");
        fetchSessions();
        setTimeout(() => setLinkSuccess(""), 3000);
      }
    } catch { /* ignore */ }
  }, [fetchSessions]);

  const sendIntervention = useCallback(async () => {
    if (!selectedId || !interventionText.trim()) return;
    setSending(true);
    try {
      const activeSession = sessions.find(s => s.user_id === selectedId);
      const res = await apiFetch(`/admin/chats/${selectedId}/intervene`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: interventionText.trim(),
          platform: activeSession?.platform || "whatsapp",
        }),
      });
      if (res.ok) {
        setInterventionText("");
      }
    } finally {
      setSending(false);
    }
  }, [selectedId, interventionText, sessions]);

  /* ── WebSocket Integration ────────────────────────────────────────── */
  useEffect(() => {
    const user = getStoredUser();
    if (!user) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/control?tid=${user.tenant_id}`;

    let reconnectTimer: any;

    const connect = () => {
      console.log("[WS] Connecting to", wsUrl);
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ghost.message_in" || data.type === "ghost.message_out") {
            // 1. Update Session List
            setSessions(prev => {
              const sid = data.user_id;
              const idx = prev.findIndex(s => s.user_id === sid);
              
              if (idx === -1) {
                // Unknown session (e.g. new email contact). Refresh all.
                fetchSessions();
                return prev;
              }
              
              const updated = [...prev];
              updated[idx] = { ...updated[idx], last_active: new Date().toISOString(), is_active: true };
              return updated.sort((a, b) => new Date(b.last_active).getTime() - new Date(a.last_active).getTime());
            });

            // 2. Update Active Chat History
            if (selectedId && (data.user_id === selectedId || data.type === "ghost.message_out")) {
              setHistory(prev => {
                // Check for duplicates via message_id or timestamp/content
                const isDuplicate = prev.some(m => 
                  (m.metadata && JSON.parse(m.metadata).message_id === data.message_id) ||
                  (m.content === (data.content || data.response) && Math.abs(new Date(m.timestamp).getTime() - new Date().getTime()) < 2000)
                );
                if (isDuplicate) return prev;

                return [...prev, {
                  role: data.type === "ghost.message_in" ? "user" : "assistant",
                  content: data.content || data.response,
                  timestamp: new Date().toISOString(),
                  metadata: JSON.stringify({ message_id: data.message_id })
                }];
              });
            }
          }
        } catch (e) { console.error("[WS] Parse error", e); }
      };

      ws.onclose = () => { reconnectTimer = setTimeout(connect, 3000); };
    };

    connect();
    return () => { if (socketRef.current) socketRef.current.close(); clearTimeout(reconnectTimer); };
  }, [selectedId, fetchSessions]);

  /* ── Effects ──────────────────────────────────────────────────────── */
  useEffect(() => { fetchSessions(); }, [fetchSessions]);
  useEffect(() => { if (selectedId) fetchHistory(selectedId); }, [selectedId, fetchHistory]);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [history]);

  useEffect(() => {
    const timer = setTimeout(() => { if (memberSearch.trim()) searchMembers(memberSearch); }, 300);
    return () => clearTimeout(timer);
  }, [memberSearch, searchMembers]);

  /* ── Derived ──────────────────────────────────────────────────────── */
  const activeSession = sessions.find(s => s.user_id === selectedId);
  const activeSessions = sessions.filter(s => s.is_active);
  const verifiedCount = sessions.filter(s => s.member_id).length;
  const unverifiedCount = sessions.filter(s => !s.member_id).length;

  const filteredSessions = useMemo(() => {
    if (!search.trim()) return sessions;
    const term = search.toLowerCase();
    return sessions.filter(s =>
      (s.user_name || "").toLowerCase().includes(term) ||
      s.user_id.toLowerCase().includes(term) ||
      (s.member_id || "").toLowerCase().includes(term) ||
      s.platform.toLowerCase().includes(term)
    );
  }, [sessions, search]);

  /* ── Render ───────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, height: "calc(100vh - 120px)" }}>
      <SectionHeader
        title={t("live.title")}
        subtitle={t("live.subtitle")}
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "6px 14px", borderRadius: 20,
              background: `${T.success}15`, border: `1px solid ${T.success}30`,
            }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.success, animation: "pulse 2s infinite" }} />
              <span style={{ fontSize: 10, fontWeight: 800, color: T.success, textTransform: "uppercase", letterSpacing: "0.1em" }}>Live</span>
            </div>
            <button onClick={() => fetchSessions()} style={btnSecondary}>
              <RefreshCw size={14} /> Aktualisieren
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card style={statCard}>
          <div><div style={statLabel}>Sitzungen</div><div style={statValue()}>{sessions.length}</div></div>
          <div style={statIcon(T.accent)}><Activity size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div><div style={statLabel}>Aktiv</div><div style={statValue(T.success)}>{activeSessions.length}</div></div>
          <div style={statIcon(T.success)}><MessageSquare size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div><div style={statLabel}>Verifiziert</div><div style={statValue(T.success)}>{verifiedCount}</div></div>
          <div style={statIcon(T.success)}><CheckCircle2 size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div><div style={statLabel}>Nicht verifiziert</div><div style={statValue(T.warning)}>{unverifiedCount}</div></div>
          <div style={statIcon(T.warning)}><AlertTriangle size={20} /></div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4" style={{ flex: 1, minHeight: 0 }}>
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "16px 16px 12px", borderBottom: `1px solid ${T.border}`, background: `${T.surface}80` }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}><Activity size={16} color={T.accent} /><span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{t("live.sessions")}</span></div>
              <Badge variant="success" size="xs">{filteredSessions.length}</Badge>
            </div>
            <div style={{ position: "relative" }}><Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} /><input style={{ ...inputBase, paddingLeft: 34, fontSize: 12 }} placeholder="Sitzung suchen…" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 8 }} className="custom-scrollbar">
            {filteredSessions.map((s) => {
              const isActive = selectedId === s.user_id;
              return (
                <button key={s.user_id} onClick={() => setSelectedId(s.user_id)} style={{ width: "100%", textAlign: "left", padding: "14px 14px", borderRadius: 10, border: `1px solid ${isActive ? `${T.accent}60` : "transparent"}`, background: isActive ? T.accentDim : "transparent", cursor: "pointer", transition: "all 0.15s ease" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}><span style={{ fontSize: 12, fontWeight: isActive ? 700 : 600, color: isActive ? T.accentLight : T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 180 }}>{s.user_name || s.user_id}</span><PlatformBadge platform={s.platform} /></div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}><span style={{ fontSize: 10, color: isActive ? T.accentLight : T.textDim }}>{new Date(s.last_active).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</span><ChevronRight size={12} style={{ color: isActive ? T.accent : T.textDim, opacity: isActive ? 1 : 0.3 }} /></div>
                </button>
              );
            })}
          </div>
        </Card>

        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selectedId && activeSession ? (
            <>
              <div style={{ padding: "14px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", background: `${T.surface}80` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}><div style={{ width: 40, height: 40, borderRadius: 12, background: activeSession.member_id ? `${T.success}15` : T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", color: activeSession.member_id ? T.success : T.accent, fontWeight: 800, fontSize: 14, border: `1px solid ${activeSession.member_id ? `${T.success}30` : `${T.accent}30`}` }}>{(activeSession.user_name || "U")[0].toUpperCase()}</div><div><div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{activeSession.user_name || selectedId}</div><div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}><PlatformBadge platform={activeSession.platform} /></div></div></div>
                <div style={{ display: "flex", gap: 8 }}>{activeSession.member_id ? <button onClick={() => unlinkMember(selectedId)} style={{ ...btnSecondary, borderColor: `${T.danger}40`, color: T.danger }}><Unlink size={14} /></button> : <button onClick={() => setLinkModal(selectedId)} style={btnPrimary}><Link2 size={14} /> {t("live.handoff.link")}</button>}</div>
              </div>
              <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 }} className="custom-scrollbar">
                {history.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  return (
                    <div key={idx} style={{ display: "flex", justifyContent: isUser ? "flex-start" : "flex-end" }}>
                      <div style={{ maxWidth: "75%" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, flexDirection: isUser ? "row" : "row-reverse" }}><div style={{ width: 24, height: 24, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: isUser ? T.surfaceAlt : T.accentDim, color: isUser ? T.textDim : T.accent, border: `1px solid ${isUser ? T.border : `${T.accent}30`}` }}>{isUser ? <User size={12} /> : <Bot size={12} />}</div><span style={{ fontSize: 10, fontWeight: 700, color: T.textDim }}>{isUser ? (activeSession?.user_name || "Nutzer") : "ARIIA"}</span><span style={{ fontSize: 9, color: T.textDim }}>{new Date(msg.timestamp).toLocaleTimeString("de-DE")}</span></div>
                        <div style={{ padding: "12px 16px", borderRadius: 14, fontSize: 13, background: isUser ? T.surfaceAlt : T.accent, color: isUser ? T.text : "#fff", borderTopLeftRadius: isUser ? 4 : 14, borderTopRightRadius: isUser ? 14 : 4, whiteSpace: "pre-wrap" }}>{msg.content}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ padding: "12px 20px", borderTop: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 10, background: `${T.surface}80` }}><input style={{ ...inputBase, flex: 1 }} placeholder="Nachricht als Admin senden…" value={interventionText} onChange={(e) => setInterventionText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendIntervention(); } }} /><button onClick={sendIntervention} disabled={sending || !interventionText.trim()} style={{ ...btnPrimary, opacity: sending || !interventionText.trim() ? 0.4 : 1 }}><Send size={16} /></button></div>
            </>
          ) : (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 48, textAlign: "center" }}><div style={{ width: 72, height: 72, borderRadius: "50%", background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 20, border: `1px solid ${T.accent}30` }}><MessageSquare size={32} color={T.accent} /></div><h3 style={{ fontSize: 16, fontWeight: 700, color: T.text }}>{t("live.selectSession")}</h3></div>
          )}
        </Card>
      </div>

      <Modal open={!!linkModal} onClose={() => setLinkModal(null)} title={t("live.handoff.link")} subtitle={t("live.handoff.hint")} width="min(560px, 90vw)">
        {linkModal && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <input style={{ ...inputBase }} placeholder="Mitglied suchen…" value={memberSearch} onChange={(e) => setMemberSearch(e.target.value)} />
            {memberResults.map((m) => (
              <button key={m.id} onClick={() => linkMember(linkModal, String(m.customer_id))} style={{ textAlign: "left", padding: 12 }}>{m.first_name} {m.last_name}</button>
            ))}
            <button onClick={() => setLinkModal(null)} style={btnSecondary}>Abbrechen</button>
          </div>
        )}
      </Modal>
    </div>
  );
}
