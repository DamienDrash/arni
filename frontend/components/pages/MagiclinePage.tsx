"use client";

import { useEffect, useState } from "react";
import { Link2, Users, Phone, Mail, UserCheck, RefreshCw, Zap } from "lucide-react";

import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Stat } from "@/components/ui/Stat";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useI18n } from "@/lib/i18n/LanguageContext";

type MembersStats = {
  total_members: number;
  new_today: number;
  with_email: number;
  with_phone: number;
  with_both: number;
};

type GlobalStats = {
  total_messages: number;
  active_users: number;
  active_handoffs: number;
};

type ChatSession = {
  user_id: string;
  platform: string;
  member_id?: string | null;
};

type EnrichmentStats = {
  total: number;
  enriched: number;
  paused: number;
  languages: Record<string, number>;
};

type SyncResult = { fetched: number; upserted: number; deleted: number } | null;

const LANG_LABELS: Record<string, string> = {
  de: "Deutsch", en: "English", tr: "Türkçe", ar: "Arabisch", fr: "Français",
  es: "Español", pl: "Polski", ru: "Русский", unknown: "Unbekannt",
};

const LANG_COLORS: Record<string, string> = {
  de: "#6C5CE7", en: "#0984E3", tr: "#E17055", ar: "#00B894",
  fr: "#FDCB6E", es: "#E84393", pl: "#A29BFE", ru: "#74B9FF",
};

