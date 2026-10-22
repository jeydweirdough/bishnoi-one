import { headers } from "next/headers";
import { THIS_APP, derivedAddresses, setAddresses, type AppName } from "./apps";

/**
 * Where every app's screens are, as Bishnoi One Platform's Applications page
 * says (GET /public/applications). Read when a page is served and kept for 5
 * minutes, so a new domain is set once, on the Platform, and every app follows
 * with nothing to change here. The Platform can't be reached: what was had
 * last stands, else the NEXT_PUBLIC_ addresses or the local ports (lib/apps.ts).
 */

const PLATFORM_API = (process.env.PLATFORM_API_URL || (THIS_APP === "platform" ? process.env.API_URL : "") || "http://127.0.0.1:8305").replace(/\/$/, "");
const KEEP = 300_000;

let had: { at: number; map: Partial<Record<AppName, string>> } | null = null;

export async function loadAddresses(): Promise<Partial<Record<AppName, string>>> {
  // The Platform's list is fetched at most once every few minutes; the host
  // overlay below runs every time, as the domain can differ between requests.
  if (!had || Date.now() - had.at >= KEEP) {
    try {
      const res = await fetch(`${PLATFORM_API}/public/applications`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(4000) });
      if (res.ok) {
        const body = (await res.json()) as { addresses?: Record<string, string> };
        had = { at: Date.now(), map: (body.addresses ?? {}) as Partial<Record<AppName, string>> };
      }
    } catch {
      // Not reachable now: keep what was had, and ask again on the next page.
    }
  }
  const map: Partial<Record<AppName, string>> = { ...(had?.map ?? {}) };
  // Follow the domain in use: if this page came in on a real host, work the
  // other apps' addresses out from it (lib/apps.ts) and use those, so a new
  // domain needs nothing set and no stale address (e.g. a leftover localhost on
  // the Platform) can send people to the wrong place. In development the host is
  // localhost, so nothing is derived and the stored addresses or ports stand.
  try {
    const h = await headers();
    const derived = derivedAddresses(h.get("x-forwarded-host") || h.get("host") || "", h.get("x-forwarded-proto") || "https");
    Object.assign(map, derived);
  } catch {
    // Not inside a request (no headers): the stored addresses stand.
  }
  setAddresses(map);
  return map;
}
