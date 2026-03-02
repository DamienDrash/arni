"use client";
import { useState, useEffect } from "react";
import {
  Sparkles, Mail, MessageSquare, Smartphone, Send, Globe,
  Calendar, Users, Target, Filter, CheckCircle,
  ArrowRight, ArrowLeft, Eye, Loader2, BookOpen,
  AlertCircle, Layers,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";

/* ═══════════════════════════════════════════════════════════════════════════
   Types
   ═══════════════════════════════════════════════════════════════════════ */

interface Template { id: number; name: string; type: string; primary_color: string | null; is_default: boolean; }
interface Segment { id: number; name: string; description: string | null; member_count: number; }
interface ContactSegment { id: number; name: string; description: string | null; contact_count?: number; }
interface WizardProps { onCreated: () => void; onCancel: () => void; }

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

  const [form, setForm] = useState({
    name: "", description: "", type: "broadcast", channel: "email",
    target_type: "all_members", target_segment_id: null as number | null,
    template_id: null as number | null, ai_prompt: "", tone: "professional",
    use_knowledge: true, use_chat_history: false,
    content_subject: "", content_body: "", scheduled_at: "",
  });

  /* ─── Load Data ──────────────────────────────────────────────────────── */

  useEffect(() => {
    const load = async () => {
      try {
        const [tplRes, segRes, csRes] = await Promise.all([
          apiFetch("/admin/campaigns/templates"), apiFetch("/admin/campaigns/segments"),
          apiFetch("/v2/admin/contacts/segments").catch(() => null),
        ]);
        if (tplRes.ok) setTemplates(await tplRes.json());
        if (segRes.ok) setSegments(await segRes.json());
        if (csRes?.ok) setContactSegments(await csRes.json());
      } catch { /* ignore */ }
    };
    load();
  }, []);

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
          target_filter_json: form.target_segment_id ? JSON.stringify({ segment_id: form.target_segment_id }) : undefined,
        }),
      });
      if (!res.ok) { setAiError("Kampagne konnte nicht erstellt werden."); setCreating(false); return; }
      const created = await res.json();

      if (form.ai_prompt.trim()) {
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

            {/* Summary */}
            <div style={{ background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 14, padding: 20, display: "flex", flexDirection: "column", gap: 0 }}>
              <h4 style={{ fontSize: 14, fontWeight: 800, color: T.text, marginBottom: 12 }}>Zusammenfassung</h4>
              {[
                { label: "Kampagne", value: form.name || "–" },
                { label: "Kanal", value: CHANNELS.find(c => c.key === form.channel)?.label || form.channel },
                { label: "Zielgruppe", value: form.target_type === "all_members" ? "Alle Kontakte" : form.target_type === "segment" ? "Segment" : form.target_type },
                { label: "Versand", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("de-DE") : "Sofort nach Freigabe" },
                { label: "KI-Inhalt", value: form.ai_prompt ? "Ja – wird nach Erstellung generiert" : "Manuell" },
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
              <div style={{ width: 40, height: 40, borderRadius: 12, background: T.successDim, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <CheckCircle size={20} style={{ color: T.success }} />
              </div>
              <div>
                <h3 style={S.sectionTitle}>KI-Inhalt prüfen</h3>
                <p style={S.sectionDesc}>Der KI-generierte Inhalt steht zur Prüfung bereit.</p>
              </div>
            </div>

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
                  <div style={{ padding: "12px 16px", background: T.surfaceAlt, border: `1px solid ${T.border}`, borderRadius: 10, color: T.text, fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{aiResult.content.body || aiResult.content.html || "–"}</div>
                </div>
              </div>
            )}

            {previewUrl && (
              <a href={previewUrl} target="_blank" rel="noopener noreferrer" style={{ ...S.secondaryBtn, color: T.accentLight, textDecoration: "none", display: "inline-flex", width: "fit-content" }}>
                <Eye size={16} /> Vollständige Vorschau öffnen
              </a>
            )}

            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={async () => {
                if (aiResult?.content) { try { const campaigns = await apiFetch("/admin/campaigns"); if (campaigns.ok) { const data = await campaigns.json(); const latest = data.items?.[0]; if (latest) await apiFetch(`/admin/campaigns/${latest.id}/approve`, { method: "POST" }); } } catch { /* ignore */ } }
                onCreated();
              }} style={S.successBtn}><CheckCircle size={16} /> Freigeben</button>
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
    </div>
  );
}
