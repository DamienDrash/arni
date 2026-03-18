"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CheckCircle, Loader2, AlertCircle, Gift, Clock } from "lucide-react";

const C = {
  bg: "#0a0a0a", card: "#1a1a1a", border: "#2a2a2a",
  text: "#e8e9ed", textMuted: "#8b8d9a", textDim: "#5a5c6b",
  accent: "#6C5CE7", accentLight: "#A29BFE",
  success: "#00D68F", danger: "#FF6B6B", warning: "#FFB74D",
};

interface ConfirmResult {
  status: string;
  tenant_name: string;
  first_name: string;
  offer_name: string | null;
}

type State = "loading" | "confirmed" | "expired" | "error";

export default function OptinConfirmPage() {
  const { token } = useParams<{ token: string }>();
  const [state, setState] = useState<State>("loading");
  const [result, setResult] = useState<ConfirmResult | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) return;

    const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const url = base
      ? `${base}/public/optin-confirm/${token}`
      : `/proxy/public/optin-confirm/${token}`;

    fetch(url)
      .then(async (res) => {
        if (res.status === 410) {
          setState("expired");
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || `Fehler ${res.status}`);
        }
        const data = await res.json() as ConfirmResult;
        setResult(data);
        setState("confirmed");
      })
      .catch((e) => {
        setErrorMsg(e.message || "Unbekannter Fehler.");
        setState("error");
      });
  }, [token]);

  if (state === "loading") return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center" }}>
        <Loader2 size={36} style={{ color: C.accent, animation: "spin 1s linear infinite", marginBottom: 16 }} />
        <p style={{ color: C.textMuted, fontSize: 14 }}>Anmeldung wird bestätigt…</p>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  );

  if (state === "expired") return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ textAlign: "center", maxWidth: 420 }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", background: "rgba(255,183,77,0.12)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <Clock size={36} style={{ color: C.warning }} />
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, margin: "0 0 10px" }}>
          Link abgelaufen
        </h1>
        <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
          Dieser Bestätigungslink ist abgelaufen oder wurde bereits verwendet.<br />
          Bitte melde dich erneut an, um einen neuen Link zu erhalten.
        </p>
      </div>
    </div>
  );

  if (state === "error") return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ textAlign: "center", maxWidth: 420 }}>
        <div style={{ width: 72, height: 72, borderRadius: "50%", background: "rgba(255,107,107,0.12)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
          <AlertCircle size={36} style={{ color: C.danger }} />
        </div>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, margin: "0 0 10px" }}>
          Fehler bei der Bestätigung
        </h1>
        <p style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>{errorMsg}</p>
      </div>
    </div>
  );

  // confirmed
  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ textAlign: "center", maxWidth: 440 }}>
        <div style={{ width: 80, height: 80, borderRadius: "50%", background: "rgba(0,214,143,0.12)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" }}>
          <CheckCircle size={40} style={{ color: C.success }} />
        </div>

        <h1 style={{ fontSize: 24, fontWeight: 800, color: C.text, margin: "0 0 10px" }}>
          Anmeldung bestätigt!
        </h1>

        <p style={{ fontSize: 15, color: C.textMuted, lineHeight: 1.7, margin: "0 0 20px" }}>
          {result?.first_name ? `Hallo ${result.first_name}, d` : "D"}eine Anmeldung bei{" "}
          <strong style={{ color: C.text }}>{result?.tenant_name}</strong> wurde erfolgreich bestätigt.
        </p>

        {result?.offer_name && (
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "12px 20px", borderRadius: 12, background: "rgba(108,92,231,0.12)", border: "1px solid rgba(108,92,231,0.25)", marginBottom: 20 }}>
            <Gift size={18} style={{ color: C.accentLight }} />
            <div style={{ textAlign: "left" }}>
              <p style={{ margin: 0, fontSize: 11, color: C.accentLight, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>
                Dein Angebot
              </p>
              <p style={{ margin: 0, fontSize: 14, color: C.text, fontWeight: 700 }}>
                {result.offer_name}
              </p>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: C.textMuted }}>
                Wird dir in Kürze per E-Mail zugesendet
              </p>
            </div>
          </div>
        )}

        <p style={{ fontSize: 12, color: C.textDim, marginTop: 8 }}>
          Du kannst dieses Fenster jetzt schließen.
        </p>
      </div>
    </div>
  );
}
