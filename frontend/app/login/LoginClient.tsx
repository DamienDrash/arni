
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LogIn, Mail, Lock, Loader2, ArrowRight, Eye, EyeOff } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import { useI18n } from "@/lib/i18n/LanguageContext";
import AuthLayout from "@/components/landing/AuthLayout";
import AriiaLogo from "@/components/landing/AriiaLogo";

export default function LoginClient() {
  const { t } = useI18n();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPwd, setShowPwd] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (res.ok) {
        const data = await res.json();
        storeSession(data.access_token, data.user);
        router.replace("/dashboard");
      } else {
        const data = await res.json();
        setError(data.detail || t("ai.errors.connectionError"));
      }
    } catch {
      setError(t("ai.errors.connectionError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <div className="w-full max-w-md">
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
              {t("common.login")}
            </h1>
            <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
              Melden Sie sich bei Ihrem ARIIA-Konto an
            </p>
          </div>

          {/* Form */}
          <div className="px-8 pb-8 pt-2">
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-1.5">
                <label
                  className="text-[10px] font-bold uppercase tracking-widest ml-1"
                  style={{ color: "oklch(0.50 0.02 270)" }}
                >
                  {t("members.form.email")}
                </label>
                <div className="relative group">
                  <Mail
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    size={18}
                    style={{ color: "oklch(0.45 0.02 270)" }}
                  />
                  <input
                    type="email"
                    required
                    className="w-full rounded-xl pl-11 pr-4 py-3.5 text-white outline-none transition-all text-sm"
                    style={{
                      background: "oklch(0.09 0.03 270)",
                      border: "1px solid oklch(0.20 0.04 270)",
                    }}
                    placeholder={t("login.placeholders.email")}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onFocus={(e) => {
                      e.target.style.borderColor = "oklch(0.62 0.22 292)";
                      e.target.style.boxShadow = "0 0 0 3px oklch(0.62 0.22 292 / 0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "oklch(0.20 0.04 270)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label
                  className="text-[10px] font-bold uppercase tracking-widest ml-1"
                  style={{ color: "oklch(0.50 0.02 270)" }}
                >
                  {t("settings.general.smtp.pass")}
                </label>
                <div className="relative group">
                  <Lock
                    className="absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors"
                    size={18}
                    style={{ color: "oklch(0.45 0.02 270)" }}
                  />
                  <input
                    type={showPwd ? "text" : "password"}
                    required
                    className="w-full rounded-xl pl-11 pr-12 py-3.5 text-white outline-none transition-all text-sm"
                    style={{
                      background: "oklch(0.09 0.03 270)",
                      border: "1px solid oklch(0.20 0.04 270)",
                    }}
                    placeholder={t("login.placeholders.password")}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onFocus={(e) => {
                      e.target.style.borderColor = "oklch(0.62 0.22 292)";
                      e.target.style.boxShadow = "0 0 0 3px oklch(0.62 0.22 292 / 0.1)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "oklch(0.20 0.04 270)";
                      e.target.style.boxShadow = "none";
                    }}
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
                  <div
                    className="w-2 h-2 rounded-full animate-pulse flex-shrink-0"
                    style={{ background: "oklch(0.60 0.2 25)" }}
                  />
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl py-4 font-bold uppercase tracking-wider text-xs flex items-center justify-center gap-3 transition-all active:scale-[0.98] disabled:opacity-50"
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
                    <LogIn size={16} />
                    {t("common.login")}
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

            {/* Register Link */}
            <Link
              href="/register"
              className="block w-full text-center rounded-xl py-3.5 text-xs font-bold uppercase tracking-wider transition-all no-underline hover:opacity-90"
              style={{
                background: "oklch(0.15 0.03 270)",
                border: "1px solid oklch(0.22 0.04 270)",
                color: "oklch(0.70 0.02 270)",
              }}
            >
              Noch kein Konto? Jetzt registrieren
            </Link>
          </div>
        </div>
      </div>
    </AuthLayout>
  );
}
