"use client";

import { useEffect, useState, useCallback } from "react";
import { AlertTriangle, Clock, CheckCircle2, TrendingDown, RefreshCw, CheckCircle, Phone } from "lucide-react";

import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MiniButton } from "@/components/ui/MiniButton";
import { Stat } from "@/components/ui/Stat";
import { ChannelIcon } from "@/components/ui/ChannelIcon";
import { Modal } from "@/components/ui/Modal";

type Handoff = {
  user_id: string;
  key: string;
  user_name?: string | null;
  platform?: string | null;
  member_id?: string | null;
  active_token?: string | null;
};

type Stats = {
  active_handoffs: number;
  total_sessions?: number;
  total_messages?: number;
};

const priorityColor: Record<string, string> = {
  high: T.wariiang,
  medium: T.info,
  low: T.textDim,
};

const priorityLabel: Record<string, string> = {
  high: "HOCH",
  medium: "MITTEL",
  low: "NIEDRIG",
};

function getPriority(h: Handoff): "high" | "medium" | "low" {
  if (!h.member_id) return "high";   // unverified = urgent
  return "medium";
}

function getReason(h: Handoff): string {
  if (!h.member_id) return "Nutzer nicht verifiziert – menschlicher Support angefordert";
  return "Handoff angefordert";
}

