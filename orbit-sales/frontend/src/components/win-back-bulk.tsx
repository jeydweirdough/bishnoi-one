"use client";

import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input } from "@/src/platform/ui/field";
import { bulkRecords } from "../actions/crm";
import { makeFormat, plural } from "@/src/platform/lib/format";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import type { Org } from "@/src/platform/lib/types";

const NOUN: [string, string] = ["customer", "customers"];

/** The win-back round: a follow-up for each ticked customer, given to whoever owns them. */
export function WinBackBulk({ org }: { org: Org }) {
  const fmt = makeFormat(org);
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [asking, setAsking] = useState(false);

  const step = (
    <BulkStep
      submitLabel={`Add ${plural(s.ids.length, "task")}`}
      onCancel={() => setAsking(false)}
      onSubmit={async (form) => {
        const title = String(form.get("title") ?? "").trim();
        const dueOn = String(form.get("dueOn") ?? "");
        if (title.length < 2 || !dueOn) {
          toast.error("Give the task a title and a date.");
          return false;
        }
        await run({ doing: "Adding win-back calls", did: (n) => `Win-back task added for ${plural(n, ...NOUN)}` }, (ids) =>
          bulkRecords("companies", ids, { action: "follow_up", followUp: { title, dueOn }, toOwner: true }),
        );
      }}
    >
      <Field label="Task, for each customer's owner" className="w-64">
        {(p) => <Input {...p} name="title" defaultValue="Win back: no quote lately" required minLength={2} maxLength={160} autoFocus />}
      </Field>
      <Field label="Due" className="w-36">
        {(p) => <Input {...p} name="dueOn" type="date" defaultValue={fmt.todayKey()} required />}
      </Field>
    </BulkStep>
  );

  return (
    <BulkBar noun={NOUN} step={asking ? step : undefined}>
      <Button size="sm" variant="primary" disabled={running} onClick={() => setAsking(true)} icon={<RotateCcw className="size-3.5" aria-hidden />}>
        Add win-back calls
      </Button>
    </BulkBar>
  );
}
