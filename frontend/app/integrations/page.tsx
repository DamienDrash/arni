"use client";

import React, { useMemo, useState, type CSSProperties } from "react";
import { useRouter } from "next/navigation";
import {
  Database, ShoppingBag, ShoppingCart, MessageSquare, Phone, Mail,
  Send, CreditCard, Calendar, Mic, Volume2, BookOpen, Globe,
  ArrowRight, ExternalLink, Search, Sparkles, Check, Clock,
  Zap, Users, Activity,
} from "lucide-react";
import { T } from "@/lib/tokens";
import { useI18n } from "@/lib/i18n/LanguageContext";

// ─── Types ────────────────────────────────────────────────────────────────────

type CategoryId =
  | "all"
  | "members_crm"
  | "ecommerce"
  | "messaging"
  | "payments"
  | "scheduling"
  | "ai"
  | "knowledge";

type IntegrationType = "deep" | "simple" | "coming_soon";

interface IntegrationDef {
  id: string;
  name: string;
  description: string;
  category: Exclude<CategoryId, "all">;
  icon: React.ReactNode;
  color: string;
  type: IntegrationType;
  href?: string;       // deep: navigate to this page
  popular?: boolean;
}

// ─── Category definitions ─────────────────────────────────────────────────────

const CATEGORIES: { id: CategoryId; label: string }[] = [
  { id: "all",         label: "Alle" },
  { id: "members_crm", label: "Mitglieder & CRM" },
  { id: "ecommerce",   label: "E-Commerce" },
  { id: "messaging",   label: "Kommunikation" },
  { id: "payments",    label: "Zahlungen" },
  { id: "scheduling",  label: "Buchung" },
  { id: "ai",          label: "KI & Sprache" },
  { id: "knowledge",   label: "Wissensbasis" },
];

// ─── Integration catalogue ────────────────────────────────────────────────────

