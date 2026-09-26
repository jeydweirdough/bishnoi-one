"use client";

import { Check, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { approveFunds, declineFunds } from "../../actions/funds";
import type { FundRequest } from "./types";

/** The Team Lead's decision: approve (for as much as asked, or less), or
 *  decline with a reason the requester reads. */
export function Decide({ request, org }: { request: FundRequest; org: Org }) {
  const fmt = makeFormat(org);
  const [amount, setAmount] = useState(fmt.pesosText(request.amountCentavos));
  const [liquidate, setLiquidate] = useState(request.liquidate);
  const [note, setNote] = useState("");
  const [declining, setDeclining] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function approve() {
    const centavos = fmt.toCentavos(amount);
    if (!centavos) {
      setFields({ approvedCentavos: "Enter a valid amount, e.g. 2,500.00." });
      return;
    }
    start(async () => {
      const result = await approveFunds(request.id, { approvedCentavos: centavos, liquidate, note: note.trim() || null });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${request.number} approved`, {
        description: result.data.status === "to_release" ? "Forwarded to Finance for release." : "It will be forwarded to Finance once Finance is reachable.",
      });
    });
  }

  function decline() {
    if (!note.trim()) {
      setFields({ note: "Enter the reason for declining. The requester will see it." });
      return;
    }
    start(async () => {
      const result = await declineFunds(request.id, note.trim());
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${request.number} declined`);
    });
  }

  return (
    <div className="space-y-4">
      {!declining && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={`Approved amount (${fmt.symbol})`} error={fields.approvedCentavos} hint={`Amount requested: ${fmt.peso(request.amountCentavos)}. The approved amount may be lower, but not higher.`}>
            {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input type="checkbox" checked={liquidate} onChange={(e) => setLiquidate(e.target.checked)} className="size-4 accent-hema" />
            Subject to liquidation
          </label>
        </div>
      )}
      <Field label={declining ? "Reason for declining" : "Remarks"} optional={!declining} error={fields.note}>
        {(p) => <Textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} className="min-h-16" />}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        {declining ? (
          <>
            <Button variant="danger" loading={pending} icon={<X className="size-4" aria-hidden />} onClick={decline}>
              Decline
            </Button>
            <Button variant="quiet" onClick={() => setDeclining(false)}>
              Back
            </Button>
          </>
        ) : (
          <>
            <Button variant="primary" loading={pending} icon={<Check className="size-4" aria-hidden />} onClick={approve}>
              Approve
            </Button>
            <Button variant="quiet" onClick={() => setDeclining(true)}>
              Decline…
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
