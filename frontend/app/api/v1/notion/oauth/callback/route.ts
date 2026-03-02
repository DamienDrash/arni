import { NextRequest, NextResponse } from "next/server";

/**
 * Notion OAuth Callback Handler (Popup Mode)
 *
 * Notion redirects here after user authorizes the integration.
 * This endpoint renders a small HTML page that:
 * 1. Sends the OAuth code to the parent/opener window via postMessage
 * 2. Closes the popup automatically
 *
 * Redirect URI configured in Notion: https://www.ariia.ai/api/v1/notion/oauth/callback
 */
export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get("code") || "";
  const state = searchParams.get("state") || "";
  const error = searchParams.get("error") || "";

  // Determine the correct external origin from headers (behind reverse proxy)
  const proto = request.headers.get("x-forwarded-proto") || "https";
  const host = request.headers.get("x-forwarded-host") || request.headers.get("host") || "www.ariia.ai";
  const origin = `${proto}://${host}`;

  const html = `<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <title>Notion-Verbindung</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; margin: 0;
      background: #0a0a0f; color: #e0e0e0;
    }
    .container { text-align: center; padding: 2rem; }
    .spinner {
      width: 36px; height: 36px; border: 3px solid #333;
      border-top-color: #6c5ce7; border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 0 auto 1rem;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .error { color: #e74c3c; }
    p { font-size: 14px; opacity: 0.7; }
  </style>
</head>
<body>
  <div class="container">
    <div class="spinner" id="spinner"></div>
    <p id="status">Verbindung wird hergestellt…</p>
  </div>
  <script>
    (function() {
      var code = ${JSON.stringify(code)};
      var state = ${JSON.stringify(state)};
      var error = ${JSON.stringify(error)};
      var origin = ${JSON.stringify(origin)};

      if (error) {
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('status').className = 'error';
        document.getElementById('status').textContent = 'Autorisierung fehlgeschlagen: ' + error;
        // Still try to notify parent
        if (window.opener) {
          window.opener.postMessage({ type: 'notion_oauth_callback', error: error }, origin);
        }
        setTimeout(function() { window.close(); }, 3000);
        return;
      }

      if (code && window.opener) {
        // Send code to parent window
        window.opener.postMessage({
          type: 'notion_oauth_callback',
          code: code,
          state: state
        }, origin);
        document.getElementById('status').textContent = 'Erfolgreich autorisiert! Fenster schließt sich…';
        setTimeout(function() { window.close(); }, 1000);
      } else if (code && !window.opener) {
        // Fallback: redirect to knowledge page if no opener (e.g. popup blocked)
        window.location.href = origin + '/knowledge?code=' + encodeURIComponent(code) + '&state=' + encodeURIComponent(state) + '&notion_callback=true';
      } else {
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('status').className = 'error';
        document.getElementById('status').textContent = 'Kein Autorisierungscode erhalten.';
        setTimeout(function() { window.close(); }, 3000);
      }
    })();
  </script>
</body>
</html>`;

  return new NextResponse(html, {
    status: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}
