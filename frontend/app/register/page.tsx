"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { T } from "@/lib/tokens";
import { storeSession } from "@/lib/auth";
import { withBasePath } from "@/lib/base-path";
import { useI18n } from "@/lib/i18n/LanguageContext";

export default function RegisterPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [tenantName, setTenantName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(withBasePath("/proxy/auth/register"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tenant_name: tenantName,
          tenant_slug: tenantSlug || undefined,
          email,
          full_name: fullName || undefined,
          password,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || `Register failed (${res.status})`);
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
      <Card style={{ width: 500, maxWidth: "92vw", padding: 24 }}>
        <h1 style={{ margin: 0, fontSize: 24, color: T.text }}>{t("register.title")}</h1>
        <p style={{ marginTop: 6, color: T.textDim, fontSize: 13 }}>{t("register.subtitle")}</p>
        <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
          <input value={tenantName} onChange={(e) => setTenantName(e.target.value)} placeholder={t("register.tenantName")} style={inputStyle} />
          <input value={tenantSlug} onChange={(e) => setTenantSlug(e.target.value)} placeholder={t("register.tenantSlug")} style={inputStyle} />
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("register.email")} style={inputStyle} />
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder={t("register.name")} style={inputStyle} />
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder={t("register.password")} style={inputStyle} />
          {error && <div style={{ color: T.danger, fontSize: 12 }}>{error}</div>}
          <button onClick={submit} disabled={loading} style={buttonStyle}>{loading ? t("register.waiting") : t("register.button")}</button>
          <button onClick={() => router.push("/login")} style={{ ...buttonStyle, background: T.surfaceAlt, color: T.text }}>
            {t("register.backToLogin")}
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
