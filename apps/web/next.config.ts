import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Increase server-side timeout for long-running API routes (PDF processing)
  serverExternalPackages: ['pdf-parse'],
  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
  },
};

export default nextConfig;
