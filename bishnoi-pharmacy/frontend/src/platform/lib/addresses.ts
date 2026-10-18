import { THIS_APP, setAddresses, type AppName } from "./apps";

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
  if (had && Date.now() - had.at < KEEP) return had.map;
  try {
    const res = await fetch(`${PLATFORM_API}/public/applications`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(4000) });
    if (res.ok) {
      const body = (await res.json()) as { addresses?: Record<string, string> };
      had = { at: Date.now(), map: (body.addresses ?? {}) as Partial<Record<AppName, string>> };
    }
  } catch {
    // Not reachable now: keep what was had, and ask again on the next page.
  }
  const map = had?.map ?? {};
  setAddresses(map);
  return map;
}
