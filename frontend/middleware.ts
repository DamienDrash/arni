import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware for SEO-critical redirects:
 * 1. Enforce www.ariia.ai as canonical domain (redirect non-www)
 * 2. Enforce HTTPS
 * 3. Remove trailing slashes
 */
export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const host = request.headers.get("host") || "";

  // 1. Redirect non-www to www (only for ariia.ai domain)
  if (host === "ariia.ai") {
    const url = new URL(`https://www.ariia.ai${pathname}${search}`);
    return NextResponse.redirect(url, 301);
  }

  // 2. Redirect old /ariia/* paths
  if (pathname.startsWith("/ariia/") || pathname === "/ariia") {
    const newPath = pathname.replace(/^\/ariia/, "") || "/";
    const url = new URL(`https://www.ariia.ai${newPath}${search}`);
    return NextResponse.redirect(url, 301);
  }

  // 3. Remove trailing slashes (except root)
  if (pathname !== "/" && pathname.endsWith("/")) {
    const url = new URL(`https://www.ariia.ai${pathname.slice(0, -1)}${search}`);
    return NextResponse.redirect(url, 301);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico, robots.txt, sitemap.xml, etc.
     * - API proxy routes
     */
    "/((?!_next/static|_next/image|favicon\\.ico|favicon.*\\.png|apple-touch-icon\\.png|robots\\.txt|sitemap\\.xml|llms\\.txt|llms-full\\.txt|humans\\.txt|site\\.webmanifest|\\.well-known|proxy|ws).*)",
  ],
};
