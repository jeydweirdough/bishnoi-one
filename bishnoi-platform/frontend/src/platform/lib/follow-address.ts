import "server-only";
import { headers } from "next/headers";
import { forgetAddresses } from "./addresses";
import { api } from "./api";
import { appUrl, THIS_APP } from "./apps";

// Addresses that follow the platform's (decided 2026-10-22): when someone signed
// in to the console opens the platform at an address that names it
// (platform-bishnoi.local, platform.bishnoi-one.cloud-ip.cc), the API is told,
// and moves every app to the same address with its own name (an administrator's
// visit only: the API refuses anyone else). Once per address per process.

const tried = new Set<string>();

export async function followAddress(): Promise<void> {
  if (THIS_APP !== "platform") return;
  const h = await headers();
  const host = (h.get("x-forwarded-host") ?? h.get("host") ?? "").split(",")[0].trim().toLowerCase();
  if (!host.includes("platform")) return;
  const proto = (h.get("x-forwarded-proto") ?? "").split(",")[0].trim() || "https";
  const origin = `${proto}://${host}`;
  if (tried.has(origin)) return;
  tried.add(origin);
  let current = "";
  try {
    current = new URL(appUrl("platform")).origin;
  } catch {
    // no address yet: it's set below
  }
  if (current === origin) return;
  try {
    const r = await api.post<{ changed: unknown[] }>("/platform/applications/adopt-address", { platformUrl: origin });
    if (r.changed.length) forgetAddresses();
  } catch {
    // Not an administrator, or the API is busy: nothing moves.
  }
}
