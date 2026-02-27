"use client";

import { useEffect, useState, useCallback, useRef } from "react";

import {
  Server,
  Play,
  Square,
  RotateCw,
  Terminal,
  Activity,
  Cpu,
  HardDrive,
  Network,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Box,
  Layers,
  Info,
  X,
} from "lucide-react";
import { apiFetch } from "@/lib/api";

/* ─── Types ─────────────────────────────────────────────────────────── */

interface Container {
  id: string;
  full_id: string;
  name: string;
  image: string;
  status: string;
  state: string;
  started_at: string;
  uptime: string;
  health: string;
  ports: string[];
  restart_policy: string;
  memory_limit: number;
  labels: Record<string, string>;
  created: string;
}

interface ContainerStats {
  cpu_percent: number;
  memory_usage_mb: number;
  memory_limit_mb: number;
  memory_percent: number;
  network_rx_mb: number;
  network_tx_mb: number;
  pids: number;
}

interface SystemInfo {
  docker_version: string;
  api_version: string;
  os: string;
  kernel: string;
  architecture: string;
  cpus: number;
  memory_total_gb: number;
  containers_total: number;
  containers_running: number;
  containers_stopped: number;
  containers_paused: number;
  images: number;
  storage_driver: string;
  server_time: string;
}

interface ContainerListResponse {
  containers: Container[];
  total: number;
  running: number;
  stopped: number;
}

/* ─── Styles ────────────────────────────────────────────────────────── */

const styles = {
  page: "min-h-screen bg-[var(--bg-primary)] p-6",
  header: "flex items-center justify-between mb-6",
  title: "text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2",
  subtitle: "text-sm text-[var(--text-secondary)] mt-1",
  refreshBtn:
    "flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors text-sm font-medium",
  spinning: "animate-spin",

  // System Info Cards
  infoGrid: "grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6",
  infoCard:
    "bg-[var(--bg-secondary)] rounded-xl p-4 border border-[var(--border-primary)]",
  infoLabel: "text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-1",
  infoValue: "text-lg font-semibold text-[var(--text-primary)]",

  // Summary Cards
  summaryGrid: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6",
  summaryCard:
    "bg-[var(--bg-secondary)] rounded-xl p-5 border border-[var(--border-primary)] flex items-center gap-4",
  summaryIcon: "w-12 h-12 rounded-xl flex items-center justify-center",
  summaryIconGreen: "bg-emerald-500/10 text-emerald-500",
  summaryIconRed: "bg-red-500/10 text-red-500",
  summaryIconBlue: "bg-blue-500/10 text-blue-500",
  summaryNumber: "text-2xl font-bold text-[var(--text-primary)]",
  summaryLabel: "text-sm text-[var(--text-secondary)]",

  // Container Table
  tableWrap:
    "bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-primary)] overflow-hidden",
  tableHeader:
    "px-6 py-4 border-b border-[var(--border-primary)] flex items-center justify-between",
  tableTitle: "text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2",
  toggleBtn:
    "text-xs px-3 py-1.5 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors",
  table: "w-full",
  th: "text-left text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider px-6 py-3 bg-[var(--bg-tertiary)]",
  td: "px-6 py-4 text-sm text-[var(--text-primary)] border-t border-[var(--border-primary)]",
  tdSecondary:
    "px-6 py-4 text-sm text-[var(--text-secondary)] border-t border-[var(--border-primary)]",

  // Status badges
  badgeRunning:
    "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-500",
  badgeStopped:
    "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-500",
  badgeOther:
    "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-yellow-500/10 text-yellow-500",

  // Health badges
  healthHealthy:
    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-500/10 text-emerald-500",
  healthUnhealthy:
    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-red-500/10 text-red-500",
  healthNone:
    "inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-tertiary)]",

  // Action buttons
  actionBtn:
    "p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed",
  actionBtnDanger:
    "p-1.5 rounded-lg hover:bg-red-500/10 transition-colors text-[var(--text-secondary)] hover:text-red-500 disabled:opacity-30 disabled:cursor-not-allowed",

  // Stats row
  statsRow:
    "px-6 py-3 bg-[var(--bg-primary)] border-t border-[var(--border-primary)]",
  statsGrid: "grid grid-cols-2 md:grid-cols-4 gap-4",
  statItem: "flex items-center gap-2",
  statLabel: "text-xs text-[var(--text-tertiary)]",
  statValue: "text-sm font-medium text-[var(--text-primary)]",
  statBar: "w-20 h-1.5 rounded-full bg-[var(--bg-tertiary)] overflow-hidden",
  statBarFill: "h-full rounded-full transition-all duration-500",

  // Log viewer
  logOverlay:
    "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4",
  logModal:
    "bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-primary)] w-full max-w-4xl max-h-[80vh] flex flex-col",
  logHeader:
    "flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)]",
  logTitle: "text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2",
  logClose:
    "p-2 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors",
  logBody:
    "flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-[var(--text-secondary)] bg-[var(--bg-primary)]",
  logLine: "py-0.5 hover:bg-[var(--bg-secondary)] px-2 rounded",
  logFooter:
    "flex items-center justify-between px-6 py-3 border-t border-[var(--border-primary)]",

  // Ports
  portBadge:
    "inline-flex items-center px-2 py-0.5 rounded text-xs bg-blue-500/10 text-blue-400 font-mono",

  // Loading
  loadingWrap: "flex items-center justify-center py-20",
  loadingText: "text-[var(--text-secondary)] ml-3",

  // Error
  errorWrap:
    "flex flex-col items-center justify-center py-20 text-center",
  errorIcon: "text-red-500 mb-4",
  errorText: "text-[var(--text-secondary)] mb-4",
  retryBtn:
    "px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white hover:opacity-90 transition-opacity text-sm font-medium",

  // Confirm dialog
  confirmOverlay:
    "fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4",
  confirmModal:
    "bg-[var(--bg-secondary)] rounded-2xl border border-[var(--border-primary)] p-6 max-w-md w-full",
  confirmTitle: "text-lg font-semibold text-[var(--text-primary)] mb-2",
  confirmText: "text-sm text-[var(--text-secondary)] mb-6",
  confirmActions: "flex justify-end gap-3",
  confirmCancel:
    "px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors text-sm font-medium",
  confirmDanger:
    "px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors text-sm font-medium",
  confirmPrimary:
    "px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white hover:opacity-90 transition-opacity text-sm font-medium",
};

