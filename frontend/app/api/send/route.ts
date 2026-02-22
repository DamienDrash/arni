import { NextRequest, NextResponse } from "next/server";

type SendPayload = { to?: string; text?: string };

function getBridgeUrl() {
  return (process.env.WHATSAPP_BRIDGE_SEND_URL || "").trim();
}

function legacyProxyEnabled() {
  return (process.env.NEXT_ENABLE_LEGACY_SEND_PROXY || "false").toLowerCase() === "true";
}

function isAuthorized(request: NextRequest) {
  const configured = (process.env.LEGACY_SEND_TOKEN || "").trim();
  if (!configured) return true;
  const header = request.headers.get("x-send-token") || "";
  return header === configured;
}

export async function POST(request: NextRequest) {
  if (!legacyProxyEnabled()) {
    return NextResponse.json(
      {
        error: "legacy_send_proxy_disabled",
        detail:
          "Legacy /api/send is disabled. Use backend channel delivery via gateway send_to_user/admin intervene.",
      },
      { status: 410 },
    );
  }

  if (!isAuthorized(request)) {
    return NextResponse.json({ error: "forbidden" }, { status: 403 });
  }

  const bridgeUrl = getBridgeUrl();
  if (!bridgeUrl) {
    return NextResponse.json(
      { error: "missing_bridge_url", detail: "WHATSAPP_BRIDGE_SEND_URL is not configured." },
      { status: 500 },
    );
  }

  let payload: SendPayload;
  try {
    payload = (await request.json()) as SendPayload;
  } catch {
    return NextResponse.json({ error: "invalid_payload" }, { status: 400 });
  }

  const to = String(payload.to || "").trim();
  const text = String(payload.text || "").trim();
  if (!to || !text) {
    return NextResponse.json({ error: "invalid_payload", detail: "Fields 'to' and 'text' are required." }, { status: 400 });
  }

  try {
    const upstream = await fetch(bridgeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to, text }),
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "bridge_unreachable" }, { status: 502 });
  }
}

export async function GET() {
  if (!legacyProxyEnabled()) {
    return NextResponse.json({ status: "disabled" });
  }
  return NextResponse.json({ status: "enabled", bridge: getBridgeUrl() || "unconfigured" });
}

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 204,
    headers: {
      Allow: "POST,GET,OPTIONS",
    },
  });
}
