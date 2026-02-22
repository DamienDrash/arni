import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: "/ariia",
  assetPrefix: "/ariia",
  async rewrites() {
    return [
      {
        source: "/proxy/:path*",
        destination: `${process.env.GATEWAY_INTERNAL_URL || "http://ariia-core:8000"}/:path*`,
      },
      {
        source: "/ws/:path*",
        destination: `${process.env.GATEWAY_INTERNAL_URL || "http://ariia-core:8000"}/ws/:path*`, // Next.js supports WebSocket proxying on rewrites
      },
    ];
  },
};

export default nextConfig;
