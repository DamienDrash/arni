/**
 * ARIIA v2.0 – Contact Sync React Query Hooks.
 *
 * @ARCH: Contacts-Sync Refactoring, Phase 2
 * Provides typed hooks for all contact-sync API endpoints.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

export interface ConfigField {
  key: string;
  label: string;
  type: "text" | "password" | "number" | "select" | "toggle" | "url";
  placeholder?: string;
  help_text?: string;
  required?: boolean;
  options?: { label: string; value: string }[];
  default_value?: string | number | boolean;
  group?: string;
  validation_regex?: string;
}

export interface ConfigSchema {
  fields: ConfigField[];
  groups?: { key: string; label: string; description?: string }[];
  documentation_url?: string;
}

export interface AvailableIntegration {
  integration_id: string;
  display_name: string;
  category: string;
  supported_sync_directions: string[];
  supports_incremental_sync: boolean;
  supports_webhooks: boolean;
  config_schema: ConfigSchema;
}

export interface TenantIntegration {
  id: number;
  integration_id: string;
  display_name: string;
  category: string;
  status: string;
  enabled: boolean;
  sync_direction: string;
  sync_interval_minutes: number;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
  last_sync_log: SyncLogEntry | null;
  created_at: string | null;
}

export interface SyncLogEntry {
  id?: number;
  integration_id: string;
  sync_mode: string;
  status: string;
  triggered_by: string;
  records_fetched: number;
  records_created: number;
  records_updated: number;
  records_failed: number;
  duration_ms: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface ConnectionTestResult {
  success: boolean;
  message: string;
  details?: Record<string, unknown>;
  latency_ms?: number;
}

export interface SyncRunResult {
  success: boolean;
  error?: string;
  integration_id: string;
  records_fetched?: number;
  records_created?: number;
  records_updated?: number;
  records_unchanged?: number;
  records_deleted?: number;
  records_failed?: number;
  duration_ms?: number;
  sync_mode?: string;
  triggered_by?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const errBody = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${errBody || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function putJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${errBody || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

async function deleteJSON<T>(path: string): Promise<T> {
  const res = await apiFetch(path, { method: "DELETE" });
  if (!res.ok) {
    const errBody = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${errBody || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── Query Keys ───────────────────────────────────────────────────────────────

export const SYNC_KEYS = {
  available: ["sync", "available"] as const,
  configured: ["sync", "configured"] as const,
  integration: (id: string) => ["sync", "integration", id] as const,
  history: ["sync", "history"] as const,
  integrationHistory: (id: string) => ["sync", "history", id] as const,
};

// ── Queries ──────────────────────────────────────────────────────────────────

/** List all available integrations (marketplace). */
export function useAvailableIntegrations() {
  return useQuery({
    queryKey: SYNC_KEYS.available,
    queryFn: () => fetchJSON<AvailableIntegration[]>("/sync/integrations/available"),
    staleTime: 300_000, // 5min – rarely changes
  });
}

/** List tenant's configured integrations. */
export function useConfiguredIntegrations() {
  return useQuery({
    queryKey: SYNC_KEYS.configured,
    queryFn: () => fetchJSON<TenantIntegration[]>("/sync/integrations"),
    staleTime: 30_000, // 30s – may change after sync
    refetchInterval: 60_000, // auto-refresh every 60s
  });
}

/** Get sync history for all integrations. */
export function useSyncHistory(limit = 20) {
  return useQuery({
    queryKey: [...SYNC_KEYS.history, limit],
    queryFn: () => fetchJSON<SyncLogEntry[]>(`/sync/history?limit=${limit}`),
    staleTime: 15_000,
  });
}

/** Get sync history for a specific integration. */
export function useIntegrationSyncHistory(integrationId: string, limit = 20) {
  return useQuery({
    queryKey: [...SYNC_KEYS.integrationHistory(integrationId), limit],
    queryFn: () => fetchJSON<SyncLogEntry[]>(`/sync/history/${integrationId}?limit=${limit}`),
    staleTime: 15_000,
    enabled: !!integrationId,
  });
}

