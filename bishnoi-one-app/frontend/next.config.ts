import type { NextConfig } from "next";

// Bishnoi One's one app (decided 2026-10-23): every module's screens on one
// site, each under its path (src/platform/lib/modules.ts), each talking to its
// own API.
const nextConfig: NextConfig = {
  // Everything this app uses is inside this folder. Saying so keeps Next from
  // guessing a root further up the repo.
  turbopack: {
    root: import.meta.dirname,
  },
  outputFileTracingRoot: import.meta.dirname,
  poweredByHeader: false,
  // Bishnoi One.exe runs the screens on each PC as a small server of their own
  // (its build sets BISHNOI_DESKTOP).
  ...(process.env.BISHNOI_DESKTOP ? { output: "standalone" as const } : {}),
  experimental: {
    // forbidden(): a page the person's role doesn't reach shows app/forbidden.tsx.
    authInterrupts: true,
    // A receipt or a guarantee letter goes up through a server action; the default (1 MB) is less than a phone photo.
    serverActions: { bodySizeLimit: "4.5mb" },
  },
};

export default nextConfig;
