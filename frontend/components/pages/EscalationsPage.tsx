"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  AlertTriangle, Clock, CheckCircle2, TrendingDown, RefreshCw,
  CheckCircle, Phone, Search, Link2, Unlink, XCircle, Hash,
  Mail, User, Shield, ChevronRight, MessageSquare, Info,
} from "lucide-react";

import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { useI18n } from "@/lib/i18n/LanguageContext";

/* ── Types ──────────────────────────────────────────────────────────── */
type Handoff = {
  user_id: string;
  key: string;
  user_name?: string | null;
  platform?: string | null;
  member_id?: string | null;
  active_token?: string | null;
};
type Stats = {
  active_handoffs: number;
  total_sessions?: number;
  total_messages?: number;
};
type MemberResult = {
  id: number;
  customer_id: number;
  member_number?: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone_number?: string;
};

/* ── Styles ─────────────────────────────────────────────────────────── */
const statCard: React.CSSProperties = {
  padding: "20px 24px",
  display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16,
};
const statIcon: (color: string) => React.CSSProperties = (color) => ({
  width: 44, height: 44, borderRadius: 12,
  background: `${color}15`,
  display: "flex", alignItems: "center", justifyContent: "center",
  color, flexShrink: 0,
});
const statLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 800, color: T.textDim,
  textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 4,
};
const statValue: (color?: string) => React.CSSProperties = (color) => ({
  fontSize: 24, fontWeight: 800, color: color || T.text, letterSpacing: "-0.02em",
});
const inputBase: React.CSSProperties = {
  width: "100%", padding: "10px 14px", borderRadius: 10,
  background: T.surfaceAlt, border: `1px solid ${T.border}`,
  color: T.text, fontSize: 13, outline: "none",
  transition: "border-color 0.2s ease",
};
const btnPrimary: React.CSSProperties = {
  border: "none", borderRadius: 10, background: T.accent, color: "#fff",
  fontWeight: 700, padding: "10px 20px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13,
  transition: "all 0.2s ease",
};
const btnSecondary: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt,
  color: T.text, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
  transition: "all 0.2s ease",
};

/* ── Priority Helpers ───────────────────────────────────────────────── */
function getPriority(h: Handoff): "high" | "medium" | "low" {
  if (!h.member_id) return "high";
  return "medium";
}
const priorityConfig: Record<string, { color: string; label: string; bg: string }> = {
  high: { color: T.danger, label: "HOCH", bg: T.dangerDim },
  medium: { color: T.warning, label: "MITTEL", bg: T.warningDim },
  low: { color: T.textDim, label: "NIEDRIG", bg: `${T.textDim}15` },
};

/* ── Platform Badge ─────────────────────────────────────────────────── */
function PlatformBadge({ platform }: { platform: string }) {
  const colors: Record<string, string> = {
    whatsapp: T.whatsapp, telegram: T.telegram, email: T.email, phone: T.phone,
  };
  const color = colors[platform] || T.textDim;
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, textTransform: "uppercase",
      letterSpacing: "0.08em", color, background: `${color}15`,
      padding: "2px 8px", borderRadius: 6, border: `1px solid ${color}30`,
    }}>
      {platform}
    </span>
  );
}

