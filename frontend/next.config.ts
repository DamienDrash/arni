import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: "/ariia",
  devIndicators: {
  },
  /* 
     WebSocket HMR Fix for Next.js 15 + Turbopack behind Nginx Proxy.
     Explicitly setting the HMR path ensures the client connects correctly.
  */
  // Turbopack specific config via experimental if needed, but usually ENV vars are better.
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
};

export default nextConfig;
