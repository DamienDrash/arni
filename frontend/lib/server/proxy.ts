import { NextRequest } from "next/server";
import { randomUUID } from "crypto";

export const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export const AUTH_COOKIE = "arni_access_token";
export const CSRF_COOKIE = "arni_csrf_token";

export function isMutatingMethod(method: string) {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export function applyAuthFromCookie(request: NextRequest, headers: Headers) {
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (token && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${token}`);
  }
}

export function sanitizeUpstreamHeaders(headers: Headers) {
  headers.delete("host");
  for (const h of HOP_BY_HOP_HEADERS) headers.delete(h);
}

export function validateCsrf(request: NextRequest) {
  if (!isMutatingMethod(request.method)) return null;
  const csrfCookie = request.cookies.get(CSRF_COOKIE)?.value || "";
  const csrfHeader = request.headers.get("x-csrf-token") || "";
  if (!csrfCookie || !csrfHeader || csrfCookie !== csrfHeader) {
    return Response.json({ error: "csrf_validation_failed" }, { status: 403 });
  }
  return null;
}

export async function proxyRequest(request: NextRequest, targetUrl: string) {
  const headers = new Headers(request.headers);
  sanitizeUpstreamHeaders(headers);
  applyAuthFromCookie(request, headers);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    redirect: "follow",
  });

  const responseHeaders = new Headers(upstream.headers);
  for (const h of HOP_BY_HOP_HEADERS) responseHeaders.delete(h);

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export function clearAuthCookieHeaders() {
  const headers = new Headers();
  headers.append(
    "set-cookie",
    `${AUTH_COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`,
  );
  headers.append(
    "set-cookie",
    `${CSRF_COOKIE}=; Path=/; Max-Age=0; Secure; SameSite=Lax`,
  );
  return headers;
}

export function setAuthCookieHeaders(token: string) {
  const headers = new Headers();
  headers.append(
    "set-cookie",
    `${AUTH_COOKIE}=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; SameSite=Lax`,
  );
  return headers;
}

export function setCsrfCookieHeaders(value?: string) {
  const headers = new Headers();
  const csrfToken = value || randomUUID();
  headers.append(
    "set-cookie",
    `${CSRF_COOKIE}=${encodeURIComponent(csrfToken)}; Path=/; Secure; SameSite=Lax`,
  );
  return headers;
}
