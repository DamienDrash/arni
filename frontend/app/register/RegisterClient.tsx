"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { UserPlus, Mail, Lock, Building2, User, Globe, Loader2, ArrowRight, Eye, EyeOff } from "lucide-react";
import { storeSession } from "@/lib/auth";
import { withBasePath } from "@/lib/base-path";
import { useI18n } from "@/lib/i18n/LanguageContext";
import AuthLayout from "@/components/landing/AuthLayout";
import AriiaLogo from "@/components/landing/AriiaLogo";

export default function RegisterClient() {
  const { t } = useI18n();
  const router = useRouter();
  const [tenantName, setTenantName] = useState("");
  const [tenantSlug, setTenantSlug] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPwd, setShowPwd] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
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
        setError(data?.detail || `Registrierung fehlgeschlagen (${res.status})`);
        return;
      }
      const data = await res.json();
      storeSession(data.access_token, data.user);
      router.replace("/dashboard");
    } catch {
      setError("Verbindungsfehler. Bitte versuchen Sie es erneut.");
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full rounded-xl pl-11 pr-4 py-3.5 text-white outline-none transition-all text-sm";
  const inputStyle: React.CSSProperties = {
    background: "oklch(0.09 0.03 270)",
    border: "1px solid oklch(0.20 0.04 270)",
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = "oklch(0.62 0.22 292)";
    e.target.style.boxShadow = "0 0 0 3px oklch(0.62 0.22 292 / 0.1)";
  };
  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = "oklch(0.20 0.04 270)";
    e.target.style.boxShadow = "none";
  };

  return (
    <AuthLayout>
      <div className="w-full max-w-lg">
        {/* Card */}
        <div
          className="rounded-2xl overflow-hidden shadow-2xl"
          style={{
            background: "oklch(0.12 0.03 270)",
            border: "1px solid oklch(0.20 0.04 270)",
          }}
        >
          {/* Header with gradient */}
          <div
            className="px-8 pt-10 pb-8 text-center"
            style={{
              background: "linear-gradient(135deg, oklch(0.14 0.06 292 / 0.5), oklch(0.10 0.03 270))",
            }}
          >
            <div className="flex justify-center mb-5">
              <AriiaLogo variant="full" height={40} />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              {t("register.title")}
            </h1>
            <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
              {t("register.subtitle")}
            </p>
          </div>

          {/* Form */}
          <div className="px-8 pb-8 pt-2">
            <form onSubmit={submit} className="space-y-4">
              {/* Studio / Tenant Section */}
              <div className="space-y-1">
                <p
                  className="text-[10px] font-bold uppercase tracking-widest ml-1 mb-3 flex items-center gap-2"
                  style={{ color: "oklch(0.62 0.22 292)" }}
                >
                  <Building2 size={12} /> Ihr Studio
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                    {t("register.tenantName")}
                  </label>
                  <div className="relative">
                    <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                    <input
                      required
                      className={inputClass}
                      style={inputStyle}
                      placeholder="Mein Studio"
                      value={tenantName}
                      onChange={(e) => setTenantName(e.target.value)}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                    {t("register.tenantSlug")}
                  </label>
                  <div className="relative">
                    <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                    <input
                      className={inputClass}
                      style={inputStyle}
                      placeholder="mein-studio"
                      value={tenantSlug}
                      onChange={(e) => setTenantSlug(e.target.value)}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                    />
                  </div>
                </div>
              </div>

              {/* Divider */}
              <div className="flex items-center gap-4 py-1">
                <div className="flex-1 h-px" style={{ background: "oklch(0.18 0.03 270)" }} />
                <span className="text-[10px] font-bold uppercase tracking-widest flex items-center gap-2" style={{ color: "oklch(0.62 0.22 292)" }}>
                  <User size={12} /> Ihr Konto
                </span>
                <div className="flex-1 h-px" style={{ background: "oklch(0.18 0.03 270)" }} />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                  Vollständiger Name
                </label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                  <input
                    className={inputClass}
                    style={inputStyle}
                    placeholder="Max Mustermann"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                  {t("register.email")}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                  <input
                    type="email"
                    required
                    className={inputClass}
                    style={inputStyle}
                    placeholder="admin@studio.de"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                  {t("register.password")}
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                  <input
                    type={showPwd ? "text" : "password"}
                    required
                    className="w-full rounded-xl pl-11 pr-12 py-3.5 text-white outline-none transition-all text-sm"
                    style={inputStyle}
                    placeholder="Sicheres Passwort"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(!showPwd)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 transition-colors hover:opacity-80"
                    style={{ color: "oklch(0.45 0.02 270)" }}
                    tabIndex={-1}
                  >
                    {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {error && (
                <div
                  className="p-3.5 rounded-xl text-xs font-semibold flex items-center gap-3"
                  style={{
                    background: "oklch(0.25 0.12 25 / 0.15)",
                    border: "1px solid oklch(0.55 0.2 25 / 0.3)",
                    color: "oklch(0.70 0.15 25)",
                  }}
                >
                  <div className="w-2 h-2 rounded-full animate-pulse flex-shrink-0" style={{ background: "oklch(0.60 0.2 25)" }} />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl py-4 font-bold uppercase tracking-wider text-xs flex items-center justify-center gap-3 transition-all active:scale-[0.98] disabled:opacity-50 mt-2"
                style={{
                  background: "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))",
                  color: "white",
                  boxShadow: "0 4px 20px oklch(0.55 0.25 292 / 0.3)",
                }}
              >
                {loading ? (
                  <Loader2 className="animate-spin" size={18} />
                ) : (
                  <>
                    <UserPlus size={16} />
                    {t("register.button")}
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-4 my-6">
              <div className="flex-1 h-px" style={{ background: "oklch(0.20 0.04 270)" }} />
              <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: "oklch(0.40 0.02 270)" }}>
                oder
              </span>
              <div className="flex-1 h-px" style={{ background: "oklch(0.20 0.04 270)" }} />
            </div>

            {/* Login Link */}
            <Link
              href="/login"
              className="block w-full text-center rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider transition-all no-underline hover:opacity-90"
              style={{
                background: "oklch(0.15 0.03 270)",
                border: "1px solid oklch(0.22 0.04 270)",
                color: "oklch(0.70 0.02 270)",
              }}
            >
              {t("register.backToLogin")}
            </Link>
          </div>
        </div>
      </div>
    </AuthLayout>
  );
}
