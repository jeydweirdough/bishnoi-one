import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Everything this app uses is inside this folder. Saying so keeps Next from
  // guessing a root further up, and keeps the build output where Cloudflare's
  // adapter (OpenNext) looks for it.
  turbopack: {
    root: import.meta.dirname,
  },
  outputFileTracingRoot: import.meta.dirname,
  poweredByHeader: false,
  // Which app this is, for the sidebar. Built into the screens, so it is set
  // here and not left to each machine's .env.local or Cloudflare's settings.
  env: {
    NEXT_PUBLIC_ORBIT_APP: process.env.NEXT_PUBLIC_ORBIT_APP ?? "crm",
  },
};

export default nextConfig;
