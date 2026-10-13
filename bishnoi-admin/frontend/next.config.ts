import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // core ships raw TypeScript, so Next compiles it with this app.
  
  turbopack: {
    // core is a sibling folder, and Turbopack resolves nothing outside
    // its root, so the root is the folder holding both.
    root: path.resolve(import.meta.dirname, ".."),
  },
  poweredByHeader: false,
  // forbidden(): a page the person's role doesn't reach shows app/forbidden.tsx.
  experimental: { authInterrupts: true },
  // Which app this is, for the sidebar and the sign-in cookie. Built in, so
  // no .env.local or host setting needs it; one there still wins.
  env: {
    NEXT_PUBLIC_BISHNOI_APP: (process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "exec",
  },
};

export default nextConfig;
