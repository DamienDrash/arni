"use client";

import React, { useEffect, useMemo, useState, useRef, Fragment, type CSSProperties } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, Phone, Mail, Send, Globe, Camera, Facebook,
  CreditCard, Calendar, Mic, Volume2, Brain, BarChart3,
  Search, ArrowRight, ArrowLeft, Check, CheckCircle2, AlertCircle,
  Loader2, Zap, Key, BookOpen, Copy, Play, ExternalLink,
  Shield, Lock, Crown, RefreshCw, Settings, PlugZap, QrCode,
  Smartphone, Terminal, X, ChevronDown, Filter, Star, Sparkles,
  ShoppingBag, Users, Activity, Eye, EyeOff, Info, HelpCircle,
  MoreHorizontal, Power, Trash2, Link2, Unlink, Clock, TrendingUp,
} from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { FeatureGate } from "@/components/FeatureGate";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { usePermissions } from "@/lib/permissions";
import { useI18n } from "@/lib/i18n/LanguageContext";

// ══════════════════════════════════════════════════════════════════════════════
// TYPES
// ══════════════════════════════════════════════════════════════════════════════

type CategoryId = "messaging" | "payments" | "scheduling" | "ai_voice" | "analytics" | "members" | "crm";
type PlanTier = "starter" | "professional" | "pro" | "business" | "enterprise";
type IntegrationStatus = "connected" | "disconnected" | "error" | "pending";
type ViewState = "hub" | "onboarding" | "manage";

interface IntegrationDef {
  id: string;
  name: string;
  description: string;
  category: CategoryId;
  icon: React.ReactNode;
  color: string;
  minPlan: PlanTier;
  featureKey?: string;
  addonSlug?: string;
  tags: string[];
  popular?: boolean;
  comingSoon?: boolean;
  connectorId?: string;
  setupSteps: SetupStep[];
  docUrl?: string;
}

interface SetupStep {
  title: string;
  description: string;
  type: "info" | "config" | "test" | "complete";
  fields?: ConfigField[];
}

interface ConfigField {
  key: string;
  label: string;
  type: "text" | "password" | "select" | "toggle";
  placeholder?: string;
  helpText?: string;
  options?: string[];
  optional?: boolean;
  dependsOn?: string;
}

interface ConnectorStatus {
  id: string;
  status: IntegrationStatus;
  enabled: boolean;
  lastSync?: string;
}

// ══════════════════════════════════════════════════════════════════════════════
// ANIMATION PRESETS
// ══════════════════════════════════════════════════════════════════════════════

const fadeSlide = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] as const } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.06 } },
};

const staggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

// ══════════════════════════════════════════════════════════════════════════════
// SHARED STYLES
// ══════════════════════════════════════════════════════════════════════════════

const inputStyle: CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: 10,
  background: T.surfaceAlt,
  border: `1px solid ${T.border}`,
  color: T.text,
  fontSize: 13,
  outline: "none",
  transition: "border-color 0.2s",
};

const labelStyle: CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  color: T.textDim,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
  marginBottom: 6,
  display: "block",
};

// ══════════════════════════════════════════════════════════════════════════════
// CATEGORY DEFINITIONS
// ══════════════════════════════════════════════════════════════════════════════

const CATEGORIES: Array<{
  id: CategoryId | "all";
  label: string;
  labelDe: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  descriptionDe: string;
}> = [
  {
    id: "all",
    label: "All Integrations",
    labelDe: "Alle Integrationen",
    icon: <PlugZap size={16} />,
    color: T.accent,
    description: "Browse all available integrations",
    descriptionDe: "Alle verfügbaren Integrationen durchsuchen",
  },
  {
    id: "messaging",
    label: "Communication",
    labelDe: "Kommunikation",
    icon: <MessageSquare size={16} />,
    color: T.whatsapp,
    description: "Connect messaging channels for customer communication",
    descriptionDe: "Messaging-Kanäle für Kundenkommunikation verbinden",
  },
  {
    id: "payments",
    label: "Payments & Billing",
    labelDe: "Zahlungen & Abrechnung",
    icon: <CreditCard size={16} />,
    color: "#6772E5",
    description: "Process payments and manage invoices",
    descriptionDe: "Zahlungen verarbeiten und Rechnungen verwalten",
  },
  {
    id: "scheduling",
    label: "Scheduling & Booking",
    labelDe: "Termine & Buchungen",
    icon: <Calendar size={16} />,
    color: "#0069FF",
    description: "Let customers book appointments and meetings",
    descriptionDe: "Kunden Termine und Meetings buchen lassen",
  },
  {
    id: "ai_voice",
    label: "AI & Voice",
    labelDe: "KI & Sprache",
    icon: <Mic size={16} />,
    color: "#F97316",
    description: "Premium text-to-speech and speech recognition",
    descriptionDe: "Premium Text-to-Speech und Spracherkennung",
  },
  {
    id: "analytics",
    label: "Analytics",
    labelDe: "Analytik",
    icon: <BarChart3 size={16} />,
    color: "#8B5CF6",
    description: "Track and analyze customer interactions",
    descriptionDe: "Kundeninteraktionen verfolgen und analysieren",
  },
];

// ══════════════════════════════════════════════════════════════════════════════
// INTEGRATION DEFINITIONS
// ══════════════════════════════════════════════════════════════════════════════

