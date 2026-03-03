"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { storeSession } from "@/lib/auth";
import { withBasePath } from "@/lib/base-path";
import { Eye, EyeOff, CheckCircle, AlertTriangle, Users } from "lucide-react";

export default function AcceptInvitationClient() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Password strength
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasDigit = /\d/.test(password);
  const passwordsMatch = password === confirmPassword && password.length > 0;
  const strengthChecks = [hasMinLength, hasUppercase, hasLowercase, hasDigit].filter(Boolean).length;

  useEffect(() => {
    if (!token) {
      setError("Invalid invitation link. Please check the link from your email.");
    }
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (strengthChecks < 4) {
      setError("Please meet all password requirements.");
      return;
    }
    if (!passwordsMatch) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const res = await apiFetch("/auth/accept-invitation", {
        method: "POST",
        body: JSON.stringify({ token, password, full_name: fullName }),
      });

      if (res.ok) {
        const data = await res.json();
        storeSession(data.access_token, data.user);
        setSuccess(true);
        setTimeout(() => router.push(withBasePath("/dashboard")), 2000);
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Failed to accept invitation. The link may be expired.");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0b0f] px-4">
        <div className="w-full max-w-md text-center">
          <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-8 h-8 text-green-400" />
          </div>
          <h1 className="text-2xl font-bold text-[#e8e9ed] mb-2">Welcome to the team!</h1>
          <p className="text-[#8b8d9a]">Your account has been created. Redirecting to dashboard...</p>
        </div>
      </div>
    );
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
              <Users className="w-5 h-5 text-[#6c5ce7]" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#e8e9ed]">Accept Invitation</h1>
              <p className="text-sm text-[#8b8d9a]">Create your account to join the team</p>
            </div>
          </div>

          {!token ? (
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

              <div>
                <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Full Name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="John Doe"
                  className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="Create a strong password"
                    className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors pr-12"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5a5c6b] hover:text-[#8b8d9a]"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>

                {/* Strength indicator */}
                {password.length > 0 && (
                  <div className="mt-2 space-y-1.5">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4].map((i) => (
                        <div
                          key={i}
                          className={`h-1 flex-1 rounded-full transition-colors ${
                            i <= strengthChecks
                              ? strengthChecks <= 2 ? "bg-red-400" : strengthChecks === 3 ? "bg-yellow-400" : "bg-green-400"
                              : "bg-[#252630]"
                          }`}
                        />
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-1 text-xs">
                      <span className={hasMinLength ? "text-green-400" : "text-[#5a5c6b]"}>
                        {hasMinLength ? "✓" : "○"} 8+ characters
                      </span>
                      <span className={hasUppercase ? "text-green-400" : "text-[#5a5c6b]"}>
                        {hasUppercase ? "✓" : "○"} Uppercase
                      </span>
                      <span className={hasLowercase ? "text-green-400" : "text-[#5a5c6b]"}>
                        {hasLowercase ? "✓" : "○"} Lowercase
                      </span>
                      <span className={hasDigit ? "text-green-400" : "text-[#5a5c6b]"}>
                        {hasDigit ? "✓" : "○"} Number
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  placeholder="Confirm your password"
                  className={`w-full px-4 py-3 bg-[#1a1b24] border rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none transition-colors ${
                    confirmPassword.length > 0
                      ? passwordsMatch ? "border-green-500/50" : "border-red-500/50"
                      : "border-[#252630] focus:border-[#6c5ce7]"
                  }`}
                />
              </div>

              <button
                type="submit"
                disabled={loading || strengthChecks < 4 || !passwordsMatch}
                className="w-full py-3 bg-gradient-to-r from-[#6c5ce7] to-[#a855f7] text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? "Creating account..." : "Accept & Create Account"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
