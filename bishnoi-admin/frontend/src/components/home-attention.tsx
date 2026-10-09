"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { logStep } from "@/src/actions/operations";
import type { CountdownHighlight } from "@/src/platform/lib/types";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Icon, type IconName } from "@/src/platform/ui/icons";

// What each kind of line is, and the one step that settles it from here (a
// car's renewal, its PMS). Others open their page, where the work is done.
const ICON: Record<string, IconName> = {
  permit: "permits",
  immigration: "immigration",
  document: "documents",
  property: "properties",
  ticket: "tickets",
  vehicle_registration: "vehicles",
  vehicle_insurance: "vehicles",
  vehicle_pms: "vehicles",
  travel: "travel",
};
const STEP: Record<string, { action: string; label: string }> = {
  vehicle_registration: { action: "registration_renewed", label: "Renewed" },
  vehicle_insurance: { action: "insurance_renewed", label: "Renewed" },
  vehicle_pms: { action: "pms_done", label: "PMS done" },
};

function when(days: number): string {
  if (days < 0) return `Overdue ${Math.abs(days)} ${Math.abs(days) === 1 ? "day" : "days"}`;
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `Due in ${days} days`;
}

/** The CRM's "Needs your attention": the lines that are late or close, each with its next step. */
const SHOWN = 6;

export function HomeAttention({ items, canLog }: { items: CountdownHighlight[]; canLog: boolean }) {
  const router = useRouter();
  const [done, setDone] = useState<string[]>([]);
  const [pending, start] = useTransition();
  const left = items.filter((i) => !done.includes(`${i.entityType}-${i.entityId}`));

  return (
    <section className="rounded-[28px] bg-mint px-6 py-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-[17px] font-semibold text-ink">Needs your attention</h2>
        <span className="inline-flex h-[26px] items-center rounded-full border border-ink bg-sheet px-3 text-[12.5px] font-medium">{left.length}</span>
      </div>
      {left.length === 0 ? (
        <p className="mt-3 text-sm text-ink-2">Nothing is late or due this week. Due next is on the right.</p>
      ) : (
        <ul className="mt-3">
          {left.slice(0, SHOWN).map((i) => {
            const step = canLog ? STEP[i.entityType] : undefined;
            const key = `${i.entityType}-${i.entityId}`;
            return (
              <li key={key} className="flex items-start gap-3.5 border-b border-mint-2 py-3.5 last:border-0 last:pb-0">
                <span className="grid size-[38px] shrink-0 place-items-center rounded-full border-[1.5px] border-ink bg-sheet">
                  <Icon name={ICON[i.entityType] ?? "notifications"} className="size-[18px]" />
                </span>
                <div className="min-w-0 flex-1">
                  <Link href={i.actionPath} className="font-semibold text-ink hover:underline">
                    {i.title}
                    {i.entityType.startsWith("vehicle_") ? `: ${i.subtitle.charAt(0).toLowerCase() + i.subtitle.slice(1)}` : ""}
                  </Link>
                  <p className={`text-[12.5px] ${i.daysRemaining < 0 ? "font-medium text-danger" : "text-ink-3"}`}>
                    {when(i.daysRemaining)}
                    <span className="font-normal text-ink-3"> · {i.entityType.startsWith("vehicle_") ? i.reference : i.subtitle}</span>
                  </p>
                </div>
                {step ? (
                  <Button
                    size="sm"
                    disabled={pending}
                    onClick={() =>
                      start(async () => {
                        const r = await logStep("vehicles", i.entityId, step.action);
                        if (!r.ok) return void toast.error(r.error);
                        setDone((d) => [...d, key]);
                        toast.success(step.label === "PMS done" ? "PMS done" : `${i.subtitle} renewed`, { description: i.title });
                        router.refresh();
                      })
                    }
                  >
                    {step.label}
                  </Button>
                ) : (
                  <LinkButton href={i.actionPath} size="sm">
                    Open
                  </LinkButton>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {left.length > SHOWN && (
        <p className="mt-4 border-t border-mint-2 pt-3.5 text-[13px] text-ink-2">
          And {left.length - SHOWN} more late or due this week.{" "}
          <Link href="/notifications" className="font-semibold text-ink underline">
            See them in Renewal alerts
          </Link>
        </p>
      )}
    </section>
  );
}