const INTEGRATIONS: IntegrationDef[] = [
  // ── Mitglieder & CRM ──────────────────────────────────────────────────────
  {
    id: "magicline",
    name: "Magicline",
    description: "Mitgliederverwaltung, Buchungen und vollständiger Kontakt-Sync für Fitnessstudios.",
    category: "members_crm",
    icon: <Database size={22} />,
    color: "#00D68F",
    type: "deep",
    href: "/magicline",
    popular: true,
  },
  {
    id: "hubspot",
    name: "HubSpot",
    description: "CRM-Daten, Deals und Kontakte mit HubSpot synchronisieren.",
    category: "members_crm",
    icon: <Users size={22} />,
    color: "#FF7A59",
    type: "deep",
    href: "/sync",
  },
  {
    id: "salesforce",
    name: "Salesforce",
    description: "Enterprise-CRM-Sync für Kontakte, Leads und Opportunities.",
    category: "members_crm",
    icon: <Activity size={22} />,
    color: "#00A1E0",
    type: "coming_soon",
  },

  // ── E-Commerce ────────────────────────────────────────────────────────────
  {
    id: "shopify",
    name: "Shopify",
    description: "Kunden, Bestellungen und Produkte aus Shopify synchronisieren.",
    category: "ecommerce",
    icon: <ShoppingBag size={22} />,
    color: "#96BF48",
    type: "deep",
    href: "/sync",
  },
  {
    id: "woocommerce",
    name: "WooCommerce",
    description: "WordPress-Shop-Daten und Kundensync über WooCommerce.",
    category: "ecommerce",
    icon: <ShoppingCart size={22} />,
    color: "#7B2D8E",
    type: "deep",
    href: "/sync",
  },

  // ── Kommunikation ─────────────────────────────────────────────────────────
  {
    id: "whatsapp",
    name: "WhatsApp Business",
    description: "WhatsApp Business API für automatisierte Kundenkommunikation.",
    category: "messaging",
    icon: <MessageSquare size={22} />,
    color: "#25D366",
    type: "simple",
    href: "/settings/integrations",
    popular: true,
  },
  {
    id: "telegram",
    name: "Telegram",
    description: "Telegram-Bot für automatisierte Nachrichten und Befehle.",
    category: "messaging",
    icon: <Send size={22} />,
    color: "#0088CC",
    type: "simple",
    href: "/settings/integrations",
  },
  {
    id: "twilio",
    name: "Twilio SMS",
    description: "SMS-Versand und Empfang über Twilio.",
    category: "messaging",
    icon: <Phone size={22} />,
    color: "#F22F46",
    type: "simple",
    href: "/settings/integrations",
  },
  {
    id: "email",
    name: "E-Mail (SMTP/IMAP)",
    description: "Eigenen E-Mail-Server oder Postmark für transaktionale E-Mails.",
    category: "messaging",
    icon: <Mail size={22} />,
    color: "#EA4335",
    type: "simple",
    href: "/settings/integrations",
  },

  // ── Zahlungen ─────────────────────────────────────────────────────────────
  {
    id: "stripe",
    name: "Stripe",
    description: "Zahlungen, Abonnements und Rechnungen über Stripe verwalten.",
    category: "payments",
    icon: <CreditCard size={22} />,
    color: "#635BFF",
    type: "simple",
    href: "/settings/integrations",
    popular: true,
  },
  {
    id: "mollie",
    name: "Mollie",
    description: "Europäische Zahlungslösung für Online-Transaktionen.",
    category: "payments",
    icon: <CreditCard size={22} />,
    color: "#00A88E",
    type: "simple",
    href: "/settings/integrations",
  },

  // ── Buchung ───────────────────────────────────────────────────────────────
  {
    id: "calendly",
    name: "Calendly",
    description: "Terminbuchungen mit Calendly automatisieren.",
    category: "scheduling",
    icon: <Calendar size={22} />,
    color: "#006BFF",
    type: "simple",
    href: "/settings/integrations",
  },
  {
    id: "cal",
    name: "Cal.com",
    description: "Open-Source-Terminplanung und Buchungsverwaltung.",
    category: "scheduling",
    icon: <Calendar size={22} />,
    color: "#111827",
    type: "simple",
    href: "/settings/integrations",
  },

  // ── KI & Sprache ──────────────────────────────────────────────────────────
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    description: "Natürliche KI-Sprachsynthese für Voice-Agenten.",
    category: "ai",
    icon: <Volume2 size={22} />,
    color: "#8B5CF6",
    type: "simple",
    href: "/settings/integrations",
  },
  {
    id: "openai_whisper",
    name: "OpenAI Whisper",
    description: "Spracherkennung und Transkription über OpenAI Whisper.",
    category: "ai",
    icon: <Mic size={22} />,
    color: "#10A37F",
    type: "simple",
    href: "/settings/integrations",
  },

  // ── Wissensbasis ──────────────────────────────────────────────────────────
  {
    id: "notion",
    name: "Notion",
    description: "Notion-Seiten und Datenbanken in die Wissensbasis importieren.",
    category: "knowledge",
    icon: <BookOpen size={22} />,
    color: "#000000",
    type: "deep",
    href: "/settings/notion",
  },
];

// ─── Status badge (placeholder – could be fetched from API) ──────────────────

function StatusBadge({ type }: { type: IntegrationType }) {
  if (type === "coming_soon") {
    return (
      <span style={{
        fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
        textTransform: "uppercase",
        padding: "2px 8px", borderRadius: 20,
        background: T.surfaceAlt, color: T.textDim, border: `1px solid ${T.border}`,
      }}>
        Demnächst
      </span>
    );
  }
  return null;
}

// ─── Integration card ─────────────────────────────────────────────────────────

