"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { T } from "@/lib/tokens";
import { CreditCard, Layers3, Wallet, PlugZap } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Plan = {
  id: string;
  name: string;
  priceMonthly: number;
  membersIncluded: number;
  messagesIncluded: number;
  aiAgents: number;
  support: string;
  highlight?: boolean;
};

type Provider = { id: string; name: string; enabled: boolean; mode: "mock" | "live"; note: string };

type StripeConfig = {
  enabled: boolean;
  mode: "test" | "live";
  publishable_key: string;
  secret_key: string;
  webhook_secret: string;
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

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [scope, setScope] = useState("global_system");
  const [status, setStatus] = useState("Lade Konfiguration...");
  const [isSaving, setIsSaving] = useState(false);

  const [stripe, setStripe] = useState<StripeConfig>({
    enabled: false,
    mode: "test",
    publishable_key: "",
    secret_key: "",
    webhook_secret: "",
  });
  const [connectorStatus, setConnectorStatus] = useState("");

  const [draftName, setDraftName] = useState("");
  const [draftPrice, setDraftPrice] = useState(99);

  const loadAll = async () => {
    try {
      const [plansRes, connectorsRes] = await Promise.all([
        apiFetch("/admin/plans/config"),
        apiFetch("/admin/billing/connectors"),
      ]);
      if (plansRes.ok) {
        const data = await plansRes.json();
        setPlans(Array.isArray(data.plans) ? data.plans : []);
        setProviders(Array.isArray(data.providers) ? data.providers : []);
        setScope(typeof data.scope === "string" ? data.scope : "global_system");
      }
      if (connectorsRes.ok) {
        const c = await connectorsRes.json();
        if (c?.stripe) {
          setStripe({
            enabled: !!c.stripe.enabled,
            mode: (c.stripe.mode || "test") as "test" | "live",
            publishable_key: c.stripe.publishable_key || "",
            secret_key: c.stripe.secret_key || "",
            webhook_secret: c.stripe.webhook_secret || "",
          });
        }
      }
      setStatus("Globale Billing-Konfiguration geladen.");
    } catch {
      setStatus("Laden fehlgeschlagen.");
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  const persistPlans = async (nextPlans: Plan[], nextProviders: Provider[]) => {
    setIsSaving(true);
    try {
      const defaultProvider =
        nextProviders.find((p) => p.id === "stripe")?.enabled
          ? "stripe"
          : (nextProviders.find((p) => p.enabled)?.id || "stripe");
      const res = await apiFetch("/admin/plans/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plans: nextPlans, providers: nextProviders, default_provider: defaultProvider }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setStatus(data?.detail || `Speichern fehlgeschlagen (${res.status})`);
        return false;
      }
      setStatus("Globale Plans-Konfiguration gespeichert.");
      return true;
    } catch {
      setStatus("Speichern fehlgeschlagen (Netzwerkfehler).");
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const persistStripe = async () => {
    setIsSaving(true);
    try {
      const res = await apiFetch("/admin/billing/connectors", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stripe }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setConnectorStatus(data?.detail || `Connector speichern fehlgeschlagen (${res.status})`);
        return;
      }
      setConnectorStatus("Stripe Connector gespeichert (global_system).");
      await loadAll();
    } catch {
      setConnectorStatus("Connector speichern fehlgeschlagen (Netzwerkfehler).");
    } finally {
      setIsSaving(false);
    }
  };

  const testStripe = async () => {
    setConnectorStatus("Teste Stripe-Verbindung...");
    try {
      const res = await apiFetch("/admin/billing/connectors/stripe/test", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setConnectorStatus(data?.detail || `Stripe Test fehlgeschlagen (${res.status})`);
        return;
      }
      setConnectorStatus(`Stripe OK · Account: ${data.account_id || "-"} · Charges: ${String(data.charges_enabled)}`);
    } catch {
      setConnectorStatus("Stripe Test fehlgeschlagen (Netzwerkfehler).");
    }
  };

  const stats = useMemo(() => {
    return {
      planCount: plans.length,
      avgPrice: Math.round(plans.reduce((acc, p) => acc + Number(p.priceMonthly || 0), 0) / Math.max(1, plans.length)),
      enabledProviders: providers.filter((p) => p.enabled).length,
    };
  }, [plans, providers]);

  const toggleProvider = (id: string) => {
    const nextProviders = providers.map((p) => {
      if (p.id !== id) return p;
      if (id === "stripe") return { ...p, enabled: true };
      return { ...p, enabled: !p.enabled };
    });
    setProviders(nextProviders);
    void persistPlans(plans, nextProviders);
  };

  const setStripeDefault = () => {
    const nextProviders = providers.map((p) => ({ ...p, enabled: p.id === "stripe" ? true : p.enabled }));
    setProviders(nextProviders);
    void persistPlans(plans, nextProviders);
    setStatus("Stripe als Default Provider markiert.");
  };

  const addPlan = () => {
    if (!draftName.trim()) return;
    const nextPlans = [
      ...plans,
      {
        id: draftName.trim().toLowerCase().replace(/\s+/g, "-"),
        name: draftName.trim(),
        priceMonthly: Number(draftPrice) || 0,
        membersIncluded: 1000,
        messagesIncluded: 20000,
        aiAgents: 3,
        support: "Email",
      },
    ];
    setPlans(nextPlans);
    void persistPlans(nextPlans, providers);
    setDraftName("");
    setDraftPrice(99);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 12 }}>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>Pläne</div><div style={{ fontSize: 26, color: T.text, fontWeight: 800 }}>{stats.planCount}</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>Ø Preis / Monat</div><div style={{ fontSize: 26, color: T.accent, fontWeight: 800 }}>{stats.avgPrice}€</div></Card>
        <Card style={{ padding: 14 }}><div style={{ fontSize: 11, color: T.textDim }}>Aktive Provider</div><div style={{ fontSize: 26, color: T.success, fontWeight: 800 }}>{stats.enabledProviders}</div></Card>
      </div>

      <Card style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Layers3 size={15} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Plans Catalog</span>
          <Badge variant="accent" size="xs">Scope: {scope}</Badge>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
          {plans.map((p) => (
            <div key={p.id} style={{ border: `1px solid ${p.highlight ? `${T.accent}88` : T.border}`, borderRadius: 12, padding: 12, background: p.highlight ? T.accentDim : T.surfaceAlt }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: 14, color: T.text, fontWeight: 700 }}>{p.name}</div>
                {p.highlight && <Badge variant="accent" size="xs">Recommended</Badge>}
              </div>
              <div style={{ marginTop: 6, fontSize: 22, color: T.text, fontWeight: 800 }}>{p.priceMonthly}€<span style={{ fontSize: 11, color: T.textDim, fontWeight: 500 }}>/Monat</span></div>
              <div style={{ marginTop: 8, fontSize: 12, color: T.textDim }}>Mitglieder: {p.membersIncluded}</div>
              <div style={{ marginTop: 2, fontSize: 12, color: T.textDim }}>Messages: {p.messagesIncluded}</div>
              <div style={{ marginTop: 2, fontSize: 12, color: T.textDim }}>Agents: {p.aiAgents}</div>
              <div style={{ marginTop: 2, fontSize: 12, color: T.textDim }}>Support: {p.support}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: 10 }}>
          <input style={inputStyle} placeholder="Neuer Planname" value={draftName} onChange={(e) => setDraftName(e.target.value)} />
          <input style={inputStyle} type="number" min={0} value={draftPrice} onChange={(e) => setDraftPrice(Number(e.target.value || 0))} />
          <button onClick={addPlan} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 14px", cursor: "pointer" }}>Plan hinzufügen</button>
        </div>
      </Card>

      <Card style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <Wallet size={15} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Payment Methods (Mockup)</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
          {providers.map((p) => (
            <div key={p.id} style={{ border: `1px solid ${T.border}`, borderRadius: 12, padding: 12, background: T.surfaceAlt }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <CreditCard size={14} color={T.textDim} />
                  <span style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>{p.name}</span>
                </div>
                {p.id === "stripe" ? <Badge variant="accent" size="xs">Default</Badge> : <Badge size="xs">Optional</Badge>}
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: T.textDim }}>{p.note} · Modus: {p.mode}</div>
              <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                <button onClick={() => toggleProvider(p.id)} style={{ borderRadius: 8, border: `1px solid ${T.border}`, background: p.enabled ? T.successDim : T.surface, color: T.text, fontSize: 12, padding: "7px 10px", cursor: "pointer" }}>
                  {p.enabled ? "Aktiv" : "Inaktiv"}
                </button>
                {p.id === "stripe" && <button onClick={setStripeDefault} style={{ borderRadius: 8, border: `1px solid ${T.border}`, background: T.accentDim, color: T.text, fontSize: 12, padding: "7px 10px", cursor: "pointer" }}>Als Default</button>}
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: T.textDim }}>{status} {isSaving ? "· Speichere..." : ""}</div>
      </Card>

      <Card style={{ padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <PlugZap size={15} color={T.accent} />
          <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Stripe Connector (global)</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 10 }}>
          <select style={inputStyle} value={stripe.mode} onChange={(e) => setStripe({ ...stripe, mode: e.target.value as "test" | "live" })}>
            <option value="test">test</option>
            <option value="live">live</option>
          </select>
          <select style={inputStyle} value={stripe.enabled ? "true" : "false"} onChange={(e) => setStripe({ ...stripe, enabled: e.target.value === "true" })}>
            <option value="true">enabled</option>
            <option value="false">disabled</option>
          </select>
          <input style={inputStyle} placeholder="Publishable Key (pk_...)" value={stripe.publishable_key} onChange={(e) => setStripe({ ...stripe, publishable_key: e.target.value })} />
          <input style={inputStyle} placeholder="Secret Key (sk_...)" value={stripe.secret_key} onChange={(e) => setStripe({ ...stripe, secret_key: e.target.value })} />
          <input style={inputStyle} placeholder="Webhook Secret (whsec_...)" value={stripe.webhook_secret} onChange={(e) => setStripe({ ...stripe, webhook_secret: e.target.value })} />
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={persistStripe} style={{ borderRadius: 10, border: "none", background: T.accent, color: "#061018", fontWeight: 700, padding: "10px 14px", cursor: "pointer" }}>Connector speichern</button>
            <button onClick={testStripe} style={{ borderRadius: 10, border: `1px solid ${T.border}`, background: T.surfaceAlt, color: T.text, fontWeight: 600, padding: "10px 14px", cursor: "pointer" }}>Verbindung testen</button>
          </div>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: T.textDim }}>{connectorStatus || "Noch kein Test ausgeführt."}</div>
      </Card>
    </div>
  );
}
