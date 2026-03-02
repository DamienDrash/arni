"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen, CheckCircle2, Clock, Database, ExternalLink, FileText,
  Info, Key, Link2, RefreshCw, Search, Settings, Shield, Trash2, Unlink, Zap,
} from "lucide-react";

import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";

/* ── Types ──────────────────────────────────────────────────────────── */
type ConnectionStatus = {
  connected: boolean;
  platform_configured: boolean;
  workspace_name: string | null;
  workspace_icon: string | null;
  connected_at: string | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  webhook_active: boolean;
  pages_synced: number;
  databases_synced: number;
};

type NotionPage = {
  page_id: string;
  title: string;
  type: string;
  url: string;
  last_edited: string;
  synced: boolean;
  sync_status: string;
  chunk_count: number;
  parent_type: string;
  parent_name: string;
};

type SyncLog = {
  id: string;
  type: string;
  status: string;
  pages_processed: number;
  chunks_created: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

type PlatformConfig = {
  configured: boolean;
  client_id: string;
  has_secret: boolean;
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
};
const btnPrimary: React.CSSProperties = {
  border: "none", borderRadius: 10, background: T.accent, color: "#fff",
  fontWeight: 700, padding: "10px 20px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13,
};
const btnSecondary: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt,
  color: T.text, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
};
const btnDanger: React.CSSProperties = {
  ...btnPrimary, background: T.danger,
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "–";
  try {
    return new Date(dateStr).toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return dateStr; }
}

/* ── Admin Config Panel ────────────────────────────────────────────── */
function NotionAdminConfig({
  onSaved,
}: {
  onSaved: () => void;
}) {
  const [config, setConfig] = useState<PlatformConfig | null>(null);
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await apiFetch("/memory-platform/notion/admin/config");
        if (res.ok) {
          const data = await res.json();
          setConfig(data);
          setClientId(data.client_id || "");
        }
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  const handleSave = async () => {
    if (!clientId.trim()) {
      setError("Client ID ist erforderlich");
      return;
    }
    if (!clientSecret.trim() && !config?.has_secret) {
      setError("Client Secret ist erforderlich");
      return;
    }

    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const res = await apiFetch("/memory-platform/notion/admin/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim() || "KEEP_EXISTING",
        }),
      });

      if (res.ok) {
        setSuccess("Notion-Konfiguration gespeichert!");
        setClientSecret("");
        setConfig({ configured: true, client_id: clientId.trim(), has_secret: true });
        onSaved();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Fehler beim Speichern");
      }
    } catch {
      setError("Verbindungsfehler");
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <Card style={{ padding: 32, textAlign: "center" }}>
        <RefreshCw size={18} style={{ animation: "spin 1s linear infinite", color: T.textDim }} />
      </Card>
    );
  }

  return (
    <Card style={{ padding: 0, overflow: "hidden" }}>
      <div style={{
        padding: "16px 20px",
        borderBottom: `1px solid ${T.border}`,
        display: "flex", alignItems: "center", gap: 10,
        background: `${T.accent}08`,
      }}>
        <div style={statIcon(T.accent)}><Settings size={18} /></div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Notion OAuth-Konfiguration</div>
          <div style={{ fontSize: 11, color: T.textMuted }}>
            Platform-Level Einstellungen für die Notion-Integration aller Mandanten
          </div>
        </div>
        {config?.configured && (
          <Badge variant="success" size="xs" style={{ marginLeft: "auto" }}>Konfiguriert</Badge>
        )}
      </div>

      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        {error && (
          <div style={{ padding: "10px 16px", borderRadius: 8, background: T.dangerDim, border: `1px solid ${T.danger}40`, fontSize: 12, color: T.danger, fontWeight: 600 }}>
            {error}
          </div>
        )}
        {success && (
          <div style={{ padding: "10px 16px", borderRadius: 8, background: T.successDim, border: `1px solid ${T.success}40`, fontSize: 12, color: T.success, fontWeight: 600 }}>
            {success}
          </div>
        )}

        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 16px", borderRadius: 10, background: `${T.info}10`, border: `1px solid ${T.info}20` }}>
          <Info size={16} style={{ color: T.info, flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6 }}>
            Erstellen Sie eine Notion-Integration unter{" "}
            <a href="https://www.notion.so/my-integrations" target="_blank" rel="noopener noreferrer" style={{ color: T.accent, textDecoration: "underline" }}>
              notion.so/my-integrations
            </a>
            {" "}und tragen Sie die OAuth-Credentials hier ein. Alle Mandanten nutzen diese gemeinsame Integration, erhalten aber jeweils einen eigenen Zugangstoken.
          </div>
        </div>

        <div>
          <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
            OAuth Client ID
          </label>
          <div style={{ position: "relative" }}>
            <Key size={14} style={{ position: "absolute", left: 12, top: 12, color: T.textDim }} />
            <input
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="z.B. abc123-def456-..."
              style={{ ...inputBase, paddingLeft: 34 }}
            />
          </div>
        </div>

        <div>
          <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
            OAuth Client Secret {config?.has_secret && <span style={{ color: T.success, fontWeight: 400 }}>(gespeichert – leer lassen um beizubehalten)</span>}
          </label>
          <div style={{ position: "relative" }}>
            <Shield size={14} style={{ position: "absolute", left: 12, top: 12, color: T.textDim }} />
            <input
              type="password"
              value={clientSecret}
              onChange={(e) => setClientSecret(e.target.value)}
              placeholder={config?.has_secret ? "••••••••••••••••" : "secret_..."}
              style={{ ...inputBase, paddingLeft: 34 }}
            />
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button onClick={handleSave} disabled={saving} style={btnPrimary}>
            {saving ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <CheckCircle2 size={14} />}
            {saving ? "Speichere…" : "Konfiguration speichern"}
          </button>
        </div>
      </div>
    </Card>
  );
}

