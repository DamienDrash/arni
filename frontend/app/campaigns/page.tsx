"use client";
import React, { useCallback, useEffect, useState, useMemo } from "react";
import {
  Megaphone, Plus, Send, Clock, CheckCircle, Eye,
  Trash2, Mail, MessageSquare, Phone, Users,
  Calendar, ChevronRight, Zap, Search, RefreshCw,
  Globe, Smartphone, Target, TrendingUp, BarChart3,
} from "lucide-react";
import { T } from "@/lib/tokens";
import CreateCampaignWizard from "@/components/campaigns/CreateCampaignWizard";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { apiFetch } from "@/lib/api";
import { usePermissions } from "@/lib/permissions";

/* ═══════════════════════════════════════════════════════════════════════════
   TYPES
   ═══════════════════════════════════════════════════════════════════════════ */

interface Campaign {
  id: number;
  name: string;
  description: string | null;
  type: string;
  status: string;
  channel: string;
  target_type: string;
  content_subject: string | null;
  content_body: string | null;
  content_html: string | null;
  ai_prompt: string | null;
  ai_generated_content: string | null;
  preview_token: string | null;
  scheduled_at: string | null;
  sent_at: string | null;
  is_ab_test: boolean;
  stats_total: number;
  stats_sent: number;
  stats_delivered: number;
  stats_opened: number;
  stats_clicked: number;
  stats_failed: number;
  created_at: string;
}

interface OrchestrationStep {
  step_order: number;
  channel: string;
  wait_hours: number;
  condition_type: string;
  subject_override: string | null;
  content_override: string | null;
}

type ViewMode = "list" | "create";

/* ═══════════════════════════════════════════════════════════════════════════
   CONSTANTS
   ═══════════════════════════════════════════════════════════════════════════ */

const STATUS_MAP: Record<string, { label: string; variant: "success" | "warning" | "danger" | "info" | "accent" | "default" }> = {
  draft: { label: "Entwurf", variant: "default" },
  ai_generating: { label: "KI generiert...", variant: "info" },
  pending_review: { label: "Prüfung ausstehend", variant: "warning" },
  approved: { label: "Genehmigt", variant: "success" },
  scheduled: { label: "Geplant", variant: "accent" },
  sending: { label: "Wird gesendet...", variant: "info" },
  sent: { label: "Gesendet", variant: "success" },
  failed: { label: "Fehlgeschlagen", variant: "danger" },
  cancelled: { label: "Abgebrochen", variant: "default" },
};

const CHANNEL_MAP: Record<string, { label: string; icon: typeof Mail; color: string }> = {
  email: { label: "E-Mail", icon: Mail, color: T.email },
  whatsapp: { label: "WhatsApp", icon: MessageSquare, color: T.whatsapp },
  telegram: { label: "Telegram", icon: Send, color: T.telegram },
  sms: { label: "SMS", icon: Smartphone, color: T.phone },
  multi: { label: "Multi-Kanal", icon: Globe, color: T.accent },
};

const TARGET_MAP: Record<string, string> = {
  all_members: "Alle Kontakte",
  segment: "Segment",
  selected: "Ausgewählt",
  tags: "Nach Tags",
};

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════════════════ */

