import type { NextConfig } from "next";

// Where the FastAPI backend listens. The browser only ever talks to this app's own origin; /api/* is
// forwarded here, so there is no CORS to configure. WebSockets are not proxied by Next: in production
// the tunnel/reverse proxy sends /ws/* straight to the backend, and in local dev the app connects to the
// backend's port directly (see src/lib/ws.ts).
const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The repo root also has a package.json (the one-command runner), so say which folder is this app's
  // root instead of letting Next guess between the two lockfiles.
  turbopack: { root: process.cwd() },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      { source: "/health", destination: `${backend}/health` },
    ];
  },
  // The tunnel hostname loads this app (and its dev assets) from another origin.
  allowedDevOrigins: ["test-voicemitra.apoorvm.com"],
};

export default nextConfig;
