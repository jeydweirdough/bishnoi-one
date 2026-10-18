"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { toBasisPoints } from "@/src/platform/lib/format";
import { addTaxRate } from "./actions";
import type { TaxCode } from "./types";

/**
 * A change in the law, entered ahead of an update: a new rate from a day on.
 * The rate before it ends the day before, so sales before that day keep
 * theirs.
 */
export function RateChangeForm({ codes, today }: { codes: TaxCode[]; today: string }) {
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();
  const rated = codes.filter((c) => c.rated);
  const [code, setCode] = useState(rated[0]?.code ?? "");
  const [rate, setRate] = useState("");
  const [from, setFrom] = useState(today);
  const [basis, setBasis] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} icon={<Plus className="size-4" aria-hidden />}>
        Enter a rate change
      </Button>
    );
  }

  function submit() {
    const rateBp = toBasisPoints(rate);
    if (rateBp === null) return setFields({ rateBp: "A percent, like 12." });
    start(async () => {
      const result = await addTaxRate({ code, rateBp, validFrom: from, basis: basis.trim() });
      if (result.ok) {
        toast.success("Rate change saved", { description: `From ${from}` });
        setOpen(false);
        setRate("");
        setBasis("");
        setError(null);
        setFields({});
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4 rounded-[3px] border border-rule p-4"
    >
      <p className="text-sm text-ink-2">
        For a change in the law. Sales before the day you give keep the old rate; sales from that day on get the new one.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Tax" error={fields.code}>
          {(f) => (
            <Select {...f} value={code} onChange={(e) => setCode(e.target.value)}>
              {rated.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="New rate (%)" error={fields.rateBp}>
          {(f) => <Input {...f} inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="12" />}
        </Field>
        <Field label="Effective date" error={fields.validFrom}>
          {(f) => <Input {...f} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}
        </Field>
        <Field label="Legal basis" error={fields.basis} className="sm:col-span-3">
          {(f) => <Input {...f} value={basis} onChange={(e) => setBasis(e.target.value)} placeholder="RA 00000, sec. 00" />}
        </Field>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Save rate change
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
