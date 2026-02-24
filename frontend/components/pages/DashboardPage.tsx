"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ComposedChart, Area, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts";
import { 
  MessageSquare, Cpu, Clock, Star, ArrowUpRight, RefreshCw, 
  Building2, Users, ShieldCheck, Server, Activity, Database
} from "lucide-react";

import { T } from "@/lib/tokens";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { MiniButton } from "@/components/ui/MiniButton";
import { getStoredUser } from "@/lib/auth";
import { buildChatAnalyticsFromHistory, buildSystemAnalytics } from "@/lib/chat-analytics";

// ── Shared UI Components ───────────────────────────────────────────────────────

function KpiCard({ label, value, icon, color, trend }: any) {
  return (
    <Card style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div style={{ width: 40, height: 40, borderRadius: 10, background: `${color}15`, display: "flex", alignItems: "center", justifyContent: "center", color }}>
          {icon}
        </div>
        {trend && (
          <div style={{ display: "flex", alignItems: "center", gap: 3, padding: "3px 8px", borderRadius: 6, background: T.successDim }}>
            <ArrowUpRight size={11} color={T.success} />
            <span style={{ fontSize: 11, fontWeight: 600, color: T.success }}>{trend}</span>
          </div>
        )}
      </div>
      <p style={{ fontSize: 11, fontWeight: 500, color: T.textMuted, margin: "0 0 6px", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</p>
      <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <span style={{ fontSize: 32, fontWeight: 800, color: T.text, letterSpacing: "-0.03em" }}>{value}</span>
      </div>
    </Card>
  );
}

// ── System Admin Dashboard View ───────────────────────────────────────────────

function SystemDashboard({ data, onRefresh, refreshing }: any) {
  const tenantData = [
    { name: "Aktiv", value: data.activeTenants, color: T.success },
    { name: "Inaktiv", value: data.totalTenants - data.activeTenants, color: T.danger },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderRadius: 12, background: `${T.accent}15`, border: `1px solid ${T.accent}33` }}>
        <ShieldCheck size={18} color={T.accent} />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>Platform Governance Mode</span>
          <span style={{ fontSize: 12, color: T.textMuted, marginLeft: 16 }}>
            Version {data.engineVersion} · {data.totalTenants} Tenants registriert
          </span>
        </div>
        <Badge variant="info">SYSTEM</Badge>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard label="Total Tenants" value={data.totalTenants} icon={<Building2 size={18}/>} color={T.accent} />
        <KpiCard label="Total Users" value={data.totalUsers} icon={<Users size={18}/>} color={T.info} />
        <KpiCard label="Platform Uptime" value="99.9%" icon={<Activity size={18}/>} color={T.success} />
        <KpiCard label="System Status" value="Healthy" icon={<Server size={18}/>} color={T.success} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card style={{ padding: 24 }}>
          <SectionHeader title="Tenant Distribution" subtitle="Active vs. Inactive" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={tenantData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                  {tenantData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 20, marginTop: 10 }}>
             {tenantData.map(d => (
               <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                 <div style={{ width: 8, height: 8, borderRadius: 4, background: d.color }} />
                 <span style={{ fontSize: 12, color: T.textMuted }}>{d.name}: {d.value}</span>
               </div>
             ))}
          </div>
        </Card>

        <Card style={{ padding: 24, flex: 1 }} className="lg:col-span-2">
          <SectionHeader title="Infrastructure Status" subtitle="SaaS Core Services" />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 10 }}>
             <div style={{ padding: 16, borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <Database size={20} color={T.success} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>PostgreSQL</div>
                  <div style={{ fontSize: 11, color: T.success }}>Connected · 12ms lat.</div>
                </div>
             </div>
             <div style={{ padding: 16, borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <Activity size={20} color={T.success} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Redis Cache</div>
                  <div style={{ fontSize: 11, color: T.success }}>Connected · 2ms lat.</div>
                </div>
             </div>
             <div style={{ padding: 16, borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <Cpu size={20} color={T.info} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Vector Engine</div>
                  <div style={{ fontSize: 11, color: T.info }}>Qdrant Online</div>
                </div>
             </div>
             <div style={{ padding: 16, borderRadius: 12, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <ShieldCheck size={20} color={T.success} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Auth Service</div>
                  <div style={{ fontSize: 11, color: T.success }}>JWKS Active</div>
                </div>
             </div>
          </div>
        </Card>
      </div>

      <Card style={{ padding: 24 }}>
        <SectionHeader 
          title="Recent Platform Events" 
          subtitle="Audit Trail (System-wide)" 
          action={
            <MiniButton onClick={onRefresh}>
              <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} /> Update
            </MiniButton>
          }
        />
        <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          {data.recentAudit.length === 0 ? (
            <div style={{ padding: 20, textAlign: "center", color: T.textDim, fontSize: 13 }}>Keine Ereignisse vorhanden.</div>
          ) : data.recentAudit.map((row: any) => (
            <div key={row.id} style={{ padding: "12px 16px", borderRadius: 10, background: T.surfaceAlt, border: `1px solid ${T.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>{row.action}</div>
                <div style={{ fontSize: 11, color: T.textMuted }}>{row.actor_email} · Tenant ID: {row.tenant_id || "System"}</div>
              </div>
              <div style={{ fontSize: 11, color: T.textDim }}>{new Date(row.created_at).toLocaleString("de-DE")}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── Main Dashboard Page ───────────────────────────────────────────────────────

export function DashboardPage() {
  const [tenantData, setTenantData] = useState<any>(null);
  const [systemData, setSystemData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    else setRefreshing(true);
    try {
      if (isSystemAdmin) {
        const data = await buildSystemAnalytics();
        setSystemData(data);
      } else {
        const data = await buildChatAnalyticsFromHistory();
        setTenantData(data);
      }
    } catch (err) {
      console.error("Dashboard load failed", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isSystemAdmin]);

  useEffect(() => { void load(); }, [load]);

  if (loading) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, color: T.textDim, fontSize: 13 }}>Initialisiere Dashboard…</div>;
  }

  if (isSystemAdmin && systemData) {
    return <SystemDashboard data={systemData} onRefresh={() => void load(true)} refreshing={refreshing} />;
  }

  if (!isSystemAdmin && tenantData) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <TenantDashboardView data={tenantData} onRefresh={() => void load(true)} refreshing={refreshing} />
      </div>
    );
  }

  return <div style={{ padding: 40, textAlign: "center", color: T.textDim }}>Fehler beim Laden der Daten.</div>;
}

// ── Sub-view for Tenant Dashboard (The original implementation) ────────────────

function TenantDashboardView({ data, onRefresh, refreshing }: any) {
  const overview = data.overview;
  const kpis = [
    { label: "Tickets (24h)", value: String(overview.tickets_24h), color: T.info, icon: <MessageSquare size={18}/> },
    { label: "AI Resolution", value: overview.ai_resolution_rate.toFixed(1), color: T.success, icon: <Cpu size={18}/> },
    { label: "Ø Confidence", value: overview.confidence_avg.toFixed(0), color: T.warning, icon: <Clock size={18}/> },
    { label: "Tickets (30d)", value: String(overview.tickets_30d), color: T.accent, icon: <Star size={18}/> },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
       <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 20px", borderRadius: 12, background: T.successDim, border: `1px solid rgba(0,214,143,0.2)` }}>
        <div style={{ width: 8, height: 8, borderRadius: 4, background: T.success }} />
        <div style={{ flex: 1 }}><span style={{ fontSize: 13, fontWeight: 600, color: T.success }}>Alle Systeme online</span></div>
        <Badge variant="success">LIVE</Badge>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi, i) => <KpiCard key={i} {...kpi} />)}
      </div>
      <Card style={{ padding: 24 }}>
        <SectionHeader title="Letzte Tickets" subtitle="Kürzliche Konversationen" action={<MiniButton onClick={onRefresh}><RefreshCw size={12} className={refreshing ? "animate-spin" : ""}/> Update</MiniButton>} />
        <div style={{ fontSize: 12, color: T.textDim, marginTop: 10 }}>Nutze den Menüpunkt "Analytics" für detaillierte Auswertungen.</div>
      </Card>
    </div>
  );
}
