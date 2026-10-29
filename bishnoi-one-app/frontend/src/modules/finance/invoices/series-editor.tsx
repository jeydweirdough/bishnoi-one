"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, FormGrid, Input } from "@/src/modules/finance/platform/ui/field";
import { addSeries, setAutoInvoice, switchSeries } from "@/src/modules/finance/invoices/actions";
import { Choice } from "@/src/platform/ui/field";

/** Invoices from deliveries (step 13): issued at once from the series, or made as drafts for Finance to check and issue. */
export function AutoInvoiceSetting({ value, canChange }: { value: "issue" | "draft"; canChange: boolean }) {
  const [current, setCurrent] = useState(value);
  const [pending, start] = useTransition();
  function change(next: "issue" | "draft") {
    if (!canChange || next === current) return;
    start(async () => {
      const r = await setAutoInvoice(next);
      if (!r.ok) return void toast.error(r.error);
      setCurrent(next);
      toast.success(next === "issue" ? "Deliveries' invoices are issued at once" : "Deliveries' invoices wait for Finance to issue");
    });
  }
  return (
    <div aria-busy={pending}>
      <Choice
        name="autoInvoice"
        legend="When a customer's delivery leaves the warehouse"
        value={current}
        onChange={change}
        options={[{ value: "issue", label: "Issue its invoice at once" }, { value: "draft", label: "Make a draft for Finance" }]}
      />
      <p className="mt-1.5 text-meta text-ink-3">
        Either way the invoice has the sale&apos;s lines, prices and VAT, and a shipping fee charged to the customer. One that can&apos;t be issued by itself waits under From deliveries to check.
      </p>
    </div>
  );
}

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
      <FormGrid>
        <Field label="Name" size="lg" error={fields.name}>
          {(p) => <Input {...p} value={v.name} onChange={put("name")} maxLength={80} />}
        </Field>
        <Field label="ATP number" size="sm" error={fields.atpNumber} hint="Or the permit number, for invoices a system prints.">
          {(p) => <Input {...p} value={v.atp} onChange={put("atp")} maxLength={40} />}
        </Field>
        <Field label="Date issued" size="sm" error={fields.atpDate}>
          {(p) => <Input {...p} type="date" value={v.atpDate} onChange={put("atpDate")} />}
        </Field>
        <Field label="First number" size="sm" error={fields.firstNumber}>
          {(p) => <Input {...p} inputMode="numeric" value={v.first} onChange={put("first")} placeholder="1" />}
        </Field>
        <Field label="Last number" size="sm" error={fields.lastNumber}>
          {(p) => <Input {...p} inputMode="numeric" value={v.last} onChange={put("last")} placeholder="5000" />}
        </Field>
        <>
          <Field label="Prefix" size="sm" optional error={fields.prefix}>
            {(p) => <Input {...p} value={v.prefix} onChange={put("prefix")} maxLength={10} placeholder="SI-" />}
          </Field>
          <Field label="Digits" size="sm" error={fields.digits}>
            {(p) => <Input {...p} inputMode="numeric" value={v.digits} onChange={put("digits")} />}
          </Field>
        </>
      </FormGrid>
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
