import { execFileSync } from "node:child_process";
import path from "node:path";
import type { NextConfig } from "next";

// The commit these screens are built from, for the sidebar's version line
// (src/version). Vercel gives it; on this computer Git is asked, and "-dirty"
// means changes not yet committed. Neither: empty, and the line says nothing.
function builtFrom(): string {
  const given = process.env.VERCEL_GIT_COMMIT_SHA;
  if (given) return given.slice(0, 7);
  try {
    return execFileSync("git", ["describe", "--always", "--dirty", "--abbrev=7", "--exclude", "*"], {
      cwd: import.meta.dirname,
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 3000,
    })
      .toString()
      .trim();
  } catch {
    return "";
  }
}

const nextConfig: NextConfig = {
  // core ships raw TypeScript, so Next compiles it with this app.
  
  turbopack: {
    // core is a sibling folder, and Turbopack resolves nothing outside its
    // root, so the root has to be the folder holding both.
    root: path.resolve(import.meta.dirname, ".."),
  },
  poweredByHeader: false,
  // forbidden(): a page the person's role doesn't reach shows app/forbidden.tsx.
  experimental: { authInterrupts: true },
  // Which app this is, for the sidebar and the sign-in cookie. Built in, so
  // no .env.local or host setting needs it; one there still wins.
  env: {
    NEXT_PUBLIC_BISHNOI_APP: (process.env.NEXT_PUBLIC_BISHNOI_APP ?? process.env.NEXT_PUBLIC_NABHI_APP) ?? "finance",
    NEXT_PUBLIC_FINANCE_BUILD: builtFrom(),
    // Where that came from: only two deployed (Vercel) builds are compared (src/version/build.ts).
    NEXT_PUBLIC_FINANCE_BUILD_SOURCE: process.env.VERCEL_GIT_COMMIT_SHA ? "vercel" : "local",
    NEXT_PUBLIC_FINANCE_BUILT_AT: new Date().toISOString(),
  },
};

export default nextConfig;
