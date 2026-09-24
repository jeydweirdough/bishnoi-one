"use client";

import { useEffect, useRef, useState } from "react";
import { inWorkHours, metres, type Where } from "./where";

type TrailPoint = Where & { at: string };

// A field agent's trail while the CRM is open, in work hours only.
//
// - A point is kept when they've moved 50 m from the last one, or 5 minutes
//   have passed: parked at a clinic that's one point in five minutes.
// - Kept points wait on the phone (this browser's storage), so a dropped
//   signal or a closed tab loses nothing already kept.
// - Every 15 minutes, when the page is hidden or closed, and when the phone
//   comes back online, the waiting points go up in one request. They're only
//   cleared once the API has them.
//
// The browser only gives the location while the page is open on screen, so
// the trail has gaps when the phone is locked. The pill in the corner says,
// always, whether the location is being taken.
const MOVED_M = 50;
const EVERY_MS = 5 * 60_000;
const SEND_EVERY_MS = 15 * 60_000;
const WORST_ACCURACY_M = 200;
const MOST_WAITING = 2000;

type State = "starting" | "on" | "after-hours" | "denied" | "unsupported";

const WORDS: Record<State, { text: string; hint: string }> = {
  starting: { text: "Location starting", hint: "Asking your phone where you are." },
  on: { text: "Location on", hint: "Your route is saved while Nabhi is open, 6:00 to 20:00. Your lead and the admin can see it." },
  "after-hours": { text: "Location off after hours", hint: "Nothing is saved outside 6:00 to 20:00." },
  denied: { text: "Location blocked", hint: "Allow location for this site in your browser, so your visits and route are saved." },
  unsupported: { text: "No location", hint: "This browser can't share your location." },
};

export function FieldTracker({ userId, timeZone }: { userId: string; timeZone: string }) {
  const [state, setState] = useState<State>("starting");
  const sending = useRef(false);

  useEffect(() => {
    const key = `nabhi-trail:${userId}`;
    const read = (): TrailPoint[] => {
      try {
        return JSON.parse(localStorage.getItem(key) ?? "[]");
      } catch {
        return [];
      }
    };
    const write = (points: TrailPoint[]) => {
      try {
        localStorage.setItem(key, JSON.stringify(points.slice(-MOST_WAITING)));
      } catch {
        // Storage full or off: the points in hand still go up with the next send.
      }
    };
    let last: TrailPoint | null = read().at(-1) ?? null;

    function send(closing = false) {
      const waiting = read();
      if (!waiting.length || sending.current) return;
      // A closing page can only send a small body; the rest waits for next time.
      const batch = waiting.slice(0, closing ? 300 : 1000);
      sending.current = true;
      fetch("/api/trail", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ points: batch }), keepalive: closing })
        .then((r) => {
          // Points kept while this was on its way stay, after the ones sent.
          if (r.ok) write(read().slice(batch.length));
        })
        .catch(() => {})
        .finally(() => {
          sending.current = false;
        });
    }

    function keep(position: GeolocationPosition) {
      if (!inWorkHours(timeZone)) return setState("after-hours");
      setState("on");
      const accuracyM = Math.round(position.coords.accuracy);
      if (accuracyM > WORST_ACCURACY_M) return;
      const point = { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracyM, at: new Date(position.timestamp).toISOString() };
      if (last && metres(last, point) < MOVED_M && position.timestamp - Date.parse(last.at) < EVERY_MS) return;
      last = point;
      write([...read(), point]);
    }

    if (!("geolocation" in navigator)) {
      setState("unsupported");
      return;
    }
    let watch: number | null = null;
    const follow = () => {
      if (!inWorkHours(timeZone)) {
        if (watch !== null) navigator.geolocation.clearWatch(watch);
        watch = null;
        setState("after-hours");
        return;
      }
      if (watch !== null) return;
      watch = navigator.geolocation.watchPosition(
        keep,
        (error) => {
          if (error.code === error.PERMISSION_DENIED) setState("denied");
        },
        { enableHighAccuracy: true, maximumAge: 30_000, timeout: 60_000 },
      );
    };
    follow();
    send();

    const hours = window.setInterval(follow, 60_000);
    const upload = window.setInterval(() => send(), SEND_EVERY_MS);
    const onHide = () => document.visibilityState === "hidden" && send(true);
    const onLeave = () => send(true);
    const onOnline = () => send();
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", onLeave);
    window.addEventListener("online", onOnline);
    return () => {
      if (watch !== null) navigator.geolocation.clearWatch(watch);
      window.clearInterval(hours);
      window.clearInterval(upload);
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("pagehide", onLeave);
      window.removeEventListener("online", onOnline);
    };
  }, [userId, timeZone]);

  const words = WORDS[state];
  const dot = state === "on" ? "bg-hema" : state === "denied" ? "bg-danger" : "bg-ink-3";
  return (
    <div
      role="status"
      title={words.hint}
      className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-[3px] bg-sheet px-3 py-1.5 text-meta text-ink-2 shadow-overlay"
    >
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      {words.text}
      <span className="sr-only">. {words.hint}</span>
    </div>
  );
}
