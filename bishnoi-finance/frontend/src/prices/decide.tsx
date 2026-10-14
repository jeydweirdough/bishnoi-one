"use client";

import { Check, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Textarea } from "@/src/platform/ui/field";
import type { Result } from "@/src/platform/lib/result";
import { decidePrice, decideQuote } from "./actions";
import type { WaitingPrice } from "./types";

type Decide = (d: { decision: "approve" | "reject"; reason: string | null }) => Promise<Result<{ ok: boolean }>>;

/** Approve at once; reject only with a reason, which the person who asked sees. */
function Decision({ decide, what, rejectHint }: { decide: Decide; what: string; rejectHint: string }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function send(decision: "approve" | "reject") {
    if (decision === "reject" && !reason.trim()) return setError("Say why it's rejected.");
    setError(null);
    start(async () => {
      const result = await decide({ decision, reason: decision === "reject" ? reason.trim() : null });
      if (!result.ok) return setError(result.error);
      toast.success(decision === "approve" ? `${what}: approved` : `${what}: rejected`);
    });
  }

  if (rejecting) {
    return (
      <div className="w-full space-y-2 sm:max-w-sm">
        <Field label="Why it's rejected" hint={rejectHint}>
          {(p) => <Textarea {...p} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />}
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
    <div className="space-y-1.5">
      <div className="flex gap-2">
        <Button variant="primary" size="sm" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={() => send("approve")}>
          Approve
        </Button>
        <Button size="sm" disabled={pending} icon={<X className="size-4" aria-hidden />} onClick={() => setRejecting(true)}>
          Reject
        </Button>
      </div>
      <FormError message={error} />
    </div>
  );
}

export function DecidePrice({ price }: { price: WaitingPrice }) {
  return (
    <Decision
      decide={(d) => decidePrice(price, d)}
      what={`${price.productName} ${price.priceTypeName}`}
      rejectHint={price.currentAmountCentavos ? "The price in use now stays." : "The product keeps no price of this kind."}
    />
  );
}

export function DecideQuote({ id, number }: { id: string; number: string }) {
  return <Decision decide={(d) => decideQuote(id, number, d)} what={number} rejectHint="The rep sees your reason on the quote." />;
}
