"use client";

import { useState } from "react";
import Link from "next/link";
import { Mail, Loader2, ArrowRight, ArrowLeft, KeyRound } from "lucide-react";
import { apiFetch } from "@/lib/api";
import AuthLayout from "@/components/landing/AuthLayout";
import AriiaLogo from "@/components/landing/AriiaLogo";

export default function ForgotPasswordClient() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (res.ok) {
        setSent(true);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || "Something went wrong. Please try again.");
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <div className="w-full max-w-md">
        <div
          className="rounded-2xl overflow-hidden shadow-2xl"
          style={{
            background: "oklch(0.12 0.03 270)",
            border: "1px solid oklch(0.20 0.04 270)",
          }}
        >
          {/* Header */}
          <div
            className="px-8 pt-10 pb-8 text-center"
            style={{
              background: "linear-gradient(135deg, oklch(0.14 0.06 292 / 0.5), oklch(0.10 0.03 270))",
            }}
          >
            <div className="flex justify-center mb-5">
              <AriiaLogo variant="full" height={40} />
            </div>
            <div className="flex justify-center mb-4">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))" }}
              >
                <KeyRound size={32} className="text-white" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              {sent ? "Check your email" : "Forgot password?"}
            </h1>
            <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
              {sent
                ? "If the email is registered, we've sent a reset code."
                : "Enter your email and we'll send you a reset code."
              }
            </p>
          </div>

          {/* Form */}
          <div className="px-8 pb-8 pt-4">
            {sent ? (
              <div className="space-y-4">
                {/* Success message */}
                <div
                  className="p-4 rounded-xl text-center"
                  style={{
                    background: "oklch(0.15 0.06 292 / 0.2)",
                    border: "1px solid oklch(0.55 0.25 292 / 0.3)",
                  }}
                >
                  <p className="text-sm" style={{ color: "oklch(0.75 0.02 270)" }}>
                    A 6-digit reset code has been sent to
                  </p>
                  <p className="text-sm font-bold mt-1" style={{ color: "oklch(0.62 0.22 292)" }}>
                    {email}
                  </p>
                </div>

                <Link
                  href={`/reset-password?email=${encodeURIComponent(email)}`}
                  className="block w-full text-center rounded-xl py-4 font-bold uppercase tracking-wider text-xs transition-all no-underline hover:opacity-90"
                  style={{
                    background: "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))",
                    color: "white",
                    boxShadow: "0 4px 20px oklch(0.55 0.25 292 / 0.3)",
                  }}
                >
                  Enter Reset Code
                </Link>

                <button
                  onClick={() => { setSent(false); setEmail(""); }}
                  className="w-full text-center text-xs font-semibold transition-all hover:opacity-80"
                  style={{ color: "oklch(0.55 0.02 270)" }}
                >
                  Try a different email
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-1.5">
                  <label
                    className="text-[10px] font-bold uppercase tracking-widest ml-1"
                    style={{ color: "oklch(0.50 0.02 270)" }}
                  >
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail
                      className="absolute left-3.5 top-1/2 -translate-y-1/2"
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
                      placeholder="your@email.com"
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
                      <Mail size={16} />
                      Send Reset Code
                      <ArrowRight size={16} />
                    </>
                  )}
                </button>
              </form>
            )}

            {/* Back to login */}
            <div className="mt-6">
              <Link
                href="/login"
                className="flex items-center justify-center gap-2 w-full text-center rounded-xl py-3 text-xs font-bold uppercase tracking-wider transition-all no-underline hover:opacity-90"
                style={{
                  background: "oklch(0.15 0.03 270)",
                  border: "1px solid oklch(0.22 0.04 270)",
                  color: "oklch(0.70 0.02 270)",
                }}
              >
                <ArrowLeft size={14} />
                Back to Login
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AuthLayout>
  );
}
