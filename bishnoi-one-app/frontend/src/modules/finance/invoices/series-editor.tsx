"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input } from "@/src/modules/finance/platform/ui/field";
import { addSeries, switchSeries } from "@/src/modules/finance/invoices/actions";

/** A new run of numbers, as the BIR's Authority to Print states it. */
export function AddSeries({ today }: { today: string }) {
  const [open, setOpen] = useState(false);
  const [v, setV] = useState({ name: "Sales invoices", prefix: "", digits: "6", first: "", last: "", atp: "", atpDate: today });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!open) {
    return (
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        Add a series
      </Button>
    );
  }
  function submit(e: React.FormEvent) {
    e.preventDefault();
    start(async () => {
      const result = await addSeries({
        name: v.name.trim(),
        prefix: v.prefix.trim(),
        digits: Number(v.digits) || 6,
        firstNumber: Number(v.first),
        lastNumber: Number(v.last),
        atpNumber: v.atp.trim(),
        atpDate: v.atpDate,
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Series added");
      setOpen(false);
    });
  }
  const put = (k: keyof typeof v) => (e: React.ChangeEvent<HTMLInputElement>) => setV({ ...v, [k]: e.target.value });
  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
      <p className="text-sm font-semibold">New series from the Authority to Print</p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Name" error={fields.name}>
          {(p) => <Input {...p} value={v.name} onChange={put("name")} maxLength={80} />}
        </Field>
        <Field label="ATP number" error={fields.atpNumber} hint="Or the permit number, for invoices a system prints.">
          {(p) => <Input {...p} value={v.atp} onChange={put("atp")} maxLength={40} />}
        </Field>
        <Field label="Date issued" error={fields.atpDate}>
          {(p) => <Input {...p} type="date" value={v.atpDate} onChange={put("atpDate")} />}
        </Field>
        <Field label="First number" error={fields.firstNumber}>
          {(p) => <Input {...p} inputMode="numeric" value={v.first} onChange={put("first")} placeholder="1" />}
        </Field>
        <Field label="Last number" error={fields.lastNumber}>
          {(p) => <Input {...p} inputMode="numeric" value={v.last} onChange={put("last")} placeholder="5000" />}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Prefix" optional error={fields.prefix}>
            {(p) => <Input {...p} value={v.prefix} onChange={put("prefix")} maxLength={10} placeholder="SI-" />}
          </Field>
          <Field label="Digits" error={fields.digits}>
            {(p) => <Input {...p} inputMode="numeric" value={v.digits} onChange={put("digits")} />}
          </Field>
        </div>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Add series
        </Button>
        <Button type="button" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function SwitchSeries({ id, isActive }: { id: string; isActive: boolean }) {
  const [pending, start] = useTransition();
  return (
    <Button
      size="sm"
      loading={pending}
      onClick={() =>
        start(async () => {
          const result = await switchSeries(id, !isActive);
          if (!result.ok) toast.error(result.error);
        })
      }
    >
      {isActive ? "Deactivate" : "Activate"}
    </Button>
  );
}
