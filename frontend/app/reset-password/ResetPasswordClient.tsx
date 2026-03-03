"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Lock, Loader2, ArrowRight, ArrowLeft, KeyRound, Eye, EyeOff, CheckCircle2, Check, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import AuthLayout from "@/components/landing/AuthLayout";
import AriiaLogo from "@/components/landing/AriiaLogo";

function PasswordStrength({ password }: { password: string }) {
  const checks = useMemo(() => [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "One uppercase letter", met: /[A-Z]/.test(password) },
    { label: "One lowercase letter", met: /[a-z]/.test(password) },
    { label: "One digit", met: /\d/.test(password) },
  ], [password]);

  const score = checks.filter(c => c.met).length;
  const barColor = score <= 1 ? "oklch(0.60 0.2 25)" : score <= 2 ? "oklch(0.70 0.18 60)" : score <= 3 ? "oklch(0.70 0.15 90)" : "oklch(0.65 0.2 145)";

  if (!password) return null;

  return (
    <div className="mt-2 space-y-2">
      <div className="flex gap-1">
        {[0,1,2,3].map(i => (
          <div
            key={i}
            className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{ background: i < score ? barColor : "oklch(0.20 0.04 270)" }}
          />
        ))}
      </div>
      <div className="grid grid-cols-2 gap-1">
        {checks.map((c, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {c.met ? <Check size={10} style={{ color: "oklch(0.65 0.2 145)" }} /> : <X size={10} style={{ color: "oklch(0.45 0.02 270)" }} />}
            <span className="text-[10px]" style={{ color: c.met ? "oklch(0.65 0.2 145)" : "oklch(0.45 0.02 270)" }}>{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ResetPasswordClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const emailParam = searchParams.get("email") || "";

  const [code, setCode] = useState(["", "", "", "", "", ""]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => { inputRefs.current[0]?.focus(); }, []);

  const handleInput = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    const newCode = [...code];
    newCode[index] = value.slice(-1);
    setCode(newCode);
    if (value && index < 5) inputRefs.current[index + 1]?.focus();
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !code[index] && index > 0) inputRefs.current[index - 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pasted.length === 6) {
      setCode(pasted.split(""));
      inputRefs.current[5]?.focus();
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const fullCode = code.join("");
    if (fullCode.length !== 6) { setError("Please enter the complete 6-digit code."); return; }
    if (newPassword !== confirmPassword) { setError("Passwords do not match."); return; }

    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailParam, code: fullCode, new_password: newPassword }),
      });

      if (res.ok) {
        setSuccess(true);
        setTimeout(() => router.replace("/login"), 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail || "Reset failed. Please try again.");
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

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
      <div className="w-full max-w-md">
        <div
          className="rounded-2xl overflow-hidden shadow-2xl"
          style={{ background: "oklch(0.12 0.03 270)", border: "1px solid oklch(0.20 0.04 270)" }}
        >
          {/* Header */}
          <div
            className="px-8 pt-10 pb-8 text-center"
            style={{ background: "linear-gradient(135deg, oklch(0.14 0.06 292 / 0.5), oklch(0.10 0.03 270))" }}
          >
            <div className="flex justify-center mb-5"><AriiaLogo variant="full" height={40} /></div>
            <div className="flex justify-center mb-4">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center"
                style={{ background: success ? "linear-gradient(135deg, oklch(0.45 0.2 145), oklch(0.55 0.2 160))" : "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))" }}
              >
                {success ? <CheckCircle2 size={32} className="text-white" /> : <KeyRound size={32} className="text-white" />}
              </div>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              {success ? "Password Reset!" : "Reset your password"}
            </h1>
            <p className="text-sm mt-2" style={{ color: "oklch(0.55 0.02 270)" }}>
              {success ? "Redirecting to login..." : `Enter the code sent to ${emailParam || "your email"}`}
            </p>
          </div>

          {/* Form */}
          {!success && (
            <div className="px-8 pb-8 pt-4">
              <form onSubmit={handleSubmit} className="space-y-5">
                {/* Code input */}
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-widest ml-1 block mb-2" style={{ color: "oklch(0.50 0.02 270)" }}>
                    Reset Code
                  </label>
                  <div className="flex justify-center gap-3" onPaste={handlePaste}>
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
                        onFocus={(e) => { e.target.style.borderColor = "oklch(0.62 0.22 292)"; e.target.style.boxShadow = "0 0 0 3px oklch(0.62 0.22 292 / 0.15)"; }}
                        onBlur={(e) => { e.target.style.borderColor = digit ? "oklch(0.62 0.22 292)" : "oklch(0.20 0.04 270)"; e.target.style.boxShadow = "none"; }}
                      />
                    ))}
                  </div>
                </div>

                {/* New password */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                    New Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                    <input
                      type={showPwd ? "text" : "password"}
                      required
                      className="w-full rounded-xl pl-11 pr-12 py-3.5 text-white outline-none transition-all text-sm"
                      style={inputStyle}
                      placeholder="New secure password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                    />
                    <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3.5 top-1/2 -translate-y-1/2" style={{ color: "oklch(0.45 0.02 270)" }} tabIndex={-1}>
                      {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  <PasswordStrength password={newPassword} />
                </div>

                {/* Confirm password */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold uppercase tracking-widest ml-1" style={{ color: "oklch(0.50 0.02 270)" }}>
                    Confirm Password
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2" size={18} style={{ color: "oklch(0.45 0.02 270)" }} />
                    <input
                      type="password"
                      required
                      className="w-full rounded-xl pl-11 pr-4 py-3.5 text-white outline-none transition-all text-sm"
                      style={inputStyle}
                      placeholder="Confirm new password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                    />
                  </div>
                  {confirmPassword && newPassword !== confirmPassword && (
                    <p className="text-[10px] mt-1" style={{ color: "oklch(0.60 0.2 25)" }}>Passwords do not match</p>
                  )}
                </div>

                {error && (
                  <div className="p-3.5 rounded-xl text-xs font-semibold flex items-center gap-3" style={{ background: "oklch(0.25 0.12 25 / 0.15)", border: "1px solid oklch(0.55 0.2 25 / 0.3)", color: "oklch(0.70 0.15 25)" }}>
                    <div className="w-2 h-2 rounded-full animate-pulse flex-shrink-0" style={{ background: "oklch(0.60 0.2 25)" }} />
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading || code.some(d => !d) || !newPassword || newPassword !== confirmPassword}
                  className="w-full rounded-xl py-4 font-bold uppercase tracking-wider text-xs flex items-center justify-center gap-3 transition-all active:scale-[0.98] disabled:opacity-50"
                  style={{ background: "linear-gradient(135deg, oklch(0.55 0.25 292), oklch(0.50 0.22 280))", color: "white", boxShadow: "0 4px 20px oklch(0.55 0.25 292 / 0.3)" }}
                >
                  {loading ? <Loader2 className="animate-spin" size={18} /> : (
                    <><KeyRound size={16} /> Reset Password <ArrowRight size={16} /></>
                  )}
                </button>
              </form>

              <div className="mt-6">
                <Link
                  href="/login"
                  className="flex items-center justify-center gap-2 w-full text-center rounded-xl py-3 text-xs font-bold uppercase tracking-wider transition-all no-underline hover:opacity-90"
                  style={{ background: "oklch(0.15 0.03 270)", border: "1px solid oklch(0.22 0.04 270)", color: "oklch(0.70 0.02 270)" }}
                >
                  <ArrowLeft size={14} /> Back to Login
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </AuthLayout>
  );
}
