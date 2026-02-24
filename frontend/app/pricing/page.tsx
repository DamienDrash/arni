"use client";

/*
 * ARIIA Pricing Page – Studio Deck Design Language
 * Violet-based theme aligned with Home and Features pages.
 */
import { useState, useRef } from "react";
import Link from "next/link";
import { motion, useInView, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import {
  CheckCircle2, ArrowRight, Sparkles, Zap, MessageSquare,
  Headphones, Eye, Plug, Users, BarChart3, Palette, HelpCircle, ChevronRight
} from "lucide-react";

function Section({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.section
      ref={ref}
      initial={{ opacity: 0, y: 50 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.section>
  );
}

const plans = [
  {
    name: "Starter",
    desc: "Für Personal Trainer und Mikro-Studios, die KI-Kommunikation testen wollen.",
    priceMonthly: 79,
    priceYearly: 63,
    features: [
      "1 Kommunikationskanal",
      "500 KI-Konversationen / Monat",
      "ARIIA Core Agent",
      "Basis-Connector (1 System)",
      "1 Benutzer",
      "E-Mail Support",
      "Studio Deck Dashboard",
    ],
    cta: "Starter wählen",
    highlight: false,
    badge: null,
  },
  {
    name: "Professional",
    desc: "Für etablierte Studios und KMUs mit mehreren Kanälen und vollem KI-Swarm.",
    priceMonthly: 199,
    priceYearly: 159,
    features: [
      "3 Kommunikationskanäle",
      "2.000 KI-Konversationen / Monat",
      "Voller KI-Agenten-Swarm (5 Agenten)",
      "3 Connectors inklusive",
      "5 Benutzer",
      "Custom Prompts & Tonalität",
      "Analytics & Reporting",
      "Prioritäts-Support",
    ],
    cta: "Professional wählen",
    highlight: true,
    badge: "Beliebtester Plan",
  },
  {
    name: "Business",
    desc: "Für Studioketten und wachsende Unternehmen mit hohem Volumen.",
    priceMonthly: 399,
    priceYearly: 319,
    features: [
      "Alle Kommunikationskanäle",
      "10.000 KI-Konversationen / Monat",
      "Voller KI-Swarm + Priority Routing",
      "Unbegrenzte Connectors",
      "15 Benutzer",
      "Churn Prediction inklusive",
      "API-Zugang (REST + Webhooks)",
      "Audit Logs & RBAC",
      "Dedizierter Support",
    ],
    cta: "Business wählen",
    highlight: false,
    badge: null,
  },
];

const addons = [
  { icon: BarChart3, name: "Churn Prediction", price: "49", desc: "ML-basierte Abwanderungsprognose mit proaktiven Maßnahmen.", color: "oklch(0.8 0.16 85)" },
  { icon: Headphones, name: "Voice Pipeline", price: "79", desc: "Whisper STT + ElevenLabs TTS für Sprachnachrichten.", color: "oklch(0.62 0.22 292)" },
  { icon: Eye, name: "Vision AI", price: "39", desc: "YOLOv8-basierte Bildanalyse für eingesendete Fotos.", color: "oklch(0.68 0.18 25)" },
  { icon: MessageSquare, name: "Extra Kanal", price: "29", desc: "Zusätzlicher Kommunikationskanal freischalten.", color: "oklch(0.62 0.22 292)" },
  { icon: Zap, name: "Konversations-Boost", price: "0,05€/Stk.", desc: "Zusätzliche KI-Konversationen über das Planlimit hinaus.", color: "oklch(0.62 0.22 292)" },
  { icon: Users, name: "Extra Benutzer", price: "15", desc: "Zusätzlicher Benutzer-Seat für dein Team.", color: "oklch(0.72 0.2 292)" },
  { icon: Palette, name: "White-Label", price: "149", desc: "Eigenes Branding, Logo und Domain für deine Kunden.", color: "oklch(0.8 0.16 85)" },
  { icon: Plug, name: "Extra Connector", price: "49", desc: "Zusätzliches Geschäftssystem anbinden (Magicline, Shopify etc.).", color: "oklch(0.62 0.22 292)" },
];

const faqs = [
  { q: "Gibt es eine kostenlose Testphase?", a: "Ja, alle Pläne beinhalten eine 14-tägige kostenlose Testphase. Keine Kreditkarte erforderlich." },
  { q: "Kann ich meinen Plan jederzeit wechseln?", a: "Ja, du kannst jederzeit upgraden oder downgraden. Bei einem Upgrade wird die Differenz anteilig berechnet." },
  { q: "Was passiert, wenn ich mein Konversationslimit erreiche?", a: "Du wirst benachrichtigt und kannst entweder den Konversations-Boost buchen (€0,05/Stk.) oder auf einen höheren Plan upgraden." },
  { q: "Ist ARIIA DSGVO-konform?", a: "Ja, ARIIA wurde von Grund auf für den deutschen Markt entwickelt. Row-Level Security, PII-Filter und verschlüsselte Kommunikation sind Standard." },
  { q: "Gibt es einen Enterprise-Plan?", a: "Ja, für Unternehmen mit besonderen Anforderungen (SLA, On-Premise, Custom Integrationen) bieten wir individuelle Enterprise-Lösungen an. Kontaktiere uns." },
];

export default function PricingPage() {
  const [yearly, setYearly] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen" style={{ background: "oklch(0.09 0.04 270)" }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-12 lg:pt-36 lg:pb-16 relative overflow-hidden">
        {/* Animated grid */}
        <div className="absolute inset-0 pointer-events-none opacity-20" 
             style={{ 
               backgroundImage: "radial-gradient(oklch(0.62 0.22 292 / 0.15) 1px, transparent 1px)", 
               backgroundSize: "40px 40px" 
             }} 
        />
        <div className="container mx-auto px-4 text-center relative z-10">
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "oklch(0.62 0.22 292)" }}
          >
            Pricing
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6"
            style={{ color: "oklch(0.97 0.005 270)" }}
          >
            Transparente <span style={{ color: "oklch(0.62 0.22 292)" }}>Preise</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-lg max-w-2xl mx-auto mb-10"
            style={{ color: "oklch(0.75 0.01 270)" }}
          >
            Wähle den Plan, der zu deinem Business passt. Alle Pläne beinhalten eine 14-tägige kostenlose Testphase – ohne Kreditkarte.
          </motion.p>

          {/* Toggle */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="flex items-center justify-center gap-4 mb-14"
          >
            <span className="text-sm font-medium" style={{ color: yearly ? "oklch(0.6 0.015 270)" : "oklch(0.97 0.005 270)" }}>
              Monatlich
            </span>
            <button
              onClick={() => setYearly(!yearly)}
              className="relative w-14 h-7 rounded-full transition-colors duration-300"
              style={{ background: yearly ? "oklch(0.62 0.22 292)" : "oklch(0.38 0.04 270)", border: "1px solid oklch(0.45 0.04 270)" }}
            >
              <div
                className="absolute top-1 w-5 h-5 rounded-full transition-transform duration-300"
                style={{
                  background: "oklch(0.97 0.005 270)",
                  transform: yearly ? "translateX(32px)" : "translateX(4px)",
                }}
              />
            </button>
            <span className="text-sm font-medium" style={{ color: yearly ? "oklch(0.97 0.005 270)" : "oklch(0.6 0.015 270)" }}>
              Jährlich{" "}
              <span className="text-xs px-2 py-0.5 rounded-full ml-1"
                style={{ background: "oklch(0.62 0.22 292 / 0.12)", color: "oklch(0.62 0.22 292)" }}>
                -20%
              </span>
            </span>
          </motion.div>
        </div>
      </section>

      {/* Plans */}
      <Section className="pb-20">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="relative rounded-2xl p-7 lg:p-8 flex flex-col group hover:scale-[1.02] transition-all duration-300"
                style={{
                  background: plan.highlight ? "oklch(0.13 0.04 270)" : "oklch(0.12 0.04 270)",
                  border: plan.highlight ? "1px solid oklch(0.62 0.22 292 / 0.35)" : "1px solid oklch(0.22 0.04 270)",
                  boxShadow: plan.highlight ? "0 0 50px oklch(0.62 0.22 292 / 0.08)" : "none",
                }}
              >
                {plan.badge && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-bold"
                    style={{ background: "oklch(0.62 0.22 292)", color: "white" }}>
                    <Sparkles size={12} /> {plan.badge}
                  </div>
                )}

                <h3 className="text-xl font-bold mb-1" style={{ color: "oklch(0.97 0.005 270)" }}>
                  {plan.name}
                </h3>
                <p className="text-sm mb-6 leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{plan.desc}</p>

                <div className="mb-7">
                  <span className="text-5xl font-bold" style={{ color: "oklch(0.97 0.005 270)" }}>
                    {yearly ? plan.priceYearly : plan.priceMonthly}€
                  </span>
                  <span className="text-sm ml-1.5" style={{ color: "oklch(0.7 0.015 270)" }}>/Monat</span>
                  {yearly && (
                    <div className="text-xs mt-1" style={{ color: "oklch(0.62 0.22 292)" }}>
                      {plan.priceYearly * 12}€ jährlich abgerechnet
                    </div>
                  )}
                </div>

                <div className="space-y-3 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <div key={f} className="flex items-start gap-2.5">
                      <CheckCircle2 size={15} className="shrink-0 mt-0.5"
                        style={{ color: plan.highlight ? "oklch(0.62 0.22 292)" : "oklch(0.5 0.12 292)" }} />
                      <span className="text-sm" style={{ color: "oklch(0.78 0.01 270)" }}>{f}</span>
                    </div>
                  ))}
                </div>

                <Link href="/register">
                  <Button
                    className={`w-full rounded-xl h-auto py-3.5 text-sm font-semibold`}
                    variant={plan.highlight ? "default" : "outline"}
                    style={plan.highlight ? { backgroundColor: "oklch(0.62 0.22 292)", color: "white" } : { borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.8 0.005 270)", background: "transparent" }}
                  >
                    {plan.cta} <ArrowRight size={14} className="ml-2" />
                  </Button>
                </Link>
              </motion.div>
            ))}
          </div>

          {/* Enterprise CTA */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="max-w-5xl mx-auto mt-6 p-6 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4"
            style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.62 0.22 292 / 0.2)" }}
          >
            <div>
              <h3 className="text-lg font-bold mb-1" style={{ color: "oklch(0.97 0.005 270)" }}>
                Enterprise
              </h3>
              <p className="text-sm" style={{ color: "oklch(0.65 0.015 270)" }}>
                SLA-Garantie, On-Premise, Custom Integrationen, dedizierter Account Manager.
              </p>
            </div>
            <a href="mailto:enterprise@ariia.ai">
              <Button className="text-sm px-6 py-2.5 rounded-lg shrink-0" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                Kontakt aufnehmen
              </Button>
            </a>
          </motion.div>
        </div>
      </Section>

      {/* Add-ons */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "oklch(0.62 0.22 292)" }}>
              Modulare Erweiterungen
            </span>
            <h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>
              Zubuchbare <span style={{ color: "oklch(0.62 0.22 292)" }}>Add-ons</span>
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "oklch(0.65 0.015 270)" }}>
              Erweitere deinen Plan flexibel mit zusätzlichen Modulen – zahle nur für das, was du brauchst.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
            {addons.map((addon, i) => (
              <motion.div
                key={addon.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="p-5 rounded-xl group hover:scale-[1.03] transition-all duration-300"
                style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
                  style={{ background: `${addon.color}12` }}>
                  <addon.icon size={18} style={{ color: addon.color }} />
                </div>
                <div className="text-xl font-bold mb-1" style={{ color: addon.color }}>
                  +{addon.price}{!addon.price.includes("€") && "€"}<span className="text-xs font-normal" style={{ color: "oklch(0.6 0.015 270)" }}>/Monat</span>
                </div>
                <h3 className="text-sm font-semibold mb-2" style={{ color: "oklch(0.92 0.005 270)" }}>{addon.name}</h3>
                <p className="text-xs leading-relaxed" style={{ color: "oklch(0.6 0.015 270)" }}>{addon.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* FAQ */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 max-w-3xl">
          <div className="text-center mb-14">
            <h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>
              Häufig gestellte Fragen
            </h2>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 15 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="rounded-xl overflow-hidden"
                style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between p-5 text-left"
                >
                  <span className="text-sm font-semibold pr-4" style={{ color: "oklch(0.92 0.005 270)" }}>{faq.q}</span>
                  <HelpCircle size={18} className="shrink-0 transition-transform duration-200"
                    style={{
                      color: openFaq === i ? "oklch(0.62 0.22 292)" : "oklch(0.5 0.015 270)",
                      transform: openFaq === i ? "rotate(180deg)" : "rotate(0deg)",
                    }} />
                </button>
                <AnimatePresence>
                  {openFaq === i && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="px-5 pb-5 overflow-hidden"
                    >
                      <p className="text-sm leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{faq.a}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* CTA */}
      <Section className="py-24 lg:py-32">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>
            Noch unsicher? <span style={{ color: "oklch(0.62 0.22 292)" }}>Teste es einfach.</span>
          </h2>
          <p className="text-lg max-w-xl mx-auto mb-10" style={{ color: "oklch(0.65 0.015 270)" }}>
            14 Tage kostenlos, voller Funktionsumfang, keine Kreditkarte. Überzeuge dich selbst.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/register">
              <Button className="text-base px-9 py-4 rounded-xl h-auto" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                14 Tage kostenlos testen <ArrowRight size={16} className="ml-2" />
              </Button>
            </Link>
            <a href="mailto:hello@ariia.ai">
              <Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto bg-transparent group"
                 style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.75 0.01 270)" }}>
                Kontakt aufnehmen
                <ChevronRight size={16} className="ml-1 transition-transform group-hover:translate-x-1" />
              </Button>
            </a>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
