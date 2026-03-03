import { withBasePath } from "@/lib/base-path";

const RETRYABLE_STATUSES = new Set([404, 502, 503, 504]);

// ─── Token Refresh Logic ──────────────────────────────────────────────────
let _refreshPromise: Promise<boolean> | null = null;

async function _tryRefreshToken(): Promise<boolean> {
  // Deduplicate concurrent refresh attempts
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      const res = await fetch(withBasePath("/proxy/auth/refresh"), {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        // Update session storage with refreshed user info
        if (data.user && typeof window !== "undefined") {
          window.sessionStorage.setItem("ariia_user", JSON.stringify(data.user));
          window.dispatchEvent(new Event("ariia:session-updated"));
        }
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      _refreshPromise = null;
    }
  })();
  return _refreshPromise;
}

function normalizePath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

function isRetryableMethod(method: string) {
  return method === "GET" || method === "HEAD";
}

function readCookie(name: string) {
  if (typeof document === "undefined") return "";
  const pattern = `${name}=`;
  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(pattern));
  if (!match) return "";
  return decodeURIComponent(match.slice(pattern.length));
}

function withCacheBust(url: string, enabled: boolean) {
  if (!enabled) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}__ariia_cb=${Date.now()}`;
}

export async function apiFetch(path: string, init?: RequestInit) {
  const normalizedPath = normalizePath(path);
  const method = (init?.method || "GET").toUpperCase();
  const isRetryableRead = isRetryableMethod(method);
  
  // Routes starting with /api/ are Next.js API routes (with cookie→bearer conversion).
  // All other routes go through the Next.js rewrite proxy at /proxy/...
  const isApiRoute = normalizedPath.startsWith("/api/");
  const candidates = [
    isApiRoute
      ? withBasePath(normalizedPath)
      : withBasePath(`/proxy${normalizedPath}`)
  ];

  const uniqueCandidates = [...new Set(candidates)];
  let lastError: any;

  for (let index = 0; index < uniqueCandidates.length; index += 1) {
    const url = uniqueCandidates[index];
    const requestUrl = withCacheBust(url, isRetryableRead && index === 0);
    const headers = new Headers(init?.headers || {});
    
    if (!isRetryableRead && typeof window !== "undefined") {
      const csrf = readCookie("ariia_csrf_token");
      if (csrf && !headers.has("x-csrf-token")) {
        headers.set("x-csrf-token", csrf);
      }
      if (!headers.has("content-type") && init?.body && !(init.body instanceof FormData)) {
        headers.set("content-type", "application/json");
      }
    }
    
    const requestInitBase: RequestInit = {
      ...init,
      headers,
      credentials: "same-origin", // Keep same-origin for strict security
    };
    
    const requestInit = isRetryableRead
      ? { ...requestInitBase, cache: "no-store" as RequestCache, redirect: "manual" as RequestRedirect }
      : requestInitBase;
      
    try {
      const response = await fetch(requestUrl, requestInit);
      
      if (response.ok) return response;

      if (!isRetryableRead || !RETRYABLE_STATUSES.has(response.status)) {
        // Auto-refresh on 401 (except for auth endpoints themselves)
        if (
          typeof window !== "undefined" &&
          response.status === 401 &&
          !normalizedPath.startsWith("/auth/login") &&
          !normalizedPath.startsWith("/auth/refresh") &&
          !normalizedPath.startsWith("/auth/register")
        ) {
          const refreshed = await _tryRefreshToken();
          if (refreshed) {
            // Retry the original request with new cookies
            try {
              const retryResponse = await fetch(requestUrl, requestInit);
              if (retryResponse.ok || retryResponse.status !== 401) {
                return retryResponse;
              }
            } catch {
              // Fall through to redirect
            }
          }
          // Refresh failed or retry still 401 → redirect to login
          window.sessionStorage.removeItem("ariia_user");
          window.localStorage.removeItem("ariia_user");
          const loginPath = withBasePath("/login");
          if (
            window.location.pathname !== loginPath &&
            !window.location.pathname.includes("/register") &&
            !window.location.pathname.includes("/forgot-password") &&
            !window.location.pathname.includes("/reset-password") &&
            !window.location.pathname.includes("/verify-email") &&
            !window.location.pathname.includes("/pricing")
          ) {
            window.location.href = loginPath;
          }
        }
        return response;
      }
    } catch (error: any) {
      lastError = error;
      if (index < uniqueCandidates.length - 1) {
        continue;
      }
      break;
    }
  }

  console.error("API network request failed permanently", { 
    path: normalizedPath, 
    method, 
    tried: uniqueCandidates,
    lastError: lastError?.message || lastError
  });
  throw lastError ?? new Error(`API request failed for ${normalizedPath}`);
}
