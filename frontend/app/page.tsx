"use client";

import { useRef, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getStoredUser } from "@/lib/auth";
import { motion, useInView, useScroll, useTransform, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import {
  MessageSquare, Brain, Shield, BarChart3, Zap, Users,
  ArrowRight, CheckCircle2, Headphones, Globe, Cpu, Eye,
  TrendingUp, Lock, Plug, Sparkles, ChevronRight, Play
} from "lucide-react";

/* ═══ CDN Image URLs ═══ */
const IMG_DASHBOARD = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/uFpxKFIPPBOjWMhN.png";
const IMG_WORKFLOW = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/RLPnfyDfBfDTxKYO.png";
const IMG_CHANNELS = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/oRAymPgKYxqGxAch.png";
const IMG_CHURN = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/dnKoNnkDxgeOfnYt.png";
const IMG_CONNECTORS = "https://files.manuscdn.com/user_upload_by_module/session_file/107911917/YhlHENXxfCkEDuSS.png";

/* ═══ Reusable Components ═══ */
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

function FloatingOrb({ delay, x, y, size, color = "oklch(0.62 0.22 292 / 0.15)" }: { delay: number; x: string; y: string; size: number; color?: string }) {
  return (
    <motion.div
      className="absolute rounded-full pointer-events-none blur-sm"
      style={{ left: x, top: y, width: `${size}rem`, height: `${size}rem`, background: color }}
      animate={{
        y: [0, -20, 0],
        opacity: [0.5, 1, 0.5],
      }}
      transition={{
        duration: 4,
        delay: delay,
        repeat: Infinity,
        ease: "easeInOut",
      }}
    />
  );
}

function Counter({ value, suffix = "" }: { value: string; suffix?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const [display, setDisplay] = useState("0");

  useEffect(() => {
    if (!isInView) return;
    const num = parseFloat(value.replace(",", ".").replace(/[^0-9.]/g, ""));
    if (isNaN(num)) { setDisplay(value); return; }
    const duration = 1500;
    const start = Date.now();
    const tick = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = num * eased;
      if (value.includes(",")) {
        setDisplay(current.toFixed(1).replace(".", ","));
      } else {
        setDisplay(Math.round(current).toString());
      }
      if (progress < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }, [isInView, value]);

  return <span ref={ref}>{value.startsWith("<") ? "< " : ""}{value.startsWith("<") ? value.replace("< ", "") : display}{suffix}</span>;
}

/* Typing effect for hero */
function TypingWords({ words }: { words: string[] }) {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setIndex((i) => (i + 1) % words.length), 3000);
    return () => clearInterval(timer);
  }, [words.length]);
  return (
    <AnimatePresence mode="wait">
      <motion.span
        key={words[index]}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.4 }}
        className="inline-block"
        style={{ color: "oklch(0.62 0.22 292)" }}
      >
        {words[index]}
      </motion.span>
    </AnimatePresence>
  );
}

/* ═══ Data ═══ */
const features = [
  { icon: Brain, title: "KI-Agenten-Swarm", desc: "5 spezialisierte Agenten (Ops, Sales, Medic, Vision, Persona) arbeiten als Team – orchestriert durch Project Titan.", color: "oklch(0.62 0.22 292)" },
  { icon: MessageSquare, title: "Omni-Channel", desc: "WhatsApp, Telegram, Voice, Web-Chat – eine KI, konsistente Antworten auf allen Kanälen.", color: "oklch(0.62 0.22 292)" },
  { icon: BarChart3, title: "Churn Prediction", desc: "ML-basierte Abwanderungsprognose erkennt gefährdete Kunden und schlägt proaktive Maßnahmen vor.", color: "oklch(0.8 0.16 85)" },
  { icon: Cpu, title: "3-Tier Memory", desc: "Session, Semantic und Episodic Memory – ARIIA erinnert sich an jeden Kunden und jede Interaktion.", color: "oklch(0.68 0.18 25)" },
  { icon: Lock, title: "Enterprise Security", desc: "DSGVO-konform mit Row-Level Security, PII-Filter, Audit Logs und verschlüsselter Kommunikation.", color: "oklch(0.65 0.15 220)" },
  { icon: Plug, title: "Offene Connectors", desc: "Magicline, Shopify, WooCommerce, API – verbinde jedes Geschäftssystem in Minuten.", color: "oklch(0.72 0.2 292)" },
];

