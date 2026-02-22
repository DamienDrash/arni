"use client";

import { useState } from "react";
import { Search, Filter, Eye, AlertTriangle, Archive, ThumbsUp, ThumbsDown, ArrowLeft } from "lucide-react";

import { T } from "@/lib/tokens";
import { conversations } from "@/lib/mock-data";
import { Badge } from "@/components/ui/Badge";
import { MiniButton } from "@/components/ui/MiniButton";
import { Avatar } from "@/components/ui/Avatar";
import { ChannelIcon } from "@/components/ui/ChannelIcon";

type FilterStatus = "all" | "resolved" | "pending" | "escalated";

const mockMessages = (issue: string) => [
  { from: "member", text: issue, time: "14:22" },
  { from: "ai", text: "Hallo! Ich bin ARIIA, dein KI-Assistent. Lass mich das für dich prüfen. Einen Moment bitte…", time: "14:22" },
  { from: "ai", text: "Ich habe deine Mitgliederdaten in Magicline gefunden. Ich kann dir bei dieser Anfrage weiterhelfen.", time: "14:23" },
  { from: "member", text: "Super, danke!", time: "14:23" },
];

export function ConversationsPage() {
  const [selected, setSelected] = useState(0);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>("all");
  const [mobileView, setMobileView] = useState<"list" | "chat">("list");

  const filtered = filterStatus === "all" ? conversations : conversations.filter(c => c.status === filterStatus);
  const active = conversations[selected];
  const messages = mockMessages(active?.issue ?? "");

  const handleSelect = (idx: number) => {
    setSelected(idx);
    setMobileView("chat");
  };

  const listPanel = (
    <div style={{ background: T.surface, display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "20px 16px 12px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, padding: "8px 12px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
            <Search size={14} color={T.textDim} />
            <span style={{ fontSize: 12, color: T.textDim }}>Konversationen durchsuchen…</span>
          </div>
          <MiniButton><Filter size={12} /></MiniButton>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {(["all", "resolved", "pending", "escalated"] as const).map(f => (
            <MiniButton key={f} active={filterStatus === f} onClick={() => setFilterStatus(f)}>
              {{ all: "Alle", resolved: "Gelöst", pending: "Offen", escalated: "Eskaliert" }[f]}
            </MiniButton>
          ))}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {filtered.map((conv) => {
          const idx = conversations.indexOf(conv);
          return (
            <button
              key={conv.id}
              type="button"
              aria-label={`Konversation öffnen: ${conv.member}`}
              onClick={() => handleSelect(idx)}
              style={{
                width: "100%",
                border: "none",
                textAlign: "left",
                padding: "14px 16px",
                borderBottom: `1px solid ${T.border}`,
                cursor: "pointer",
                background: selected === idx ? T.accentDim : "transparent",
                transition: "background 0.15s",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <Avatar
                  initials={conv.avatar}
                  size={36}
                  color={conv.status === "escalated" ? T.danger : conv.status === "pending" ? T.wariiang : T.accent}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{conv.member}</span>
                    <span style={{ fontSize: 10, color: T.textDim }}>{conv.time}</span>
                  </div>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: "3px 0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{conv.issue}</p>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                    <ChannelIcon channel={conv.channel as "whatsapp" | "telegram" | "email" | "phone"} size={10} />
                    <Badge variant={conv.status === "resolved" ? "success" : conv.status === "escalated" ? "danger" : "wariiang"} size="xs">
                      {conv.status === "resolved" ? "Gelöst" : conv.status === "escalated" ? "Eskaliert" : "Offen"}
                    </Badge>
                    <Badge size="xs">{conv.confidence}%</Badge>
                  </div>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );

  const chatPanel = (
    <div style={{ background: T.bg, display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Chat Header */}
      <div style={{ padding: "16px 24px", borderBottom: `1px solid ${T.border}`, background: T.surface, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {/* Mobile back button */}
          <button
            className="md:hidden"
            onClick={() => setMobileView("list")}
            style={{ background: "none", border: "none", cursor: "pointer", color: T.textMuted, display: "flex", padding: 4, marginRight: 4 }}
            aria-label="Zurück zur Liste"
          >
            <ArrowLeft size={18} />
          </button>
          <Avatar initials={active?.avatar ?? ""} size={38} />
          <div>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>{active?.member}</h3>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
              <ChannelIcon channel={active?.channel as "whatsapp" | "telegram" | "email" | "phone"} size={10} />
              <span style={{ fontSize: 11, color: T.textMuted }}>{active?.id} · {active?.messages} Nachrichten</span>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <MiniButton><Eye size={12} /> Magicline</MiniButton>
          <MiniButton><AlertTriangle size={12} /> Eskalieren</MiniButton>
          <MiniButton><Archive size={12} /></MiniButton>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: "flex", justifyContent: msg.from === "member" ? "flex-start" : "flex-end" }}>
            <div style={{
              maxWidth: "80%", padding: "12px 16px", borderRadius: 14,
              background: msg.from === "member" ? T.surfaceAlt : T.accentDim,
              border: `1px solid ${msg.from === "member" ? T.border : "rgba(108,92,231,0.3)"}`,
            }}>
              <p style={{ fontSize: 13, color: T.text, margin: 0, lineHeight: 1.5 }}>{msg.text}</p>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6, marginTop: 6 }}>
                <span style={{ fontSize: 10, color: T.textDim }}>{msg.time}</span>
                {msg.from === "ai" && <Badge variant="accent" size="xs">ARIIA</Badge>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div style={{ padding: "12px 24px", borderTop: `1px solid ${T.border}`, background: T.surface, display: "flex", alignItems: "center", gap: 16 }}>
        <Badge variant={active?.sentiment === "positive" ? "success" : active?.sentiment === "negative" ? "danger" : "default"}>
          {active?.sentiment === "positive" ? "😊 Positiv" : active?.sentiment === "negative" ? "😟 Negativ" : "😐 Neutral"}
        </Badge>
        <div style={{ flex: 1 }} />
        <button type="button" aria-label="Hilfreich" style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0 }}>
          <ThumbsUp size={14} color={T.textDim} />
        </button>
        <button type="button" aria-label="Nicht hilfreich" style={{ border: "none", background: "transparent", cursor: "pointer", padding: 0 }}>
          <ThumbsDown size={14} color={T.textDim} />
        </button>
      </div>
    </div>
  );

  return (
    <div style={{ borderRadius: 16, overflow: "hidden", border: `1px solid ${T.border}`, height: "calc(100vh - 120px)" }}>
      {/* Desktop: side-by-side */}
      <div className="hidden md:grid h-full" style={{ gridTemplateColumns: "380px 1fr" }}>
        {listPanel}
        {chatPanel}
      </div>

      {/* Mobile: single panel at a time */}
      <div className="md:hidden h-full">
        {mobileView === "list" ? listPanel : chatPanel}
      </div>
    </div>
  );
}
