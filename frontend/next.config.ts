import type { NextConfig } from "next";

const apiBaseUrl = process.env.API_BASE_URL ?? "https://weather-api-production-0800.up.railway.app";

const nextConfig: NextConfig = {
  outputFileTracingRoot: __dirname,
  typescript: {
    ignoreBuildErrors: true,
  },

  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
