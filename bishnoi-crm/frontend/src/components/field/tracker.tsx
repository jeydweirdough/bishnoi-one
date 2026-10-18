"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LocationGuide } from "./location-guide";
import { inWorkHours, locate, metres, type NoLocation, type Where } from "./where";

type TrailPoint = Where & { at: string };

// A field agent's location while the CRM is open, in work hours only. It's
// required: without it, a guide stands in front of the CRM until it's on.
//
// The trail:
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
// What stops the CRM until it's fixed. "slow" doesn't: a clinic's thick walls
// shouldn't lock an agent out; the pill says it's still looking.
const BLOCKING: NoLocation[] = ["denied", "off", "unsupported", "insecure"];

type State = "starting" | "on" | "after-hours" | NoLocation;

const PILL: Record<State, { text: string; hint: string }> = {
  starting: { text: "Finding your location", hint: "Asking your phone where you are." },
  on: { text: "Location on", hint: "Your route is saved while Bishnoi One is open, 6:00 to 20:00. Your lead and the admin can see it." },
  "after-hours": { text: "Location off after hours", hint: "Nothing is saved outside 6:00 to 20:00." },
  slow: { text: "Finding your location", hint: "Your phone hasn't found you yet. Near a window or outside helps." },
  denied: { text: "Location blocked", hint: "Allow location for this site." },
  off: { text: "Location off", hint: "Turn on your phone's location." },
  unsupported: { text: "No location", hint: "This browser can't share your location." },
  insecure: { text: "No location", hint: "Open Bishnoi One from its https address." },
};

export function FieldTracker({ userId, timeZone }: { userId: string; timeZone: string }) {
  const [state, setState] = useState<State>("starting");
  const [retrying, setRetrying] = useState(false);
  const sending = useRef(false);
  // Starts (or restarts) following the phone; set once the effect has run.
  const restart = useRef<() => void>(() => {});

  useEffect(() => {
    const key = `bishnoi-trail:${userId}`;
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

    let watch: number | null = null;
    const stop = () => {
      if (watch !== null) navigator.geolocation.clearWatch(watch);
      watch = null;
    };
    const follow = () => {
      if (!inWorkHours(timeZone)) {
        stop();
        setState("after-hours");
        return;
      }
      if (!window.isSecureContext) return setState("insecure");
      if (!("geolocation" in navigator)) return setState("unsupported");
      if (watch !== null) return;
      watch = navigator.geolocation.watchPosition(
        keep,
        (error) => {
          if (error.code === error.PERMISSION_DENIED || error.code === error.POSITION_UNAVAILABLE) {
            // Stopped, so the next try (Try again, or coming back to the tab) asks afresh.
            stop();
            setState(error.code === error.PERMISSION_DENIED ? "denied" : "off");
          } else {
            setState((now) => (now === "on" ? now : "slow"));
          }
        },
        { enableHighAccuracy: true, maximumAge: 30_000, timeout: 60_000 },
      );
    };
    restart.current = () => {
      stop();
      follow();
    };
    follow();
    send();

    // When they allow it in the browser's settings, carry on by itself.
    let permission: PermissionStatus | null = null;
    navigator.permissions
      ?.query({ name: "geolocation" })
      .then((p) => {
        permission = p;
        p.onchange = () => p.state === "granted" && restart.current();
      })
      .catch(() => {});

    const hours = window.setInterval(follow, 60_000);
    const upload = window.setInterval(() => send(), SEND_EVERY_MS);
    const onVisible = () => {
      if (document.visibilityState === "hidden") return send(true);
      // Back from the phone's Settings: look again.
      if (watch === null) follow();
    };
    const onLeave = () => send(true);
    const onOnline = () => send();
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pagehide", onLeave);
    window.addEventListener("online", onOnline);
    return () => {
      stop();
      if (permission) permission.onchange = null;
      window.clearInterval(hours);
      window.clearInterval(upload);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pagehide", onLeave);
      window.removeEventListener("online", onOnline);
    };
  }, [userId, timeZone]);

  const retry = useCallback(async () => {
    setRetrying(true);
    // Asking once directly shows the browser's prompt again where it still can.
    const found = await locate(15_000);
    setRetrying(false);
    if (found.ok) {
      setState("on");
      restart.current();
    } else {
      setState(found.why);
    }
  }, []);

  const pill = PILL[state];
  const dot = state === "on" ? "bg-hema" : BLOCKING.includes(state as NoLocation) ? "bg-danger" : "bg-ink-3";
  return (
    <>
      {BLOCKING.includes(state as NoLocation) && <LocationGuide why={state as NoLocation} onRetry={retry} retrying={retrying} />}
      <div
        role="status"
        title={pill.hint}
        className="fixed right-4 bottom-4 z-40 flex items-center gap-2 rounded-md bg-sheet px-3 py-1.5 text-meta text-ink-2 shadow-overlay"
      >
        <span aria-hidden className={`size-2 rounded-full ${dot}`} />
        {pill.text}
        <span className="sr-only">. {pill.hint}</span>
      </div>
    </>
  );
}
