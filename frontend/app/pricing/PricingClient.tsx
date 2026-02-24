"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { motion, useInView, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { useI18n } from "@/lib/i18n/LanguageContext";
import {
  CheckCircle2, ArrowRight, Sparkles, Zap, MessageSquare, Crown,
  Headphones, Eye, Plug, Users, BarChart3, Palette, HelpCircle,
  ChevronRight, Brain, Shield, Server, Key, Cpu, Link2, UserPlus,
  X, Check, Minus
} from "lucide-react";

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function Section({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.section ref={ref} initial={{ opacity: 0, y: 50 }} animate={isInView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }} className={className}>
      {children}
    </motion.section>
  );
}

const c = {
  bg: "oklch(0.09 0.04 270)",
  card: "oklch(0.12 0.04 270)",
  cardHi: "oklch(0.13 0.04 270)",
  border: "oklch(0.22 0.04 270)",
  accent: "oklch(0.62 0.22 292)",
  accentSoft: "oklch(0.62 0.22 292 / 0.12)",
  gold: "oklch(0.8 0.16 85)",
  green: "oklch(0.72 0.19 155)",
  text: "oklch(0.97 0.005 270)",
  textSub: "oklch(0.75 0.01 270)",
  textMuted: "oklch(0.6 0.015 270)",
  textDim: "oklch(0.65 0.015 270)",
};

/* ── Component ───────────────────────────────────────────────────────────── */

