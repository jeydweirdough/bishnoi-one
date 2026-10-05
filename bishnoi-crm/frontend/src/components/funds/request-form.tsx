"use client";

import { X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { askForFunds } from "../../actions/funds";
import { findCustomers } from "../../actions/crm";
import type { FundPurpose } from "./types";

/** Asking for money: what it's for, how much, by when, and for whom. */
export function RequestForm({ purposes, org, today }: { purposes: FundPurpose[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [purposeId, setPurposeId] = useState(purposes[0]?.id ?? "");
  const [amount, setAmount] = useState("");
  const [neededOn, setNeededOn] = useState("");
  const [details, setDetails] = useState("");
  const [customer, setCustomer] = useState<{ id: string; name: string } | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const purpose = purposes.find((p) => p.id === purposeId);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const problems: Record<string, string> = {};
    const centavos = fmt.toCentavos(amount);
    if (!purposeId) problems.purposeId = "Select a purpose.";
    if (!centavos) problems.amountCentavos = "Enter a valid amount, e.g. 2,500.00.";
    if (!details.trim()) problems.details = "Enter the details for your Team Lead's review.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await askForFunds({ purposeId, amountCentavos: centavos!, neededOn: neededOn || null, details: details.trim(), companyId: customer?.id ?? null });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Request submitted", { description: `${result.data.number} is now for your Team Lead's approval.` });
      router.push(`/funds/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <fieldset>
        <legend className="mb-2 text-meta font-medium text-ink-2">Purpose</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {purposes.map((p) => (
            <label
              key={p.id}
              className="flex cursor-pointer gap-3 rounded-[6px] border border-rule-strong px-3 py-2.5 has-checked:border-hema has-checked:bg-hema-tint has-focus-visible:outline-2 has-focus-visible:outline-hema"
            >
              <input type="radio" name="purpose" value={p.id} checked={purposeId === p.id} onChange={() => setPurposeId(p.id)} className="mt-1 accent-hema" />
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{p.name}</span>
                {p.description && <span className="block text-meta text-ink-3">{p.description}</span>}
                <span className="mt-0.5 block text-meta text-ink-2">{p.liquidate ? "Subject to liquidation" : "Not subject to liquidation"}</span>
              </span>
            </label>
          ))}
        </div>
        {fields.purposeId && <p className="mt-1 text-meta text-danger">{fields.purposeId}</p>}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={`Amount (${fmt.symbol})`} error={fields.amountCentavos}>
          {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0.00" />}
        </Field>
        <Field label="Date needed" optional error={fields.neededOn} hint="When the cash advance must be released.">
          {(p) => <Input {...p} type="date" min={today} value={neededOn} onChange={(e) => setNeededOn(e.target.value)} />}
        </Field>
      </div>

      <CustomerPick value={customer} onChange={setCustomer} error={fields.companyId} />

      <Field
        label="Details"
        error={fields.details}
        hint={purpose?.liquidate ? "Business purpose and attendees. After spending, you submit a liquidation with the official receipts and refund any excess." : "Business purpose and attendees."}
      >
        {(p) => <Textarea {...p} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Dinner with Dr. Reyes and two clinic staff, to present the new antibiotic line." />}
      </Field>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Submit for approval
        </Button>
        <Button variant="quiet" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** The customer it's for, found by name. Optional: not every request is for one. */
function CustomerPick({ value, onChange, error }: { value: { id: string; name: string } | null; onChange: (c: { id: string; name: string } | null) => void; error?: string }) {
  const [words, setWords] = useState("");
  const [found, setFound] = useState<{ id: string; name: string }[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function search(text: string) {
    setWords(text);
    if (timer.current) clearTimeout(timer.current);
    if (text.trim().length < 2) return setFound([]);
    timer.current = setTimeout(async () => {
      const result = await findCustomers(text.trim());
      setFound(result.ok ? result.data.slice(0, 8) : []);
    }, 250);
  }

  if (value) {
    return (
      <div>
        <p className="mb-1 text-meta font-medium text-ink-2">Customer</p>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-hema-tint py-1 pr-1.5 pl-3 text-sm text-ink">
          {value.name}
          <button type="button" onClick={() => onChange(null)} className="rounded-full p-0.5 hover:bg-sheet" aria-label={`Not for ${value.name}`}>
            <X className="size-3.5" aria-hidden />
          </button>
        </span>
      </div>
    );
  }
  return (
    <div className="relative">
      <Field label="Customer" optional error={error} hint="The doctor, clinic or partner involved, if any.">
        {(p) => <Input {...p} value={words} onChange={(e) => search(e.target.value)} placeholder="Search by name" autoComplete="off" />}
      </Field>
      {found.length > 0 && (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-[6px] border border-rule bg-sheet shadow-lg">
          {found.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => {
                  onChange(c);
                  setFound([]);
                  setWords("");
                }}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-hema-tint"
              >
                {c.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
