"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { motion, useInView, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import { useI18n } from "@/lib/i18n/LanguageContext";
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

export default function PricingClient() {
  const { t } = useI18n();
  const [yearly, setYearly] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const plans = [
    {
      name: t("pricing.plans.starter.name"),
      desc: t("pricing.plans.starter.desc"),
      priceMonthly: 79,
      priceYearly: 63,
      features: t("pricing.plans.starter.features"),
      cta: t("pricing.plans.starter.cta"),
      highlight: false,
      badge: null,
    },
    {
      name: t("pricing.plans.professional.name"),
      desc: t("pricing.plans.professional.desc"),
      priceMonthly: 199,
      priceYearly: 159,
      features: t("pricing.plans.professional.features"),
      cta: t("pricing.plans.professional.cta"),
      highlight: true,
      badge: t("pricing.plans.professional.badge"),
    },
    {
      name: t("pricing.plans.business.name"),
      desc: t("pricing.plans.business.desc"),
      priceMonthly: 399,
      priceYearly: 319,
      features: t("pricing.plans.business.features"),
      cta: t("pricing.plans.business.cta"),
      highlight: false,
      badge: null,
    },
  ];

  const addons = [
    { icon: BarChart3, name: t("pricing.addons.churn.name"), price: "49", desc: t("pricing.addons.churn.desc"), color: "oklch(0.8 0.16 85)" },
    { icon: Headphones, name: t("pricing.addons.voice.name"), price: "79", desc: t("pricing.addons.voice.desc"), color: "oklch(0.62 0.22 292)" },
    { icon: Eye, name: t("pricing.addons.vision.name"), price: "39", desc: t("pricing.addons.vision.desc"), color: "oklch(0.68 0.18 25)" },
    { icon: MessageSquare, name: t("pricing.addons.channel.name"), price: "29", desc: t("pricing.addons.channel.desc"), color: "oklch(0.62 0.22 292)" },
  ];

  const faqs = t("pricing.faqs");

  return (
    <div className="min-h-screen" style={{ background: "oklch(0.09 0.04 270)" }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-12 lg:pt-36 lg:pb-16 relative overflow-hidden">
        <div className="absolute inset-0 pointer-events-none opacity-20" 
             style={{ backgroundImage: "radial-gradient(oklch(0.62 0.22 292 / 0.15) 1px, transparent 1px)", backgroundSize: "40px 40px" }} 
        />
        <div className="container mx-auto px-4 text-center relative z-10">
          <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>
            Pricing
          </motion.span>
          <motion.h1 initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }} className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>
            {t("pricing.title")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("pricing.titleAccent")}</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.1 }} className="text-lg max-w-2xl mx-auto mb-10" style={{ color: "oklch(0.75 0.01 270)" }}>
            {t("pricing.description")}
          </motion.p>

          {/* Toggle */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} className="flex items-center justify-center gap-4 mb-14">
            <span className="text-sm font-medium" style={{ color: yearly ? "oklch(0.6 0.015 270)" : "oklch(0.97 0.005 270)" }}>{t("pricing.monthly")}</span>
            <button onClick={() => setYearly(!yearly)} className="relative w-14 h-7 rounded-full transition-colors duration-300" style={{ background: yearly ? "oklch(0.62 0.22 292)" : "oklch(0.38 0.04 270)", border: "1px solid oklch(0.45 0.04 270)" }}>
              <div className="absolute top-1 w-5 h-5 rounded-full transition-transform duration-300" style={{ background: "oklch(0.97 0.005 270)", transform: yearly ? "translateX(32px)" : "translateX(4px)" }} />
            </button>
            <span className="text-sm font-medium" style={{ color: yearly ? "oklch(0.97 0.005 270)" : "oklch(0.6 0.015 270)" }}>
              {t("pricing.yearly")} <span className="text-xs px-2 py-0.5 rounded-full ml-1" style={{ background: "oklch(0.62 0.22 292 / 0.12)", color: "oklch(0.62 0.22 292)" }}>{t("pricing.discount")}</span>
            </span>
          </motion.div>
        </div>
      </section>

      {/* Plans */}
      <Section className="pb-20">
        <div className="container mx-auto px-4">
          <div className="grid md:grid-cols-3 gap-5 max-w-5xl mx-auto">
            {plans.map((plan, i) => (
              <motion.div key={plan.name} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.1 }} className="relative rounded-2xl p-7 lg:p-8 flex flex-col group hover:scale-[1.02] transition-all duration-300" style={{ background: plan.highlight ? "oklch(0.13 0.04 270)" : "oklch(0.12 0.04 270)", border: plan.highlight ? "1px solid oklch(0.62 0.22 292 / 0.35)" : "1px solid oklch(0.22 0.04 270)", boxShadow: plan.highlight ? "0 0 50px oklch(0.62 0.22 292 / 0.08)" : "none" }}>
                {plan.badge && <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-bold" style={{ background: "oklch(0.62 0.22 292)", color: "white" }}><Sparkles size={12} /> {plan.badge}</div>}
                <h3 className="text-xl font-bold mb-1" style={{ color: "oklch(0.97 0.005 270)" }}>{plan.name}</h3>
                <p className="text-sm mb-6 leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{plan.desc}</p>
                <div className="mb-7">
                  <span className="text-5xl font-bold" style={{ color: "oklch(0.97 0.005 270)" }}>{yearly ? plan.priceYearly : plan.priceMonthly}€</span>
                  <span className="text-sm ml-1.5" style={{ color: "oklch(0.7 0.015 270)" }}>/Monat</span>
                  {yearly && <div className="text-xs mt-1" style={{ color: "oklch(0.62 0.22 292)" }}>{plan.priceYearly * 12}€ {t("pricing.billedYearly")}</div>}
                </div>
                <div className="space-y-3 mb-8 flex-1">
                  {Array.isArray(plan.features) && plan.features.map((f: string) => (
                    <div key={f} className="flex items-start gap-2.5">
                      <CheckCircle2 size={15} className="shrink-0 mt-0.5" style={{ color: plan.highlight ? "oklch(0.62 0.22 292)" : "oklch(0.5 0.12 292)" }} />
                      <span className="text-sm" style={{ color: "oklch(0.78 0.01 270)" }}>{f}</span>
                    </div>
                  ))}
                </div>
                <Link href="/register">
                  <Button className="w-full rounded-xl h-auto py-3.5 text-sm font-semibold" variant={plan.highlight ? "default" : "outline"} style={plan.highlight ? { backgroundColor: "oklch(0.62 0.22 292)", color: "white" } : { borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.8 0.005 270)", background: "transparent" }}>
                    {plan.cta} <ArrowRight size={14} className="ml-2" />
                  </Button>
                </Link>
              </motion.div>
            ))}
          </div>

          {/* Enterprise CTA */}
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="max-w-5xl mx-auto mt-6 p-6 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4" style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.62 0.22 292 / 0.2)" }}>
            <div>
              <h3 className="text-lg font-bold mb-1" style={{ color: "oklch(0.97 0.005 270)" }}>{t("pricing.enterpriseTitle")}</h3>
              <p className="text-sm" style={{ color: "oklch(0.65 0.015 270)" }}>{t("pricing.enterpriseDesc")}</p>
            </div>
            <a href="mailto:enterprise@ariia.ai"><Button className="text-sm px-6 py-2.5 rounded-lg shrink-0" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>{t("pricing.enterpriseCta")}</Button></a>
          </motion.div>
        </div>
      </Section>

      {/* Add-ons */}
      <Section className="py-20 lg:py-28">
        <div className="container mx-auto px-4">
          <div className="text-center mb-14">
            <span className="inline-block text-xs font-semibold uppercase tracking-widest mb-4" style={{ color: "oklch(0.62 0.22 292)" }}>{t("pricing.addonsTitle")}</span>
            <h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>{t("pricing.addonsSubtitle")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("pricing.addonsSubtitleAccent")}</span></h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "oklch(0.65 0.015 270)" }}>{t("pricing.addonsDesc")}</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 max-w-5xl mx-auto">
            {addons.map((addon, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.06 }} className="p-5 rounded-xl group hover:scale-[1.03] transition-all duration-300" style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: `${addon.color}12` }}><addon.icon size={18} style={{ color: addon.color }} /></div>
                <div className="text-xl font-bold mb-1" style={{ color: addon.color }}>+{addon.price}{!addon.price.includes("€") && "€"}<span className="text-xs font-normal" style={{ color: "oklch(0.6 0.015 270)" }}>/Monat</span></div>
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
          <div className="text-center mb-14"><h2 className="text-2xl lg:text-4xl font-bold tracking-tight mb-4" style={{ color: "oklch(0.97 0.005 270)" }}>{t("pricing.faqTitle")}</h2></div>
          <div className="space-y-3">
            {Array.isArray(faqs) && faqs.map((faq, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 15 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.06 }} className="rounded-xl overflow-hidden" style={{ background: "oklch(0.12 0.04 270)", border: "1px solid oklch(0.22 0.04 270)" }}>
                <button onClick={() => setOpenFaq(openFaq === i ? null : i)} className="w-full flex items-center justify-between p-5 text-left">
                  <span className="text-sm font-semibold pr-4" style={{ color: "oklch(0.92 0.005 270)" }}>{faq.q}</span>
                  <HelpCircle size={18} className="shrink-0 transition-transform duration-200" style={{ color: openFaq === i ? "oklch(0.62 0.22 292)" : "oklch(0.5 0.015 270)", transform: openFaq === i ? "rotate(180deg)" : "rotate(0deg)" }} />
                </button>
                <AnimatePresence>
                  {openFaq === i && <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="px-5 pb-5 overflow-hidden"><p className="text-sm leading-relaxed" style={{ color: "oklch(0.7 0.015 270)" }}>{faq.a}</p></motion.div>}
                </AnimatePresence>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* CTA */}
      <Section className="py-24 lg:py-32">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl lg:text-4xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>{t("pricing.finalCta")} <span style={{ color: "oklch(0.62 0.22 292)" }}>{t("pricing.finalCtaAccent")}</span></h2>
          <p className="text-lg max-w-xl mx-auto mb-10" style={{ color: "oklch(0.65 0.015 270)" }}>{t("pricing.finalCtaDesc")}</p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link href="/register"><Button className="text-base px-9 py-4 rounded-xl h-auto" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>{t("hero.cta")} <ArrowRight size={16} className="ml-2" /></Button></Link>
            <a href="mailto:hello@ariia.ai"><Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto bg-transparent group" style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.75 0.01 270)" }}>{t("pricing.enterpriseCta")}</Button></a>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
