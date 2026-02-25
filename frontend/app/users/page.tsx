"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Shield, UserPlus, Search, Save, Pencil, Eye } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { T } from "@/lib/tokens";
import { getStoredUser, setStoredUser, type AuthUser } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { withBasePath } from "@/lib/base-path";
import { useI18n } from "@/lib/i18n/LanguageContext";

type UserRow = {
  id: number;
  email: string;
  full_name?: string | null;
  role: "system_admin" | "tenant_admin" | "tenant_user";
  tenant_id: number;
  tenant_slug?: string | null;
  tenant_name?: string | null;
  is_active: boolean;
  created_at?: string | null;
};

type TenantRow = { id: number; slug: string; name: string };
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

type EditUserState = {
  id: number;
  full_name: string;
  role: UserRow["role"];
  tenant_id: number;
  is_active: boolean;
  password: string;
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

function roleBadge(role: UserRow["role"], t: any) {
  if (role === "system_admin") return <Badge variant="danger" size="xs">{t("users.roles.systemAdmin")}</Badge>;
  if (role === "tenant_admin") return <Badge variant="accent" size="xs">{t("users.roles.tenantAdmin")}</Badge>;
  return <Badge size="xs">{t("users.roles.tenantUser")}</Badge>;
}

export default function UsersPage() {
  const { t } = useI18n();
  const [rows, setRows] = useState<UserRow[]>([]);
  const [tenants, setTenants] = useState<TenantRow[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveRowBusy, setSaveRowBusy] = useState<number | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<UserRow["role"]>("tenant_user");
  const [tenantId, setTenantId] = useState<number | "">("");

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [tenantFilter, setTenantFilter] = useState("all");
  const [editUser, setEditUser] = useState<EditUserState | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<"activate" | "deactivate" | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [auditRows, setAuditRows] = useState<AuditRow[]>([]);
  const [detailUser, setDetailUser] = useState<UserRow | null>(null);
  const [ghostTarget, setGhostTarget] = useState<UserRow | null>(null);
  const [ghostReason, setGhostReason] = useState("");
  const [ghostBusy, setGhostBusy] = useState(false);
  const [ghostError, setGhostError] = useState("");
  const user = getStoredUser();

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [uRes, tRes, aRes] = await Promise.all([
        apiFetch("/auth/users"),
        apiFetch("/auth/tenants"),
        apiFetch("/auth/audit?limit=500"),
      ]);
      if (!uRes.ok) throw new Error(`Users load failed (${uRes.status})`);
      const usersData = (await uRes.json()) as UserRow[];
      setRows(usersData);
      if (tRes.ok) {
        const t = (await tRes.json()) as TenantRow[];
        setTenants(t);
        if (user?.role === "system_admin" && t.length > 0 && tenantId === "") {
          const systemTenant = t.find((x) => x.slug === "system");
          setTenantId((systemTenant || t[0]).id);
        }
      }
      if (aRes.ok) {
        const a = (await aRes.json()) as AuditRow[];
        setAuditRows(Array.isArray(a) ? a : []);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, user?.role]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createUser() {
    if (!email || !password) {
      setError("E-Mail und Passwort sind erforderlich.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = { email, password, full_name: fullName || undefined, role };
      if (user?.role === "system_admin" && tenantId !== "") payload.tenant_id = tenantId;

      const res = await apiFetch("/auth/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Create failed (${res.status})`);
      }
      setEmail("");
      setPassword("");
      setFullName("");
      setRole("tenant_user");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  const startEdit = (r: UserRow) => {
    setEditUser({
      id: r.id,
      full_name: r.full_name || "",
      role: r.role,
      tenant_id: r.tenant_id,
      is_active: r.is_active,
      password: "",
    });
  };

  const saveEdit = async () => {
    if (!editUser) return;
    setSaveRowBusy(editUser.id);
    setError("");
    try {
      const payload: Record<string, unknown> = {
        full_name: editUser.full_name,
        role: editUser.role,
        is_active: editUser.is_active,
      };
      if (user?.role === "system_admin") payload.tenant_id = editUser.tenant_id;
      if (editUser.password.trim()) payload.password = editUser.password.trim();

      const res = await apiFetch(`/auth/users/${editUser.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Update failed (${res.status})`);
      }
      setEditUser(null);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaveRowBusy(null);
    }
  };

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (roleFilter !== "all" && r.role !== roleFilter) return false;
      const tenantSlug = (r.tenant_slug || "").toLowerCase();
      if (tenantFilter !== "all" && tenantSlug !== tenantFilter) return false;
      if (!q) return true;
      return (
        r.email.toLowerCase().includes(q) ||
        (r.full_name || "").toLowerCase().includes(q) ||
        (r.tenant_name || r.tenant_slug || String(r.tenant_id)).toLowerCase().includes(q)
      );
    });
  }, [rows, query, roleFilter, tenantFilter]);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);
  const allFilteredSelected = filteredRows.length > 0 && filteredRows.every((r) => selectedSet.has(r.id));

  const stats = useMemo(() => {
    const total = rows.length;
    const active = rows.filter((r) => r.is_active).length;
    const tenantAdmins = rows.filter((r) => r.role === "tenant_admin").length;
    const systemAdmins = rows.filter((r) => r.role === "system_admin").length;
    return { total, active, tenantAdmins, systemAdmins };
  }, [rows]);

  const tenantOptions = useMemo(
    () => Array.from(new Set(rows.map((r) => (r.tenant_slug || "").toLowerCase()).filter(Boolean))).sort(),
    [rows],
  );

  const detailAuditRows = useMemo(() => {
    if (!detailUser) return [];
    return auditRows
      .filter((r) => r.target_type === "user" && r.target_id === String(detailUser.id))
      .slice(0, 15);
  }, [auditRows, detailUser]);

  const toggleSelectRow = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAllFiltered = () => {
    if (allFilteredSelected) {
      const filteredSet = new Set(filteredRows.map((r) => r.id));
      setSelectedIds((prev) => prev.filter((id) => !filteredSet.has(id)));
      return;
    }
    setSelectedIds((prev) => Array.from(new Set([...prev, ...filteredRows.map((r) => r.id)])));
  };

  const runBulkStatus = async () => {
    if (!bulkAction) return;
    const desired = bulkAction === "activate";
    const candidates = rows.filter((r) => selectedSet.has(r.id));
    if (candidates.length === 0) {
      setBulkAction(null);
      return;
    }
    setBulkBusy(true);
    setError("");
    try {
      for (const r of candidates) {
        if (r.is_active === desired) continue;
        const res = await apiFetch(`/auth/users/${r.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: desired }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data?.detail || `Bulk update failed for user ${r.id} (${res.status})`);
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

  const startGhostMode = async () => {
    if (!ghostTarget) return;
    setGhostError("");
    const reason = ghostReason.trim();
    if (reason.length < 8) {
      setGhostError("Bitte gib einen nachvollziehbaren Grund mit mindestens 8 Zeichen an.");
      return;
    }
    setGhostBusy(true);
    setError("");
    try {
      const res = await apiFetch(`/auth/users/${ghostTarget.id}/impersonate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `Ghost Mode failed (${res.status})`);
      }
      const payload = (await res.json()) as { user?: AuthUser };
      if (payload.user) {
        setStoredUser(payload.user);
      }
      window.location.assign(withBasePath("/"));
    } catch (e) {
      setGhostError(String(e));
      setError(String(e));
    } finally {
      setGhostBusy(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("common.details")}</div><div style={{ fontSize: 26, color: T.text, fontWeight: 800 }}>{stats.total}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("common.active")}</div><div style={{ fontSize: 26, color: T.success, fontWeight: 800 }}>{stats.active}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("users.tenantAdmins")}</div><div style={{ fontSize: 26, color: T.accent, fontWeight: 800 }}>{stats.tenantAdmins}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>{t("users.systemAdmins")}</div><div style={{ fontSize: 26, color: T.warning, fontWeight: 800 }}>{stats.systemAdmins}</div></Card>
      </div>

      <Card style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <UserPlus size={15} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{t("users.createUser")}</span>
        </div>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))" }}>
          <input style={inputStyle} placeholder={t("users.email")} value={email} onChange={(e) => setEmail(e.target.value)} />
          <input style={inputStyle} placeholder={t("users.password")} value={password} onChange={(e) => setPassword(e.target.value)} />
          <input style={inputStyle} placeholder={t("users.name")} value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <select style={inputStyle} value={role} onChange={(e) => setRole(e.target.value as UserRow["role"])}>
            <option value="tenant_user">tenant_user</option>
            <option value="tenant_admin">tenant_admin</option>
            {user?.role === "system_admin" && <option value="system_admin">system_admin</option>}
          </select>
          {user?.role === "system_admin" && (
            <select style={inputStyle} value={tenantId} onChange={(e) => setTenantId(e.target.value ? Number(e.target.value) : "")}>
              {tenants.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.slug})</option>)}
            </select>
          )}
          <button onClick={createUser} disabled={saving} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer" }}>
            {saving ? t("users.saving") : t("users.createUser")}
          </button>
        </div>
        {error && <div style={{ marginTop: 8, fontSize: 12, color: T.danger }}>{error}</div>}
      </Card>

      <Card style={{ padding: 16 }}>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, border: `1px solid ${T.border}`, borderRadius: 10, padding: "10px 12px", background: T.surfaceAlt }}>
            <Search size={14} color={T.textDim} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Suche nach E-Mail, Name oder Tenant" style={{ flex: 1, border: "none", outline: "none", background: "transparent", color: T.text, fontSize: 13 }} />
          </div>
          <select style={inputStyle} value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="all">Alle Rollen</option>
            <option value="system_admin">system_admin</option>
            <option value="tenant_admin">tenant_admin</option>
            <option value="tenant_user">tenant_user</option>
          </select>
          <select style={inputStyle} value={tenantFilter} onChange={(e) => setTenantFilter(e.target.value)}>
            <option value="all">Alle Tenants</option>
            {tenantOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
          <Badge size="xs">{selectedIds.length} selektiert</Badge>
          <button
            type="button"
            onClick={() => setBulkAction("activate")}
            disabled={selectedIds.length === 0}
            style={miniActionStyle}
          >
            Bulk aktivieren
          </button>
          <button
            type="button"
            onClick={() => setBulkAction("deactivate")}
            disabled={selectedIds.length === 0}
            style={miniActionStyle}
          >
            Bulk deaktivieren
          </button>
        </div>
      </Card>

      <Card style={{ padding: 0, overflow: "auto" }}>
        <table className="hidden md:table" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: T.surfaceAlt }}>
              <th style={{ textAlign: "left", fontSize: 10, color: T.textDim, padding: "10px 12px", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                <input type="checkbox" checked={allFilteredSelected} onChange={toggleSelectAllFiltered} />
              </th>
              {["Benutzer", "Rolle", "Tenant", "Status", "Erstellt", "Aktionen"].map((h) => (
                <th key={h} style={{ textAlign: "left", fontSize: 10, color: T.textDim, padding: "10px 12px", textTransform: "uppercase", letterSpacing: "0.08em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ padding: 20, color: T.textDim, fontSize: 13 }}>Lade Benutzer...</td></tr>
            ) : filteredRows.map((r) => (
              <tr key={r.id} style={{ borderTop: `1px solid ${T.border}` }}>
                <td style={{ padding: "10px 12px" }}>
                  <input
                    type="checkbox"
                    checked={selectedSet.has(r.id)}
                    onChange={() => toggleSelectRow(r.id)}
                    aria-label={`User ${r.email} auswählen`}
                  />
                </td>
                <td style={{ padding: "10px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Shield size={13} color={T.textDim} />
                    <div>
                      <div style={{ fontSize: 13, color: T.text }}>{r.email}</div>
                      <div style={{ fontSize: 11, color: T.textDim }}>{r.full_name || "-"}</div>
                    </div>
                  </div>
                </td>
                <td style={{ padding: "10px 12px" }}>{roleBadge(r.role, t)}</td>
                <td style={{ padding: "10px 12px", fontSize: 12, color: T.text }}>{r.tenant_name || r.tenant_slug || r.tenant_id}</td>
                <td style={{ padding: "10px 12px" }}>{r.is_active ? <Badge variant="success" size="xs">active</Badge> : <Badge variant="warning" size="xs">inactive</Badge>}</td>
                <td style={{ padding: "10px 12px", fontSize: 12, color: T.textDim }}>{r.created_at ? new Date(r.created_at).toLocaleString("de-DE") : "-"}</td>
                <td style={{ padding: "10px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <button onClick={() => setDetailUser(r)} style={{ borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 12, padding: "7px 10px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Eye size={12} /> Details
                    </button>
                    <button onClick={() => startEdit(r)} style={{ borderRadius: 8, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontSize: 12, padding: "7px 10px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
                      <Pencil size={12} /> Bearbeiten
                    </button>
                    {user?.role === "system_admin" && r.role !== "system_admin" && r.id !== user.id && (
                      <button
                        onClick={() => {
                          setGhostTarget(r);
                          setGhostReason("");
                          setGhostError("");
                        }}
                        style={{ borderRadius: 8, border: `1px solid ${T.accentLight}`, background: T.accentDim, color: T.accentLight, fontSize: 12, padding: "7px 10px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}
                      >
                        Ghost Mode
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!loading && filteredRows.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 20, color: T.textDim, fontSize: 13 }}>Keine Benutzer für den aktuellen Filter.</td></tr>
            )}
          </tbody>
        </table>

        {/* Mobile View */}
        <div className="md:hidden flex flex-col gap-3 p-4">
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <input type="checkbox" checked={allFilteredSelected} onChange={toggleSelectAllFiltered} />
            <span style={{ fontSize: 12, color: T.textDim }}>Alle auswählen</span>
          </div>

          {loading ? (
            <div style={{ color: T.textDim, fontSize: 13, textAlign: "center", padding: 20 }}>Lade Benutzer...</div>
          ) : filteredRows.length === 0 ? (
            <div style={{ color: T.textDim, fontSize: 13, textAlign: "center", padding: 20 }}>Keine Benutzer für den aktuellen Filter.</div>
          ) : filteredRows.map((r) => (
            <div key={r.id} style={{ display: "flex", flexDirection: "column", gap: 10, padding: 14, borderRadius: 12, border: `1px solid ${T.border}`, background: T.surfaceAlt }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={selectedSet.has(r.id)}
                    onChange={() => toggleSelectRow(r.id)}
                    aria-label={`User ${r.email} auswählen`}
                  />
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: T.text }}>{r.email}</div>
                    <div style={{ fontSize: 12, color: T.textDim }}>{r.full_name || "-"}</div>
                  </div>
                </div>
                <div>{r.is_active ? <Badge variant="success" size="xs">active</Badge> : <Badge variant="warning" size="xs">inactive</Badge>}</div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <div>
                  <div style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>Rolle</div>
                  <div style={{ marginTop: 4 }}>{roleBadge(r.role, t)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase" }}>Tenant</div>
                  <div style={{ fontSize: 12, color: T.text, marginTop: 4 }}>{r.tenant_name || r.tenant_slug || r.tenant_id}</div>
                </div>
              </div>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                <button onClick={() => setDetailUser(r)} style={miniActionStyle}><Eye size={12} /> Details</button>
                <button onClick={() => startEdit(r)} style={miniActionStyle}><Pencil size={12} /> Bearbeiten</button>
                {user?.role === "system_admin" && r.role !== "system_admin" && r.id !== user.id && (
                  <button onClick={() => { setGhostTarget(r); setGhostReason(""); setGhostError(""); }} style={{ ...miniActionStyle, border: `1px solid ${T.accentLight}`, background: T.accentDim, color: T.accentLight }}>
                    Ghost Mode
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Modal
        open={!!bulkAction}
        onClose={() => !bulkBusy && setBulkAction(null)}
        title={bulkAction === "activate" ? "Benutzer aktivieren" : "Benutzer deaktivieren"}
        subtitle={`${selectedIds.length} Benutzer selektiert`}
      >
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ fontSize: 13, color: T.text }}>
            Diese Aktion wird auf alle selektierten Benutzer angewendet und im Audit-Log protokolliert.
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setBulkAction(null)} disabled={bulkBusy} style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "10px 12px", cursor: "pointer" }}>
              Abbrechen
            </button>
            <button onClick={runBulkStatus} disabled={bulkBusy} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer" }}>
              {bulkBusy ? "Läuft..." : "Ausführen"}
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!detailUser}
        onClose={() => setDetailUser(null)}
        title={detailUser ? detailUser.email : "Benutzer Detail"}
        subtitle={detailUser ? `ID ${detailUser.id} · ${detailUser.role}` : ""}
        width="min(900px, 100%)"
      >
        {detailUser && (
          <div style={{ display: "grid", gap: 14 }}>
            <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Tenant</div><div style={{ fontSize: 13, color: T.text }}>{detailUser.tenant_name || detailUser.tenant_slug || detailUser.tenant_id}</div></Card>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Status</div><div style={{ fontSize: 13, color: detailUser.is_active ? T.success : T.warning }}>{detailUser.is_active ? "active" : "inactive"}</div></Card>
              <Card style={{ padding: 12 }}><div style={{ fontSize: 11, color: T.textDim }}>Erstellt</div><div style={{ fontSize: 13, color: T.text }}>{detailUser.created_at ? new Date(detailUser.created_at).toLocaleString("de-DE") : "-"}</div></Card>
            </div>
            <div style={{ border: `1px solid ${T.border}`, borderRadius: 12, overflow: "hidden" }}>
              <div style={{ padding: "10px 12px", background: T.surfaceAlt, fontSize: 11, color: T.textDim, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                Letzte Audit-Events
              </div>
              <div style={{ maxHeight: 280, overflow: "auto" }}>
                {detailAuditRows.length === 0 ? (
                  <div style={{ padding: 12, fontSize: 12, color: T.textDim }}>Keine Audit-Events gefunden.</div>
                ) : detailAuditRows.map((row) => (
                  <div key={row.id} style={{ borderTop: `1px solid ${T.border}`, padding: "10px 12px" }}>
                    <div style={{ fontSize: 12, color: T.text }}>{row.action}</div>
                    <div style={{ marginTop: 2, fontSize: 11, color: T.textDim }}>
                      {row.created_at ? new Date(row.created_at).toLocaleString("de-DE") : "-"} · {row.actor_email || "system"}
                    </div>
                    {row.details_json && (
                      <pre style={{ marginTop: 8, marginBottom: 0, whiteSpace: "pre-wrap", fontSize: 11, color: T.textMuted }}>
                        {row.details_json}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!ghostTarget}
        onClose={() => !ghostBusy && setGhostTarget(null)}
        title="Ghost Mode starten"
        subtitle={ghostTarget ? `Du übernimmst temporär ${ghostTarget.email}` : ""}
      >
        {ghostTarget && (
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ fontSize: 13, color: T.text }}>
              Du erhältst exakt den Rechteumfang dieses Nutzers. Alle Aktionen bleiben auditierbar und der Modus ist zeitlich begrenzt.
            </div>
            <div>
              <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Grund (Pflicht)</div>
              <input
                style={inputStyle}
                value={ghostReason}
                onChange={(e) => setGhostReason(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    void startGhostMode();
                  }
                }}
                placeholder="z. B. Supportfall #4812: Nutzer kann Einstellungen nicht speichern"
              />
              {ghostError && (
                <div style={{ marginTop: 6, fontSize: 12, color: T.danger }}>
                  {ghostError}
                </div>
              )}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button
                onClick={() => setGhostTarget(null)}
                disabled={ghostBusy}
                style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, padding: "10px 12px", cursor: "pointer" }}
              >
                Abbrechen
              </button>
              <button
                onClick={() => void startGhostMode()}
                disabled={ghostBusy}
                style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer" }}
              >
                {ghostBusy ? "Starte..." : "Ghost Mode starten"}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={!!editUser}
        onClose={() => setEditUser(null)}
        title="Benutzer bearbeiten"
        subtitle={editUser ? `ID ${editUser.id} · Governance & Access Control` : ""}
      >
        {editUser && (
          <>
            <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))" }}>
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Name</div>
                <input style={inputStyle} placeholder="Name" value={editUser.full_name} onChange={(e) => setEditUser({ ...editUser, full_name: e.target.value })} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Rolle</div>
                <select style={inputStyle} value={editUser.role} onChange={(e) => setEditUser({ ...editUser, role: e.target.value as UserRow["role"] })}>
                  <option value="tenant_user">tenant_user</option>
                  <option value="tenant_admin">tenant_admin</option>
                  {user?.role === "system_admin" && <option value="system_admin">system_admin</option>}
                </select>
              </div>
              {user?.role === "system_admin" && (
                <div>
                  <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Tenant</div>
                  <select style={inputStyle} value={editUser.tenant_id} onChange={(e) => setEditUser({ ...editUser, tenant_id: Number(e.target.value) })}>
                    {tenants.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.slug})</option>)}
                  </select>
                </div>
              )}
              <div>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Status</div>
                <select style={inputStyle} value={editUser.is_active ? "true" : "false"} onChange={(e) => setEditUser({ ...editUser, is_active: e.target.value === "true" })}>
                  <option value="true">active</option>
                  <option value="false">inactive</option>
                </select>
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <div style={{ fontSize: 11, color: T.textDim, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Passwort Reset (optional)</div>
                <input style={inputStyle} placeholder="Neues Passwort (optional)" value={editUser.password} onChange={(e) => setEditUser({ ...editUser, password: e.target.value })} />
              </div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
              <button onClick={() => setEditUser(null)} style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surface, color: T.text, fontWeight: 600, padding: "10px 12px", cursor: "pointer" }}>
                Abbrechen
              </button>
              <button onClick={saveEdit} disabled={saveRowBusy === editUser.id} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 12px", cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                <Save size={12} /> {saveRowBusy === editUser.id ? "Speichern..." : "Änderungen speichern"}
              </button>
            </div>
          </>
        )}
      </Modal>
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