export function EscalationsPage() {
  const [handoffs, setHandoffs] = useState<Handoff[]>([]);
  const [apiStats, setApiStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeToken, setActiveToken] = useState<string | null>(null);
  const [tokenForUser, setTokenForUser] = useState<string | null>(null);
  const [linkDialogUserId, setLinkDialogUserId] = useState<string | null>(null);
  const [memberIdInput, setMemberIdInput] = useState("");
  const [confirmResolveUserId, setConfirmResolveUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [handoffsRes, statsRes] = await Promise.all([
        apiFetch("/admin/handoffs"),
        apiFetch("/admin/stats"),
      ]);
      if (handoffsRes.ok) setHandoffs(await handoffsRes.json());
      if (statsRes.ok) setApiStats(await statsRes.json());
    } catch (e) {
      console.error("EscalationsPage fetch failed", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function handleGenerateToken(userId: string) {
    if (!memberIdInput.trim()) {
      setActionError("Bitte eine gültige Member ID angeben.");
      return;
    }
    try {
      const res = await apiFetch("/admin/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: memberIdInput.trim(), user_id: userId }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveToken(data.token);
        setTokenForUser(userId);
        setLinkDialogUserId(null);
        setMemberIdInput("");
        setActionError("");
        fetchData();
      } else {
        setActionError(`Token-Generierung fehlgeschlagen (${res.status}).`);
      }
    } catch {
      setActionError("Fehler bei der Token-Generierung.");
    }
  }

  async function resolveHandoff(userId: string) {
    try {
      const res = await apiFetch(`/admin/handoffs/${userId}/resolve`, { method: "POST" });
      if (res.ok) {
        setConfirmResolveUserId(null);
        fetchData();
      } else {
        setActionError(`Auflösen fehlgeschlagen (${res.status}).`);
      }
    } catch {
      setActionError("Fehler beim Auflösen des Handoffs.");
    }
  }

  const openCount = apiStats?.active_handoffs ?? handoffs.length;

  const stats = [
    { label: "Offene Eskalationen", value: String(openCount),    color: T.danger,  icon: <AlertTriangle size={18} /> },
    { label: "Ø Bearbeitungszeit",  value: "–",                  unit: "min", color: T.wariiang, icon: <Clock size={18} /> },
    { label: "Heute gelöst",        value: "–",                  color: T.success, icon: <CheckCircle2 size={18} /> },
    { label: "Eskalationsrate",     value: "–",                  unit: "%", color: T.info,    icon: <TrendingDown size={18} /> },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Token Banner */}
      {activeToken && (
        <div style={{
          background: T.accentDim,
          border: `1px solid ${T.accent}`,
          borderRadius: 12,
          padding: "14px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <Phone size={18} color={T.accentLight} />
            <div>
              <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Verifizierungscode{tokenForUser ? ` · ${tokenForUser}` : ""}
              </div>
              <div style={{ fontSize: 22, fontFamily: "monospace", fontWeight: 700, color: T.accentLight, letterSpacing: "0.15em" }}>
                {activeToken}
              </div>
            </div>
          </div>
          <MiniButton onClick={() => { setActiveToken(null); setTokenForUser(null); }}>✕</MiniButton>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s, i) => (
          <Card key={i} style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: `${s.color}15`, display: "flex", alignItems: "center", justifyContent: "center", color: s.color }}>
                {s.icon}
              </div>
              <Stat label={s.label} value={s.value} unit={s.unit} color={s.color} />
            </div>
          </Card>
        ))}
      </div>

      {/* Escalation Queue */}
      <Card style={{ padding: 24 }}>
        <SectionHeader
          title="Eskalations-Queue"
          subtitle="Tickets die menschliche Bearbeitung benötigen"
          action={
            <MiniButton onClick={fetchData}>
              <RefreshCw size={12} /> Aktualisieren
            </MiniButton>
          }
        />

        {isLoading ? (
          <div style={{ padding: "32px 0", textAlign: "center", color: T.textMuted }}>Lädt…</div>
        ) : handoffs.length === 0 ? (
          <div style={{ padding: "48px 0", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div style={{ padding: 16, background: "#E2FBD7", borderRadius: "50%", color: "#3DD598" }}>
              <CheckCircle size={32} />
            </div>
            <span style={{ fontWeight: 700, color: T.text }}>Alles klar</span>
            <span style={{ fontSize: 13, color: T.textMuted }}>Keine offenen Eskalationen.</span>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {handoffs.map((h) => {
              const priority = getPriority(h);
              return (
                <div
                  key={h.user_id}
                  style={{
                    padding: "16px 20px", borderRadius: 12, background: T.surfaceAlt,
                    border: `1px solid ${priority === "high" ? "rgba(255,107,107,0.3)" : T.border}`,
                    display: "flex", alignItems: "center", gap: 16,
                  }}
                >
                  <div style={{ width: 4, height: 48, borderRadius: 2, background: priorityColor[priority] }} />
                  <ChannelIcon channel={(h.platform ?? "telegram") as "whatsapp" | "telegram" | "email" | "phone"} size={16} />
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: T.text }}>{h.user_name || h.user_id}</span>
                      <span style={{ fontSize: 11, color: T.textDim, fontFamily: "monospace" }}>
                        {h.member_id ? h.member_id : h.user_id}
                      </span>
                      <Badge variant={priority === "high" ? "wariiang" : "info"} size="xs">
                        {priorityLabel[priority]}
                      </Badge>
                    </div>
                    <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{getReason(h)}</p>
                    {h.active_token && (
                      <span style={{ fontSize: 11, fontFamily: "monospace", color: T.accentLight, background: T.accentDim, padding: "2px 8px", borderRadius: 6, border: `1px solid ${T.accent}50`, marginTop: 4, display: "inline-block" }}>
                        Token: {h.active_token}
                      </span>
                    )}
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <p style={{ fontSize: 11, color: T.danger, fontWeight: 600, margin: "0 0 4px" }}>
                      ⚠ Nicht zugewiesen
                    </p>
                    <span style={{ fontSize: 10, color: T.textDim }}>
                      {h.platform ?? "unbekannt"}
                    </span>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, marginLeft: 8 }}>
                    {!h.member_id && (
                      <MiniButton
                        onClick={() => {
                          setLinkDialogUserId(h.user_id);
                          setMemberIdInput("");
                          setActionError("");
                        }}
                      >
                        <Phone size={12} /> Link Member
                      </MiniButton>
                    )}
                    <MiniButton onClick={() => setConfirmResolveUserId(h.user_id)}>
                      <CheckCircle2 size={12} /> Lösen
                    </MiniButton>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
      {actionError && (
        <Card style={{ padding: 12, border: `1px solid ${T.danger}55`, background: T.dangerDim }}>
          <div style={{ fontSize: 12, color: T.danger }}>{actionError}</div>
        </Card>
      )}
      <Modal
        open={!!linkDialogUserId}
        onClose={() => setLinkDialogUserId(null)}
        title="Member verknüpfen"
        subtitle={linkDialogUserId ? `Handoff: ${linkDialogUserId}` : ""}
        width="min(460px,100%)"
      >
        {linkDialogUserId && (
          <div style={{ display: "grid", gap: 10 }}>
            <input
              value={memberIdInput}
              onChange={(e) => setMemberIdInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleGenerateToken(linkDialogUserId);
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
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                onClick={() => setLinkDialogUserId(null)}
                style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "8px 10px", cursor: "pointer" }}
              >
                Abbrechen
              </button>
              <button
                onClick={() => void handleGenerateToken(linkDialogUserId)}
                style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "8px 12px", cursor: "pointer" }}
              >
                Token erstellen
              </button>
            </div>
          </div>
        )}
      </Modal>
      <Modal
        open={!!confirmResolveUserId}
        onClose={() => setConfirmResolveUserId(null)}
        title="Handoff auflösen?"
        subtitle={confirmResolveUserId ? `Der Handoff für ${confirmResolveUserId} wird geschlossen.` : ""}
        width="min(460px,100%)"
      >
        {confirmResolveUserId && (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ fontSize: 12, color: T.textMuted }}>
              Die KI übernimmt danach wieder automatisch die Kommunikation.
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                onClick={() => setConfirmResolveUserId(null)}
                style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "8px 10px", cursor: "pointer" }}
              >
                Abbrechen
              </button>
              <button
                onClick={() => void resolveHandoff(confirmResolveUserId)}
                style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "8px 12px", cursor: "pointer" }}
              >
                Auflösen
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
