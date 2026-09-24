import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Everything this app uses is inside this folder. Saying so keeps Next from
  // guessing a root further up the repo, which would put the build's files
  // under frontend/ where hosts don't look for them.
  turbopack: {
    root: import.meta.dirname,
  },
  outputFileTracingRoot: import.meta.dirname,
  poweredByHeader: false,
  // Which app this is, for the sidebar. Built into the screens, so it is set
  // here and not left to each machine's .env.local or the host's settings.
  env: {
    NEXT_PUBLIC_ORBIT_APP: process.env.NEXT_PUBLIC_ORBIT_APP ?? "crm",
  },
};

export default nextConfig;
