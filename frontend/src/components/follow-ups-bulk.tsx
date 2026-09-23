"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import { Button } from "@/src/platform/ui/button";
import { Field, Input, Select } from "@/src/platform/ui/field";
import { bulkActivities } from "../actions/crm";
import { makeFormat, plural } from "@/src/platform/lib/format";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";
import type { Assignable, Org } from "@/src/platform/lib/types";

const NOUN: [string, string] = ["follow-up", "follow-ups"];

export function FollowUpsBulk({
  people,
  state,
  org,
}: {
  // Who follow-ups can be given to: the people within the person's reach.
  people: Assignable[];
  state: "open" | "done";
  org: Org;
}) {
  const fmt = makeFormat(org);
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [step, setStep] = useState<"due" | "assign" | null>(null);
  const many = plural(s.ids.length, ...NOUN);

  function openAssign() {
    setStep("assign");
  }

  if (state === "done") {
    return (
      <BulkBar noun={NOUN}>
        <Button
          size="sm"
          variant="primary"
          loading={running}
          onClick={() => run({ doing: "Reopening", did: (n) => `${plural(n, ...NOUN)} reopened` }, (ids) => bulkActivities(ids, { action: "open" }))}
        >
          Reopen
        </Button>
      </BulkBar>
    );
  }

  const steps = {
    due: (
      <BulkStep
        submitLabel={`Move ${many}`}
        onCancel={() => setStep(null)}
        onSubmit={async (form) => {
          const dueOn = String(form.get("dueOn") ?? "");
          if (!dueOn) return false;
          await run({ doing: "Moving", did: (n) => `${plural(n, ...NOUN)} moved to ${fmt.dateLabel(dueOn)}` }, (ids) =>
            bulkActivities(ids, { action: "due", dueOn }),
          );
        }}
      >
        <Field label="New due date" className="w-40">
          {(p) => <Input {...p} name="dueOn" type="date" defaultValue={fmt.todayKey()} min={fmt.todayKey()} required autoFocus />}
        </Field>
      </BulkStep>
    ),
    assign: (
      <BulkStep
        submitLabel={`Give ${many}`}
        onCancel={() => setStep(null)}
        onSubmit={async (form) => {
          const assigneeId = String(form.get("assigneeId") ?? "");
          if (!assigneeId) return false;
          const name = people.find((p) => p.id === assigneeId)?.name ?? "them";
          await run({ doing: "Reassigning", did: (n) => `${plural(n, ...NOUN)} now with ${name}` }, (ids) =>
            bulkActivities(ids, { action: "assign", assigneeId }),
          );
        }}
      >
        <Field label="Give to" className="w-52">
          {(p) => (
            <Select {...p} name="assigneeId" required defaultValue="" autoFocus>
              <option value="" disabled>
                Pick someone
              </option>
              {people.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </BulkStep>
    ),
  };

  return (
    <BulkBar noun={NOUN} step={step ? steps[step] : undefined}>
      <Button
        size="sm"
        variant="primary"
        loading={running}
        icon={<Check className="size-4" aria-hidden />}
        onClick={() => run({ doing: "Marking done", did: (n) => `${plural(n, ...NOUN)} marked done` }, (ids) => bulkActivities(ids, { action: "done" }))}
      >
        Mark done
      </Button>
      <Button size="sm" disabled={running} onClick={() => setStep("due")}>
        Move date
      </Button>
      {people.length > 1 && (
        <Button size="sm" disabled={running} onClick={openAssign}>
          Reassign
        </Button>
      )}
    </BulkBar>
  );
}
