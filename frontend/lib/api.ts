import { withBasePath } from "@/lib/base-path";

const RETRYABLE_STATUSES = new Set([404, 502, 503, 504]);

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
  
  // Internal API routes should go through our Next.js proxy
  // /admin/... -> /arni/proxy/admin/...
  // /auth/... -> /arni/proxy/auth/...
  
  const candidates = [
    withBasePath(`/proxy${normalizedPath}`)
  ];

  const uniqueCandidates = [...new Set(candidates)];
  let lastError: unknown;

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
      credentials: "same-origin",
    };
    
    const requestInit = isRetryableRead
      ? { ...requestInitBase, cache: "no-store" as RequestCache, redirect: "manual" as RequestRedirect }
      : requestInitBase;
      
    try {
      const response = await fetch(requestUrl, requestInit);
      if (response.ok) return response;

      const shouldRetry =
        isRetryableRead && RETRYABLE_STATUSES.has(response.status) &&
        index < uniqueCandidates.length - 1;

      if (!shouldRetry) {
        if (typeof window !== "undefined" && response.status === 401) {
          window.sessionStorage.removeItem("ariia_user");
          window.localStorage.removeItem("ariia_user");
          const loginPath = withBasePath("/login/");
          if (window.location.pathname !== loginPath) {
            window.location.href = loginPath;
          }
        }
        return response;
      }
    } catch (error) {
      lastError = error;
      if (!isRetryableRead || index === uniqueCandidates.length - 1) {
        break;
      }
    }
  }

  console.warn("API network request failed", { path: normalizedPath, method, tried: uniqueCandidates });
  throw lastError ?? new Error(`API request failed for ${normalizedPath}`);
}
