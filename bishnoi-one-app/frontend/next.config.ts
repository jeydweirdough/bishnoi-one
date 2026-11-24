import type { NextConfig } from "next";

// Bishnoi One's one app (decided 2026-10-23): every module's screens on one
// site, each under its path (src/platform/lib/modules.ts), each talking to its
// own API.
const nextConfig: NextConfig = {
  // Optional second local Finance site uses a separate dev lock and build cache.
  ...(process.env.FINANCE_OFFICIAL_PREVIEW === "1" ? { distDir: ".next-finance-official" } : {}),
  // Everything this app uses is inside this folder. Saying so keeps Next from
  // guessing a root further up the repo.
  turbopack: {
    root: import.meta.dirname,
  },
  outputFileTracingRoot: import.meta.dirname,
  poweredByHeader: false,
  // Browser protections on every page (2026-11-19): not framed by another site (clickjacking), files not
  // guessed into scripts, addresses not leaked to other sites, camera and location only for this site
  // (field photos and route tracking), and HTTPS only once served over it (production).
  async headers() {
    const always = [
      { key: "X-Frame-Options", value: "SAMEORIGIN" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'self'; base-uri 'self'; object-src 'none'" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(self), geolocation=(self), microphone=(), payment=(), usb=()" },
    ];
    const https = process.env.NODE_ENV === "production" ? [{ key: "Strict-Transport-Security", value: "max-age=15552000" }] : [];
    return [{ source: "/:path*", headers: [...always, ...https] }];
  },
  // Bishnoi One.exe runs the screens on each PC as a small server of their own
  // (its build sets BISHNOI_DESKTOP).
  ...(process.env.BISHNOI_DESKTOP ? { output: "standalone" as const } : {}),
  experimental: {
    // forbidden(): a page the person's role doesn't reach shows app/forbidden.tsx.
    authInterrupts: true,
    // A receipt or a guarantee letter goes up through a server action; the default (1 MB) is less than a phone photo.
    serverActions: { bodySizeLimit: "4.5mb" },
    // A build on a small machine (a laptop with little memory free): NEXT_BUILD_CPUS=2 npm run build. Unset, Next decides.
    ...(process.env.NEXT_BUILD_CPUS ? { cpus: Number(process.env.NEXT_BUILD_CPUS) } : {}),
  },
};

export default nextConfig;
