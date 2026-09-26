import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  // Local generation on an 8 GB Mac can exceed Next's 30-second proxy default.
  experimental: { proxyTimeout: 180000 },
  async rewrites() {
    return [{ source: "/api/:path*", destination: "http://api:8000/api/:path*" }];
  },
};

export default config;
