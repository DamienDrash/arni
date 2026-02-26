"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  CheckCircle, XCircle, Clock, Mail, MessageSquare, Send,
  Smartphone, Globe, Megaphone, ArrowLeft, ThumbsUp, ThumbsDown,
  Edit3, Eye,
} from "lucide-react";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { apiFetch } from "@/lib/api";

interface CampaignPreview {
  id: number;
  name: string;
  description: string | null;
  channel: string;
  status: string;
  content_subject: string | null;
  content_body: string | null;
  content_html: string | null;
  ai_generated_content: string | null;
  target_type: string;
  scheduled_at: string | null;
  created_at: string;
}

const CHANNEL_MAP: Record<string, { label: string; icon: typeof Mail; color: string }> = {
  email: { label: "E-Mail", icon: Mail, color: T.email },
  whatsapp: { label: "WhatsApp", icon: MessageSquare, color: T.whatsapp },
  telegram: { label: "Telegram", icon: Send, color: T.telegram },
  sms: { label: "SMS", icon: Smartphone, color: T.phone },
  multi: { label: "Multi-Kanal", icon: Globe, color: T.accent },
};

export default function CampaignPreviewPage() {
  const params = useParams();
  const token = params?.token as string;
  const [campaign, setCampaign] = useState<CampaignPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    if (!token) return;
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

  const handleApprove = async () => {
    if (!campaign) return;
    try {
      const res = await apiFetch(`/admin/campaigns/${campaign.id}/approve`, { method: "POST" });
      if (res.ok) setApproved(true);
    } catch { /* ignore */ }
  };

  const handleReject = async () => {
    if (!campaign) return;
    try {
      const res = await apiFetch(`/admin/campaigns/${campaign.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "draft" }),
      });
      if (res.ok) setRejected(true);
    } catch { /* ignore */ }
  };

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh", background: T.bg, display: "flex",
        alignItems: "center", justifyContent: "center",
      }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: T.accentDim, display: "flex",
            alignItems: "center", justifyContent: "center", margin: "0 auto 16px",
          }}>
            <Eye size={24} color={T.accent} />
          </div>
          <p style={{ color: T.textMuted, fontSize: 14 }}>Kampagne wird geladen...</p>
        </div>
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div style={{
        minHeight: "100vh", background: T.bg, display: "flex",
        alignItems: "center", justifyContent: "center",
      }}>
        <Card style={{ padding: 40, textAlign: "center", maxWidth: 440 }}>
          <XCircle size={40} color={T.danger} style={{ marginBottom: 16 }} />
          <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>
            Vorschau nicht verfügbar
          </h2>
          <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
            {error || "Die Kampagne konnte nicht geladen werden."}
          </p>
        </Card>
      </div>
    );
  }

  const channelInfo = CHANNEL_MAP[campaign.channel] || CHANNEL_MAP.email;
  const ChannelIcon = channelInfo.icon;
  const displayContent = campaign.ai_generated_content || campaign.content_body || "";

  return (
    <div style={{ minHeight: "100vh", background: T.bg, padding: "40px 20px" }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 16px",
          }}>
            <Megaphone size={28} color="#fff" />
          </div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: T.text, margin: "0 0 4px", letterSpacing: "-0.02em" }}>
            Kampagnen-Vorschau
          </h1>
          <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
            Prüfen und genehmigen Sie den Inhalt vor dem Versand
          </p>
        </div>

        {/* Approval Status */}
        {approved && (
          <Card style={{ padding: 20, marginBottom: 20, background: T.successDim, border: `1px solid ${T.success}40` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <CheckCircle size={20} color={T.success} />
              <div>
                <p style={{ fontSize: 14, fontWeight: 600, color: T.success, margin: 0 }}>Kampagne freigegeben!</p>
                <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>Die Kampagne wurde genehmigt und wird zum geplanten Zeitpunkt versendet.</p>
              </div>
            </div>
          </Card>
        )}
        {rejected && (
          <Card style={{ padding: 20, marginBottom: 20, background: T.warningDim, border: `1px solid ${T.warning}40` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Edit3 size={20} color={T.warning} />
              <div>
                <p style={{ fontSize: 14, fontWeight: 600, color: T.warning, margin: 0 }}>Zurück zum Entwurf</p>
                <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>Die Kampagne wurde zur Überarbeitung zurückgesetzt.</p>
              </div>
            </div>
          </Card>
        )}

        {/* Campaign Info */}
        <Card style={{ padding: 24, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: `${channelInfo.color}15`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <ChannelIcon size={18} color={channelInfo.color} />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: 0 }}>{campaign.name}</h2>
              <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                <Badge variant="accent">{channelInfo.label}</Badge>
                {campaign.scheduled_at && (
                  <Badge variant="info">
                    <Clock size={10} /> {new Date(campaign.scheduled_at).toLocaleDateString("de-DE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                  </Badge>
                )}
              </div>
            </div>
          </div>
          {campaign.description && (
            <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 12px", lineHeight: 1.5 }}>
              {campaign.description}
            </p>
          )}
        </Card>

        {/* Content Preview */}
        <Card style={{ padding: 0, marginBottom: 16, overflow: "hidden" }}>
          <div style={{ padding: "12px 20px", background: T.surfaceAlt, borderBottom: `1px solid ${T.border}` }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: T.textMuted, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Nachrichteninhalt
            </span>
          </div>

          {campaign.content_subject && (
            <div style={{ padding: "12px 20px", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 11, color: T.textMuted }}>Betreff: </span>
              <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{campaign.content_subject}</span>
            </div>
          )}

          {campaign.content_html ? (
            <div
              style={{ padding: 20, background: "#fff", color: "#333" }}
              dangerouslySetInnerHTML={{ __html: campaign.content_html }}
            />
          ) : (
            <div style={{ padding: 20, fontSize: 14, color: T.text, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
              {displayContent || "Kein Inhalt vorhanden."}
            </div>
          )}

          {campaign.ai_generated_content && (
            <div style={{ padding: "8px 20px", background: T.accentDim, borderTop: `1px solid ${T.accent}30` }}>
              <span style={{ fontSize: 11, color: T.accentLight, fontWeight: 500 }}>
                ✨ Dieser Inhalt wurde von der KI generiert
              </span>
            </div>
          )}
        </Card>

        {/* Approval Actions */}
        {!approved && !rejected && campaign.status !== "sent" && (
          <Card style={{ padding: 24 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 16px" }}>
              Freigabe-Entscheidung
            </h3>
            <div>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: T.textMuted, marginBottom: 6 }}>
                Feedback (optional)
              </label>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="Anmerkungen oder Änderungswünsche..."
                rows={3}
                style={{
                  width: "100%", padding: "10px 14px", background: T.surfaceAlt,
                  border: `1px solid ${T.border}`, borderRadius: 8, color: T.text,
                  fontSize: 13, outline: "none", resize: "vertical", boxSizing: "border-box",
                }}
              />
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
              <button
                onClick={handleApprove}
                style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "12px 24px",
                  background: `linear-gradient(135deg, ${T.success}, #00B87A)`,
                  color: "#fff", border: "none", borderRadius: 10,
                  fontSize: 14, fontWeight: 700, cursor: "pointer", flex: 1,
                  justifyContent: "center",
                }}
              >
                <ThumbsUp size={16} /> Freigeben & Senden
              </button>
              <button
                onClick={handleReject}
                style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "12px 24px",
                  background: T.surfaceAlt, color: T.textMuted,
                  border: `1px solid ${T.border}`, borderRadius: 10,
                  fontSize: 14, fontWeight: 600, cursor: "pointer", flex: 1,
                  justifyContent: "center",
                }}
              >
                <Edit3 size={16} /> Überarbeiten
              </button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