export function MagiclinePage() {
  const { t } = useI18n();
  const [stats, setStats] = useState<MembersStats | null>(null);
  const [globalStats, setGlobalStats] = useState<GlobalStats | null>(null);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [enrichmentStats, setEnrichmentStats] = useState<EnrichmentStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isEnrichingAll, setIsEnrichingAll] = useState(false);
  const [enrichAllDone, setEnrichAllDone] = useState(false);
  const [enrichEnqueued, setEnrichEnqueued] = useState<number | null>(null);
  const [enrichMinutes, setEnrichMinutes] = useState<number | null>(null);
  const [syncResult, setSyncResult] = useState<SyncResult>(null);
  const [syncError, setSyncError] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const fetchAll = async () => {
    setIsLoading(true);
    try {
      const [membersRes, globalRes, chatsRes, enrichRes] = await Promise.all([
        apiFetch("/admin/members/stats"),
        apiFetch("/admin/stats"),
        apiFetch("/admin/chats?limit=500"),
        apiFetch("/admin/members/enrichment-stats"),
      ]);
      if (membersRes.ok) { setStats(await membersRes.json()); setConnected(true); }
      else setConnected(false);
      if (globalRes.ok) setGlobalStats(await globalRes.json());
      if (chatsRes.ok) setChats(await chatsRes.json());
      if (enrichRes.ok) setEnrichmentStats(await enrichRes.json());
    } catch {
      setConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerSync = async () => {
    setIsSyncing(true);
    setSyncResult(null);
    setSyncError(false);
    try {
      const res = await apiFetch("/admin/members/sync", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setSyncResult({ fetched: data.fetched, upserted: data.upserted, deleted: data.deleted });
        setLastSync(new Date().toLocaleTimeString("de", { hour: "2-digit", minute: "2-digit" }));
        await fetchAll();
      } else {
        setSyncError(true);
      }
    } catch {
      setSyncError(true);
    } finally {
      setIsSyncing(false);
    }
  };

  const triggerEnrichAll = async () => {
    setIsEnrichingAll(true);
    setEnrichAllDone(false);
    setEnrichEnqueued(null);
    setEnrichMinutes(null);
    try {
      const res = await apiFetch("/admin/members/enrich-all", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setEnrichEnqueued(data.enqueued);
        setEnrichMinutes(data.estimated_minutes);
        setEnrichAllDone(true);
      }
    } finally {
      setIsEnrichingAll(false);
      // Refresh stats after a short delay
      setTimeout(fetchAll, 3000);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  // Always render 4 stat cards
  const memberStats = [
    { label: "Gesamt-Kontakte", value: stats ? stats.total_members.toLocaleString("de") : "–", color: T.accent, icon: <Users size={18} /> },
    { label: "Mit Telefon", value: stats ? stats.with_phone.toLocaleString("de") : "–", color: T.whatsapp, icon: <Phone size={18} /> },
    { label: "Mit E-Mail", value: stats ? stats.with_email.toLocaleString("de") : "–", color: T.info, icon: <Mail size={18} /> },
    { label: "Neu (heute)", value: stats ? `+${stats.new_today}` : "–", color: T.success, icon: <UserCheck size={18} /> },
  ];

  // ARIIA Adoption
  const totalMembers = stats?.total_members ?? 0;
  const activeUsers = globalStats?.active_users ?? 0;
  const adoptionPct = totalMembers > 0 ? Math.round((activeUsers / totalMembers) * 100) : 0;
  const neverUsed = Math.max(0, totalMembers - activeUsers);

  // Platform & Verification
  const whatsapp = chats.filter(c => c.platform === "whatsapp").length;
  const telegram = chats.filter(c => c.platform === "telegram").length;
  const total = chats.length;
  const verified = chats.filter(c => c.member_id).length;
  const unverified = total - verified;
  const whatsappPct = total > 0 ? Math.round((whatsapp / total) * 100) : 0;
  const telegramPct = total > 0 ? Math.round((telegram / total) * 100) : 0;
  const verifiedPct = total > 0 ? Math.round((verified / total) * 100) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Connection Banner */}
      <div style={{
        display: "flex", alignItems: "center", gap: 16, padding: "18px 24px", borderRadius: 14,
        background: connected ? T.successDim : T.dangerDim,
        border: `1px solid ${connected ? T.success + "35" : T.danger + "35"}`,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 11, flexShrink: 0,
          background: connected ? T.success + "25" : T.danger + "25",
          border: `1px solid ${connected ? T.success + "40" : T.danger + "40"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Link2 size={20} color={connected ? T.success : T.danger} />
        </div>
        <div style={{ flex: 1 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: connected ? T.success : T.danger, margin: "0 0 4px" }}>
            {connected ? "Externe API Verbunden" : "Externe API Nicht Erreichbar"}
          </h3>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: T.textMuted }}>
              {lastSync ? `${t("magicline.lastSync")}: ${lastSync}` : t("magicline.syncNotStarted")}
            </span>
            {syncResult && (
              <>
                <Badge variant="success" size="xs">{syncResult.fetched} geladen</Badge>
                <Badge variant="accent" size="xs">{syncResult.upserted} aktualisiert</Badge>
                {syncResult.deleted > 0 && <Badge variant="warning" size="xs">{syncResult.deleted} entfernt</Badge>}
              </>
            )}
            {enrichAllDone && enrichEnqueued !== null && enrichEnqueued > 0 && (
              <Badge variant="accent" size="xs">{enrichEnqueued} zur Anreicherung eingereiht (~{enrichMinutes} Min)</Badge>
            )}
            {enrichAllDone && enrichEnqueued === 0 && (
              <Badge variant="success" size="xs">{t("magicline.allEnriched")}</Badge>
            )}
            {syncError && <Badge variant="danger" size="xs">{t("magicline.syncFailed")}</Badge>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <button
            onClick={triggerEnrichAll}
            disabled={isEnrichingAll || !connected}
            title={t("magicline.syncDescription")}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "9px 16px", borderRadius: 9, border: `1px solid ${T.border}`,
              background: enrichAllDone ? T.successDim : T.surfaceAlt,
              color: enrichAllDone ? T.success : isEnrichingAll ? T.textMuted : T.text,
              fontSize: 12, fontWeight: 600,
              cursor: (isEnrichingAll || !connected) ? "not-allowed" : "pointer",
              transition: "all 0.15s",
            }}
          >
            <Zap size={13} style={{ animation: isEnrichingAll ? "spin 1s linear infinite" : "none" }} />
            {isEnrichingAll ? "Anreichern…" : enrichAllDone ? "Gestartet" : t("magicline.enrichAll")}
          </button>
          <button
            onClick={triggerSync}
            disabled={isSyncing}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "9px 16px", borderRadius: 9, border: "none",
              background: isSyncing ? T.surfaceAlt : T.accent,
              color: isSyncing ? T.textMuted : "#fff",
              fontSize: 12, fontWeight: 600,
              cursor: isSyncing ? "not-allowed" : "pointer",
              transition: "background 0.15s",
            }}
          >
            <RefreshCw size={13} style={{ animation: isSyncing ? "spin 1s linear infinite" : "none" }} />
            {isSyncing ? "Syncing…" : t("sidebar.sync")}
          </button>
        </div>
      </div>

      {/* Stats – always shown */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {memberStats.map((s, i) => (
          <Card key={i} style={{ padding: 20, opacity: isLoading ? 0.5 : 1, transition: "opacity 0.2s" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: `${s.color}15`,
                display: "flex", alignItems: "center", justifyContent: "center",
                color: s.color,
              }}>
                {s.icon}
              </div>
              <Stat label={s.label} value={s.value} color={s.color} />
            </div>
          </Card>
        ))}
      </div>

      {/* Two analysis cards side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Left: ARIIA Adoption */}
        <Card style={{ padding: 24 }}>
          <SectionHeader
            title={t("magicline.adoption")}
            subtitle={t("magicline.adoptionSubtitle")}
          />
          <div style={{ marginTop: 12 }}>
            {/* Big numbers */}
            <div style={{ display: "flex", gap: 24, marginBottom: 20 }}>
              <div>
                <div style={{ fontSize: 28, fontWeight: 800, color: T.accent, letterSpacing: "-0.03em", lineHeight: 1 }}>
                  {isLoading ? "–" : activeUsers.toLocaleString("de")}
                </div>
                <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>{t("magicline.usersActive")}</div>
              </div>
              <div style={{ width: 1, background: T.border }} />
              <div>
                <div style={{ fontSize: 28, fontWeight: 800, color: T.textDim, letterSpacing: "-0.03em", lineHeight: 1 }}>
                  {isLoading ? "–" : neverUsed.toLocaleString("de")}
                </div>
                <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>noch nicht genutzt</div>
              </div>
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: adoptionPct > 0 ? T.success : T.textDim, letterSpacing: "-0.03em", lineHeight: 1 }}>
                  {isLoading ? "–" : `${adoptionPct}%`}
                </div>
                <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>Adoptionsrate</div>
              </div>
            </div>
            <ProgressBar value={adoptionPct} max={100} color={T.accent} height={6} />
            {globalStats && (
              <div style={{ marginTop: 14, fontSize: 12, color: T.textDim }}>
                {globalStats.total_messages.toLocaleString("de")} Nachrichten insgesamt verarbeitet
              </div>
            )}
          </div>
        </Card>

        {/* Right: Platform & Verification */}
        <Card style={{ padding: 24 }}>
          <SectionHeader
            title={t("magicline.platformVerification")}
            subtitle={t("magicline.platformSubtitle")}
          />
          <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 16 }}>

            {total === 0 && !isLoading ? (
              <div style={{ fontSize: 13, color: T.textDim, padding: "12px 0" }}>{t("magicline.noSessions")}</div>
            ) : (
              <>
                {/* Platform breakdown */}
                <div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Kanal</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[
                      { label: "WhatsApp", value: whatsapp, pct: whatsappPct, color: T.whatsapp },
                      { label: "Telegram", value: telegram, pct: telegramPct, color: T.telegram },
                    ].map((p, i) => (
                      <div key={i}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{p.label}</span>
                          <span style={{ fontSize: 12, color: p.color, fontWeight: 700 }}>
                            {p.value} <span style={{ color: T.textDim, fontWeight: 400 }}>({p.pct}%)</span>
                          </span>
                        </div>
                        <ProgressBar value={p.pct} max={100} color={p.color} height={5} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Verification breakdown */}
                <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 14 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>Verifikation</div>
                  <div style={{ display: "flex", gap: 16 }}>
                    <div style={{ flex: 1, padding: "12px 14px", borderRadius: 10, background: T.successDim, border: `1px solid ${T.success}30` }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: T.success }}>{verified}</div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>verifiziert</div>
                      <div style={{ fontSize: 11, color: T.success, fontWeight: 600 }}>{verifiedPct}%</div>
                    </div>
                    <div style={{ flex: 1, padding: "12px 14px", borderRadius: 10, background: T.warningDim, border: `1px solid ${T.warning}30` }}>
                      <div style={{ fontSize: 20, fontWeight: 800, color: T.warning }}>{unverified}</div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 2 }}>unverifiziert</div>
                      <div style={{ fontSize: 11, color: T.warning, fontWeight: 600 }}>{100 - verifiedPct}%</div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </Card>

      </div>

      {/* Third row: Enrichment analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Language distribution */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title={t("magicline.languageDistribution")} subtitle={t("magicline.languageSubtitle")} />
          <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
            {enrichmentStats && enrichmentStats.total > 0 ? (() => {
              const langs = enrichmentStats.languages;
              const total = Object.values(langs).reduce((a, b) => a + b, 0);
              const sorted = Object.entries(langs)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5);
              return sorted.map(([code, count]) => {
                const pct = Math.round((count / total) * 100);
                const label = LANG_LABELS[code] ?? code.toUpperCase();
                const color = LANG_COLORS[code] ?? T.textDim;
                return (
                  <div key={code}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{label}</span>
                      <span style={{ fontSize: 12, color, fontWeight: 700 }}>
                        {count} <span style={{ color: T.textDim, fontWeight: 400 }}>({pct}%)</span>
                      </span>
                    </div>
                    <ProgressBar value={pct} max={100} color={color} height={5} />
                  </div>
                );
              });
            })() : (
              <div style={{ fontSize: 13, color: T.textDim, padding: "12px 0" }}>
                {isLoading ? t("common.loading") : t("magicline.noLanguageData")}
              </div>
            )}
          </div>
        </Card>

        {/* Member status: paused */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title={t("magicline.memberStatus")} subtitle={t("magicline.memberStatusSubtitle")} />
          <div style={{ marginTop: 14 }}>
            {enrichmentStats ? (() => {
              const total = enrichmentStats.total;
              const paused = enrichmentStats.paused;
              const active = Math.max(0, total - paused);
              const pausedPct = total > 0 ? Math.round((paused / total) * 100) : 0;
              const activePct = 100 - pausedPct;
              return (
                <>
                  <div style={{ display: "flex", gap: 12, marginBottom: 18 }}>
                    <div style={{ flex: 1, padding: "12px 14px", borderRadius: 10, background: T.successDim, border: `1px solid ${T.success}30` }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: T.success, lineHeight: 1 }}>{active.toLocaleString("de")}</div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 3 }}>{t("common.active")}</div>
                      <div style={{ fontSize: 11, color: T.success, fontWeight: 600, marginTop: 1 }}>{activePct}%</div>
                    </div>
                    <div style={{ flex: 1, padding: "12px 14px", borderRadius: 10, background: T.warningDim, border: `1px solid ${T.warning}30` }}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: T.warning, lineHeight: 1 }}>{paused.toLocaleString("de")}</div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 3 }}>{t("common.paused")}</div>
                      <div style={{ fontSize: 11, color: T.warning, fontWeight: 600, marginTop: 1 }}>{pausedPct}%</div>
                    </div>
                  </div>
                  <ProgressBar value={activePct} max={100} color={T.success} height={5} />
                </>
              );
            })() : (
              <div style={{ fontSize: 13, color: T.textDim, padding: "12px 0" }}>
                {isLoading ? t("common.loading") : t("magicline.noData")}
              </div>
            )}
          </div>
        </Card>

        {/* Enrichment coverage */}
        <Card style={{ padding: 24 }}>
          <SectionHeader title={t("magicline.dataCoverage")} subtitle={t("magicline.dataCoverageSubtitle")} />
          <div style={{ marginTop: 14 }}>
            {enrichmentStats ? (() => {
              const total = enrichmentStats.total;
              const enriched = enrichmentStats.enriched;
              const missing = Math.max(0, total - enriched);
              const enrichedPct = total > 0 ? Math.round((enriched / total) * 100) : 0;
              return (
                <>
                  <div style={{ display: "flex", gap: 24, marginBottom: 18 }}>
                    <div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: T.accent, letterSpacing: "-0.03em", lineHeight: 1 }}>
                        {enrichedPct}%
                      </div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>angereichert</div>
                    </div>
                    <div style={{ width: 1, background: T.border }} />
                    <div>
                      <div style={{ fontSize: 28, fontWeight: 800, color: T.textDim, letterSpacing: "-0.03em", lineHeight: 1 }}>
                        {missing.toLocaleString("de")}
                      </div>
                      <div style={{ fontSize: 11, color: T.textMuted, marginTop: 4 }}>noch ausstehend</div>
                    </div>
                  </div>
                  <ProgressBar value={enrichedPct} max={100} color={T.accent} height={5} />
                  <div style={{ marginTop: 12, fontSize: 12, color: T.textDim }}>
                    {enriched.toLocaleString("de")} von {total.toLocaleString("de")} Kontakten mit Aktivitätsdaten
                  </div>
                </>
              );
            })() : (
              <div style={{ fontSize: 13, color: T.textDim, padding: "12px 0" }}>
                {isLoading ? t("common.loading") : t("magicline.noData")}
              </div>
            )}
          </div>
        </Card>

      </div>
    </div>
  );
}
