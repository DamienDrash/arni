"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Globe, CheckCircle2, XCircle, RefreshCw, Trash2, Link2, Clock,
  Database, FileText, AlertTriangle, Zap, Settings, ExternalLink,
  ChevronRight, Layers, BookOpen, Info,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Modal } from "@/components/ui/Modal";
import { T } from "@/lib/tokens";
import { apiFetch } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";

/* ── Types ──────────────────────────────────────────────────────────── */
type NotionConnection = {
  connected: boolean;
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
  parent_type: string;
  parent_name: string;
  last_edited: string;
  synced: boolean;
  sync_status: string;
  chunk_count: number;
};

type SyncLog = {
  id: string;
  type: string;
  status: string;
  pages_processed: number;
  started_at: string;
  completed_at: string | null;
  error: string | null;
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
  transition: "all 0.2s ease",
};
const btnSecondary: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt,
  color: T.text, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
  transition: "all 0.2s ease",
};
const btnDanger: React.CSSProperties = {
  borderRadius: 10, border: `1px solid ${T.danger}40`, background: T.dangerDim,
  color: T.danger, fontWeight: 600, padding: "8px 14px", cursor: "pointer",
  display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
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

/* ── Component ──────────────────────────────────────────────────────── */
export default function NotionSettingsPage() {
  const currentUser = getStoredUser();
  const isSystemAdmin = currentUser?.role === "system_admin";

  const [connection, setConnection] = useState<NotionConnection | null>(null);
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showDisconnect, setShowDisconnect] = useState(false);
  const [pageSearch, setPageSearch] = useState("");

  /* ── Data Loading ─────────────────────────────────────────────────── */
  const loadConnection = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/status");
      if (res.ok) setConnection(await res.json());
      else setConnection({ connected: false, workspace_name: null, workspace_icon: null, connected_at: null, last_sync_at: null, last_sync_status: null, webhook_active: false, pages_synced: 0, databases_synced: 0 });
    } catch { /* ignore */ }
  }, []);

  const loadPages = useCallback(async () => {
    try {
      const res = await apiFetch("/memory-platform/notion/pages");
      if (res.ok) setPages(await res.json());
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
    Promise.all([loadConnection(), loadPages(), loadSyncLogs()]).finally(() => setLoading(false));
  }, [loadConnection, loadPages, loadSyncLogs]);

  /* ── Actions ──────────────────────────────────────────────────────── */
  async function connectNotion() {
    try {
      const res = await apiFetch("/memory-platform/notion/connect", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        if (data.auth_url) {
          window.open(data.auth_url, "_blank", "width=600,height=700");
        }
      } else {
        setError("Verbindung konnte nicht hergestellt werden");
      }
    } catch { setError("Netzwerkfehler"); }
  }

  async function disconnectNotion() {
    try {
      const res = await apiFetch("/memory-platform/notion/disconnect", { method: "POST" });
      if (res.ok) {
        setConnection({ connected: false, workspace_name: null, workspace_icon: null, connected_at: null, last_sync_at: null, last_sync_status: null, webhook_active: false, pages_synced: 0, databases_synced: 0 });
        setPages([]); setSyncLogs([]);
        setSuccess("Notion-Verbindung getrennt"); setTimeout(() => setSuccess(""), 3000);
      } else setError("Trennung fehlgeschlagen");
    } catch { setError("Netzwerkfehler"); }
    setShowDisconnect(false);
  }

  async function triggerSync() {
    setSyncing(true); setError("");
    try {
      const res = await apiFetch("/memory-platform/notion/sync", { method: "POST" });
      if (res.ok) {
        setSuccess("Synchronisierung gestartet"); setTimeout(() => setSuccess(""), 3000);
        setTimeout(() => { void loadPages(); void loadSyncLogs(); void loadConnection(); }, 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Sync fehlgeschlagen");
      }
    } catch { setError("Netzwerkfehler"); }
    setSyncing(false);
  }

  async function togglePageSync(pageId: string, enable: boolean) {
    try {
      const res = await apiFetch(`/memory-platform/notion/pages/${pageId}/sync`, {
        method: enable ? "POST" : "DELETE",
      });
      if (res.ok) {
        setPages((prev) => prev.map((p) => p.page_id === pageId ? { ...p, synced: enable, sync_status: enable ? "pending" : "disabled" } : p));
      }
    } catch { /* ignore */ }
  }

  const filteredPages = pages.filter((p) =>
    p.title.toLowerCase().includes(pageSearch.toLowerCase()) ||
    p.parent_name.toLowerCase().includes(pageSearch.toLowerCase())
  );

  /* ── Render ───────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: 80 }}>
        <RefreshCw size={24} style={{ color: T.textDim, animation: "spin 1s linear infinite" }} />
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <SectionHeader
        title="Notion-Integration"
        subtitle="Verbinden Sie Ihre Notion-Wissensdatenbank mit ARIIA"
        action={
          connection?.connected ? (
            <div style={{ display: "flex", gap: 10 }}>
              <button onClick={triggerSync} disabled={syncing} style={btnSecondary}>
                <RefreshCw size={14} style={syncing ? { animation: "spin 1s linear infinite" } : {}} />
                {syncing ? "Synchronisiere…" : "Jetzt synchronisieren"}
              </button>
              <button onClick={() => setShowDisconnect(true)} style={btnDanger}>
                <Trash2 size={14} /> Trennen
              </button>
            </div>
          ) : undefined
        }
      />

      {/* Alerts */}
      {success && (
        <div style={{ padding: "12px 20px", borderRadius: 12, background: T.successDim, border: `1px solid ${T.success}40`, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.success, fontWeight: 600 }}>
          <CheckCircle2 size={16} /> {success}
        </div>
      )}
      {error && (
        <div style={{ padding: "12px 20px", borderRadius: 12, background: T.dangerDim, border: `1px solid ${T.danger}40`, display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: T.danger, fontWeight: 600 }}>
          <XCircle size={16} /> {error}
          <button onClick={() => setError("")} style={{ marginLeft: "auto", background: "none", border: "none", color: T.danger, cursor: "pointer" }}>✕</button>
        </div>
      )}

      {/* ── Not Connected State ───────────────────────────────────────── */}
      {!connection?.connected && (
        <Card style={{ padding: 48, textAlign: "center" }}>
          <div style={{ width: 80, height: 80, borderRadius: 20, background: T.surfaceAlt, display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px", border: `1px solid ${T.border}` }}>
            <Globe size={36} style={{ color: T.textMuted }} />
          </div>
          <h3 style={{ fontSize: 20, fontWeight: 700, color: T.text, margin: "0 0 8px" }}>Notion verbinden</h3>
          <p style={{ fontSize: 14, color: T.textMuted, maxWidth: 480, margin: "0 auto 24px", lineHeight: 1.6 }}>
            Verbinden Sie Ihren Notion-Workspace, um Seiten und Datenbanken automatisch als Wissensquelle zu synchronisieren.
            Die KI kann dann auf Ihre Notion-Inhalte zugreifen und diese in Gesprächen und Kampagnen nutzen.
          </p>
          <button onClick={connectNotion} style={{ ...btnPrimary, padding: "12px 28px", fontSize: 14 }}>
            <Link2 size={18} /> Mit Notion verbinden
          </button>
          <div style={{ marginTop: 24, display: "flex", justifyContent: "center", gap: 32 }}>
            {[
              { icon: <Zap size={14} />, text: "Automatische Synchronisierung" },
              { icon: <Database size={14} />, text: "Seiten & Datenbanken" },
              { icon: <BookOpen size={14} />, text: "Echtzeit-Updates via Webhooks" },
            ].map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.textDim }}>
                {item.icon} {item.text}
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Connected State ───────────────────────────────────────────── */}
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
                <div style={statLabel}>Datenbanken</div>
                <div style={statValue(T.info)}>{connection.databases_synced}</div>
              </div>
              <div style={statIcon(T.info)}><Database size={20} /></div>
            </Card>
            <Card style={statCard}>
              <div>
                <div style={statLabel}>Webhook</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: connection.webhook_active ? T.success : T.textDim }}>
                  {connection.webhook_active ? "Aktiv" : "Inaktiv"}
                </div>
              </div>
              <div style={statIcon(connection.webhook_active ? T.success : T.textDim)}>
                <Zap size={20} />
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
                <input value={pageSearch} onChange={(e) => setPageSearch(e.target.value)} placeholder="Seite suchen…" style={{ ...inputBase, fontSize: 11, paddingRight: 12 }} />
              </div>
            </div>
            {filteredPages.length === 0 ? (
              <div style={{ padding: 32, textAlign: "center", color: T.textDim, fontSize: 13 }}>
                {pages.length === 0 ? "Noch keine Seiten synchronisiert. Starten Sie eine Synchronisierung." : "Keine Seiten gefunden."}
              </div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${T.border}` }}>
                      {["Seite", "Übergeordnet", "Chunks", "Status", "Zuletzt bearbeitet", "Sync"].map((h, i) => (
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
                            <span style={{ fontSize: 13, color: T.text, fontWeight: 500 }}>{page.title}</span>
                          </div>
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{page.parent_name}</td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{page.chunk_count}</td>
                        <td style={{ padding: "10px 16px" }}>
                          <Badge variant={page.sync_status === "synced" ? "success" : page.sync_status === "pending" ? "warning" : page.sync_status === "error" ? "danger" : "default"} size="xs">
                            {page.sync_status === "synced" ? "Synchronisiert" : page.sync_status === "pending" ? "Ausstehend" : page.sync_status === "error" ? "Fehler" : page.sync_status}
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
                      {["Typ", "Status", "Seiten", "Gestartet", "Abgeschlossen", "Fehler"].map((h, i) => (
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
                          <Badge variant={log.status === "completed" ? "success" : log.status === "running" ? "warning" : "danger"} size="xs">
                            {log.status === "completed" ? "Abgeschlossen" : log.status === "running" ? "Läuft…" : "Fehler"}
                          </Badge>
                        </td>
                        <td style={{ padding: "10px 16px", fontSize: 12, color: T.textMuted }}>{log.pages_processed}</td>
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

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
