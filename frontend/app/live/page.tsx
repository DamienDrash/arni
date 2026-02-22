"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Users, Send, Clock, Ghost, Phone } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/Badge";
import { MiniButton } from "@/components/ui/MiniButton";
import { Modal } from "@/components/ui/Modal";

type ChatSession = {
  user_id: string;
  platform: string;
  last_active: string;
  is_active: boolean;
  user_name?: string;
  member_id?: string;
  active_token?: string;
};

type Message = {
  role: string;
  content: string;
  timestamp: string;
  metadata?: string;
};

function platformColor(platform: string): string {
  if (platform === "whatsapp") return T.whatsapp;
  if (platform === "telegram") return T.telegram;
  if (platform === "email") return T.email;
  return T.phone;
}

function initials(name: string) {
  return name.substring(0, 2).toUpperCase();
}

export default function LiveGhostPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [wsStatus, setWsStatus] = useState<"connecting" | "connected" | "stale" | "fallback">("connecting");
  const [manualToken, setManualToken] = useState<string | null>(null);
  const [mobileView, setMobileView] = useState<"list" | "chat">("list");
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [showLinkDialog, setShowLinkDialog] = useState(false);
  const [memberIdInput, setMemberIdInput] = useState("");
  const [actionError, setActionError] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const selectedUserRef = useRef<string | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastWsEventAtRef = useRef<number>(0);

  const currentSession = sessions.find(s => s.user_id === selectedUser);
  const activeToken = currentSession?.member_id ? null : (manualToken ?? currentSession?.active_token ?? null);

  const fetchSessions = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/chats?limit=200");
      if (res.ok) setSessions(await res.json());
    } catch { }
  }, []);

  const fetchHistory = useCallback(async (userId: string) => {
    try {
      const res = await apiFetch(`/admin/chats/${userId}/history`);
      if (res.ok) setMessages(await res.json());
    } catch { }
  }, []);

  useEffect(() => {
    if (!selectedUser) return;
    const kickoff = setTimeout(() => { void fetchHistory(selectedUser); }, 0);
    const bottomReset = setTimeout(() => {
      shouldAutoScrollRef.current = true;
      setIsAtBottom(true);
    }, 0);
    return () => {
      clearTimeout(kickoff);
      clearTimeout(bottomReset);
    };
  }, [fetchHistory, selectedUser]);

  useEffect(() => {
    selectedUserRef.current = selectedUser;
  }, [selectedUser]);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    if (!selectedUser && sessions.length > 0) {
      timer = setTimeout(() => setSelectedUser(sessions[0].user_id), 0);
    } else if (selectedUser && sessions.length > 0 && !sessions.some((s) => s.user_id === selectedUser)) {
      timer = setTimeout(() => setSelectedUser(sessions[0].user_id), 0);
    }
    return () => { if (timer) clearTimeout(timer); };
  }, [sessions, selectedUser]);

  useEffect(() => {
    const timer = setTimeout(() => setManualToken(null), 0);
    return () => clearTimeout(timer);
  }, [selectedUser]);

  useEffect(() => {
    const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    const wsEnabled = process.env.NEXT_PUBLIC_ENABLE_WS === "true" || isLocalhost;
    if (!wsEnabled) {
      setWsStatus("fallback");
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const configuredBasePath = (process.env.NEXT_PUBLIC_GATEWAY_BASE_PATH || "").trim().replace(/\/+$/, "");
    const wsCandidates: string[] = isLocalhost
      ? ["ws://localhost:8000/ws/control"]
      : [...new Set([
        "/ws/control",
        "/arni/ws/control",
        "/proxy/ws/control",
        "/arni/proxy/ws/control",
        `${configuredBasePath}/ws/control`,
        `${configuredBasePath}/proxy/ws/control`,
      ])].map(p => `${protocol}//${window.location.host}${p}`);

    let closedByCleanup = false;

    const scheduleRefresh = () => {
      if (refreshTimerRef.current) return;
      refreshTimerRef.current = setTimeout(() => {
        refreshTimerRef.current = null;
        void fetchSessions();
        const activeUser = selectedUserRef.current;
        if (activeUser) void fetchHistory(activeUser);
      }, 300);
    };

    const scheduleReconnect = () => {
      if (closedByCleanup) return;
      const attempt = reconnectAttemptsRef.current + 1;
      reconnectAttemptsRef.current = attempt;
      const delay = Math.min(15000, 1000 * Math.pow(2, Math.min(attempt, 4)));
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => connect(0), delay);
    };

    const connect = (index: number) => {
      if (closedByCleanup) return;
      if (index >= wsCandidates.length) {
        setWsStatus("fallback");
        scheduleReconnect();
        return;
      }
      setWsStatus("connecting");
      const ws = new WebSocket(wsCandidates[index]);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttemptsRef.current = 0;
        lastWsEventAtRef.current = Date.now();
        setWsStatus("connected");
        scheduleRefresh();
      };
      ws.onclose = () => {
        if (closedByCleanup) return;
        setWsStatus("fallback");
        scheduleReconnect();
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onmessage = (event) => {
        lastWsEventAtRef.current = Date.now();
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ghost.message_in" || data.type === "ghost.message_out") {
            scheduleRefresh();
          }
        } catch {
          // Keep socket alive even if malformed payload arrives.
        }
      };
    };

    connect(0);
    return () => {
      closedByCleanup = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
      wsRef.current?.close();
    };
  }, [fetchHistory, fetchSessions]);

  useEffect(() => {
    void fetchSessions();
    if (selectedUser) void fetchHistory(selectedUser);
  }, [fetchHistory, fetchSessions, selectedUser]);

  useEffect(() => {
    if (wsStatus !== "connected") return;
    const timer = setInterval(() => {
      const lastEvent = lastWsEventAtRef.current;
      if (!lastEvent) return;
      if (Date.now() - lastEvent > 20000) {
        setWsStatus("stale");
        wsRef.current?.close();
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [wsStatus]);

  useEffect(() => {
    if (wsStatus === "connected") return;
    const sessionsTimer = setInterval(() => { void fetchSessions(); }, 5000);
    const historyTimer = setInterval(() => {
      if (selectedUserRef.current) void fetchHistory(selectedUserRef.current);
    }, 3500);
    return () => {
      clearInterval(sessionsTimer);
      clearInterval(historyTimer);
    };
  }, [fetchHistory, fetchSessions, wsStatus]);

  const handleSend = () => {
    if (!input || !selectedUser || isSending) return;
    const content = input;
    const platform = currentSession?.platform || "telegram";
    setIsSending(true);
    setInput("");
    setMessages(prev => [...prev, {
      role: "assistant",
      content,
      timestamp: new Date().toISOString(),
      metadata: JSON.stringify({ source: "admin" }),
    }]);

    const run = async () => {
      try {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            type: "intervention",
            user_id: selectedUser,
            content,
            platform,
          }));
        } else {
          await apiFetch(`/admin/chats/${selectedUser}/intervene`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content, platform }),
          });
        }
      } catch {
        // keep optimistic message, history polling will reconcile.
      } finally {
        setIsSending(false);
      }
    };
    void run();
  };

  const handleGenerateToken = async () => {
    if (!selectedUser || !memberIdInput.trim()) {
      setActionError("Bitte eine gültige Member ID angeben.");
      return;
    }
    try {
      const res = await apiFetch("/admin/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: memberIdInput.trim(), user_id: selectedUser }),
      });
      if (res.ok) {
        const data = await res.json();
        setManualToken(data.token);
        setShowLinkDialog(false);
        setMemberIdInput("");
        setActionError("");
      } else {
        setActionError(`Token-Generierung fehlgeschlagen (${res.status}).`);
      }
    } catch {
      setActionError("Token-Generierung fehlgeschlagen.");
    }
  };

  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    if (!shouldAutoScrollRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  // ── List Panel ────────────────────────────────────────────────────────────
  const listPanel = (
    <div style={{ background: T.surface, display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ padding: "20px 16px 16px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Users size={15} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Live Sessions</span>
          {sessions.length > 0 && (
            <Badge variant="accent" size="xs">{sessions.length}</Badge>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {sessions.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: T.textDim, fontSize: 13 }}>
            Keine aktiven Sessions
          </div>
        ) : (
          sessions.map(session => {
            const isSelected = selectedUser === session.user_id;
            const name = session.user_name || session.user_id;
            return (
              <button
                key={session.user_id}
                type="button"
                aria-label={`Session öffnen: ${name}`}
                onClick={() => { setSelectedUser(session.user_id); setMobileView("chat"); }}
                style={{
                  width: "100%",
                  textAlign: "left",
                  padding: "14px 16px",
                  border: "none",
                  borderBottom: `1px solid ${T.border}`,
                  cursor: "pointer",
                  background: isSelected ? T.accentDim : "transparent",
                  borderLeft: `3px solid ${isSelected ? T.accent : "transparent"}`,
                  transition: "background 0.15s",
                }}
              >
                <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                  <Avatar
                    initials={initials(name)}
                    size={36}
                    color={platformColor(session.platform)}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{name}</span>
                      <span style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>{session.platform}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 4 }}>
                      <Clock size={11} color={T.textDim} />
                      <span style={{ fontSize: 11, color: T.textMuted }}>
                        {new Date(session.last_active).toLocaleTimeString()}
                      </span>
                      {session.member_id && (
                        <Badge variant="accent" size="xs">{session.member_id}</Badge>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );

  // ── Chat Panel ────────────────────────────────────────────────────────────
  const chatPanel = (
    <div style={{ background: T.bg, display: "flex", flexDirection: "column", height: "100%", minHeight: 0, overflow: "hidden" }}>
      {selectedUser && currentSession ? (
        <>
          {/* Header */}
          <div style={{
            padding: "16px 24px",
            borderBottom: `1px solid ${T.border}`,
            background: T.surface,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 8,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button
                className="md:hidden"
                onClick={() => setMobileView("list")}
                style={{ background: "none", border: "none", cursor: "pointer", color: T.textMuted, padding: 4 }}
              >
                ←
              </button>
              <Avatar
                initials={initials(currentSession.user_name || selectedUser)}
                size={38}
                color={platformColor(currentSession.platform)}
              />
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>
                  {currentSession.user_name || selectedUser}
                </h3>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                  <span style={{ fontSize: 11, color: T.textDim, textTransform: "uppercase" }}>
                    {currentSession.platform}
                  </span>
                  {currentSession.member_id && (
                    <Badge variant="accent" size="xs">Member: {currentSession.member_id}</Badge>
                  )}
                  <span style={{ fontSize: 11, color: T.textDim }}>· {selectedUser}</span>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {!currentSession.member_id && (
                <MiniButton
                  onClick={() => {
                    setShowLinkDialog(true);
                    setActionError("");
                    setMemberIdInput("");
                  }}
                >
                  <Phone size={12} /> Link Member
                </MiniButton>
              )}
              <Badge variant={wsStatus === "connected" ? "success" : "warning"}>
                {wsStatus === "connected" ? "Realtime aktiv" : wsStatus === "connecting" ? "Verbinde…" : wsStatus === "stale" ? "Reconnect…" : "Fallback Polling"}
              </Badge>
            </div>
          </div>

          {/* Token Banner */}
          {activeToken && (
            <div style={{
              background: T.accentDim,
              borderBottom: `1px solid ${T.accent}`,
              padding: "12px 24px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Phone size={18} color={T.accentLight} />
                <div>
                  <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                    Verifizierungscode
                  </div>
                  <div style={{ fontSize: 22, fontFamily: "monospace", fontWeight: 700, color: T.accentLight, letterSpacing: "0.15em" }}>
                    {activeToken}
                  </div>
                </div>
              </div>
              <MiniButton onClick={() => setManualToken(null)}>✕</MiniButton>
            </div>
          )}

          {/* Messages */}
          <div
            ref={messagesContainerRef}
            onScroll={(e) => {
              const el = e.currentTarget;
              const distanceFromBottom = el.scrollHeight - (el.scrollTop + el.clientHeight);
              const atBottom = distanceFromBottom < 48;
              shouldAutoScrollRef.current = atBottom;
              setIsAtBottom(atBottom);
            }}
            style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}
          >
            {messages.length === 0 && !activeToken && (
              <div style={{ textAlign: "center", color: T.textDim, marginTop: 40, fontSize: 13 }}>
                <Ghost size={40} style={{ opacity: 0.2, margin: "0 auto 12px", display: "block" }} />
                Noch keine Nachrichten.
                {!currentSession.member_id && (
                  <div style={{ marginTop: 12 }}>
                    <MiniButton
                      onClick={() => {
                        setShowLinkDialog(true);
                        setActionError("");
                        setMemberIdInput("");
                      }}
                    >
                      <Phone size={12} /> Verifizierungstoken generieren
                    </MiniButton>
                  </div>
                )}
              </div>
            )}
            {messages.map((msg, idx) => {
              const isUser = msg.role === "user";
              return (
                <div key={idx} style={{ display: "flex", justifyContent: isUser ? "flex-start" : "flex-end" }}>
                  <div style={{
                    maxWidth: "80%",
                    padding: "12px 16px",
                    borderRadius: 14,
                    background: isUser ? T.surfaceAlt : T.accentDim,
                    border: `1px solid ${isUser ? T.border : "rgba(108,92,231,0.3)"}`,
                  }}>
                    <p style={{ fontSize: 13, color: T.text, margin: 0, lineHeight: 1.5 }}>{msg.content}</p>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6, marginTop: 6 }}>
                      <span style={{ fontSize: 10, color: T.textDim }}>
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </span>
                      {!isUser && <Badge variant="accent" size="xs">ARNI</Badge>}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {!isAtBottom && (
            <div style={{ padding: "6px 24px 0", background: T.surface }}>
              <MiniButton onClick={() => {
                if (messagesContainerRef.current) {
                  messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
                }
                shouldAutoScrollRef.current = true;
                setIsAtBottom(true);
              }}>
                Zu neuesten Nachrichten
              </MiniButton>
            </div>
          )}

          {/* Input */}
          <div style={{
            padding: "12px 24px",
            borderTop: `1px solid ${T.border}`,
            background: T.surface,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              disabled={isSending}
              placeholder={isSending ? "Sende…" : "Intervention eingeben…"}
              style={{
                flex: 1,
                background: T.surfaceAlt,
                border: `1px solid ${T.border}`,
                borderRadius: 10,
                padding: "10px 14px",
                fontSize: 13,
                color: T.text,
                outline: "none",
                opacity: isSending ? 0.6 : 1,
              }}
            />
            <button
              onClick={handleSend}
              disabled={isSending || !input.trim()}
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                border: "none",
                background: (!isSending && input.trim()) ? T.accent : T.surfaceAlt,
                color: (!isSending && input.trim()) ? "#fff" : T.textDim,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: (!isSending && input.trim()) ? "pointer" : "not-allowed",
                transition: "background 0.15s",
                flexShrink: 0,
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: T.textDim }}>
          <Ghost size={56} style={{ opacity: 0.15, marginBottom: 16 }} />
          <p style={{ fontSize: 13, margin: 0 }}>Session auswählen</p>
        </div>
      )}
    </div>
  );

  return (
    <>
      <div className="flex flex-col flex-1 h-[calc(100dvh-140px)] min-h-[520px] max-h-[980px] rounded-2xl overflow-hidden" style={{ border: `1px solid ${T.border}` }}>
        {/* Desktop */}
        <div className="hidden md:grid h-full" style={{ gridTemplateColumns: "340px 1fr", minHeight: 0 }}>
          {listPanel}
          {chatPanel}
        </div>
        {/* Mobile */}
        <div className="md:hidden flex flex-col h-full" style={{ minHeight: 0 }}>
          {mobileView === "list" ? listPanel : chatPanel}
        </div>
      </div>
      <Modal
        open={showLinkDialog}
        onClose={() => setShowLinkDialog(false)}
        title="Member verknüpfen"
        subtitle="Bitte Member ID eingeben (z. B. M-1005)."
        width="min(480px,100%)"
      >
        <div style={{ display: "grid", gap: 10 }}>
          <input
            value={memberIdInput}
            onChange={(e) => setMemberIdInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleGenerateToken();
            }}
            placeholder="Member ID"
            style={{
              borderRadius: 10,
              border: `1px solid ${T.border}`,
              background: T.surfaceAlt,
              color: T.text,
              padding: "10px 12px",
              fontSize: 13,
              outline: "none",
            }}
          />
          {actionError && <div style={{ fontSize: 12, color: T.danger }}>{actionError}</div>}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button
              onClick={() => setShowLinkDialog(false)}
              style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "8px 10px", cursor: "pointer" }}
            >
              Abbrechen
            </button>
            <button
              onClick={() => void handleGenerateToken()}
              style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "8px 12px", cursor: "pointer" }}
            >
              Token erstellen
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