export default function CampaignsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);

  const { plan } = usePermissions();

  /* ─── Data Loading ─────────────────────────────────────────────────────── */

  const loadCampaigns = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns");
      if (res.ok) {
        const data = await res.json();
        setCampaigns(data.items || []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await loadCampaigns();
      setLoading(false);
    })();
  }, [loadCampaigns]);

  /* ─── Filtered Campaigns ───────────────────────────────────────────────── */

  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (channelFilter !== "all" && c.channel !== channelFilter) return false;
      if (searchTerm && !c.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
  }, [campaigns, statusFilter, channelFilter, searchTerm]);

  /* ─── Computed Stats ───────────────────────────────────────────────────── */

  const stats = useMemo(() => ({
    total: campaigns.length,
    scheduled: campaigns.filter(c => c.status === "scheduled").length,
    sent: campaigns.filter(c => c.status === "sent").length,
    pendingReview: campaigns.filter(c => c.status === "pending_review").length,
    draft: campaigns.filter(c => c.status === "draft").length,
    totalSent: campaigns.reduce((sum, c) => sum + (c.stats_sent || 0), 0),
    totalOpened: campaigns.reduce((sum, c) => sum + (c.stats_opened || 0), 0),
    totalClicked: campaigns.reduce((sum, c) => sum + (c.stats_clicked || 0), 0),
  }), [campaigns]);

  const openRate = stats.totalSent > 0 ? ((stats.totalOpened / stats.totalSent) * 100).toFixed(1) : "0.0";
  const clickRate = stats.totalSent > 0 ? ((stats.totalClicked / stats.totalSent) * 100).toFixed(1) : "0.0";

  /* ─── Campaign Actions ─────────────────────────────────────────────────── */

  const approveCampaign = async (id: number) => {
    try {
      await apiFetch(`/admin/campaigns/${id}/approve`, { method: "POST" });
      await loadCampaigns();
    } catch { /* ignore */ }
  };

  const sendCampaign = async (id: number) => {
    try {
      await apiFetch(`/admin/campaigns/${id}/send`, { method: "POST" });
      await loadCampaigns();
    } catch { /* ignore */ }
  };

  const deleteCampaign = async (id: number) => {
    try {
      await apiFetch(`/admin/campaigns/${id}`, { method: "DELETE" });
      await loadCampaigns();
    } catch { /* ignore */ }
  };

  /* ═══════════════════════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════════════════════ */

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 14,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Megaphone size={22} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
              Kampagnen
            </h1>
            <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
              Erstellen, planen und versenden Sie personalisierte Nachrichten
            </p>
          </div>
        </div>
        {viewMode === "list" ? (
          <button
            onClick={() => setViewMode("create")}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "10px 20px",
              background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
              color: "#fff", border: "none", borderRadius: 10,
              fontSize: 13, fontWeight: 600, cursor: "pointer",
              boxShadow: `0 4px 16px ${T.accentDim}`,
              transition: "all 0.2s ease",
            }}
          >
            <Plus size={16} /> Neue Kampagne
          </button>
        ) : (
          <button
            onClick={() => setViewMode("list")}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "10px 20px",
              background: T.surfaceAlt, color: T.textMuted,
              border: `1px solid ${T.border}`, borderRadius: 10,
              fontSize: 13, fontWeight: 500, cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            ← Zurück zur Übersicht
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 80 }}>
          <RefreshCw size={28} color={T.accent} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      )}

      {/* View: Create Wizard */}
      {!loading && viewMode === "create" && (
        <CreateCampaignWizard
          onCreated={() => { setViewMode("list"); loadCampaigns(); }}
          onCancel={() => setViewMode("list")}
        />
      )}

      {/* View: Campaign List */}
      {!loading && viewMode === "list" && (
        <div>
          {/* Quick Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 14, marginBottom: 24 }}>
            {[
              { label: "Gesamt", value: stats.total, icon: Megaphone, color: T.accent },
              { label: "Geplant", value: stats.scheduled, icon: Clock, color: T.warning },
              { label: "Gesendet", value: stats.sent, icon: CheckCircle, color: T.success },
              { label: "Öffnungsrate", value: `${openRate}%`, icon: Eye, color: T.info },
              { label: "Klickrate", value: `${clickRate}%`, icon: TrendingUp, color: T.warning },
            ].map((stat, i) => {
              const Icon = stat.icon;
              return (
                <Card key={i} style={{ padding: 18 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div>
                      <p style={{
                        fontSize: 10, color: T.textMuted, margin: "0 0 6px",
                        fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em",
                      }}>
                        {stat.label}
                      </p>
                      <span style={{ fontSize: 24, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>
                        {stat.value}
                      </span>
                    </div>
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: `${stat.color}15`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <Icon size={16} color={stat.color} />
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Filter Bar */}
          <Card style={{ padding: 14, marginBottom: 20 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8, flex: 1,
                background: T.surfaceAlt, borderRadius: 8, padding: "8px 12px",
                border: `1px solid ${T.border}`,
              }}>
                <Search size={14} color={T.textMuted} />
                <input
                  type="text"
                  placeholder="Kampagne suchen..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  style={{
                    background: "transparent", border: "none", outline: "none",
                    color: T.text, fontSize: 13, width: "100%",
                  }}
                />
              </div>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  borderRadius: 8, padding: "8px 12px", color: T.text,
                  fontSize: 13, outline: "none", cursor: "pointer",
                }}
              >
                <option value="all">Alle Status</option>
                <option value="draft">Entwurf</option>
                <option value="pending_review">Prüfung</option>
                <option value="approved">Genehmigt</option>
                <option value="scheduled">Geplant</option>
                <option value="sending">Wird gesendet</option>
                <option value="sent">Gesendet</option>
                <option value="failed">Fehlgeschlagen</option>
              </select>
              <select
                value={channelFilter}
                onChange={(e) => setChannelFilter(e.target.value)}
                style={{
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  borderRadius: 8, padding: "8px 12px", color: T.text,
                  fontSize: 13, outline: "none", cursor: "pointer",
                }}
              >
                <option value="all">Alle Kanäle</option>
                <option value="email">E-Mail</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="telegram">Telegram</option>
                <option value="sms">SMS</option>
                <option value="multi">Multi-Kanal</option>
              </select>
              <button
                onClick={loadCampaigns}
                style={{
                  padding: "8px 10px", background: T.surfaceAlt, color: T.textMuted,
                  border: `1px solid ${T.border}`, borderRadius: 8, cursor: "pointer",
                  display: "flex", alignItems: "center",
                }}
                title="Aktualisieren"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </Card>

          {/* Pending Review Banner */}
          {stats.pendingReview > 0 && (
            <Card style={{
              padding: 16, marginBottom: 16,
              background: T.warningDim, borderColor: T.warning,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Zap size={18} color={T.warning} />
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>
                    {stats.pendingReview} Kampagne{stats.pendingReview > 1 ? "n" : ""} wartet{stats.pendingReview > 1 ? "en" : ""} auf Freigabe
                  </span>
                  <span style={{ fontSize: 12, color: T.textMuted, marginLeft: 8 }}>
                    KI-generierte Inhalte müssen vor dem Versand geprüft werden.
                  </span>
                </div>
                <button
                  onClick={() => setStatusFilter("pending_review")}
                  style={{
                    padding: "6px 14px", background: T.warning, color: "#000",
                    border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
                  }}
                >
                  Anzeigen
                </button>
              </div>
            </Card>
          )}

          {/* Campaign List */}
          {filteredCampaigns.length === 0 ? (
            <Card style={{ padding: 80, textAlign: "center" }}>
              <Megaphone size={48} color={T.textDim} style={{ marginBottom: 16 }} />
              <p style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>
                {searchTerm || statusFilter !== "all" || channelFilter !== "all"
                  ? "Keine Kampagnen gefunden"
                  : "Noch keine Kampagnen erstellt"}
              </p>
              <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 24px", maxWidth: 400, marginInline: "auto" }}>
                {searchTerm || statusFilter !== "all" || channelFilter !== "all"
                  ? "Versuchen Sie andere Filter oder erstellen Sie eine neue Kampagne."
                  : "Erstellen Sie Ihre erste Kampagne, um personalisierte Nachrichten an Ihre Kontakte zu senden."}
              </p>
              <button
                onClick={() => setViewMode("create")}
                style={{
                  display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 24px",
                  background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                  color: "#fff", border: "none", borderRadius: 10,
                  fontSize: 14, fontWeight: 600, cursor: "pointer",
                  boxShadow: `0 4px 16px ${T.accentDim}`,
                }}
              >
                <Plus size={16} /> Erste Kampagne erstellen
              </button>
            </Card>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filteredCampaigns.map((campaign) => {
                const statusInfo = STATUS_MAP[campaign.status] || STATUS_MAP.draft;
                const channelInfo = CHANNEL_MAP[campaign.channel] || CHANNEL_MAP.email;
                const ChannelIcon = channelInfo.icon;
                return (
                  <Card
                    key={campaign.id}
                    style={{ padding: 20, cursor: "pointer", transition: "all 0.15s ease" }}
                    onClick={() => setSelectedCampaign(campaign)}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                      {/* Channel Icon */}
                      <div style={{
                        width: 44, height: 44, borderRadius: 12,
                        background: `${channelInfo.color}15`,
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                      }}>
                        <ChannelIcon size={20} color={channelInfo.color} />
                      </div>

                      {/* Campaign Info */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{
                            fontSize: 14, fontWeight: 600, color: T.text,
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                          }}>
                            {campaign.name}
                          </span>
                          <Badge variant={statusInfo.variant} size="xs">{statusInfo.label}</Badge>
                          {campaign.is_ab_test && <Badge variant="accent" size="xs">A/B</Badge>}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: T.textMuted }}>
                          <span>{channelInfo.label}</span>
                          <span style={{ color: T.textDim }}>·</span>
                          <span>{TARGET_MAP[campaign.target_type] || campaign.target_type}</span>
                          {campaign.scheduled_at && (
                            <>
                              <span style={{ color: T.textDim }}>·</span>
                              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                <Clock size={11} />
                                {new Date(campaign.scheduled_at).toLocaleDateString("de-DE", {
                                  day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
                                })}
                              </span>
                            </>
                          )}
                          {campaign.created_at && !campaign.scheduled_at && (
                            <>
                              <span style={{ color: T.textDim }}>·</span>
                              <span>
                                Erstellt {new Date(campaign.created_at).toLocaleDateString("de-DE", {
                                  day: "2-digit", month: "short",
                                })}
                              </span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Inline Stats (sent campaigns) */}
                      {campaign.status === "sent" && (
                        <div style={{ display: "flex", gap: 16, marginRight: 12 }}>
                          {[
                            { label: "Gesendet", value: campaign.stats_sent, color: T.text },
                            { label: "Zugestellt", value: campaign.stats_delivered, color: T.success },
                            { label: "Geöffnet", value: campaign.stats_opened, color: T.info },
                            { label: "Geklickt", value: campaign.stats_clicked, color: T.warning },
                          ].map((s, i) => (
                            <div key={i} style={{ textAlign: "center", minWidth: 48 }}>
                              <p style={{ fontSize: 15, fontWeight: 700, color: s.color, margin: 0 }}>{s.value}</p>
                              <p style={{ fontSize: 10, color: T.textMuted, margin: 0 }}>{s.label}</p>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Quick Actions */}
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        {campaign.status === "pending_review" && (
                          <button
                            onClick={(e) => { e.stopPropagation(); approveCampaign(campaign.id); }}
                            style={{
                              padding: "6px 12px", background: T.successDim, color: T.success,
                              border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600,
                              cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                            }}
                          >
                            <CheckCircle size={12} /> Freigeben
                          </button>
                        )}
                        {(campaign.status === "approved" || campaign.status === "draft") && (
                          <button
                            onClick={(e) => { e.stopPropagation(); sendCampaign(campaign.id); }}
                            style={{
                              padding: "6px 12px", background: T.accentDim, color: T.accentLight,
                              border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600,
                              cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                            }}
                          >
                            <Send size={12} /> Senden
                          </button>
                        )}
                        {campaign.preview_token && (
                          <button
                            onClick={(e) => { e.stopPropagation(); window.open(`/campaigns/preview/${campaign.preview_token}`, "_blank"); }}
                            style={{
                              padding: "6px 10px", background: T.surfaceAlt, color: T.textMuted,
                              border: `1px solid ${T.border}`, borderRadius: 6, cursor: "pointer",
                              display: "flex", alignItems: "center",
                            }}
                            title="Vorschau"
                          >
                            <Eye size={12} />
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteCampaign(campaign.id); }}
                          style={{
                            padding: "6px 10px", background: T.dangerDim, color: T.danger,
                            border: "none", borderRadius: 6, cursor: "pointer",
                            display: "flex", alignItems: "center",
                          }}
                          title="Löschen"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>

                      <ChevronRight size={16} color={T.textDim} />
                    </div>
                  </Card>
                );
              })}

              {/* Results Count */}
              <div style={{ textAlign: "center", padding: "12px 0" }}>
                <span style={{ fontSize: 12, color: T.textDim }}>
                  {filteredCampaigns.length} von {campaigns.length} Kampagne{campaigns.length !== 1 ? "n" : ""}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Campaign Detail Modal */}
      {selectedCampaign && (
        <CampaignDetailModal
          campaign={selectedCampaign}
          onClose={() => setSelectedCampaign(null)}
          onApprove={(id) => { approveCampaign(id); setSelectedCampaign(null); }}
          onSend={(id) => { sendCampaign(id); setSelectedCampaign(null); }}
          onDelete={(id) => { deleteCampaign(id); setSelectedCampaign(null); }}
        />
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   CAMPAIGN DETAIL MODAL
   ═══════════════════════════════════════════════════════════════════════════ */

interface CampaignDetailModalProps {
  campaign: Campaign;
  onClose: () => void;
  onApprove: (id: number) => void;
  onSend: (id: number) => void;
  onDelete: (id: number) => void;
}

function CampaignDetailModal({ campaign: c, onClose, onApprove, onSend, onDelete }: CampaignDetailModalProps) {
  const [orchestrationSteps, setOrchestrationSteps] = React.useState<OrchestrationStep[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch(`/admin/campaigns/${c.id}/orchestration-steps`);
        if (res.ok && !cancelled) {
          const data = await res.json();
          if (Array.isArray(data) && data.length > 0) setOrchestrationSteps(data);
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [c.id]);

  const statusInfo = STATUS_MAP[c.status] || STATUS_MAP.draft;
  const channelInfo = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
  const ChannelIcon = channelInfo.icon;

  const CHANNEL_LABELS: Record<string, string> = {
    email: "E-Mail", whatsapp: "WhatsApp", sms: "SMS", telegram: "Telegram",
  };
  const CONDITION_LABELS: Record<string, string> = {
    always: "Immer", if_not_opened: "Wenn nicht geöffnet", if_not_clicked: "Wenn nicht geklickt",
  };

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
        backdropFilter: "blur(4px)",
      }}
      onClick={onClose}
    >
      <Card
        style={{ width: 720, maxHeight: "85vh", overflow: "auto", padding: 32 }}
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14,
              background: `${channelInfo.color}15`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <ChannelIcon size={22} color={channelInfo.color} />
            </div>
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>{c.name}</h3>
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                <Badge variant="default">{channelInfo.label}</Badge>
                {c.is_ab_test && <Badge variant="accent">A/B Test</Badge>}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: "6px 14px", background: T.surfaceAlt, color: T.textMuted,
              border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 12, cursor: "pointer",
            }}
          >
            Schließen
          </button>
        </div>

        {/* Description */}
        {c.description && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Beschreibung</label>
            <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>{c.description}</p>
          </div>
        )}

        {/* Content Preview */}
        {c.content_subject && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Betreff</label>
            <p style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>{c.content_subject}</p>
          </div>
        )}
        {c.content_body && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Inhalt</label>
            <div style={{
              background: T.surfaceAlt, borderRadius: 10, padding: 16,
              border: `1px solid ${T.border}`, fontSize: 13, color: T.text,
              lineHeight: 1.7, whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto",
            }}>
              {c.content_body}
            </div>
          </div>
        )}

        {/* AI Prompt (if used) */}
        {c.ai_prompt && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>KI-Prompt</label>
            <div style={{
              background: T.accentDim, borderRadius: 10, padding: 14,
              border: `1px solid ${T.accent}30`, fontSize: 12, color: T.accentLight,
              lineHeight: 1.6, fontStyle: "italic",
            }}>
              {c.ai_prompt}
            </div>
          </div>
        )}

        {/* Stats */}
        {c.status === "sent" && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Performance</label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
              {[
                { label: "Gesendet", value: c.stats_sent, color: T.text },
                { label: "Zugestellt", value: c.stats_delivered, color: T.success },
                { label: "Geöffnet", value: c.stats_opened, color: T.info },
                { label: "Geklickt", value: c.stats_clicked, color: T.warning },
              ].map((s, i) => (
                <div key={i} style={{
                  textAlign: "center", padding: 14, background: T.surfaceAlt,
                  borderRadius: 10, border: `1px solid ${T.border}`,
                }}>
                  <p style={{ fontSize: 22, fontWeight: 800, color: s.color, margin: 0 }}>{s.value}</p>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: "4px 0 0" }}>{s.label}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Schedule Info */}
        {c.scheduled_at && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Geplanter Versand</label>
            <div style={{
              display: "flex", alignItems: "center", gap: 8, padding: 12,
              background: T.surfaceAlt, borderRadius: 8, border: `1px solid ${T.border}`,
            }}>
              <Calendar size={14} color={T.accent} />
              <span style={{ fontSize: 13, color: T.text }}>
                {new Date(c.scheduled_at).toLocaleDateString("de-DE", {
                  weekday: "long", day: "2-digit", month: "long", year: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </span>
            </div>
          </div>
        )}

        {/* Orchestration Steps */}
        {orchestrationSteps.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <label style={labelStyle}>Omnichannel-Sequenz ({orchestrationSteps.length} Schritte)</label>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {orchestrationSteps.map((s, i) => (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                  background: T.surfaceAlt, borderRadius: 8, border: `1px solid ${T.border}`,
                }}>
                  <div style={{
                    width: 24, height: 24, borderRadius: "50%", background: T.accentDim,
                    color: T.accent, display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 700, flexShrink: 0,
                  }}>{s.step_order}</div>
                  <span style={{ fontSize: 12, fontWeight: 600, color: T.text, minWidth: 70 }}>
                    {CHANNEL_LABELS[s.channel] || s.channel}
                  </span>
                  {i > 0 && (
                    <span style={{ fontSize: 11, color: T.textDim }}>
                      nach {s.wait_hours}h • {CONDITION_LABELS[s.condition_type] || s.condition_type}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{
          display: "flex", gap: 8, paddingTop: 20, marginTop: 8,
          borderTop: `1px solid ${T.border}`,
        }}>
          {c.status === "pending_review" && (
            <button
              onClick={() => onApprove(c.id)}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "10px 18px",
                background: T.success, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <CheckCircle size={14} /> Freigeben
            </button>
          )}
          {(c.status === "approved" || c.status === "draft") && (
            <button
              onClick={() => onSend(c.id)}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "10px 18px",
                background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Send size={14} /> Jetzt senden
            </button>
          )}
          {c.preview_token && (
            <button
              onClick={() => window.open(`/campaigns/preview/${c.preview_token}`, "_blank")}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "10px 18px",
                background: T.surfaceAlt, color: T.text,
                border: `1px solid ${T.border}`, borderRadius: 8,
                fontSize: 13, fontWeight: 500, cursor: "pointer",
              }}
            >
              <Eye size={14} /> Vorschau
            </button>
          )}
          <div style={{ flex: 1 }} />
          <button
            onClick={() => onDelete(c.id)}
            style={{
              display: "flex", alignItems: "center", gap: 6, padding: "10px 18px",
              background: T.dangerDim, color: T.danger, border: "none", borderRadius: 8,
              fontSize: 13, fontWeight: 500, cursor: "pointer",
            }}
          >
            <Trash2 size={14} /> Löschen
          </button>
        </div>
      </Card>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   SHARED STYLES
   ═══════════════════════════════════════════════════════════════════════════ */

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 11,
  fontWeight: 600,
  color: T.textMuted,
  marginBottom: 6,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};
