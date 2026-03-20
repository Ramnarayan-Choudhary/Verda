import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const appDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(appDir, "..", "..");

// Canonical env location for the monorepo.
loadEnvConfig(repoRoot, process.env.NODE_ENV !== "production");

const nextConfig: NextConfig = {
  // Increase server-side timeout for long-running API routes (PDF processing)
  serverExternalPackages: ['pdf-parse'],
  experimental: {
    serverActions: {
      bodySizeLimit: '50mb',
    },
  },
  // Increase proxy timeout for long-running hypothesis pipeline calls
  httpAgentOptions: {
    keepAlive: true,
  },
};

export default nextConfig;
