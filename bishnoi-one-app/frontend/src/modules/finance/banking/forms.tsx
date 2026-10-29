"use client";

import { Lock, LockOpen, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { closeYear, recordEquity, saveBankAccount, saveRate, setLock } from "@/src/modules/finance/banking/actions";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Choice, Field, FormError, Input, Select } from "@/src/platform/ui/field";

// Banks, payments and equity (feature plan step 16).

export type Provider = { key: string; kind: string; name: string; color: string; initials: string };
export type Bank = { id: string; kind: string; provider: Provider; name: string; accountName: string | null; accountNumber: string | null; currency: string;
                     isDefault: boolean; isActive: boolean; account: { id: string; code: string; name: string } };

/** A bank's or e-wallet's badge: its initials in its colour (no logos copied). */
export function BankBadge({ provider }: { provider: Provider }) {
  return (
    <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-lg text-[0.6875rem] font-bold text-white" style={{ background: provider.color }}>
      {provider.initials}
    </span>
  );
}

export function AddBankAccount({ providers, accounts }: { providers: Provider[]; accounts: { id: string; code: string; name: string }[] }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [open, setOpen] = useState(false);
  const [v, setV] = useState({ provider: "bdo", name: "", accountName: "", accountNumber: "", currency: "PHP", accountId: accounts[0]?.id ?? "", isDefault: false });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  if (!open) return <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>Add a bank account or e-wallet</Button>;
  function save() {
    start(async () => {
      const r = await saveBankAccount(null, { ...v, name: v.name.trim(), accountName: v.accountName.trim() || null, accountNumber: v.accountNumber.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${v.name.trim()} added`);
      setOpen(false);
      router.refresh();
    });
  }
  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="grid gap-4 sm:grid-cols-3">
      <Field label="Bank or e-wallet" error={fields.provider}>
        {(p) => <Select {...p} value={v.provider} onChange={(e) => setV({ ...v, provider: e.target.value })}>{providers.map((x) => <option key={x.key} value={x.key}>{x.name}</option>)}</Select>}
      </Field>
      <Field label="Name" error={fields.name} hint="As people will see it, e.g. BDO Savings 1234.">{(p) => <Input {...p} value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} maxLength={120} />}</Field>
      <Field label="Ledger account" error={fields.accountId} hint="The asset account its money is kept in.">
        {(p) => <Select {...p} value={v.accountId} onChange={(e) => setV({ ...v, accountId: e.target.value })}>{accounts.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}</Select>}
      </Field>
      <Field label="Account name" optional error={fields.accountName}>{(p) => <Input {...p} value={v.accountName} onChange={(e) => setV({ ...v, accountName: e.target.value })} maxLength={160} />}</Field>
      <Field label="Account or mobile number" optional error={fields.accountNumber}>{(p) => <Input {...p} value={v.accountNumber} onChange={(e) => setV({ ...v, accountNumber: e.target.value })} maxLength={40} />}</Field>
      <Field label="Currency" error={fields.currency}>{(p) => <Select {...p} value={v.currency} onChange={(e) => setV({ ...v, currency: e.target.value })}><option value="PHP">PHP</option><option value="USD">USD</option></Select>}</Field>
      <label className="flex items-center gap-2 text-sm sm:col-span-3"><input suppressHydrationWarning type="checkbox" checked={v.isDefault} onChange={(e) => setV({ ...v, isDefault: e.target.checked })} /> The usual one for its kind</label>
      <div className="sm:col-span-3"><FormError message={error} /><div className="flex gap-2"><Button type="submit" variant="primary" loading={busy}>Save</Button><Button variant="quiet" onClick={() => setOpen(false)}>Cancel</Button></div></div>
    </form>
  );
}

export function BankActions({ bank }: { bank: Bank }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const run = (input: Record<string, unknown>, done: string) =>
    start(async () => {
      const r = await saveBankAccount(bank.id, input);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
      router.refresh();
    });
  return (
    <span className="flex gap-1">
      {!bank.isDefault && bank.isActive && <Button size="sm" variant="quiet" disabled={busy} onClick={() => run({ isDefault: true }, `${bank.name} is the usual one`)}>Make usual</Button>}
      <Button size="sm" variant="quiet" disabled={busy} onClick={() => run({ isActive: !bank.isActive }, bank.isActive ? `${bank.name} switched off` : `${bank.name} switched on`)}>
        {bank.isActive ? "Switch off" : "Switch on"}
      </Button>
    </span>
  );
}

export function RateForm({ today }: { today: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [v, setV] = useState({ currency: "USD", on: today, rate: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  function save() {
    start(async () => {
      const r = await saveRate({ currency: v.currency, on: v.on, rate: Number(v.rate) });
      if (!r.ok) return void (setFields(r.fields ?? {}), !r.fields && toast.error(r.error));
      toast.success(`${v.currency} ${v.rate} recorded for ${v.on}`);
      setV({ ...v, rate: "" });
      setFields({});
      router.refresh();
    });
  }
  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="flex flex-wrap items-end gap-3">
      <Field label="Currency" error={fields.currency}>{(p) => <Select {...p} value={v.currency} onChange={(e) => setV({ ...v, currency: e.target.value })}><option>USD</option><option>EUR</option><option>CNY</option><option>SGD</option></Select>}</Field>
      <Field label="Day" error={fields.on}>{(p) => <Input {...p} type="date" max={today} value={v.on} onChange={(e) => setV({ ...v, on: e.target.value })} />}</Field>
      <Field label="Pesos per unit" error={fields.rate}>{(p) => <Input {...p} inputMode="decimal" value={v.rate} onChange={(e) => setV({ ...v, rate: e.target.value })} placeholder="56.1250" className="w-32" />}</Field>
      <Button type="submit" size="sm" loading={busy} disabled={!v.rate}>Record rate</Button>
    </form>
  );
}

export function EquityForm({ banks, today }: { banks: { id: string; name: string }[]; today: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [v, setV] = useState({ kind: "capital" as "capital" | "drawing", amount: "", on: today, bankAccountId: banks[0]?.id ?? "", owner: "", memo: "" });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  function save() {
    const cents = Math.round((Number(v.amount.replace(/,/g, "")) || 0) * 100);
    start(async () => {
      const r = await recordEquity({ kind: v.kind, amountCentavos: cents, on: v.on, bankAccountId: v.bankAccountId, owner: v.owner.trim(), memo: v.memo.trim() || null });
      if (!r.ok) {
        setFields(r.fields ?? {});
        return setError(r.fields ? null : r.error);
      }
      toast.success(`${v.kind === "capital" ? "Capital" : "Drawings"} recorded`, { description: `Journal entry ${r.data.number}.` });
      setV({ ...v, amount: "", memo: "" });
      setError(null);
      router.refresh();
    });
  }
  if (banks.length === 0) return <p className="text-meta text-ink-3">Add the company&apos;s bank accounts first (Banking, Bank accounts): capital comes into one, drawings go out of one.</p>;
  return (
    <form noValidate onSubmit={(e) => (e.preventDefault(), save())} className="space-y-3">
      <Choice name="equityKind" legend="What it is" value={v.kind} onChange={(kind) => setV({ ...v, kind })} options={[{ value: "capital", label: "Capital put in" }, { value: "drawing", label: "Drawings taken out" }]} />
      <div className="grid gap-4 sm:grid-cols-4">
        <Field label="Owner" error={fields.owner}>{(p) => <Input {...p} value={v.owner} onChange={(e) => setV({ ...v, owner: e.target.value })} maxLength={120} />}</Field>
        <Field label="Amount" error={fields.amountCentavos}>{(p) => <Input {...p} inputMode="decimal" prefix="₱" value={v.amount} onChange={(e) => setV({ ...v, amount: e.target.value })} />}</Field>
        <Field label="Date" error={fields.on}>{(p) => <Input {...p} type="date" max={today} value={v.on} onChange={(e) => setV({ ...v, on: e.target.value })} />}</Field>
        <Field label={v.kind === "capital" ? "Into" : "Out of"} error={fields.bankAccountId}>
          {(p) => <Select {...p} value={v.bankAccountId} onChange={(e) => setV({ ...v, bankAccountId: e.target.value })}>{banks.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}</Select>}
        </Field>
      </div>
      <FormError message={error} />
      <Button type="submit" size="sm" variant="primary" loading={busy} disabled={!v.amount || !v.owner.trim()}>Record</Button>
    </form>
  );
}

export function CloseYear({ yearEnd, label }: { yearEnd: string; label: string }) {
  const router = useRouter();
  return (
    <ConfirmButton
      label="Close the year"
      icon={<Lock className="size-4" aria-hidden />}
      triggerVariant="primary"
      triggerSize="sm"
      danger={false}
      title={`Close the fiscal year ended ${label}?`}
      body="Its income and expenses move to retained earnings and its drawings to capital, in one entry dated its last day; then the books lock up to that day."
      confirmLabel="Close and lock"
      onConfirm={async () => {
        const r = await closeYear(yearEnd, true);
        if (!r.ok) {
          toast.error(r.error);
          return false;
        }
        toast.success("Year closed and locked", { description: `Net income ${(r.data.netIncomeCentavos / 100).toLocaleString("en-PH", { minimumFractionDigits: 2 })} moved to retained earnings.` });
        router.refresh();
      }}
    />
  );
}

export function LockForm({ lockedUntil, today }: { lockedUntil: string | null; today: string }) {
  const router = useRouter();
  const [busy, start] = useTransition();
  const [day, setDay] = useState(lockedUntil ?? "");
  const run = (value: string | null, done: string) =>
    start(async () => {
      const r = await setLock(value);
      if (!r.ok) return void toast.error(r.error);
      toast.success(done);
      router.refresh();
    });
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="Closed up to">{(p) => <Input {...p} type="date" max={today} value={day} onChange={(e) => setDay(e.target.value)} />}</Field>
      <Button size="sm" icon={<Lock className="size-4" aria-hidden />} loading={busy} disabled={!day || day === lockedUntil} onClick={() => run(day, `Books closed up to ${day}`)}>Lock</Button>
      {lockedUntil && <Button size="sm" variant="quiet" icon={<LockOpen className="size-4" aria-hidden />} disabled={busy} onClick={() => run(null, "Books open again")}>Open the books</Button>}
    </div>
  );
}
