import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: {},

  /* ── Performance & SEO ── */
  compress: true,
  poweredByHeader: false,
  reactStrictMode: true,

  /* ── Image Optimization ── */
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "files.manuscdn.com",
      },
    ],
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },

  /* ── Proxy Rewrites ── */
  async rewrites() {
    return [
      {
        source: "/proxy/:path*",
        destination: `${process.env.GATEWAY_INTERNAL_URL || "http://ariia-core:8000"}/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${process.env.GATEWAY_INTERNAL_URL || "http://ariia-core:8000"}/ws/:path*`,
      },
    ];
  },

  /* ── SEO Redirects ── */
  async redirects() {
    return [
      // Trailing slash normalization
      {
        source: "/:path+/",
        destination: "/:path+",
        permanent: true,
      },
      // Old /ariia paths redirect to root
      {
        source: "/ariia/:path*",
        destination: "/:path*",
        permanent: true,
      },
    ];
  },

  /* ── Security & SEO Headers ── */
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "X-XSS-Protection",
            value: "1; mode=block",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      // Cache static assets aggressively
      {
        source: "/(.*)\\.(ico|png|svg|jpg|jpeg|gif|webp|avif|woff|woff2)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      // Cache sitemap and robots
      {
        source: "/(sitemap\\.xml|robots\\.txt|llms\\.txt|llms-full\\.txt)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=86400, s-maxage=86400",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