/* ── Component ──────────────────────────────────────────────────────── */
export function EscalationsPage() {
  const { t } = useI18n();
  const [handoffs, setHandoffs] = useState<Handoff[]>([]);
  const [apiStats, setApiStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");

  // Token Banner
  const [activeToken, setActiveToken] = useState<string | null>(null);
  const [tokenForUser, setTokenForUser] = useState<string | null>(null);

  // Link Member Modal
  const [linkDialogUserId, setLinkDialogUserId] = useState<string | null>(null);
  const [memberSearch, setMemberSearch] = useState("");
  const [memberResults, setMemberResults] = useState<MemberResult[]>([]);
  const [searchingMembers, setSearchingMembers] = useState(false);

  // Resolve Modal
  const [confirmResolveUserId, setConfirmResolveUserId] = useState<string | null>(null);

  // Feedback
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [handoffsRes, statsRes] = await Promise.all([
        apiFetch("/admin/handoffs"),
        apiFetch("/admin/stats"),
      ]);
      if (handoffsRes.ok) setHandoffs(await handoffsRes.json());
      if (statsRes.ok) setApiStats(await statsRes.json());
    } catch (e) {
      console.error("EscalationsPage fetch failed", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* ── Member Search ────────────────────────────────────────────────── */
  const searchMembers = useCallback(async (query: string) => {
    if (!query.trim()) { setMemberResults([]); return; }
    setSearchingMembers(true);
    try {
      const res = await apiFetch(`/admin/members/search-for-link?q=${encodeURIComponent(query)}`);
      if (res.ok) setMemberResults(await res.json());
    } finally {
      setSearchingMembers(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { if (memberSearch.trim()) searchMembers(memberSearch); }, 300);
    return () => clearTimeout(timer);
  }, [memberSearch, searchMembers]);

  /* ── Link Member ──────────────────────────────────────────────────── */
  const linkMember = useCallback(async (userId: string, memberId: string) => {
    setActionError("");
    try {
      const res = await apiFetch(`/admin/chats/${userId}/link-member`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: memberId }),
      });
      if (res.ok) {
        setActionSuccess(`Mitglied ${memberId} erfolgreich verknüpft`);
        setLinkDialogUserId(null);
        setMemberSearch("");
        setMemberResults([]);
        fetchData();
        setTimeout(() => setActionSuccess(""), 4000);
      } else {
        const data = await res.json().catch(() => ({}));
        setActionError(data.detail || "Verknüpfung fehlgeschlagen");
      }
    } catch {
      setActionError("Fehler bei der Verknüpfung");
    }
  }, [fetchData]);

  /* ── Generate Token (Legacy) ──────────────────────────────────────── */
  const handleGenerateToken = useCallback(async (userId: string, memberId: string) => {
    if (!memberId.trim()) {
      setActionError(t("escalations.memberIdError"));
      return;
    }
    try {
      const res = await apiFetch("/admin/tokens", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_id: memberId.trim(), user_id: userId }),
      });
      if (res.ok) {
        const data = await res.json();
        setActiveToken(data.token);
        setTokenForUser(userId);
        setLinkDialogUserId(null);
        setMemberSearch("");
        setActionError("");
        fetchData();
      } else {
        setActionError(t("escalations.tokenError"));
      }
    } catch {
      setActionError(t("escalations.tokenError"));
    }
  }, [fetchData, t]);

  /* ── Resolve Handoff ──────────────────────────────────────────────── */
  const resolveHandoff = useCallback(async (userId: string) => {
    try {
      const res = await apiFetch(`/admin/handoffs/${userId}/resolve`, { method: "POST" });
      if (res.ok) {
        setConfirmResolveUserId(null);
        setActionSuccess("Eskalation erfolgreich aufgelöst");
        fetchData();
        setTimeout(() => setActionSuccess(""), 3000);
      } else {
        setActionError(t("escalations.handoffError"));
      }
    } catch {
      setActionError(t("escalations.handoffError"));
    }
  }, [fetchData, t]);

  /* ── Derived ──────────────────────────────────────────────────────── */
  const openCount = apiStats?.active_handoffs ?? handoffs.length;
  const highPriorityCount = handoffs.filter(h => !h.member_id).length;

  const filteredHandoffs = useMemo(() => {
    if (!search.trim()) return handoffs;
    const term = search.toLowerCase();
    return handoffs.filter(h =>
      (h.user_name || "").toLowerCase().includes(term) ||
      h.user_id.toLowerCase().includes(term) ||
      (h.member_id || "").toLowerCase().includes(term) ||
      (h.platform || "").toLowerCase().includes(term)
    );
  }, [handoffs, search]);

  /* ── Render ───────────────────────────────────────────────────────── */
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Header */}
      <SectionHeader
        title={t("escalations.title")}
        subtitle={t("escalations.subtitle")}
        action={
          <button onClick={fetchData} style={btnSecondary}>
            <RefreshCw size={14} /> Aktualisieren
          </button>
        }
      />

      {/* Token Banner */}
      {activeToken && (
        <div style={{
          background: T.accentDim, border: `1px solid ${T.accent}40`,
          borderRadius: 12, padding: "16px 20px",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={statIcon(T.accent)}>
              <Shield size={20} />
            </div>
            <div>
              <div style={{ fontSize: 10, color: T.textMuted, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                Verifizierungscode{tokenForUser ? ` · ${tokenForUser}` : ""}
              </div>
              <div style={{ fontSize: 28, fontFamily: "'JetBrains Mono', monospace", fontWeight: 800, color: T.accentLight, letterSpacing: "0.2em" }}>
                {activeToken}
              </div>
            </div>
          </div>
          <button
            onClick={() => { setActiveToken(null); setTokenForUser(null); }}
            style={{ ...btnSecondary, borderColor: `${T.accent}40` }}
          >
            Schließen
          </button>
        </div>
      )}

      {/* Status Alerts */}
      {actionSuccess && (
        <div style={{
          padding: "12px 20px", borderRadius: 12,
          background: T.successDim, border: `1px solid ${T.success}40`,
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.success, fontWeight: 600,
        }}>
          <CheckCircle2 size={16} /> {actionSuccess}
        </div>
      )}
      {actionError && (
        <div style={{
          padding: "12px 20px", borderRadius: 12,
          background: T.dangerDim, border: `1px solid ${T.danger}40`,
          display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.danger, fontWeight: 600,
        }}>
          <XCircle size={16} /> {actionError}
          <button onClick={() => setActionError("")} style={{ marginLeft: "auto", background: "none", border: "none", color: T.danger, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Offene Eskalationen</div>
            <div style={statValue(T.danger)}>{openCount}</div>
          </div>
          <div style={statIcon(T.danger)}><AlertTriangle size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Hohe Priorität</div>
            <div style={statValue(T.warning)}>{highPriorityCount}</div>
          </div>
          <div style={statIcon(T.warning)}><Shield size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Ø Bearbeitungszeit</div>
            <div style={statValue()}>–</div>
            <div style={{ fontSize: 10, color: T.textDim }}>min</div>
          </div>
          <div style={statIcon(T.info)}><Clock size={20} /></div>
        </Card>
        <Card style={statCard}>
          <div>
            <div style={statLabel}>Heute gelöst</div>
            <div style={statValue(T.success)}>–</div>
          </div>
          <div style={statIcon(T.success)}><CheckCircle2 size={20} /></div>
        </Card>
      </div>

      {/* Escalation Queue */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{
          padding: "16px 20px", borderBottom: `1px solid ${T.border}`,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          background: `${T.surface}80`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <AlertTriangle size={16} color={T.danger} />
            <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Eskalations-Queue</span>
            <Badge variant="danger" size="xs">{filteredHandoffs.length}</Badge>
          </div>
          <div style={{ position: "relative", width: 240 }}>
            <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
            <input
              style={{ ...inputBase, paddingLeft: 34, fontSize: 12 }}
              placeholder="Eskalation suchen…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div style={{ padding: 12 }}>
          {isLoading ? (
            <div style={{ padding: 40, textAlign: "center", color: T.textMuted }}>
              <RefreshCw size={20} style={{ animation: "spin 1s linear infinite", marginBottom: 8 }} />
              <div style={{ fontSize: 13 }}>Lade Eskalationen…</div>
            </div>
          ) : filteredHandoffs.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
              <div style={{
                width: 64, height: 64, borderRadius: "50%",
                background: `${T.success}15`, display: "flex", alignItems: "center", justifyContent: "center",
                border: `1px solid ${T.success}30`,
              }}>
                <CheckCircle size={28} color={T.success} />
              </div>
              <div>
                <div style={{ fontWeight: 700, color: T.text, marginBottom: 4 }}>{t("escalations.allClear")}</div>
                <div style={{ fontSize: 13, color: T.textMuted }}>{t("escalations.noEscalations")}</div>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {filteredHandoffs.map((h) => {
                const priority = getPriority(h);
                const config = priorityConfig[priority];
                return (
                  <div
                    key={h.user_id}
                    style={{
                      padding: "16px 20px", borderRadius: 12,
                      background: T.surfaceAlt,
                      border: `1px solid ${priority === "high" ? `${T.danger}30` : T.border}`,
                      display: "flex", alignItems: "center", gap: 16,
                      transition: "all 0.15s ease",
                    }}
                  >
                    {/* Priority Indicator */}
                    <div style={{
                      width: 4, height: 52, borderRadius: 2,
                      background: config.color, flexShrink: 0,
                    }} />

                    {/* User Avatar */}
                    <div style={{
                      width: 44, height: 44, borderRadius: 12,
                      background: h.member_id ? `${T.success}15` : `${T.warning}15`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      color: h.member_id ? T.success : T.warning,
                      fontWeight: 800, fontSize: 16, flexShrink: 0,
                      border: `1px solid ${h.member_id ? `${T.success}30` : `${T.warning}30`}`,
                    }}>
                      {(h.user_name || "U")[0].toUpperCase()}
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>
                          {h.user_name || h.user_id.slice(0, 16)}
                        </span>
                        <PlatformBadge platform={h.platform || "unknown"} />
                        <Badge
                          variant={priority === "high" ? "danger" : "warning"}
                          size="xs"
                        >
                          {config.label}
                        </Badge>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: T.textMuted }}>
                        {h.member_id ? (
                          <span style={{ display: "flex", alignItems: "center", gap: 4, color: T.success }}>
                            <CheckCircle2 size={12} /> Verifiziert: {h.member_id}
                          </span>
                        ) : (
                          <span style={{ display: "flex", alignItems: "center", gap: 4, color: T.warning }}>
                            <AlertTriangle size={12} /> Nicht verifiziert
                          </span>
                        )}
                        <span style={{ color: T.textDim, fontFamily: "monospace", fontSize: 10 }}>
                          {h.user_id}
                        </span>
                      </div>
                      {h.active_token && (
                        <div style={{
                          marginTop: 6, display: "inline-flex", alignItems: "center", gap: 6,
                          padding: "3px 10px", borderRadius: 6,
                          background: T.accentDim, border: `1px solid ${T.accent}40`,
                        }}>
                          <Shield size={10} color={T.accent} />
                          <span style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: T.accentLight, letterSpacing: "0.1em" }}>
                            {h.active_token}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                      {!h.member_id && (
                        <button
                          onClick={() => {
                            setLinkDialogUserId(h.user_id);
                            setMemberSearch("");
                            setMemberResults([]);
                            setActionError("");
                          }}
                          style={btnPrimary}
                        >
                          <Link2 size={14} /> {t("escalations.linkMember")}
                        </button>
                      )}
                      <button
                        onClick={() => setConfirmResolveUserId(h.user_id)}
                        style={btnSecondary}
                      >
                        <CheckCircle2 size={14} /> Lösen
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      {/* Info Card */}
      <Card style={{ padding: "16px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={statIcon(T.info)}>
          <Info size={18} />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>
            Wie funktioniert die Eskalation?
          </div>
          <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
            Wenn ein Nutzer im Chat menschliche Hilfe anfordert oder die KI einen Fall nicht lösen kann,
            wird automatisch eine Eskalation erstellt. Nicht verifizierte Nutzer erhalten die höchste Priorität.
            Sie können Nutzer manuell mit einem Mitglied verknüpfen, um die Identität zu bestätigen,
            oder die Eskalation auflösen, damit die KI wieder übernimmt.
          </p>
        </div>
      </Card>

      {/* Link Member Modal */}
      <Modal
        open={!!linkDialogUserId}
        onClose={() => setLinkDialogUserId(null)}
        title={t("escalations.linkMember")}
        subtitle={linkDialogUserId ? `Eskalation: ${linkDialogUserId}` : ""}
        width="min(560px, 90vw)"
      >
        {linkDialogUserId && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "4px 0" }}>
            {/* Search Input */}
            <div style={{ position: "relative" }}>
              <Search size={14} style={{ position: "absolute", left: 14, top: 13, color: T.textDim }} />
              <input
                style={{ ...inputBase, paddingLeft: 36 }}
                placeholder="Mitglied suchen (Name, E-Mail, Telefon, Mitgliedsnr.)…"
                value={memberSearch}
                onChange={(e) => setMemberSearch(e.target.value)}
                autoFocus
              />
              {searchingMembers && (
                <RefreshCw size={14} style={{ position: "absolute", right: 14, top: 13, color: T.accent, animation: "spin 1s linear infinite" }} />
              )}
            </div>

            {/* Search Results */}
            <div style={{
              maxHeight: 300, overflowY: "auto", borderRadius: 10,
              border: `1px solid ${T.border}`, background: T.surface,
            }} className="custom-scrollbar">
              {memberResults.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", color: T.textDim, fontSize: 12 }}>
                  {memberSearch.trim() ? (searchingMembers ? "Suche…" : "Keine Kontakte gefunden") : "Suchbegriff eingeben, um Kontakte zu finden"}
                </div>
              ) : (
                memberResults.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => linkMember(linkDialogUserId, String(m.customer_id))}
                    style={{
                      width: "100%", textAlign: "left",
                      padding: "14px 16px", borderBottom: `1px solid ${T.border}`,
                      background: "transparent", border: "none", cursor: "pointer",
                      color: T.text, transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = T.surfaceAlt)}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>
                          {m.first_name} {m.last_name}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 11, color: T.textMuted }}>
                          {m.member_number && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Hash size={10} /> {m.member_number}
                            </span>
                          )}
                          {m.email && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Mail size={10} /> {m.email}
                            </span>
                          )}
                          {m.phone_number && (
                            <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                              <Phone size={10} /> {m.phone_number}
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{
                        padding: "6px 12px", borderRadius: 8,
                        background: T.accentDim, color: T.accent,
                        fontSize: 11, fontWeight: 700,
                        display: "flex", alignItems: "center", gap: 6,
                      }}>
                        <Link2 size={12} /> Verknüpfen
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>

            {/* Manual Input + Token Generation */}
            <div style={{
              padding: "12px 16px", borderRadius: 10,
              background: T.surfaceAlt, border: `1px solid ${T.border}`,
            }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Oder manuell verknüpfen / Token generieren
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  style={{ ...inputBase, flex: 1, fontSize: 12 }}
                  placeholder={t("escalations.memberId")}
                  value={memberSearch}
                  onChange={(e) => setMemberSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && memberSearch.trim()) {
                      linkMember(linkDialogUserId, memberSearch.trim());
                    }
                  }}
                />
                <button
                  onClick={() => {
                    if (memberSearch.trim()) linkMember(linkDialogUserId, memberSearch.trim());
                  }}
                  style={{ ...btnPrimary, padding: "8px 14px" }}
                >
                  <Link2 size={14} /> Verknüpfen
                </button>
                <button
                  onClick={() => {
                    if (memberSearch.trim()) handleGenerateToken(linkDialogUserId, memberSearch.trim());
                  }}
                  style={{ ...btnSecondary, padding: "8px 14px" }}
                  title="Verifizierungstoken generieren"
                >
                  <Shield size={14} /> Token
                </button>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button onClick={() => setLinkDialogUserId(null)} style={btnSecondary}>
                Abbrechen
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Resolve Confirmation Modal */}
      <Modal
        open={!!confirmResolveUserId}
        onClose={() => setConfirmResolveUserId(null)}
        title={t("escalations.resolveHandoff")}
        subtitle={confirmResolveUserId ? `Eskalation für ${confirmResolveUserId} wird geschlossen.` : ""}
        width="min(460px, 90vw)"
      >
        {confirmResolveUserId && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <p style={{ fontSize: 13, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
              Die KI übernimmt danach wieder automatisch die Kommunikation mit diesem Nutzer.
              Stellen Sie sicher, dass das Anliegen gelöst wurde.
            </p>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button onClick={() => setConfirmResolveUserId(null)} style={btnSecondary}>
                Abbrechen
              </button>
              <button
                onClick={() => void resolveHandoff(confirmResolveUserId)}
                style={btnPrimary}
              >
                <CheckCircle2 size={14} /> Auflösen
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
