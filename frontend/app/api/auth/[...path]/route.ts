import { NextRequest } from "next/server";
import {
  clearAuthCookieHeaders,
  proxyRequest,
  setCsrfCookieHeaders,
  setAuthCookieHeaders,
  validateCsrf,
} from "@/lib/server/proxy";

function buildTargetUrl(path: string[], request: NextRequest) {
  const base = (process.env.GATEWAY_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const pathname = path.join("/");
  const query = request.nextUrl.search;
  return `${base}/auth/${pathname}${query}`;
}

async function proxy(request: NextRequest, path: string[]) {
  try {
    const first = path[0] || "";
    const isPublicAuthWrite =
      request.method !== "GET" && (first === "login" || first === "register" || first === "logout");
    if (!isPublicAuthWrite) {
      const csrfFailure = validateCsrf(request);
      if (csrfFailure) return csrfFailure;
    }

    if (path.length === 1 && path[0] === "logout") {
      return new Response(null, { status: 204, headers: clearAuthCookieHeaders() });
    }
    const targetUrl = buildTargetUrl(path, request);
    const response = await proxyRequest(request, targetUrl);

    const writesSessionCookie =
      request.method === "POST" &&
      (
        path[0] === "login" ||
        path[0] === "register" ||
        (path[0] === "users" && path[2] === "impersonate") ||
        (path[0] === "impersonation" && path[1] === "stop")
      );
    if (writesSessionCookie && response.ok) {
      const clone = response.clone();
      const payload = await clone.json().catch(() => ({}));
      const token = typeof payload?.access_token === "string" ? payload.access_token : "";
      if (token) {
        const headers = new Headers(response.headers);
        headers.append("set-cookie", setAuthCookieHeaders(token).get("set-cookie") || "");
        headers.append("set-cookie", setCsrfCookieHeaders().get("set-cookie") || "");
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers,
        });
      }
    }

    if (response.status === 401) {
      const headers = new Headers(response.headers);
      headers.append("set-cookie", clearAuthCookieHeaders().get("set-cookie") || "");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    return response;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown proxy error";
    return Response.json({ error: "Auth proxy failed", detail: message }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  return proxy(request, path);
}
