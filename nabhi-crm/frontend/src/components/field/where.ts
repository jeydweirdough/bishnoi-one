// Where the phone is, asked of the browser. Nothing here runs on the server.

export type Where = { latitude: number; longitude: number; accuracyM: number };

/** When locations are taken, in the company's own hours: 6:00 to 20:00 (the API keeps the same). */
export const WORK_HOURS = [6, 20] as const;

export function inWorkHours(timeZone: string, now = new Date()): boolean {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone, hour: "2-digit", hourCycle: "h23" }).format(now));
  return hour >= WORK_HOURS[0] && hour < WORK_HOURS[1];
}

/** The phone's position now, or null if it can't or won't say within the time. */
export function whereNow(timeoutMs = 10_000): Promise<Where | null> {
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracyM: Math.round(p.coords.accuracy) }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    );
  });
}

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
