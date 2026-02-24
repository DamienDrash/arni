"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Mail, Server, Shield, Trash2, Lock, History, Save, Send, RefreshCw } from "lucide-react";

import SettingsSubnav from "@/components/settings/SettingsSubnav";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { ToggleSwitch } from "@/components/ui/ToggleSwitch";
import { apiFetch } from "@/lib/api";
import { T } from "@/lib/tokens";
import { getStoredUser } from "@/lib/auth";

type Setting = { key: string; value: string; description?: string };

const labelStyle: React.CSSProperties = {
  fontSize: 11,
  color: "#5A5C6B",
  textTransform: "uppercase",
  fontWeight: 700,
  marginBottom: 4,
  display: "block"
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  borderRadius: 8,
  border: `1px solid #CBD5E1`,
  background: "#FFFFFF",
  color: "#0F172A",
  fontSize: 14,
  padding: "10px 12px",
  outline: "none",
  boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
};

export default function SettingsGeneralPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const user = getStoredUser();
  const isSystemAdmin = user?.role === "system_admin";

  const [smtpForm, setSmtpForm] = useState({
    host: "",
    port: "",
    user: "",
    pass: "",
    fromName: "",
    fromAddr: ""
  });

  async function fetchData() {
    try {
      const res = await apiFetch("/admin/settings");
      if (res.ok) {
        const data = await res.json() as Setting[];
        setSettings(data);
        
        const find = (k: string) => data.find(s => s.key === k)?.value || "";
        setSmtpForm({
          host: find("platform_email_smtp_host"),
          port: find("platform_email_smtp_port"),
          user: find("platform_email_smtp_user"),
          pass: find("platform_email_smtp_pass") ? "__REDACTED__" : "",
          fromName: find("platform_email_from_name"),
          fromAddr: find("platform_email_from_addr")
        });
      }
    } catch (e) {
      console.error("Fetch failed", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  const saveSmtp = async () => {
    setBusy(true);
    const updates = [
      { key: "platform_email_smtp_host", value: smtpForm.host },
      { key: "platform_email_smtp_port", value: smtpForm.port },
      { key: "platform_email_smtp_user", value: smtpForm.user },
      { key: "platform_email_from_name", value: smtpForm.fromName },
      { key: "platform_email_from_addr", value: smtpForm.fromAddr },
    ];

    if (smtpForm.pass !== "__REDACTED__" && smtpForm.pass !== "") {
      updates.push({ key: "platform_email_smtp_pass", value: smtpForm.pass });
    }

    try {
      for (const u of updates) {
        await apiFetch(`/admin/settings/${u.key}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value: u.value })
        });
      }
      alert("SMTP-Einstellungen gespeichert.");
      void fetchData();
    } catch (e) {
      alert("Speichern fehlgeschlagen.");
    } finally {
      setBusy(false);
    }
  };

  const sendTestMail = async () => {
    const recipient = prompt("An welche E-Mail Adresse soll die Test-Mail gesendet werden?", user?.email || "");
    if (!recipient) return;

    setTesting(true);
    try {
      const res = await apiFetch("/admin/platform/email/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: smtpForm.host,
          port: parseInt(smtpForm.port),
          user: smtpForm.user,
          pass: smtpForm.pass,
          from_name: smtpForm.fromName,
          from_addr: smtpForm.fromAddr,
          recipient: recipient
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        alert(data.message);
      } else {
        alert(`Fehler beim Senden: ${data.error}`);
      }
    } catch (e) {
      alert("Test-Verbindung fehlgeschlagen.");
    } finally {
      setTesting(false);
    }
  };

  const getS = (key: string) => settings.find(s => s.key === key)?.value || "";

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "#64748B" }}>Konfiguration wird geladen…</div>;

  if (isSystemAdmin) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        <SettingsSubnav />
        
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
           <Card style={{ padding: 24 }}>
              <SectionHeader title="Datenschutz & Sicherheit" subtitle="Globale PII-Maskierung und Aufbewahrungsfristen." />
              <div style={{ display: "grid", gap: 16, marginTop: 12 }}>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px", borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                       <Lock size={18} color="#10B981" />
                       <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#1E293B" }}>Globale PII Maskierung</div>
                          <div style={{ fontSize: 11, color: "#64748B" }}>Namen und Nummern in Logs automatisch schwärzen.</div>
                       </div>
                    </div>
                    <ToggleSwitch value={getS("platform_pii_masking_enabled") === "true"} label="PII" onChange={() => {}} />
                 </div>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px", borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                       <History size={18} color="#3B82F6" />
                       <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#1E293B" }}>Daten-Retention</div>
                          <div style={{ fontSize: 11, color: "#64748B" }}>Tage bis Nachrichten endgültig gelöscht werden.</div>
                       </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                       <input style={{...inputStyle, width: 60, textAlign: "center", padding: "6px"}} value={getS("platform_data_retention_days") || "90"} readOnly />
                       <span style={{ fontSize: 11, color: "#94A3B8" }}>Tage</span>
                    </div>
                 </div>
              </div>
           </Card>

           <Card style={{ padding: 24 }}>
              <SectionHeader title="System Governance" subtitle="Plattformweite Wartung und Compliance." />
              <div style={{ display: "grid", gap: 16, marginTop: 12 }}>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px", borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                       <Shield size={18} color="#EF4444" />
                       <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#1E293B" }}>Wartungsmodus</div>
                          <div style={{ fontSize: 11, color: "#64748B" }}>Studio-Zugang sperren und Agenten pausieren.</div>
                       </div>
                    </div>
                    <ToggleSwitch value={getS("maintenance_mode") === "true"} label="Maintenance" onChange={() => {}} />
                 </div>
                 <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px", borderRadius: 12, background: "#F8FAFC", border: "1px solid #E2E8F0" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                       <Trash2 size={18} color="#F59E0B" />
                       <div>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "#1E293B" }}>Audit Log Lifecycle</div>
                          <div style={{ fontSize: 11, color: "#64748B" }}>Aufbewahrungsdauer für Compliance-Protokolle.</div>
                       </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                       <input style={{...inputStyle, width: 60, textAlign: "center", padding: "6px"}} value={getS("platform_audit_retention_days") || "365"} readOnly />
                       <span style={{ fontSize: 11, color: "#94A3B8" }}>Tage</span>
                    </div>
                 </div>
              </div>
           </Card>
        </div>

        <Card style={{ padding: 24 }}>
          <SectionHeader title="Platform Communication" subtitle="SMTP Konfiguration für System-Mails (Resets, Billing)." />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginTop: 20 }}>
             <div style={{ gridColumn: "span 2" }}>
               <label style={labelStyle}>SMTP Host</label>
               <input style={inputStyle} value={smtpForm.host} onChange={e => setSmtpForm({...smtpForm, host: e.target.value})} placeholder="e.g. smtp.postmarkapp.com" />
             </div>
             <div>
               <label style={labelStyle}>Port</label>
               <input style={inputStyle} value={smtpForm.port} onChange={e => setSmtpForm({...smtpForm, port: e.target.value})} placeholder="587" />
             </div>
             <div>
               <label style={labelStyle}>Username</label>
               <input style={inputStyle} value={smtpForm.user} onChange={e => setSmtpForm({...smtpForm, user: e.target.value})} placeholder="api-key-username" />
             </div>
             <div>
               <label style={labelStyle}>Password</label>
               <input type="password" style={inputStyle} value={smtpForm.pass} onChange={e => setSmtpForm({...smtpForm, pass: e.target.value})} placeholder="••••••••" />
             </div>
             <div>
               <label style={labelStyle}>Sender Name</label>
               <input style={inputStyle} value={smtpForm.fromName} onChange={e => setSmtpForm({...smtpForm, fromName: e.target.value})} placeholder="ARIIA Platform" />
             </div>
             <div style={{ gridColumn: "span 3" }}>
               <label style={labelStyle}>Absender E-Mail (From Address)</label>
               <input style={inputStyle} value={smtpForm.fromAddr} onChange={e => setSmtpForm({...smtpForm, fromAddr: e.target.value})} placeholder="noreply@ariia.io" />
             </div>
          </div>
          <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end", gap: 12 }}>
             <button onClick={sendTestMail} disabled={testing || !smtpForm.host} className="btn btn-sm btn-outline gap-2" style={{borderColor: "#CBD5E1", color: "#475569"}}>
               {testing ? <RefreshCw size={14} className="animate-spin" /> : <Send size={14} />} 
               Test-Mail senden
             </button>
             <button onClick={saveSmtp} disabled={busy} className="btn btn-sm btn-primary gap-2" style={{background: "#6C5CE7", border: "none", color: "white"}}>
               {busy ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
               SMTP-Einstellungen speichern
             </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SettingsSubnav />
      <Card style={{ padding: 24 }}>
        <SectionHeader title="Studio Settings" subtitle="Zentrale Studio-Parameter verwalten." />
        <div style={{ marginTop: 20, color: "#64748B", fontSize: 13 }}>
          Die Studio-Konfiguration wurde in die spezifischen Module (Integrationen, Profil) ausgelagert.
        </div>
      </Card>
    </div>
  );
}
