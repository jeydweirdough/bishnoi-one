// Where the phone is, asked of the browser. Nothing here runs on the server.

export type Where = { latitude: number; longitude: number; accuracyM: number };

/** When locations are taken, in the company's own hours: 6:00 to 20:00 (the API keeps the same). */
export const WORK_HOURS = [6, 20] as const;

export function inWorkHours(timeZone: string, now = new Date()): boolean {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", hourCycle: "h23" }).format(now));
  return hour >= WORK_HOURS[0] && hour < WORK_HOURS[1];
}

/**
 * Why there's no location, which decides what the person is told to do:
 * - denied: this site was blocked from it (the browser's site settings);
 * - off: the phone's own location is switched off;
 * - slow: it's on, but no fix came in time (indoors, weak signal);
 * - unsupported: this browser can't give one;
 * - insecure: the page isn't on https, where browsers never give one.
 */
export type NoLocation = "denied" | "off" | "slow" | "unsupported" | "insecure";

export type Located = { ok: true; where: Where } | { ok: false; why: NoLocation };

/** The phone's position now, or why not. */
export function locate(timeoutMs = 10_000): Promise<Located> {
  if (typeof window !== "undefined" && !window.isSecureContext) return Promise.resolve({ ok: false, why: "insecure" });
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve({ ok: false, why: "unsupported" });
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ ok: true, where: { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracyM: Math.round(p.coords.accuracy) } }),
      (e) => resolve({ ok: false, why: e.code === e.PERMISSION_DENIED ? "denied" : e.code === e.POSITION_UNAVAILABLE ? "off" : "slow" }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    );
  });
}

/** The phone's position now, or null if it can't or won't say within the time. */
export async function whereNow(timeoutMs = 10_000): Promise<Where | null> {
  const found = await locate(timeoutMs);
  return found.ok ? found.where : null;
}

/** What to say, in a sentence, when there's no location. */
export const NO_LOCATION: Record<NoLocation, string> = {
  denied: "Location is blocked for Bishnoi One in your browser.",
  off: "Your phone's location is switched off.",
  slow: "Your phone couldn't find where you are yet. Step near a window or outside, then try again.",
  unsupported: "This browser can't share your location. Use Chrome or Safari on your phone.",
  insecure: "Location only works on the secure (https) address of Bishnoi One.",
};

/** How far apart two places are, in metres, along the ground. */
export function metres(a: { latitude: number; longitude: number }, b: { latitude: number; longitude: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.latitude - a.latitude) * rad;
  const dLng = (b.longitude - a.longitude) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.latitude * rad) * Math.cos(b.latitude * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6_371_000 * Math.asin(Math.sqrt(h));
}

/** "55 m" or "1.2 km". */
export function distanceText(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(m < 10_000 ? 1 : 0)} km`;
}

/** A place on Google Maps, for a quick look. */
export const mapLink = (w: { latitude: number; longitude: number }) => `https://www.google.com/maps?q=${w.latitude},${w.longitude}`;
