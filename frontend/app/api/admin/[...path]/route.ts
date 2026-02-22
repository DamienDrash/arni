import { NextRequest } from "next/server";
import { proxyRequest, validateCsrf } from "@/lib/server/proxy";

function buildTargetUrl(path: string[], request: NextRequest) {
  const base = (process.env.GATEWAY_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
  const pathname = path.join("/");
  const query = request.nextUrl.search;
  return `${base}/admin/${pathname}${query}`;
}

async function proxy(request: NextRequest, path: string[]) {
  try {
    const csrfFailure = validateCsrf(request);
    if (csrfFailure) return csrfFailure;
    const targetUrl = buildTargetUrl(path, request);
    return await proxyRequest(request, targetUrl);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown proxy error";
    return Response.json(
      {
        error: "Gateway proxy failed",
        detail: message,
        target: buildTargetUrl(path, request),
      },
      { status: 502 },
    );
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
