"use client";

import { CloudOff, CloudUpload, Check, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { counts, dropRefused, onQueueChange, sendQueue, type QueueCounts } from "@/src/modules/crm/components/field/offline-queue";

const plural = (n: number, one: string, many: string) => `${n.toLocaleString()} ${n === 1 ? one : many}`;

/** "3 visits and 120 points": what's still on the phone, in plain words. */
export function waitingText(c: QueueCounts): string {
  const parts = [
    c.visits ? plural(c.visits, "visit", "visits") : "",
    c.photos ? plural(c.photos, "photo", "photos") : "",
    c.points ? plural(c.points, "point", "points") : "",
  ].filter(Boolean);
  return parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}` : (parts[0] ?? "");
}

/**
 * What the phone still has to send (Step 4H), above the location pill: "Offline · 3 visits and 120 points
 * waiting", "Sending…", "All sent". Tapping it sends now; a visit the CRM refused says why and can be removed.
 */
export function QueueChip({ userId }: { userId: string }) {
  const [c, setC] = useState<QueueCounts | null>(null);
  const [online, setOnline] = useState(true);
  const [busy, setBusy] = useState(false);

  const read = useCallback(() => {
    counts(userId).then(setC);
  }, [userId]);

  useEffect(() => {
    setOnline(navigator.onLine);
    read();
    const stop = onQueueChange(read);
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      stop();
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, [read]);

  if (!c) return null;
  const waiting = waitingText(c);
  const refused = c.refused.length;

  async function tap() {
    if (refused) {
      toast.error(refused === 1 ? `A visit to ${c!.refused[0].label} couldn't be sent` : `${refused} visits couldn't be sent`, {
        description: c!.refused.map((r) => `${r.label}: ${r.error}`).join(" "),
        duration: 12_000,
        action: { label: "Remove from phone", onClick: () => void dropRefused(userId) },
      });
      return;
    }
    if (!online || !waiting) return;
    setBusy(true);
    await sendQueue(userId);
    setBusy(false);
  }

  const text = !online
    ? `Offline · ${waiting ? `${waiting} waiting` : "nothing waiting"}`
    : busy
      ? `Sending · ${waiting}`
      : waiting
        ? `${waiting} waiting · Send now`
        : "All sent";
  const hint = !online
    ? "You're offline. Your visits and route are kept on this phone and will be sent when you're back online."
    : waiting
      ? "Kept on this phone until the CRM has them. Tap to send now."
      : "Everything this phone kept has reached the CRM.";
  const Icon = refused ? TriangleAlert : !online ? CloudOff : waiting ? CloudUpload : Check;

  return (
    <button
      type="button"
      onClick={tap}
      title={hint}
      aria-live="polite"
      className={`fixed right-4 bottom-14 z-40 flex min-h-11 items-center gap-2 rounded-md bg-sheet px-3 text-meta shadow-overlay ${refused ? "text-danger" : "text-ink-2"}`}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <span>
        {text}
        {refused ? ` · ${plural(refused, "visit", "visits")} not sent` : ""}
      </span>
      <span className="sr-only">. {hint}</span>
    </button>
  );
}
