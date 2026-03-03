"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { Shield, ShieldCheck, ShieldOff, Key, Copy, CheckCircle, AlertTriangle, Eye, EyeOff, RefreshCw } from "lucide-react";

type MfaState = "disabled" | "setup" | "verify" | "enabled";

export default function SecuritySettingsClient() {
  // MFA State
  const [mfaState, setMfaState] = useState<MfaState>("disabled");
  const [mfaLoading, setMfaLoading] = useState(true);
  const [mfaSecret, setMfaSecret] = useState("");
  const [mfaUri, setMfaUri] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [mfaError, setMfaError] = useState("");
  const [mfaPassword, setMfaPassword] = useState("");
  const [showBackupCodes, setShowBackupCodes] = useState(false);

  // Disable MFA
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableError, setDisableError] = useState("");

  // Password Change
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [pwError, setPwError] = useState("");
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwLoading, setPwLoading] = useState(false);

  // Copied state
  const [copied, setCopied] = useState(false);

  // Password strength
  const hasMinLength = newPassword.length >= 8;
  const hasUppercase = /[A-Z]/.test(newPassword);
  const hasLowercase = /[a-z]/.test(newPassword);
  const hasDigit = /\d/.test(newPassword);
  const strengthChecks = [hasMinLength, hasUppercase, hasLowercase, hasDigit].filter(Boolean).length;

  useEffect(() => {
    checkMfaStatus();
  }, []);

  async function checkMfaStatus() {
    try {
      const res = await apiFetch("/auth/me");
      if (res.ok) {
        const data = await res.json();
        setMfaState(data.mfa_enabled ? "enabled" : "disabled");
      }
    } catch {
      // ignore
    } finally {
      setMfaLoading(false);
    }
  }

  async function startMfaSetup() {
    if (!mfaPassword) {
      setMfaError("Please enter your password.");
      return;
    }
    setMfaError("");
    setMfaLoading(true);
    try {
      const res = await apiFetch("/auth/mfa/setup", {
        method: "POST",
        body: JSON.stringify({ password: mfaPassword }),
      });
      if (res.ok) {
        const data = await res.json();
        setMfaSecret(data.secret);
        setMfaUri(data.uri);
        setMfaState("verify");
      } else {
        const data = await res.json().catch(() => ({}));
        setMfaError(data.detail || "Failed to start MFA setup.");
      }
    } catch {
      setMfaError("Network error.");
    } finally {
      setMfaLoading(false);
    }
  }

  async function verifyMfaSetup() {
    if (mfaCode.length !== 6) {
      setMfaError("Please enter a 6-digit code.");
      return;
    }
    setMfaError("");
    setMfaLoading(true);
    try {
      const res = await apiFetch("/auth/mfa/verify-setup", {
        method: "POST",
        body: JSON.stringify({ code: mfaCode }),
      });
      if (res.ok) {
        const data = await res.json();
        setBackupCodes(data.backup_codes || []);
        setShowBackupCodes(true);
        setMfaState("enabled");
      } else {
        const data = await res.json().catch(() => ({}));
        setMfaError(data.detail || "Invalid code.");
      }
    } catch {
      setMfaError("Network error.");
    } finally {
      setMfaLoading(false);
    }
  }

  async function disableMfa() {
    if (!disablePassword || disableCode.length !== 6) {
      setDisableError("Password and 6-digit code required.");
      return;
    }
    setDisableError("");
    try {
      const res = await apiFetch("/auth/mfa/disable", {
        method: "POST",
        body: JSON.stringify({ password: disablePassword, code: disableCode }),
      });
      if (res.ok) {
        setMfaState("disabled");
        setDisablePassword("");
        setDisableCode("");
        setBackupCodes([]);
      } else {
        const data = await res.json().catch(() => ({}));
        setDisableError(data.detail || "Failed to disable MFA.");
      }
    } catch {
      setDisableError("Network error.");
    }
  }

  async function regenerateBackupCodes() {
    try {
      const res = await apiFetch("/auth/mfa/regenerate-backup-codes", { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setBackupCodes(data.backup_codes || []);
        setShowBackupCodes(true);
      }
    } catch {
      // ignore
    }
  }

  async function changePassword() {
    setPwError("");
    setPwSuccess(false);
    if (strengthChecks < 4) {
      setPwError("Password does not meet requirements.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwError("Passwords do not match.");
      return;
    }
    setPwLoading(true);
    try {
      const res = await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (res.ok) {
        setPwSuccess(true);
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        const data = await res.json().catch(() => ({}));
        setPwError(data.detail || "Failed to change password.");
      }
    } catch {
      setPwError("Network error.");
    } finally {
      setPwLoading(false);
    }
  }

  function copyBackupCodes() {
    navigator.clipboard.writeText(backupCodes.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="min-h-screen bg-[#0a0b0f] p-6 md:p-10">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <h1 className="text-2xl font-bold text-[#e8e9ed]">Security Settings</h1>
          <p className="text-[#8b8d9a] mt-1">Manage your password and two-factor authentication.</p>
        </div>

        {/* ─── Password Change ─── */}
        <div className="bg-[#12131a] border border-[#252630] rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-[#6c5ce7]/10 flex items-center justify-center">
              <Key className="w-5 h-5 text-[#6c5ce7]" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[#e8e9ed]">Change Password</h2>
              <p className="text-sm text-[#8b8d9a]">Update your account password</p>
            </div>
          </div>

          <div className="space-y-3">
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Current password"
              className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors"
            />
            <div className="relative">
              <input
                type={showNewPassword ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="New password"
                className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors pr-12"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#5a5c6b] hover:text-[#8b8d9a]"
              >
                {showNewPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>

            {newPassword.length > 0 && (
              <div className="space-y-1.5">
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
                  <span className={hasMinLength ? "text-green-400" : "text-[#5a5c6b]"}>{hasMinLength ? "✓" : "○"} 8+ characters</span>
                  <span className={hasUppercase ? "text-green-400" : "text-[#5a5c6b]"}>{hasUppercase ? "✓" : "○"} Uppercase</span>
                  <span className={hasLowercase ? "text-green-400" : "text-[#5a5c6b]"}>{hasLowercase ? "✓" : "○"} Lowercase</span>
                  <span className={hasDigit ? "text-green-400" : "text-[#5a5c6b]"}>{hasDigit ? "✓" : "○"} Number</span>
                </div>
              </div>
            )}

            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
              className={`w-full px-4 py-3 bg-[#1a1b24] border rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none transition-colors ${
                confirmPassword.length > 0
                  ? newPassword === confirmPassword ? "border-green-500/50" : "border-red-500/50"
                  : "border-[#252630] focus:border-[#6c5ce7]"
              }`}
            />

            {pwError && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                <p className="text-sm text-red-300">{pwError}</p>
              </div>
            )}
            {pwSuccess && (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
                <p className="text-sm text-green-300">Password changed successfully.</p>
              </div>
            )}

            <button
              onClick={changePassword}
              disabled={pwLoading || strengthChecks < 4 || newPassword !== confirmPassword}
              className="px-6 py-2.5 bg-gradient-to-r from-[#6c5ce7] to-[#a855f7] text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            >
              {pwLoading ? "Changing..." : "Change Password"}
            </button>
          </div>
        </div>

        {/* ─── Two-Factor Authentication ─── */}
        <div className="bg-[#12131a] border border-[#252630] rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 rounded-lg bg-[#6c5ce7]/10 flex items-center justify-center">
              {mfaState === "enabled" ? (
                <ShieldCheck className="w-5 h-5 text-green-400" />
              ) : (
                <Shield className="w-5 h-5 text-[#6c5ce7]" />
              )}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-[#e8e9ed]">Two-Factor Authentication</h2>
              <p className="text-sm text-[#8b8d9a]">
                {mfaState === "enabled"
                  ? "2FA is active – your account is protected"
                  : "Add an extra layer of security to your account"}
              </p>
            </div>
            {mfaState === "enabled" && (
              <span className="ml-auto px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-full text-xs font-medium text-green-400">
                Active
              </span>
            )}
          </div>

          {/* MFA Disabled – Setup Start */}
          {mfaState === "disabled" && (
            <div className="space-y-3">
              <p className="text-sm text-[#8b8d9a]">
                Use an authenticator app (Google Authenticator, Authy, 1Password) to generate time-based one-time passwords for enhanced security.
              </p>
              <input
                type="password"
                value={mfaPassword}
                onChange={(e) => setMfaPassword(e.target.value)}
                placeholder="Enter your password to begin setup"
                className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors"
              />
              {mfaError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <p className="text-sm text-red-300">{mfaError}</p>
                </div>
              )}
              <button
                onClick={() => { setMfaState("setup"); startMfaSetup(); }}
                disabled={mfaLoading || !mfaPassword}
                className="px-6 py-2.5 bg-gradient-to-r from-[#6c5ce7] to-[#a855f7] text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                Enable 2FA
              </button>
            </div>
          )}

          {/* MFA Setup – Show Secret */}
          {mfaState === "setup" && (
            <div className="space-y-4 text-center">
              <p className="text-sm text-[#8b8d9a]">Loading setup...</p>
            </div>
          )}

          {/* MFA Verify – Enter Code */}
          {mfaState === "verify" && (
            <div className="space-y-4">
              <p className="text-sm text-[#8b8d9a]">
                Scan this QR code with your authenticator app, or enter the secret key manually:
              </p>

              {/* QR Code placeholder using URI */}
              <div className="bg-[#1a1b24] border border-[#252630] rounded-xl p-4 text-center">
                <div className="bg-white rounded-lg p-4 inline-block mb-3">
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(mfaUri)}`}
                    alt="MFA QR Code"
                    width={200}
                    height={200}
                    className="block"
                  />
                </div>
                <div className="mt-2">
                  <p className="text-xs text-[#5a5c6b] mb-1">Manual entry key:</p>
                  <code className="text-sm text-[#6c5ce7] font-mono bg-[#0a0b0f] px-3 py-1.5 rounded-lg inline-block break-all">
                    {mfaSecret}
                  </code>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[#8b8d9a] mb-1.5">Verification Code</label>
                <input
                  type="text"
                  inputMode="numeric"
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder="000000"
                  maxLength={6}
                  className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-[#6c5ce7] transition-colors text-center font-mono text-xl tracking-[0.4em]"
                />
              </div>

              {mfaError && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                  <p className="text-sm text-red-300">{mfaError}</p>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={() => { setMfaState("disabled"); setMfaCode(""); setMfaError(""); setMfaPassword(""); }}
                  className="px-6 py-2.5 border border-[#252630] text-[#8b8d9a] rounded-xl hover:bg-[#1a1b24] transition-colors text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={verifyMfaSetup}
                  disabled={mfaLoading || mfaCode.length !== 6}
                  className="flex-1 px-6 py-2.5 bg-gradient-to-r from-[#6c5ce7] to-[#a855f7] text-white font-semibold rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                >
                  {mfaLoading ? "Verifying..." : "Verify & Enable"}
                </button>
              </div>
            </div>
          )}

          {/* MFA Enabled */}
          {mfaState === "enabled" && (
            <div className="space-y-4">
              {/* Backup Codes Section */}
              {showBackupCodes && backupCodes.length > 0 && (
                <div className="bg-[#1a1b24] border border-yellow-500/20 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    <span className="text-sm font-semibold text-yellow-300">Save your backup codes</span>
                  </div>
                  <p className="text-xs text-[#8b8d9a] mb-3">
                    Store these codes in a safe place. Each code can only be used once. If you lose access to your authenticator app, you can use these to sign in.
                  </p>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    {backupCodes.map((code, i) => (
                      <div key={i} className="bg-[#0a0b0f] rounded-lg px-3 py-2 text-center">
                        <code className="text-sm font-mono text-[#e8e9ed]">{code}</code>
                      </div>
                    ))}
                  </div>
                  <button
                    onClick={copyBackupCodes}
                    className="flex items-center gap-2 px-4 py-2 border border-[#252630] rounded-lg text-sm text-[#8b8d9a] hover:bg-[#252630] transition-colors"
                  >
                    {copied ? <CheckCircle className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                    {copied ? "Copied!" : "Copy all codes"}
                  </button>
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={regenerateBackupCodes}
                  className="flex items-center gap-2 px-4 py-2.5 border border-[#252630] text-[#8b8d9a] rounded-xl hover:bg-[#1a1b24] transition-colors text-sm"
                >
                  <RefreshCw className="w-4 h-4" />
                  New Backup Codes
                </button>
              </div>

              {/* Disable MFA */}
              <div className="border-t border-[#252630] pt-4 mt-4">
                <h3 className="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
                  <ShieldOff className="w-4 h-4" />
                  Disable Two-Factor Authentication
                </h3>
                <div className="space-y-3">
                  <input
                    type="password"
                    value={disablePassword}
                    onChange={(e) => setDisablePassword(e.target.value)}
                    placeholder="Your password"
                    className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-red-500/50 transition-colors"
                  />
                  <input
                    type="text"
                    inputMode="numeric"
                    value={disableCode}
                    onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="6-digit code"
                    maxLength={6}
                    className="w-full px-4 py-3 bg-[#1a1b24] border border-[#252630] rounded-xl text-[#e8e9ed] placeholder-[#5a5c6b] focus:outline-none focus:border-red-500/50 transition-colors font-mono"
                  />
                  {disableError && (
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                      <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
                      <p className="text-sm text-red-300">{disableError}</p>
                    </div>
                  )}
                  <button
                    onClick={disableMfa}
                    disabled={!disablePassword || disableCode.length !== 6}
                    className="px-6 py-2.5 bg-red-500/10 border border-red-500/30 text-red-400 font-semibold rounded-xl hover:bg-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                  >
                    Disable 2FA
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
