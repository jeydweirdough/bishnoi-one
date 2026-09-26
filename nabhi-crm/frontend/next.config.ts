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
  // A receipt or a guarantee letter goes up through a server action, and the
  // default (1 MB) is less than a phone photo. Vercel takes up to 4.5 MB.
  experimental: {
    serverActions: { bodySizeLimit: "4.5mb" },
  },
  // Which app this is, for the sidebar. Built into the screens, so it is set
  // here and not left to each machine's .env.local or the host's settings.
  env: {
    NEXT_PUBLIC_NABHI_APP: process.env.NEXT_PUBLIC_NABHI_APP ?? "crm",
  },
};

export default nextConfig;
