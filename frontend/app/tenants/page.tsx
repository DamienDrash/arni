"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, Globe2, Plus, Pencil, Save, Eye, X } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/LanguageContext";

type TenantRow = { id: number; slug: string; name: string; is_active?: boolean };
type UserRow = { id: number; tenant_id: number; role: string; is_active: boolean };
type AuditRow = {
  id: number;
  created_at: string | null;
  action: string;
  category: string;
  target_type: string | null;
  target_id: string | null;
  details_json: string | null;
  actor_email: string | null;
};

type EditTenantState = {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 13,
  padding: "10px 12px",
  outline: "none",
};

export default function TenantsPage() {
  const { t } = useI18n();
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveTenantBusy, setSaveTenantBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [editTenant, setEditTenant] = useState<EditTenantState | null>(null);
  const [detailTenant, setDetailTenant] = useState<TenantRow | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<"activate" | "deactivate" | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [auditRows, setAuditRows] = useState<AuditRow[]>([]);
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [tRes, uRes, aRes] = await Promise.all([
        apiFetch("/auth/tenants"),
        apiFetch("/auth/users"),
        apiFetch("/auth/audit?limit=500"),
      ]);
      if (!tRes.ok) throw new Error(`Tenant load failed (${tRes.status})`);
      const t = (await tRes.json()) as TenantRow[];
      setTenants(t);
      if (uRes.ok) setUsers((await uRes.json()) as UserRow[]);
      if (aRes.ok) {
        const a = (await aRes.json()) as AuditRow[];
        setAuditRows(Array.isArray(a) ? a : []);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function createTenant() {
    if (!isSystemAdmin) return;
    if (!name.trim()) {
      setError(t("tenants.errors.nameRequired") || "Name required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await apiFetch("/auth/tenants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), slug: slug.trim() || undefined }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Create failed (${res.status})`);
      }
      setName("");
      setSlug("");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const startEdit = (t: TenantRow) => {
    setEditTenant({ id: t.id, name: t.name, slug: t.slug, is_active: t.is_active ?? true });
  };

  const saveEdit = async () => {
    if (!editTenant || !isSystemAdmin) return;
    setSaveTenantBusy(editTenant.id);
    setError("");
    try {
      const res = await apiFetch(`/auth/tenants/${editTenant.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editTenant.name, slug: editTenant.slug, is_active: editTenant.is_active }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Update failed (${res.status})`);
      }
      setEditTenant(null);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaveTenantBusy(null);
    }
  };

  const stats = useMemo(() => {
    const totalTenants = tenants.length;
    const totalUsers = users.length;
    const avgUsersPerTenant = totalTenants > 0 ? (totalUsers / totalTenants).toFixed(1) : "0.0";
    return { totalTenants, totalUsers, avgUsersPerTenant };
  }, [tenants, users]);

  const byTenant = useMemo(() => {
    const map = new Map<number, { users: number; admins: number; active: number }>();
    for (const u of users) {
      const curr = map.get(u.tenant_id) || { users: 0, admins: 0, active: 0 };
      curr.users += 1;
      if (u.role === "tenant_admin" || u.role === "system_admin") curr.admins += 1;
      if (u.is_active) curr.active += 1;
      map.set(u.tenant_id, curr);
    }
    return map;
  }, [users]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allSelected = tenants.length > 0 && tenants.every((t) => selectedSet.has(t.id));

  const detailAuditRows = useMemo(() => {
    if (!detailTenant) return [];
    return auditRows
      .filter((r) => r.target_type === "tenant" && r.target_id === String(detailTenant.id))
      .slice(0, 15);
  }, [auditRows, detailTenant]);

  const detailUsers = useMemo(() => {
    if (!detailTenant) return [];
    return users.filter((u) => u.tenant_id === detailTenant.id);
  }, [detailTenant, users]);

  const toggleSelectTenant = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(tenants.map((t) => t.id));
  };

  const runBulkStatus = async () => {
    if (!bulkAction || !isSystemAdmin) return;
    const desired = bulkAction === "activate";
    const targets = tenants.filter((t) => selectedSet.has(t.id));
    if (targets.length === 0) {
      setBulkAction(null);
      return;
    }
    setBulkBusy(true);
    setError("");
    try {
      for (const t of targets) {
        if ((t.is_active ?? true) === desired) continue;
        const res = await apiFetch(`/auth/tenants/${t.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: desired }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data?.detail || `Bulk update failed for tenant ${t.id} (${res.status})`);
        }
      }
      setSelectedIds([]);
      setBulkAction(null);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("tenants.stats.total")}</div><div style={{ fontSize: 26, color: T.text, fontWeight: 800 }}>{stats.totalTenants}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("tenants.stats.users")}</div><div style={{ fontSize: 26, color: T.accent, fontWeight: 800 }}>{stats.totalUsers}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("tenants.stats.avg")}</div><div style={{ fontSize: 26, color: T.success, fontWeight: 800 }}>{stats.avgUsersPerTenant}</div></Card>
      </div>

      {isSystemAdmin && (
        <Card style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Plus size={14} color={T.accent} />
            <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{t("tenants.create.title")}</span>
          </div>
          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))" }}>
            <input style={inputStyle} placeholder={t("tenants.create.name")} value={name} onChange={(e) => setName(e.target.value)} />
            <input style={inputStyle} placeholder={t("tenants.create.slug")} value={slug} onChange={(e) => setSlug(e.target.value)} />
            <button onClick={createTenant} disabled={saving} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 14px", cursor: "pointer" }}>
              {saving ? t("common.loading") : t("tenants.create.title")}
            </button>
          </div>
          {error && <div style={{ marginTop: 8, fontSize: 12, color: T.danger }}>{error}</div>}
        </Card>
      )}

      <Card style={{ padding: 0, overflow: "auto" }}>
        {isSystemAdmin && (
          <div style={{ padding: "12px 12px 0", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <Badge size="xs">{selectedIds.length} {t("members.stats.selected")}</Badge>
            <button type="button" onClick={() => setBulkAction("activate")} disabled={selectedIds.length === 0} style={miniActionStyle}>{t("common.active")} (Bulk)</button>
            <button type="button" onClick={() => setBulkAction("deactivate")} disabled={selectedIds.length === 0} style={miniActionStyle}>{t("common.paused")} (Bulk)</button>
          </div>
        )}
        <table className="hidden md:table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: T.surfaceAlt }}>
              {isSystemAdmin && (
                <th style={{ textAlign: "left", fontSize: 10, color: T.textDim, padding: "10px 12px", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
                </th>
              )}
              {[t("tenants.table.name"), "Slug", t("tenants.table.users"), t("tenants.table.admins"), t("sidebar.monitor"), t("common.status"), t("ai.actions")].map((h) => (
                <th key={h} style={{ textAlign: "left", fontSize: 10, color: T.textDim, padding: "10px 12px", textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={isSystemAdmin ? 8 : 7} style={{ padding: 20, color: T.textDim, fontSize: 13 }}>{t("common.loading")}</td></tr>
            ) : tenants.map((tRow) => {
              const counts = byTenant.get(tRow.id) || { users: 0, admins: 0, active: 0 };
              return (
                <tr key={tRow.id} style={{ borderTop: `1px solid ${T.border}` }}>
                  {isSystemAdmin && (
                    <td style={{ padding: "10px 12px" }}>
                      <input
                        type="checkbox"
                        checked={selectedSet.has(tRow.id)}
                        onChange={() => toggleSelectTenant(tRow.id)}
                      />
                    </td>
                  )}
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Building2 size={14} color={T.textDim} />
                      <span style={{ fontSize: 13, color: T.text }}>{tRow.name}</span>
                    </div>
                  </td>
                  <td style={{ padding: "10px 12px" }}><span style={{ fontSize: 12, color: T.textDim }}>{tRow.slug}</span></td>
                  <td style={{ padding: "10px 12px", fontSize: 13, color: T.text }}>{counts.users}</td>
                  <td style={{ padding: "10px 12px", fontSize: 13, color: T.text }}>{counts.admins}</td>
                  <td style={{ padding: "10px 12px", fontSize: 13, color: T.text }}>{counts.active}</td>
                  <td style={{ padding: "10px 12px" }}><Badge variant={(tRow.is_active ?? true) ? "success" : "warning"} size="xs">{(tRow.is_active ?? true) ? t("common.active") : t("common.paused")}</Badge></td>
                  <td style={{ padding: "10px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <button onClick={() => setDetailTenant(tRow)} style={miniActionStyle}>
                        <Eye size={12} /> {t("common.details")}
                      </button>
                      {isSystemAdmin && (
                        <button onClick={() => startEdit(tRow)} style={miniActionStyle}>
                          <Pencil size={12} /> {t("common.edit")}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
            {!loading && tenants.length === 0 && (
              <tr><td colSpan={isSystemAdmin ? 8 : 7} style={{ padding: 20, color: T.textDim, fontSize: 13 }}>{t("common.noEntries")}</td></tr>
            )}
          </tbody>
        </table>

        {/* Mobile View */}
        <div className="md:hidden flex flex-col gap-3 p-4">
          {isSystemAdmin && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} />
              <span style={{ fontSize: 12, color: T.textDim }}>{t("common.details")} (Bulk)</span>
            </div>
          )}

          {loading ? (
            <div style={{ color: T.textDim, fontSize: 13, textAlign: "center", padding: 20 }}>{t("common.loading")}</div>
          ) : tenants.length === 0 ? (
            <div style={{ color: T.textDim, fontSize: 13, textAlign: "center", padding: 20 }}>{t("common.noEntries")}</div>
          ) : tenants.map((tRow) => {
            const counts = byTenant.get(tRow.id) || { users: 0, admins: 0, active: 0 };
            return (
              <div key={tRow.id} style={{ display: "flex", flexDirection: "column", gap: 10, padding: 14, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    {isSystemAdmin && (
                      <input
                        type="checkbox"
                        checked={selectedSet.has(tRow.id)}
                        onChange={() => toggleSelectTenant(tRow.id)}
                      />
                    )}
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: T.text, display: "flex", alignItems: "center", gap: 6 }}>
                        <Building2 size={14} color={T.textDim} /> {tRow.name}
                      </div>
                      <div style={{ fontSize: 12, color: T.textDim }}>{tRow.slug}</div>
                    </div>
                  </div>
                  <div><Badge variant={(tRow.is_active ?? true) ? "success" : "warning"} size="xs">{(tRow.is_active ?? true) ? t("common.active") : t("common.paused")}</Badge></div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 4 }}>
                  <div>
                    <div style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>{t("tenants.table.users")}</div>
                    <div style={{ fontSize: 12, color: T.text, marginTop: 2 }}>{counts.users}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>{t("tenants.table.admins")}</div>
                    <div style={{ fontSize: 12, color: T.text, marginTop: 2 }}>{counts.admins}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>{t("tenants.table.active")}</div>
                    <div style={{ fontSize: 12, color: T.text, marginTop: 2 }}>{counts.active}</div>
                  </div>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                  <button onClick={() => setDetailTenant(tRow)} style={miniActionStyle}><Eye size={12} /> {t("common.details")}</button>
                  {isSystemAdmin && (
                    <button onClick={() => startEdit(tRow)} style={miniActionStyle}><Pencil size={12} /> {t("common.edit")}</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Modal
        open={!!bulkAction}
        onClose={() => !bulkBusy && setBulkAction(null)}
        title={bulkAction === "activate" ? t("common.active") : t("common.paused")}
        subtitle={`${selectedIds.length} ${t("tenants.stats.total")}`}
      >
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ fontSize: 13, color: T.text }}>
            {t("tenants.bulk.hint")}
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setBulkAction(null)} disabled={bulkBusy} style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "10px 12px", cursor: "pointer" }}>
              {t("common.cancel")}
            </button>
            <button onClick={runBulkStatus} disabled={bulkBusy} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer" }}>
              {bulkBusy ? t("common.loading") : t("common.confirmed")}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!detailTenant}
        onClose={() => setDetailTenant(null)}
        title={detailTenant ? detailTenant.name : t("common.details")}
        subtitle={detailTenant ? `ID ${detailTenant.id} · ${detailTenant.slug}` : ""}
        width="min(900px, 100%)"
      >
        {detailTenant && (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("common.status")}</div><div style={{ fontSize: 13, color: (detailTenant.is_active ?? true) ? T.success : T.warning }}>{(detailTenant.is_active ?? true) ? t("common.active") : t("common.paused")}</div></Card>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("tenants.table.users")}</div><div style={{ fontSize: 13, color: T.text }}>{detailUsers.length}</div></Card>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("tenants.table.active")}</div><div style={{ fontSize: 13, color: T.text }}>{detailUsers.filter((u) => u.is_active).length}</div></Card>
            </div>
            <div style={{ border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "10px 12px", background: T.surfaceAlt, fontSize: 11, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                {t("tenants.audit.title")}
              </div>
              <div style={{ maxHeight: 280, overflow: "auto" }}>
                {detailAuditRows.length === 0 ? (
                  <div style={{ padding: 12, fontSize: 12, color: T.textDim }}>{t("common.noEntries")}</div>
                ) : detailAuditRows.map((row) => (
                  <div key={row.id} style={{ borderTop: `1px solid ${T.border}`, padding: "10px 12px" }}>
                    <div style={{ fontSize: 12, color: T.text }}>{row.action}</div>
                    <div style={{ marginTop: 2, fontSize: 11, color: T.textDim }}>
                      {row.created_at ? new Date(row.created_at).toLocaleString() : "-"} · {row.actor_email || "system"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!editTenant && isSystemAdmin}
        onClose={() => setEditTenant(null)}
        title={t("tenants.edit.title")}
        subtitle={editTenant ? `ID ${editTenant.id} · Multi-Tenant Governance` : ""}
        width="min(820px, 100%)"
      >
        {editTenant && isSystemAdmin && (
          <>
            <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>{t("tenants.create.name")}</div>
                <input style={inputStyle} placeholder={t("tenants.create.name")} value={editTenant.name} onChange={(e) => setEditTenant({ ...editTenant, name: e.target.value })} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Slug</div>
                <input style={inputStyle} placeholder="Slug" value={editTenant.slug} onChange={(e) => setEditTenant({ ...editTenant, slug: e.target.value })} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>{t("common.status")}</div>
                <select style={inputStyle} value={editTenant.is_active ? "true" : "false"} onChange={(e) => setEditTenant({ ...editTenant, is_active: e.target.value === "true" })}>
                  <option value="true">{t("common.active")}</option>
                  <option value="false">{t("common.paused")}</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
              <button onClick={() => setEditTenant(null)} style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontWeight: 600, padding: "10px 12px", cursor: "pointer" }}>
                {t("common.cancel")}
              </button>
              <button onClick={saveEdit} disabled={saveTenantBusy === editTenant.id} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Save size={12} /> {saveTenantBusy === editTenant.id ? t("common.loading") : t("common.save")}
              </button>
            </div>
            {error && <div style={{ paddingTop: 10, fontSize: 12, color: T.danger }}>{error}</div>}
          </>
        )}
      </Modal>

      <Card style={{ padding: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Globe2 size={14} color={T.textDim} />
          <span style={{ fontSize: 12, color: T.textDim }}>{t("tenants.footer.registration")}</span>
        </div>
      </Card>
    </div>
  );
}

const miniActionStyle: React.CSSProperties = {
  borderRadius: 8,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 12,
  padding: "7px 10px",
  cursor: "pointer",
};
