"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import type { Deal, DealLists, DealStage } from "@/src/platform/lib/types";
import { deleteDeal, loseDeal, reopenDeal, winDeal } from "../../actions/deals";

type Step = null | "win" | "lose" | "reopen";

/**
 * Closing a deal, and opening it again. Won can name the quote that won it
 * (its total becomes the deal's value); lost asks why, from the list an
 * administrator keeps, and optionally to whom.
 */
export function DealClose({
  deal,
  lists,
  stages,
  quotes,
  today,
}: {
  deal: Deal;
  lists: DealLists;
  stages: DealStage[];
  /** The deal's approved quotes, which can be what won it. */
  quotes: { id: string; label: string }[];
  today: string;
}) {
  const router = useRouter();
  const [step, setStep] = useState<Step>(null);
  const [pending, start] = useTransition();
  const [quoteId, setQuoteId] = useState(quotes[0]?.id ?? "");
  const [reason, setReason] = useState("");
  const [competitor, setCompetitor] = useState("");
  const open = stages.filter((s) => s.outcome === "open" && s.isActive);
  const [stageCode, setStageCode] = useState(open[0]?.code ?? "");
  const [closeOn, setCloseOn] = useState(today);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function run(work: () => Promise<{ ok: boolean; error?: string; fields?: Record<string, string> }>, done: string) {
    start(async () => {
      const result = await work();
      if (!result.ok) {
        setError(result.error ?? "Something went wrong. Try again.");
        setFields(result.fields ?? {});
        return;
      }
      toast.success(done);
      setStep(null);
      setError(null);
      setFields({});
      router.refresh();
    });
  }

  const remove = deal.can.delete && (
    <ConfirmButton
      label="Delete"
      triggerVariant="quiet"
      icon={<Trash2 className="size-4" aria-hidden />}
      title={`Delete ${deal.name}?`}
      body={deal.quotes.length ? "Its quotes stay; they just won't be for a deal any more. This can't be undone." : "This can't be undone."}
      confirmLabel="Delete deal"
      onConfirm={async () => {
        const result = await deleteDeal(deal.id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success("Deal deleted");
        router.push("/deals");
        router.refresh();
      }}
    />
  );

  if (!deal.can.edit) return remove || null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {deal.state === "open" ? (
          <>
            <Button variant={step === "win" ? "primary" : "default"} onClick={() => setStep(step === "win" ? null : "win")}>
              Mark won
            </Button>
            <Button variant={step === "lose" ? "primary" : "default"} onClick={() => setStep(step === "lose" ? null : "lose")}>
              Mark lost
            </Button>
          </>
        ) : (
          <Button variant={step === "reopen" ? "primary" : "default"} onClick={() => setStep(step === "reopen" ? null : "reopen")}>
            Reopen
          </Button>
        )}
        {remove}
      </div>

      {step && (
        <form
          noValidate
          className="space-y-4 border-t border-rule pt-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (step === "win") run(() => winDeal(deal.id, quoteId || null), "Deal won");
            else if (step === "lose") {
              if (!reason) {
                setFields({ reason: "Say why it was lost." });
                return;
              }
              run(() => loseDeal(deal.id, reason, competitor.trim() || null), "Deal marked lost");
            } else run(() => reopenDeal(deal.id, stageCode || null, closeOn), "Deal reopened");
          }}
        >
          <FormError message={error} />
          {step === "win" && (
            <Field
              label="Won with"
              error={fields.quoteId}
              hint={quotes.length ? "The quote's total becomes the deal's value." : "No approved quote is linked to this deal; it's won at its expected value."}
            >
              {(p) => (
                <Select {...p} value={quoteId} onChange={(e) => setQuoteId(e.target.value)}>
                  <option value="">No quote: keep the expected value</option>
                  {quotes.map((q) => (
                    <option key={q.id} value={q.id}>
                      {q.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          )}
          {step === "lose" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Loss reason" error={fields.reason}>
                {(p) => (
                  <Select {...p} value={reason} onChange={(e) => setReason(e.target.value)}>
                    <option value="">Select a reason</option>
                    {lists.lostReasons.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Competitor" optional error={fields.competitor} hint="The competitor that won the deal, if known.">
                {(p) => <Input {...p} value={competitor} onChange={(e) => setCompetitor(e.target.value)} maxLength={120} />}
              </Field>
            </div>
          )}
          {step === "reopen" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Reopen at stage" error={fields.stageCode}>
                {(p) => (
                  <Select {...p} value={stageCode} onChange={(e) => setStageCode(e.target.value)}>
                    {open.map((s) => (
                      <option key={s.code} value={s.code}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Expected close date" error={fields.expectedCloseOn}>
                {(p) => <Input {...p} type="date" value={closeOn} onChange={(e) => setCloseOn(e.target.value)} />}
              </Field>
            </div>
          )}
          <div className="flex gap-3">
            <Button type="submit" variant="primary" loading={pending}>
              {step === "win" ? "Mark won" : step === "lose" ? "Mark lost" : "Reopen deal"}
            </Button>
            <Button type="button" variant="quiet" onClick={() => setStep(null)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
