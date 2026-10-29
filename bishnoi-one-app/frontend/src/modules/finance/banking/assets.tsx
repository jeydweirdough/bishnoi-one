"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { addFixedAsset, deleteBudget, disposeAsset, runDepreciation, saveBudget } from "@/src/modules/finance/banking/actions";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";

// Fixed assets and budgets (feature plan step 17).

type Acc = { id: string; code: string; name: string; type: string };
const toCents = (v: string) => Math.round((Number(v.replace(/,/g, "")) || 0) * 100);

export function AddAsset({ accounts, today }: { accounts: Acc[]; today: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [open, setOpen] = useState(false);
  const assets = accounts.filter((a) => a.type === "asset");
  const expenses = accounts.filter((a) => a.type === "expense");
  const [v, setV] = useState({ name: "", cost: "", salvage: "", acquiredOn: today, years: "5", assetAccountId: assets[0]?.id ?? "", accumulatedAccountId: assets[0]?.id ?? "", expenseAccountId: expenses[0]?.id ?? "", divisionName: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  if (!open) return <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>Add a fixed asset</Button>;
  function save() {
    start(async () => {
      const r = await addFixedAsset({ name: v.name.trim(), costCentavos: toCents(v.cost), salvageCentavos: toCents(v.salvage), acquiredOn: v.acquiredOn,
        usefulMonths: Math.round((Number(v.years) || 0) * 12), assetAccountId: v.assetAccountId, accumulatedAccountId: v.accumulatedAccountId,
        expenseAccountId: v.expenseAccountId, divisionName: v.divisionName.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${v.name.trim()} added`, { description: "Depreciated each month from the month after it was bought." });
      setOpen(false);
      router.refresh();
    });
  }
  const opts = (list: Acc[]) => list.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>);
  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="grid gap-4 sm:grid-cols-3">
      <Field label="Asset" error={fields.name}>{(p) => <Input {...p} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} maxLength={160} placeholder="Delivery van, ABC 1234" />}</Field>
      <Field label="Cost" error={fields.costCentavos}>{(p) => <Input {...p} inputMode="decimal" prefix="₱" value={v.cost} onChange={(e) => setV({ ...v, cost: e.target.value })} />}</Field>
      <Field label="Worth at the end" optional error={fields.salvageCentavos}>{(p) => <Input {...p} inputMode="decimal" prefix="₱" value={v.salvage} onChange={(e) => setV({ ...v, salvage: e.target.value })} placeholder="0.00" />}</Field>
      <Field label="Bought on" error={fields.acquiredOn}>{(p) => <Input {...p} type="date" max={today} value={v.acquiredOn} onChange={(e) => setV({ ...v, acquiredOn: e.target.value })} />}</Field>
      <Field label="Useful life (years)" error={fields.usefulMonths}>{(p) => <Input {...p} inputMode="decimal" value={v.years} onChange={(e) => setV({ ...v, years: e.target.value })} />}</Field>
      <Field label="Division" optional>{(p) => <Input {...p} value={v.divisionName} onChange={(e) => setV({ ...v, divisionName: e.target.value })} maxLength={120} />}</Field>
      <Field label="Kept in (asset account)" error={fields.assetAccountId}>{(p) => <Select {...p} value={v.assetAccountId} onChange={(e) => setV({ ...v, assetAccountId: e.target.value })}>{opts(assets)}</Select>}</Field>
      <Field label="Accumulated depreciation" error={fields.accumulatedAccountId}>{(p) => <Select {...p} value={v.accumulatedAccountId} onChange={(e) => setV({ ...v, accumulatedAccountId: e.target.value })}>{opts(assets)}</Select>}</Field>
      <Field label="Depreciation expense" error={fields.expenseAccountId}>{(p) => <Select {...p} value={v.expenseAccountId} onChange={(e) => setV({ ...v, expenseAccountId: e.target.value })}>{opts(expenses)}</Select>}</Field>
      <div className="sm:col-span-3"><FormError message={error} /><div className="flex gap-2"><Button type="submit" variant="primary" loading={busy}>Save</Button><Button variant="quiet" onClick={() => setOpen(false)}>Cancel</Button></div></div>
    </form>
  );
}

export function Depreciate({ today }: { today: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [through, setThrough] = useState(today);
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="Depreciate up to">{(p) => <Input {...p} type="date" max={today} value={through} onChange={(e) => setThrough(e.target.value)} />}</Field>
      <Button
        loading={busy}
        onClick={() =>
          start(async () => {
            const r = await runDepreciation(through);
            if (!r.ok) return void toast.error(r.error);
            toast.success(r.data.entries.length ? `${r.data.entries.length} month${r.data.entries.length === 1 ? "" : "s"} depreciated` : "Nothing more to depreciate up to then");
            router.refresh();
          })
        }
      >
        Post depreciation
      </Button>
    </div>
  );
}

export function DisposeAsset({ id, name }: { id: string; name: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <Button size="sm" variant="quiet" disabled={busy} onClick={() => start(async () => {
      const r = await disposeAsset(id);
      if (!r.ok) return void toast.error(r.error);
      toast.success(`${name} disposed`, { description: "Record its sale or write-off as a journal entry." });
      router.refresh();
    })}>
      Disposed of
    </Button>
  );
}

export function BudgetLine({ yearEnd, accounts }: { yearEnd: string; accounts: Acc[] }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const list = accounts.filter((a) => a.type === "income" || a.type === "expense");
  const [v, setV] = useState({ accountId: list[0]?.id ?? "", divisionName: "", yearly: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  function save() {
    start(async () => {
      const r = await saveBudget({ yearEnd, accountId: v.accountId, divisionName: v.divisionName.trim() || null, yearlyCentavos: toCents(v.yearly) });
      if (!r.ok) return void (setFields(r.fields ?? {}), !r.fields && toast.error(r.error));
      toast.success("Budget saved", { description: "Spread evenly over the twelve months." });
      setV({ ...v, yearly: "" });
      setFields({});
      router.refresh();
    });
  }
  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="flex flex-wrap items-end gap-3">
      <Field label="Account" error={fields.accountId}>{(p) => <Select {...p} value={v.accountId} onChange={(e) => setV({ ...v, accountId: e.target.value })}>{list.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}</Select>}</Field>
      <Field label="Division" optional>{(p) => <Input {...p} value={v.divisionName} onChange={(e) => setV({ ...v, divisionName: e.target.value })} maxLength={120} className="w-40" />}</Field>
      <Field label="For the year" error={fields.yearlyCentavos}>{(p) => <Input {...p} inputMode="decimal" prefix="₱" value={v.yearly} onChange={(e) => setV({ ...v, yearly: e.target.value })} className="w-40" />}</Field>
      <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!v.yearly}>Save</Button>
    </form>
  );
}

export function RemoveBudget({ id }: { id: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  return (
    <button suppressHydrationWarning type="button" title="Remove this budget line" disabled={busy} className="rounded-md p-1 text-ink-3 hover:text-danger"
      onClick={() => start(async () => {
        const r = await deleteBudget(id);
        if (!r.ok) return void toast.error(r.error);
        router.refresh();
      })}>
      <Trash2 className="size-4" aria-hidden />
      <span className="sr-only">Remove</span>
    </button>
  );
}