export default function PricingClient() {
  const { t } = useI18n();
  const [yearly, setYearly] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [showComparison, setShowComparison] = useState(false);

  /* ── Plan Data ──────────────────────────────────────────────────────── */

  const plans = [
    {
      slug: "starter",
      name: "Starter",
      desc: "Ideal für Personal Trainer und kleine Studios mit einem Kommunikationskanal.",
      priceMonthly: 79,
      priceYearly: 63,
      highlight: false,
      badge: null,
      features: [
        "1 Kommunikationskanal (WhatsApp)",
        "500 Konversationen/Monat",
        "Bis zu 500 Mitglieder",
        "1 User",
        "Basic AI (GPT-4.1 Nano)",
        "100.000 LLM-Tokens/Monat",
        "Manuelle Kundenpflege + API",
        "E-Mail Support",
      ],
    },
    {
      slug: "professional",
      name: "Professional",
      desc: "Für wachsende Studios mit Multi-Channel-Kommunikation und erweiterten KI-Funktionen.",
      priceMonthly: 199,
      priceYearly: 159,
      highlight: true,
      badge: "Beliebtester Plan",
      features: [
        "3 Kanäle frei wählbar",
        "2.000 Konversationen/Monat",
        "Unbegrenzte Mitglieder",
        "5 Users",
        "Standard AI (GPT-4.1 Mini)",
        "500.000 LLM-Tokens/Monat",
        "1 Connector frei wählbar",
        "Member Memory Analyzer",
        "Custom Prompts & Analytics+",
        "Branding & Audit Log",
        "API Access",
        "Priority E-Mail Support",
      ],
    },
    {
      slug: "business",
      name: "Business",
      desc: "Für Multi-Location-Studios und Ketten mit allen Kanälen und Premium-KI.",
      priceMonthly: 399,
      priceYearly: 319,
      highlight: false,
      badge: null,
      features: [
        "Alle Kanäle inklusive",
        "10.000 Konversationen/Monat",
        "Unbegrenzte Mitglieder",
        "15 Users",
        "Premium AI (GPT-4.1 + Gemini)",
        "2.000.000 LLM-Tokens/Monat",
        "Alle Connectors inklusive",
        "Churn Prediction (ML)",
        "Automation Engine",
        "Vision AI",
        "Priority Support",
        "Alle Professional-Features",
      ],
    },
  ];

  /* ── Add-on Data ────────────────────────────────────────────────────── */

  const addons = [
    { icon: BarChart3, name: "Churn Prediction", price: "49", desc: "ML-basierte Abwanderungsprognose mit Frühwarnsystem und Handlungsempfehlungen.", color: c.gold, min: "Business" },
    { icon: Headphones, name: "Voice Pipeline", price: "79", desc: "Whisper STT + ElevenLabs TTS für telefonische KI-Gespräche.", color: c.accent, min: "Business" },
    { icon: Eye, name: "Vision AI", price: "39", desc: "YOLOv8-basierte Bildanalyse für Equipment-Erkennung und Übungskorrektur.", color: "oklch(0.68 0.18 25)", min: "Business" },
    { icon: MessageSquare, name: "Zusätzlicher Kanal", price: "29", desc: "Einen weiteren Kommunikationskanal zu deinem Plan hinzufügen.", color: c.accent, min: "Starter" },
    { icon: Zap, name: "Extra Konversationen", price: "19", desc: "+1.000 Konversationen/Monat über dein Plan-Limit hinaus.", color: c.green, min: "Starter" },
    { icon: UserPlus, name: "Zusätzlicher User", price: "15", desc: "Einen weiteren Team-Mitarbeiter hinzufügen.", color: "oklch(0.65 0.18 200)", min: "Starter" },
    { icon: Palette, name: "White-Label", price: "149", desc: "Eigenes Branding, Custom Domain und vollständige Markenanpassung.", color: c.gold, min: "Business" },
    { icon: Key, name: "API Access", price: "99", desc: "REST API + Webhooks für externe System-Integration.", color: "oklch(0.68 0.18 25)", min: "Professional" },
    { icon: Link2, name: "Extra Connector", price: "49", desc: "Einen weiteren Mitglieder-Connector (Magicline, Shopify, WooCommerce, HubSpot).", color: c.accent, min: "Professional" },
  ];

  /* ── Comparison Table Data ──────────────────────────────────────────── */

  type CellValue = boolean | string;
  const comparisonRows: { category: string; rows: { label: string; values: CellValue[] }[] }[] = [
    {
      category: "Kommunikation",
      rows: [
        { label: "WhatsApp", values: [true, true, true, true] },
        { label: "Telegram", values: [false, true, true, true] },
        { label: "E-Mail", values: [false, true, true, true] },
        { label: "SMS (Twilio)", values: [false, true, true, true] },
        { label: "Instagram DM", values: [false, true, true, true] },
        { label: "Facebook Messenger", values: [false, true, true, true] },
        { label: "Voice Pipeline", values: [false, false, true, true] },
        { label: "Google Business", values: [false, false, true, true] },
        { label: "Max. Kanäle", values: ["1", "3", "Alle", "Alle"] },
      ],
    },
    {
      category: "KI & Modelle",
      rows: [
        { label: "AI Tier", values: ["Basic", "Standard", "Premium", "Unlimited"] },
        { label: "GPT-4.1 Nano", values: [true, true, true, true] },
        { label: "GPT-4.1 Mini", values: [false, true, true, true] },
        { label: "GPT-4.1", values: [false, false, true, true] },
        { label: "Gemini 2.5 Flash", values: [false, false, true, true] },
        { label: "Eigene API-Keys", values: [false, false, false, true] },
        { label: "LLM-Tokens/Monat", values: ["100K", "500K", "2M", "Unbegrenzt"] },
      ],
    },
    {
      category: "Mitglieder & Connectors",
      rows: [
        { label: "Max. Mitglieder", values: ["500", "Unbegrenzt", "Unbegrenzt", "Unbegrenzt"] },
        { label: "Manuelle Pflege + API", values: [true, true, true, true] },
        { label: "CSV Import/Export", values: [true, true, true, true] },
        { label: "Magicline", values: [false, "1 wählbar", true, true] },
        { label: "Shopify", values: [false, "1 wählbar", true, true] },
        { label: "WooCommerce", values: [false, "1 wählbar", true, true] },
        { label: "HubSpot", values: [false, "1 wählbar", true, true] },
      ],
    },
    {
      category: "Features",
      rows: [
        { label: "Konversationen/Monat", values: ["500", "2.000", "10.000", "Unbegrenzt"] },
        { label: "Users", values: ["1", "5", "15", "Unbegrenzt"] },
        { label: "Member Memory", values: [false, true, true, true] },
        { label: "Custom Prompts", values: [false, true, true, true] },
        { label: "Analytics+", values: [false, true, true, true] },
        { label: "Branding", values: [false, true, true, true] },
        { label: "Audit Log", values: [false, true, true, true] },
        { label: "Automation Engine", values: [false, false, true, true] },
        { label: "Churn Prediction", values: [false, false, true, true] },
        { label: "Vision AI", values: [false, false, true, true] },
        { label: "White-Label", values: [false, false, false, true] },
        { label: "SLA-Garantie", values: [false, false, false, true] },
        { label: "On-Premise Option", values: [false, false, false, true] },
      ],
    },
    {
      category: "Support",
      rows: [
        { label: "E-Mail Support", values: [true, true, true, true] },
        { label: "Priority Support", values: [false, false, true, true] },
        { label: "Dedicated CSM", values: [false, false, false, true] },
      ],
    },
  ];

  const planHeaders = ["Starter", "Professional", "Business", "Enterprise"];

  /* ── FAQ Data ───────────────────────────────────────────────────────── */

  const defaultFaqs = [
    { q: "Kann ich den Plan jederzeit wechseln?", a: "Ja, du kannst jederzeit upgraden oder downgraden. Bei Upgrades wird sofort anteilig abgerechnet, bei Downgrades wird das Guthaben auf die nächste Rechnung angerechnet." },
    { q: "Was passiert wenn ich mein Konversations-Limit überschreite?", a: "Dein Service wird nicht unterbrochen. Überschreitungen werden mit 0,05€ pro zusätzlicher Konversation abgerechnet (Overage). Du erhältst eine Warnung bei 80% Auslastung." },
    { q: "Gibt es eine kostenlose Testphase?", a: "Ja, alle Pläne können 14 Tage kostenlos getestet werden. Keine Kreditkarte erforderlich für den Start." },
    { q: "Was ist der Unterschied zwischen den AI-Tiers?", a: "Basic nutzt GPT-4.1 Nano (schnell, kostengünstig), Standard nutzt GPT-4.1 Mini (ausgewogen), Premium nutzt GPT-4.1 und Gemini 2.5 Flash (höchste Qualität). Enterprise kann zusätzlich eigene API-Keys einsetzen." },
    { q: "Wie funktionieren die Connectors?", a: "Connectors synchronisieren automatisch Kundendaten von externen Plattformen (Magicline, Shopify, WooCommerce, HubSpot). Im Starter-Plan pflegst du Kunden manuell oder per API/CSV. Ab Professional ist ein Connector frei wählbar." },
    { q: "Kann ich Add-ons jederzeit hinzufügen oder kündigen?", a: "Ja, Add-ons werden monatlich abgerechnet und können jederzeit über das Billing-Dashboard hinzugefügt oder gekündigt werden." },
    { q: "Was bedeutet jährliche Abrechnung?", a: "Bei jährlicher Abrechnung sparst du 20% gegenüber der monatlichen Zahlung. Der Betrag wird einmal jährlich im Voraus abgerechnet." },
  ];

  const faqs = (() => {
    try {
      const translated = t("pricing.faqs");
      return Array.isArray(translated) ? translated : defaultFaqs;
    } catch {
      return defaultFaqs;
    }
  })();

  /* ── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="min-h-screen" style={{ background: c.bg }}>
      <Navbar />

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="pt-28 pb-12 lg:pt-36 lg:pb-16 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-20" style={{ backgroundImage: `radial-gradient(${c.accent}26 1px, transparent 1px)`, backgroundSize: "40px 40px" }} />
        <div className="container mx-auto px-4 text-center relative z-10">
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: c.accent }}>Pricing</motion.span>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6" style={{ color: c.text }}>
            Transparente Preise, <span style={{ color: c.accent }}>maximaler Wert</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }} className="text-lg max-w-2xl mx-auto mb-10" style={{ color: c.textSub }}>
            Von Personal Trainern bis zu Multi-Location-Ketten — wähle den Plan der zu deinem Business passt. 14 Tage kostenlos testen.
          </motion.p>

          {/* Toggle */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} className="flex items-center justify-center gap-4 mb-14">
            <span className="text-sm font-medium" style={{ color: yearly ? c.textMuted : c.text }}>Monatlich</span>
            <button onClick={() => setYearly(!yearly)} className="relative w-14 h-7 rounded-full transition-colors duration-300" style={{ background: yearly ? c.accent : "oklch(0.38 0.04 270)", border: `1px solid oklch(0.45 0.04 270)` }}>
              <div className="absolute top-1 w-5 h-5 rounded-full transition-transform duration-300" style={{ background: c.text, transform: yearly ? "translateX(32px)" : "translateX(4px)" }} />
            </button>
            <span className="text-sm font-medium" style={{ color: yearly ? c.text : c.textMuted }}>
              Jährlich <span className="text-xs px-2 py-0.5 rounded-full ml-1" style={{ background: c.accentSoft, color: c.accent }}>-20%</span>
            </span>
          </motion.div>
        </div>
      </section>

      {/* ── Plans ─────────────────────────────────────────────────────── */}
      <Section className="pb-20">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <motion.div key={plan.slug} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.1 }}
                className="relative rounded-2xl p-7 lg:p-8 flex flex-col group hover:scale-[1.02] transition-all duration-300"
                style={{ background: plan.highlight ? c.cardHi : c.card, border: `1px solid ${plan.highlight ? c.accent + "59" : c.border}`, boxShadow: plan.highlight ? `0 0 50px ${c.accent}14` : "none" }}>
                {plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-bold" style={{ background: c.accent, color: "white" }}>
                    <Sparkles size={12} /> {plan.badge}
                  </div>
                )}
                <h3 className="text-xl font-bold mb-1" style={{ color: c.text }}>{plan.name}</h3>
                <p className="text-sm mb-6 leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{plan.desc}</p>
                <div className="mb-7">
                  <span className="text-5xl font-bold" style={{ color: c.text }}>{yearly ? plan.priceYearly : plan.priceMonthly}€</span>
                  <span className="text-sm ml-1.5" style={{ color: "oklch(0.7 0.015 270)" }}>/Monat</span>
                  {yearly && <div className="text-xs mt-1" style={{ color: c.accent }}>= {plan.priceYearly * 12}€ jährlich abgerechnet</div>}
                </div>
                <div className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <div key={f} className="flex items-start gap-2.5">
                      <CheckCircle2 size={15} className="shrink-0 mt-0.5" style={{ color: plan.highlight ? c.accent : "oklch(0.5 0.12 292)" }} />
                      <span className="text-sm" style={{ color: "oklch(0.78 0.01 270)" }}>{f}</span>
                    </div>
                  ))}
                </div>
                <Link href="/register">
                  <Button className="w-full rounded-xl h-auto py-3.5 text-sm font-semibold" variant={plan.highlight ? "default" : "outline"}
                    style={plan.highlight ? { backgroundColor: c.accent, color: "white" } : { borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.8 0.005 270)", background: "transparent" }}>
                    14 Tage kostenlos testen <ArrowRight size={14} className="ml-2" />
                  </Button>
                </Link>
              </motion.div>
            ))}
          </div>

          {/* Enterprise CTA */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
            className="max-w-5xl mx-auto mt-6 p-6 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4"
            style={{ background: c.card, border: `1px solid ${c.accent}33` }}>
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: `${c.gold}15` }}>
                <Crown size={22} style={{ color: c.gold }} />
              </div>
              <div>
                <h3 className="text-lg font-bold mb-1" style={{ color: c.text }}>Enterprise</h3>
                <p className="text-sm" style={{ color: c.textDim }}>Unbegrenzt alles, SLA-Garantie, Dedicated Support, On-Premise Option, eigene LLM-Keys. Individuelles Pricing.</p>
              </div>
            </div>
            <a href="mailto:enterprise@ariia.ai">
              <Button className="text-sm px-6 py-2.5 rounded-lg shrink-0" style={{ backgroundColor: c.gold, color: "oklch(0.15 0.04 85)" }}>
                Sales kontaktieren
              </Button>
            </a>
          </motion.div>

          {/* Comparison Toggle */}
          <div className="text-center mt-10">
            <button onClick={() => setShowComparison(!showComparison)} className="text-sm font-medium inline-flex items-center gap-2 px-5 py-2.5 rounded-lg transition-colors" style={{ color: c.accent, border: `1px solid ${c.accent}33`, background: `${c.accent}08` }}>
              {showComparison ? "Vergleich ausblenden" : "Detaillierter Plan-Vergleich"}
              <ChevronRight size={14} style={{ transform: showComparison ? "rotate(90deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
            </button>
          </div>
        </div>
      </Section>

      {/* ── Comparison Table ──────────────────────────────────────────── */}
      <AnimatePresence>
        {showComparison && (
          <motion.section initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
            <div className="container mx-auto px-4 pb-20">
              <div className="max-w-6xl mx-auto overflow-x-auto rounded-2xl" style={{ background: c.card, border: `1px solid ${c.border}` }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                      <th className="text-left p-4 font-semibold" style={{ color: c.textSub, minWidth: 200 }}>Feature</th>
                      {planHeaders.map((h, i) => (
                        <th key={h} className="p-4 text-center font-semibold" style={{ color: i === 1 ? c.accent : c.text, minWidth: 130 }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonRows.map((cat) => (
                      <>
                        <tr key={cat.category}>
                          <td colSpan={5} className="px-4 pt-5 pb-2 text-xs font-bold uppercase tracking-wider" style={{ color: c.accent }}>{cat.category}</td>
                        </tr>
                        {cat.rows.map((row) => (
                          <tr key={row.label} style={{ borderBottom: `1px solid ${c.border}40` }}>
                            <td className="px-4 py-2.5" style={{ color: c.textSub }}>{row.label}</td>
                            {row.values.map((val, vi) => (
                              <td key={vi} className="px-4 py-2.5 text-center">
                                {val === true ? <Check size={16} className="mx-auto" style={{ color: c.green }} /> :
                                 val === false ? <Minus size={16} className="mx-auto" style={{ color: "oklch(0.35 0.02 270)" }} /> :
                                 <span style={{ color: c.text, fontSize: "0.8125rem" }}>{val}</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.section>
        )}
      </AnimatePresence>

      {/* ── Add-ons ───────────────────────────────────────────────────── */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: c.accent }}>Modulare Erweiterungen</span>
            <h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: c.text }}>
              Erweitere deinen Plan mit <span style={{ color: c.accent }}>Add-ons</span>
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: c.textDim }}>
              Zahle nur für das was du brauchst. Alle Add-ons monatlich kündbar.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
            {addons.map((addon, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.04 }}
                className="p-5 rounded-xl group hover:scale-[1.03] transition-all duration-300"
                style={{ background: c.card, border: `1px solid ${c.border}` }}>
                <div className="flex items-start justify-between mb-3">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: `${addon.color}12` }}>
                    <addon.icon size={18} style={{ color: addon.color }} />
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `${addon.color}12`, color: addon.color }}>
                    ab {addon.min}
                  </span>
                </div>
                <div className="text-xl font-bold mb-1" style={{ color: addon.color }}>
                  +{addon.price}€<span className="text-xs font-normal" style={{ color: c.textMuted }}>/Monat</span>
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "oklch(0.92 0.005 270)" }}>{addon.name}</h3>
                <p className="text-xs leading-relaxed" style={{ color: c.textMuted }}>{addon.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Overage Info ──────────────────────────────────────────────── */}
      <Section className="pb-20">
        <div className="container mx-auto px-4">
          <div className="max-w-3xl mx-auto p-6 rounded-2xl" style={{ background: c.card, border: `1px solid ${c.border}` }}>
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: c.text }}>
              <Zap size={18} style={{ color: c.gold }} /> Flexible Overage-Abrechnung
            </h3>
            <p className="text-sm mb-4" style={{ color: c.textSub }}>
              Dein Service wird nie unterbrochen. Wenn du dein Limit überschreitest, wird der Mehrverbrauch automatisch und fair abgerechnet:
            </p>
            <div className="grid sm:grid-cols-2 gap-3">
              {[
                { label: "Zusätzliche Konversation", price: "0,05€" },
                { label: "Zusätzlicher User", price: "15€/Monat" },
                { label: "Zusätzlicher Connector", price: "49€/Monat" },
                { label: "Zusätzlicher Kanal", price: "29€/Monat" },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between p-3 rounded-lg" style={{ background: "oklch(0.1 0.04 270)" }}>
                  <span className="text-sm" style={{ color: c.textSub }}>{item.label}</span>
                  <span className="text-sm font-semibold" style={{ color: c.text }}>{item.price}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      {/* ── FAQ ───────────────────────────────────────────────────────── */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <div className="text-center mb-14">
            <h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: c.text }}>Häufige Fragen</h2>
          </div>
          <div className="space-y-3">
            {faqs.map((faq: any, i: number) => (
              <motion.div key={i} initial={{ opacity: 0, y: 15 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.06 }}
                className="rounded-xl overflow-hidden" style={{ background: c.card, border: `1px solid ${c.border}` }}>
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="w-full flex items-center justify-between p-5 text-left">
                  <span className="text-sm font-semibold pr-4" style={{ color: "oklch(0.92 0.005 270)" }}>{faq.q}</span>
                  <HelpCircle size={18} className="shrink-0 transition-transform duration-200" style={{ color: openFaq === i ? c.accent : "oklch(0.5 0.015 270)", transform: openFaq === i ? "rotate(180deg)" : "rotate(0deg)" }} />
                </button>
                <AnimatePresence>
                  {openFaq === i && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="px-5 pb-5 overflow-hidden">
                      <p className="text-sm leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{faq.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Final CTA ─────────────────────────────────────────────────── */}
      <Section className="py-24 lg:py-32">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-6" style={{ color: c.text }}>
            Bereit für die <span style={{ color: c.accent }}>Zukunft deines Business?</span>
          </h2>
          <p className="text-lg max-w-xl mx-auto mb-10" style={{ color: c.textDim }}>
            Starte noch heute mit 14 Tagen kostenlosem Test. Keine Kreditkarte erforderlich.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/register">
              <Button className="text-base px-9 py-4 rounded-xl h-auto" style={{ backgroundColor: c.accent, color: "white" }}>
                Jetzt kostenlos starten <ArrowRight size={16} className="ml-2" />
              </Button>
            </Link>
            <a href="mailto:hello@ariia.ai">
              <Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto bg-transparent group" style={{ borderColor: "oklch(0.28 0.04 270)", color: c.textSub }}>
                Demo vereinbaren
              </Button>
            </a>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
