"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle, Loader2, AlertCircle, MailX } from "lucide-react";

const C = {
  bg: "#0a0a0a", card: "#1a1a1a", border: "#2a2a2a",
  text: "#e8e9ed", textMuted: "#8b8d9a", textDim: "#5a5c6b",
  accent: "#6C5CE7", success: "#00D68F", danger: "#FF6B6B",
};

interface UnsubInfo {
  tenant_name: string;
  channel: string;
}

export default function UnsubscribePage() {
  const { token } = useParams<{ token: string }>();

  const [info, setInfo] = useState<UnsubInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const url = base ? `${base}/public/unsubscribe/${token}` : `/proxy/public/unsubscribe/${token}`;

    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error("Ungültiger Abmelde-Link.");
        return res.json() as Promise<UnsubInfo>;
      })
      .then(setInfo)
      .catch((e) => setLoadError(e.message || "Fehler beim Laden."))
      .finally(() => setLoading(false));
  }, [token]);

  const handleUnsubscribe = async () => {
    setSubmitting(true);
    setSubmitError(null);
    const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const url = base ? `${base}/public/unsubscribe/${token}` : `/proxy/public/unsubscribe/${token}`;
    try {
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || "Fehler bei der Abmeldung.");
      }
      setDone(true);
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

  if (done) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ textAlign: "center", maxWidth: 420 }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", background: "rgba(0,214,143,0.12)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <CheckCircle size={36} style={{ color: C.success }} />
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: "0 0 8px" }}>Erfolgreich abgemeldet</h1>
        <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
          Sie erhalten keine weiteren Nachrichten{info?.tenant_name ? ` von ${info.tenant_name}` : ""}.
        </p>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <div style={{ width: "100%", maxWidth: 420, background: C.card, borderRadius: 20, border: `1px solid ${C.border}`, padding: 36, textAlign: "center" }}>
        <div style={{ width: 64, height: 64, borderRadius: "50%", background: "rgba(255,107,107,0.1)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <MailX size={28} style={{ color: C.danger }} />
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, margin: "0 0 10px" }}>Abmelden</h1>
        <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6, margin: "0 0 28px" }}>
          Möchten Sie sich von{info?.tenant_name ? ` ${info.tenant_name}` : ""} abmelden?
          Sie erhalten dann keine weiteren Nachrichten mehr.
        </p>

        {submitError && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 10, marginBottom: 16, background: "rgba(255,107,107,0.1)", border: "1px solid rgba(255,107,107,0.3)", textAlign: "left" }}>
            <AlertCircle size={14} style={{ color: C.danger, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: C.danger }}>{submitError}</span>
          </div>
        )}

        <button
          onClick={() => void handleUnsubscribe()}
          disabled={submitting}
          style={{ width: "100%", padding: "14px 0", borderRadius: 12, border: "none", background: submitting ? C.textDim : C.danger, color: "#fff", fontSize: 15, fontWeight: 700, cursor: submitting ? "default" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
        >
          {submitting ? <><Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} /> Abmelden...</> : "Ja, abmelden"}
        </button>

        <p style={{ fontSize: 11, color: C.textDim, marginTop: 16 }}>
          Sie können sich jederzeit wieder anmelden.
        </p>
      </div>
    </div>
  );
}
