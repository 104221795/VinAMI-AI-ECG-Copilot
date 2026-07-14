import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output:
    process.env.VINAMI_NEXT_STANDALONE === "true" ? "standalone" : undefined,
  poweredByHeader: false,
  reactStrictMode: true,
  transpilePackages: ["@vinami/ui", "@vinami/api-client", "@vinami/contracts"],
};

export default nextConfig;
