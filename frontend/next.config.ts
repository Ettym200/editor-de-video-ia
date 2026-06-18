import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    middlewareClientMaxBodySize: 500 * 1024 * 1024,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.INTERNAL_API_URL || "http://api:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