/* ─── Component ─────────────────────────────────────────────────────── */

export default function InfrastructurePage() {
  const [containers, setContainers] = useState<Container[]>([]);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [stats, setStats] = useState<Record<string, ContainerStats>>({});
  const [expandedStats, setExpandedStats] = useState<Set<string>>(new Set());
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [summary, setSummary] = useState({ total: 0, running: 0, stopped: 0 });

  // Log viewer
  const [logContainer, setLogContainer] = useState<Container | null>(null);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [logLoading, setLogLoading] = useState(false);
  const logBodyRef = useRef<HTMLDivElement>(null);

  // Confirm dialog
  const [confirm, setConfirm] = useState<{
    title: string;
    message: string;
    action: () => void;
    danger?: boolean;
  } | null>(null);

  /* ── Data fetching ── */

  const fetchContainers = useCallback(async () => {
    try {
      const res = await apiFetch(`/admin/docker/containers?all=${showAll}`);
      if (!res.ok) throw new Error(await res.text());
      const data: ContainerListResponse = await res.json();
      setContainers(data.containers);
      setSummary({ total: data.total, running: data.running, stopped: data.stopped });
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load containers");
    }
  }, [showAll]);

  const fetchSystemInfo = useCallback(async () => {
    try {
      const res = await apiFetch("/admin/docker/system-info");
      if (!res.ok) return;
      setSystemInfo(await res.json());
    } catch {
      // non-critical
    }
  }, []);

  const fetchStats = useCallback(async (containerId: string) => {
    try {
      const res = await apiFetch(`/admin/docker/containers/${containerId}/stats`);
      if (!res.ok) return;
      const data: ContainerStats = await res.json();
      setStats((prev) => ({ ...prev, [containerId]: data }));
    } catch {
      // non-critical
    }
  }, []);

  const fetchLogs = useCallback(async (container: Container) => {
    setLogContainer(container);
    setLogLoading(true);
    try {
      const res = await apiFetch(`/admin/docker/containers/${container.id}/logs?tail=500`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setLogLines(data.lines || []);
    } catch {
      setLogLines(["Error loading logs"]);
    } finally {
      setLogLoading(false);
    }
  }, []);

  /* ── Initial load ── */

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchContainers(), fetchSystemInfo()]);
      setLoading(false);
    };
    init();
  }, [fetchContainers, fetchSystemInfo]);

  /* ── Auto-refresh stats for expanded containers ── */

  useEffect(() => {
    if (expandedStats.size === 0) return;
    const interval = setInterval(() => {
      expandedStats.forEach((id) => fetchStats(id));
    }, 5000);
    return () => clearInterval(interval);
  }, [expandedStats, fetchStats]);

  /* ── Auto-scroll log viewer ── */

  useEffect(() => {
    if (logBodyRef.current) {
      logBodyRef.current.scrollTop = logBodyRef.current.scrollHeight;
    }
  }, [logLines]);

  /* ── Container actions ── */

  const handleAction = async (
    containerId: string,
    action: "start" | "stop" | "restart"
  ) => {
    setActionLoading(`${containerId}-${action}`);
    try {
      const res = await apiFetch(`/admin/docker/containers/${containerId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeout: 10 }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Action failed");
        return;
      }
      // Refresh after action
      setTimeout(() => fetchContainers(), 2000);
    } catch (err: any) {
      alert(err.message || "Action failed");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchContainers(), fetchSystemInfo()]);
    setRefreshing(false);
  };

  const toggleStats = (containerId: string) => {
    setExpandedStats((prev) => {
      const next = new Set(prev);
      if (next.has(containerId)) {
        next.delete(containerId);
      } else {
        next.add(containerId);
        fetchStats(containerId);
      }
      return next;
    });
  };

  /* ── Helpers ── */

  const getStatusBadge = (status: string) => {
    if (status === "running")
      return (
        <span className={styles.badgeRunning}>
          <CheckCircle2 size={12} /> Running
        </span>
      );
    if (status === "exited" || status === "dead")
      return (
        <span className={styles.badgeStopped}>
          <XCircle size={12} /> Stopped
        </span>
      );
    return (
      <span className={styles.badgeOther}>
        <Clock size={12} /> {status}
      </span>
    );
  };

  const getHealthBadge = (health: string) => {
    if (health === "healthy")
      return <span className={styles.healthHealthy}><CheckCircle2 size={10} /> Healthy</span>;
    if (health === "unhealthy")
      return <span className={styles.healthUnhealthy}><XCircle size={10} /> Unhealthy</span>;
    return <span className={styles.healthNone}>–</span>;
  };

  const getBarColor = (percent: number) => {
    if (percent > 80) return "bg-red-500";
    if (percent > 60) return "bg-yellow-500";
    return "bg-emerald-500";
  };

  const isCoreContainer = (name: string) => name === "ariia_core";

  /* ── Render ── */

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingWrap}>
          <RefreshCw size={20} className={styles.spinning + " text-[var(--accent-primary)]"} />
          <span className={styles.loadingText}>Loading infrastructure data...</span>
        </div>
      </div>
    );
  }

  if (error && containers.length === 0) {
    return (
      <div className={styles.page}>
        <div className={styles.errorWrap}>
          <AlertTriangle size={48} className={styles.errorIcon} />
          <p className={styles.errorText}>{error}</p>
          <button className={styles.retryBtn} onClick={handleRefresh}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <div>
          <h1 className={styles.title}>
            <Server size={24} /> Infrastructure
          </h1>
          <p className={styles.subtitle}>
            Docker container management and system monitoring
          </p>
        </div>
        <button
          className={styles.refreshBtn}
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw size={14} className={refreshing ? styles.spinning : ""} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}>
          <div className={`${styles.summaryIcon} ${styles.summaryIconBlue}`}>
            <Box size={24} />
          </div>
          <div>
            <div className={styles.summaryNumber}>{summary.total}</div>
            <div className={styles.summaryLabel}>Total Containers</div>
          </div>
        </div>
        <div className={styles.summaryCard}>
          <div className={`${styles.summaryIcon} ${styles.summaryIconGreen}`}>
            <CheckCircle2 size={24} />
          </div>
          <div>
            <div className={styles.summaryNumber}>{summary.running}</div>
            <div className={styles.summaryLabel}>Running</div>
          </div>
        </div>
        <div className={styles.summaryCard}>
          <div className={`${styles.summaryIcon} ${styles.summaryIconRed}`}>
            <XCircle size={24} />
          </div>
          <div>
            <div className={styles.summaryNumber}>{summary.stopped}</div>
            <div className={styles.summaryLabel}>Stopped</div>
          </div>
        </div>
      </div>

      {/* System Info */}
      {systemInfo && (
        <div className={styles.infoGrid}>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>Docker</div>
            <div className={styles.infoValue}>{systemInfo.docker_version}</div>
          </div>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>OS</div>
            <div className={styles.infoValue}>{systemInfo.os.split(" ").slice(0, 2).join(" ")}</div>
          </div>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>CPUs</div>
            <div className={styles.infoValue}>{systemInfo.cpus}</div>
          </div>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>Memory</div>
            <div className={styles.infoValue}>{systemInfo.memory_total_gb} GB</div>
          </div>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>Images</div>
            <div className={styles.infoValue}>{systemInfo.images}</div>
          </div>
          <div className={styles.infoCard}>
            <div className={styles.infoLabel}>Storage</div>
            <div className={styles.infoValue}>{systemInfo.storage_driver}</div>
          </div>
        </div>
      )}

      {/* Container Table */}
      <div className={styles.tableWrap}>
        <div className={styles.tableHeader}>
          <div className={styles.tableTitle}>
            <Layers size={18} /> Containers
          </div>
          <button
            className={styles.toggleBtn}
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? "Show Running Only" : "Show All (incl. Stopped)"}
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>Container</th>
                <th className={styles.th}>Image</th>
                <th className={styles.th}>Status</th>
                <th className={styles.th}>Health</th>
                <th className={styles.th}>Uptime</th>
                <th className={styles.th}>Ports</th>
                <th className={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {containers.map((c) => (
                <>
                  <tr key={c.id} className="hover:bg-[var(--bg-tertiary)]/50 transition-colors">
                    <td className={styles.td}>
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{c.name}</span>
                        {isCoreContainer(c.name) && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] font-medium">
                            SELF
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-[var(--text-tertiary)] mt-0.5 font-mono">
                        {c.id}
                      </div>
                    </td>
                    <td className={styles.tdSecondary}>
                      <span className="font-mono text-xs">{c.image.length > 40 ? c.image.slice(0, 37) + "..." : c.image}</span>
                    </td>
                    <td className={styles.td}>{getStatusBadge(c.status)}</td>
                    <td className={styles.td}>{getHealthBadge(c.health)}</td>
                    <td className={styles.tdSecondary}>
                      <div className="flex items-center gap-1">
                        <Clock size={12} />
                        {c.uptime}
                      </div>
                    </td>
                    <td className={styles.td}>
                      <div className="flex flex-wrap gap-1">
                        {c.ports.length > 0
                          ? c.ports.map((p, i) => (
                              <span key={i} className={styles.portBadge}>
                                {p}
                              </span>
                            ))
                          : <span className="text-xs text-[var(--text-tertiary)]">–</span>}
                      </div>
                    </td>
                    <td className={styles.td}>
                      <div className="flex items-center gap-1">
                        {/* Stats toggle */}
                        {c.status === "running" && (
                          <button
                            className={styles.actionBtn}
                            onClick={() => toggleStats(c.id)}
                            title="Toggle Stats"
                          >
                            <Activity size={14} />
                          </button>
                        )}
                        {/* Logs */}
                        <button
                          className={styles.actionBtn}
                          onClick={() => fetchLogs(c)}
                          title="View Logs"
                        >
                          <Terminal size={14} />
                        </button>
                        {/* Start */}
                        {c.status !== "running" && (
                          <button
                            className={styles.actionBtn}
                            onClick={() =>
                              setConfirm({
                                title: "Start Container",
                                message: `Are you sure you want to start "${c.name}"?`,
                                action: () => handleAction(c.id, "start"),
                              })
                            }
                            disabled={actionLoading === `${c.id}-start`}
                            title="Start"
                          >
                            <Play size={14} />
                          </button>
                        )}
                        {/* Stop */}
                        {c.status === "running" && !isCoreContainer(c.name) && (
                          <button
                            className={styles.actionBtnDanger}
                            onClick={() =>
                              setConfirm({
                                title: "Stop Container",
                                message: `Are you sure you want to stop "${c.name}"? This may cause service disruption.`,
                                action: () => handleAction(c.id, "stop"),
                                danger: true,
                              })
                            }
                            disabled={actionLoading === `${c.id}-stop`}
                            title="Stop"
                          >
                            <Square size={14} />
                          </button>
                        )}
                        {/* Restart */}
                        {c.status === "running" && !isCoreContainer(c.name) && (
                          <button
                            className={styles.actionBtn}
                            onClick={() =>
                              setConfirm({
                                title: "Restart Container",
                                message: `Are you sure you want to restart "${c.name}"? There will be a brief service interruption.`,
                                action: () => handleAction(c.id, "restart"),
                              })
                            }
                            disabled={actionLoading === `${c.id}-restart`}
                            title="Restart"
                          >
                            <RotateCw size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {/* Stats Row */}
                  {expandedStats.has(c.id) && stats[c.id] && (
                    <tr key={`${c.id}-stats`}>
                      <td colSpan={7} className={styles.statsRow}>
                        <div className={styles.statsGrid}>
                          <div className={styles.statItem}>
                            <Cpu size={14} className="text-blue-400" />
                            <div>
                              <div className={styles.statLabel}>CPU</div>
                              <div className={styles.statValue}>
                                {stats[c.id].cpu_percent.toFixed(1)}%
                              </div>
                              <div className={styles.statBar}>
                                <div
                                  className={`${styles.statBarFill} ${getBarColor(stats[c.id].cpu_percent)}`}
                                  style={{ width: `${Math.min(stats[c.id].cpu_percent, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                          <div className={styles.statItem}>
                            <HardDrive size={14} className="text-purple-400" />
                            <div>
                              <div className={styles.statLabel}>Memory</div>
                              <div className={styles.statValue}>
                                {stats[c.id].memory_usage_mb.toFixed(0)} MB / {stats[c.id].memory_limit_mb.toFixed(0)} MB
                              </div>
                              <div className={styles.statBar}>
                                <div
                                  className={`${styles.statBarFill} ${getBarColor(stats[c.id].memory_percent)}`}
                                  style={{ width: `${Math.min(stats[c.id].memory_percent, 100)}%` }}
                                />
                              </div>
                            </div>
                          </div>
                          <div className={styles.statItem}>
                            <Network size={14} className="text-green-400" />
                            <div>
                              <div className={styles.statLabel}>Network I/O</div>
                              <div className={styles.statValue}>
                                ↓ {stats[c.id].network_rx_mb.toFixed(1)} MB / ↑{" "}
                                {stats[c.id].network_tx_mb.toFixed(1)} MB
                              </div>
                            </div>
                          </div>
                          <div className={styles.statItem}>
                            <Activity size={14} className="text-orange-400" />
                            <div>
                              <div className={styles.statLabel}>PIDs</div>
                              <div className={styles.statValue}>{stats[c.id].pids}</div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Log Viewer Modal */}
      {logContainer && (
        <div className={styles.logOverlay} onClick={() => setLogContainer(null)}>
          <div className={styles.logModal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.logHeader}>
              <div className={styles.logTitle}>
                <Terminal size={18} />
                Logs: {logContainer.name}
              </div>
              <div className="flex items-center gap-2">
                <button
                  className={styles.refreshBtn}
                  onClick={() => fetchLogs(logContainer)}
                  disabled={logLoading}
                >
                  <RefreshCw size={12} className={logLoading ? styles.spinning : ""} />
                  Refresh
                </button>
                <button className={styles.logClose} onClick={() => setLogContainer(null)}>
                  <X size={18} />
                </button>
              </div>
            </div>
            <div className={styles.logBody} ref={logBodyRef}>
              {logLoading ? (
                <div className="flex items-center gap-2 py-4">
                  <RefreshCw size={14} className={styles.spinning} />
                  Loading logs...
                </div>
              ) : (
                logLines.map((line, i) => (
                  <div key={i} className={styles.logLine}>
                    <span className="text-[var(--text-tertiary)] mr-3 select-none">
                      {String(i + 1).padStart(4, " ")}
                    </span>
                    {line}
                  </div>
                ))
              )}
            </div>
            <div className={styles.logFooter}>
              <span className="text-xs text-[var(--text-tertiary)]">
                {logLines.length} lines (last 500)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Dialog */}
      {confirm && (
        <div className={styles.confirmOverlay} onClick={() => setConfirm(null)}>
          <div className={styles.confirmModal} onClick={(e) => e.stopPropagation()}>
            <h3 className={styles.confirmTitle}>{confirm.title}</h3>
            <p className={styles.confirmText}>{confirm.message}</p>
            <div className={styles.confirmActions}>
              <button className={styles.confirmCancel} onClick={() => setConfirm(null)}>
                Cancel
              </button>
              <button
                className={confirm.danger ? styles.confirmDanger : styles.confirmPrimary}
                onClick={() => {
                  confirm.action();
                  setConfirm(null);
                }}
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
