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
          platform: activeSession?.platform || "telegram",
        }),
      });
      if (res.ok) {
        setInterventionText("");
        fetchHistory(selectedId);
      }
    } finally {
      setSending(false);
    }
  }, [selectedId, interventionText, sessions, fetchHistory]);

  /* ── Effects ──────────────────────────────────────────────────────── */
  useEffect(() => { fetchSessions(); const t = setInterval(fetchSessions, 5000); return () => clearInterval(t); }, [fetchSessions]);
  useEffect(() => { if (selectedId) fetchHistory(selectedId); }, [selectedId, fetchHistory]);
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [history]);

  // Debounced member search
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
      {/* Header */}
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

      {/* Status Alerts */}
      {linkSuccess && (
        <div style={{
          padding: "12px 20px", borderRadius: 12,
          background: T.successDim, border: `1px solid ${T.success}40`,
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.success, fontWeight: 600,
        }}>
          <CheckCircle2 size={16} /> {linkSuccess}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Sitzungen</div>
            <div style={statValue()}>{sessions.length}</div>
          </div>
          <div style={statIcon(T.accent)}><Activity size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Aktiv</div>
            <div style={statValue(T.success)}>{activeSessions.length}</div>
          </div>
          <div style={statIcon(T.success)}><MessageSquare size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Verifiziert</div>
            <div style={statValue(T.success)}>{verifiedCount}</div>
          </div>
          <div style={statIcon(T.success)}><CheckCircle2 size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Nicht verifiziert</div>
            <div style={statValue(T.warning)}>{unverifiedCount}</div>
          </div>
          <div style={statIcon(T.warning)}><AlertTriangle size={20} /></div>
        </Card>
      </div>

      {/* Main Content: Session List + Chat View */}
      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4" style={{ flex: 1, minHeight: 0 }}>
        {/* Session List */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{
            padding: "16px 16px 12px", borderBottom: `1px solid ${T.border}`,
            background: `${T.surface}80`,
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Activity size={16} color={T.accent} />
                <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{t("live.sessions")}</span>
              </div>
              <Badge variant="success" size="xs">{filteredSessions.length}</Badge>
            </div>
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
              <input
                style={{ ...inputBase, paddingLeft: 34, fontSize: 12 }}
                placeholder="Sitzung suchen…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div style={{ flex: 1, overflowY: "auto", padding: 8 }} className="custom-scrollbar">
            {filteredSessions.length === 0 && !loading ? (
              <div style={{ padding: 32, textAlign: "center", color: T.textDim, fontSize: 12 }}>
                <MessageSquare size={24} style={{ marginBottom: 8, opacity: 0.3 }} />
                <div>{t("live.noSessions")}</div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {filteredSessions.map((s) => {
                  const isActive = selectedId === s.user_id;
                  return (
                    <button
                      key={s.user_id}
                      onClick={() => setSelectedId(s.user_id)}
                      style={{
                        width: "100%", textAlign: "left", padding: "14px 14px",
                        borderRadius: 10, border: `1px solid ${isActive ? `${T.accent}60` : "transparent"}`,
                        background: isActive ? T.accentDim : "transparent",
                        cursor: "pointer", transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                        <span style={{
                          fontSize: 12, fontWeight: isActive ? 700 : 600,
                          color: isActive ? T.accentLight : T.text,
                          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          maxWidth: 180,
                        }}>
                          {s.user_name || s.user_id.slice(0, 16)}
                        </span>
                        <PlatformBadge platform={s.platform} />
                      </div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                        <span style={{ fontSize: 10, color: isActive ? T.accentLight : T.textDim }}>
                          {new Date(s.last_active).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {s.member_id ? (
                            <Badge variant="success" size="xs">Verifiziert</Badge>
                          ) : s.active_token ? (
                            <span style={{
                              fontSize: 9, fontWeight: 800, color: T.warning,
                              background: T.warningDim, padding: "2px 6px", borderRadius: 4,
                              border: `1px solid ${T.warning}30`, fontFamily: "monospace",
                            }}>
                              {s.active_token}
                            </span>
                          ) : null}
                          <ChevronRight size={12} style={{ color: isActive ? T.accent : T.textDim, opacity: isActive ? 1 : 0.3 }} />
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </Card>

        {/* Chat Area */}
        <Card style={{ padding: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {selectedId && activeSession ? (
            <>
              {/* Chat Header */}
              <div style={{
                padding: "14px 20px", borderBottom: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", justifyContent: "space-between",
                background: `${T.surface}80`, flexWrap: "wrap", gap: 10,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 12,
                    background: activeSession.member_id ? `${T.success}15` : T.accentDim,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: activeSession.member_id ? T.success : T.accent,
                    fontWeight: 800, fontSize: 14,
                    border: `1px solid ${activeSession.member_id ? `${T.success}30` : `${T.accent}30`}`,
                  }}>
                    {(activeSession.user_name || "U")[0].toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>
                      {activeSession.user_name || selectedId}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                      <PlatformBadge platform={activeSession.platform} />
                      {activeSession.member_id && (
                        <span style={{ fontSize: 10, color: T.success, fontWeight: 600 }}>
                          Mitglied: {activeSession.member_id}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 8 }}>
                  {activeSession.member_id ? (
                    <>
                      <div style={{
                        display: "flex", alignItems: "center", gap: 6,
                        padding: "6px 12px", borderRadius: 8,
                        background: `${T.success}15`, border: `1px solid ${T.success}30`,
                        fontSize: 11, fontWeight: 700, color: T.success,
                      }}>
                        <Check size={14} /> Verifiziert
                      </div>
                      <button
                        onClick={() => unlinkMember(selectedId)}
                        style={{ ...btnSecondary, borderColor: `${T.danger}40`, color: T.danger }}
                        title="Verknüpfung aufheben"
                      >
                        <Unlink size={14} />
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => {
                        setLinkModal(selectedId);
                        setMemberSearch("");
                        setMemberResults([]);
                        setLinkError("");
                      }}
                      style={btnPrimary}
                    >
                      <Link2 size={14} /> {t("live.handoff.link")}
                    </button>
                  )}
                </div>
              </div>

              {/* Chat Messages */}
              <div
                ref={scrollRef}
                style={{
                  flex: 1, overflowY: "auto", padding: "20px 24px",
                  display: "flex", flexDirection: "column", gap: 16,
                }}
                className="custom-scrollbar"
              >
                {loadingHistory ? (
                  <div style={{ display: "flex", justifyContent: "center", padding: 32 }}>
                    <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: T.accent }} />
                  </div>
                ) : history.length === 0 ? (
                  <div style={{ textAlign: "center", padding: 48, color: T.textDim, fontSize: 12 }}>
                    Keine Nachrichten in dieser Sitzung.
                  </div>
                ) : (
                  history.map((msg, idx) => {
                    const isUser = msg.role === "user";
                    return (
                      <div key={idx} style={{ display: "flex", justifyContent: isUser ? "flex-start" : "flex-end" }}>
                        <div style={{ maxWidth: "75%" }}>
                          <div style={{
                            display: "flex", alignItems: "center", gap: 8,
                            marginBottom: 6, flexDirection: isUser ? "row" : "row-reverse",
                          }}>
                            <div style={{
                              width: 24, height: 24, borderRadius: 8,
                              display: "flex", alignItems: "center", justifyContent: "center",
                              background: isUser ? T.surfaceAlt : T.accentDim,
                              color: isUser ? T.textDim : T.accent,
                              border: `1px solid ${isUser ? T.border : `${T.accent}30`}`,
                            }}>
                              {isUser ? <User size={12} /> : <Bot size={12} />}
                            </div>
                            <span style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                              {isUser ? (activeSession?.user_name || "Nutzer") : "ARIIA"}
                            </span>
                            <span style={{ fontSize: 9, color: T.textDim }}>
                              {new Date(msg.timestamp).toLocaleTimeString("de-DE")}
                            </span>
                          </div>
                          <div style={{
                            padding: "12px 16px", borderRadius: 14,
                            fontSize: 13, lineHeight: 1.6,
                            background: isUser ? T.surfaceAlt : T.accent,
                            color: isUser ? T.text : "#fff",
                            border: `1px solid ${isUser ? T.border : T.accent}`,
                            borderTopLeftRadius: isUser ? 4 : 14,
                            borderTopRightRadius: isUser ? 14 : 4,
                            whiteSpace: "pre-wrap", wordBreak: "break-word",
                          }}>
                            {msg.content}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Intervention Input */}
              <div style={{
                padding: "12px 20px", borderTop: `1px solid ${T.border}`,
                display: "flex", alignItems: "center", gap: 10,
                background: `${T.surface}80`,
              }}>
                <input
                  style={{ ...inputBase, flex: 1 }}
                  placeholder="Nachricht als Admin senden…"
                  value={interventionText}
                  onChange={(e) => setInterventionText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendIntervention(); } }}
                />
                <button
                  onClick={sendIntervention}
                  disabled={sending || !interventionText.trim()}
                  style={{
                    ...btnPrimary,
                    opacity: sending || !interventionText.trim() ? 0.4 : 1,
                    padding: "10px 16px",
                  }}
                >
                  {sending ? <RefreshCw size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Send size={16} />}
                </button>
              </div>
            </>
          ) : (
            /* Empty State */
            <div style={{
              flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", padding: 48, textAlign: "center",
            }}>
              <div style={{
                width: 72, height: 72, borderRadius: "50%",
                background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center",
                marginBottom: 20, border: `1px solid ${T.accent}30`,
              }}>
                <MessageSquare size={32} color={T.accent} strokeWidth={1.5} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, marginBottom: 8 }}>
                {t("live.selectSession")}
              </h3>
              <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 360, lineHeight: 1.6 }}>
                Wählen Sie links eine Sitzung aus, um den Chatverlauf einzusehen und bei Bedarf einzugreifen.
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Link Member Modal */}
      <Modal
        open={!!linkModal}
        onClose={() => setLinkModal(null)}
        title={t("live.handoff.link")}
        subtitle={t("live.handoff.hint")}
        width="min(560px, 90vw)"
      >
        {linkModal && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "4px 0" }}>
            {/* Search Input */}
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 14, top: 13, color: T.textDim }} />
              <input
                style={{ ...inputBase, paddingLeft: 36 }}
                placeholder="Mitglied suchen (Name, E-Mail, Telefon, Mitgliedsnr.)…"
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
                autoFocus
              />
              {searchingMembers && (
                <RefreshCw size={14} style={{ position: "absolute", right: 14, top: 13, color: T.accent, animation: "spin 1s linear infinite" }} />
              )}
            </div>

            {/* Error */}
            {linkError && (
              <div style={{
                padding: "10px 14px", borderRadius: 10,
                background: T.dangerDim, border: `1px solid ${T.danger}30`,
                fontSize: 12, color: T.danger, display: "flex", alignItems: "center", gap: 8,
              }}>
                <XCircle size={14} /> {linkError}
              </div>
            )}

            {/* Search Results */}
            <div style={{
              maxHeight: 300, overflowY: "auto", borderRadius: 10,
              border: `1px solid ${T.border}`, background: T.surface,
            }} className="custom-scrollbar">
              {memberResults.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: T.textDim, fontSize: 12 }}>
                  {memberSearch.trim() ? (searchingMembers ? "Suche…" : "Keine Kontakte gefunden") : "Suchbegriff eingeben, um Kontakte zu finden"}
                </div>
              ) : (
                memberResults.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => linkMember(linkModal, String(m.customer_id))}
                    style={{
                      width: "100%", textAlign: "left",
                      padding: "14px 16px", borderBottom: `1px solid ${T.border}`,
                      background: "transparent", border: "none", cursor: "pointer",
                      color: T.text, transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>
                          {m.first_name} {m.last_name}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: T.textMuted }}>
                          {m.member_number && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Hash size={10} /> {m.member_number}
                            </span>
                          )}
                          {m.email && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Mail size={10} /> {m.email}
                            </span>
                          )}
                          {m.phone_number && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Phone size={10} /> {m.phone_number}
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{
                        padding: "6px 12px", borderRadius: 8,
                        background: T.accentDim, color: T.accent,
                        fontSize: 11, fontWeight: 700,
                        display: "flex", alignItems: "center", gap: 6,
                      }}>
                        <Link2 size={12} /> Verknüpfen
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Manual ID Input */}
            <div style={{
              padding: "12px 16px", borderRadius: 10,
              background: T.surfaceAlt, border: `1px solid ${T.border}`,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Oder manuell verknüpfen
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  style={{ ...inputBase, flex: 1, fontSize: 12 }}
                  placeholder={t("live.handoff.placeholder")}
                  value={memberSearch}
                  onChange={(e) => setMemberSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && memberSearch.trim()) {
                      linkMember(linkModal, memberSearch.trim());
                    }
                  }}
                />
                <button
                  onClick={() => {
                    if (memberSearch.trim()) linkMember(linkModal, memberSearch.trim());
                  }}
                  style={{ ...btnPrimary, padding: "8px 14px" }}
                >
                  <Link2 size={14} /> Verknüpfen
                </button>
              </div>
            </div>

            {/* Cancel */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={() => setLinkModal(null)} style={btnSecondary}>
                Abbrechen
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