const stats = [
  { value: "98,7", suffix: "%", label: "KI-Auflösungsrate", icon: TrendingUp },
  { value: "< 2s", suffix: "", label: "Antwortzeit", icon: Zap },
  { value: "5", suffix: "", label: "KI-Agenten im Swarm", icon: Brain },
  { value: "24/7", suffix: "", label: "Verfügbarkeit", icon: Globe },
];

const workflowSteps = [
  { num: "01", title: "Kunde schreibt", desc: "Über WhatsApp, Telegram oder Voice – der Kanal spielt keine Rolle.", icon: MessageSquare, color: "oklch(0.62 0.22 292)" },
  { num: "02", title: "Orchestrator analysiert", desc: "Project Titan erkennt Intent, Kontext und wählt den passenden Agenten.", icon: Cpu, color: "oklch(0.62 0.22 292)" },
  { num: "03", title: "Agent antwortet", desc: "Der spezialisierte Agent greift auf Memory und Wissensbasis zu.", icon: Brain, color: "oklch(0.8 0.16 85)" },
  { num: "04", title: "Lernen & Optimieren", desc: "Jede Interaktion fließt ins 3-Tier Memory für bessere Antworten.", icon: Sparkles, color: "oklch(0.68 0.18 25)" },
];

const logos = [
  { name: "WhatsApp", color: "oklch(0.62 0.22 292)" },
  { name: "Telegram", color: "oklch(0.65 0.15 220)" },
  { name: "Magicline", color: "oklch(0.62 0.22 292)" },
  { name: "Shopify", color: "oklch(0.62 0.22 292)" },
  { name: "WooCommerce", color: "oklch(0.62 0.22 292)" },
];

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    if (getStoredUser()) {
      router.replace("/dashboard");
    }
  }, [router]);

  const heroRef = useRef(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, 150]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const dashboardScale = useTransform(scrollYProgress, [0, 0.5], [1, 0.92]);

  return (
    <div className="min-h-screen overflow-x-hidden font-sans" style={{ background: "oklch(0.09 0.04 270)" }}>
      <Navbar />

      {/* ═══════════════════ HERO ═══════════════════ */}
      <section ref={heroRef} className="relative pt-24 pb-20 lg:pt-32 lg:pb-28 overflow-hidden min-h-[90vh] flex items-center">
        {/* Animated grid */}
        <div className="absolute inset-0 pointer-events-none opacity-40" 
             style={{ 
               backgroundImage: "radial-gradient(oklch(0.62 0.22 292 / 0.1) 1px, transparent 1px)", 
               backgroundSize: "40px 40px" 
             }} 
        />

        {/* Floating orbs */}
        <FloatingOrb delay={0} x="5%" y="15%" size={8} />
        <FloatingOrb delay={1.2} x="90%" y="25%" size={6} color="oklch(0.62 0.22 292 / 0.15)" />
        <FloatingOrb delay={0.6} x="75%" y="65%" size={10} />
        <FloatingOrb delay={2} x="20%" y="80%" size={5} color="oklch(0.62 0.22 292 / 0.12)" />
        <FloatingOrb delay={0.8} x="55%" y="10%" size={7} />
        <FloatingOrb delay={1.5} x="35%" y="70%" size={4} color="oklch(0.8 0.16 85 / 0.1)" />

        {/* Animated gradient orb behind dashboard */}
        <motion.div
          className="absolute pointer-events-none"
          style={{ right: "5%", top: "20%", width: 500, height: 500, borderRadius: "50%", filter: "blur(120px)" }}
          animate={{
            background: [
              "radial-gradient(circle, oklch(0.62 0.22 292 / 0.15), transparent)",
              "radial-gradient(circle, oklch(0.62 0.22 292 / 0.12), transparent)",
              "radial-gradient(circle, oklch(0.62 0.22 292 / 0.15), transparent)",
            ],
          }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />

        <motion.div style={{ y: heroY, opacity: heroOpacity }} className="container mx-auto px-4 relative z-10">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Left: Copy */}
            <div>
              <motion.div
                initial={{ opacity: 0, x: -30 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.6 }}
              >
                <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-8"
                  style={{ background: "oklch(0.62 0.22 292 / 0.1)", color: "oklch(0.62 0.22 292)", border: "1px solid oklch(0.62 0.22 292 / 0.25)" }}>
                  <motion.span animate={{ rotate: [0, 360] }} transition={{ duration: 4, repeat: Infinity, ease: "linear" }}>
                    <Zap size={12} />
                  </motion.span>
                  Living System Agent v2.0
                </span>
              </motion.div>

              <motion.h1
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
                className="text-4xl sm:text-5xl lg:text-[3.5rem] xl:text-6xl font-bold leading-[1.06] tracking-tight mb-7"
                style={{ color: "oklch(0.97 0.005 270)" }}
              >
                Dein KI-Assistent für{" "}
                <TypingWords words={["intelligente", "persönliche", "automatisierte", "skalierbare"]} />{" "}
                Kundenkommunikation
              </motion.h1>

              <motion.p
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.25 }}
                className="text-lg lg:text-xl leading-relaxed mb-9 max-w-xl"
                style={{ color: "oklch(0.65 0.015 270)" }}
              >
                ARIIA beantwortet Kundenanfragen über WhatsApp, Telegram und Voice – rund um die Uhr, persönlich und intelligent. Für Fitness Studios, Personal Trainer und KMUs.
              </motion.p>

              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6, delay: 0.35 }}
                className="flex flex-wrap gap-4"
              >
                <Link href="/register">
                  <Button className="text-base px-8 py-3.5 rounded-lg h-auto group" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                    14 Tage kostenlos testen
                    <motion.span className="ml-2 inline-block" animate={{ x: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity }}>
                      <ArrowRight size={16} />
                    </motion.span>
                  </Button>
                </Link>
                <Link href="/features">
                  <Button variant="outline" className="text-base px-8 py-3.5 rounded-lg h-auto bg-transparent group"
                    style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.8 0.01 270)" }}>
                    Features entdecken
                    <ChevronRight size={16} className="ml-1 transition-transform group-hover:translate-x-1" />
                  </Button>
                </Link>
              </motion.div>

              {/* Trust badges */}
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.6, delay: 0.5 }}
                className="flex items-center gap-6 mt-10"
              >
                {["DSGVO-konform", "Made in Germany", "Enterprise-Ready"].map((badge, i) => (
                  <motion.span
                    key={badge}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + i * 0.1 }}
                    className="flex items-center gap-1.5 text-xs font-medium"
                    style={{ color: "oklch(0.55 0.015 270)" }}
                  >
                    <CheckCircle2 size={13} style={{ color: "oklch(0.62 0.22 292 / 0.7)" }} />
                    {badge}
                  </motion.span>
                ))}
              </motion.div>
            </div>

            {/* Right: Dashboard Mockup with parallax */}
            <motion.div
              initial={{ opacity: 0, scale: 0.88, rotateY: -10 }}
              animate={{ opacity: 1, scale: 1, rotateY: 0 }}
              transition={{ duration: 1.2, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
              style={{ perspective: "1200px", scale: dashboardScale }}
              className="relative hidden lg:block"
            >
              <div className="relative rounded-2xl overflow-hidden"
                style={{ border: "1px solid oklch(0.62 0.22 292 / 0.25)", boxShadow: "0 0 50px oklch(0.62 0.22 292 / 0.15)" }}>
                <img src={IMG_DASHBOARD} alt="ARIIA Studio Deck Dashboard" className="w-full h-auto" loading="eager" />
                <div className="absolute inset-0 pointer-events-none"
                  style={{ background: "linear-gradient(180deg, transparent 60%, oklch(0.09 0.04 270 / 0.5))" }} />
              </div>

              {/* Floating status badge */}
              <motion.div
                initial={{ opacity: 0, y: 20, x: -20 }}
                animate={{ opacity: 1, y: 0, x: 0 }}
                transition={{ duration: 0.6, delay: 1 }}
                className="absolute -bottom-5 -left-5 rounded-xl px-5 py-3.5 flex items-center gap-3 backdrop-blur-md"
                style={{ background: "oklch(0.12 0.04 270 / 0.8)", border: "1px solid oklch(0.62 0.22 292 / 0.2)" }}
              >
                <motion.div
                  className="w-9 h-9 rounded-full flex items-center justify-center"
                  style={{ background: "oklch(0.62 0.22 292 / 0.15)" }}
                  animate={{ scale: [1, 1.1, 1] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <CheckCircle2 size={18} style={{ color: "oklch(0.62 0.22 292)" }} />
                </motion.div>
                <div>
                  <div className="text-sm font-semibold" style={{ color: "oklch(0.95 0.005 270)" }}>All Systems Online</div>
                  <div className="text-xs" style={{ color: "oklch(0.55 0.015 270)" }}>180 Mitglieder synchronisiert</div>
                </div>
              </motion.div>

              {/* Floating KPI badge */}
              <motion.div
                initial={{ opacity: 0, y: -20, x: 20 }}
                animate={{ opacity: 1, y: 0, x: 0 }}
                transition={{ duration: 0.6, delay: 1.2 }}
                className="absolute -top-4 -right-4 rounded-xl px-4 py-3 text-center backdrop-blur-md"
                style={{ background: "oklch(0.62 0.22 292 / 0.15)", border: "1px solid oklch(0.62 0.22 292 / 0.3)" }}
              >
                <motion.div
                  className="text-2xl font-bold"
                  style={{ color: "oklch(0.72 0.2 292)" }}
                  animate={{ scale: [1, 1.05, 1] }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  98,7%
                </motion.div>
                <div className="text-xs" style={{ color: "oklch(0.9 0.01 270)" }}>AI Resolution Rate</div>
              </motion.div>
            </motion.div>
          </div>
        </motion.div>
      </section>

      {/* ═══════════════════ LOGO TICKER ═══════════════════ */}
      <div className="py-8 overflow-hidden relative" style={{ borderTop: "1px solid oklch(0.18 0.04 270)", borderBottom: "1px solid oklch(0.18 0.04 270)" }}>
        <div className="absolute left-0 top-0 bottom-0 w-24 z-10" style={{ background: "linear-gradient(90deg, oklch(0.09 0.04 270), transparent)" }} />
        <div className="absolute right-0 top-0 bottom-0 w-24 z-10" style={{ background: "linear-gradient(270deg, oklch(0.09 0.04 270), transparent)" }} />
        <motion.div
          className="flex gap-16 items-center whitespace-nowrap"
          animate={{ x: [0, -600] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        >
          {[...logos, ...logos, ...logos].map((logo, i) => (
            <span key={i} className="text-sm font-semibold tracking-wider uppercase opacity-40" style={{ color: logo.color }}>
              {logo.name}
            </span>
          ))}
        </motion.div>
      </div>

      {/* ═══════════════════ STATS BAR ═══════════════════ */}
      <Section className="py-20 lg:py-24 relative">
        <div className="container mx-auto px-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 lg:gap-12">
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.12 }}
                className="text-center group"
              >
                <div className="flex justify-center mb-4">
                  <motion.div
                    className="w-12 h-12 rounded-xl flex items-center justify-center"
                    style={{ background: "oklch(0.62 0.22 292 / 0.1)", border: "1px solid oklch(0.62 0.22 292 / 0.15)" }}
                    whileHover={{ scale: 1.15, rotate: 5 }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <s.icon size={20} style={{ color: "oklch(0.62 0.22 292)" }} />
                  </motion.div>
                </div>
                <div className="text-3xl lg:text-4xl font-bold tracking-tight mb-1" style={{ color: "oklch(0.97 0.005 270)" }}>
                  <Counter value={s.value} suffix={s.suffix} />
                </div>
                <div className="text-sm" style={{ color: "oklch(0.55 0.015 270)" }}>{s.label}</div>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══════════════════ FEATURES GRID ═══════════════════ */}
      <Section className="py-24 lg:py-32">
        <div className="container mx-auto px-4">
          <div className="text-center mb-16 lg:mb-20">
            <motion.span
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="inline-block text-xs font-semibold uppercase tracking-widest mb-4"
              style={{ color: "oklch(0.62 0.22 292)" }}
            >
              Plattform-Features
            </motion.span>
            <h2 className="text-3xl lg:text-5xl font-bold tracking-tight mb-5" style={{ color: "oklch(0.97 0.005 270)" }}>
              Alles, was dein Business <span style={{ color: "oklch(0.62 0.22 292)" }}>braucht</span>
            </h2>
            <p className="text-lg max-w-2xl mx-auto" style={{ color: "oklch(0.6 0.015 270)" }}>
              ARIIA vereint modernste KI-Technologie mit einer intuitiven Plattform – gebaut für Unternehmen, die ihre Kundenkommunikation transformieren wollen.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 lg:gap-6">
            {features.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="rounded-2xl p-7 lg:p-8 group hover:scale-[1.03] transition-all duration-300 relative overflow-hidden backdrop-blur-sm"
                style={{ background: "oklch(0.12 0.04 270 / 0.5)", border: "1px solid oklch(0.22 0.04 270)" }}
              >
                {/* Hover glow */}
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                  style={{ background: `radial-gradient(circle at 30% 30%, ${f.color}08, transparent 70%)` }} />
                <motion.div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                  style={{ background: `${f.color}15`, border: `1px solid ${f.color}20` }}
                  whileHover={{ scale: 1.15, rotate: -5 }}
                >
                  <f.icon size={22} style={{ color: f.color }} />
                </motion.div>
                <h3 className="text-lg font-bold mb-2.5 relative z-10" style={{ color: "oklch(0.95 0.005 270)" }}>
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed relative z-10" style={{ color: "oklch(0.6 0.015 270)" }}>
                  {f.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </Section>

      {/* ═══════════════════ FINAL CTA ═══════════════════ */}
      <Section className="py-28 lg:py-36 relative overflow-hidden">
        {/* Animated background */}
        <motion.div
          className="absolute inset-0 pointer-events-none"
          animate={{
            background: [
              "radial-gradient(ellipse 60% 50% at 50% 50%, oklch(0.62 0.22 292 / 0.06), transparent)",
              "radial-gradient(ellipse 60% 50% at 50% 50%, oklch(0.62 0.22 292 / 0.05), transparent)",
              "radial-gradient(ellipse 60% 50% at 50% 50%, oklch(0.62 0.22 292 / 0.06), transparent)",
            ],
          }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
        />
        <div className="container mx-auto px-4 text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-6" style={{ color: "oklch(0.97 0.005 270)" }}>
              Bereit, deine Kundenkommunikation zu{" "}
              <span style={{ color: "oklch(0.62 0.22 292)" }}>transformieren</span>?
            </h2>
            <p className="text-lg max-w-2xl mx-auto mb-10" style={{ color: "oklch(0.6 0.015 270)" }}>
              Starte jetzt mit der 14-tägigen kostenlosen Testphase. Kein Risiko, keine Kreditkarte erforderlich.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link href="/register">
                <Button className="text-base px-9 py-4 rounded-xl h-auto text-lg group" style={{ backgroundColor: "oklch(0.62 0.22 292)", color: "white" }}>
                  Jetzt kostenlos starten
                  <motion.span className="ml-2 inline-block" animate={{ x: [0, 4, 0] }} transition={{ duration: 1.5, repeat: Infinity }}>
                    <ArrowRight size={18} />
                  </motion.span>
                </Button>
              </Link>
              <Link href="/pricing">
                <Button variant="outline" className="text-base px-9 py-4 rounded-xl h-auto text-lg bg-transparent group"
                  style={{ borderColor: "oklch(0.28 0.04 270)", color: "oklch(0.8 0.01 270)" }}>
                  Pläne vergleichen
                  <ChevronRight size={18} className="ml-1 transition-transform group-hover:translate-x-1" />
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
