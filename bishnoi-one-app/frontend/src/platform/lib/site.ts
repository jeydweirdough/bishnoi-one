// Where this site is, as the browser sees it. Behind a proxy (Coolify's Traefik,
// a Cloudflare Tunnel) request.url is the container's own address
// (http://localhost:4301), so redirects and return addresses are built from
// this instead: ONE_APP_URL when set; else the forwarded host, with the scheme
// Cloudflare saw (CF-Visitor: Traefik rewrites X-Forwarded-Proto to http).
export function siteOrigin(headers: Headers, fallback: string): string {
  const set = process.env.ONE_APP_URL;
  if (set) return set.replace(/\/$/, "");
  const first = (name: string) => headers.get(name)?.split(",")[0].trim() || null;
  const host = first("x-forwarded-host") || first("host");
  if (!host) return new URL(fallback).origin;
  const visitor = headers.get("cf-visitor")?.match(/"scheme"\s*:\s*"(https?)"/)?.[1];
  const proto = visitor || first("x-forwarded-proto") || new URL(fallback).protocol.replace(":", "");
  return `${proto}://${host}`;
}

// A page of this site: siteUrl("/login", request).
export function siteUrl(path: string, request: { headers: Headers; url: string }): URL {
  return new URL(path, siteOrigin(request.headers, request.url));
}
