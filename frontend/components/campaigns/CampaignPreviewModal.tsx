"use client";

import { useEffect, useState } from "react";
import {
  X, CheckCircle, Edit3, ThumbsUp, Clock,
  Mail, MessageSquare, Send, Smartphone, Globe, Megaphone,
} from "lucide-react";
import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { apiFetch } from "@/lib/api";

interface CampaignPreviewData {
  id: number;
  name: string;
  channel: string;
  status: string;
  content_subject: string | null;
  content_body: string | null;
  content_html: string | null;
  ai_generated_content: string | null;
  scheduled_at: string | null;
}

const CHANNEL_MAP: Record<string, { label: string; icon: typeof Mail; color: string }> = {
  email:    { label: "E-Mail",      icon: Mail,          color: T.email },
  whatsapp: { label: "WhatsApp",    icon: MessageSquare, color: T.whatsapp },
  telegram: { label: "Telegram",    icon: Send,          color: T.telegram },
  sms:      { label: "SMS",         icon: Smartphone,    color: T.phone },
  multi:    { label: "Multi-Kanal", icon: Globe,         color: T.accent },
};

interface Props {
  token: string;
  onClose: () => void;
  onApproved?: () => void;
  onRejected?: () => void;
}

export default function CampaignPreviewModal({ token, onClose, onApproved, onRejected }: Props) {
  const [campaign, setCampaign] = useState<CampaignPreviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch(`/admin/campaigns/preview/${token}`);
        if (res.ok) {
          setCampaign(await res.json());
        } else {
          setError("Kampagne nicht gefunden oder Link abgelaufen.");
        }
      } catch {
        setError("Fehler beim Laden der Kampagne.");
      }
      setLoading(false);
    };
    load();
  }, [token]);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleApprove = async () => {
    if (!campaign) return;
    const res = await apiFetch(`/admin/campaigns/${campaign.id}/approve`, { method: "POST" });
    if (res.ok) {
      setApproved(true);
      onApproved?.();
    }
  };

  const handleReject = async () => {
    if (!campaign) return;
    const res = await apiFetch(`/admin/campaigns/${campaign.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: "draft" }),
    });
    if (res.ok) {
      setRejected(true);
      onRejected?.();
    }
  };

  const channelInfo = campaign ? (CHANNEL_MAP[campaign.channel] || CHANNEL_MAP.email) : CHANNEL_MAP.email;
  const ChannelIcon = channelInfo.icon;

  return (
    /* Backdrop */
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "24px 16px",
      }}
    >
      {/* Modal panel */}
      <div style={{
        background: T.surface,
        borderRadius: 16,
        border: `1px solid ${T.border}`,
        width: "100%",
        maxWidth: 700,
        maxHeight: "90vh",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        boxShadow: "0 24px 80px rgba(0,0,0,0.4)",
      }}>
        {/* Modal header bar */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "16px 20px",
          borderBottom: `1px solid ${T.border}`,
          background: T.surfaceAlt,
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Megaphone size={16} color="#fff" />
            </div>
            <div>
              <p style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>Kampagnen-Vorschau</p>
              {campaign && (
                <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>{campaign.name}</p>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: 8,
              background: "transparent", border: `1px solid ${T.border}`,
              color: T.textMuted, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Scrollable body */}
        <div style={{ overflowY: "auto", flex: 1, padding: 20 }}>
          {loading && (
            <div style={{ textAlign: "center", padding: "40px 0", color: T.textMuted, fontSize: 13 }}>
              Kampagne wird geladen...
            </div>
          )}

          {error && (
            <div style={{
              padding: 16, borderRadius: 10,
              background: `${T.danger}15`, border: `1px solid ${T.danger}40`,
              color: T.danger, fontSize: 13, textAlign: "center",
            }}>
              {error}
            </div>
          )}

          {campaign && !loading && (
            <>
              {/* Approval status banners */}
              {approved && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "12px 16px", borderRadius: 10, marginBottom: 16,
                  background: `${T.success}15`, border: `1px solid ${T.success}40`,
                }}>
                  <CheckCircle size={18} color={T.success} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: T.success, margin: 0 }}>Kampagne freigegeben!</p>
                    <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>Wird zum geplanten Zeitpunkt versendet.</p>
                  </div>
                </div>
              )}
              {rejected && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "12px 16px", borderRadius: 10, marginBottom: 16,
                  background: `${T.warning}15`, border: `1px solid ${T.warning}40`,
                }}>
                  <Edit3 size={18} color={T.warning} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: T.warning, margin: 0 }}>Zurück zum Entwurf</p>
                    <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>Zur Überarbeitung zurückgesetzt.</p>
                  </div>
                </div>
              )}

              {/* Meta row */}
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: 9,
                  background: `${channelInfo.color}15`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <ChannelIcon size={16} color={channelInfo.color} />
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0 }}>{campaign.name}</p>
                  <div style={{ display: "flex", gap: 6, marginTop: 3 }}>
                    <Badge variant="accent">{channelInfo.label}</Badge>
                    {campaign.scheduled_at && (
                      <Badge variant="info">
                        <Clock size={10} />
                        {new Date(campaign.scheduled_at).toLocaleDateString("de-DE", {
                          day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
                        })}
                      </Badge>
                    )}
                    {campaign.ai_generated_content && <Badge variant="accent">✨ KI-generiert</Badge>}
                  </div>
                </div>
              </div>

              {/* Subject line */}
              {campaign.content_subject && (
                <div style={{
                  padding: "10px 14px", borderRadius: 8, marginBottom: 12,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                }}>
                  <span style={{ fontSize: 11, color: T.textMuted, fontWeight: 600 }}>Betreff: </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{campaign.content_subject}</span>
                </div>
              )}

              {/* Email HTML preview in iframe for isolation */}
              {campaign.content_html ? (
                <div style={{
                  borderRadius: 10, overflow: "hidden",
                  border: `1px solid ${T.border}`,
                  marginBottom: 16,
                  background: "#ffffff",
                }}>
                  <div style={{
                    padding: "8px 14px", background: T.surfaceAlt,
                    borderBottom: `1px solid ${T.border}`,
                    fontSize: 11, color: T.textMuted, fontWeight: 600,
                    textTransform: "uppercase", letterSpacing: "0.05em",
                  }}>
                    E-Mail Vorschau
                  </div>
                  <iframe
                    srcDoc={campaign.content_html}
                    style={{ width: "100%", border: "none", minHeight: 480, display: "block" }}
                    sandbox="allow-same-origin"
                    title="E-Mail Vorschau"
                    onLoad={(e) => {
                      const iframe = e.currentTarget;
                      const doc = iframe.contentDocument;
                      if (doc) {
                        iframe.style.height = doc.documentElement.scrollHeight + "px";
                      }
                    }}
                  />
                </div>
              ) : (
                <div style={{
                  padding: 16, borderRadius: 10,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  fontSize: 13, color: T.text, lineHeight: 1.7,
                  whiteSpace: "pre-wrap", marginBottom: 16,
                }}>
                  {campaign.content_body || "Kein Inhalt vorhanden."}
                </div>
              )}

              {/* Approval actions */}
              {!approved && !rejected && campaign.status !== "sent" && (
                <div style={{
                  padding: 16, borderRadius: 12,
                  border: `1px solid ${T.border}`,
                  background: T.surfaceAlt,
                }}>
                  <p style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: "0 0 12px" }}>
                    Freigabe-Entscheidung
                  </p>
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Anmerkungen oder Änderungswünsche (optional)..."
                    rows={2}
                    style={{
                      width: "100%", padding: "10px 14px",
                      background: T.surface, border: `1px solid ${T.border}`,
                      borderRadius: 8, color: T.text,
                      fontSize: 13, outline: "none", resize: "vertical",
                      boxSizing: "border-box", marginBottom: 12,
                    }}
                  />
                  <div style={{ display: "flex", gap: 10 }}>
                    <button
                      onClick={handleApprove}
                      style={{
                        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                        gap: 8, padding: "11px 20px",
                        background: `linear-gradient(135deg, ${T.success}, #00B87A)`,
                        color: "#fff", border: "none", borderRadius: 9,
                        fontSize: 13, fontWeight: 700, cursor: "pointer",
                      }}
                    >
                      <ThumbsUp size={15} /> Freigeben & Senden
                    </button>
                    <button
                      onClick={handleReject}
                      style={{
                        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
                        gap: 8, padding: "11px 20px",
                        background: T.surface, color: T.textMuted,
                        border: `1px solid ${T.border}`, borderRadius: 9,
                        fontSize: 13, fontWeight: 600, cursor: "pointer",
                      }}
                    >
                      <Edit3 size={15} /> Überarbeiten
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
