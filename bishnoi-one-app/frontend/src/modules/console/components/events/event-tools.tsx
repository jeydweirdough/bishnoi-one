"use client";

import { RotateCcw, SkipForward, Stethoscope } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { toast } from "sonner";
import { checkEvents, retryDelivery, skipDelivery } from "@/src/modules/console/actions/events";
import { Button } from "@/src/platform/ui/button";

/** Retry or skip one stuck delivery, beside it. */
export function DeliveryTools({ eventId, target }: { eventId: string; target: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const run = (what: "retry" | "skip") =>
    start(async () => {
      const r = what === "retry" ? await retryDelivery(eventId, target) : await skipDelivery(eventId, target);
      if (!r.ok) return void toast.error(r.error);
      const said = what === "skip" ? "Skipped" : r.data.status === "delivered" ? "Delivered" : "Tried again: still not taken";
      toast.success(said, { description: what === "skip" ? "The events behind it go on." : undefined });
      router.refresh();
    });
  return (
    <span className="flex gap-1.5">
      <Button size="sm" icon={<RotateCcw className="size-4" aria-hidden />} loading={busy} onClick={() => run("retry")}>
        Retry
      </Button>
      <Button size="sm" variant="quiet" icon={<SkipForward className="size-4" aria-hidden />} disabled={busy} onClick={() => run("skip")}>
        Skip
      </Button>
    </span>
  );
}

/** The nightly check, now. */
export function CheckNow() {
  const router = useRouter();
  const [busy, start] = useTransition();
  function run() {
    start(async () => {
      const r = await checkEvents();
      if (!r.ok) return void toast.error(r.error);
      toast.success(`Checked: ${r.data.delivered} delivered, ${r.data.stuck} stuck`, { description: `${r.data.appsAsked} apps asked to send what they hold.` });
      router.refresh();
    });
  }
  return (
    <Button icon={<Stethoscope className="size-4" aria-hidden />} loading={busy} onClick={run}>
      Check now
    </Button>
  );
}
