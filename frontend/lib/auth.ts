export type AuthUser = {
  id: number;
  email: string;
  role: "system_admin" | "tenant_admin" | "tenant_user";
  tenant_id: number;
  tenant_slug: string;
  impersonation?: {
    active: boolean;
    actor_user_id?: number;
    actor_email?: string;
    actor_role?: string;
    actor_tenant_id?: number;
    actor_tenant_slug?: string;
    reason?: string;
    started_at?: string;
  };
};

const USER_KEYS = ["arni_user", "user"] as const;
const LEGACY_TOKEN_KEYS = ["arni_access_token", "access_token", "auth_token", "token"] as const;

export function getStoredToken(): string | null {
  return null;
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem("arni_user");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function storeSession(_token: string, user: AuthUser): void {
  if (typeof window === "undefined") return;
  void _token;
  window.sessionStorage.setItem("arni_user", JSON.stringify(user));
  for (const key of LEGACY_TOKEN_KEYS) {
    window.sessionStorage.removeItem(key);
    window.localStorage.removeItem(key);
  }
  for (const key of USER_KEYS) window.localStorage.removeItem(key);
  window.dispatchEvent(new Event("arni:session-updated"));
}

export function setStoredUser(user: AuthUser): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem("arni_user", JSON.stringify(user));
  window.localStorage.removeItem("arni_user");
  window.localStorage.removeItem("user");
  window.dispatchEvent(new Event("arni:session-updated"));
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  for (const key of LEGACY_TOKEN_KEYS) {
    window.sessionStorage.removeItem(key);
    window.localStorage.removeItem(key);
  }
  for (const key of USER_KEYS) window.sessionStorage.removeItem(key);
  for (const key of USER_KEYS) window.localStorage.removeItem(key);
  window.dispatchEvent(new Event("arni:session-updated"));
  void fetch("/arni/api/auth/logout", { method: "POST" }).catch(() => {});
}
