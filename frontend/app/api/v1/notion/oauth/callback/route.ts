import { NextRequest, NextResponse } from "next/server";

/**
 * Notion OAuth Callback Handler
 *
 * Notion redirects here after user authorizes the integration.
 * This is a GET endpoint that receives `code` and `state` query parameters
 * from Notion's OAuth flow, then redirects to the /knowledge page
 * where the frontend handles the token exchange.
 *
 * Redirect URI configured in Notion: https://www.ariia.ai/api/v1/notion/oauth/callback
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");

  // Determine the correct external origin from headers (behind reverse proxy)
  const proto = request.headers.get("x-forwarded-proto") || "https";
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "www.ariia.ai";
  const baseUrl = `${proto}://${host}`;

  // Build the redirect URL to the knowledge page
  const redirectUrl = new URL("/knowledge", baseUrl);

  if (error) {
    redirectUrl.searchParams.set("notion_error", error);
  } else if (code) {
    redirectUrl.searchParams.set("code", code);
    if (state) {
      redirectUrl.searchParams.set("state", state);
    }
    redirectUrl.searchParams.set("notion_callback", "true");
  } else {
    redirectUrl.searchParams.set("notion_error", "no_code");
  }

  return NextResponse.redirect(redirectUrl.toString());
}