const INTEGRATIONS: IntegrationDef[] = [
  // ── Communication ─────────────────────────────────────────────────────────
  {
    id: "whatsapp_web",
    name: "WhatsApp Web",
    description: "Connect via QR code scan — no API credentials needed",
    category: "messaging",
    icon: <MessageSquare size={20} />,
    color: "#25D366",
    minPlan: "starter",
    featureKey: "whatsapp",
    tags: ["messaging", "chat", "qr"],
    popular: true,
    connectorId: "whatsapp",
    setupSteps: [
      { title: "Overview", description: "WhatsApp Web connects via QR code — the simplest way to get started.", type: "info" },
      { title: "Scan QR Code", description: "Open WhatsApp on your phone and scan the QR code displayed here.", type: "config", fields: [
        { key: "mode", label: "Connection Mode", type: "select", options: ["qr"], helpText: "QR mode is available on all plans" },
      ]},
      { title: "Verify Connection", description: "We'll verify your WhatsApp connection is active.", type: "test" },
      { title: "Ready!", description: "WhatsApp Web is connected and ready to receive messages.", type: "complete" },
    ],
  },
  {
    id: "whatsapp_api",
    name: "WhatsApp Business API",
    description: "Official Meta Cloud API for high-volume messaging",
    category: "messaging",
    icon: <MessageSquare size={20} />,
    color: "#25D366",
    minPlan: "professional",
    featureKey: "whatsapp",
    tags: ["messaging", "chat", "api", "meta"],
    popular: true,
    connectorId: "whatsapp",
    setupSteps: [
      { title: "Overview", description: "The WhatsApp Business API enables automated, high-volume messaging through Meta's Cloud API.", type: "info" },
      { title: "API Credentials", description: "Enter your Meta Business API credentials.", type: "config", fields: [
        { key: "mode", label: "Connection Mode", type: "select", options: ["api"], helpText: "API mode requires Professional plan or higher" },
        { key: "phone_number_id", label: "Phone Number ID", type: "text", placeholder: "e.g. 123456789012345", helpText: "Found in Meta Business Suite > WhatsApp > API Setup" },
        { key: "access_token", label: "Permanent Access Token", type: "password", placeholder: "EAABs...", helpText: "Generate in Meta Business Suite > System Users" },
        { key: "verify_token", label: "Webhook Verify Token", type: "text", placeholder: "your-custom-verify-token", helpText: "Custom string for webhook verification" },
        { key: "app_secret", label: "App Secret", type: "password", placeholder: "abc123...", helpText: "Found in Meta Developers > App Settings > Basic" },
      ]},
      { title: "Test Connection", description: "We'll verify your API credentials and webhook configuration.", type: "test" },
      { title: "Connected!", description: "WhatsApp Business API is configured and ready for high-volume messaging.", type: "complete" },
    ],
    docUrl: "https://developers.facebook.com/docs/whatsapp/cloud-api/get-started",
  },
  {
    id: "telegram",
    name: "Telegram",
    description: "Connect a Telegram Bot for automated customer messaging",
    category: "messaging",
    icon: <Send size={20} />,
    color: "#0088CC",
    minPlan: "professional",
    featureKey: "telegram",
    tags: ["messaging", "chat", "bot"],
    popular: true,
    connectorId: "telegram",
    setupSteps: [
      { title: "Overview", description: "Create a Telegram Bot via @BotFather and connect it to ARIIA.", type: "info" },
      { title: "Bot Configuration", description: "Enter your Telegram Bot credentials.", type: "config", fields: [
        { key: "bot_token", label: "Bot Token", type: "password", placeholder: "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11", helpText: "Get this from @BotFather on Telegram" },
        { key: "admin_chat_id", label: "Admin Chat ID", type: "text", placeholder: "e.g. 123456789", helpText: "Optional: Your personal chat ID for admin notifications", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your bot token and set up the webhook.", type: "test" },
      { title: "Connected!", description: "Your Telegram Bot is live and ready to receive messages.", type: "complete" },
    ],
    docUrl: "https://core.telegram.org/bots#how-do-i-create-a-bot",
  },
  {
    id: "postmark",
    name: "Postmark",
    description: "Transactional email delivery with high deliverability",
    category: "messaging",
    icon: <Mail size={20} />,
    color: "#FFDE00",
    minPlan: "professional",
    featureKey: "email_channel",
    tags: ["email", "transactional", "notifications"],
    connectorId: "postmark",
    setupSteps: [
      { title: "Overview", description: "Postmark provides reliable transactional email delivery with excellent deliverability rates.", type: "info" },
      { title: "API Configuration", description: "Enter your Postmark server credentials.", type: "config", fields: [
        { key: "server_token", label: "Server API Token", type: "password", placeholder: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", helpText: "Found in Postmark > Servers > Your Server > API Tokens" },
        { key: "from_email", label: "Sender Email", type: "text", placeholder: "noreply@yourdomain.com", helpText: "Must be a verified sender signature in Postmark" },
        { key: "from_name", label: "Sender Name", type: "text", placeholder: "Your Company", helpText: "Display name for outgoing emails", optional: true },
      ]},
      { title: "Test Connection", description: "We'll send a test email to verify your configuration.", type: "test" },
      { title: "Connected!", description: "Postmark is configured for transactional email delivery.", type: "complete" },
    ],
    docUrl: "https://postmarkapp.com/developer",
  },
  {
    id: "smtp_email",
    name: "SMTP E-Mail",
    description: "Eigener SMTP-Server für E-Mail-Versand (Gmail, Outlook, eigener Server)",
    category: "messaging",
    icon: <Mail size={20} />,
    color: "#4FC3F7",
    minPlan: "starter",
    featureKey: "email_channel",
    tags: ["email", "smtp", "custom", "eigener server"],
    connectorId: "smtp_email",
    popular: true,
    setupSteps: [
      { title: "Übersicht", description: "Verbinden Sie Ihren eigenen SMTP-Server für den E-Mail-Versand. Unterstützt Gmail, Outlook, und jeden SMTP-kompatiblen Server.", type: "info" },
      { title: "SMTP-Konfiguration", description: "Geben Sie Ihre SMTP-Serverdaten ein.", type: "config", fields: [
        { key: "host", label: "SMTP Host", type: "text", placeholder: "smtp.gmail.com", helpText: "Hostname Ihres SMTP-Servers" },
        { key: "port", label: "Port", type: "text", placeholder: "587", helpText: "Standard: 587 (STARTTLS) oder 465 (SSL)" },
        { key: "username", label: "Benutzername", type: "text", placeholder: "user@example.com", helpText: "SMTP-Login (meist Ihre E-Mail-Adresse)" },
        { key: "password", label: "Passwort", type: "password", placeholder: "App-Passwort eingeben", helpText: "Bei Gmail: App-Passwort verwenden" },
        { key: "from_email", label: "Absender-E-Mail", type: "text", placeholder: "noreply@ihredomain.de", helpText: "Absenderadresse für ausgehende E-Mails" },
        { key: "from_name", label: "Absendername", type: "text", placeholder: "Ihr Unternehmen", helpText: "Anzeigename für ausgehende E-Mails", optional: true },
      ]},
      { title: "Verbindung testen", description: "Wir senden eine Test-E-Mail um die Konfiguration zu überprüfen.", type: "test" },
      { title: "Verbunden!", description: "SMTP E-Mail ist konfiguriert und bereit für den Versand.", type: "complete" },
    ],
  },
  {
    id: "twilio_sms",
    name: "Twilio SMS",
    description: "Send and receive SMS messages worldwide",
    category: "messaging",
    icon: <Smartphone size={20} />,
    color: "#F22F46",
    minPlan: "professional",
    featureKey: "sms",
    tags: ["sms", "text", "notifications"],
    connectorId: "sms",
    setupSteps: [
      { title: "Overview", description: "Twilio enables SMS messaging in 180+ countries with local and toll-free numbers.", type: "info" },
      { title: "Account Setup", description: "Enter your Twilio account credentials.", type: "config", fields: [
        { key: "account_sid", label: "Account SID", type: "text", placeholder: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", helpText: "Found on your Twilio Console Dashboard" },
        { key: "auth_token", label: "Auth Token", type: "password", placeholder: "your_auth_token", helpText: "Found on your Twilio Console Dashboard" },
        { key: "phone_number", label: "Twilio Phone Number", type: "text", placeholder: "+1234567890", helpText: "Your purchased Twilio phone number in E.164 format" },
      ]},
      { title: "Test Connection", description: "We'll verify your Twilio credentials and phone number.", type: "test" },
      { title: "Connected!", description: "Twilio SMS is active and ready for messaging.", type: "complete" },
    ],
    docUrl: "https://www.twilio.com/docs/sms",
  },
  {
    id: "twilio_voice",
    name: "Twilio Voice",
    description: "Inbound and outbound voice calls with AI integration",
    category: "messaging",
    icon: <Phone size={20} />,
    color: "#F22F46",
    minPlan: "professional",
    featureKey: "voice",
    tags: ["voice", "phone", "calls"],
    connectorId: "twilio_voice",
    setupSteps: [
      { title: "Overview", description: "Twilio Voice enables programmable phone calls with AI-powered voice agents.", type: "info" },
      { title: "Voice Configuration", description: "Configure your Twilio Voice settings.", type: "config", fields: [
        { key: "account_sid", label: "Account SID", type: "text", placeholder: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", helpText: "Same as your Twilio SMS Account SID" },
        { key: "auth_token", label: "Auth Token", type: "password", placeholder: "your_auth_token", helpText: "Same as your Twilio SMS Auth Token" },
        { key: "phone_number", label: "Voice Phone Number", type: "text", placeholder: "+1234567890", helpText: "Twilio number with voice capability enabled" },
        { key: "twiml_app_sid", label: "TwiML App SID", type: "text", placeholder: "APxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", helpText: "Optional: For advanced call routing", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your voice configuration.", type: "test" },
      { title: "Connected!", description: "Twilio Voice is configured for inbound and outbound calls.", type: "complete" },
    ],
    docUrl: "https://www.twilio.com/docs/voice",
  },
  {
    id: "instagram",
    name: "Instagram Messenger",
    description: "Respond to Instagram DMs automatically",
    category: "messaging",
    icon: <Camera size={20} />,
    color: "#E4405F",
    minPlan: "professional",
    featureKey: "instagram",
    tags: ["social", "messaging", "meta", "dm"],
    connectorId: "instagram",
    setupSteps: [
      { title: "Overview", description: "Connect your Instagram Business account to respond to DMs automatically.", type: "info" },
      { title: "Meta Configuration", description: "Enter your Instagram API credentials.", type: "config", fields: [
        { key: "page_id", label: "Instagram Business Account ID", type: "text", placeholder: "e.g. 17841400123456789", helpText: "Found in Meta Business Suite > Instagram Accounts" },
        { key: "access_token", label: "Page Access Token", type: "password", placeholder: "EAABs...", helpText: "Generate via Meta Graph API Explorer with instagram_manage_messages permission" },
      ]},
      { title: "Test Connection", description: "We'll verify your Instagram API access.", type: "test" },
      { title: "Connected!", description: "Instagram Messenger is live and responding to DMs.", type: "complete" },
    ],
    docUrl: "https://developers.facebook.com/docs/instagram-api/",
  },
  {
    id: "facebook",
    name: "Facebook Messenger",
    description: "Automate Facebook Page messaging",
    category: "messaging",
    icon: <Facebook size={20} />,
    color: "#1877F2",
    minPlan: "professional",
    featureKey: "facebook",
    tags: ["social", "messaging", "meta"],
    connectorId: "facebook",
    setupSteps: [
      { title: "Overview", description: "Connect your Facebook Page to automate Messenger conversations.", type: "info" },
      { title: "Page Configuration", description: "Enter your Facebook Page API credentials.", type: "config", fields: [
        { key: "page_id", label: "Facebook Page ID", type: "text", placeholder: "e.g. 123456789012345", helpText: "Found in Facebook Page Settings > About" },
        { key: "access_token", label: "Page Access Token", type: "password", placeholder: "EAABs...", helpText: "Generate via Meta Graph API with pages_messaging permission" },
      ]},
      { title: "Test Connection", description: "We'll verify your Facebook Page API access.", type: "test" },
      { title: "Connected!", description: "Facebook Messenger is live and automating conversations.", type: "complete" },
    ],
    docUrl: "https://developers.facebook.com/docs/messenger-platform/",
  },
  {
    id: "viber",
    name: "Viber",
    description: "Connect Viber Bot for messaging in Eastern Europe and Asia",
    category: "messaging",
    icon: <MessageSquare size={20} />,
    color: "#7360F2",
    minPlan: "business",
    tags: ["messaging", "chat", "bot"],
    connectorId: "viber",
    setupSteps: [
      { title: "Overview", description: "Viber is popular in Eastern Europe, Middle East and parts of Asia. Connect a Viber Bot to reach these markets.", type: "info" },
      { title: "Bot Configuration", description: "Enter your Viber Bot credentials.", type: "config", fields: [
        { key: "auth_token", label: "Bot Auth Token", type: "password", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxx-xxxx", helpText: "Get this from Viber Admin Panel > Create Bot Account" },
        { key: "bot_name", label: "Bot Name", type: "text", placeholder: "Your Company Bot", helpText: "Display name for your Viber Bot" },
        { key: "bot_avatar", label: "Bot Avatar URL", type: "text", placeholder: "https://...", helpText: "URL to your bot's avatar image", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your Viber Bot token and set up the webhook.", type: "test" },
      { title: "Connected!", description: "Viber Bot is live and ready for messaging.", type: "complete" },
    ],
    docUrl: "https://developers.viber.com/docs/api/rest-bot-api/",
  },
  {
    id: "google_business",
    name: "Google Business Messages",
    description: "Respond to customers directly from Google Search and Maps",
    category: "messaging",
    icon: <Globe size={20} />,
    color: "#4285F4",
    minPlan: "business",
    featureKey: "google_business",
    tags: ["messaging", "google", "search"],
    connectorId: "google_business",
    setupSteps: [
      { title: "Overview", description: "Google Business Messages lets customers message you directly from Google Search and Maps results.", type: "info" },
      { title: "API Configuration", description: "Enter your Google Business Messages credentials.", type: "config", fields: [
        { key: "service_account_json", label: "Service Account JSON", type: "password", placeholder: "Paste your service account JSON", helpText: "Download from Google Cloud Console > IAM > Service Accounts" },
        { key: "agent_id", label: "Agent ID", type: "text", placeholder: "brands/xxx/agents/yyy", helpText: "Found in Business Communications Console" },
      ]},
      { title: "Test Connection", description: "We'll verify your Google Business Messages configuration.", type: "test" },
      { title: "Connected!", description: "Google Business Messages is active.", type: "complete" },
    ],
    docUrl: "https://developers.google.com/business-communications",
  },
  {
    id: "line",
    name: "LINE",
    description: "Connect LINE Messaging API for Japan, Thailand and Taiwan",
    category: "messaging",
    icon: <MessageSquare size={20} />,
    color: "#00B900",
    minPlan: "business",
    tags: ["messaging", "chat", "asia"],
    connectorId: "line",
    setupSteps: [
      { title: "Overview", description: "LINE is the dominant messaging platform in Japan, Thailand, and Taiwan with 200M+ users.", type: "info" },
      { title: "Channel Configuration", description: "Enter your LINE Messaging API credentials.", type: "config", fields: [
        { key: "channel_access_token", label: "Channel Access Token", type: "password", placeholder: "your-channel-access-token", helpText: "Found in LINE Developers Console > Messaging API" },
        { key: "channel_secret", label: "Channel Secret", type: "password", placeholder: "your-channel-secret", helpText: "Found in LINE Developers Console > Basic Settings" },
      ]},
      { title: "Test Connection", description: "We'll verify your LINE channel configuration.", type: "test" },
      { title: "Connected!", description: "LINE Messaging is active and ready.", type: "complete" },
    ],
    docUrl: "https://developers.line.biz/en/docs/messaging-api/",
  },
  {
    id: "wechat",
    name: "WeChat",
    description: "Connect WeChat Official Account for the Chinese market",
    category: "messaging",
    icon: <MessageSquare size={20} />,
    color: "#07C160",
    minPlan: "enterprise",
    tags: ["messaging", "chat", "china"],
    comingSoon: true,
    connectorId: "wechat",
    setupSteps: [
      { title: "Overview", description: "WeChat is essential for reaching the Chinese market with 1.3B+ monthly active users.", type: "info" },
      { title: "Official Account Setup", description: "Configure your WeChat Official Account.", type: "config", fields: [
        { key: "app_id", label: "App ID", type: "text", placeholder: "wx...", helpText: "Found in WeChat Official Account Admin Platform" },
        { key: "app_secret", label: "App Secret", type: "password", placeholder: "your-app-secret", helpText: "Found in WeChat Official Account Admin Platform" },
        { key: "token", label: "Token", type: "text", placeholder: "your-custom-token", helpText: "Custom token for server verification" },
        { key: "encoding_aes_key", label: "Encoding AES Key", type: "password", placeholder: "43-char-key", helpText: "Message encryption key" },
      ]},
      { title: "Test Connection", description: "We'll verify your WeChat configuration.", type: "test" },
      { title: "Connected!", description: "WeChat Official Account is configured.", type: "complete" },
    ],
  },

  // ── Payments & Billing ────────────────────────────────────────────────────
  {
    id: "stripe",
    name: "Stripe",
    description: "Accept payments and manage subscriptions for your customers",
    category: "payments",
    icon: <CreditCard size={20} />,
    color: "#6772E5",
    minPlan: "professional",
    featureKey: "platform_integrations",
    tags: ["payments", "subscriptions", "invoices"],
    popular: true,
    connectorId: "stripe",
    setupSteps: [
      { title: "Overview", description: "Stripe enables you to accept payments, manage subscriptions, and send invoices to your customers.", type: "info" },
      { title: "API Keys", description: "Enter your Stripe API credentials.", type: "config", fields: [
        { key: "publishable_key", label: "Publishable Key", type: "text", placeholder: "pk_live_...", helpText: "Found in Stripe Dashboard > Developers > API Keys" },
        { key: "secret_key", label: "Secret Key", type: "password", placeholder: "sk_live_...", helpText: "Found in Stripe Dashboard > Developers > API Keys" },
        { key: "webhook_secret", label: "Webhook Signing Secret", type: "password", placeholder: "whsec_...", helpText: "Found in Stripe Dashboard > Developers > Webhooks", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your Stripe API keys and webhook configuration.", type: "test" },
      { title: "Connected!", description: "Stripe is configured and ready to process payments.", type: "complete" },
    ],
    docUrl: "https://stripe.com/docs/api",
  },
  {
    id: "paypal",
    name: "PayPal",
    description: "Accept PayPal payments from customers worldwide",
    category: "payments",
    icon: <CreditCard size={20} />,
    color: "#003087",
    minPlan: "business",
    featureKey: "platform_integrations",
    tags: ["payments", "checkout"],
    connectorId: "paypal",
    setupSteps: [
      { title: "Overview", description: "PayPal is trusted by millions of customers worldwide for secure online payments.", type: "info" },
      { title: "API Credentials", description: "Enter your PayPal REST API credentials.", type: "config", fields: [
        { key: "client_id", label: "Client ID", type: "text", placeholder: "AV...", helpText: "Found in PayPal Developer Dashboard > My Apps & Credentials" },
        { key: "client_secret", label: "Client Secret", type: "password", placeholder: "EL...", helpText: "Found in PayPal Developer Dashboard > My Apps & Credentials" },
        { key: "mode", label: "Environment", type: "select", options: ["sandbox", "live"], helpText: "Use sandbox for testing, live for production" },
      ]},
      { title: "Test Connection", description: "We'll verify your PayPal API access.", type: "test" },
      { title: "Connected!", description: "PayPal is configured and ready for payments.", type: "complete" },
    ],
    docUrl: "https://developer.paypal.com/docs/api/overview/",
  },
  {
    id: "mollie",
    name: "Mollie",
    description: "European payment provider with local payment methods",
    category: "payments",
    icon: <CreditCard size={20} />,
    color: "#000000",
    minPlan: "business",
    featureKey: "platform_integrations",
    tags: ["payments", "europe", "ideal", "sofort"],
    connectorId: "mollie",
    setupSteps: [
      { title: "Overview", description: "Mollie supports iDEAL, SOFORT, Bancontact, and other European payment methods.", type: "info" },
      { title: "API Key", description: "Enter your Mollie API key.", type: "config", fields: [
        { key: "api_key", label: "API Key", type: "password", placeholder: "live_...", helpText: "Found in Mollie Dashboard > Developers > API Keys" },
      ]},
      { title: "Test Connection", description: "We'll verify your Mollie API key.", type: "test" },
      { title: "Connected!", description: "Mollie is configured for European payments.", type: "complete" },
    ],
    docUrl: "https://docs.mollie.com/",
  },

  // ── Scheduling & Booking ──────────────────────────────────────────────────
  {
    id: "calendly",
    name: "Calendly",
    description: "Let customers book appointments and meetings",
    category: "scheduling",
    icon: <Calendar size={20} />,
    color: "#0069FF",
    minPlan: "professional",
    featureKey: "platform_integrations",
    tags: ["scheduling", "appointments", "booking"],
    popular: true,
    connectorId: "calendly",
    setupSteps: [
      { title: "Overview", description: "Calendly makes it easy for your customers to schedule appointments without back-and-forth emails.", type: "info" },
      { title: "API Configuration", description: "Enter your Calendly API credentials.", type: "config", fields: [
        { key: "api_key", label: "Personal Access Token", type: "password", placeholder: "eyJhb...", helpText: "Found in Calendly > Integrations > API & Webhooks" },
        { key: "organization_uri", label: "Organization URI", type: "text", placeholder: "https://api.calendly.com/organizations/...", helpText: "Your Calendly organization URL", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your Calendly API access.", type: "test" },
      { title: "Connected!", description: "Calendly is integrated — customers can now book appointments.", type: "complete" },
    ],
    docUrl: "https://developer.calendly.com/",
  },
  {
    id: "calcom",
    name: "Cal.com",
    description: "Open-source scheduling infrastructure",
    category: "scheduling",
    icon: <Calendar size={20} />,
    color: "#292929",
    minPlan: "professional",
    featureKey: "platform_integrations",
    tags: ["scheduling", "open-source", "booking"],
    connectorId: "calcom",
    setupSteps: [
      { title: "Overview", description: "Cal.com is an open-source scheduling platform with full API access and self-hosting options.", type: "info" },
      { title: "API Configuration", description: "Enter your Cal.com API credentials.", type: "config", fields: [
        { key: "api_key", label: "API Key", type: "password", placeholder: "cal_live_...", helpText: "Found in Cal.com > Settings > Developer > API Keys" },
        { key: "base_url", label: "Base URL", type: "text", placeholder: "https://api.cal.com/v1", helpText: "Default: https://api.cal.com/v1 — change for self-hosted", optional: true },
      ]},
      { title: "Test Connection", description: "We'll verify your Cal.com API access.", type: "test" },
      { title: "Connected!", description: "Cal.com is integrated for scheduling.", type: "complete" },
    ],
    docUrl: "https://cal.com/docs/api-reference",
  },
  {
    id: "acuity",
    name: "Acuity Scheduling",
    description: "Advanced appointment scheduling with payment integration",
    category: "scheduling",
    icon: <Calendar size={20} />,
    color: "#315B7D",
    minPlan: "business",
    featureKey: "platform_integrations",
    tags: ["scheduling", "appointments", "payments"],
    connectorId: "acuity",
    setupSteps: [
      { title: "Overview", description: "Acuity Scheduling (by Squarespace) offers advanced scheduling with built-in payment processing.", type: "info" },
      { title: "API Configuration", description: "Enter your Acuity API credentials.", type: "config", fields: [
        { key: "user_id", label: "User ID", type: "text", placeholder: "12345678", helpText: "Found in Acuity > Integrations > API" },
        { key: "api_key", label: "API Key", type: "password", placeholder: "your-api-key", helpText: "Found in Acuity > Integrations > API" },
      ]},
      { title: "Test Connection", description: "We'll verify your Acuity API access.", type: "test" },
      { title: "Connected!", description: "Acuity Scheduling is integrated.", type: "complete" },
    ],
    docUrl: "https://developers.acuityscheduling.com/",
  },

  // ── AI & Voice ────────────────────────────────────────────────────────────
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    description: "Premium AI voice synthesis with ultra-realistic voices",
    category: "ai_voice",
    icon: <Volume2 size={20} />,
    color: "#000000",
    minPlan: "business",
    addonSlug: "voice_pipeline",
    tags: ["tts", "voice", "ai", "premium"],
    popular: true,
    connectorId: "elevenlabs",
    setupSteps: [
      { title: "Overview", description: "ElevenLabs provides the most realistic AI voices available, supporting 29+ languages.", type: "info" },
      { title: "API Configuration", description: "Enter your ElevenLabs API credentials.", type: "config", fields: [
        { key: "api_key", label: "API Key", type: "password", placeholder: "xi-...", helpText: "Found in ElevenLabs > Profile > API Key" },
        { key: "voice_id", label: "Default Voice ID", type: "text", placeholder: "21m00Tcm4TlvDq8ikWAM", helpText: "Choose a voice from ElevenLabs Voice Library", optional: true },
        { key: "model_id", label: "Model", type: "select", options: ["eleven_multilingual_v2", "eleven_turbo_v2", "eleven_monolingual_v1"], helpText: "Multilingual v2 recommended for multi-language support" },
      ]},
      { title: "Test Connection", description: "We'll generate a test audio clip to verify your configuration.", type: "test" },
      { title: "Connected!", description: "ElevenLabs is configured for premium voice synthesis.", type: "complete" },
    ],
    docUrl: "https://elevenlabs.io/docs/api-reference",
  },
  {
    id: "openai_tts",
    name: "OpenAI TTS",
    description: "Text-to-speech powered by OpenAI's voice models",
    category: "ai_voice",
    icon: <Volume2 size={20} />,
    color: "#10A37F",
    minPlan: "professional",
    featureKey: "voice",
    tags: ["tts", "voice", "ai", "openai"],
    connectorId: "openai_tts",
    setupSteps: [
      { title: "Overview", description: "OpenAI TTS provides natural-sounding voice synthesis with multiple voice options.", type: "info" },
      { title: "API Configuration", description: "Enter your OpenAI API credentials.", type: "config", fields: [
        { key: "api_key", label: "OpenAI API Key", type: "password", placeholder: "sk-...", helpText: "Found in OpenAI Platform > API Keys" },
        { key: "voice", label: "Default Voice", type: "select", options: ["alloy", "echo", "fable", "onyx", "nova", "shimmer"], helpText: "Choose the default voice for TTS" },
        { key: "model", label: "Model", type: "select", options: ["tts-1", "tts-1-hd"], helpText: "HD model provides higher quality but is slower" },
      ]},
      { title: "Test Connection", description: "We'll generate a test audio clip.", type: "test" },
      { title: "Connected!", description: "OpenAI TTS is configured.", type: "complete" },
    ],
    docUrl: "https://platform.openai.com/docs/guides/text-to-speech",
  },
  {
    id: "openai_whisper",
    name: "OpenAI Whisper",
    description: "Speech-to-text transcription with high accuracy",
    category: "ai_voice",
    icon: <Mic size={20} />,
    color: "#10A37F",
    minPlan: "professional",
    featureKey: "voice",
    tags: ["stt", "transcription", "ai", "openai"],
    connectorId: "openai_whisper",
    setupSteps: [
      { title: "Overview", description: "OpenAI Whisper provides state-of-the-art speech recognition supporting 97 languages.", type: "info" },
      { title: "API Configuration", description: "Enter your OpenAI API credentials.", type: "config", fields: [
        { key: "api_key", label: "OpenAI API Key", type: "password", placeholder: "sk-...", helpText: "Found in OpenAI Platform > API Keys" },
        { key: "model", label: "Model", type: "select", options: ["whisper-1"], helpText: "Whisper v1 is the current production model" },
      ]},
      { title: "Test Connection", description: "We'll verify your API access.", type: "test" },
      { title: "Connected!", description: "OpenAI Whisper is configured for speech recognition.", type: "complete" },
    ],
    docUrl: "https://platform.openai.com/docs/guides/speech-to-text",
  },
  {
    id: "deepgram",
    name: "Deepgram",
    description: "Real-time speech-to-text with streaming support",
    category: "ai_voice",
    icon: <Mic size={20} />,
    color: "#13EF93",
    minPlan: "business",
    addonSlug: "voice_pipeline",
    tags: ["stt", "realtime", "streaming", "ai"],
    connectorId: "deepgram",
    setupSteps: [
      { title: "Overview", description: "Deepgram provides real-time speech recognition with streaming WebSocket support — ideal for live conversations.", type: "info" },
      { title: "API Configuration", description: "Enter your Deepgram API credentials.", type: "config", fields: [
        { key: "api_key", label: "API Key", type: "password", placeholder: "your-deepgram-api-key", helpText: "Found in Deepgram Console > API Keys" },
        { key: "model", label: "Model", type: "select", options: ["nova-2", "nova", "enhanced", "base"], helpText: "Nova-2 recommended for best accuracy" },
      ]},
      { title: "Test Connection", description: "We'll verify your Deepgram API access.", type: "test" },
      { title: "Connected!", description: "Deepgram is configured for real-time transcription.", type: "complete" },
    ],
    docUrl: "https://developers.deepgram.com/",
  },
  {
    id: "google_tts",
    name: "Google Cloud TTS",
    description: "Multi-language text-to-speech with WaveNet voices",
    category: "ai_voice",
    icon: <Volume2 size={20} />,
    color: "#4285F4",
    minPlan: "business",
    featureKey: "voice",
    tags: ["tts", "voice", "google", "wavenet"],
    connectorId: "google_tts",
    setupSteps: [
      { title: "Overview", description: "Google Cloud TTS offers 220+ voices in 40+ languages with WaveNet and Neural2 voice models.", type: "info" },
      { title: "API Configuration", description: "Enter your Google Cloud credentials.", type: "config", fields: [
        { key: "service_account_json", label: "Service Account JSON", type: "password", placeholder: "Paste your service account JSON", helpText: "Download from Google Cloud Console > IAM > Service Accounts" },
        { key: "language_code", label: "Default Language", type: "text", placeholder: "de-DE", helpText: "BCP-47 language code (e.g. de-DE, en-US, fr-FR)" },
      ]},
      { title: "Test Connection", description: "We'll generate a test audio clip.", type: "test" },
      { title: "Connected!", description: "Google Cloud TTS is configured.", type: "complete" },
    ],
    docUrl: "https://cloud.google.com/text-to-speech/docs",
  },
  {
    id: "azure_speech",
    name: "Azure Speech",
    description: "Enterprise-grade TTS and STT from Microsoft Azure",
    category: "ai_voice",
    icon: <Brain size={20} />,
    color: "#0078D4",
    minPlan: "business",
    featureKey: "voice",
    tags: ["tts", "stt", "azure", "enterprise"],
    connectorId: "azure_speech",
    setupSteps: [
      { title: "Overview", description: "Azure Speech Services provides enterprise-grade TTS and STT with custom voice and language model support.", type: "info" },
      { title: "API Configuration", description: "Enter your Azure Speech credentials.", type: "config", fields: [
        { key: "subscription_key", label: "Subscription Key", type: "password", placeholder: "your-subscription-key", helpText: "Found in Azure Portal > Speech Service > Keys and Endpoint" },
        { key: "region", label: "Service Region", type: "text", placeholder: "westeurope", helpText: "Azure region where your Speech resource is deployed" },
      ]},
      { title: "Test Connection", description: "We'll verify your Azure Speech configuration.", type: "test" },
      { title: "Connected!", description: "Azure Speech is configured for TTS and STT.", type: "complete" },
    ],
    docUrl: "https://learn.microsoft.com/azure/ai-services/speech-service/",
  },

  // ── Analytics ─────────────────────────────────────────────────────────────
  {
    id: "google_analytics",
    name: "Google Analytics",
    description: "Track customer interactions and conversion events",
    category: "analytics",
    icon: <TrendingUp size={20} />,
    color: "#E37400",
    minPlan: "professional",
    featureKey: "advanced_analytics",
    tags: ["analytics", "tracking", "google"],
    connectorId: "google_analytics",
    setupSteps: [
      { title: "Overview", description: "Send conversation events and conversion data to Google Analytics 4.", type: "info" },
      { title: "Configuration", description: "Enter your GA4 measurement details.", type: "config", fields: [
        { key: "measurement_id", label: "Measurement ID", type: "text", placeholder: "G-XXXXXXXXXX", helpText: "Found in GA4 > Admin > Data Streams" },
        { key: "api_secret", label: "API Secret", type: "password", placeholder: "your-api-secret", helpText: "Found in GA4 > Admin > Data Streams > Measurement Protocol" },
      ]},
      { title: "Test Connection", description: "We'll send a test event to verify your configuration.", type: "test" },
      { title: "Connected!", description: "Google Analytics is tracking conversation events.", type: "complete" },
    ],
    docUrl: "https://developers.google.com/analytics/devguides/collection/protocol/ga4",
  },
  {
    id: "mixpanel",
    name: "Mixpanel",
    description: "Product analytics for customer behavior insights",
    category: "analytics",
    icon: <BarChart3 size={20} />,
    color: "#7856FF",
    minPlan: "business",
    featureKey: "advanced_analytics",
    tags: ["analytics", "product", "events"],
    connectorId: "mixpanel",
    setupSteps: [
      { title: "Overview", description: "Mixpanel provides detailed product analytics to understand how customers interact with your services.", type: "info" },
      { title: "Configuration", description: "Enter your Mixpanel project credentials.", type: "config", fields: [
        { key: "project_token", label: "Project Token", type: "text", placeholder: "your-project-token", helpText: "Found in Mixpanel > Settings > Project Settings" },
        { key: "api_secret", label: "API Secret", type: "password", placeholder: "your-api-secret", helpText: "Found in Mixpanel > Settings > Project Settings", optional: true },
      ]},
      { title: "Test Connection", description: "We'll send a test event to Mixpanel.", type: "test" },
      { title: "Connected!", description: "Mixpanel is configured for product analytics.", type: "complete" },
    ],
    docUrl: "https://developer.mixpanel.com/",
  },
];

// ══════════════════════════════════════════════════════════════════════════════
// PLAN HIERARCHY
// ══════════════════════════════════════════════════════════════════════════════

const PLAN_ORDER: Record<string, number> = {
  trial: -1,
  starter: 0,
  pro: 1,
  professional: 1,
  business: 2,
  enterprise: 3,
};

const PLAN_LABELS: Record<string, string> = {
  trial: "Trial",
  starter: "Starter",
  pro: "Professional",
  professional: "Professional",
  business: "Business",
  enterprise: "Enterprise",
};

function isPlanSufficient(currentPlan: string | undefined, requiredPlan: PlanTier): boolean {
  if (!currentPlan) return false;
  const current = currentPlan.toLowerCase();
  const currentOrder = PLAN_ORDER[current as PlanTier] ?? -1;
  const requiredOrder = PLAN_ORDER[requiredPlan] ?? 99;
  return currentOrder >= requiredOrder;
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ══════════════════════════════════════════════════════════════════════════════

export default function SettingsIntegrationsPage() {
  const { t } = useI18n();
  const { feature, plan, hasAddon, loading: permLoading } = usePermissions();

  // ── State ──────────────────────────────────────────────────────────────────
  const [view, setView] = useState<ViewState>("hub");
  const [activeCategory, setActiveCategory] = useState<CategoryId | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "available" | "connected" | "locked">("all");
  const [selectedIntegration, setSelectedIntegration] = useState<IntegrationDef | null>(null);
  const [onboardingStep, setOnboardingStep] = useState(0);

  // Connector state
  const [connectorCatalog, setConnectorCatalog] = useState<any[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});
  const [configSaving, setConfigSaving] = useState(false);
  const [configTesting, setConfigTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});
  const [setupDocs, setSetupDocs] = useState<string>("");

  // ── Data Fetching ──────────────────────────────────────────────────────────
  async function fetchCatalog() {
    setCatalogLoading(true);
    try {
      const res = await apiFetch("/admin/connector-hub/catalog");
      if (res.ok) setConnectorCatalog(await res.json());
    } catch { /* best effort */ }
    finally { setCatalogLoading(false); }
  }

  useEffect(() => { fetchCatalog(); }, []);

  // ── Derived State ──────────────────────────────────────────────────────────
  const connectedIds = useMemo(() => {
    return new Set(connectorCatalog.filter(c => c.status === "connected").map(c => c.id));
  }, [connectorCatalog]);

  const filteredIntegrations = useMemo(() => {
    let list = INTEGRATIONS;
    if (activeCategory !== "all") {
      list = list.filter(i => i.category === activeCategory);
    }
    if (statusFilter !== "all") {
      list = list.filter(i => {
        const accessible = isIntegrationAccessible(i);
        const connected = i.connectorId ? connectedIds.has(i.connectorId) : false;
        if (statusFilter === "connected") return connected;
        if (statusFilter === "available") return accessible && !connected;
        if (statusFilter === "locked") return !accessible;
        return true;
      });
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(i =>
        i.name.toLowerCase().includes(q) ||
        i.description.toLowerCase().includes(q) ||
        i.tags.some(tag => tag.includes(q))
      );
    }
    return list;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeCategory, searchQuery, statusFilter, connectedIds, plan]);

  const connectedCount = connectedIds.size;
  const availableCount = INTEGRATIONS.filter(i => isIntegrationAccessible(i)).length;

  // ── Handlers ───────────────────────────────────────────────────────────────
  function startOnboarding(integration: IntegrationDef) {
    setSelectedIntegration(integration);
    setOnboardingStep(0);
    setConfigValues({});
    setTestResult(null);
    setShowPassword({});
    setSetupDocs("");
    setView("onboarding");

    // Load existing config if connector exists
    if (integration.connectorId) {
      loadExistingConfig(integration.connectorId);
    }
  }

  async function loadExistingConfig(connectorId: string) {
    try {
      const res = await apiFetch(`/admin/connector-hub/${connectorId}/config`);
      if (res.ok) {
        const data = await res.json();
        setConfigValues(data);
      }
    } catch { /* best effort */ }
  }

  async function saveConfig() {
    if (!selectedIntegration?.connectorId) return false;
    setConfigSaving(true);
    try {
      const res = await apiFetch(`/admin/connector-hub/${selectedIntegration.connectorId}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...configValues, enabled: true }),
      });
      if (res.ok) {
        fetchCatalog();
        return true;
      }
      return false;
    } finally {
      setConfigSaving(false);
    }
  }

  async function testConnection() {
    if (!selectedIntegration?.connectorId) return;
    setConfigTesting(true);
    setTestResult(null);
    try {
      await saveConfig();
      const res = await apiFetch(`/admin/connector-hub/${selectedIntegration.connectorId}/test`, {
        method: "POST",
      });
      if (res.ok) {
        const result = await res.json();
        setTestResult(result);
      } else {
        setTestResult({ status: "error", message: "Connection test failed" });
      }
    } catch {
      setTestResult({ status: "error", message: "Network error" });
    } finally {
      setConfigTesting(false);
    }
  }

  async function disconnectIntegration(connectorId: string) {
    try {
      await apiFetch(`/admin/connector-hub/${connectorId}/config`, {
        method: "DELETE",
      });
      fetchCatalog();
    } catch { /* best effort */ }
  }

  function isIntegrationAccessible(integration: IntegrationDef): boolean {
    const planOk = isPlanSufficient(plan?.slug, integration.minPlan);
    // Feature keys that are actually plan-gated (not separate feature flags)
    const planGatedFeatures = ["platform_integrations"];
    const featureOk = integration.featureKey
      ? planGatedFeatures.includes(integration.featureKey)
        ? planOk  // For plan-gated features, plan check is sufficient
        : feature(integration.featureKey)
      : true;
    const addonOk = integration.addonSlug ? hasAddon(integration.addonSlug) : true;
    return planOk && (featureOk || addonOk);
  }

  function getIntegrationStatus(integration: IntegrationDef): IntegrationStatus {
    if (integration.connectorId && connectedIds.has(integration.connectorId)) return "connected";
    return "disconnected";
  }

  // ══════════════════════════════════════════════════════════════════════════
  // HUB VIEW
  // ══════════════════════════════════════════════════════════════════════════

  function renderHub() {
    return (
      <motion.div {...fadeSlide} key="hub" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Hero Section */}
        <div
          style={{
            position: "relative",
            padding: "36px 32px",
            borderRadius: 20,
            background: `linear-gradient(135deg, ${T.surface} 0%, ${T.surfaceAlt} 100%)`,
            border: `1px solid ${T.border}`,
            overflow: "hidden",
          }}
        >
          <div style={{ position: "absolute", top: -60, right: -40, width: 200, height: 200, borderRadius: "50%", background: `radial-gradient(circle, ${T.accentDim} 0%, transparent 70%)`, pointerEvents: "none" }} />
          <div style={{ position: "absolute", bottom: -80, left: -20, width: 160, height: 160, borderRadius: "50%", background: `radial-gradient(circle, ${T.infoDim} 0%, transparent 70%)`, pointerEvents: "none" }} />

          <div style={{ position: "relative", zIndex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
              <div style={{ width: 48, height: 48, borderRadius: 14, background: T.accentDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.accent }}>
                <PlugZap size={24} />
              </div>
              <div>
                <h1 style={{ fontSize: 24, fontWeight: 800, color: T.text, margin: 0, letterSpacing: "-0.03em" }}>
                  {t("integrations.hub.title")}
                </h1>
                <p style={{ fontSize: 13, color: T.textMuted, margin: 0 }}>
                  {t("integrations.hub.subtitle")}
                </p>
              </div>
            </div>

            {/* Quick Stats */}
            <div style={{ display: "flex", gap: 20, marginTop: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.success }} />
                <span style={{ fontSize: 13, color: T.textMuted }}>
                  <strong style={{ color: T.text }}>{connectedCount}</strong> {t("integrations.hub.connected")}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.accent }} />
                <span style={{ fontSize: 13, color: T.textMuted }}>
                  <strong style={{ color: T.text }}>{availableCount}</strong> {t("integrations.hub.available")}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.warning }} />
                <span style={{ fontSize: 13, color: T.textMuted }}>
                  <strong style={{ color: T.text }}>{INTEGRATIONS.length}</strong> {t("integrations.hub.total")}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Search + Status Filter */}
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ position: "relative", flex: 1 }}>
            <Search size={15} style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", color: T.textDim }} />
            <input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t("integrations.hub.searchPlaceholder")}
              style={{ ...inputStyle, paddingLeft: 38 }}
            />
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            {([
              { id: "all" as const, label: t("integrations.filter.all"), icon: <Filter size={13} />, count: INTEGRATIONS.length },
              { id: "available" as const, label: t("integrations.filter.available"), icon: <Check size={13} />, count: availableCount },
              { id: "connected" as const, label: t("integrations.filter.connected"), icon: <CheckCircle2 size={13} />, count: connectedCount },
              { id: "locked" as const, label: t("integrations.filter.locked"), icon: <Lock size={13} />, count: INTEGRATIONS.length - availableCount },
            ]).map((f) => {
              const active = statusFilter === f.id;
              return (
                <button
                  key={f.id}
                  onClick={() => setStatusFilter(f.id)}
                  style={{
                    display: "flex", alignItems: "center", gap: 5,
                    padding: "7px 12px", borderRadius: 8,
                    background: active ? T.accentDim : T.surface,
                    border: `1px solid ${active ? T.accent + "44" : T.border}`,
                    color: active ? T.accent : T.textMuted,
                    fontSize: 11, fontWeight: 600, cursor: "pointer",
                    transition: "all 0.2s", whiteSpace: "nowrap",
                  }}
                >
                  {f.icon}
                  {f.label}
                  <span style={{ fontSize: 9, fontWeight: 700, background: active ? T.accent + "22" : T.surfaceAlt, padding: "1px 5px", borderRadius: 4 }}>
                    {f.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Category Tabs */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {CATEGORIES.map((cat) => {
            const isActive = activeCategory === cat.id;
            const count = cat.id === "all" ? INTEGRATIONS.length : INTEGRATIONS.filter(i => i.category === cat.id).length;
            return (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id as CategoryId | "all")}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "8px 16px",
                  borderRadius: 10,
                  background: isActive ? `${cat.color}18` : T.surface,
                  border: `1px solid ${isActive ? `${cat.color}44` : T.border}`,
                  color: isActive ? cat.color : T.textMuted,
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                {cat.icon}
                {cat.label}
                <span style={{ fontSize: 10, opacity: 0.7, background: isActive ? `${cat.color}22` : T.surfaceAlt, padding: "2px 6px", borderRadius: 5, fontWeight: 700 }}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Connected Integrations Banner */}
        {connectedCount > 0 && (
          <Card style={{ padding: "14px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <CheckCircle2 size={18} color={T.success} />
              <span style={{ fontSize: 13, fontWeight: 600, color: T.text, flex: 1 }}>
                {t("integrations.hub.activeIntegrations")}
              </span>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {INTEGRATIONS.filter(i => i.connectorId && connectedIds.has(i.connectorId)).map(i => (
                  <div
                    key={i.id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      padding: "4px 10px",
                      borderRadius: 7,
                      background: `${i.color}15`,
                      border: `1px solid ${i.color}33`,
                    }}
                  >
                    <div style={{ color: i.color, display: "flex" }}>{React.cloneElement(i.icon as React.ReactElement<any>, { size: 12 })}</div>
                    <span style={{ fontSize: 11, fontWeight: 600, color: T.text }}>{i.name}</span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        )}

        {/* Integration Grid */}
        <motion.div variants={staggerContainer} initial="initial" animate="animate" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {filteredIntegrations.map((integration) => {
            const accessible = isIntegrationAccessible(integration);
            const status = getIntegrationStatus(integration);
            const isConnected = status === "connected";

            return (
              <motion.div key={integration.id} variants={staggerItem}>
                <IntegrationCard
                  integration={integration}
                  accessible={accessible}
                  isConnected={isConnected}
                  onSetup={() => startOnboarding(integration)}
                  onManage={() => { setSelectedIntegration(integration); setView("manage"); loadExistingConfig(integration.connectorId || ""); }}
                  onDisconnect={() => integration.connectorId && disconnectIntegration(integration.connectorId)}
                  t={t}
                />
              </motion.div>
            );
          })}
        </motion.div>

        {filteredIntegrations.length === 0 && (
          <div style={{ padding: 48, textAlign: "center" }}>
            <Search size={32} color={T.textDim} style={{ margin: "0 auto 12px", display: "block" }} />
            <p style={{ fontSize: 14, fontWeight: 600, color: T.textMuted }}>{t("integrations.hub.noResults")}</p>
          </div>
        )}
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // ONBOARDING VIEW
  // ══════════════════════════════════════════════════════════════════════════

  function renderOnboarding() {
    if (!selectedIntegration) return null;
    const steps = selectedIntegration.setupSteps;
    const currentStepDef = steps[onboardingStep];
    if (!currentStepDef) return null;

    return (
      <motion.div {...fadeSlide} key="onboarding" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button
            onClick={() => {
              if (onboardingStep > 0) {
                setOnboardingStep(s => s - 1);
              } else {
                setView("hub");
                setSelectedIntegration(null);
              }
            }}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              width: 38, height: 38, borderRadius: 10,
              background: T.surfaceAlt, border: `1px solid ${T.border}`,
              color: T.textMuted, cursor: "pointer", flexShrink: 0,
            }}
          >
            <ArrowLeft size={16} />
          </button>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: `${selectedIntegration.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: selectedIntegration.color }}>
            {selectedIntegration.icon}
          </div>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0, letterSpacing: "-0.02em" }}>
              {t("integrations.onboarding.setupTitle", { name: selectedIntegration.name })}
            </h2>
            <p style={{ fontSize: 12, color: T.textMuted, margin: "3px 0 0" }}>
              {selectedIntegration.description}
            </p>
          </div>
        </div>

        {/* Step Indicator */}
        <StepIndicator steps={steps.map(s => ({ title: s.title, desc: s.description }))} currentStep={onboardingStep} color={selectedIntegration.color} />

        {/* Step Content */}
        <AnimatePresence mode="wait">
          <motion.div {...fadeSlide} key={`step-${onboardingStep}`}>
          {currentStepDef.type === "info" && (
            <>
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: T.infoDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.info, flexShrink: 0 }}>
                    <BookOpen size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {currentStepDef.title}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {currentStepDef.description}
                    </p>
                  </div>
                </div>

                {/* Feature highlights */}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 24 }}>
                  {selectedIntegration.tags.slice(0, 4).map((tag, i) => (
                    <div key={tag} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                      <CheckCircle2 size={14} color={T.success} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text, textTransform: "capitalize" }}>{tag}</span>
                    </div>
                  ))}
                </div>

                {/* Doc link */}
                {selectedIntegration.docUrl && (
                  <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}` }}>
                    <ExternalLink size={14} color={T.accent} />
                    <a href={selectedIntegration.docUrl} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, fontWeight: 600, color: T.accent, textDecoration: "none" }}>
                      {t("integrations.onboarding.viewDocs")}
                    </a>
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(1)} label={t("integrations.onboarding.next")} icon={<ArrowRight size={14} />} />
                </div>
              </Card>
            </>
          )}

          {currentStepDef.type === "config" && (
            <>
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: T.warningDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.warning, flexShrink: 0 }}>
                    <Key size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {currentStepDef.title}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {currentStepDef.description}
                    </p>
                  </div>
                </div>

                {/* Dynamic Fields */}
                <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                  {currentStepDef.fields?.map((field) => {
                    if (field.dependsOn) {
                      const [k, v] = field.dependsOn.split("=");
                      if (configValues[k] !== v) return null;
                    }

                    return (
                      <div key={field.key}>
                        <label style={labelStyle}>
                          {field.label}
                          {field.optional && <span style={{ fontWeight: 400, color: T.textDim, marginLeft: 6 }}>({t("integrations.onboarding.optional")})</span>}
                        </label>
                        {field.type === "select" && field.options ? (
                          <select
                            value={configValues[field.key] || ""}
                            onChange={(e) => setConfigValues(c => ({ ...c, [field.key]: e.target.value }))}
                            style={{ ...inputStyle, cursor: "pointer" }}
                          >
                            <option value="">{t("integrations.onboarding.selectOption")}</option>
                            {field.options.map(opt => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : field.type === "toggle" ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <button
                              onClick={() => setConfigValues(c => ({ ...c, [field.key]: c[field.key] === "true" ? "false" : "true" }))}
                              style={{
                                width: 44, height: 24, borderRadius: 12, border: "none", cursor: "pointer",
                                background: configValues[field.key] === "true" ? T.success : T.surfaceAlt,
                                position: "relative", transition: "background 0.2s",
                              }}
                            >
                              <div style={{
                                width: 18, height: 18, borderRadius: 9, background: "#fff",
                                position: "absolute", top: 3,
                                left: configValues[field.key] === "true" ? 23 : 3,
                                transition: "left 0.2s",
                              }} />
                            </button>
                          </div>
                        ) : (
                          <div style={{ position: "relative" }}>
                            <input
                              type={field.type === "password" && !showPassword[field.key] ? "password" : "text"}
                              value={configValues[field.key] || ""}
                              onChange={(e) => setConfigValues(c => ({ ...c, [field.key]: e.target.value }))}
                              placeholder={field.placeholder || ""}
                              style={{ ...inputStyle, paddingRight: field.type === "password" ? 40 : 14 }}
                            />
                            {field.type === "password" && (
                              <button
                                onClick={() => setShowPassword(s => ({ ...s, [field.key]: !s[field.key] }))}
                                style={{
                                  position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
                                  background: "none", border: "none", color: T.textDim, cursor: "pointer", padding: 4,
                                }}
                              >
                                {showPassword[field.key] ? <EyeOff size={14} /> : <Eye size={14} />}
                              </button>
                            )}
                          </div>
                        )}
                        {field.helpText && (
                          <p style={{ fontSize: 11, color: T.textDim, margin: "6px 0 0", display: "flex", alignItems: "center", gap: 4 }}>
                            <HelpCircle size={10} /> {field.helpText}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(s => s - 1)} label={t("integrations.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  <ActionButton onClick={() => setOnboardingStep(s => s + 1)} label={t("integrations.onboarding.next")} icon={<ArrowRight size={14} />} />
                </div>
              </Card>
            </>
          )}

          {currentStepDef.type === "test" && (
            <>
              <Card style={{ padding: 28 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 24 }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: T.infoDim, display: "flex", alignItems: "center", justifyContent: "center", color: T.info, flexShrink: 0 }}>
                    <Zap size={20} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, color: T.text, margin: "0 0 6px" }}>
                      {currentStepDef.title}
                    </h3>
                    <p style={{ fontSize: 13, color: T.textMuted, margin: 0, lineHeight: 1.6 }}>
                      {currentStepDef.description}
                    </p>
                  </div>
                </div>

                {/* Test Area */}
                <div style={{ padding: 28, borderRadius: 14, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
                  {configTesting ? (
                    <>
                      <Loader2 size={36} color={selectedIntegration.color} className="animate-spin" />
                      <p style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{t("integrations.onboarding.testing")}</p>
                    </>
                  ) : testResult ? (
                    <>
                      {testResult.status === "ok" ? (
                        <CheckCircle2 size={40} color={T.success} />
                      ) : (
                        <AlertCircle size={40} color={T.danger} />
                      )}
                      <p style={{ fontSize: 14, fontWeight: 700, color: testResult.status === "ok" ? T.success : T.danger }}>
                        {testResult.message}
                      </p>
                      {testResult.status !== "ok" && (
                        <p style={{ fontSize: 12, color: T.textMuted, textAlign: "center" }}>
                          {t("integrations.onboarding.testFailed")}
                        </p>
                      )}
                    </>
                  ) : (
                    <>
                      <div style={{ width: 60, height: 60, borderRadius: 18, background: `${selectedIntegration.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: selectedIntegration.color }}>
                        {selectedIntegration.icon}
                      </div>
                      <p style={{ fontSize: 13, color: T.textMuted, textAlign: "center" }}>
                        {t("integrations.onboarding.testReady")}
                      </p>
                    </>
                  )}

                  <button
                    onClick={testConnection}
                    disabled={configTesting || configSaving}
                    style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "10px 24px", borderRadius: 10,
                      background: selectedIntegration.color, color: "#fff",
                      fontSize: 13, fontWeight: 700, border: "none",
                      cursor: configTesting ? "not-allowed" : "pointer",
                      opacity: configTesting ? 0.6 : 1,
                    }}
                  >
                    {configTesting ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                    {t("integrations.onboarding.runTest")}
                  </button>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
                  <ActionButton onClick={() => setOnboardingStep(s => s - 1)} label={t("integrations.onboarding.back")} icon={<ArrowLeft size={14} />} variant="ghost" iconPosition="left" />
                  <ActionButton
                    onClick={() => setOnboardingStep(s => s + 1)}
                    label={t("integrations.onboarding.next")}
                    icon={<ArrowRight size={14} />}
                    disabled={!testResult || testResult.status !== "ok"}
                  />
                </div>
              </Card>
            </>
          )}

          {currentStepDef.type === "complete" && (
            <>
              <Card style={{ padding: 36, textAlign: "center" }}>
                <div style={{ width: 72, height: 72, borderRadius: 20, background: T.successDim, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                  <CheckCircle2 size={36} color={T.success} />
                </div>
                <h3 style={{ fontSize: 20, fontWeight: 800, color: T.text, margin: "0 0 8px" }}>
                  {currentStepDef.title}
                </h3>
                <p style={{ fontSize: 13, color: T.textMuted, margin: "0 0 8px", maxWidth: 420, marginLeft: "auto", marginRight: "auto" }}>
                  {currentStepDef.description}
                </p>

                <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "8px 16px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.success}44`, margin: "16px 0 24px" }}>
                  <div style={{ color: selectedIntegration.color }}>{selectedIntegration.icon}</div>
                  <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{selectedIntegration.name}</span>
                  <Badge variant="success">Connected</Badge>
                </div>

                <div style={{ display: "flex", justifyContent: "center", gap: 12 }}>
                  <ActionButton
                    onClick={() => { setView("hub"); setSelectedIntegration(null); fetchCatalog(); }}
                    label={t("integrations.onboarding.backToHub")}
                    icon={<ArrowRight size={14} />}
                    variant="success"
                  />
                </div>
              </Card>
            </>
          )}
          </motion.div>
        </AnimatePresence>
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // MANAGE VIEW
  // ══════════════════════════════════════════════════════════════════════════

  function renderManage() {
    if (!selectedIntegration) return null;
    const isConnected = selectedIntegration.connectorId && connectedIds.has(selectedIntegration.connectorId);

    return (
      <motion.div {...fadeSlide} key="manage" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <button
              onClick={() => { setView("hub"); setSelectedIntegration(null); }}
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 38, height: 38, borderRadius: 10,
                background: T.surfaceAlt, border: `1px solid ${T.border}`,
                color: T.textMuted, cursor: "pointer",
              }}
            >
              <ArrowLeft size={16} />
            </button>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: `${selectedIntegration.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: selectedIntegration.color }}>
              {selectedIntegration.icon}
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: T.text, margin: 0 }}>{selectedIntegration.name}</h2>
              <p style={{ fontSize: 12, color: T.textMuted, margin: "2px 0 0" }}>{selectedIntegration.description}</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {isConnected && (
              <Badge variant="success">Connected</Badge>
            )}
          </div>
        </div>

        {/* Config Card */}
        <Card style={{ padding: 28 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: T.text, margin: "0 0 20px", display: "flex", alignItems: "center", gap: 8 }}>
            <Settings size={16} color={T.textDim} />
            {t("integrations.manage.configuration")}
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {selectedIntegration.setupSteps
              .filter(s => s.type === "config")
              .flatMap(s => s.fields || [])
              .map((field) => {
                if (field.dependsOn) {
                  const [k, v] = field.dependsOn.split("=");
                  if (configValues[k] !== v) return null;
                }
                return (
                  <div key={field.key}>
                    <label style={labelStyle}>{field.label}</label>
                    {field.type === "select" && field.options ? (
                      <select
                        value={configValues[field.key] || ""}
                        onChange={(e) => setConfigValues(c => ({ ...c, [field.key]: e.target.value }))}
                        style={{ ...inputStyle, cursor: "pointer" }}
                      >
                        <option value="">{t("integrations.onboarding.selectOption")}</option>
                        {field.options.map(opt => (
                          <option key={opt} value={opt}>{opt}</option>
                        ))}
                      </select>
                    ) : (
                      <div style={{ position: "relative" }}>
                        <input
                          type={field.type === "password" && !showPassword[field.key] ? "password" : "text"}
                          value={configValues[field.key] || ""}
                          onChange={(e) => setConfigValues(c => ({ ...c, [field.key]: e.target.value }))}
                          placeholder={field.placeholder || ""}
                          style={{ ...inputStyle, paddingRight: field.type === "password" ? 40 : 14 }}
                        />
                        {field.type === "password" && (
                          <button
                            onClick={() => setShowPassword(s => ({ ...s, [field.key]: !s[field.key] }))}
                            style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: T.textDim, cursor: "pointer", padding: 4 }}
                          >
                            {showPassword[field.key] ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        )}
                      </div>
                    )}
                    {field.helpText && (
                      <p style={{ fontSize: 11, color: T.textDim, margin: "6px 0 0", display: "flex", alignItems: "center", gap: 4 }}>
                        <HelpCircle size={10} /> {field.helpText}
                      </p>
                    )}
                  </div>
                );
              })}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24, paddingTop: 20, borderTop: `1px solid ${T.border}` }}>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={testConnection}
                disabled={configTesting}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "9px 16px", borderRadius: 9,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  color: T.textMuted, fontSize: 12, fontWeight: 600, cursor: "pointer",
                }}
              >
                {configTesting ? <Loader2 size={14} className="animate-spin" /> : <Activity size={14} />}
                {t("integrations.manage.test")}
              </button>
              {isConnected && (
                <button
                  onClick={() => {
                    if (selectedIntegration.connectorId) {
                      disconnectIntegration(selectedIntegration.connectorId);
                      setView("hub");
                      setSelectedIntegration(null);
                    }
                  }}
                  style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "9px 16px", borderRadius: 9,
                    background: T.dangerDim, border: "none",
                    color: T.danger, fontSize: 12, fontWeight: 600, cursor: "pointer",
                  }}
                >
                  <Unlink size={14} />
                  {t("integrations.manage.disconnect")}
                </button>
              )}
            </div>
            <button
              onClick={saveConfig}
              disabled={configSaving}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "9px 20px", borderRadius: 9,
                background: T.accent, border: "none",
                color: "#fff", fontSize: 13, fontWeight: 700, cursor: "pointer",
                opacity: configSaving ? 0.6 : 1,
              }}
            >
              {configSaving && <Loader2 size={14} className="animate-spin" />}
              {t("integrations.manage.save")}
            </button>
          </div>

          {/* Test result */}
          {testResult && (
            <div style={{
              marginTop: 16, padding: "12px 16px", borderRadius: 10,
              background: testResult.status === "ok" ? T.successDim : T.dangerDim,
              border: `1px solid ${testResult.status === "ok" ? T.success : T.danger}33`,
              display: "flex", alignItems: "center", gap: 10,
            }}>
              {testResult.status === "ok" ? <CheckCircle2 size={16} color={T.success} /> : <AlertCircle size={16} color={T.danger} />}
              <span style={{ fontSize: 13, fontWeight: 600, color: testResult.status === "ok" ? T.success : T.danger }}>
                {testResult.message}
              </span>
            </div>
          )}
        </Card>

        {/* Documentation */}
        {selectedIntegration.docUrl && (
          <Card style={{ padding: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <BookOpen size={18} color={T.textDim} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: T.text, margin: 0 }}>
                  {t("integrations.manage.documentation")}
                </p>
                <p style={{ fontSize: 11, color: T.textMuted, margin: "2px 0 0" }}>
                  {t("integrations.manage.docDesc")}
                </p>
              </div>
              <a
                href={selectedIntegration.docUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "7px 14px", borderRadius: 8,
                  background: T.surfaceAlt, border: `1px solid ${T.border}`,
                  color: T.accent, fontSize: 12, fontWeight: 600, textDecoration: "none",
                }}
              >
                <ExternalLink size={12} />
                {t("integrations.manage.openDocs")}
              </a>
            </div>
          </Card>
        )}
      </motion.div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════════════════════

  if (permLoading || catalogLoading) {
    return (
      <div className="flex flex-col gap-4">
        <SettingsSubnav />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 400 }}>
          <div style={{ textAlign: "center" }}>
            <Loader2 size={28} color={T.accent} className="animate-spin" style={{ margin: "0 auto 12px", display: "block" }} />
            <span style={{ fontSize: 13, color: T.textMuted }}>{t("common.loading")}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSubnav />
      <AnimatePresence mode="wait">
        {view === "hub" && renderHub()}
        {view === "onboarding" && renderOnboarding()}
        {view === "manage" && renderManage()}
      </AnimatePresence>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════

// ── Integration Card ────────────────────────────────────────────────────────

function IntegrationCard({
  integration,
  accessible,
  isConnected,
  onSetup,
  onManage,
  onDisconnect,
  t,
}: {
  integration: IntegrationDef;
  accessible: boolean;
  isConnected: boolean;
  onSetup: () => void;
  onManage: () => void;
  onDisconnect: () => void;
  t: (key: string, vars?: Record<string, any>) => any;
}) {
  const [hovered, setHovered] = useState(false);
  const isLocked = !accessible && !integration.comingSoon;
  const isComing = integration.comingSoon;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        padding: 20,
        borderRadius: 16,
        background: isConnected ? `${integration.color}08` : hovered ? T.surfaceAlt : T.surface,
        border: `1px solid ${isConnected ? `${integration.color}44` : hovered ? T.borderLight : T.border}`,
        transition: "all 0.25s ease",
        transform: hovered && !isLocked && !isComing ? "translateY(-2px)" : "none",
        opacity: isLocked || isComing ? 0.65 : 1,
        display: "flex",
        flexDirection: "column",
        gap: 14,
        position: "relative",
        minHeight: 180,
      }}
    >
      {/* Status indicators */}
      {isConnected && (
        <div style={{ position: "absolute", top: 12, right: 12 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.success, boxShadow: `0 0 8px ${T.success}66` }} />
        </div>
      )}
      {integration.popular && !isConnected && (
        <div style={{ position: "absolute", top: 12, right: 12 }}>
          <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 5, background: T.warningDim, color: T.warning, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Popular
          </span>
        </div>
      )}

      {/* Icon + Name */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{
          width: 42, height: 42, borderRadius: 12,
          background: `${integration.color}15`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: integration.color,
        }}>
          {integration.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: 14, fontWeight: 700, color: T.text, margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {integration.name}
          </p>
          <p style={{ fontSize: 10, fontWeight: 600, color: T.textDim, margin: 0, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            {CATEGORIES.find(c => c.id === integration.category)?.label || integration.category}
          </p>
        </div>
      </div>

      {/* Description */}
      <p style={{ fontSize: 12, color: T.textMuted, margin: 0, lineHeight: 1.5, flex: 1 }}>
        {integration.description}
      </p>

      {/* Footer */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        {/* Plan badge */}
        <span style={{
          fontSize: 10, fontWeight: 700, padding: "3px 8px", borderRadius: 5,
          background: isLocked ? T.dangerDim : T.surfaceAlt,
          color: isLocked ? T.danger : T.textDim,
          textTransform: "uppercase", letterSpacing: "0.04em",
        }}>
          {isLocked && <Lock size={8} style={{ marginRight: 3, verticalAlign: "middle" }} />}
          {PLAN_LABELS[integration.minPlan]}+
        </span>

        {/* Action */}
        {isComing ? (
          <span style={{ fontSize: 11, fontWeight: 600, color: T.textDim }}>
            {t("integrations.card.comingSoon")}
          </span>
        ) : isLocked ? (
          <span style={{ fontSize: 11, fontWeight: 600, color: T.warning, display: "flex", alignItems: "center", gap: 4 }}>
            <Crown size={12} /> {t("integrations.card.upgrade")}
          </span>
        ) : isConnected ? (
          <button
            onClick={onManage}
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "6px 12px", borderRadius: 7,
              background: `${integration.color}18`, border: `1px solid ${integration.color}33`,
              color: integration.color, fontSize: 11, fontWeight: 700, cursor: "pointer",
            }}
          >
            <Settings size={12} /> {t("integrations.card.manage")}
          </button>
        ) : (
          <button
            onClick={onSetup}
            style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "6px 12px", borderRadius: 7,
              background: T.accent, border: "none",
              color: "#fff", fontSize: 11, fontWeight: 700, cursor: "pointer",
            }}
          >
            <Zap size={12} /> {t("integrations.card.setup")}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Step Indicator ──────────────────────────────────────────────────────────

function StepIndicator({
  steps,
  currentStep,
  color,
}: {
  steps: Array<{ title: string; desc: string }>;
  currentStep: number;
  color?: string;
}) {
  const accentColor = color || T.accent;

  return (
    <Card style={{ padding: "16px 20px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
        {steps.map((step, i) => (
          <Fragment key={i}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1 }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: i <= currentStep ? `${accentColor}18` : T.surfaceAlt,
                border: `1.5px solid ${i <= currentStep ? accentColor : T.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: i <= currentStep ? accentColor : T.textDim,
                fontSize: 12, fontWeight: 700, flexShrink: 0,
              }}>
                {i < currentStep ? <Check size={14} /> : i + 1}
              </div>
              <div style={{ minWidth: 0 }}>
                <p style={{
                  fontSize: 12, fontWeight: 600,
                  color: i <= currentStep ? T.text : T.textDim,
                  margin: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>
                  {step.title}
                </p>
              </div>
            </div>
            {i < steps.length - 1 && (
              <div style={{
                flex: "0 0 32px", height: 2, borderRadius: 1,
                background: i < currentStep ? accentColor : T.border,
                margin: "0 4px",
              }} />
            )}
          </Fragment>
        ))}
      </div>
    </Card>
  );
}

// ── Action Button ───────────────────────────────────────────────────────────

function ActionButton({
  onClick,
  label,
  icon,
  variant = "primary",
  iconPosition = "right",
  disabled = false,
}: {
  onClick: () => void;
  label: string;
  icon?: React.ReactNode;
  variant?: "primary" | "ghost" | "success";
  iconPosition?: "left" | "right";
  disabled?: boolean;
}) {
  const styles: Record<string, CSSProperties> = {
    primary: { background: T.accent, color: "#fff", border: "none" },
    ghost: { background: T.surfaceAlt, color: T.textMuted, border: `1px solid ${T.border}` },
    success: { background: T.success, color: "#fff", border: "none" },
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex", alignItems: "center", gap: 6,
        padding: "9px 18px", borderRadius: 9,
        fontSize: 13, fontWeight: 700,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        flexDirection: iconPosition === "left" ? "row-reverse" : "row",
        ...styles[variant],
      }}
    >
      {label} {icon}
    </button>
  );
}
