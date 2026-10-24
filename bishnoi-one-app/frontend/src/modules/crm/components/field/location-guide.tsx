"use client";

import { MapPinOff } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { NO_LOCATION, type NoLocation } from "@/src/modules/crm/components/field/where";

type Device = "android" | "iphone-safari" | "iphone-chrome" | "windows" | "mac" | "computer";

function deviceOf(agent: string): Device {
  if (/iPhone|iPad|iPod/.test(agent)) return /CriOS/.test(agent) ? "iphone-chrome" : "iphone-safari";
  if (/Android/.test(agent)) return "android";
  if (/Windows/.test(agent)) return "windows";
  if (/Macintosh/.test(agent)) return "mac";
  return "computer";
}

// The steps, per device and per reason, in the words the phone itself uses.
const BLOCKED: Record<Device, string[]> = {
  android: [
    "Tap the icon at the left of the address bar (a lock or two sliders).",
    "Tap Permissions (or Site settings), then Location, and choose Allow.",
    "Come back here and tap Try again.",
  ],
  "iphone-safari": [
    "Tap aA at the left of the address bar, then Website Settings.",
    "Set Location to Allow.",
    "If Location isn't there: open the Settings app, then Apps, Safari, Location, and choose Ask or Allow.",
    "Come back here and tap Try again.",
  ],
  "iphone-chrome": [
    "Open the Settings app, then Apps, then Chrome.",
    "Tap Location and choose While Using the App.",
    "Come back to Chrome, tap Try again, and tap Allow when it asks.",
  ],
  windows: [
    "Click the icon at the left of the address bar (a lock or two sliders).",
    "Set Location to Allow (under Permissions or Site settings).",
    "Click Try again.",
  ],
  mac: [
    "Click the icon at the left of the address bar (a lock or two sliders), or aA in Safari.",
    "Set Location to Allow.",
    "Click Try again.",
  ],
  computer: ["Open this site's settings from the icon at the left of the address bar.", "Set Location to Allow.", "Click Try again."],
};

const SWITCHED_OFF: Record<Device, string[]> = {
  android: ["Swipe down from the top of the screen.", "Tap Location to turn it on.", "Come back here and tap Try again."],
  "iphone-safari": [
    "Open the Settings app, then Privacy & Security, then Location Services, and turn it on.",
    "In the same list, tap Safari Websites and choose While Using the App.",
    "Come back here and tap Try again.",
  ],
  "iphone-chrome": [
    "Open the Settings app, then Privacy & Security, then Location Services, and turn it on.",
    "In the same list, tap Chrome and choose While Using the App.",
    "Come back here and tap Try again.",
  ],
  windows: ["Open Settings, then Privacy & security, then Location.", "Turn on Location services, and let apps (your browser) use it.", "Click Try again."],
  mac: ["Open System Settings, then Privacy & Security, then Location Services.", "Turn it on, and turn it on for your browser.", "Click Try again."],
  computer: ["Turn on location in your computer's privacy settings, for your browser too.", "Click Try again."],
};

const OTHER: Record<Exclude<NoLocation, "denied" | "off">, string[]> = {
  slow: ["Step near a window or outside.", "Turn on Wi-Fi: it helps the phone find you, even without joining a network.", "Tap Try again."],
  unsupported: ["Open Bishnoi One in Chrome (Android) or Safari (iPhone).", "Sign in there, and allow location when it asks."],
  insecure: ["Open Bishnoi One from its https:// address (the one your admin gave you).", "Sign in there, and allow location when it asks."],
};

/**
 * In the way of the whole CRM, for a field agent in work hours with no
 * location: what's wrong, why it's needed, and the steps for their device.
 */
export function LocationGuide({ why, onRetry, retrying }: { why: NoLocation; onRetry: () => void; retrying: boolean }) {
  const [device, setDevice] = useState<Device>("computer");
  useEffect(() => setDevice(deviceOf(navigator.userAgent)), []);
  const steps = why === "denied" ? BLOCKED[device] : why === "off" ? SWITCHED_OFF[device] : OTHER[why];

  return (
    <div role="alertdialog" aria-modal="true" aria-labelledby="location-title" className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div className="max-h-[90vh] w-[min(30rem,100%)] overflow-y-auto rounded-xl bg-sheet p-6 text-ink shadow-overlay">
        <span className="mb-3 flex size-10 items-center justify-center rounded-full bg-danger/10 text-danger">
          <MapPinOff className="size-5" aria-hidden />
        </span>
        <h2 id="location-title" className="text-heading">
          Turn on your location to use Bishnoi One
        </h2>
        <p className="mt-1 text-sm text-ink-2">{NO_LOCATION[why]}</p>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm">
          {steps.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <Button className="mt-5 w-full" variant="primary" loading={retrying} onClick={onRetry}>
          Try again
        </Button>
        <p className="mt-4 border-t border-rule pt-3 text-meta text-ink-3">
          Field work saves where each visit is logged, and your route while Bishnoi One is open, from 6:00 to 20:00. Your lead and the admin can see it. Nothing
          is taken after hours.
        </p>
      </div>
    </div>
  );
}