/* ── Main Component ───────────────────────────────────────────────── */
export default function NotionIntegration({ isAdmin = false }: { isAdmin?: boolean }) {
  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [pageSearch, setPageSearch] = useState("");
  const [showDisconnect, setShowDisconnect] = useState(false);
  const [error, setError] = useState("");

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const loadStatus = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/status");
      if (res.ok) setConnection(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadPages = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/pages");
      if (res.ok) setPages(await res.json());
    } catch { /* ignore */ }
  }, []);

  const loadSyncedPages = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/synced-pages");
      if (res.ok) {
        const synced = await res.json();
        setPages(prev => {
          const map = new Map(prev.map(p => [p.page_id, p]));
          for (const sp of synced) {
            if (map.has(sp.page_id)) {
              const existing = map.get(sp.page_id)!;
              map.set(sp.page_id, { ...existing, ...sp });
            } else {
              map.set(sp.page_id, sp);
            }
          }
          return Array.from(map.values());
        });
      }
    } catch { /* ignore */ }
  }, []);

  const loadSyncLogs = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/sync-logs");
      if (res.ok) setSyncLogs(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadStatus().then(() => setLoading(false));
  }, [loadStatus]);

  useEffect(() => {
    if (connection?.connected) {
      Promise.all([loadPages(), loadSyncedPages(), loadSyncLogs()]);
    }
  }, [connection?.connected, loadPages, loadSyncedPages, loadSyncLogs]);

  /* ── Actions ──────────────────────────────────────────────────────── */
  const connectNotion = async () => {
    setConnecting(true);
    setError("");
    try {
      const redirectUri = `${window.location.origin}/knowledge?notion_callback=true`;
      const res = await apiFetch(`/memory-platform/notion/oauth-url?redirect_uri=${encodeURIComponent(redirectUri)}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Fehler beim Starten der Notion-Verbindung");
        setConnecting(false);
        return;
      }
      const data = await res.json();
      if (data.oauth_url) {
        window.open(data.oauth_url, "_blank", "width=600,height=700");
      }
    } catch (e) {
      setError("Verbindungsfehler");
    }
    setConnecting(false);
  };

  const disconnectNotion = async () => {
    try {
      await apiFetch("/memory-platform/notion/disconnect", { method: "POST" });
      setConnection({
        connected: false,
        platform_configured: connection?.platform_configured ?? false,
        workspace_name: null, workspace_icon: null,
        connected_at: null, last_sync_at: null, last_sync_status: null,
        webhook_active: false, pages_synced: 0, databases_synced: 0,
      });
      setPages([]);
      setSyncLogs([]);
      setShowDisconnect(false);
    } catch { setError("Fehler beim Trennen"); }
  };

  const triggerSync = async () => {
    setSyncing(true);
    setError("");
    try {
      const res = await apiFetch("/memory-platform/notion/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        await Promise.all([loadStatus(), loadSyncedPages(), loadSyncLogs()]);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Sync fehlgeschlagen");
      }
    } catch { setError("Sync-Fehler"); }
    setSyncing(false);
  };

  const togglePageSync = async (pageId: string, enable: boolean) => {
    try {
      const res = await apiFetch(`/memory-platform/notion/pages/${pageId}/sync?enable=${enable}`, { method: "POST" });
      if (res.ok) {
        await Promise.all([loadPages(), loadSyncedPages(), loadStatus()]);
      }
    } catch { /* ignore */ }
  };

  const filteredPages = useMemo(() => {
    if (!pageSearch) return pages;
    const q = pageSearch.toLowerCase();
    return pages.filter(p => p.title.toLowerCase().includes(q));
  }, [pages, pageSearch]);

  /* ── Render ──────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <Card style={{ padding: 48, textAlign: "center" }}>
        <RefreshCw size={24} style={{ animation: "spin 1s linear infinite", color: T.textDim, marginBottom: 12 }} />
        <div style={{ fontSize: 13, color: T.textDim }}>Notion-Status wird geladen…</div>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Error */}
      {error && (
        <div style={{ padding: "12px 20px", borderRadius: 12, background: T.dangerDim, border: `1px solid ${T.danger}40`, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.danger, fontWeight: 600 }}>
          {error}
          <button onClick={() => setError("")} style={{ marginLeft: "auto", background: "none", border: "none", color: T.danger, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* ── Admin Config Panel (only for system admins) ─────────────── */}
      {isAdmin && (
        <NotionAdminConfig onSaved={loadStatus} />
      )}

      {/* ── Platform Not Configured ────────────────────────────────── */}
      {!connection?.platform_configured && !isAdmin && (
        <Card style={{ padding: "48px 32px", textAlign: "center" }}>
          <div style={{ width: 72, height: 72, borderRadius: 20, background: `${T.warning}15`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
            <Settings size={32} style={{ color: T.warning }} />
          </div>
          <h3 style={{ fontSize: 20, fontWeight: 800, color: T.text, marginBottom: 8 }}>Notion nicht konfiguriert</h3>
          <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 480, margin: "0 auto 24px", lineHeight: 1.6 }}>
            Die Notion-Integration wurde noch nicht vom Platform-Administrator eingerichtet.
            Bitte kontaktieren Sie Ihren Administrator, um die Notion OAuth-Credentials zu konfigurieren.
          </p>
        </Card>
      )}

      {/* ── Not Connected (but platform is configured) ─────────────── */}
      {connection?.platform_configured && !connection?.connected && (
        <Card style={{ padding: "48px 32px", textAlign: "center" }}>
          <div style={{ width: 72, height: 72, borderRadius: 20, background: `${T.accent}15`, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
            <BookOpen size={32} style={{ color: T.accent }} />
          </div>
          <h3 style={{ fontSize: 20, fontWeight: 800, color: T.text, marginBottom: 8 }}>Notion verbinden</h3>
          <p style={{ fontSize: 13, color: T.textMuted, maxWidth: 480, margin: "0 auto 24px", lineHeight: 1.6 }}>
            Verbinden Sie Ihren Notion-Workspace, um Seiten und Datenbanken automatisch in die Wissensdatenbank zu synchronisieren.
            Die KI kann dann auf alle Notion-Inhalte zugreifen.
          </p>
          <button onClick={connectNotion} disabled={connecting} style={btnPrimary}>
            {connecting ? <RefreshCw size={14} style={{ animation: "spin 1s linear infinite" }} /> : <Link2 size={14} />}
            {connecting ? "Verbinde…" : "Mit Notion verbinden"}
          </button>
          <div style={{ marginTop: 20, display: "flex", gap: 16, justifyContent: "center", flexWrap: "wrap" }}>
            {[
              { icon: <Zap size={14} />, text: "Automatische Synchronisierung" },
              { icon: <Database size={14} />, text: "Seiten & Datenbanken" },
              { icon: <BookOpen size={14} />, text: "Echtzeit-Updates via Webhooks" },
            ].map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.textDim, padding: "6px 12px", borderRadius: 8, background: T.surfaceAlt }}>
                {item.icon} {item.text}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Connected State ─────────────────────────────────────────── */}
      {connection?.connected && (
        <>
          {/* Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card style={statCard}>
              <div>
                <div style={statLabel}>Workspace</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text }}>{connection.workspace_name || "–"}</div>
              </div>
              <div style={statIcon(T.success)}><CheckCircle2 size={20} /></div>
            </Card>
            <Card style={statCard}>
              <div>
                <div style={statLabel}>Synchronisierte Seiten</div>
                <div style={statValue(T.accent)}>{connection.pages_synced}</div>
              </div>
              <div style={statIcon(T.accent)}><FileText size={20} /></div>
            </Card>
            <Card style={statCard}>
              <div>
                <div style={statLabel}>Letzter Sync</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: T.text }}>{formatDate(connection.last_sync_at)}</div>
              </div>
              <div style={statIcon(T.info)}><Clock size={20} /></div>
            </Card>
            <Card style={statCard}>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={triggerSync} disabled={syncing} style={{ ...btnPrimary, padding: "8px 14px", fontSize: 12 }}>
                    <RefreshCw size={12} style={syncing ? { animation: "spin 1s linear infinite" } : {}} />
                    {syncing ? "Sync…" : "Jetzt synchronisieren"}
                  </button>
                  <button onClick={() => setShowDisconnect(true)} style={{ ...btnSecondary, padding: "8px 12px" }} title="Trennen">
                    <Unlink size={14} />
                  </button>
                </div>
              </div>
            </Card>
          </div>

          {/* Pages List */}
          <Card style={{ padding: 0, overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <FileText size={16} style={{ color: T.accent }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Notion-Seiten</span>
                <Badge variant="info" size="xs">{pages.length}</Badge>
              </div>
              <div style={{ position: "relative", width: 240 }}>
                <Search size={14} style={{ position: "absolute", left: 12, top: 11, color: T.textDim }} />
                <input value={pageSearch} onChange={(e) => setPageSearch(e.target.value)} placeholder="Seite suchen…" style={{ ...inputBase, fontSize: 11, paddingLeft: 34 }} />
              </div>
            </div>
            {filteredPages.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                {pages.length === 0 ? "Noch keine Seiten gefunden. Starten Sie eine Synchronisierung." : "Keine Seiten gefunden."}
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                      {["Seite", "Typ", "Chunks", "Status", "Zuletzt bearbeitet", "Sync"].map((h, i) => (
                        <th key={i} style={{ padding: "10px 16px", textAlign: "left", fontSize: 10, fontWeight: 800, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPages.map((page) => (
                      <tr key={page.page_id} style={{ borderBottom: `1px solid ${T.border}` }}>
                        <td style={{ padding: "10px 16px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <FileText size={14} style={{ color: T.textDim, flexShrink: 0 }} />
                            <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{page.title || "Untitled"}</span>
                            {page.url && (
                              <a href={page.url} target="_blank" rel="noopener noreferrer" style={{ color: T.textDim, flexShrink: 0 }}>
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                        </td>
                        <td style={{ padding: "10px 16px" }}>
                          <Badge variant={page.type === "database" ? "info" : "default"} size="xs">
                            {page.type === "database" ? "Datenbank" : "Seite"}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{page.chunk_count || "–"}</td>
                        <td style={{ padding: "10px 16px" }}>
                          <Badge variant={
                            page.sync_status === "synced" ? "success" :
                            page.sync_status === "pending" ? "warning" :
                            page.sync_status === "error" ? "danger" :
                            page.sync_status === "disabled" ? "default" :
                            "default"
                          } size="xs">
                            {page.sync_status === "synced" ? "Synchronisiert" :
                             page.sync_status === "pending" ? "Ausstehend" :
                             page.sync_status === "error" ? "Fehler" :
                             page.sync_status === "disabled" ? "Deaktiviert" :
                             page.sync_status === "not_synced" ? "Nicht synchronisiert" :
                             page.sync_status || "–"}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 11, color: T.textDim }}>{formatDate(page.last_edited)}</td>
                        <td style={{ padding: "10px 16px" }}>
                          <button
                            onClick={() => togglePageSync(page.page_id, !page.synced)}
                            style={{
                              padding: "4px 12px", borderRadius: 6, border: "none",
                              background: page.synced ? T.successDim : T.surfaceAlt,
                              color: page.synced ? T.success : T.textDim,
                              fontSize: 11, fontWeight: 600, cursor: "pointer",
                            }}
                          >
                            {page.synced ? "Aktiv" : "Aktivieren"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Sync History */}
          {syncLogs.length > 0 && (
            <Card style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 10 }}>
                <Clock size={16} style={{ color: T.textDim }} />
                <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>Sync-Verlauf</span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                      {["Typ", "Status", "Seiten", "Chunks", "Gestartet", "Abgeschlossen", "Fehler"].map((h, i) => (
                        <th key={i} style={{ padding: "10px 16px", textAlign: "left", fontSize: 10, fontWeight: 800, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {syncLogs.slice(0, 10).map((log) => (
                      <tr key={log.id} style={{ borderBottom: `1px solid ${T.border}` }}>
                        <td style={{ padding: "10px 16px" }}>
                          <Badge variant={log.type === "full" ? "accent" : log.type === "webhook" ? "info" : "default"} size="xs">
                            {log.type === "full" ? "Vollständig" : log.type === "webhook" ? "Webhook" : log.type}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 16px" }}>
                          <Badge variant={log.status === "completed" ? "success" : log.status === "running" ? "warning" : log.status === "partial" ? "warning" : "danger"} size="xs">
                            {log.status === "completed" ? "Abgeschlossen" : log.status === "running" ? "Läuft…" : log.status === "partial" ? "Teilweise" : "Fehler"}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{log.pages_processed}</td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{log.chunks_created}</td>
                        <td style={{ padding: "10px 16px", fontSize: 11, color: T.textDim }}>{formatDate(log.started_at)}</td>
                        <td style={{ padding: "10px 16px", fontSize: 11, color: T.textDim }}>{formatDate(log.completed_at)}</td>
                        <td style={{ padding: "10px 16px", fontSize: 11, color: log.error ? T.danger : T.textDim }}>{log.error || "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {/* Info Card */}
      <Card style={{ padding: "16px 20px", display: "flex", alignItems: "flex-start", gap: 14 }}>
        <div style={statIcon(T.info)}><Info size={18} /></div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Wie funktioniert die Notion-Integration?</div>
          <p style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.6, margin: 0 }}>
            Nach der Verbindung mit Ihrem Notion-Workspace werden ausgewählte Seiten und Datenbanken automatisch synchronisiert.
            Die Inhalte werden in Chunks aufgeteilt und vektorisiert, sodass die KI sie in Gesprächen und Kampagnen nutzen kann.
            Über Webhooks werden Änderungen in Notion automatisch erkannt und synchronisiert – ohne manuelle Eingriffe.
          </p>
        </div>
      </Card>

      {/* Disconnect Modal */}
      <Modal open={showDisconnect} title="Notion trennen?" onClose={() => setShowDisconnect(false)} footer={
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={() => setShowDisconnect(false)} style={btnSecondary}>Abbrechen</button>
          <button onClick={disconnectNotion} style={btnDanger}><Trash2 size={14} /> Endgültig trennen</button>
        </div>
      }>
        <p style={{ fontSize: 13, color: T.textMuted, lineHeight: 1.6 }}>
          Wenn Sie die Notion-Verbindung trennen, werden alle synchronisierten Seiten aus der Wissensdatenbank entfernt.
          Die Originaldaten in Notion bleiben unverändert. Sie können die Verbindung jederzeit wiederherstellen.
        </p>
      </Modal>
    </div>
  );
}
