"use client";
import { useState, useCallback, useEffect } from "react";
import {
  Sparkles, Mail, MessageSquare, Smartphone, Send, Globe,
  Megaphone, Calendar, Users, Target, Filter, CheckCircle,
  ArrowRight, ArrowLeft, Clock, Eye, Loader2, BookOpen,
  AlertCircle, Layers,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface Template {
  id: number;
  name: string;
  type: string;
  primary_color: string | null;
  is_default: boolean;
}

interface Segment {
  id: number;
  name: string;
  description: string | null;
  member_count: number;
}

interface ContactSegment {
  id: number;
  name: string;
  description: string | null;
  contact_count?: number;
}

interface WizardProps {
  onCreated: () => void;
  onCancel: () => void;
}

/* ─── Constants ─────────────────────────────────────────────────────────── */

const CHANNELS = [
  { key: "email", label: "E-Mail", icon: Mail, color: "#3B82F6" },
  { key: "whatsapp", label: "WhatsApp", icon: MessageSquare, color: "#25D366" },
  { key: "sms", label: "SMS", icon: Smartphone, color: "#F59E0B" },
  { key: "telegram", label: "Telegram", icon: Send, color: "#0EA5E9" },
  { key: "multi", label: "Multi-Kanal", icon: Globe, color: "#8B5CF6" },
];

const TONES = [
  { key: "professional", label: "Professionell", desc: "Seriös und geschäftlich" },
  { key: "casual", label: "Locker", desc: "Freundlich und nahbar" },
  { key: "motivational", label: "Motivierend", desc: "Energiegeladen und inspirierend" },
  { key: "urgent", label: "Dringend", desc: "Handlungsorientiert und zeitkritisch" },
];

/* ─── Component ─────────────────────────────────────────────────────────── */

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
    name: "",
    description: "",
    type: "broadcast",
    channel: "email",
    target_type: "all_members",
    target_segment_id: null as number | null,
    template_id: null as number | null,
    ai_prompt: "",
    tone: "professional",
    use_knowledge: true,
    use_chat_history: false,
    content_subject: "",
    content_body: "",
    scheduled_at: "",
  });

  /* ─── Load Data ───────────────────────────────────────────────────────── */

  useEffect(() => {
    const load = async () => {
      try {
        const [tplRes, segRes, csRes] = await Promise.all([
          apiFetch("/admin/campaigns/templates"),
          apiFetch("/admin/campaigns/segments"),
          apiFetch("/v2/admin/contacts/segments").catch(() => null),
        ]);
        if (tplRes.ok) setTemplates(await tplRes.json());
        if (segRes.ok) setSegments(await segRes.json());
        if (csRes?.ok) setContactSegments(await csRes.json());
      } catch { /* ignore */ }
    };
    load();
  }, []);

  /* ─── Actions ─────────────────────────────────────────────────────────── */

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    setAiError(null);
    try {
      // Step 1: Create campaign
      const res = await apiFetch("/admin/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description,
          type: form.type,
          channel: form.channel,
          target_type: form.target_type,
          template_id: form.template_id || undefined,
          content_subject: form.content_subject || undefined,
          content_body: form.content_body || undefined,
          ai_prompt: form.ai_prompt || undefined,
          scheduled_at: form.scheduled_at || undefined,
          target_filter_json: form.target_segment_id
            ? JSON.stringify({ segment_id: form.target_segment_id })
            : undefined,
        }),
      });

      if (!res.ok) {
        setAiError("Kampagne konnte nicht erstellt werden.");
        setCreating(false);
        return;
      }

      const created = await res.json();

      // Step 2: If AI prompt provided, generate content
      if (form.ai_prompt.trim()) {
        setAiGenerating(true);
        try {
          const aiRes = await apiFetch("/admin/campaigns/ai-generate", {
            method: "POST",
            body: JSON.stringify({
              campaign_id: created.id,
              prompt: form.ai_prompt,
              use_knowledge: form.use_knowledge,
              use_chat_history: form.use_chat_history,
              tone: form.tone,
            }),
          });
          if (aiRes.ok) {
            const data = await aiRes.json();
            setAiResult(data);
            if (data.preview_url) setPreviewUrl(data.preview_url);
            // Move to review step
            setStep(4);
          } else {
            setAiError("KI-Generierung fehlgeschlagen. Sie können den Inhalt manuell bearbeiten.");
          }
        } catch (e) {
          setAiError("KI-Generierung fehlgeschlagen.");
        }
        setAiGenerating(false);
      } else {
        onCreated();
      }
    } catch (e) {
      setAiError("Ein Fehler ist aufgetreten.");
    }
    setCreating(false);
  };

  /* ─── Steps ───────────────────────────────────────────────────────────── */

  const steps = [
    { title: "Grundlagen", desc: "Name und Kanal" },
    { title: "KI-Prompt", desc: "Inhalt beschreiben" },
    { title: "Zielgruppe", desc: "Empfänger wählen" },
    { title: "Planung", desc: "Zeitpunkt & Vorlage" },
    { title: "Prüfung", desc: "KI-Ergebnis prüfen" },
  ];

  const canProceed = () => {
    if (step === 0) return !!form.name.trim();
    if (step === 1) return true; // Prompt is optional
    return true;
  };

  /* ─── Render ──────────────────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      {/* Progress Bar */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
        <div className="flex items-center justify-between">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center gap-3 flex-1">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 transition-all ${
                i < step ? "bg-green-500 text-white" :
                i === step ? "bg-purple-600 text-white ring-2 ring-purple-400" :
                "bg-zinc-800 text-zinc-500"
              }`}>
                {i < step ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <div className="hidden sm:block">
                <p className={`text-xs font-semibold ${i <= step ? "text-white" : "text-zinc-500"}`}>{s.title}</p>
                <p className="text-[10px] text-zinc-600">{s.desc}</p>
              </div>
              {i < steps.length - 1 && (
                <div className={`flex-1 h-0.5 mx-3 rounded ${i < step ? "bg-green-500" : "bg-zinc-800"}`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step Content */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8">

        {/* Step 0: Basics */}
        {step === 0 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-white">Kampagnen-Grundlagen</h3>
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Kampagnenname *</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="z.B. Newsletter März 2026"
                className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Beschreibung</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Kurze Beschreibung..."
                rows={2}
                className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Kanal *</label>
              <div className="grid grid-cols-5 gap-3">
                {CHANNELS.map((ch) => {
                  const Icon = ch.icon;
                  const selected = form.channel === ch.key;
                  return (
                    <button
                      key={ch.key}
                      onClick={() => setForm({ ...form, channel: ch.key })}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                        selected
                          ? "border-purple-500 bg-purple-500/10"
                          : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                      }`}
                    >
                      <Icon className="w-5 h-5" style={{ color: selected ? ch.color : "#71717a" }} />
                      <span className={`text-xs font-semibold ${selected ? "text-white" : "text-zinc-500"}`}>{ch.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Step 1: AI Prompt */}
        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-bold text-white mb-1">KI-Inhaltsgenerierung</h3>
              <p className="text-sm text-zinc-400">
                Beschreiben Sie, was die Kampagne beinhalten soll. Die KI nutzt Ihren Wissensspeicher, um faktenbasierte Inhalte zu erstellen.
              </p>
            </div>

            <div className="bg-gradient-to-br from-purple-500/10 to-zinc-900 border border-purple-500/30 rounded-xl p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <span className="text-sm font-bold text-white">KI-Prompt</span>
                <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 text-[10px] font-bold rounded-full uppercase">Empfohlen</span>
              </div>
              <textarea
                value={form.ai_prompt}
                onChange={(e) => setForm({ ...form, ai_prompt: e.target.value })}
                placeholder="z.B. Erstelle einen Newsletter über unsere neuen Kursangebote im März. Erwähne die Preise aus unserer aktuellen Preisliste und füge einen Call-to-Action für eine kostenlose Probestunde hinzu."
                rows={5}
                className="w-full px-4 py-3 bg-zinc-800/80 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
              />

              {/* Tone Selection */}
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">Tonalität</label>
                <div className="grid grid-cols-4 gap-2">
                  {TONES.map((t) => (
                    <button
                      key={t.key}
                      onClick={() => setForm({ ...form, tone: t.key })}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        form.tone === t.key
                          ? "border-purple-500 bg-purple-500/10"
                          : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                      }`}
                    >
                      <p className={`text-xs font-semibold ${form.tone === t.key ? "text-white" : "text-zinc-400"}`}>{t.label}</p>
                      <p className="text-[10px] text-zinc-600">{t.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Knowledge Toggle */}
              <div className="flex items-center gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.use_knowledge}
                    onChange={(e) => setForm({ ...form, use_knowledge: e.target.checked })}
                    className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-purple-600 focus:ring-purple-500"
                  />
                  <BookOpen className="w-3.5 h-3.5 text-zinc-400" />
                  <span className="text-xs text-zinc-300">Wissensspeicher nutzen</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.use_chat_history}
                    onChange={(e) => setForm({ ...form, use_chat_history: e.target.checked })}
                    className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-purple-600 focus:ring-purple-500"
                  />
                  <MessageSquare className="w-3.5 h-3.5 text-zinc-400" />
                  <span className="text-xs text-zinc-300">Chat-Kontext einbeziehen</span>
                </label>
              </div>
            </div>

            {/* Manual Fallback */}
            <div className="border-t border-zinc-800 pt-6">
              <p className="text-xs text-zinc-500 mb-3">Oder manuell eingeben:</p>
              {form.channel === "email" && (
                <div className="mb-3">
                  <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Betreff</label>
                  <input
                    type="text"
                    value={form.content_subject}
                    onChange={(e) => setForm({ ...form, content_subject: e.target.value })}
                    placeholder="E-Mail Betreff..."
                    className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Nachricht</label>
                <textarea
                  value={form.content_body}
                  onChange={(e) => setForm({ ...form, content_body: e.target.value })}
                  placeholder="Ihre Nachricht..."
                  rows={4}
                  className="w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none font-mono text-sm"
                />
                <div className="flex gap-2 mt-2">
                  {["{{ contact.first_name }}", "{{ contact.last_name }}", "{{ contact.company }}"].map((v) => (
                    <button
                      key={v}
                      onClick={() => setForm({ ...form, content_body: form.content_body + v })}
                      className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-[10px] text-purple-400 font-mono hover:bg-zinc-700 transition-colors"
                    >
                      {v}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Targeting */}
        {step === 2 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-white">Zielgruppe auswählen</h3>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: "all_members", label: "Alle Kontakte", desc: "An alle aktiven Kontakte senden", icon: Users },
                { key: "segment", label: "Segment", desc: "Vordefiniertes Segment verwenden", icon: Target },
                { key: "tags", label: "Nach Tags", desc: "Kontakte nach Tags filtern", icon: Filter },
                { key: "selected", label: "Manuell", desc: "Einzelne Kontakte auswählen", icon: CheckCircle },
              ].map((t) => {
                const Icon = t.icon;
                const selected = form.target_type === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => setForm({ ...form, target_type: t.key })}
                    className={`flex items-center gap-3 p-5 rounded-xl border-2 text-left transition-all ${
                      selected
                        ? "border-purple-500 bg-purple-500/10"
                        : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                    }`}
                  >
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      selected ? "bg-purple-500/20" : "bg-zinc-900"
                    }`}>
                      <Icon className="w-5 h-5" style={{ color: selected ? "#a78bfa" : "#71717a" }} />
                    </div>
                    <div>
                      <p className={`text-sm font-semibold ${selected ? "text-white" : "text-zinc-400"}`}>{t.label}</p>
                      <p className="text-[11px] text-zinc-600">{t.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Segment Picker */}
            {form.target_type === "segment" && (
              <div className="space-y-3">
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider">Segment auswählen</label>
                {[...segments.map(s => ({ ...s, source: "legacy" })), ...contactSegments.map(s => ({ ...s, member_count: s.contact_count || 0, source: "v2" }))].map((seg: any) => (
                  <button
                    key={`${seg.source}-${seg.id}`}
                    onClick={() => setForm({ ...form, target_segment_id: seg.id })}
                    className={`w-full flex items-center justify-between p-4 rounded-lg border transition-all text-left ${
                      form.target_segment_id === seg.id
                        ? "border-purple-500 bg-purple-500/10"
                        : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                    }`}
                  >
                    <div>
                      <span className="text-sm font-semibold text-white">{seg.name}</span>
                      {seg.description && <p className="text-xs text-zinc-500 mt-0.5">{seg.description}</p>}
                    </div>
                    <span className="text-xs font-bold text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded-full">
                      {seg.member_count} Kontakte
                    </span>
                  </button>
                ))}
                {segments.length === 0 && contactSegments.length === 0 && (
                  <p className="text-sm text-zinc-500 py-4 text-center">Keine Segmente vorhanden. Erstellen Sie zuerst ein Segment im Kontakte-Modul.</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Scheduling & Template */}
        {step === 3 && (
          <div className="space-y-6">
            <h3 className="text-lg font-bold text-white">Planung & Vorlage</h3>

            {/* Send Time */}
            <div>
              <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">Versandzeitpunkt</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => setForm({ ...form, scheduled_at: "" })}
                  className={`flex items-center gap-3 p-5 rounded-xl border-2 text-left transition-all ${
                    !form.scheduled_at
                      ? "border-purple-500 bg-purple-500/10"
                      : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                  }`}
                >
                  <Send className="w-5 h-5" style={{ color: !form.scheduled_at ? "#a78bfa" : "#71717a" }} />
                  <div>
                    <p className="text-sm font-semibold text-white">Sofort senden</p>
                    <p className="text-[11px] text-zinc-600">Nach Freigabe direkt versenden</p>
                  </div>
                </button>
                <button
                  onClick={() => setForm({ ...form, scheduled_at: new Date(Date.now() + 86400000).toISOString().slice(0, 16) })}
                  className={`flex items-center gap-3 p-5 rounded-xl border-2 text-left transition-all ${
                    form.scheduled_at
                      ? "border-purple-500 bg-purple-500/10"
                      : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                  }`}
                >
                  <Calendar className="w-5 h-5" style={{ color: form.scheduled_at ? "#a78bfa" : "#71717a" }} />
                  <div>
                    <p className="text-sm font-semibold text-white">Zeitpunkt planen</p>
                    <p className="text-[11px] text-zinc-600">Datum und Uhrzeit festlegen</p>
                  </div>
                </button>
              </div>
              {form.scheduled_at && (
                <input
                  type="datetime-local"
                  value={form.scheduled_at}
                  onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
                  className="mt-3 w-full px-4 py-2.5 bg-zinc-800 border border-zinc-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              )}
            </div>

            {/* Template Selection */}
            {form.channel === "email" && templates.length > 0 && (
              <div>
                <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                  <Layers className="w-3.5 h-3.5 inline mr-1" />
                  E-Mail-Vorlage
                </label>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    onClick={() => setForm({ ...form, template_id: null })}
                    className={`p-4 rounded-lg border-2 text-center transition-all ${
                      !form.template_id
                        ? "border-purple-500 bg-purple-500/10"
                        : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                    }`}
                  >
                    <p className="text-xs font-semibold text-zinc-400">Keine Vorlage</p>
                  </button>
                  {templates.filter(t => t.type === "email").map((tpl) => (
                    <button
                      key={tpl.id}
                      onClick={() => setForm({ ...form, template_id: tpl.id })}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        form.template_id === tpl.id
                          ? "border-purple-500 bg-purple-500/10"
                          : "border-zinc-700 bg-zinc-800 hover:border-zinc-600"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-3 h-3 rounded-full" style={{ background: tpl.primary_color || "#6C5CE7" }} />
                        <span className="text-xs font-semibold text-white truncate">{tpl.name}</span>
                      </div>
                      {tpl.is_default && (
                        <span className="text-[10px] text-yellow-400">★ Standard</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-5 space-y-3">
              <h4 className="text-sm font-bold text-white">Zusammenfassung</h4>
              {[
                { label: "Kampagne", value: form.name || "–" },
                { label: "Kanal", value: CHANNELS.find(c => c.key === form.channel)?.label || form.channel },
                { label: "Zielgruppe", value: form.target_type === "all_members" ? "Alle Kontakte" : form.target_type === "segment" ? "Segment" : form.target_type },
                { label: "Versand", value: form.scheduled_at ? new Date(form.scheduled_at).toLocaleString("de-DE") : "Sofort nach Freigabe" },
                { label: "KI-Inhalt", value: form.ai_prompt ? "Ja – wird nach Erstellung generiert" : "Manuell" },
              ].map((item, i) => (
                <div key={i} className="flex justify-between py-1.5 border-b border-zinc-700/50 last:border-0">
                  <span className="text-xs text-zinc-500">{item.label}</span>
                  <span className="text-xs text-white font-medium">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 4: AI Review */}
        {step === 4 && (
          <div className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/10 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">KI-Inhalt prüfen</h3>
                <p className="text-sm text-zinc-400">Der KI-generierte Inhalt steht zur Prüfung bereit.</p>
              </div>
            </div>

            {aiResult?.content && (
              <div className="space-y-4">
                {aiResult.content.subject && (
                  <div>
                    <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Betreff</label>
                    <div className="px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white">
                      {aiResult.content.subject}
                    </div>
                  </div>
                )}
                <div>
                  <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-1">Inhalt</label>
                  <div className="px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm leading-relaxed whitespace-pre-wrap">
                    {aiResult.content.body || aiResult.content.html || "–"}
                  </div>
                </div>
              </div>
            )}

            {previewUrl && (
              <a
                href={previewUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-purple-400 hover:bg-zinc-700 transition-colors"
              >
                <Eye className="w-4 h-4" /> Vollständige Vorschau öffnen
              </a>
            )}

            <div className="flex gap-3">
              <button
                onClick={async () => {
                  // Approve the campaign
                  if (aiResult?.content) {
                    try {
                      const campaigns = await apiFetch("/admin/campaigns");
                      if (campaigns.ok) {
                        const data = await campaigns.json();
                        const latest = data.items?.[0];
                        if (latest) {
                          await apiFetch(`/admin/campaigns/${latest.id}/approve`, { method: "POST" });
                        }
                      }
                    } catch { /* ignore */ }
                  }
                  onCreated();
                }}
                className="flex items-center gap-2 px-6 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-colors"
              >
                <CheckCircle className="w-4 h-4" /> Freigeben
              </button>
              <button
                onClick={onCreated}
                className="flex items-center gap-2 px-6 py-2.5 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg font-medium transition-colors"
              >
                Später prüfen
              </button>
            </div>
          </div>
        )}

        {/* Error Display */}
        {aiError && (
          <div className="mt-4 flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span className="text-sm text-red-300">{aiError}</span>
          </div>
        )}

        {/* AI Generating Overlay */}
        {aiGenerating && (
          <div className="mt-6 flex flex-col items-center gap-3 py-8">
            <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
            <p className="text-sm text-zinc-400">KI generiert Inhalte aus Ihrem Wissensspeicher...</p>
            <p className="text-xs text-zinc-600">Dies kann einige Sekunden dauern.</p>
          </div>
        )}

        {/* Navigation */}
        {step < 4 && !aiGenerating && (
          <div className="flex justify-between mt-8 pt-6 border-t border-zinc-800">
            <button
              onClick={() => step > 0 ? setStep(step - 1) : onCancel()}
              className="flex items-center gap-2 px-5 py-2.5 bg-zinc-800 text-zinc-400 border border-zinc-700 rounded-lg hover:bg-zinc-700 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              {step > 0 ? "Zurück" : "Abbrechen"}
            </button>
            {step < 3 ? (
              <button
                onClick={() => setStep(step + 1)}
                disabled={!canProceed()}
                className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white rounded-lg font-semibold transition-colors"
              >
                Weiter <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleCreate}
                disabled={!form.name.trim() || creating}
                className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-700 hover:to-purple-600 disabled:opacity-40 text-white rounded-lg font-bold transition-all"
              >
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Kampagne erstellen
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