// ── Mutations ────────────────────────────────────────────────────────────────

/** Test connection to an integration. */
export function useTestConnection() {
  return useMutation({
    mutationFn: ({ integrationId, config }: { integrationId: string; config: Record<string, unknown> }) =>
      postJSON<ConnectionTestResult>(`/sync/integrations/${integrationId}/test`, { config }),
  });
}

/** Save/update integration configuration. */
export function useSaveIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      integrationId,
      config,
      sync_direction = "inbound",
      sync_interval_minutes = 60,
      enabled = true,
    }: {
      integrationId: string;
      config: Record<string, unknown>;
      sync_direction?: string;
      sync_interval_minutes?: number;
      enabled?: boolean;
    }) =>
      postJSON<{ id: number; integration_id: string; status: string; enabled: boolean; message: string }>(
        `/sync/integrations/${integrationId}/save`,
        { config, sync_direction, sync_interval_minutes, enabled }
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SYNC_KEYS.configured });
    },
  });
}

/** Toggle integration enabled/disabled. */
export function useToggleIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ integrationId, enabled }: { integrationId: string; enabled: boolean }) =>
      putJSON<{ success: boolean; enabled: boolean; message: string }>(
        `/sync/integrations/${integrationId}/toggle`,
        { enabled }
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SYNC_KEYS.configured });
    },
  });
}

/** Delete an integration. */
export function useDeleteIntegration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (integrationId: string) =>
      deleteJSON<{ success: boolean; message: string }>(`/sync/integrations/${integrationId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SYNC_KEYS.configured });
    },
  });
}

/** Get sync health status. */
export function useSyncHealth() {
  return useQuery({
    queryKey: ["sync", "health"],
    queryFn: () => fetchJSON<{
      overall_status: string;
      checked_at: string;
      summary: { total: number; healthy: number; warning: number; critical: number; disabled: number; unknown: number };
      aggregated_metrics: { total_records_synced_24h: number; total_errors_24h: number; avg_sync_duration_ms: number };
      integrations: Array<{
        tenant_id: number;
        integration_id: string;
        display_name: string;
        status: string;
        enabled: boolean;
        issues: string[];
        metrics: Record<string, unknown>;
        last_check_at: string | null;
      }>;
    }>("/sync/health"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

/** Get sync statistics for dashboard. */
export function useSyncStats() {
  return useQuery({
    queryKey: ["sync", "stats"],
    queryFn: () => fetchJSON<{
      period_24h: { total_syncs: number; successful_syncs: number; failed_syncs: number; records_synced: number; success_rate: number | null };
      period_7d: { total_syncs: number; records_synced: number };
      period_30d: { total_syncs: number; records_synced: number };
      integrations: Array<{ integration_id: string; display_name: string; status: string; enabled: boolean; syncs_24h: number; records_24h: number; errors_24h: number; last_sync_at: string | null }>;
      trend_7d: Array<{ date: string; syncs: number; records: number; errors: number }>;
    }>("/sync/stats"),
    staleTime: 30_000,
  });
}

/** Get scheduler status. */
export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["sync", "scheduler"],
    queryFn: () => fetchJSON<{
      is_running: boolean;
      active_syncs: number;
      started_at: string | null;
      last_check_at: string | null;
      total_checks: number;
      total_syncs_triggered: number;
      total_syncs_failed: number;
    }>("/sync/scheduler/status"),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/** Trigger manual sync. */
export function useRunSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ integrationId, syncMode }: { integrationId: string; syncMode?: string }) =>
      postJSON<SyncRunResult>(`/sync/integrations/${integrationId}/run`, {
        sync_mode: syncMode || null,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: SYNC_KEYS.configured });
      void qc.invalidateQueries({ queryKey: SYNC_KEYS.history });
    },
  });
}
