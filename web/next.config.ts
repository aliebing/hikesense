import type { NextConfig } from "next";

// Server-side targets of the same-origin proxy: the browser only ever talks to :3000, so one
// HTTPS tunnel serves the phone (README „Auf dem Handy“). In docker compose these are set to
// the api service and host.docker.internal.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
const SUPABASE_URL = process.env.SUPABASE_URL || "http://127.0.0.1:54321";

const nextConfig: NextConfig = {
  // The dev badge sits bottom-left over the data/photo attribution.
  devIndicators: false,
  // the dev server answers a quick tunnel (cloudflared) to :3000
  allowedDevOrigins: ["*.trycloudflare.com"],
  async rewrites() {
    return [
      { source: "/api/chat", destination: `${API_INTERNAL_URL}/chat` },
      { source: "/api/admin/:path*", destination: `${API_INTERNAL_URL}/admin/:path*` },
      { source: "/sb/:path*", destination: `${SUPABASE_URL}/:path*` },
    ];
  },
};

export default nextConfig;
