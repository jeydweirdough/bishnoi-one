"use client";

import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { AsyncButton } from "@/src/platform/ui/async-button";
import { bulkRecords } from "../actions/crm";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";

/** One click: a follow-up task, due today, for whoever owns the company. */
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
      aria-label={`Win back ${name}: add a task`}
      onRun={async () => {
        const result = await bulkRecords("companies", [customerId], {
          action: "follow_up",
          followUp: { title: `Win back: no quote in ${days} days`, dueOn: fmt.todayKey() },
          toOwner: true,
        });
        if (!result.ok) return void toast.error(result.error);
        if (result.data.failed) return void toast.error(result.data.failures[0]?.error ?? "Couldn't add the task.");
        toast.success(`Task added for ${ownerName ?? "you"}`, { description: `${name}, due today` });
      }}
    >
      Win back
    </AsyncButton>
  );
}
