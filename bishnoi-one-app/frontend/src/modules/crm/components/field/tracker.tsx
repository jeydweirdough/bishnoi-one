"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { LocationGuide } from "@/src/modules/crm/components/field/location-guide";
import { keepPoint, moveOldPoints, sendQueue, setQueueUser, type QueuedPointData } from "@/src/modules/crm/components/field/offline-queue";
import { QueueChip } from "@/src/modules/crm/components/field/queue-chip";
import { inWorkHours, locate, metres, type NoLocation } from "@/src/modules/crm/components/field/where";

// A field agent's location while the CRM is open, in work hours only. It's
// required: without it, a guide stands in front of the CRM until it's on.
//
// The trail:
// - A point is kept when they've moved 50 m from the last one, or 5 minutes
//   have passed: parked at a clinic that's one point in five minutes.
// - Kept points wait on the phone (the offline queue, offline-queue.ts, with
//   visits logged offline), so days without a signal or a closed tab lose
//   nothing already kept (Step 4H).
// - Weak readings (less sure than 200 m) are kept too: the route map marks
//   them weak and leaves them out of the distance.
// - Every 5 minutes, when the page is hidden or closed, when the app opens
//   and when the phone comes back online, what's waiting goes up. Each item
//   is only cleared once the API has it.
//
// The browser only gives the location while the page is open on screen, so
// the trail has gaps when the phone is locked. The pill in the corner says,
// always, whether the location is being taken.
const MOVED_M = 50;
const EVERY_MS = 5 * 60_000;
const SEND_EVERY_MS = 5 * 60_000;
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
  // Starts (or restarts) following the phone; set once the effect has run.
  const restart = useRef<() => void>(() => {});

  useEffect(() => {
    setQueueUser(userId);
    let last: QueuedPointData | null = null;
    const send = (closing = false) => void sendQueue(userId, { closing });

    function keep(position: GeolocationPosition) {
      if (!inWorkHours(timeZone)) return setState("after-hours");
      setState("on");
      const accuracyM = Math.round(position.coords.accuracy);
      const point = { latitude: position.coords.latitude, longitude: position.coords.longitude, accuracyM, at: new Date(position.timestamp).toISOString() };
      if (last && metres(last, point) < MOVED_M && position.timestamp - Date.parse(last.at) < EVERY_MS) return;
      last = point;
      keepPoint(userId, point).catch(() => {});
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
    moveOldPoints(userId).catch(() => {}).finally(() => send());

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
    // Background Sync (public/sw.js): the phone says it's back online, send now.
    const onWorker = (e: MessageEvent) => e.data?.type === "send" && send();
    navigator.serviceWorker?.addEventListener("message", onWorker);
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
      navigator.serviceWorker?.removeEventListener("message", onWorker);
      setQueueUser(null);
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
      <QueueChip userId={userId} />
    </>
  );
}
