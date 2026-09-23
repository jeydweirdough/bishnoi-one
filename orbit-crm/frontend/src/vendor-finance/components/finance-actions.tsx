"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { checkLetter, decideApproval, recordPayment, type Decision } from "../actions";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org, Quote } from "@/src/platform/lib/types";

type Decide = (id: string, input: Decision) => Promise<{ ok: true } | { ok: false; error: string }>;

/**
 * Yes / no on something waiting for Finance. Yes is the one solid button on the
 * page, so it's found first; no is quieter and needs a reason, so the rep knows
 * what to fix.
 */
function DecisionButtons({ quote, what, yes, decide, org }: { quote: Quote; what: string; yes: string; decide: Decide; org: Org }) {
  const fmt = makeFormat(org);
  const [note, setNote] = useState("");
  const noteField = (placeholder: string) => (
    <Textarea
      aria-label="Note"
      value={note}
      onChange={(e) => setNote(e.target.value)}
      rows={3}
      maxLength={1000}
      placeholder={placeholder}
      className="mt-3"
    />
  );
  const run = async (decision: Decision["decision"]) => {
    if (decision === "reject" && !note.trim()) {
      toast.error("Say why, so the rep knows what to fix.");
      return false;
    }
    const result = await decide(quote.id, { decision, note: note.trim() || null });
    if (!result.ok) {
      toast.error(result.error);
      return false;
    }
    setNote("");
    toast.success(decision === "approve" ? `${yes}: ${quote.number}` : `Rejected: ${quote.number}`);
  };
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <ConfirmButton
        label={yes}
        triggerVariant="primary"
        title={`${yes}: ${what}?`}
        body={
          <>
            <p>
              {quote.customerName} · {fmt.peso(quote.totalCentavos)}
            </p>
            {noteField("Note for the rep (optional)")}
          </>
        }
        confirmLabel={yes}
        danger={false}
        onConfirm={() => run("approve")}
      />
      <ConfirmButton
        label="Reject"
        triggerVariant="quiet"
        title={`Reject ${what}?`}
        body={
          <>
            <p>The rep sees your reason on the quote.</p>
            {noteField("Why? e.g. the discount is too deep; 10% at most")}
          </>
        }
        confirmLabel="Reject"
        onConfirm={() => run("reject")}
      />
    </div>
  );
}

/** Record what the issuer paid, right under what's been paid so far. */
export function PaymentForm({ quote, org }: { quote: Quote; org: Org }) {
  if (!quote.can.recordPayment) return null;
  return <PaymentFields quote={quote} org={org} />;
}

function PaymentFields({ quote, org }: { quote: Quote; org: Org }) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const left = (quote.letter?.amountCentavos ?? 0) - quote.payment.paidCentavos;
  const today = fmt.todayKey();

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const amountCentavos = fmt.toCentavos(String(data.get("amount") ?? ""));
    if (!amountCentavos) {
      setFields({ amountCentavos: "Enter an amount like 1,250.00." });
      return;
    }
    const input = {
      paidOn: String(data.get("paidOn") ?? ""),
      amountCentavos,
      reference: String(data.get("reference") ?? "").trim() || null,
    };
    start(async () => {
      const result = await recordPayment(quote.id, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${fmt.peso(amountCentavos)} recorded on ${quote.number}`);
      form.reset();
      setError(null);
      setFields({});
    });
  }

  return (
    <form onSubmit={submit} noValidate className="mt-3 space-y-3">
      <p className="text-meta font-semibold text-ink-2">
        Record a payment <span className="font-normal text-ink-3">· {fmt.peso(left)} left on the letter</span>
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Paid on" error={fields.paidOn}>
          {(p) => <Input {...p} name="paidOn" type="date" defaultValue={today} max={today} />}
        </Field>
        <Field label="Amount" error={fields.amountCentavos}>
          {(p) => <Input {...p} name="amount" inputMode="decimal" defaultValue={(left / 100).toFixed(2)} className="text-right" />}
        </Field>
      </div>
      <Field label="Reference" optional error={fields.reference}>
        {(p) => <Input {...p} name="reference" maxLength={80} placeholder="Check or OR number" />}
      </Field>
      <FormError message={error} />
      <Button type="submit" size="sm" variant="primary" loading={pending}>
        Record payment
      </Button>
    </form>
  );
}

// Each decision sits in the part of the quote it decides; `quote.can` says what the API allows now.

export function ApprovalActions({ quote, org }: { quote: Quote; org: Org }) {
  if (!quote.can.approve) return null;
  return <DecisionButtons quote={quote} org={org} what={`${quote.priceTypeName} quote ${quote.number}`} yes="Approve" decide={decideApproval} />;
}

export function LetterActions({ quote, org }: { quote: Quote; org: Org }) {
  if (!quote.can.checkLetter) return null;
  return <DecisionButtons quote={quote} org={org} what={`the letter on ${quote.number}`} yes="Verify" decide={checkLetter} />;
}
