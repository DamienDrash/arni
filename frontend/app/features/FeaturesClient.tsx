"use client";

import { useRef } from "react";
import Link from "next/link";
import { motion, useInView } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { useI18n } from "@/lib/i18n/LanguageContext";
import {
  Brain, MessageSquare, BarChart3, Cpu, Lock, Plug, Headphones,
  Eye, Globe, Users, ArrowRight, CheckCircle2, Activity, ChevronRight, Sparkles, Settings, Bell, Layers, Bot
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

export default function FeaturesClient() {
  const { t } = useI18n();

  const coreFeatures = [
    {
      icon: Bot,
      title: t("features.swarm.title"),
      desc: t("features.swarm.desc"),
      color: "oklch(0.62 0.22 292)",
      details: [t("features.details.intent"), t("features.details.routing"), t("features.details.fallback"), t("features.details.confidence")],
    },
    {
      icon: MessageSquare,
      title: t("features.omnichannel.title"),
      desc: t("features.omnichannel.desc"),
      color: "oklch(0.62 0.22 292)",
      details: [t("features.details.wa"), t("features.details.tg"), t("features.details.voice"), t("features.details.chat")],
    },
    {
      icon: BarChart3,
      title: t("features.churn.title"),
      desc: t("features.churn.desc"),
      color: "oklch(0.8 0.16 85)",
      details: [t("features.details.ml"), t("features.details.proactive"), t("features.details.scoring"), t("features.details.behavior")],
    },
    {
      icon: Cpu,
      title: t("features.memory.title"),
      desc: t("features.memory.desc"),
      color: "oklch(0.68 0.18 25)",
      details: [t("features.details.session"), t("features.details.semantic"), t("features.details.episodic"), t("features.details.auto")],
    },
    {
      icon: Lock,
      title: t("features.security.title"),
      desc: t("features.security.desc"),
      color: "oklch(0.65 0.15 220)",
      details: [t("features.details.dsgvo"), t("features.details.rls"), t("features.details.pii"), t("features.details.audit")],
    },
    {
      icon: Plug,
      title: t("features.connectors.title"),
      desc: t("features.connectors.desc"),
      color: "oklch(0.72 0.2 292)",
      details: [t("features.details.magicline"), t("features.details.shopify"), t("features.details.woo"), t("features.details.api")],
    },
  ];

  const securityFeatures = [
    { icon: Lock, label: t("features.securityLabels.dsgvo") },
    { icon: Lock, label: t("features.securityLabels.rls") },
    { icon: Eye, label: t("features.securityLabels.pii") },
    { icon: Activity, label: t("features.securityLabels.audit") },
    { icon: Users, label: t("features.securityLabels.rbac") },
    { icon: Lock, label: t("features.securityLabels.encryption") },
  ];

  const platformFeatures = [
    { icon: Activity, title: t("features.platform.live.title"), desc: t("features.platform.live.desc") },
    { icon: BarChart3, title: t("features.platform.churn.title"), desc: t("features.platform.churn.desc") },
    { icon: Users, title: t("features.platform.members.title"), desc: t("features.platform.members.desc") },
    { icon: Layers, title: t("features.platform.knowledge.title"), desc: t("features.platform.knowledge.desc") },
    { icon: Globe, title: t("features.platform.multi.title"), desc: t("features.platform.multi.desc") },
    { icon: Sparkles, title: t("features.platform.prompts.title"), desc: t("features.platform.prompts.desc") },
  ];

  return (
    <div className="min-h-screen" style={{ background: "oklch(0.09 0.04 270)" }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-16 lg:pt-36 lg:pb-20 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-20" 
             style={{ backgroundImage: "radial-gradient(oklch(0.62 0.22 292 / 0.15) 1px, transparent 1px)", backgroundSize: "40px 40px" }} 
        />
        <div className="container mx-auto px-4 text-center relative z-10">
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>
            {t("features.badge")}
          </motion.span>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>
            {t("features.page.title")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("features.page.titleAccent")}</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }} className="text-lg max-w-2xl mx-auto" style={{ color: "oklch(0.65 0.015 270)" }}>
            {t("features.page.description")}
          </motion.p>
        </div>
      </section>

      {/* Core Features */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>
              {t("features.page.techTitle")}
            </span>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>
              {t("features.page.techSubtitle")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("features.page.techSubtitleAccent")}</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
            {coreFeatures.map((f, i) => (
              <motion.div key={f.title} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.08 }} className="rounded-2xl p-7 group hover:scale-[1.02] transition-all duration-300" style={{ background: "oklch(0.12 0.04 270 / 0.5)", border: "1px solid oklch(0.22 0.04 270)" }}>
                <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-5 transition-all duration-300 group-hover:scale-110" style={{ background: `${f.color}12` }}>
                  <f.icon size={22} style={{ color: f.color }} />
                </div>
                <h3 className="text-lg font-bold mb-2.5" style={{ color: "oklch(0.95 0.005 270)" }}>{f.title}</h3>
                <p className="text-sm leading-relaxed mb-5" style={{ color: "oklch(0.62 0.015 270)" }}>{f.desc}</p>
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
          <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>
            {t("features.page.securityTitle")}
          </span>
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-5" style={{ color: "oklch(0.97 0.005 270)" }}>
            {t("features.page.securitySubtitle")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("features.page.securitySubtitleAccent")}</span>
          </h2>
          <p className="text-base max-w-xl mx-auto mb-14" style={{ color: "oklch(0.65 0.015 270)" }}>
            {t("features.page.securityDesc")}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 max-w-4xl mx-auto">
            {securityFeatures.map((sf, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.06 }} className="p-5 rounded-xl text-center group hover:scale-105 transition-all duration-300" style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}>
                <div className="w-10 h-10 rounded-lg flex items-center justify-center mx-auto mb-3 transition-all group-hover:scale-110" style={{ background: "oklch(0.62 0.22 292 / 0.08)" }}>
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
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>
              {t("features.page.deckTitle")}
            </span>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-5" style={{ color: "oklch(0.97 0.005 270)" }}>
              {t("features.page.deckSubtitle")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("features.page.deckSubtitleAccent")}</span>
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "oklch(0.65 0.015 270)" }}>
              {t("features.page.deckDesc")}
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {platformFeatures.map((pf, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.08 }} className="rounded-xl p-6 group hover:scale-[1.02] transition-all duration-300" style={{ background: "oklch(0.12 0.04 270 / 0.5)", border: "1px solid oklch(0.22 0.04 270)" }}>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-4" style={{ background: "oklch(0.62 0.22 292 / 0.08)" }}>
                  <pf.icon size={18} style={{ color: "oklch(0.62 0.22 292)" }} />
                </div>
                <h3 className="text-base font-bold mb-2" style={{ color: "oklch(0.95 0.005 270)" }}>{pf.title}</h3>
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
            {t("cta.title")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("cta.titleAccent")}</span>?
          </h2>
          <p className="text-lg max-w-xl mx-auto mb-10" style={{ color: "oklch(0.65 0.015 270)" }}>
            {t("cta.subtitle")}
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/register">
              <Button className="text-base px-9 py-4 rounded-xl h-auto" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                {t("cta.button")} <ArrowRight size={16} className="ml-2" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto bg-transparent group" style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.75 0.01 270)" }}>
                {t("cta.compare")} <ChevronRight size={16} className="ml-1 transition-transform group-hover:translate-x-1" />
              </Button>
            </Link>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
