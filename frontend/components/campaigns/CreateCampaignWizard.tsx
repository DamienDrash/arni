"use client";
import { useState, useEffect } from "react";
import {
  Sparkles, Mail, MessageSquare, Smartphone, Send, Globe,
  Calendar, Users, Target, Filter, CheckCircle,
  ArrowRight, ArrowLeft, Eye, Loader2, BookOpen,
  AlertCircle, Layers, Search, X, Image, Info, XCircle,
  Link2, Copy, FileText, Paperclip, Upload, RefreshCw,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import OrchestrationSteps, { OrchestrationStep } from "@/components/campaigns/OrchestrationSteps";
import ABTestConfig from "@/components/campaigns/ABTestConfig";
import CampaignPreviewModal from "@/components/campaigns/CampaignPreviewModal";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface Template { id: number; name: string; type: string; primary_color: string | null; is_default: boolean; }
interface Segment { id: number; name: string; description: string | null; member_count: number; }
interface ContactSegment { id: number; name: string; description: string | null; contact_count?: number; }
interface ContactItem { id: number; first_name: string; last_name: string; email: string; phone?: string; company?: string; tags?: { name: string; color?: string }[]; }
interface TagItem { id: number; name: string; color?: string; contact_count?: number; }
interface WizardProps { onCreated: () => void; onCancel: () => void; }
interface ImageModel {
  slug: string;
  name: string;
  price_per_image: number;
  price_label: string;
  cost_tier: string;
  cost_multiplier: number;
  elo_score: number | null;
  elo_rank: number | null;
  elo_source: string | null;
  quality_stars: number;
  speed_seconds: number;
  best_for: string[];
  description: string;
  badge: string | null;
  badge_color: string | null;
  is_default: boolean;
  cost_note?: string;
  speed_note?: string;
}

interface MediaAsset {
  id: number;
  url: string;
  display_name: string | null;
  description: string | null;
  mime_type: string;
  width: number | null;
  height: number | null;
  created_at: string | null;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════════════════════ */

const CHANNELS = [
  { key: "email", label: "E-Mail", icon: Mail, color: T.email },
  { key: "whatsapp", label: "WhatsApp", icon: MessageSquare, color: T.whatsapp },
  { key: "sms", label: "SMS", icon: Smartphone, color: T.warning },
  { key: "telegram", label: "Telegram", icon: Send, color: T.telegram },
  { key: "multi", label: "Multi-Kanal", icon: Globe, color: T.accentLight },
];

const TONES = [
  { key: "professional", label: "Professionell", desc: "Seriös und geschäftlich" },
  { key: "casual", label: "Locker", desc: "Freundlich und nahbar" },
  { key: "motivational", label: "Motivierend", desc: "Energiegeladen und inspirierend" },
  { key: "urgent", label: "Dringend", desc: "Handlungsorientiert und zeitkritisch" },
];

const CAMPAIGN_TYPES = [
  { key: "broadcast", label: "Broadcast", desc: "Einmaliger Versand an alle Empfänger", icon: Send },
  { key: "drip", label: "Drip-Kampagne", desc: "Automatische Sequenz über Zeit", icon: Calendar },
  { key: "follow_up", label: "Follow-Up", desc: "Nachfassung nach Aktion", icon: ArrowRight },
];

/* ═══════════════════════════════════════════════════════════════════════════
   Shared Styles
   ═══════════════════════════════════════════════════════════════════════ */

const S = {
  card: { background: T.surface, borderRadius: 16, border: `1px solid ${T.border}`, padding: 28 } as React.CSSProperties,
  label: { display: "block", fontSize: 11, fontWeight: 700, color: T.textMuted, marginBottom: 6, textTransform: "uppercase" as const, letterSpacing: "0.04em" } as React.CSSProperties,
  input: { width: "100%", padding: "10px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" as const } as React.CSSProperties,
  textarea: { width: "100%", padding: "10px 14px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 13, outline: "none", boxSizing: "border-box" as const, resize: "vertical" as const } as React.CSSProperties,
  sectionTitle: { fontSize: 17, fontWeight: 800, color: T.text, letterSpacing: "-0.01em" } as React.CSSProperties,
  sectionDesc: { fontSize: 13, color: T.textMuted, marginTop: 4 } as React.CSSProperties,
  primaryBtn: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 22px", borderRadius: 10, border: "none", background: T.accent, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", transition: "all .15s" } as React.CSSProperties,
  secondaryBtn: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.textMuted, fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all .15s" } as React.CSSProperties,
  successBtn: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 22px", borderRadius: 10, border: "none", background: T.success, color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer", transition: "all .15s" } as React.CSSProperties,
  selectCard: (selected: boolean): React.CSSProperties => ({
    display: "flex", alignItems: "center", gap: 12, padding: "16px 18px", borderRadius: 14,
    border: `2px solid ${selected ? T.accent : T.border}`, background: selected ? T.accentDim : T.surfaceAlt,
    cursor: "pointer", transition: "all .15s", textAlign: "left" as const, width: "100%",
  }),
  selectCardIcon: (selected: boolean): React.CSSProperties => ({
    width: 40, height: 40, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
    background: selected ? "rgba(108,92,231,0.2)" : T.surface, flexShrink: 0,
  }),
};

/* ═══════════════════════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════════════════ */

export default function CreateCampaignWizard({ onCreated, onCancel }: WizardProps) {
  const [step, setStep] = useState(0);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [contactSegments, setContactSegments] = useState<ContactSegment[]>([]);
  const [creating, setCreating] = useState(false);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiResult, setAiResult] = useState<any>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Image upload / AI generate state
  const [imageUploading, setImageUploading] = useState(false);
  const [imageGenerating, setImageGenerating] = useState(false);
  const [imageGenPrompt, setImageGenPrompt] = useState("");
  const [showImageGen, setShowImageGen] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [imagePreviewMode, setImagePreviewMode] = useState<'idle' | 'previewing' | 'final'>('idle');
  const [imageHasTextOverlay, setImageHasTextOverlay] = useState(false);
  const [selectedModelSlug, setSelectedModelSlug] = useState<string>("flux2_pro");
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [imageModels, setImageModels] = useState<ImageModel[]>([]);

  // Media library picker state
  const [showMediaPicker, setShowMediaPicker] = useState(false);
  const [mediaPickerAssets, setMediaPickerAssets] = useState<MediaAsset[]>([]);
  const [mediaPickerLoading, setMediaPickerLoading] = useState(false);
  const [mediaPickerPage, setMediaPickerPage] = useState(1);
  const [mediaPickerTotal, setMediaPickerTotal] = useState(0);

  // Auto-generate image state
  const [autoGenerateImage, setAutoGenerateImage] = useState(false);
  const [creditBalance, setCreditBalance] = useState<number | null>(null);
  const [creditCheckLoading, setCreditCheckLoading] = useState(false);
  const [autoImageStatus, setAutoImageStatus] = useState<'idle' | 'generating' | 'done' | 'error'>('idle');
  const [autoImageUrl, setAutoImageUrl] = useState<string | null>(null);
  const [autoImageError, setAutoImageError] = useState<string | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [docUploading, setDocUploading] = useState(false);
  const [docUploadError, setDocUploadError] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "", description: "", type: "broadcast", channel: "email",
    target_type: "all_members", target_segment_id: null as number | null,
    template_id: null as number | null, ai_prompt: "", tone: "professional",
    use_knowledge: true, use_chat_history: false,
    content_subject: "", content_body: "", scheduled_at: "",
    featured_image_url: "",
    attachment_url: "",
    attachment_filename: "",
  });
  const [createdCampaignId, setCreatedCampaignId] = useState<number | null>(null);
  const [orchSteps, setOrchSteps] = useState<OrchestrationStep[]>([
    { step_order: 1, channel: "email", template_id: null, content_override_json: null, wait_hours: 0, condition_type: "always" },
  ]);
  const [showOrchestration, setShowOrchestration] = useState(false);

  // Tags & Manual Contact Selection State
  const [allTags, setAllTags] = useState<TagItem[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [allContacts, setAllContacts] = useState<ContactItem[]>([]);
  const [selectedContactIds, setSelectedContactIds] = useState<number[]>([]);
  const [selectedContactsData, setSelectedContactsData] = useState<Record<number, ContactItem>>({});
  const [contactSearch, setContactSearch] = useState("");
  const [contactsLoading, setContactsLoading] = useState(false);
  const [tagsLoading, setTagsLoading] = useState(false);

  // A/B Testing State
  const [abEnabled, setAbEnabled] = useState(false);
  const [abVariants, setAbVariants] = useState<{variant_name:string;content_subject:string;content_body:string;content_html:string;percentage:number}[]>([
    { variant_name: "A", content_subject: "", content_body: "", content_html: "", percentage: 50 },
    { variant_name: "B", content_subject: "", content_body: "", content_html: "", percentage: 50 },
  ]);
  const [abTestPct, setAbTestPct] = useState(20);
  const [abDuration, setAbDuration] = useState(4);
  const [abMetric, setAbMetric] = useState("open_rate");
  const [abAutoSend, setAbAutoSend] = useState(true);

  /* ─── Load Data ──────────────────────────────────────────────────────── */

  useEffect(() => {
    const load = async () => {
      try {
        const [tplRes, segRes, csRes, modelRes] = await Promise.all([
          apiFetch("/admin/campaigns/templates"), apiFetch("/admin/campaigns/segments"),
          apiFetch("/v2/admin/contacts/segments").catch(() => null),
          apiFetch("/admin/media/image-models").catch(() => null),
        ]);
        if (tplRes.ok) setTemplates(await tplRes.json());
        if (segRes.ok) setSegments(await segRes.json());
        if (csRes?.ok) setContactSegments(await csRes.json());
        if (modelRes?.ok) {
          const d = await modelRes.json();
          const models: ImageModel[] = Array.isArray(d) ? d : (d.models || []);
          setImageModels(models);
          // Auto-select best ELO model (lowest rank number = best)
          const ranked = models
            .filter((m) => m.elo_rank != null)
            .sort((a, b) => (a.elo_rank ?? 999) - (b.elo_rank ?? 999));
          const best = ranked[0] ?? models.find((m) => m.slug === "flux2_pro") ?? models[0];
          if (best) setSelectedModelSlug(best.slug);
        }
      } catch { /* ignore */ }
    };
    load();
  }, []);

  /* ─── Load Tags when "tags" target selected ─────────────────────────── */
  useEffect(() => {
    if (form.target_type === "tags" && allTags.length === 0) {
      setTagsLoading(true);
      apiFetch("/api/v2/contacts/tags")
        .then(async (res) => { if (res.ok) { const data = await res.json(); setAllTags(data.items || data || []); } })
        .catch(() => {})
        .finally(() => setTagsLoading(false));
    }
  }, [form.target_type]);

  /* ─── Load Contacts when "selected" target selected ─────────────────── */
  useEffect(() => {
    if (form.target_type !== "selected") return;

    const timeout = setTimeout(() => {
      setContactsLoading(true);
      const query = contactSearch.trim() ? `&search=${encodeURIComponent(contactSearch.trim())}` : "";
      
      // Filter by channel capability
      let channelFilter = "";
      if (form.channel === "email") {
        channelFilter = "&has_email=true";
      } else if (["whatsapp", "sms", "telegram"].includes(form.channel)) {
        channelFilter = "&has_phone=true";
      }

      apiFetch(`/api/v2/contacts?page_size=2000${channelFilter}${query}`)
        .then(async (res) => { 
          if (res.ok) { 
            const data = await res.json(); 
            setAllContacts(data.items || data || []); 
          } 
        })
        .catch(() => {})
        .finally(() => setContactsLoading(false));
    }, 400);

    return () => clearTimeout(timeout);
  }, [form.target_type, contactSearch, form.channel]);

  /* ─── Media Library Picker ───────────────────────────────────────────── */

  const openMediaPicker = async (page = 1) => {
    setShowMediaPicker(true);
    setMediaPickerLoading(true);
    setMediaPickerPage(page);
    try {
      const res = await apiFetch(`/admin/media?page=${page}&limit=24`);
      if (res.ok) {
        const data = await res.json();
        setMediaPickerAssets(data.items ?? []);
        setMediaPickerTotal(data.total ?? 0);
      }
    } catch { /* ignore */ } finally {
      setMediaPickerLoading(false);
    }
  };

  const selectMediaAsset = (asset: MediaAsset) => {
    setForm(f => ({ ...f, featured_image_url: asset.url }));
    setShowMediaPicker(false);
  };

  const checkCreditBalance = async () => {
    setCreditCheckLoading(true);
    try {
      const res = await apiFetch("/admin/media/credits/balance");
      if (res.ok) {
        const data = await res.json();
        setCreditBalance(data.balance ?? 0);
      }
    } catch { /* ignore */ } finally {
      setCreditCheckLoading(false);
    }
  };

  const triggerAutoImageGeneration = async (campaignId: number) => {
    setAutoImageStatus('generating');
    setAutoImageError(null);
    try {
      const prompt = form.ai_prompt.trim() || form.name;
      const res = await apiFetch("/admin/media/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          size: "1024x1024",
          mode: "final",
          campaign_name: form.name,
          channel: form.channel,
          tone: form.tone,
          task_context: "email_hero",
          has_text_overlay: false,
          model_slug: selectedModelSlug,
        }),
      });
      const data = await res.json() as { url?: string; detail?: string };
      if (!res.ok) throw new Error(data.detail || "Bildgenerierung fehlgeschlagen");
      const imgUrl = data.url ?? "";
      // Persist generated image URL on the campaign
      await apiFetch(`/admin/campaigns/${campaignId}`, {
        method: "PUT",
        body: JSON.stringify({ featured_image_url: imgUrl }),
      });
      setAutoImageUrl(imgUrl);
      setForm((f) => ({ ...f, featured_image_url: imgUrl }));
      setAutoImageStatus('done');
    } catch (e: unknown) {
      setAutoImageError(e instanceof Error ? e.message : "Fehler bei der Bildgenerierung");
      setAutoImageStatus('error');
    }
  };

  /* ─── Image Upload / AI Generate ────────────────────────────────────── */

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageUploading(true);
    setImageError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await apiFetch("/admin/media/upload", { method: "POST", body: fd });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setForm((f) => ({ ...f, featured_image_url: data.url }));
    } catch {
      setImageError("Upload fehlgeschlagen.");
    } finally {
      setImageUploading(false);
      e.target.value = "";
    }
  };

  const handleImagePreview = async () => {
    if (!imageGenPrompt.trim()) return;
    setImageGenerating(true);
    setImageError(null);
    try {
      const res = await apiFetch("/admin/media/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: imageGenPrompt,
          size: "1024x1024",
          mode: "preview",
          campaign_name: form.name,
          channel: form.channel,
          tone: form.tone,
          task_context: "email",
          has_text_overlay: imageHasTextOverlay,
          model_slug: "fal_ai_schnell",  // preview always uses schnell
        }),
      });
      const data = await res.json() as { url?: string; detail?: string };
      if (!res.ok) throw new Error(data.detail || "Vorschau fehlgeschlagen");
      setImagePreviewUrl(data.url ?? null);
      setImagePreviewMode('previewing');
      // Don't set featured_image_url yet — only on finalize
    } catch (e: unknown) {
      setImageError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setImageGenerating(false);
    }
  };

  const handleImageFinalize = async () => {
    if (!imageGenPrompt.trim()) return;
    setImageGenerating(true);
    setImageError(null);
    try {
      const res = await apiFetch("/admin/media/ai-generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: imageGenPrompt,
          size: "1024x1024",
          mode: "final",
          campaign_name: form.name,
          channel: form.channel,
          tone: form.tone,
          task_context: "email",
          has_text_overlay: imageHasTextOverlay,
          model_slug: selectedModelSlug,
        }),
      });
      const data = await res.json() as { url?: string; detail?: string };
      if (!res.ok) throw new Error(data.detail || "Generierung fehlgeschlagen");
      setForm((f: typeof form) => ({ ...f, featured_image_url: data.url ?? "" }));
      setImagePreviewUrl(data.url ?? null);
      setImagePreviewMode('final');
    } catch (e: unknown) {
      setImageError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setImageGenerating(false);
    }
  };

  /* ─── Actions ────────────────────────────────────────────────────────── */

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true); setAiError(null);
    try {
      const res = await apiFetch("/admin/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: form.name, description: form.description, type: form.type, channel: form.channel,
          target_type: form.target_type, template_id: form.template_id || undefined,
          content_subject: form.content_subject || undefined, content_body: form.content_body || undefined,
          ai_prompt: form.ai_prompt || undefined, scheduled_at: form.scheduled_at || undefined,
          featured_image_url: form.featured_image_url || undefined,
          attachment_url: form.attachment_url || undefined,
          attachment_filename: form.attachment_filename || undefined,
          target_filter_json: form.target_segment_id ? JSON.stringify({ segment_id: form.target_segment_id })
            : form.target_type === "tags" && selectedTags.length > 0 ? JSON.stringify({ tags: selectedTags })
            : form.target_type === "selected" && selectedContactIds.length > 0 ? JSON.stringify({ contact_ids: selectedContactIds })
            : undefined,
        }),
      });
      if (!res.ok) { setAiError("Kampagne konnte nicht erstellt werden."); setCreating(false); return; }
      const created = await res.json();
      setCreatedCampaignId(created.id);


      /* Save A/B test config if enabled */
      if (abEnabled && abVariants.length >= 2) {
        try {
          await apiFetch(`/v2/admin/campaigns/${created.id}/ab-test`, {
            method: "POST",
            body: JSON.stringify({
              test_percentage: abTestPct,
              duration_hours: abDuration,
              metric: abMetric,
              auto_send_winner: abAutoSend,
              variants: abVariants,
            }),
          });
        } catch { /* non-blocking */ }
      }

      /* Save orchestration steps if multi-step enabled */
      if (showOrchestration && orchSteps.length > 1) {
        try {
          await apiFetch(`/admin/campaigns/${created.id}/orchestration-steps`, {
            method: "POST",
            body: JSON.stringify({ steps: orchSteps }),
          });
        } catch { /* non-blocking */ }
      }

      if (form.ai_prompt.trim()) {
        if (autoGenerateImage) triggerAutoImageGeneration(created.id); // fire in parallel
        setAiGenerating(true);
        try {
          const aiRes = await apiFetch("/admin/campaigns/ai-generate", {
            method: "POST",
            body: JSON.stringify({ campaign_id: created.id, prompt: form.ai_prompt, use_knowledge: form.use_knowledge, use_chat_history: form.use_chat_history, tone: form.tone }),
          });
          if (aiRes.ok) { const data = await aiRes.json(); setAiResult(data); if (data.preview_url) setPreviewUrl(data.preview_url); setStep(4); }
          else { setAiError("KI-Generierung fehlgeschlagen. Sie können den Inhalt manuell bearbeiten."); }
        } catch { setAiError("KI-Generierung fehlgeschlagen."); }
        setAiGenerating(false);
      } else if (autoGenerateImage) {
        setStep(4);
        triggerAutoImageGeneration(created.id);
      } else { onCreated(); }
    } catch { setAiError("Ein Fehler ist aufgetreten."); }
    setCreating(false);
  };

  /* ─── Steps ──────────────────────────────────────────────────────────── */

  const steps = [
    { title: "Grundlagen", desc: "Name und Kanal" },
    { title: "KI-Prompt", desc: "Inhalt beschreiben" },
    { title: "Zielgruppe", desc: "Empfänger wählen" },
    { title: "Planung", desc: "Zeitpunkt & Vorlage" },
    { title: "Prüfung", desc: "KI-Ergebnis prüfen" },
  ];

  const canProceed = () => { if (step === 0) return !!form.name.trim(); return true; };

  /* ─── Render ─────────────────────────────────────────────────────────── */

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* ── Progress Bar ────────────────────────────────────────────────── */}
      <div style={S.card}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {steps.map((s, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
              <div style={{
                width: 36, height: 36, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 800, flexShrink: 0, transition: "all .2s",
                background: i < step ? T.success : i === step ? T.accent : T.surfaceAlt,
                color: i <= step ? "#fff" : T.textDim,
                boxShadow: i === step ? `0 0 0 3px ${T.accentDim}` : "none",
              }}>
                {i < step ? <CheckCircle size={16} /> : i + 1}
              </div>
              <div style={{ display: "block" }}>
                <p style={{ fontSize: 12, fontWeight: 700, color: i <= step ? T.text : T.textDim }}>{s.title}</p>
                <p style={{ fontSize: 10, color: T.textDim }}>{s.desc}</p>
              </div>
              {i < steps.length - 1 && (
                <div style={{ flex: 1, height: 2, margin: "0 12px", borderRadius: 1, background: i < step ? T.success : T.border }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ── Step Content ────────────────────────────────────────────────── */}
      <div style={{ ...S.card, padding: 32 }}>

        {/* Step 0: Basics */}
        {step === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <h3 style={S.sectionTitle}>Kampagnen-Grundlagen</h3>
            <div>
              <label style={S.label}>Kampagnenname *</label>
              <input style={S.input} type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="z.B. Newsletter März 2026" />
            </div>
            <div>
              <label style={S.label}>Beschreibung</label>
              <textarea style={{ ...S.textarea, height: 56 }} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Kurze Beschreibung..." />
            </div>
            <div>
              <label style={{ ...S.label, marginBottom: 12 }}>Kanal *</label>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
                {CHANNELS.map((ch) => {
                  const Icon = ch.icon; const selected = form.channel === ch.key;
                  return (
                    <button key={ch.key} onClick={() => setForm({ ...form, channel: ch.key })} style={{
                      display: "flex", flexDirection: "column", alignItems: "center", gap: 8, padding: "16px 8px",
                      borderRadius: 14, border: `2px solid ${selected ? T.accent : T.border}`,
                      background: selected ? T.accentDim : T.surfaceAlt, cursor: "pointer", transition: "all .15s",
                    }}>
                      <Icon size={20} style={{ color: selected ? ch.color : T.textDim }} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: selected ? T.text : T.textDim }}>{ch.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Campaign Type */}
            <div>
              <label style={{ ...S.label, marginBottom: 12 }}>Kampagnen-Typ</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {CAMPAIGN_TYPES.map((ct) => {
                  const Icon = ct.icon; const selected = form.type === ct.key;
                  return (
                    <button key={ct.key} onClick={() => setForm({ ...form, type: ct.key })} style={S.selectCard(selected)}>
                      <div style={S.selectCardIcon(selected)}>
                        <Icon size={18} style={{ color: selected ? T.accentLight : T.textDim }} />
                      </div>
                      <div>
                        <p style={{ fontSize: 13, fontWeight: 700, color: selected ? T.text : T.textMuted }}>{ct.label}</p>
                        <p style={{ fontSize: 11, color: T.textDim }}>{ct.desc}</p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

          </div>
        )}

        {/* Step 1: AI Prompt */}
        {step === 1 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <h3 style={S.sectionTitle}>KI-gestützte Inhaltserstellung</h3>
              <p style={S.sectionDesc}>Beschreiben Sie, was die Kampagne beinhalten soll. Die KI nutzt Ihren Wissensspeicher, um faktenbasierte Inhalte zu erstellen.</p>
            </div>

            {/* AI Prompt Card */}
            <div style={{ background: `linear-gradient(135deg, ${T.accentDim}, ${T.surface})`, border: `1px solid rgba(108,92,231,0.3)`, borderRadius: 14, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Sparkles size={18} style={{ color: T.accentLight }} />
                <span style={{ fontSize: 13, fontWeight: 800, color: T.text }}>KI-Prompt</span>
                <span style={{ padding: "2px 8px", background: "rgba(108,92,231,0.2)", color: T.accentLight, fontSize: 10, fontWeight: 800, borderRadius: 20, textTransform: "uppercase" }}>Empfohlen</span>
              </div>
              <textarea style={{ ...S.textarea, height: 120, background: "rgba(26,27,36,0.8)" }} value={form.ai_prompt} onChange={(e) => setForm({ ...form, ai_prompt: e.target.value })}
                placeholder="z.B. Erstelle einen Newsletter über unsere neuen Kursangebote im März. Erwähne die Preise aus unserer aktuellen Preisliste und füge einen Call-to-Action für eine kostenlose Probestunde hinzu." />

              {/* Tone Selection */}
              <div>
                <label style={S.label}>Tonalität</label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
                  {TONES.map((t) => {
                    const selected = form.tone === t.key;
                    return (
                      <button key={t.key} onClick={() => setForm({ ...form, tone: t.key })} style={{
                        padding: "10px 12px", borderRadius: 10, border: `1px solid ${selected ? T.accent : T.border}`,
                        background: selected ? T.accentDim : T.surfaceAlt, cursor: "pointer", textAlign: "left", transition: "all .15s",
                      }}>
                        <p style={{ fontSize: 12, fontWeight: 700, color: selected ? T.text : T.textMuted }}>{t.label}</p>
                        <p style={{ fontSize: 10, color: T.textDim, marginTop: 2 }}>{t.desc}</p>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Knowledge Toggles */}
              <div style={{ display: "flex", alignItems: "center", gap: 20, paddingTop: 4 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                  <input type="checkbox" checked={form.use_knowledge} onChange={(e) => setForm({ ...form, use_knowledge: e.target.checked })} style={{ width: 16, height: 16, accentColor: T.accent }} />
                  <BookOpen size={14} style={{ color: T.textMuted }} />
                  <span style={{ fontSize: 12, color: T.textMuted }}>Wissensspeicher nutzen</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
                  <input type="checkbox" checked={form.use_chat_history} onChange={(e) => setForm({ ...form, use_chat_history: e.target.checked })} style={{ width: 16, height: 16, accentColor: T.accent }} />
                  <MessageSquare size={14} style={{ color: T.textMuted }} />
                  <span style={{ fontSize: 12, color: T.textMuted }}>Chat-Kontext einbeziehen</span>
                </label>
              </div>
            </div>

            {/* Manual Fallback */}
            <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 20 }}>
              <p style={{ fontSize: 12, color: T.textDim, marginBottom: 12 }}>Oder manuell eingeben:</p>
              {form.channel === "email" && (
                <div style={{ marginBottom: 12 }}>
                  <label style={S.label}>Betreff</label>
                  <input style={S.input} type="text" value={form.content_subject} onChange={(e) => setForm({ ...form, content_subject: e.target.value })} placeholder="E-Mail Betreff..." />
                </div>
              )}
              <div>
                <label style={S.label}>Nachricht</label>
                <textarea style={{ ...S.textarea, height: 100, fontFamily: "monospace" }} value={form.content_body} onChange={(e) => setForm({ ...form, content_body: e.target.value })} placeholder="Ihre Nachricht..." />
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  {["{{ contact.first_name }}", "{{ contact.last_name }}", "{{ contact.company }}"].map((v) => (
                    <button key={v} onClick={() => setForm({ ...form, content_body: form.content_body + v })} style={{
                      padding: "4px 8px", background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 6,
                      fontSize: 10, color: T.accentLight, fontFamily: "monospace", cursor: "pointer", transition: "all .12s",
                    }}>{v}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Targeting */}
        {step === 2 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <h3 style={S.sectionTitle}>Zielgruppe auswählen</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { key: "all_members", label: "Alle Kontakte", desc: "An alle aktiven Kontakte senden", icon: Users },
                { key: "segment", label: "Segment", desc: "Vordefiniertes Segment verwenden", icon: Target },
                { key: "tags", label: "Nach Tags", desc: "Kontakte nach Tags filtern", icon: Filter },
                { key: "selected", label: "Manuell", desc: "Einzelne Kontakte auswählen", icon: CheckCircle },
              ].map((t) => {
                const Icon = t.icon; const selected = form.target_type === t.key;
                return (
                  <button key={t.key} onClick={() => setForm({ ...form, target_type: t.key })} style={S.selectCard(selected)}>
                    <div style={S.selectCardIcon(selected)}>
                      <Icon size={20} style={{ color: selected ? T.accentLight : T.textDim }} />
                    </div>
                    <div>
                      <p style={{ fontSize: 13, fontWeight: 700, color: selected ? T.text : T.textMuted }}>{t.label}</p>
                      <p style={{ fontSize: 11, color: T.textDim }}>{t.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Segment Picker */}
            {form.target_type === "segment" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <label style={S.label}>Segment auswählen</label>
                {[...segments.map(s => ({ ...s, source: "legacy" })), ...contactSegments.map(s => ({ ...s, member_count: s.contact_count || 0, source: "v2" }))].map((seg: any) => {
                  const selected = form.target_segment_id === seg.id;
                  return (
                    <button key={`${seg.source}-${seg.id}`} onClick={() => setForm({ ...form, target_segment_id: seg.id })} style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", borderRadius: 12,
                      border: `1px solid ${selected ? T.accent : T.border}`, background: selected ? T.accentDim : T.surfaceAlt,
                      cursor: "pointer", textAlign: "left", width: "100%", transition: "all .15s",
                    }}>
                      <div>
                        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{seg.name}</span>
                        {seg.description && <p style={{ fontSize: 11, color: T.textDim, marginTop: 2 }}>{seg.description}</p>}
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 700, color: T.accentLight, background: T.accentDim, padding: "4px 10px", borderRadius: 20 }}>{seg.member_count} Kontakte</span>
                    </button>
                  );
                })}
                {segments.length === 0 && contactSegments.length === 0 && (
                  <p style={{ fontSize: 13, color: T.textDim, padding: "16px 0", textAlign: "center" }}>Keine Segmente vorhanden. Erstellen Sie zuerst ein Segment im Kontakte-Modul.</p>
                )}
              </div>
            )}

            {/* Tag Picker */}
            {form.target_type === "tags" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <label style={S.label}>Tags auswählen</label>
                {tagsLoading ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "16px 0", justifyContent: "center" }}>
                    <Loader2 size={16} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
                    <span style={{ fontSize: 13, color: T.textMuted }}>Tags werden geladen...</span>
                  </div>
                ) : allTags.length === 0 ? (
                  <p style={{ fontSize: 13, color: T.textDim, padding: "16px 0", textAlign: "center" }}>Keine Tags vorhanden. Erstellen Sie zuerst Tags im Kontakte-Modul.</p>
                ) : (
                  <>
                    {selectedTags.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 4 }}>
                        {selectedTags.map((tag) => (
                          <span key={tag} style={{
                            display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 8,
                            background: T.accentDim, border: `1px solid ${T.accent}`, fontSize: 12, fontWeight: 600, color: T.accentLight,
                          }}>
                            {tag}
                            <button onClick={() => setSelectedTags(selectedTags.filter(t => t !== tag))} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}>
                              <X size={12} style={{ color: T.textMuted }} />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {allTags.map((tag) => {
                        const isSelected = selectedTags.includes(tag.name);
                        return (
                          <button key={tag.id} onClick={() => {
                            setSelectedTags(isSelected ? selectedTags.filter(t => t !== tag.name) : [...selectedTags, tag.name]);
                          }} style={{
                            display: "inline-flex", alignItems: "center", gap: 6, padding: "8px 14px", borderRadius: 10,
                            border: `1px solid ${isSelected ? T.accent : T.border}`, background: isSelected ? T.accentDim : T.surfaceAlt,
                            cursor: "pointer", transition: "all .15s", fontSize: 12, fontWeight: 600,
                            color: isSelected ? T.accentLight : T.textMuted,
                          }}>
                            {tag.color && <div style={{ width: 8, height: 8, borderRadius: "50%", background: tag.color, flexShrink: 0 }} />}
                            {tag.name}
                            {tag.contact_count !== undefined && (
                              <span style={{ fontSize: 10, color: T.textDim, marginLeft: 2 }}>({tag.contact_count})</span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                    {selectedTags.length > 0 && (
                      <p style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>
                        {selectedTags.length} Tag{selectedTags.length !== 1 ? "s" : ""} ausgewählt
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            {/* Manual Contact Picker */}
            {form.target_type === "selected" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <label style={S.label}>Kontakte auswählen</label>
                {/* Search */}
                <div style={{ position: "relative" }}>
                  <Search size={16} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim }} />
                  <input
                    type="text" placeholder="Kontakte suchen (Name, E-Mail, Firma)..."
                    value={contactSearch} onChange={(e) => setContactSearch(e.target.value)}
                    style={{ ...S.input, paddingLeft: 36 }}
                  />
                </div>
                {/* Selected Contacts */}
                {selectedContactIds.length > 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {selectedContactIds.map((cid) => {
                      const c = selectedContactsData[cid] || allContacts.find(ct => ct.id === cid);
                      return c ? (
                        <span key={cid} style={{
                          display: "inline-flex", alignItems: "center", gap: 4, padding: "4px 10px", borderRadius: 8,
                          background: T.accentDim, border: `1px solid ${T.accent}`, fontSize: 12, fontWeight: 600, color: T.accentLight,
                        }}>
                          {c.first_name} {c.last_name}
                          <button onClick={() => setSelectedContactIds(selectedContactIds.filter(id => id !== cid))} style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}>
                            <X size={12} style={{ color: T.textMuted }} />
                          </button>
                        </span>
                      ) : null;
                    })}
                    <p style={{ width: "100%", fontSize: 11, color: T.textMuted }}>
                      {selectedContactIds.length} Kontakt{selectedContactIds.length !== 1 ? "e" : ""} ausgewählt
                    </p>
                  </div>
                )}
                {/* Contact List */}
                {contactsLoading ? (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "16px 0", justifyContent: "center" }}>
                    <Loader2 size={16} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
                    <span style={{ fontSize: 13, color: T.textMuted }}>Kontakte werden geladen...</span>
                  </div>
                ) : (
                  <div style={{ maxHeight: 280, overflowY: "auto", border: `1px solid ${T.border}`, borderRadius: 12, background: T.surfaceAlt }}>
                    {allContacts.map((c) => {
                      const isSelected = selectedContactIds.includes(c.id);
                      return (
                        <button key={c.id} onClick={() => {
                          if (isSelected) {
                            setSelectedContactIds(selectedContactIds.filter(id => id !== c.id));
                          } else {
                            setSelectedContactIds([...selectedContactIds, c.id]);
                            setSelectedContactsData(prev => ({ ...prev, [c.id]: c }));
                          }
                        }} style={{
                          display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", width: "100%",
                          borderBottom: `1px solid ${T.border}`, background: isSelected ? T.accentDim : "transparent",
                          cursor: "pointer", textAlign: "left", transition: "all .12s", border: "none",
                        }}>
                          <div style={{
                            width: 20, height: 20, borderRadius: 4, border: `2px solid ${isSelected ? T.accent : T.border}`,
                            background: isSelected ? T.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                          }}>
                            {isSelected && <CheckCircle size={12} style={{ color: "#fff" }} />}
                          </div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {c.first_name} {c.last_name}
                            </p>
                            <p style={{ fontSize: 11, color: T.textDim, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {c.email}{c.company ? ` · ${c.company}` : ""}
                            </p>
                          </div>
                        </button>
                      );
                    })}
                    {allContacts.length === 0 && !contactsLoading && (
                      <p style={{ fontSize: 13, color: T.textDim, padding: "16px", textAlign: "center" }}>Keine Kontakte vorhanden.</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Scheduling & Template */}
        {step === 3 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <h3 style={S.sectionTitle}>Planung & Vorlage</h3>

            {/* Send Time */}
            <div>
              <label style={{ ...S.label, marginBottom: 12 }}>Versandzeitpunkt</label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <button onClick={() => setForm({ ...form, scheduled_at: "" })} style={S.selectCard(!form.scheduled_at)}>
                  <Send size={20} style={{ color: !form.scheduled_at ? T.accentLight : T.textDim }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Sofort senden</p>
                    <p style={{ fontSize: 11, color: T.textDim }}>Nach Freigabe direkt versenden</p>
                  </div>
                </button>
                <button onClick={() => setForm({ ...form, scheduled_at: new Date(Date.now() + 86400000).toISOString().slice(0, 16) })} style={S.selectCard(!!form.scheduled_at)}>
                  <Calendar size={20} style={{ color: form.scheduled_at ? T.accentLight : T.textDim }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Zeitpunkt planen</p>
                    <p style={{ fontSize: 11, color: T.textDim }}>Versand zu einem bestimmten Zeitpunkt</p>
                  </div>
                </button>
              </div>
              {form.scheduled_at && (
                <input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} style={{ ...S.input, marginTop: 12 }} />
              )}
            </div>

            {/* Template Selection */}
            {form.channel === "email" && templates.length > 0 && (
              <div>
                <label style={{ ...S.label, marginBottom: 12 }}><Layers size={13} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} /> E-Mail-Vorlage</label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
                  <button onClick={() => setForm({ ...form, template_id: null })} style={{
                    padding: 14, borderRadius: 12, border: `2px solid ${!form.template_id ? T.accent : T.border}`,
                    background: !form.template_id ? T.accentDim : T.surfaceAlt, cursor: "pointer", textAlign: "center",
                  }}>
                    <p style={{ fontSize: 12, fontWeight: 600, color: T.textMuted }}>Keine Vorlage</p>
                  </button>
                  {templates.filter(t => t.type === "email").map((tpl) => {
                    const selected = form.template_id === tpl.id;
                    return (
                      <button key={tpl.id} onClick={() => setForm({ ...form, template_id: tpl.id })} style={{
                        padding: 14, borderRadius: 12, border: `2px solid ${selected ? T.accent : T.border}`,
                        background: selected ? T.accentDim : T.surfaceAlt, cursor: "pointer", textAlign: "left",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <div style={{ width: 12, height: 12, borderRadius: "50%", background: tpl.primary_color || T.accent }} />
                          <span style={{ fontSize: 12, fontWeight: 700, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{tpl.name}</span>
                        </div>
                        {tpl.is_default && <span style={{ fontSize: 10, color: T.warning }}>★ Standard</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Omnichannel Orchestration */}
            <div>
              <button
                onClick={() => setShowOrchestration(!showOrchestration)}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%",
                  padding: "14px 18px", borderRadius: 12,
                  border: `1px solid ${showOrchestration ? T.accent : T.border}`,
                  background: showOrchestration ? T.accentDim : T.surfaceAlt,
                  cursor: "pointer", textAlign: "left" as const,
                }}
              >
                <Globe size={18} style={{ color: showOrchestration ? T.accentLight : T.textDim }} />
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 700, color: T.text, margin: 0 }}>Omnichannel-Sequenz</p>
                  <p style={{ fontSize: 11, color: T.textDim, margin: 0 }}>Mehrstufige Kampagne über verschiedene Kanäle planen</p>
                </div>
                <div style={{
                  width: 20, height: 20, borderRadius: 4,
                  border: `2px solid ${showOrchestration ? T.accent : T.border}`,
                  background: showOrchestration ? T.accent : "transparent",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {showOrchestration && <CheckCircle size={12} style={{ color: "#fff" }} />}
                </div>
              </button>
              {showOrchestration && (
                <div style={{ marginTop: 14 }}>
                  <OrchestrationSteps
                    steps={orchSteps}
                    onChange={setOrchSteps}
                    templates={templates.map(t => ({ id: t.id, name: t.name, channel: t.type }))}
                  />
                </div>
              )}
            </div>

            {/* A/B Testing */}
            <ABTestConfig
              isEnabled={abEnabled}
              onToggle={setAbEnabled}
              variants={abVariants}
              onVariantsChange={setAbVariants}
              testPercentage={abTestPct}
              onTestPercentageChange={setAbTestPct}
              durationHours={abDuration}
              onDurationHoursChange={setAbDuration}
              metric={abMetric}
              onMetricChange={setAbMetric}
              autoSend={abAutoSend}
              onAutoSendChange={setAbAutoSend}
            />

            {/* Featured Image (email only) */}
            {form.channel === "email" && (
              <div>
                <label style={{ ...S.label, marginBottom: 12 }}><Image size={13} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} /> Titelbild (optional)</label>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>

                  {/* ── Auto-generate image checkbox ──────────────────────── */}
                  <div style={{ border: `1px solid ${T.border}`, borderRadius: 12, padding: "14px 16px", marginBottom: 12, background: autoGenerateImage ? "rgba(108,92,231,0.06)" : "transparent" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={autoGenerateImage}
                        onChange={(e) => {
                          setAutoGenerateImage(e.target.checked);
                          if (e.target.checked) checkCreditBalance();
                        }}
                        style={{ width: 16, height: 16, accentColor: T.accent }}
                      />
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>KI-Bild automatisch generieren</span>
                        <p style={{ margin: "2px 0 0", fontSize: 11, color: T.textDim }}>Generiert automatisch ein passendes Titelbild aus dem Kampagnen-Prompt</p>
                      </div>
                      {autoGenerateImage && <span style={{ padding: "2px 8px", background: "rgba(108,92,231,0.2)", color: T.accentLight, fontSize: 10, fontWeight: 800, borderRadius: 20, flexShrink: 0 }}>AUTO</span>}
                    </label>

                    {/* Credit balance + warning */}
                    {autoGenerateImage && (
                      <div style={{ paddingLeft: 26, marginTop: 8 }}>
                        {creditCheckLoading ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <Loader2 size={12} style={{ animation: "spin 1s linear infinite", color: T.textDim }} />
                            <span style={{ fontSize: 11, color: T.textDim }}>Credits werden geprüft…</span>
                          </div>
                        ) : creditBalance !== null ? (() => {
                          const needed = imageModels.find((m) => m.slug === selectedModelSlug)?.cost_multiplier ?? 3;
                          const ok = creditBalance >= needed;
                          return (
                            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                              <span style={{ fontSize: 11, color: T.textDim }}>
                                Guthaben: <strong style={{ color: ok ? T.success : T.danger }}>{creditBalance} Credits</strong>
                                {" · "}benötigt: ~{needed} Credits
                                {" · "}Modell: {imageModels.find((m) => m.slug === selectedModelSlug)?.name ?? "—"}
                              </span>
                              {!ok && (
                                <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "10px 12px", background: "rgba(255,107,107,0.1)", border: `1px solid rgba(255,107,107,0.3)`, borderRadius: 8 }}>
                                  <AlertCircle size={14} style={{ color: T.danger, flexShrink: 0, marginTop: 1 }} />
                                  <span style={{ fontSize: 12, color: T.danger }}>
                                    Nicht genug Credits für die Bildgenerierung. Bitte erwerben Sie weitere Credits unter <strong>Einstellungen → Medien</strong> oder wählen Sie ein günstigeres Modell.
                                  </span>
                                </div>
                              )}
                            </div>
                          );
                        })() : null}
                      </div>
                    )}

                    {/* Model selector for auto-generate */}
                    {autoGenerateImage && imageModels.length > 0 && (() => {
                      const bestRank1 = imageModels.filter(m => m.elo_rank != null).sort((a, b) => (a.elo_rank ?? 999) - (b.elo_rank ?? 999))[0];
                      const selectedModel = imageModels.find(m => m.slug === selectedModelSlug);
                      const isBest = selectedModel?.slug === bestRank1?.slug;
                      return (
                        <div style={{ paddingLeft: 26, marginTop: 8 }}>
                          <button
                            type="button"
                            onClick={() => setShowModelPicker(!showModelPicker)}
                            style={{
                              display: "flex", alignItems: "center", gap: 6,
                              padding: "6px 12px", borderRadius: 8,
                              background: T.surface, border: `1px solid ${T.border}`,
                              color: T.textMuted, fontSize: 11, fontWeight: 600, cursor: "pointer",
                            }}
                          >
                            <Sparkles size={12} />
                            Modell: {selectedModel?.name ?? "—"}
                            {isBest && <span style={{ padding: "1px 6px", background: "rgba(108,92,231,0.2)", color: T.accentLight, fontSize: 9, fontWeight: 800, borderRadius: 10 }}>BEST ELO</span>}
                            {selectedModel && <span style={{ color: T.textDim }}>{selectedModel.cost_multiplier} Credits</span>}
                            <span style={{ marginLeft: 2 }}>{showModelPicker ? "▲" : "▼"}</span>
                          </button>

                          {showModelPicker && (
                            <div style={{
                              marginTop: 8, borderRadius: 12,
                              border: `1px solid ${T.border}`,
                              background: T.surface,
                              overflow: "hidden",
                              maxHeight: 320, overflowY: "auto",
                            }}>
                              {imageModels.map((model) => {
                                const isSelected = model.slug === selectedModelSlug;
                                const isBestModel = model.slug === bestRank1?.slug;
                                const stars = "★".repeat(model.quality_stars) + "☆".repeat(5 - model.quality_stars);
                                return (
                                  <button
                                    key={model.slug}
                                    type="button"
                                    onClick={() => { setSelectedModelSlug(model.slug); setShowModelPicker(false); }}
                                    style={{
                                      display: "block", width: "100%", textAlign: "left",
                                      padding: "10px 14px",
                                      background: isSelected ? T.accentDim : "transparent",
                                      border: "none",
                                      borderBottom: `1px solid ${T.border}`,
                                      cursor: "pointer",
                                    }}
                                  >
                                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                        {isBestModel && (
                                          <span style={{ padding: "1px 6px", background: "rgba(108,92,231,0.2)", color: T.accentLight, fontSize: 9, fontWeight: 800, borderRadius: 10 }}>BEST ELO</span>
                                        )}
                                        {model.badge && !isBestModel && (
                                          <span style={{ padding: "2px 7px", borderRadius: 20, fontSize: 10, fontWeight: 700, background: (model.badge_color ?? T.accent) + "22", color: model.badge_color ?? T.accent }}>{model.badge}</span>
                                        )}
                                        <span style={{ fontSize: 13, fontWeight: 700, color: isSelected ? T.accent : T.text }}>{model.name}</span>
                                      </div>
                                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                        <span style={{ fontSize: 11, color: T.warning, letterSpacing: 1 }}>{stars}</span>
                                        <span style={{ fontSize: 11, fontWeight: 700, color: model.cost_tier === "premium" ? T.warning : T.success }}>{model.cost_multiplier} Credits</span>
                                      </div>
                                    </div>
                                    {model.elo_score && (
                                      <p style={{ fontSize: 10, color: T.textDim, margin: "2px 0 0" }}>
                                        Elo {model.elo_score} · Rang #{model.elo_rank} · {model.elo_source}
                                      </p>
                                    )}
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>

                  {/* ── Manual upload / generate (disabled when auto-generate is on) ─ */}
                  <div style={{ opacity: autoGenerateImage ? 0.35 : 1, pointerEvents: autoGenerateImage ? "none" : "auto", transition: "opacity .2s" }}>
                    {autoGenerateImage && (
                      <p style={{ fontSize: 11, color: T.textDim, marginBottom: 8, textAlign: "center" as const }}>Manuelles Hochladen und Generieren ist deaktiviert, solange die automatische KI-Bilderstellung aktiv ist.</p>
                    )}
                    {/* Action row */}
                    <div style={{ display: "flex", gap: 8 }}>
                      <label style={{ ...S.secondaryBtn, cursor: imageUploading ? "default" : "pointer", opacity: imageUploading ? 0.6 : 1 }}>
                        {imageUploading ? <Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Image size={14} />}
                        {imageUploading ? "Wird hochgeladen..." : "Bild hochladen"}
                        <input type="file" accept="image/*" onChange={handleImageUpload} style={{ display: "none" }} disabled={imageUploading} />
                      </label>
                      <button onClick={() => { setShowImageGen(!showImageGen); setImageError(null); if (showImageGen) { setImagePreviewMode('idle'); setImagePreviewUrl(null); } }} style={{ ...S.secondaryBtn, color: T.accentLight }}>
                        <Sparkles size={14} /> KI generieren
                      </button>
                      <button type="button" onClick={() => openMediaPicker(1)} style={{ ...S.secondaryBtn, color: T.textMuted }}>
                        <Search size={14} /> Mediathek
                      </button>
                    </div>

                    {/* AI generate form */}
                    {showImageGen && (
                      <div style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 10, padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                        {/* Prompt input */}
                        <input
                          style={S.input}
                          type="text"
                          value={imageGenPrompt}
                          onChange={(e) => setImageGenPrompt(e.target.value)}
                          placeholder="Bildprompt, z.B. Fitnessstudio, motivierende Atmosphäre, hell und modern"
                          onKeyDown={(e) => { if (e.key === "Enter") handleImagePreview(); }}
                        />

                        {/* Model selector */}
                        {imageModels.length > 0 && (
                          <div>
                            <button
                              type="button"
                              onClick={() => setShowModelPicker(!showModelPicker)}
                              style={{
                                display: "flex", alignItems: "center", gap: 6,
                                padding: "6px 12px", borderRadius: 8,
                                background: T.surface, border: `1px solid ${T.border}`,
                                color: T.textMuted, fontSize: 11, fontWeight: 600, cursor: "pointer",
                              }}
                            >
                              <Sparkles size={12} />
                              Modell: {imageModels.find(m => m.slug === selectedModelSlug)?.name ?? "FLUX.2 Pro"}
                              {" · "}{imageModels.find(m => m.slug === selectedModelSlug)?.cost_multiplier ?? 3} Credits
                              <span style={{ marginLeft: 2 }}>{showModelPicker ? "▲" : "▼"}</span>
                            </button>

                            {showModelPicker && (
                              <div style={{
                                marginTop: 8, borderRadius: 12,
                                border: `1px solid ${T.border}`,
                                background: T.surface,
                                overflow: "hidden",
                                maxHeight: 380, overflowY: "auto",
                              }}>
                                {imageModels.map((model) => {
                                  const isSelected = model.slug === selectedModelSlug;
                                  const stars = "★".repeat(model.quality_stars) + "☆".repeat(5 - model.quality_stars);
                                  const isExpensive = model.cost_tier === "premium";
                                  return (
                                    <button
                                      key={model.slug}
                                      type="button"
                                      onClick={() => { setSelectedModelSlug(model.slug); setShowModelPicker(false); }}
                                      style={{
                                        display: "block", width: "100%", textAlign: "left",
                                        padding: "12px 16px",
                                        background: isSelected ? T.accentDim : "transparent",
                                        border: "none",
                                        borderBottom: `1px solid ${T.border}`,
                                        cursor: "pointer",
                                      }}
                                    >
                                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                          {model.badge && (
                                            <span style={{
                                              padding: "2px 7px", borderRadius: 20, fontSize: 10, fontWeight: 700,
                                              background: (model.badge_color ?? T.accent) + "22",
                                              color: model.badge_color ?? T.accent,
                                              whiteSpace: "nowrap",
                                            }}>
                                              {model.badge}
                                            </span>
                                          )}
                                          <span style={{ fontSize: 13, fontWeight: 700, color: isSelected ? T.accent : T.text }}>
                                            {model.name}
                                          </span>
                                        </div>
                                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                                          <span style={{ fontSize: 11, color: T.warning, letterSpacing: 1 }}>{stars}</span>
                                          <span style={{
                                            fontSize: 11, fontWeight: 700,
                                            color: isExpensive ? T.warning : T.success,
                                          }}>
                                            {model.cost_multiplier} Credits
                                            {isExpensive && " ⚡"}
                                          </span>
                                        </div>
                                      </div>
                                      <p style={{ fontSize: 11, color: T.textMuted, margin: "3px 0 0", lineHeight: 1.4 }}>
                                        {model.description}
                                      </p>
                                      <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                                        {model.elo_score && (
                                          <span style={{ fontSize: 10, color: T.textDim }}>
                                            Elo {model.elo_score} · Rang #{model.elo_rank} · {model.elo_source}
                                          </span>
                                        )}
                                        {model.cost_note && (
                                          <span style={{ fontSize: 10, color: T.warning }}>⚡ {model.cost_note}</span>
                                        )}
                                        {model.speed_note && (
                                          <span style={{ fontSize: 10, color: T.textDim }}>⏱ {model.speed_note}</span>
                                        )}
                                      </div>
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Text overlay checkbox */}
                        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 12, color: T.textMuted }}>
                          <input
                            type="checkbox"
                            checked={imageHasTextOverlay}
                            onChange={(e) => setImageHasTextOverlay(e.target.checked)}
                            style={{ width: 14, height: 14, accentColor: T.accent }}
                          />
                          Enthält Text (z.B. Kurszeiten, Promo-Code)
                        </label>
                        {/* Action buttons */}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          <button
                            onClick={handleImagePreview}
                            disabled={imageGenerating || !imageGenPrompt.trim()}
                            style={{ ...S.primaryBtn, opacity: imageGenerating || !imageGenPrompt.trim() ? 0.6 : 1 }}
                          >
                            {imageGenerating && imagePreviewMode === 'idle' ? (
                              <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Vorschau lädt...</>
                            ) : (
                              <><Eye size={14} /> Vorschau (Schnell)</>
                            )}
                          </button>
                          {imagePreviewMode === 'previewing' && (
                            <>
                              <button
                                onClick={() => {
                                  if (imagePreviewUrl) {
                                    setForm((f: typeof form) => ({ ...f, featured_image_url: imagePreviewUrl }));
                                    setImagePreviewMode('final');
                                  }
                                }}
                                style={{ ...S.secondaryBtn, color: T.success }}
                              >
                                <CheckCircle size={14} /> Vorschau verwenden
                              </button>
                              <button
                                onClick={handleImageFinalize}
                                disabled={imageGenerating || !imageGenPrompt.trim()}
                                style={{ ...S.primaryBtn, background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`, opacity: imageGenerating || !imageGenPrompt.trim() ? 0.6 : 1 }}
                              >
                                {imageGenerating ? (
                                  <><Loader2 size={14} style={{ animation: "spin 1s linear infinite" }} /> Generiere...</>
                                ) : (
                                  <><Sparkles size={14} /> {imageModels.find(m => m.slug === selectedModelSlug)?.name ?? "Finale Qualität"}</>
                                )}
                              </button>
                            </>
                          )}
                        </div>
                        {/* Preview thumbnail */}
                        {imagePreviewUrl && imagePreviewMode !== 'idle' && (
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <img
                              src={imagePreviewUrl}
                              alt="Vorschau"
                              style={{ height: 80, borderRadius: 8, border: `1px solid ${T.border}`, objectFit: "cover" }}
                            />
                            {imagePreviewMode === 'final' && (
                              <span style={{
                                display: "inline-flex", alignItems: "center", gap: 4,
                                padding: "4px 10px", borderRadius: 20,
                                background: T.successDim, border: `1px solid rgba(0,184,148,0.3)`,
                                fontSize: 11, fontWeight: 700, color: T.success,
                              }}>
                                <CheckCircle size={11} /> Finale Version
                              </span>
                            )}
                          </div>
                        )}
                        {/* Info text */}
                        <p style={{ fontSize: 10, color: T.textDim, margin: 0 }}>
                          Vorschau: 1 Credit &bull; Finale Version: gewähltes Modell ({imageModels.find(m => m.slug === selectedModelSlug)?.cost_multiplier ?? 3} Credits)
                        </p>
                      </div>
                    )}

                    {/* URL input (manual / paste) */}
                    <input
                      style={S.input}
                      type="url"
                      value={form.featured_image_url}
                      onChange={(e) => setForm({ ...form, featured_image_url: e.target.value })}
                      placeholder="Oder URL direkt einfügen..."
                    />

                    {imageError && <p style={{ fontSize: 11, color: T.danger, margin: 0 }}>{imageError}</p>}

                    {form.featured_image_url && (
                      <div style={{ position: "relative", borderRadius: 10, overflow: "hidden", border: `1px solid ${T.border}`, maxHeight: 160 }}>
                        <img src={form.featured_image_url} alt="Titelbild Vorschau" style={{ width: "100%", height: 160, objectFit: "cover", display: "block" }} />
                        <button onClick={() => setForm({ ...form, featured_image_url: "" })} style={{ position: "absolute", top: 8, right: 8, background: "rgba(0,0,0,0.6)", border: "none", borderRadius: 6, padding: "4px 6px", cursor: "pointer", display: "flex" }}>
                          <X size={14} style={{ color: "#fff" }} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Anhang (optional) */}
            <div style={{ marginTop: 24 }}>
              <label style={{ ...S.label, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
                <Paperclip size={13} /> Anhang (optional)
              </label>

              {/* Uploaded file preview */}
              {form.attachment_url ? (
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: T.surfaceAlt, border: `1px solid ${T.success || "#22c55e"}`, borderRadius: 8, marginBottom: 8 }}>
                  <FileText size={18} style={{ color: T.accent, flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {form.attachment_filename || form.attachment_url.split("/").pop() || "Dokument"}
                    </p>
                    <a href={form.attachment_url} target="_blank" rel="noopener noreferrer"
                      style={{ fontSize: 11, color: T.accent, textDecoration: "none" }}>
                      Vorschau ↗
                    </a>
                  </div>
                  <button
                    type="button"
                    onClick={() => setForm(f => ({ ...f, attachment_url: "", attachment_filename: "" }))}
                    style={{ background: "none", border: "none", cursor: "pointer", padding: 4, display: "flex", borderRadius: 4 }}
                    title="Anhang entfernen"
                  >
                    <X size={15} style={{ color: T.textDim }} />
                  </button>
                </div>
              ) : (
                /* Upload button */
                <label style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                  padding: "12px 20px", background: T.surfaceAlt,
                  border: `2px dashed ${docUploading ? T.accent : T.border}`,
                  borderRadius: 8, cursor: docUploading ? "wait" : "pointer",
                  color: T.textDim, fontSize: 13, fontWeight: 500,
                  transition: "border-color 0.15s",
                }}>
                  {docUploading ? (
                    <><RefreshCw size={15} style={{ animation: "spin 1s linear infinite" }} /> Wird hochgeladen...</>
                  ) : (
                    <><Upload size={15} /> PDF, DOCX, XLSX hochladen (max. 25 MB)</>
                  )}
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt"
                    style={{ display: "none" }}
                    disabled={docUploading}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setDocUploading(true);
                      setDocUploadError(null);
                      try {
                        const fd = new FormData();
                        fd.append("file", file);
                        const res = await apiFetch("/admin/media/upload-document", { method: "POST", body: fd });
                        if (!res.ok) {
                          const err = await res.json().catch(() => ({}));
                          throw new Error(err.detail || `Upload fehlgeschlagen (${res.status})`);
                        }
                        const data = await res.json();
                        setForm(f => ({
                          ...f,
                          attachment_url: data.url,
                          attachment_filename: file.name,
                        }));
                      } catch (err: unknown) {
                        setDocUploadError(err instanceof Error ? err.message : "Upload fehlgeschlagen");
                      } finally {
                        setDocUploading(false);
                        e.target.value = "";
                      }
                    }}
                  />
                </label>
              )}

              {docUploadError && (
                <p style={{ fontSize: 12, color: "#ef4444", marginTop: 6 }}>⚠ {docUploadError}</p>
              )}
              <p style={{ fontSize: 11, color: T.textDim, marginTop: 4 }}>
                Datei wird auf dem Server gespeichert und als öffentlicher Link geteilt. Kein externer Dienst.
              </p>
            </div>

            {/* Summary */}
            <div style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 14, padding: 20, display: "flex", flexDirection: "column", gap: 0 }}>
              <h4 style={{ fontSize: 14, fontWeight: 800, color: T.text, marginBottom: 12 }}>Zusammenfassung</h4>
              {[
                { label: "Kampagne", value: form.name || "–" },
                { label: "Kanal", value: CHANNELS.find(c => c.key === form.channel)?.label || form.channel },
                { label: "Zielgruppe", value: form.target_type === "all_members" ? "Alle Kontakte" : form.target_type === "segment" ? (segments.find(s => s.id === form.target_segment_id)?.name || "Segment") : form.target_type === "tags" ? (selectedTags.length > 0 ? `Nach Tags (${selectedTags.join(", ")})` : "Nach Tags") : form.target_type === "selected" ? `Manuell (${selectedContactIds.length} Kontakte)` : form.target_type },
                { label: "Versand", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("de-DE") : "Sofort nach Freigabe" },
                { label: "KI-Inhalt", value: form.ai_prompt ? "Ja \u2013 wird nach Erstellung generiert" : "Manuell" },
                { label: "Orchestrierung", value: showOrchestration && orchSteps.length > 1 ? `${orchSteps.length} Schritte (Omnichannel)` : "Einzelversand" },
                { label: "A/B-Test", value: abEnabled ? `${abVariants.length} Varianten, ${abTestPct}% Testanteil, ${abDuration}h` : "Deaktiviert" },
              ].map((item, i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: `1px solid ${T.border}` }}>
                  <span style={{ fontSize: 12, color: T.textDim }}>{item.label}</span>
                  <span style={{ fontSize: 12, color: T.text, fontWeight: 600 }}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: AI Review */}
        {step === 4 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 12, background: aiResult?.qa_passed !== false ? T.successDim : "rgba(255,107,107,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {aiResult?.qa_passed !== false
                  ? <CheckCircle size={20} style={{ color: T.success }} />
                  : <XCircle size={20} style={{ color: T.danger }} />}
              </div>
              <div>
                <h3 style={S.sectionTitle}>KI-Inhalt prüfen</h3>
                <p style={S.sectionDesc}>Der KI-generierte Inhalt steht zur Prüfung bereit.</p>
              </div>
            </div>

            {/* Pipeline Steps */}
            {aiResult?.pipeline_steps && aiResult.pipeline_steps.length > 0 && (
              <div>
                <label style={S.label}>Swarm-Pipeline</label>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  {(aiResult.pipeline_steps as string[]).map((pipelineStep: string, i: number) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ padding: "4px 12px", borderRadius: 20, background: T.accentDim, border: `1px solid rgba(108,92,231,0.3)`, fontSize: 11, fontWeight: 700, color: T.accentLight, textTransform: "uppercase" as const, letterSpacing: "0.04em" }}>
                        {pipelineStep}
                      </span>
                      {i < aiResult.pipeline_steps.length - 1 && (
                        <ArrowRight size={12} style={{ color: T.textDim, flexShrink: 0 }} />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* QA Status */}
            {aiResult?.qa_passed === false && aiResult.qa_issues && aiResult.qa_issues.length > 0 && (
              <div style={{ padding: "14px 16px", background: "rgba(255,107,107,0.1)", border: `1px solid rgba(255,107,107,0.3)`, borderRadius: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <XCircle size={14} style={{ color: T.danger }} />
                  <span style={{ fontSize: 12, fontWeight: 800, color: T.danger }}>QA-Fehler ({aiResult.qa_issues.length})</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {(aiResult.qa_issues as string[]).map((issue: string, i: number) => (
                    <li key={i} style={{ fontSize: 12, color: T.danger, lineHeight: 1.6 }}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {aiResult?.qa_passed === true && (
              <div style={{ padding: "10px 16px", background: T.successDim, border: `1px solid rgba(0,184,148,0.3)`, borderRadius: 10, display: "flex", alignItems: "center", gap: 8 }}>
                <CheckCircle size={14} style={{ color: T.success }} />
                <span style={{ fontSize: 12, fontWeight: 700, color: T.success }}>QA bestanden – alle Qualitätskriterien erfüllt</span>
              </div>
            )}

            {/* QA Suggestions */}
            {aiResult?.qa_suggestions && aiResult.qa_suggestions.length > 0 && (
              <div style={{ padding: "14px 16px", background: "rgba(9,132,227,0.1)", border: `1px solid rgba(9,132,227,0.3)`, borderRadius: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Info size={14} style={{ color: "#0984e3" }} />
                  <span style={{ fontSize: 12, fontWeight: 800, color: "#0984e3" }}>Verbesserungsvorschläge</span>
                </div>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {(aiResult.qa_suggestions as string[]).map((s: string, i: number) => (
                    <li key={i} style={{ fontSize: 12, color: "#74b9ff", lineHeight: 1.6 }}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {aiResult?.content && (
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {aiResult.content.subject && (
                  <div>
                    <label style={S.label}>Betreff</label>
                    <div style={{ padding: "12px 16px", background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 10, color: T.text, fontSize: 14 }}>{aiResult.content.subject}</div>
                  </div>
                )}
                <div>
                  <label style={S.label}>Inhalt</label>
                  {aiResult.content.html ? (
                    <div style={{ border: `1px solid ${T.border}`, borderRadius: 10, overflow: "hidden", background: "#ffffff" }}>
                      <iframe
                        srcDoc={aiResult.content.html}
                        style={{ width: "100%", minHeight: 300, border: "none", display: "block" }}
                        sandbox="allow-same-origin"
                        title="E-Mail Vorschau"
                      />
                    </div>
                  ) : (
                    <div style={{ padding: "12px 16px", background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 10, color: T.text, fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{aiResult.content.body || "–"}</div>
                  )}
                </div>
              </div>
            )}

            {/* Auto-image status card */}
            {autoGenerateImage && autoImageStatus !== 'idle' && (
              <div style={{ padding: "14px 16px", background: T.surfaceAlt, border: `1px solid ${autoImageStatus === 'error' ? "rgba(255,107,107,0.4)" : autoImageStatus === 'done' ? "rgba(0,184,148,0.3)" : T.border}`, borderRadius: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Image size={14} style={{ color: autoImageStatus === 'error' ? T.danger : autoImageStatus === 'done' ? T.success : T.accentLight, flexShrink: 0 }} />
                  <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>KI-Titelbild</span>
                </div>
                {autoImageStatus === 'generating' && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Loader2 size={14} style={{ animation: "spin 1s linear infinite", color: T.accentLight }} />
                    <span style={{ fontSize: 12, color: T.textDim }}>Bild wird generiert…</span>
                  </div>
                )}
                {autoImageStatus === 'done' && autoImageUrl && (
                  <img src={autoImageUrl} alt="Generiertes Bild" style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 8 }} />
                )}
                {autoImageStatus === 'error' && autoImageError && (
                  <span style={{ fontSize: 12, color: T.danger }}>{autoImageError}</span>
                )}
              </div>
            )}


            {previewUrl && (
              <button onClick={() => setShowPreviewModal(true)} style={{ ...S.secondaryBtn, color: T.accentLight }}>
                <Eye size={16} /> Vollständige Vorschau anzeigen
              </button>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={async () => {
                if (createdCampaignId) {
                  try { await apiFetch(`/admin/campaigns/${createdCampaignId}/approve`, { method: "POST" }); } catch { /* ignore */ }
                  try { await apiFetch(`/admin/campaigns/${createdCampaignId}/send`, { method: "POST" }); } catch { /* ignore */ }
                }
                onCreated();
              }} style={{ ...S.successBtn, background: "linear-gradient(135deg, #00b894, #00cec9)" }}>
                <CheckCircle size={16} /> Freigeben &amp; Senden
              </button>
              <button onClick={async () => {
                if (createdCampaignId) {
                  try { await apiFetch(`/admin/campaigns/${createdCampaignId}/approve`, { method: "POST" }); } catch { /* ignore */ }
                }
                onCreated();
              }} style={S.successBtn}><CheckCircle size={16} /> Nur freigeben</button>
              <button onClick={onCreated} style={S.secondaryBtn}>Später prüfen</button>
            </div>
          </div>
        )}

        {/* Error Display */}
        {aiError && (
          <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", background: T.dangerDim, border: `1px solid rgba(255,107,107,0.3)`, borderRadius: 10 }}>
            <AlertCircle size={16} style={{ color: T.danger, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: T.danger }}>{aiError}</span>
          </div>
        )}

        {/* AI Generating Overlay */}
        {aiGenerating && (
          <div style={{ marginTop: 24, display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "32px 0" }}>
            <Loader2 size={32} style={{ color: T.accent, animation: "spin 1s linear infinite" }} />
            <p style={{ fontSize: 13, color: T.textMuted }}>KI generiert Inhalte aus Ihrem Wissensspeicher...</p>
            <p style={{ fontSize: 11, color: T.textDim }}>Dies kann einige Sekunden dauern.</p>
          </div>
        )}

        {/* Navigation */}
        {step < 4 && !aiGenerating && (
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 28, paddingTop: 20, borderTop: `1px solid ${T.border}` }}>
            <button onClick={() => step > 0 ? setStep(step - 1) : onCancel()} style={S.secondaryBtn}>
              <ArrowLeft size={16} /> {step > 0 ? "Zurück" : "Abbrechen"}
            </button>
            {step < 3 ? (
              <button onClick={() => setStep(step + 1)} disabled={!canProceed()} style={{ ...S.primaryBtn, opacity: canProceed() ? 1 : 0.4 }}>
                Weiter <ArrowRight size={16} />
              </button>
            ) : (
              <button onClick={handleCreate} disabled={!form.name.trim() || creating}
                style={{ ...S.primaryBtn, background: `linear-gradient(135deg, ${T.accent}, ${T.accentLight})`, opacity: !form.name.trim() || creating ? 0.4 : 1 }}>
                {creating ? <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> : <Sparkles size={16} />}
                Kampagne erstellen
              </button>
            )}
          </div>
        )}
      </div>

      {/* Spin animation */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Preview Modal */}
      {showPreviewModal && previewUrl && (() => {
        const token = previewUrl.split("/").pop() ?? "";
        return (
          <CampaignPreviewModal
            token={token}
            onClose={() => setShowPreviewModal(false)}
            onApproved={() => { setShowPreviewModal(false); onCreated(); }}
            onRejected={() => setShowPreviewModal(false)}
          />
        );
      })()}

      {/* Media Library Picker Modal */}
      {showMediaPicker && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1100,
          background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center",
        }} onClick={() => setShowMediaPicker(false)}>
          <div style={{
            background: T.surface, border: `1px solid ${T.border}`, borderRadius: 16,
            width: "min(860px, 95vw)", maxHeight: "85vh", display: "flex", flexDirection: "column",
            overflow: "hidden",
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px", borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontWeight: 700, fontSize: 15, color: T.text }}>Mediathek</span>
              <button type="button" onClick={() => setShowMediaPicker(false)} style={{ background: "none", border: "none", color: T.textDim, cursor: "pointer" }}>
                <X size={18} />
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1, padding: 16 }}>
              {mediaPickerLoading ? (
                <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
                  <Loader2 size={28} style={{ animation: "spin 1s linear infinite", color: T.accentLight }} />
                </div>
              ) : mediaPickerAssets.length === 0 ? (
                <p style={{ textAlign: "center", color: T.textDim, padding: 40 }}>Keine Bilder in der Mediathek.</p>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 10 }}>
                  {mediaPickerAssets.map(asset => (
                    <button
                      key={asset.id}
                      type="button"
                      onClick={() => selectMediaAsset(asset)}
                      style={{
                        background: T.surfaceAlt, border: `2px solid ${form.featured_image_url === asset.url ? T.accent : T.border}`,
                        borderRadius: 10, overflow: "hidden", cursor: "pointer", padding: 0, textAlign: "left",
                        transition: "border-color .15s",
                      }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={asset.url}
                        alt={asset.display_name ?? ""}
                        style={{ width: "100%", height: 120, objectFit: "cover", display: "block" }}
                      />
                      <div style={{ padding: "6px 8px" }}>
                        <p style={{ margin: 0, fontSize: 11, color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {asset.display_name || asset.description || "Bild"}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {mediaPickerTotal > 24 && (
              <div style={{ display: "flex", justifyContent: "center", gap: 8, padding: "12px 16px", borderTop: `1px solid ${T.border}` }}>
                <button type="button" disabled={mediaPickerPage <= 1} onClick={() => openMediaPicker(mediaPickerPage - 1)}
                  style={{ ...S.secondaryBtn, opacity: mediaPickerPage <= 1 ? 0.4 : 1 }}>← Zurück</button>
                <span style={{ fontSize: 12, color: T.textDim, alignSelf: "center" }}>
                  Seite {mediaPickerPage} / {Math.ceil(mediaPickerTotal / 24)}
                </span>
                <button type="button" disabled={mediaPickerPage >= Math.ceil(mediaPickerTotal / 24)} onClick={() => openMediaPicker(mediaPickerPage + 1)}
                  style={{ ...S.secondaryBtn, opacity: mediaPickerPage >= Math.ceil(mediaPickerTotal / 24) ? 0.4 : 1 }}>Weiter →</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
