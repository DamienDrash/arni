"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { CheckCircle, Loader2, AlertCircle, Gift } from "lucide-react";

const C = {
  bg: "#0a0a0a", card: "#1a1a1a", border: "#2a2a2a",
  text: "#e8e9ed", textMuted: "#8b8d9a", textDim: "#5a5c6b",
  accent: "#6C5CE7", accentLight: "#A29BFE",
  success: "#00D68F", danger: "#FF6B6B",
};

interface SubscribeInfo {
  tenant_name: string;
  campaign_name: string | null;
  channel: string;
  description: string | null;
  offer_name: string | null;
}

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "12px 16px", borderRadius: 10,
  border: `1px solid ${C.border}`, background: C.bg,
  color: C.text, fontSize: 14, outline: "none", boxSizing: "border-box",
};

export default function SubscribePage() {
  const { token } = useParams<{ token: string }>();
  const searchParams = useSearchParams();
  const offer = searchParams.get("offer");

  const [info, setInfo] = useState<SubscribeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const offerParam = offer ? `?offer=${encodeURIComponent(offer)}` : "";
    const url = base
      ? `${base}/public/subscribe/${token}${offerParam}`
      : `/proxy/public/subscribe/${token}${offerParam}`;

    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error("Ungültiger Link.");
        return res.json() as Promise<SubscribeInfo>;
      })
      .then(setInfo)
      .catch((e) => setLoadError(e.message || "Fehler beim Laden."))
      .finally(() => setLoading(false));
  }, [token, offer]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim() || !lastName.trim()) return;
    setSubmitting(true);
    setSubmitError(null);

    const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const offerParam = offer ? `?offer=${encodeURIComponent(offer)}` : "";
    const url = base
      ? `${base}/public/subscribe/${token}${offerParam}`
      : `/proxy/public/subscribe/${token}${offerParam}`;

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Fehler bei der Anmeldung.");
      }
      setSuccess(true);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Unbekannter Fehler.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Loader2 size={32} style={{ color: C.accent, animation: "spin 1s linear infinite" }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );

  if (loadError) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ textAlign: "center", maxWidth: 400 }}>
        <AlertCircle size={48} style={{ color: C.danger, marginBottom: 16 }} />
        <p style={{ color: C.danger, fontSize: 16 }}>{loadError}</p>
      </div>
    </div>
  );

  if (success) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <div style={{ textAlign: "center", maxWidth: 440 }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", background: "rgba(0,214,143,0.12)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <CheckCircle size={36} style={{ color: C.success }} />
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: "0 0 8px" }}>
          Fast geschafft!
        </h1>
        <p style={{ fontSize: 15, color: C.textMuted, lineHeight: 1.7, margin: "0 0 12px" }}>
          Wir haben dir eine <strong style={{ color: C.text }}>Bestätigungs-E-Mail</strong> gesendet.
        </p>
        <p style={{ fontSize: 13, color: C.textDim, lineHeight: 1.6 }}>
          Bitte klicke auf den Link in der E-Mail, um deine Anmeldung abzuschließen.
          {info?.offer_name && (
            <><br /><br />Danach erhältst du: <strong style={{ color: C.accentLight }}>{info.offer_name}</strong></>
          )}
        </p>
        <p style={{ fontSize: 11, color: C.textDim, marginTop: 20 }}>
          Kein E-Mail erhalten? Prüfe deinen Spam-Ordner.
        </p>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <div style={{ width: "100%", maxWidth: 440, background: C.card, borderRadius: 20, border: `1px solid ${C.border}`, padding: 32 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: "0 0 6px" }}>
            {info?.campaign_name || "Newsletter"}
          </h1>
          <p style={{ fontSize: 13, color: C.textMuted, margin: 0 }}>{info?.tenant_name || "Studio"}</p>
          {info?.description && (
            <p style={{ fontSize: 14, color: C.textDim, marginTop: 12, lineHeight: 1.5 }}>{info.description}</p>
          )}
          {/* Offer badge */}
          {info?.offer_name && (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 6, marginTop: 14, padding: "8px 14px", borderRadius: 20, background: "rgba(108,92,231,0.15)", border: "1px solid rgba(108,92,231,0.3)" }}>
              <Gift size={14} style={{ color: C.accentLight }} />
              <span style={{ fontSize: 13, fontWeight: 600, color: C.accentLight }}>{info.offer_name}</span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: C.textMuted, marginBottom: 6 }}>Vorname *</label>
            <input type="text" required value={firstName} onChange={(e) => setFirstName(e.target.value)} placeholder="Max" style={inputStyle} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: C.textMuted, marginBottom: 6 }}>Nachname *</label>
            <input type="text" required value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Mustermann" style={inputStyle} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: C.textMuted, marginBottom: 6 }}>E-Mail</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="max@example.com" style={inputStyle} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: C.textMuted, marginBottom: 6 }}>Telefon</label>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+49 170 1234567" style={inputStyle} />
          </div>

          {submitError && (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 10, background: "rgba(255,107,107,0.1)", border: "1px solid rgba(255,107,107,0.3)" }}>
              <AlertCircle size={14} style={{ color: C.danger, flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: C.danger }}>{submitError}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !firstName.trim() || !lastName.trim()}
            style={{ width: "100%", padding: "14px 0", borderRadius: 12, border: "none", background: submitting ? C.textDim : C.accent, color: "#fff", fontSize: 15, fontWeight: 700, cursor: submitting ? "default" : "pointer", marginTop: 6, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            {submitting ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Wird gesendet...</> : "Jetzt anmelden"}
          </button>
        </form>

        <p style={{ fontSize: 11, color: C.textDim, textAlign: "center", marginTop: 20, lineHeight: 1.5 }}>
          Mit der Anmeldung stimmen Sie dem Erhalt von Nachrichten zu.
          Sie können sich jederzeit <a href="#" style={{ color: C.textDim, textDecoration: "underline" }}>abmelden</a>.
        </p>
      </div>
    </div>
  );
}
