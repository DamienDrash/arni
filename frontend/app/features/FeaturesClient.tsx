"use client";

/*
 * ARIIA Features Page – Studio Deck Design Language
 * Violet-based theme aligned with Home and Pricing pages.
 */
import { useRef } from "react";
import Link from "next/link";
import { motion, useInView } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import {
  Brain, MessageSquare, BarChart3, Cpu, Lock, Plug, Headphones,
  Eye, Globe, Users, ArrowRight, CheckCircle2, Zap, Shield,
  Database, Activity, ChevronRight, Sparkles, Settings, Bell, Layers, Bot
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

const coreFeatures = [
  {
    icon: Bot,
    title: "Project Titan – Orchestrator-Worker Architektur",
    desc: "Der Master-Orchestrator analysiert jede Nachricht, erkennt den Intent und delegiert an den spezialisierten Agenten. Kein starres Routing, sondern intelligente Entscheidungen in Echtzeit.",
    color: "oklch(0.62 0.22 292)",
    details: ["Intent-Erkennung mit Kontext-Analyse", "Dynamisches Agent-Routing", "Fallback & Eskalationslogik", "Confidence-basierte Entscheidungen"],
  },
  {
    icon: Users,
    title: "5 Spezialisierte KI-Agenten",
    desc: "Jeder Agent ist ein Experte in seinem Bereich. Zusammen bilden sie einen Swarm, der jede Kundenanfrage optimal beantwortet.",
    color: "oklch(0.62 0.22 292)",
    details: ["Ops Agent – Buchungen, Öffnungszeiten, FAQ", "Sales Agent – Angebote, Upgrades, Aktionen", "Medic Agent – Gesundheit, Training, Ernährung", "Vision Agent – Bildanalyse (YOLOv8)", "Persona Agent – Persönlichkeit & Tonalität"],
  },
  {
    icon: Database,
    title: "3-Tier Memory System",
    desc: "ARIIA vergisst nichts. Session Memory für aktuelle Gespräche, Semantic Memory für Wissen, Episodic Memory für die komplette Kundenhistorie.",
    color: "oklch(0.8 0.16 85)",
    details: ["Session Memory – Gesprächskontext", "Semantic Memory – Wissensbasis (Qdrant)", "Episodic Memory – Kundenhistorie", "Automatische Memory-Konsolidierung"],
  },
  {
    icon: MessageSquare,
    title: "Omni-Channel Kommunikation",
    desc: "WhatsApp, Telegram, Voice, Web-Chat – eine KI, konsistente Antworten auf allen Kanälen. Kunden wählen ihren bevorzugten Kanal.",
    color: "oklch(0.62 0.22 292)",
    details: ["WhatsApp Business API + QR-Bridge", "Telegram Multi-Tenant Polling", "Voice Pipeline (Whisper + ElevenLabs)", "Web-Chat Widget (Coming Soon)"],
  },
  {
    icon: Headphones,
    title: "Voice Pipeline",
    desc: "Sprachnachrichten werden in Echtzeit transkribiert, analysiert und mit natürlicher Stimme beantwortet.",
    color: "oklch(0.62 0.22 292)",
    details: ["Whisper STT (Speech-to-Text)", "ElevenLabs TTS (Text-to-Speech)", "Emotionserkennung", "Mehrsprachig"],
  },
  {
    icon: Eye,
    title: "Vision Agent (YOLOv8)",
    desc: "Kunden können Bilder senden – ARIIA erkennt Geräte, Übungen, Verletzungen und mehr.",
    color: "oklch(0.68 0.18 25)",
    details: ["Objekterkennung", "Geräte-Identifikation", "Formanalyse", "Verletzungs-Screening"],
  },
];

const securityFeatures = [
  { icon: Shield, label: "DSGVO-konform" },
  { icon: Lock, label: "Row-Level Security" },
  { icon: Eye, label: "PII-Filter" },
  { icon: Activity, label: "Audit Logs" },
  { icon: Users, label: "RBAC" },
  { icon: Database, label: "Verschlüsselt" },
];

const platformFeatures = [
  { icon: Activity, title: "Live Monitor", desc: "Echtzeit-Übersicht aller aktiven Sessions mit Eskalations-Queue." },
  { icon: BarChart3, title: "Churn Prediction", desc: "ML-basierte Vorhersage mit Handlungsempfehlungen für gefährdete Kunden." },
  { icon: Users, title: "Mitgliederverwaltung", desc: "Kontaktdatenbank mit Churn-Score, Verträgen und Kommunikationshistorie." },
  { icon: Layers, title: "Wissensbasis (RAG)", desc: "WYSIWYG-Editor für die Wissensbasis – ARIIA lernt aus deinen Inhalten." },
  { icon: Globe, title: "Multi-Tenant", desc: "Mehrere Standorte, ein Dashboard. Jeder Tenant isoliert mit eigenen Daten." },
  { icon: Sparkles, title: "Custom Prompts", desc: "Definiere Tonalität, Persona und Antwortverhalten pro Tenant." },
  { icon: Bell, title: "Eskalations-Queue", desc: "Automatische Eskalation an dein Team, wenn ARIIA nicht weiterkommt." },
  { icon: Settings, title: "AI Evaluation", desc: "Automatisierte Qualitätsprüfung der KI-Antworten mit DeepEval." },
  { icon: Plug, title: "Connector Hub", desc: "Modulares System zum Anbinden von Magicline, Shopify, WooCommerce und mehr." },
];

export default function FeaturesClient() {
  return (
    <div className="min-h-screen" style={{ background: "oklch(0.09 0.04 270)" }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-16 lg:pt-36 lg:pb-20 relative overflow-hidden">
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
            Plattform
          </motion.span>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6"
            style={{ color: "oklch(0.97 0.005 270)" }}
          >
            Features die dein Business{" "}
            <span style={{ color: "oklch(0.62 0.22 292)" }}>transformieren</span>
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="text-lg max-w-2xl mx-auto"
            style={{ color: "oklch(0.65 0.015 270)" }}
          >
            ARIIA ist mehr als ein Chatbot. Es ist ein Living System Agent mit 5 spezialisierten KI-Agenten, 3-Tier Memory und Enterprise-Grade Security.
          </motion.p>
        </div>
      </section>

      {/* Core Features */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "oklch(0.62 0.22 292)" }}>
              KI-Kern-Technologie
            </span>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>
              Was ARIIA von Chatbots <span style={{ color: "oklch(0.62 0.22 292)" }}>unterscheidet</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {coreFeatures.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="rounded-2xl p-7 group hover:scale-[1.02] transition-all duration-300 border border-transparent"
                style={{ background: "oklch(0.12 0.04 270 / 0.5)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-5 transition-all duration-300 group-hover:scale-110"
                  style={{ background: `${f.color}12` }}>
                  <f.icon size={22} style={{ color: f.color }} />
                </div>
                <h3 className="text-lg font-bold mb-2.5" style={{ color: "oklch(0.95 0.005 270)" }}>
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed mb-5" style={{ color: "oklch(0.62 0.015 270)" }}>
                  {f.desc}
                </p>
                <div className="space-y-2">
                  {f.details.map((d) => (
                    <div key={d} className="flex items-start gap-2.5">
                      <CheckCircle2 size={13} className="shrink-0 mt-0.5" style={{ color: f.color }} />
                      <span className="text-xs" style={{ color: "oklch(0.7 0.015 270)" }}>{d}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* Security */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4 text-center">
          <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ color: "oklch(0.62 0.22 292)" }}>
            Enterprise Security
          </span>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-5" style={{ color: "oklch(0.97 0.005 270)" }}>
            Sicherheit auf <span style={{ color: "oklch(0.62 0.22 292)" }}>Enterprise-Niveau</span>
          </h2>
          <p className="text-base max-w-xl mx-auto mb-14" style={{ color: "oklch(0.65 0.015 270)" }}>
            Von Grund auf für den deutschen Markt entwickelt. Jede Datenzeile ist durch Row-Level Security isoliert.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 max-w-4xl mx-auto">
            {securityFeatures.map((sf, i) => (
              <motion.div
                key={sf.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.06 }}
                className="p-5 rounded-xl text-center group hover:scale-105 transition-all duration-300"
                style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                <div className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-3 transition-all group-hover:scale-110"
                  style={{ background: "oklch(0.62 0.22 292 / 0.08)" }}>
                  <sf.icon size={18} style={{ color: "oklch(0.62 0.22 292)" }} />
                </div>
                <span className="text-xs font-semibold" style={{ color: "oklch(0.8 0.005 270)" }}>{sf.label}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* Studio Deck Platform */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "oklch(0.62 0.22 292)" }}>
              Studio Deck
            </span>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-5" style={{ color: "oklch(0.97 0.005 270)" }}>
              Dein <span style={{ color: "oklch(0.62 0.22 292)" }}>Command Center</span>
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "oklch(0.65 0.015 270)" }}>
              Das Studio Deck Dashboard gibt dir die volle Kontrolle über deine KI-Agenten, Mitglieder und Kommunikation.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {platformFeatures.map((pf, i) => (
              <motion.div
                key={pf.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="rounded-xl p-6 group hover:scale-[1.02] transition-all duration-300"
                style={{ background: "oklch(0.12 0.04 270 / 0.5)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
                  style={{ background: "oklch(0.62 0.22 292 / 0.08)" }}>
                  <pf.icon size={18} style={{ color: "oklch(0.62 0.22 292)" }} />
                </div>
                <h3 className="text-base font-bold mb-2" style={{ color: "oklch(0.95 0.005 270)" }}>
                  {pf.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "oklch(0.62 0.015 270)" }}>{pf.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* CTA */}
      <Section className="py-24 lg:py-32">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>
            Bereit, ARIIA in Aktion zu <span style={{ color: "oklch(0.62 0.22 292)" }}>erleben</span>?
          </h2>
          <p className="text-lg max-w-xl mx-auto mb-10" style={{ color: "oklch(0.65 0.015 270)" }}>
            14 Tage kostenlos testen. Kein Risiko, keine Kreditkarte.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/register">
              <Button className="text-base px-9 py-4 rounded-xl h-auto" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                Kostenlos starten <ArrowRight size={16} className="ml-2" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto bg-transparent group"
                style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.75 0.01 270)" }}>
                Pläne vergleichen
                <ChevronRight size={16} className="ml-1 transition-transform group-hover:translate-x-1" />
              </Button>
            </Link>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
