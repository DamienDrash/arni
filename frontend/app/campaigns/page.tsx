"use client";

import { useCallback, useEffect, useState, useMemo } from "react";
import {
  Megaphone, Plus, Send, Clock, CheckCircle, XCircle, Eye, Pencil,
  Trash2, Sparkles, Mail, MessageSquare, Phone, Filter, Users,
  BarChart3, Calendar, ChevronRight, AlertTriangle, Zap, Copy,
  FileText, Target, ArrowRight, RefreshCw, Search, MoreVertical,
  Globe, Smartphone, Bell, TrendingUp, Layers,
} from "lucide-react";
import { T } from "@/lib/tokens";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
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

interface Template {
  id: number;
  name: string;
  description: string | null;
  type: string;
  header_html: string | null;
  footer_html: string | null;
  body_template: string | null;
  primary_color: string | null;
  is_default: boolean;
}

interface Segment {
  id: number;
  name: string;
  description: string | null;
  filter_json: string | null;
  is_dynamic: boolean;
  member_count: number;
}

interface FollowUp {
  id: number;
  member_name: string;
  reason: string | null;
  follow_up_at: string;
  channel: string;
  status: string;
}

interface CampaignAnalytics {
  total_campaigns: number;
  sent_campaigns: number;
  total_recipients: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
  pending_follow_ups: number;
  recent_campaigns: Campaign[];
}