function IntegrationCard({ item, onAction }: { item: IntegrationDef; onAction: (item: IntegrationDef) => void }) {
  const [hovered, setHovered] = useState(false);
  const isComingSoon = item.type === "coming_soon";

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: T.surface,
        border: `1px solid ${hovered && !isComingSoon ? T.borderLight : T.border}`,
        borderRadius: 14,
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        transition: "border-color 0.2s, transform 0.15s",
        transform: hovered && !isComingSoon ? "translateY(-1px)" : "translateY(0)",
        cursor: isComingSoon ? "default" : "pointer",
        opacity: isComingSoon ? 0.6 : 1,
        position: "relative",
      }}
    >
      {/* Popular badge */}
      {item.popular && (
        <span style={{
          position: "absolute", top: 12, right: 12,
          fontSize: 10, fontWeight: 700, letterSpacing: "0.05em",
          textTransform: "uppercase", padding: "2px 7px",
          borderRadius: 20, background: T.accentDim, color: T.accentLight,
        }}>
          <Sparkles size={9} style={{ marginRight: 3, display: "inline", verticalAlign: "middle" }} />
          Beliebt
        </span>
      )}

      {/* Icon */}
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: `${item.color}18`,
        border: `1px solid ${item.color}30`,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: item.color, flexShrink: 0,
      }}>
        {item.icon}
      </div>

      {/* Name + description */}
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: T.text }}>{item.name}</span>
          <StatusBadge type={item.type} />
        </div>
        <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.5, margin: 0 }}>
          {item.description}
        </p>
      </div>

      {/* CTA */}
      {!isComingSoon && (
        <button
          onClick={() => onAction(item)}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 14px", borderRadius: 8,
            background: hovered ? T.accentDim : T.surfaceAlt,
            border: `1px solid ${hovered ? T.accent + "50" : T.border}`,
            color: hovered ? T.accentLight : T.textMuted,
            fontSize: 12, fontWeight: 600, cursor: "pointer",
            transition: "all 0.2s", alignSelf: "flex-start",
          }}
        >
          {item.type === "deep" ? (
            <>Öffnen <ArrowRight size={12} /></>
          ) : (
            <>Konfigurieren <ExternalLink size={12} /></>
          )}
        </button>
      )}

      {isComingSoon && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, color: T.textDim, fontSize: 12 }}>
          <Clock size={12} />
          In Kürze verfügbar
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function IntegrationsPage() {
  const router = useRouter();
  const [activeCategory, setActiveCategory] = useState<CategoryId>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return INTEGRATIONS.filter((item) => {
      const matchCat = activeCategory === "all" || item.category === activeCategory;
      const matchSearch = !search || item.name.toLowerCase().includes(search.toLowerCase());
      return matchCat && matchSearch;
    });
  }, [activeCategory, search]);

  const handleAction = (item: IntegrationDef) => {
    if (item.href) router.push(item.href);
  };

  // Group by category for section headers (only when "all" is selected)
  const grouped = useMemo(() => {
    if (activeCategory !== "all") return null;
    const groups: Record<string, IntegrationDef[]> = {};
    for (const item of filtered) {
      if (!groups[item.category]) groups[item.category] = [];
      groups[item.category].push(item);
    }
    return groups;
  }, [activeCategory, filtered]);

  const categoryLabel = (id: string) =>
    CATEGORIES.find((c) => c.id === id)?.label ?? id;

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: T.text, margin: 0 }}>
          Integrationen
        </h1>
        <p style={{ fontSize: 14, color: T.textMuted, marginTop: 6 }}>
          Verbinde ARIIA mit deinen bestehenden Systemen.
        </p>
      </div>

      {/* Search + Category filter */}
      <div style={{ display: "flex", gap: 12, marginBottom: 28, flexWrap: "wrap" }}>
        {/* Search */}
        <div style={{ position: "relative", flex: "0 0 240px" }}>
          <Search size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: T.textDim }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suchen…"
            style={{
              width: "100%", padding: "9px 12px 9px 34px",
              borderRadius: 10, background: T.surfaceAlt,
              border: `1px solid ${T.border}`, color: T.text,
              fontSize: 13, outline: "none", boxSizing: "border-box",
            }}
          />
        </div>

        {/* Category pills */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                style={{
                  padding: "7px 14px", borderRadius: 20,
                  background: isActive ? T.accent : T.surfaceAlt,
                  border: `1px solid ${isActive ? T.accent : T.border}`,
                  color: isActive ? "#fff" : T.textMuted,
                  fontSize: 12, fontWeight: isActive ? 600 : 500,
                  cursor: "pointer", transition: "all 0.15s",
                  whiteSpace: "nowrap",
                }}
              >
                {cat.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Grid – grouped by category when "Alle" is selected */}
      {grouped ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
          {Object.entries(grouped).map(([catId, items]) => (
            <div key={catId}>
              <h2 style={{
                fontSize: 11, fontWeight: 700, letterSpacing: "0.08em",
                textTransform: "uppercase", color: T.textDim,
                margin: "0 0 14px 0",
              }}>
                {categoryLabel(catId)}
              </h2>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 14,
              }}>
                {items.map((item) => (
                  <IntegrationCard key={item.id} item={item} onAction={handleAction} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: 14,
        }}>
          {filtered.length === 0 ? (
            <p style={{ color: T.textDim, fontSize: 14, gridColumn: "1/-1" }}>
              Keine Integrationen gefunden.
            </p>
          ) : (
            filtered.map((item) => (
              <IntegrationCard key={item.id} item={item} onAction={handleAction} />
            ))
          )}
        </div>
      )}
    </div>
  );
}
