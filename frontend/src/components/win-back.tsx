"use client";

import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { addFollowUp } from "../actions/sales";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";

/** One click: a follow-up, due today, for whoever owns the customer (or you, if nobody does). */
export function WinBack({
  customerId,
  name,
  days,
  ownerId,
  ownerName,
  org,
}: {
  customerId: string;
  name: string;
  days: number;
  ownerId: string | null;
  ownerName: string | null;
  org: Org;
}) {
  const fmt = makeFormat(org);
  return (
    <AsyncButton
      size="sm"
      icon={<RotateCcw className="size-3.5" aria-hidden />}
      aria-label={`Win back ${name}: add a follow-up`}
      onRun={async () => {
        const result = await addFollowUp(customerId, {
          title: `Win back: no quote in ${days} days`,
          dueOn: fmt.todayKey(),
          assigneeId: ownerId,
        });
        if (!result.ok) return void toast.error(result.error);
        toast.success(`Follow-up added for ${ownerName ?? "you"}`, { description: `${name}, due today` });
      }}
    >
      Win back
    </AsyncButton>
  );
}
