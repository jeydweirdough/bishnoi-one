"use client";

import { Check, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Textarea } from "@/src/platform/ui/field";
import { decideEntry } from "./actions";

/** Approve a journal entry waiting for approval, or reject it with a reason the
 *  person who posted it is told. If someone else decided it a moment earlier, the
 *  message says who and when, and the page shows the entry as it now stands. */
export function DecideEntry({ id, number }: { id: string; number: string }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function send(decision: "approve" | "reject") {
    if (decision === "reject" && !reason.trim()) return setError("Enter the reason for rejection.");
    setError(null);
    start(async () => {
      const result = await decideEntry(id, decision, decision === "reject" ? reason.trim() : null);
      // A toast, not the form's error line: the page is redrawn, and this form goes once the entry is decided.
      if (!result.ok) return void toast.error(result.error);
      toast.success(decision === "approve" ? `${number} approved` : `${number} rejected`, {
        description: decision === "approve" ? "It now counts in the books." : "Whoever posted it is told why.",
      });
    });
  }

  if (rejecting) {
    return (
      <div className="mt-2 w-full space-y-2 sm:max-w-sm">
        <Field label="Reason for rejection" hint="Whoever posted it sees this, and posts a corrected entry.">
          {(p) => <Textarea {...p} rows={2} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />}
        </Field>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button variant="danger" size="sm" loading={pending} onClick={() => send("reject")}>
            Reject
          </Button>
          <Button variant="quiet" size="sm" disabled={pending} onClick={() => (setRejecting(false), setError(null))}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-2">
      <Button variant="primary" size="sm" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={() => send("approve")}>
        Approve
      </Button>
      <Button size="sm" disabled={pending} icon={<X className="size-4" aria-hidden />} onClick={() => setRejecting(true)}>
        Reject
      </Button>
    </div>
  );
}
