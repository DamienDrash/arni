"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ShieldCheck, Loader2, ArrowRight, RefreshCw, CheckCircle2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import AuthLayout from "@/components/landing/AuthLayout";
import AriiaLogo from "@/components/landing/AriiaLogo";

export default function VerifyEmailClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const emailParam = searchParams.get("email") || "";

  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Auto-focus first input
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  const handleInput = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const newCode = [...code];
    newCode[index] = value.slice(-1);
    setCode(newCode);

    // Auto-advance to next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all 6 digits entered
    if (value && index === 5 && newCode.every(d => d)) {
      handleVerify(newCode.join(""));
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      const newCode = pasted.split("");
      setCode(newCode);
      inputRefs.current[5]?.focus();
      handleVerify(pasted);
    }
  };

  const handleVerify = async (codeStr?: string) => {
    const fullCode = codeStr || code.join("");
    if (fullCode.length !== 6) {
      setError("Please enter the complete 6-digit code.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailParam, code: fullCode }),
      });

      if (res.ok) {
        setSuccess(true);
        setTimeout(() => router.replace("/dashboard"), 2000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || "Verification failed. Please try again.");
        setCode(["", "", "", "", "", ""]);
        inputRefs.current[0]?.focus();
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    setResending(true);
    setError("");

    try {
      await apiFetch("/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailParam }),
      });
      setResendCooldown(60);
    } catch {
      setError("Could not resend code. Please try again.");
    } finally {
      setResending(false);
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
            {success ? (
              <>
                <div className="flex justify-center mb-4">
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center"
                    style={{ background: "linear-gradient(135deg, oklch(0.45 0.2 145), oklch(0.55 0.2 160))" }}
                  >
                    <CheckCircle2 size={32} className="text-white" />
                  </div>
                </div>
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Email Verified!
                </h1>
                <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
                  Redirecting to your dashboard...
                </p>
              </>
            ) : (
              <>
                <div className="flex justify-center mb-4">
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center"
                    style={{ background: "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))" }}
                  >
                    <ShieldCheck size={32} className="text-white" />
                  </div>
                </div>
                <h1 className="text-2xl font-bold text-white tracking-tight">
                  Verify your email
                </h1>
                <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
                  We sent a 6-digit code to
                </p>
                <p className="text-sm font-semibold mt-1" style={{ color: "oklch(0.62 0.22 292)" }}>
                  {emailParam || "your email"}
                </p>
              </>
            )}
          </div>

          {/* Code Input */}
          {!success && (
            <div className="px-8 pb-8 pt-4">
              <div className="flex justify-center gap-3 mb-6" onPaste={handlePaste}>
                {code.map((digit, i) => (
                  <input
                    key={i}
                    ref={el => { inputRefs.current[i] = el; }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleInput(i, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    className="w-12 h-14 text-center text-xl font-bold rounded-xl outline-none transition-all"
                    style={{
                      background: "oklch(0.09 0.03 270)",
                      border: digit ? "2px solid oklch(0.62 0.22 292)" : "1px solid oklch(0.20 0.04 270)",
                      color: "white",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "oklch(0.62 0.22 292)";
                      e.target.style.boxShadow = "0 0 0 3px oklch(0.62 0.22 292 / 0.15)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = digit ? "oklch(0.62 0.22 292)" : "oklch(0.20 0.04 270)";
                      e.target.style.boxShadow = "none";
                    }}
                  />
                ))}
              </div>

              {error && (
                <div
                  className="p-3.5 rounded-xl text-xs font-semibold flex items-center gap-3 mb-4"
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
                onClick={() => handleVerify()}
                disabled={loading || code.some(d => !d)}
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
                    <ShieldCheck size={16} />
                    Verify Email
                    <ArrowRight size={16} />
                  </>
                )}
              </button>

              {/* Resend */}
              <div className="text-center mt-5">
                <button
                  onClick={handleResend}
                  disabled={resending || resendCooldown > 0}
                  className="text-xs font-semibold inline-flex items-center gap-2 transition-all hover:opacity-80 disabled:opacity-40"
                  style={{ color: "oklch(0.55 0.02 270)" }}
                >
                  <RefreshCw size={12} className={resending ? "animate-spin" : ""} />
                  {resendCooldown > 0
                    ? `Resend code in ${resendCooldown}s`
                    : "Didn't receive a code? Resend"
                  }
                </button>
              </div>

              {/* Back to login */}
              <div className="mt-6">
                <Link
                  href="/login"
                  className="block w-full text-center rounded-xl py-3 text-xs font-bold uppercase tracking-wider transition-all no-underline hover:opacity-90"
                  style={{
                    background: "oklch(0.15 0.03 270)",
                    border: "1px solid oklch(0.22 0.04 270)",
                    color: "oklch(0.70 0.02 270)",
                  }}
                >
                  Back to Login
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </AuthLayout>
  );
}
