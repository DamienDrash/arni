"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { storeSession } from "@/lib/auth";
import { withBasePath } from "@/lib/base-path";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(withBasePath("/proxy/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || `Login failed (${res.status})`);
        return;
      }
      const data = await res.json();
      storeSession(data.access_token, data.user);
      router.replace("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100svh", display: "grid", placeItems: "center" }}>
      <Card style={{ width: 420, maxWidth: "92vw", padding: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, color: T.text }}>Login</h1>
        <p style={{ marginTop: 6, color: T.textDim, fontSize: 13 }}>Melde dich mit deinem Account an.</p>
        <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-Mail" style={inputStyle} />
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Passwort" style={inputStyle} />
          {error && <div style={{ color: T.danger, fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={loading} style={buttonStyle}>{loading ? "Bitte warten…" : "Login"}</button>
          <button onClick={() => router.push("/register")} style={{ ...buttonStyle, background: T.surfaceAlt, color: T.text }}>
            Registrierung
          </button>
        </div>
      </Card>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 12px",
  borderRadius: 10,
  border: `1px solid ${T.border}`,
  background: T.surfaceAlt,
  color: T.text,
  fontSize: 14,
  outline: "none",
};

const buttonStyle: React.CSSProperties = {
  width: "100%",
  border: "none",
  borderRadius: 10,
  padding: "10px 12px",
  cursor: "pointer",
  background: T.accent,
  color: "#061018",
  fontWeight: 700,
};
