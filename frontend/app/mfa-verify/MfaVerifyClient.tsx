"use client";

import { useState, useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import { withBasePath } from "@/lib/base-path";
import { Shield, AlertTriangle, KeyRound } from "lucide-react";

export default function MfaVerifyClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const challengeToken = searchParams.get("token") || "";
  const userId = searchParams.get("user_id") || "";

  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [useBackupCode, setUseBackupCode] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!challengeToken || !userId) {
      setError("Invalid MFA challenge. Please log in again.");
    }
    inputRef.current?.focus();
  }, [challengeToken, userId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!challengeToken || !userId || !code.trim()) return;

    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/mfa/verify", {
        method: "POST",
        body: JSON.stringify({
          mfa_challenge_token: challengeToken,
          code: code.trim(),
          user_id: parseInt(userId),
        }),
      });

      if (res.ok) {
        const data = await res.json();
        storeSession(data.access_token, data.user);
        router.push(withBasePath("/dashboard"));
      } else {
        const data = await res.json().catch(() => ({}));
        if (res.status === 410) {
          setError("MFA challenge expired. Please log in again.");
          setTimeout(() => router.push(withBasePath("/login")), 2000);
        } else {
          setError(data.detail || "Invalid code. Please try again.");
        }
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0b0f] px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#6c5ce7] to-[#a855f7] flex items-center justify-center">
            <span className="text-white font-extrabold text-lg">A</span>
          </div>
          <span className="text-[#e8e9ed] text-2xl font-bold tracking-wider">ARIIA</span>
        </div>

        {/* Card */}
        <div className="bg-[#12131a] border border-[#252630] rounded-2xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-lg bg-[#6c5ce7]/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-[#6c5ce7]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#e8e9ed]">Two-Factor Authentication</h1>
              <p className="text-sm text-[#8b8d9a]">
                {useBackupCode ? "Enter a backup code" : "Enter the code from your authenticator app"}
              </p>
            </div>
          </div>

          {(!challengeToken || !userId) ? (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <p className="text-sm text-red-300">{error}</p>
                </div>
              )}

              {useBackupCode ? (
                <div>
                  <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Backup Code</label>
                  <input
                    ref={inputRef}
                    type="text"
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    placeholder="XXXX-XXXX"
                    maxLength={9}
                    className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors text-center font-mono text-lg tracking-wider"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Authentication Code</label>
                  <input
                    ref={inputRef}
                    type="text"
                    inputMode="numeric"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="000000"
                    maxLength={6}
                    autoComplete="one-time-code"
                    className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors text-center font-mono text-2xl tracking-[0.5em]"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={loading || code.trim().length < 6}
                className="w-full py-3 bg-gradient-to-r from-[#6c5ce7] to-[#a855f7] text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Verifying..." : "Verify"}
              </button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setUseBackupCode(!useBackupCode);
                    setCode("");
                    setError("");
                  }}
                  className="text-sm text-[#6c5ce7] hover:text-[#a855f7] transition-colors inline-flex items-center gap-1.5"
                >
                  <KeyRound className="w-3.5 h-3.5" />
                  {useBackupCode ? "Use authenticator app instead" : "Use a backup code instead"}
                </button>
              </div>

              <div className="text-center">
                <button
                  type="button"
                  onClick={() => router.push(withBasePath("/login"))}
                  className="text-sm text-[#5a5c6b] hover:text-[#8b8d9a] transition-colors"
                >
                  Back to login
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
