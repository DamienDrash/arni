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
  const adminSuffix = normalizedPath.startsWith("/admin/")
    ? normalizedPath.slice("/admin".length)
    : normalizedPath === "/admin"
      ? ""
      : normalizedPath;
  const authSuffix = normalizedPath.startsWith("/auth/")
    ? normalizedPath.slice("/auth".length)
    : normalizedPath === "/auth"
      ? ""
      : normalizedPath;

  const isAdminPath = normalizedPath === "/admin" || normalizedPath.startsWith("/admin/");
  const isAuthPath = normalizedPath === "/auth" || normalizedPath.startsWith("/auth/");
  const candidates = isAdminPath
    ? [`/ariia/api/admin${adminSuffix}`]
    : isAuthPath
      ? [`/ariia/api/auth${authSuffix}`]
      : [normalizedPath];

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
      const contentType = response.headers.get("content-type") || "";
      const isHtml = contentType.includes("text/html");
      const isUnexpectedHtml = response.ok && normalizedPath.startsWith("/admin/") && isHtml;
      if (response.ok && !isUnexpectedHtml) return response;

      const shouldFallbackByStatus =
        response.status === 404 || response.status === 405;

      const shouldRetry =
        (
          (isRetryableRead && (RETRYABLE_STATUSES.has(response.status) || isUnexpectedHtml)) ||
          shouldFallbackByStatus
        ) &&
        index < uniqueCandidates.length - 1;

      if (!shouldRetry) {
        if (typeof window !== "undefined" && response.status === 401) {
          window.sessionStorage.removeItem("ariia_user");
          window.localStorage.removeItem("ariia_user");
          window.sessionStorage.removeItem("access_token");
          window.sessionStorage.removeItem("auth_token");
          window.sessionStorage.removeItem("token");
          window.localStorage.removeItem("access_token");
          window.localStorage.removeItem("auth_token");
          window.localStorage.removeItem("token");
          const loginPath = withBasePath("/login");
          const registerPath = withBasePath("/register");
          if (window.location.pathname !== loginPath && window.location.pathname !== registerPath) {
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
