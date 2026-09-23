"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, Input } from "@/src/platform/ui/field";
import { bulkApprovals } from "../bulk-actions";
import { plural } from "@/src/platform/lib/format";
import { BulkBar, BulkStep, useBulkRun, useSelection } from "@/src/platform/bulk/selection";

const NOUN: [string, string] = ["quote", "quotes"];

/** Finance's approvals, several at once. Guarantee letters and payments stay one at a time: each needs its own look. */
export function ApprovalsBulk() {
  const s = useSelection();
  const { run, running } = useBulkRun();
  const [step, setStep] = useState<"approve" | "reject" | null>(null);
  const many = plural(s.ids.length, ...NOUN);

  const decide = (decision: "approve" | "reject") => (
    <BulkStep
      submitLabel={decision === "approve" ? `Approve ${many}` : `Reject ${many}`}
      danger={decision === "reject"}
      onCancel={() => setStep(null)}
      onSubmit={async (form) => {
        const note = String(form.get("note") ?? "").trim() || null;
        if (decision === "reject" && !note) {
          toast.error("Say why, so the reps know what to fix.");
          return false;
        }
        const did = decision === "approve" ? "approved" : "rejected";
        await run({ doing: decision === "approve" ? "Approving" : "Rejecting", did: (n) => `${plural(n, ...NOUN)} ${did}` }, (ids) =>
          bulkApprovals(ids, { decision, note }),
        );
      }}
    >
      <Field label={decision === "approve" ? "Note" : "Why"} optional={decision === "approve"} className="w-72">
        {(p) => (
          <Input
            {...p}
            name="note"
            maxLength={1000}
            required={decision === "reject"}
            placeholder={decision === "approve" ? "Goes on each quote" : "The reps see this on each quote"}
            autoFocus
          />
        )}
      </Field>
    </BulkStep>
  );

  return (
    <BulkBar noun={NOUN} step={step ? decide(step) : undefined}>
      <Button size="sm" variant="primary" disabled={running} onClick={() => setStep("approve")}>
        Approve
      </Button>
      <Button size="sm" disabled={running} onClick={() => setStep("reject")}>
        Reject
      </Button>
    </BulkBar>
  );
}