type TabId = "overview" | "create" | "templates" | "segments" | "follow-ups" | "analytics";

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
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [followUps, setFollowUps] = useState<FollowUp[]>([]);
  const [analytics, setAnalytics] = useState<CampaignAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Create Campaign State
  const [showCreateWizard, setShowCreateWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [newCampaign, setNewCampaign] = useState({
    name: "",
    description: "",
    type: "broadcast",
    channel: "email",
    target_type: "all_members",
    content_subject: "",
    content_body: "",
    ai_prompt: "",
    scheduled_at: "",
    template_id: null as number | null,
    is_ab_test: false,
  });
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);

  // Template Editor State
  const [showTemplateEditor, setShowTemplateEditor] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [templateForm, setTemplateForm] = useState({
    name: "",
    description: "",
    type: "email",
    header_html: "",
    footer_html: "",
    body_template: "",
    primary_color: "#6C5CE7",
  });

  // Segment Editor State
  const [showSegmentEditor, setShowSegmentEditor] = useState(false);
  const [segmentForm, setSegmentForm] = useState({
    name: "",
    description: "",
    filter_status: "active",
    is_dynamic: true,
  });

  // Follow-up Editor State
  const [showFollowUpEditor, setShowFollowUpEditor] = useState(false);
  const [followUpForm, setFollowUpForm] = useState({
    reason: "",
    follow_up_at: "",
    message_template: "",
    channel: "whatsapp",
  });

  // Detail View
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

  const loadTemplates = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns/templates");
      if (res.ok) setTemplates(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadSegments = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns/segments");
      if (res.ok) setSegments(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadFollowUps = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns/follow-ups");
      if (res.ok) setFollowUps(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadAnalytics = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/campaigns/analytics");
      if (res.ok) setAnalytics(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([loadCampaigns(), loadTemplates(), loadSegments(), loadFollowUps(), loadAnalytics()]);
      setLoading(false);
    };
    loadAll();
  }, [loadCampaigns, loadTemplates, loadSegments, loadFollowUps, loadAnalytics]);

  /* ─── Filtered Campaigns ───────────────────────────────────────────────── */

  const filteredCampaigns = useMemo(() => {
    return campaigns.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (searchTerm && !c.name.toLowerCase().includes(searchTerm.toLowerCase())) return false;
      return true;
    });
  }, [campaigns, statusFilter, searchTerm]);

  /* ─── Campaign Actions ─────────────────────────────────────────────────── */

  const createCampaign = async () => {
    try {
      const res = await apiFetch("/admin/campaigns", {
        method: "POST",
        body: JSON.stringify({
          ...newCampaign,
          template_id: newCampaign.template_id || undefined,
          scheduled_at: newCampaign.scheduled_at || undefined,
        }),
      });
      if (res.ok) {
        const created = await res.json();
        setShowCreateWizard(false);
        setWizardStep(0);
        setNewCampaign({
          name: "", description: "", type: "broadcast", channel: "email",
          target_type: "all_members", content_subject: "", content_body: "",
          ai_prompt: "", scheduled_at: "", template_id: null, is_ab_test: false,
        });
        await loadCampaigns();
        // If AI prompt was provided, generate content
        if (newCampaign.ai_prompt) {
          setAiGenerating(true);
          try {
            const aiRes = await apiFetch("/admin/campaigns/ai-generate", {
              method: "POST",
              body: JSON.stringify({
                campaign_id: created.id,
                prompt: newCampaign.ai_prompt,
                use_knowledge: true,
                use_chat_history: false,
                tone: "professional",
              }),
            });
            if (aiRes.ok) {
              setAiResult(await aiRes.json());
              await loadCampaigns();
            }
          } catch { /* ignore */ }
          setAiGenerating(false);
        }
      }
    } catch { /* ignore */ }
  };

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
      await loadAnalytics();
    } catch { /* ignore */ }
  };

  const deleteCampaign = async (id: number) => {
    try {
      await apiFetch(`/admin/campaigns/${id}`, { method: "DELETE" });
      await loadCampaigns();
    } catch { /* ignore */ }
  };

  const createTemplate = async () => {
    try {
      const res = await apiFetch("/admin/campaigns/templates", {
        method: "POST",
        body: JSON.stringify(templateForm),
      });
      if (res.ok) {
        setShowTemplateEditor(false);
        setTemplateForm({ name: "", description: "", type: "email", header_html: "", footer_html: "", body_template: "", primary_color: "#6C5CE7" });
        await loadTemplates();
      }
    } catch { /* ignore */ }
  };

  const createSegment = async () => {
    try {
      const res = await apiFetch("/admin/campaigns/segments", {
        method: "POST",
        body: JSON.stringify({
          name: segmentForm.name,
          description: segmentForm.description,
          filter_json: JSON.stringify({ status: segmentForm.filter_status }),
          is_dynamic: segmentForm.is_dynamic,
        }),
      });
      if (res.ok) {
        setShowSegmentEditor(false);
        setSegmentForm({ name: "", description: "", filter_status: "active", is_dynamic: true });
        await loadSegments();
      }
    } catch { /* ignore */ }
  };

  const createFollowUp = async () => {
    try {
      const res = await apiFetch("/admin/campaigns/follow-ups", {
        method: "POST",
        body: JSON.stringify(followUpForm),
      });
      if (res.ok) {
        setShowFollowUpEditor(false);
        setFollowUpForm({ reason: "", follow_up_at: "", message_template: "", channel: "whatsapp" });
        await loadFollowUps();
      }
    } catch { /* ignore */ }
  };

  /* ─── Tab Definitions ──────────────────────────────────────────────────── */

  const tabs: { id: TabId; label: string; icon: typeof Megaphone; count?: number }[] = [
    { id: "overview", label: "Kampagnen", icon: Megaphone, count: campaigns.length },
    { id: "create", label: "Erstellen", icon: Plus },
    { id: "templates", label: "Vorlagen", icon: FileText, count: templates.length },
    { id: "segments", label: "Segmente", icon: Target, count: segments.length },
    { id: "follow-ups", label: "Follow-ups", icon: Bell, count: followUps.filter(f => f.status === "pending").length },
    { id: "analytics", label: "Analytics", icon: BarChart3 },
  ];

  /* ═══════════════════════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════════════════════ */

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 40, height: 40, borderRadius: 12,
            background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <Megaphone size={20} color="#fff" />
          </div>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
              Kampagnen & Scheduling
            </h1>
            <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
              Erstellen, planen und versenden Sie personalisierte Nachrichten an Ihre Kontakte
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 4, marginBottom: 28, padding: 4,
        background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
        overflowX: "auto",
      }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "10px 16px",
                borderRadius: 8, border: "none", cursor: "pointer",
                background: isActive ? T.accentDim : "transparent",
                color: isActive ? T.accentLight : T.textMuted,
                fontSize: 13, fontWeight: isActive ? 600 : 500,
                transition: "all 0.2s ease", whiteSpace: "nowrap",
              }}
            >
              <Icon size={15} />
              {tab.label}
              {tab.count !== undefined && tab.count > 0 && (
                <span style={{
                  background: isActive ? T.accent : T.surfaceAlt,
                  color: isActive ? "#fff" : T.textMuted,
                  padding: "1px 7px", borderRadius: 10, fontSize: 11, fontWeight: 700,
                }}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", justifyContent: "center", padding: 60 }}>
          <RefreshCw size={24} color={T.accent} style={{ animation: "spin 1s linear infinite" }} />
        </div>
      )}

      {/* Tab Content */}
      {!loading && activeTab === "overview" && renderOverview()}
      {!loading && activeTab === "create" && renderCreateWizard()}
      {!loading && activeTab === "templates" && renderTemplates()}
      {!loading && activeTab === "segments" && renderSegments()}
      {!loading && activeTab === "follow-ups" && renderFollowUps()}
      {!loading && activeTab === "analytics" && renderAnalytics()}

      {/* Campaign Detail Modal */}
      {selectedCampaign && renderCampaignDetail()}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: OVERVIEW
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderOverview() {
    return (
      <div>
        {/* Quick Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Gesamt", value: campaigns.length, icon: Megaphone, color: T.accent },
            { label: "Geplant", value: campaigns.filter(c => c.status === "scheduled").length, icon: Clock, color: T.warning },
            { label: "Gesendet", value: campaigns.filter(c => c.status === "sent").length, icon: CheckCircle, color: T.success },
            { label: "Ausstehend", value: followUps.filter(f => f.status === "pending").length, icon: Bell, color: T.info },
          ].map((stat, i) => {
            const Icon = stat.icon;
            return (
              <Card key={i} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ fontSize: 11, color: T.textMuted, margin: "0 0 6px", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                      {stat.label}
                    </p>
                    <span style={{ fontSize: 28, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>
                      {stat.value}
                    </span>
                  </div>
                  <div style={{
                    width: 40, height: 40, borderRadius: 10,
                    background: `${stat.color}15`, display: "flex",
                    alignItems: "center", justifyContent: "center",
                  }}>
                    <Icon size={18} color={stat.color} />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        {/* Filter Bar */}
        <Card style={{ padding: 16, marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
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
              <option value="scheduled">Geplant</option>
              <option value="sent">Gesendet</option>
            </select>
            <button
              onClick={() => setActiveTab("create")}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Plus size={14} /> Neue Kampagne
            </button>
          </div>
        </Card>

        {/* Campaign List */}
        {filteredCampaigns.length === 0 ? (
          <Card style={{ padding: 60, textAlign: "center" }}>
            <Megaphone size={40} color={T.textDim} style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, fontWeight: 600, color: T.text, margin: "0 0 8px" }}>
              Noch keine Kampagnen erstellt
            </p>
            <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 20px" }}>
              Erstellen Sie Ihre erste Kampagne, um personalisierte Nachrichten an Ihre Kontakte zu senden.
            </p>
            <button
              onClick={() => setActiveTab("create")}
              style={{
                display: "inline-flex", alignItems: "center", gap: 6, padding: "10px 20px",
                background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Plus size={14} /> Erste Kampagne erstellen
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
                  style={{ padding: 20, cursor: "pointer", transition: "all 0.2s ease" }}
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
                        <span style={{ fontSize: 14, fontWeight: 600, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {campaign.name}
                        </span>
                        <Badge variant={statusInfo.variant} size="xs">{statusInfo.label}</Badge>
                        {campaign.is_ab_test && <Badge variant="accent" size="xs">A/B Test</Badge>}
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: T.textMuted }}>
                        <span>{channelInfo.label}</span>
                        <span>·</span>
                        <span>{TARGET_MAP[campaign.target_type] || campaign.target_type}</span>
                        {campaign.scheduled_at && (
                          <>
                            <span>·</span>
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Clock size={11} />
                              {new Date(campaign.scheduled_at).toLocaleDateString("de-DE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                            </span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Stats */}
                    {campaign.status === "sent" && (
                      <div style={{ display: "flex", gap: 20, marginRight: 16 }}>
                        {[
                          { label: "Gesendet", value: campaign.stats_sent },
                          { label: "Zugestellt", value: campaign.stats_delivered },
                          { label: "Geöffnet", value: campaign.stats_opened },
                          { label: "Geklickt", value: campaign.stats_clicked },
                        ].map((s, i) => (
                          <div key={i} style={{ textAlign: "center" }}>
                            <p style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: 0 }}>{s.value}</p>
                            <p style={{ fontSize: 10, color: T.textMuted, margin: 0 }}>{s.label}</p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Actions */}
                    <div style={{ display: "flex", gap: 4 }}>
                      {campaign.status === "pending_review" && (
                        <button
                          onClick={(e) => { e.stopPropagation(); approveCampaign(campaign.id); }}
                          style={{
                            padding: "6px 12px", background: T.successDim, color: T.success,
                            border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
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
                            border: "none", borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: "pointer",
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
                            border: `1px solid ${T.border}`, borderRadius: 6, fontSize: 12, cursor: "pointer",
                          }}
                        >
                          <Eye size={12} />
                        </button>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteCampaign(campaign.id); }}
                        style={{
                          padding: "6px 10px", background: T.dangerDim, color: T.danger,
                          border: "none", borderRadius: 6, fontSize: 12, cursor: "pointer",
                        }}
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>

                    <ChevronRight size={16} color={T.textDim} />
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: CREATE WIZARD
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderCreateWizard() {
    const steps = [
      { title: "Grundlagen", desc: "Name, Typ und Kanal" },
      { title: "Zielgruppe", desc: "Empfänger auswählen" },
      { title: "Inhalt", desc: "Nachricht erstellen oder KI generieren" },
      { title: "Planung", desc: "Zeitpunkt und Optionen" },
    ];

    return (
      <div>
        {/* Progress Steps */}
        <Card style={{ padding: 24, marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            {steps.map((step, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: "50%",
                  background: i <= wizardStep ? T.accent : T.surfaceAlt,
                  color: i <= wizardStep ? "#fff" : T.textMuted,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 14, fontWeight: 700, flexShrink: 0,
                  border: i === wizardStep ? `2px solid ${T.accentLight}` : "none",
                }}>
                  {i < wizardStep ? <CheckCircle size={16} /> : i + 1}
                </div>
                <div>
                  <p style={{ fontSize: 13, fontWeight: 600, color: i <= wizardStep ? T.text : T.textMuted, margin: 0 }}>
                    {step.title}
                  </p>
                  <p style={{ fontSize: 11, color: T.textDim, margin: 0 }}>{step.desc}</p>
                </div>
                {i < steps.length - 1 && (
                  <div style={{ flex: 1, height: 2, background: i < wizardStep ? T.accent : T.border, margin: "0 12px", borderRadius: 1 }} />
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Step Content */}
        <Card style={{ padding: 32 }}>
          {wizardStep === 0 && (
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                Kampagnen-Grundlagen
              </h3>
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <label style={labelStyle}>Kampagnenname *</label>
                  <input
                    type="text"
                    value={newCampaign.name}
                    onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })}
                    placeholder="z.B. Frühlings-Aktion 2026"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Beschreibung</label>
                  <textarea
                    value={newCampaign.description}
                    onChange={(e) => setNewCampaign({ ...newCampaign, description: e.target.value })}
                    placeholder="Kurze Beschreibung der Kampagne..."
                    rows={3}
                    style={{ ...inputStyle, resize: "vertical" }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Kanal</label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8 }}>
                    {Object.entries(CHANNEL_MAP).map(([key, ch]) => {
                      const Icon = ch.icon;
                      const isSelected = newCampaign.channel === key;
                      return (
                        <button
                          key={key}
                          onClick={() => setNewCampaign({ ...newCampaign, channel: key })}
                          style={{
                            display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                            padding: 16, borderRadius: 12, cursor: "pointer",
                            background: isSelected ? `${ch.color}15` : T.surfaceAlt,
                            border: isSelected ? `2px solid ${ch.color}` : `1px solid ${T.border}`,
                            color: isSelected ? ch.color : T.textMuted,
                            transition: "all 0.2s ease",
                          }}
                        >
                          <Icon size={20} />
                          <span style={{ fontSize: 12, fontWeight: 600 }}>{ch.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div>
                  <label style={labelStyle}>Kampagnentyp</label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
                    {[
                      { key: "broadcast", label: "Broadcast", desc: "Einmalige Nachricht an alle", icon: Megaphone },
                      { key: "scheduled", label: "Geplant", desc: "Zu einem bestimmten Zeitpunkt", icon: Calendar },
                    ].map((t) => {
                      const Icon = t.icon;
                      const isSelected = newCampaign.type === t.key;
                      return (
                        <button
                          key={t.key}
                          onClick={() => setNewCampaign({ ...newCampaign, type: t.key })}
                          style={{
                            display: "flex", alignItems: "center", gap: 12, padding: 16,
                            borderRadius: 12, cursor: "pointer", textAlign: "left",
                            background: isSelected ? T.accentDim : T.surfaceAlt,
                            border: isSelected ? `2px solid ${T.accent}` : `1px solid ${T.border}`,
                            color: T.text, transition: "all 0.2s ease",
                          }}
                        >
                          <Icon size={20} color={isSelected ? T.accent : T.textMuted} />
                          <div>
                            <p style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>{t.label}</p>
                            <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>{t.desc}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )}

          {wizardStep === 1 && (
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                Zielgruppe auswählen
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
                {[
                  { key: "all_members", label: "Alle Kontakte", desc: "Nachricht an alle aktiven Kontakte senden", icon: Users },
                  { key: "segment", label: "Segment", desc: "Vordefiniertes Segment verwenden", icon: Target },
                  { key: "tags", label: "Nach Tags", desc: "Kontakte nach Tags filtern", icon: Filter },
                  { key: "selected", label: "Manuell auswählen", desc: "Einzelne Kontakte auswählen", icon: CheckCircle },
                ].map((t) => {
                  const Icon = t.icon;
                  const isSelected = newCampaign.target_type === t.key;
                  return (
                    <button
                      key={t.key}
                      onClick={() => setNewCampaign({ ...newCampaign, target_type: t.key })}
                      style={{
                        display: "flex", alignItems: "center", gap: 12, padding: 20,
                        borderRadius: 12, cursor: "pointer", textAlign: "left",
                        background: isSelected ? T.accentDim : T.surfaceAlt,
                        border: isSelected ? `2px solid ${T.accent}` : `1px solid ${T.border}`,
                        color: T.text, transition: "all 0.2s ease",
                      }}
                    >
                      <div style={{
                        width: 40, height: 40, borderRadius: 10,
                        background: isSelected ? `${T.accent}25` : T.bg,
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <Icon size={18} color={isSelected ? T.accent : T.textMuted} />
                      </div>
                      <div>
                        <p style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>{t.label}</p>
                        <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{t.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>

              {newCampaign.target_type === "segment" && segments.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <label style={labelStyle}>Segment auswählen</label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {segments.map((seg) => (
                      <button
                        key={seg.id}
                        onClick={() => setNewCampaign({ ...newCampaign, target_type: "segment" })}
                        style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between",
                          padding: 14, borderRadius: 8, cursor: "pointer",
                          background: T.surfaceAlt, border: `1px solid ${T.border}`,
                          color: T.text, textAlign: "left",
                        }}
                      >
                        <div>
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{seg.name}</span>
                          {seg.description && <span style={{ fontSize: 12, color: T.textMuted, marginLeft: 8 }}>{seg.description}</span>}
                        </div>
                        <Badge variant="accent">{seg.member_count} Kontakte</Badge>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {wizardStep === 2 && (
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>
                Inhalt erstellen
              </h3>
              <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 24px" }}>
                Erstellen Sie den Inhalt manuell oder lassen Sie unsere KI einen Vorschlag generieren.
              </p>

              {/* AI Generation Section */}
              <Card style={{ padding: 20, marginBottom: 24, background: `linear-gradient(135deg, ${T.accentDim}, ${T.surface})`, border: `1px solid ${T.accent}40` }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                  <Sparkles size={18} color={T.accent} />
                  <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>KI-Assistent</span>
                  <Badge variant="accent" size="xs">Empfohlen</Badge>
                </div>
                <textarea
                  value={newCampaign.ai_prompt}
                  onChange={(e) => setNewCampaign({ ...newCampaign, ai_prompt: e.target.value })}
                  placeholder="Beschreiben Sie, was die Nachricht beinhalten soll, z.B.: 'Motivierende Nachricht für Kontakte die seit 2 Wochen nicht mehr aktiv waren. Erwähne unser neues Kursangebot und biete einen 10% Rabatt an.'"
                  rows={4}
                  style={{ ...inputStyle, resize: "vertical", marginBottom: 12 }}
                />
                <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                  Die KI nutzt Ihren Wissensspeicher und die Chat-Historie, um personalisierte Inhalte zu erstellen.
                </p>
              </Card>

              {/* Manual Content */}
              <div style={{ display: "grid", gap: 16 }}>
                {newCampaign.channel === "email" && (
                  <div>
                    <label style={labelStyle}>Betreff</label>
                    <input
                      type="text"
                      value={newCampaign.content_subject}
                      onChange={(e) => setNewCampaign({ ...newCampaign, content_subject: e.target.value })}
                      placeholder="E-Mail Betreff..."
                      style={inputStyle}
                    />
                  </div>
                )}
                <div>
                  <label style={labelStyle}>Nachricht</label>
                  <textarea
                    value={newCampaign.content_body}
                    onChange={(e) => setNewCampaign({ ...newCampaign, content_body: e.target.value })}
                    placeholder="Ihre Nachricht hier... Verwenden Sie {{first_name}} für Personalisierung."
                    rows={8}
                    style={{ ...inputStyle, resize: "vertical", fontFamily: "monospace", fontSize: 13 }}
                  />
                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    {["{{first_name}}", "{{studio_name}}", "{{plan_name}}"].map((v) => (
                      <button
                        key={v}
                        onClick={() => setNewCampaign({ ...newCampaign, content_body: newCampaign.content_body + v })}
                        style={{
                          padding: "4px 8px", background: T.surfaceAlt, border: `1px solid ${T.border}`,
                          borderRadius: 4, fontSize: 11, color: T.accentLight, cursor: "pointer", fontFamily: "monospace",
                        }}
                      >
                        {v}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Template Selection */}
                {templates.length > 0 && newCampaign.channel === "email" && (
                  <div>
                    <label style={labelStyle}>Vorlage (optional)</label>
                    <select
                      value={newCampaign.template_id || ""}
                      onChange={(e) => setNewCampaign({ ...newCampaign, template_id: e.target.value ? Number(e.target.value) : null })}
                      style={{ ...inputStyle, cursor: "pointer" }}
                    >
                      <option value="">Keine Vorlage</option>
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>{t.name}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
          )}

          {wizardStep === 3 && (
            <div>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                Planung & Optionen
              </h3>
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <label style={labelStyle}>Versandzeitpunkt</label>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <button
                      onClick={() => setNewCampaign({ ...newCampaign, scheduled_at: "" })}
                      style={{
                        display: "flex", alignItems: "center", gap: 10, padding: 16,
                        borderRadius: 12, cursor: "pointer", textAlign: "left",
                        background: !newCampaign.scheduled_at ? T.accentDim : T.surfaceAlt,
                        border: !newCampaign.scheduled_at ? `2px solid ${T.accent}` : `1px solid ${T.border}`,
                        color: T.text,
                      }}
                    >
                      <Send size={18} color={!newCampaign.scheduled_at ? T.accent : T.textMuted} />
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>Sofort senden</p>
                        <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>Nach Freigabe direkt versenden</p>
                      </div>
                    </button>
                    <button
                      onClick={() => setNewCampaign({ ...newCampaign, scheduled_at: new Date(Date.now() + 86400000).toISOString().slice(0, 16) })}
                      style={{
                        display: "flex", alignItems: "center", gap: 10, padding: 16,
                        borderRadius: 12, cursor: "pointer", textAlign: "left",
                        background: newCampaign.scheduled_at ? T.accentDim : T.surfaceAlt,
                        border: newCampaign.scheduled_at ? `2px solid ${T.accent}` : `1px solid ${T.border}`,
                        color: T.text,
                      }}
                    >
                      <Calendar size={18} color={newCampaign.scheduled_at ? T.accent : T.textMuted} />
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 600, margin: 0 }}>Planen</p>
                        <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>Zeitpunkt festlegen</p>
                      </div>
                    </button>
                  </div>
                  {newCampaign.scheduled_at && (
                    <input
                      type="datetime-local"
                      value={newCampaign.scheduled_at}
                      onChange={(e) => setNewCampaign({ ...newCampaign, scheduled_at: e.target.value })}
                      style={{ ...inputStyle, marginTop: 12 }}
                    />
                  )}
                </div>

                {/* Summary */}
                <Card style={{ padding: 20, background: T.surfaceAlt }}>
                  <h4 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 16px" }}>Zusammenfassung</h4>
                  <div style={{ display: "grid", gap: 8 }}>
                    {[
                      { label: "Kampagne", value: newCampaign.name || "—" },
                      { label: "Kanal", value: CHANNEL_MAP[newCampaign.channel]?.label || newCampaign.channel },
                      { label: "Zielgruppe", value: TARGET_MAP[newCampaign.target_type] || newCampaign.target_type },
                      { label: "Versand", value: newCampaign.scheduled_at ? new Date(newCampaign.scheduled_at).toLocaleString("de-DE") : "Sofort nach Freigabe" },
                      { label: "KI-Inhalt", value: newCampaign.ai_prompt ? "Ja" : "Manuell" },
                    ].map((item, i) => (
                      <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${T.border}` }}>
                        <span style={{ fontSize: 12, color: T.textMuted }}>{item.label}</span>
                        <span style={{ fontSize: 12, color: T.text, fontWeight: 500 }}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            </div>
          )}

          {/* Navigation Buttons */}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 32, paddingTop: 20, borderTop: `1px solid ${T.border}` }}>
            <button
              onClick={() => wizardStep > 0 ? setWizardStep(wizardStep - 1) : setActiveTab("overview")}
              style={{
                padding: "10px 20px", background: T.surfaceAlt, color: T.textMuted,
                border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer",
              }}
            >
              {wizardStep > 0 ? "Zurück" : "Abbrechen"}
            </button>
            {wizardStep < steps.length - 1 ? (
              <button
                onClick={() => setWizardStep(wizardStep + 1)}
                disabled={wizardStep === 0 && !newCampaign.name}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "10px 20px",
                  background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                  opacity: wizardStep === 0 && !newCampaign.name ? 0.5 : 1,
                }}
              >
                Weiter <ArrowRight size={14} />
              </button>
            ) : (
              <button
                onClick={createCampaign}
                disabled={!newCampaign.name}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "10px 24px",
                  background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`,
                  color: "#fff", border: "none", borderRadius: 8,
                  fontSize: 13, fontWeight: 700, cursor: "pointer",
                  opacity: !newCampaign.name ? 0.5 : 1,
                }}
              >
                <Sparkles size={14} /> Kampagne erstellen
              </button>
            )}
          </div>
        </Card>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: TEMPLATES
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderTemplates() {
    return (
      <div>
        <SectionHeader
          title="Nachrichtenvorlagen"
          subtitle="Erstellen und verwalten Sie wiederverwendbare Vorlagen für Ihre Kampagnen"
          action={
            <button
              onClick={() => { setShowTemplateEditor(true); setEditingTemplate(null); }}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Plus size={14} /> Neue Vorlage
            </button>
          }
        />

        {templates.length === 0 ? (
          <Card style={{ padding: 60, textAlign: "center" }}>
            <FileText size={40} color={T.textDim} style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, fontWeight: 600, color: T.text, margin: "0 0 8px" }}>
              Keine Vorlagen vorhanden
            </p>
            <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 20px" }}>
              Erstellen Sie Vorlagen mit Header, Footer und Platzhaltern für konsistente Kampagnen.
            </p>
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {templates.map((tpl) => (
              <Card key={tpl.id} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: "50%",
                    background: tpl.primary_color || T.accent,
                  }} />
                  <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{tpl.name}</span>
                  <Badge variant="default" size="xs">{tpl.type.toUpperCase()}</Badge>
                </div>
                {tpl.description && (
                  <p style={{ fontSize: 12, color: T.textMuted, margin: "0 0 16px", lineHeight: 1.5 }}>
                    {tpl.description}
                  </p>
                )}
                {/* Template Preview */}
                <div style={{
                  background: T.bg, borderRadius: 8, padding: 12, marginBottom: 12,
                  border: `1px solid ${T.border}`, maxHeight: 120, overflow: "hidden",
                }}>
                  {tpl.header_html && (
                    <div style={{ fontSize: 10, color: T.textDim, borderBottom: `1px solid ${T.border}`, paddingBottom: 4, marginBottom: 4 }}>
                      Header
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: T.textMuted, lineHeight: 1.4 }}>
                    {tpl.body_template ? tpl.body_template.slice(0, 100) + "..." : "Kein Inhalt"}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {tpl.is_default && <Badge variant="accent" size="xs">Standard</Badge>}
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Template Editor Modal */}
        {showTemplateEditor && (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}>
            <Card style={{ width: 640, maxHeight: "85vh", overflow: "auto", padding: 32 }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                {editingTemplate ? "Vorlage bearbeiten" : "Neue Vorlage erstellen"}
              </h3>
              <div style={{ display: "grid", gap: 16 }}>
                <div>
                  <label style={labelStyle}>Name *</label>
                  <input
                    type="text"
                    value={templateForm.name}
                    onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                    placeholder="z.B. Standard E-Mail"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Beschreibung</label>
                  <input
                    type="text"
                    value={templateForm.description}
                    onChange={(e) => setTemplateForm({ ...templateForm, description: e.target.value })}
                    placeholder="Kurze Beschreibung..."
                    style={inputStyle}
                  />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                  <div>
                    <label style={labelStyle}>Typ</label>
                    <select
                      value={templateForm.type}
                      onChange={(e) => setTemplateForm({ ...templateForm, type: e.target.value })}
                      style={{ ...inputStyle, cursor: "pointer" }}
                    >
                      <option value="email">E-Mail</option>
                      <option value="whatsapp">WhatsApp</option>
                      <option value="sms">SMS</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Primärfarbe</label>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input
                        type="color"
                        value={templateForm.primary_color}
                        onChange={(e) => setTemplateForm({ ...templateForm, primary_color: e.target.value })}
                        style={{ width: 40, height: 36, border: "none", borderRadius: 6, cursor: "pointer" }}
                      />
                      <input
                        type="text"
                        value={templateForm.primary_color}
                        onChange={(e) => setTemplateForm({ ...templateForm, primary_color: e.target.value })}
                        style={{ ...inputStyle, flex: 1 }}
                      />
                    </div>
                  </div>
                </div>
                {templateForm.type === "email" && (
                  <>
                    <div>
                      <label style={labelStyle}>Header HTML</label>
                      <textarea
                        value={templateForm.header_html}
                        onChange={(e) => setTemplateForm({ ...templateForm, header_html: e.target.value })}
                        placeholder="<div style='background: #6C5CE7; padding: 20px; text-align: center;'><h1 style='color: white;'>Ihr Studio</h1></div>"
                        rows={3}
                        style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Body-Vorlage</label>
                      <textarea
                        value={templateForm.body_template}
                        onChange={(e) => setTemplateForm({ ...templateForm, body_template: e.target.value })}
                        placeholder="Hallo {{first_name}},&#10;&#10;{{content}}&#10;&#10;Viele Grüße,&#10;{{studio_name}}"
                        rows={6}
                        style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
                      />
                    </div>
                    <div>
                      <label style={labelStyle}>Footer HTML</label>
                      <textarea
                        value={templateForm.footer_html}
                        onChange={(e) => setTemplateForm({ ...templateForm, footer_html: e.target.value })}
                        placeholder="<div style='text-align: center; padding: 20px; color: #888;'><small>© 2026 Ihr Studio</small></div>"
                        rows={3}
                        style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
                      />
                    </div>
                  </>
                )}
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button
                  onClick={() => setShowTemplateEditor(false)}
                  style={{
                    padding: "10px 20px", background: T.surfaceAlt, color: T.textMuted,
                    border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, cursor: "pointer",
                  }}
                >
                  Abbrechen
                </button>
                <button
                  onClick={createTemplate}
                  disabled={!templateForm.name}
                  style={{
                    padding: "10px 20px", background: T.accent, color: "#fff",
                    border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer",
                    opacity: !templateForm.name ? 0.5 : 1,
                  }}
                >
                  Speichern
                </button>
              </div>
            </Card>
          </div>
        )}
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: SEGMENTS
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderSegments() {
    return (
      <div>
        <SectionHeader
          title="Kontakt-Segmente"
          subtitle="Erstellen Sie Zielgruppen für gezielte Kampagnen"
          action={
            <button
              onClick={() => setShowSegmentEditor(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Plus size={14} /> Neues Segment
            </button>
          }
        />

        {segments.length === 0 ? (
          <Card style={{ padding: 60, textAlign: "center" }}>
            <Target size={40} color={T.textDim} style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, fontWeight: 600, color: T.text, margin: "0 0 8px" }}>
              Keine Segmente vorhanden
            </p>
            <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 20px" }}>
              Erstellen Sie Segmente, um Ihre Kontakte gezielt anzusprechen.
            </p>
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
            {segments.map((seg) => (
              <Card key={seg.id} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Target size={16} color={T.accent} />
                    <span style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{seg.name}</span>
                  </div>
                  {seg.is_dynamic && <Badge variant="info" size="xs">Dynamisch</Badge>}
                </div>
                {seg.description && (
                  <p style={{ fontSize: 12, color: T.textMuted, margin: "0 0 16px" }}>{seg.description}</p>
                )}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Users size={14} color={T.textMuted} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{seg.member_count}</span>
                    <span style={{ fontSize: 12, color: T.textMuted }}>Kontakte</span>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Segment Editor Modal */}
        {showSegmentEditor && (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}>
            <Card style={{ width: 520, padding: 32 }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                Neues Segment erstellen
              </h3>
              <div style={{ display: "grid", gap: 16 }}>
                <div>
                  <label style={labelStyle}>Name *</label>
                  <input
                    type="text"
                    value={segmentForm.name}
                    onChange={(e) => setSegmentForm({ ...segmentForm, name: e.target.value })}
                    placeholder="z.B. Aktive Kontakte"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Beschreibung</label>
                  <input
                    type="text"
                    value={segmentForm.description}
                    onChange={(e) => setSegmentForm({ ...segmentForm, description: e.target.value })}
                    placeholder="Kurze Beschreibung..."
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Status-Filter</label>
                  <select
                    value={segmentForm.filter_status}
                    onChange={(e) => setSegmentForm({ ...segmentForm, filter_status: e.target.value })}
                    style={{ ...inputStyle, cursor: "pointer" }}
                  >
                    <option value="active">Aktiv</option>
                    <option value="inactive">Inaktiv</option>
                    <option value="paused">Pausiert</option>
                    <option value="cancelled">Gekündigt</option>
                  </select>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={segmentForm.is_dynamic}
                    onChange={(e) => setSegmentForm({ ...segmentForm, is_dynamic: e.target.checked })}
                    style={{ accentColor: T.accent }}
                  />
                  <label style={{ fontSize: 13, color: T.text }}>
                    Dynamisches Segment (wird bei jeder Kampagne neu evaluiert)
                  </label>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button
                  onClick={() => setShowSegmentEditor(false)}
                  style={{
                    padding: "10px 20px", background: T.surfaceAlt, color: T.textMuted,
                    border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, cursor: "pointer",
                  }}
                >
                  Abbrechen
                </button>
                <button
                  onClick={createSegment}
                  disabled={!segmentForm.name}
                  style={{
                    padding: "10px 20px", background: T.accent, color: "#fff",
                    border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer",
                    opacity: !segmentForm.name ? 0.5 : 1,
                  }}
                >
                  Erstellen
                </button>
              </div>
            </Card>
          </div>
        )}
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: FOLLOW-UPS
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderFollowUps() {
    const pendingFollowUps = followUps.filter(f => f.status === "pending");
    const completedFollowUps = followUps.filter(f => f.status !== "pending");

    return (
      <div>
        <SectionHeader
          title="Geplante Follow-ups"
          subtitle="Automatische Nachfass-Nachrichten basierend auf Chat-Konversationen"
          action={
            <button
              onClick={() => setShowFollowUpEditor(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                background: T.accent, color: "#fff", border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 600, cursor: "pointer",
              }}
            >
              <Plus size={14} /> Neues Follow-up
            </button>
          }
        />

        {/* Pending Follow-ups */}
        {pendingFollowUps.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: T.textMuted, margin: "0 0 12px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Ausstehend ({pendingFollowUps.length})
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {pendingFollowUps.map((fu) => {
                const channelInfo = CHANNEL_MAP[fu.channel] || CHANNEL_MAP.whatsapp;
                const ChannelIcon = channelInfo.icon;
                return (
                  <Card key={fu.id} style={{ padding: 16 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: 10,
                        background: `${channelInfo.color}15`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        <ChannelIcon size={16} color={channelInfo.color} />
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                          <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{fu.member_name}</span>
                          <Badge variant="warning" size="xs">Ausstehend</Badge>
                        </div>
                        {fu.reason && <p style={{ fontSize: 12, color: T.textMuted, margin: 0 }}>{fu.reason}</p>}
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <p style={{ fontSize: 12, fontWeight: 600, color: T.text, margin: 0 }}>
                          {new Date(fu.follow_up_at).toLocaleDateString("de-DE", { day: "2-digit", month: "short" })}
                        </p>
                        <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>
                          {new Date(fu.follow_up_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                        </p>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {/* Completed Follow-ups */}
        {completedFollowUps.length > 0 && (
          <div>
            <h4 style={{ fontSize: 13, fontWeight: 600, color: T.textMuted, margin: "0 0 12px", textTransform: "uppercase", letterSpacing: "0.06em" }}>
              Abgeschlossen ({completedFollowUps.length})
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {completedFollowUps.map((fu) => (
                <Card key={fu.id} style={{ padding: 16, opacity: 0.6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <CheckCircle size={16} color={T.success} />
                    <span style={{ fontSize: 13, color: T.text }}>{fu.member_name}</span>
                    <Badge variant={fu.status === "sent" ? "success" : "danger"} size="xs">{fu.status}</Badge>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {followUps.length === 0 && (
          <Card style={{ padding: 60, textAlign: "center" }}>
            <Bell size={40} color={T.textDim} style={{ marginBottom: 16 }} />
            <p style={{ fontSize: 16, fontWeight: 600, color: T.text, margin: "0 0 8px" }}>
              Keine Follow-ups geplant
            </p>
            <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 20px" }}>
              Follow-ups werden automatisch erstellt, wenn ein KI-Agent eine Nachfass-Aktion plant, oder Sie können sie manuell erstellen.
            </p>
          </Card>
        )}

        {/* Follow-up Editor Modal */}
        {showFollowUpEditor && (
          <div style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
            display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
          }}>
            <Card style={{ width: 520, padding: 32 }}>
              <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: "0 0 24px" }}>
                Neues Follow-up planen
              </h3>
              <div style={{ display: "grid", gap: 16 }}>
                <div>
                  <label style={labelStyle}>Grund / Anlass</label>
                  <input
                    type="text"
                    value={followUpForm.reason}
                    onChange={(e) => setFollowUpForm({ ...followUpForm, reason: e.target.value })}
                    placeholder="z.B. Pause - Rückkehr nach 2 Wochen"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Follow-up Zeitpunkt *</label>
                  <input
                    type="datetime-local"
                    value={followUpForm.follow_up_at}
                    onChange={(e) => setFollowUpForm({ ...followUpForm, follow_up_at: e.target.value })}
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Nachricht</label>
                  <textarea
                    value={followUpForm.message_template}
                    onChange={(e) => setFollowUpForm({ ...followUpForm, message_template: e.target.value })}
                    placeholder="Hallo {{first_name}}, wir hoffen es geht dir gut..."
                    rows={4}
                    style={{ ...inputStyle, resize: "vertical" }}
                  />
                </div>
                <div>
                  <label style={labelStyle}>Kanal</label>
                  <select
                    value={followUpForm.channel}
                    onChange={(e) => setFollowUpForm({ ...followUpForm, channel: e.target.value })}
                    style={{ ...inputStyle, cursor: "pointer" }}
                  >
                    <option value="whatsapp">WhatsApp</option>
                    <option value="email">E-Mail</option>
                    <option value="telegram">Telegram</option>
                    <option value="sms">SMS</option>
                  </select>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
                <button
                  onClick={() => setShowFollowUpEditor(false)}
                  style={{
                    padding: "10px 20px", background: T.surfaceAlt, color: T.textMuted,
                    border: `1px solid ${T.border}`, borderRadius: 8, fontSize: 13, cursor: "pointer",
                  }}
                >
                  Abbrechen
                </button>
                <button
                  onClick={createFollowUp}
                  disabled={!followUpForm.follow_up_at}
                  style={{
                    padding: "10px 20px", background: T.accent, color: "#fff",
                    border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer",
                    opacity: !followUpForm.follow_up_at ? 0.5 : 1,
                  }}
                >
                  Planen
                </button>
              </div>
            </Card>
          </div>
        )}
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB: ANALYTICS
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderAnalytics() {
    if (!analytics) return null;

    return (
      <div>
        <SectionHeader
          title="Kampagnen-Analytics"
          subtitle="Übersicht über die Performance Ihrer Kampagnen"
        />

        {/* KPI Cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Kampagnen gesendet", value: analytics.sent_campaigns, icon: Send, color: T.accent },
            { label: "Zustellrate", value: `${analytics.delivery_rate}%`, icon: CheckCircle, color: T.success },
            { label: "Öffnungsrate", value: `${analytics.open_rate}%`, icon: Eye, color: T.info },
            { label: "Klickrate", value: `${analytics.click_rate}%`, icon: TrendingUp, color: T.warning },
          ].map((kpi, i) => {
            const Icon = kpi.icon;
            return (
              <Card key={i} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: 0, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                    {kpi.label}
                  </p>
                  <Icon size={16} color={kpi.color} />
                </div>
                <span style={{ fontSize: 28, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>
                  {kpi.value}
                </span>
              </Card>
            );
          })}
        </div>

        {/* Additional Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
          <Card style={{ padding: 24 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 16px" }}>Empfänger-Übersicht</h4>
            <div style={{ display: "grid", gap: 12 }}>
              {[
                { label: "Gesamte Empfänger", value: analytics.total_recipients, color: T.text },
                { label: "Bounce-Rate", value: `${analytics.bounce_rate}%`, color: analytics.bounce_rate > 5 ? T.danger : T.success },
                { label: "Ausstehende Follow-ups", value: analytics.pending_follow_ups, color: T.warning },
              ].map((item, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: `1px solid ${T.border}` }}>
                  <span style={{ fontSize: 13, color: T.textMuted }}>{item.label}</span>
                  <span style={{ fontSize: 15, fontWeight: 700, color: item.color }}>{item.value}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card style={{ padding: 24 }}>
            <h4 style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: "0 0 16px" }}>Letzte Kampagnen</h4>
            {analytics.recent_campaigns.length === 0 ? (
              <p style={{ fontSize: 13, color: T.textMuted }}>Noch keine Kampagnen gesendet.</p>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {analytics.recent_campaigns.slice(0, 5).map((c) => {
                  const channelInfo = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;
                  return (
                    <div key={c.id} style={{
                      display: "flex", alignItems: "center", gap: 10, padding: "8px 0",
                      borderBottom: `1px solid ${T.border}`,
                    }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 6,
                        background: `${channelInfo.color}15`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        {(() => { const Icon = channelInfo.icon; return <Icon size={12} color={channelInfo.color} />; })()}
                      </div>
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{c.name}</span>
                      </div>
                      <span style={{ fontSize: 11, color: T.textMuted }}>{c.stats_sent} gesendet</span>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    );
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     CAMPAIGN DETAIL MODAL
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderCampaignDetail() {
    if (!selectedCampaign) return null;
    const c = selectedCampaign;
    const statusInfo = STATUS_MAP[c.status] || STATUS_MAP.draft;
    const channelInfo = CHANNEL_MAP[c.channel] || CHANNEL_MAP.email;

    return (
      <div style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}>
        <Card style={{ width: 700, maxHeight: "85vh", overflow: "auto", padding: 32 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12,
                background: `${channelInfo.color}15`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {(() => { const Icon = channelInfo.icon; return <Icon size={20} color={channelInfo.color} />; })()}
              </div>
              <div>
                <h3 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>{c.name}</h3>
                <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                  <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                  <Badge variant="default">{channelInfo.label}</Badge>
                </div>
              </div>
            </div>
            <button
              onClick={() => setSelectedCampaign(null)}
              style={{
                padding: "6px 12px", background: T.surfaceAlt, color: T.textMuted,
                border: `1px solid ${T.border}`, borderRadius: 6, fontSize: 12, cursor: "pointer",
              }}
            >
              Schließen
            </button>
          </div>

          {/* Content Preview */}
          {c.content_subject && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ ...labelStyle, marginBottom: 4 }}>Betreff</label>
              <p style={{ fontSize: 14, fontWeight: 600, color: T.text, margin: 0 }}>{c.content_subject}</p>
            </div>
          )}
          {c.content_body && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ ...labelStyle, marginBottom: 4 }}>Inhalt</label>
              <div style={{
                background: T.surfaceAlt, borderRadius: 8, padding: 16,
                border: `1px solid ${T.border}`, fontSize: 13, color: T.text, lineHeight: 1.6,
                whiteSpace: "pre-wrap",
              }}>
                {c.content_body}
              </div>
            </div>
          )}

          {/* Stats */}
          {c.status === "sent" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
              {[
                { label: "Gesendet", value: c.stats_sent, color: T.text },
                { label: "Zugestellt", value: c.stats_delivered, color: T.success },
                { label: "Geöffnet", value: c.stats_opened, color: T.info },
                { label: "Geklickt", value: c.stats_clicked, color: T.warning },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: "center", padding: 12, background: T.surfaceAlt, borderRadius: 8 }}>
                  <p style={{ fontSize: 20, fontWeight: 700, color: s.color, margin: 0 }}>{s.value}</p>
                  <p style={{ fontSize: 11, color: T.textMuted, margin: 0 }}>{s.label}</p>
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", gap: 8, paddingTop: 16, borderTop: `1px solid ${T.border}` }}>
            {c.status === "pending_review" && (
              <button
                onClick={() => { approveCampaign(c.id); setSelectedCampaign(null); }}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                  background: T.success, color: "#fff", border: "none", borderRadius: 8,
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                }}
              >
                <CheckCircle size={14} /> Freigeben
              </button>
            )}
            {(c.status === "approved" || c.status === "draft") && (
              <button
                onClick={() => { sendCampaign(c.id); setSelectedCampaign(null); }}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                  background: T.accent, color: "#fff", border: "none", borderRadius: 8,
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
                  display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                  background: T.surfaceAlt, color: T.text, border: `1px solid ${T.border}`,
                  borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer",
                }}
              >
                <Eye size={14} /> Vorschau
              </button>
            )}
            <button
              onClick={() => { deleteCampaign(c.id); setSelectedCampaign(null); }}
              style={{
                display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
                background: T.dangerDim, color: T.danger, border: "none", borderRadius: 8,
                fontSize: 13, fontWeight: 500, cursor: "pointer", marginLeft: "auto",
              }}
            >
              <Trash2 size={14} /> Löschen
            </button>
          </div>
        </Card>
      </div>
    );
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
   SHARED STYLES
   ═══════════════════════════════════════════════════════════════════════════ */

const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "#8B8D9A",
  marginBottom: 6,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  background: "#1A1B24",
  border: "1px solid #252630",
  borderRadius: 8,
  color: "#E8E9ED",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
};
