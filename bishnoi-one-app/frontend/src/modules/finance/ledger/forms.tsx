"use client";

import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { ConfirmButton } from "@/src/modules/finance/platform/ui/confirm";
import { CellInput, Field, FormError, FormGrid, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { postEntry, reverseEntry, saveAccount, savePosting } from "@/src/modules/finance/ledger/actions";
import { TYPE_LABELS, type Account, type AccountType, type Posting } from "@/src/modules/finance/ledger/types";

/** Accounts for a picker, grouped by type, active ones only. */
function AccountOptions({ accounts, only }: { accounts: Account[]; only?: AccountType }) {
  return (
    <>
      {(Object.keys(TYPE_LABELS) as AccountType[])
        .filter((t) => !only || t === only)
        .map((t) => {
          const of = accounts.filter((a) => a.type === t && a.isActive);
          return of.length ? (
            <optgroup key={t} label={TYPE_LABELS[t]}>
              {of.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.code} · {a.name}
                </option>
              ))}
            </optgroup>
          ) : null;
        })}
    </>
  );
}

type Line = { key: number; accountId: string; debit: string; credit: string; description: string };
const blank = (key: number): Line => ({ key, accountId: "", debit: "", credit: "", description: "" });

/** A manual journal: a date, a memo, and lines whose debits equal their credits. */
export function JournalForm({ accounts, org, today }: { accounts: Account[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(today);
  const [memo, setMemo] = useState("");
  const [reference, setReference] = useState("");
  const [lines, setLines] = useState<Line[]>([blank(0), blank(1)]);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const cents = (t: string) => (t.trim() ? fmt.toCentavos(t) : 0);
  const debits = lines.reduce((n, l) => n + (cents(l.debit) ?? 0), 0);
  const credits = lines.reduce((n, l) => n + (cents(l.credit) ?? 0), 0);
  const set = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const used = lines.filter((l) => l.accountId || l.debit.trim() || l.credit.trim());
    const problems: Record<string, string> = {};
    if (!memo.trim()) problems.memo = "Enter a memo for the entry.";
    if (used.length < 2) problems.lines = "A journal entry needs at least two lines.";
    used.forEach((l, i) => {
      const d = cents(l.debit), c = cents(l.credit);
      if (!l.accountId) problems[`lines.${i}.accountId`] = "Select an account.";
      if (d === null || c === null || (d > 0) === (c > 0)) problems[`lines.${i}.debitCentavos`] = "Enter either a debit or a credit.";
    });
    if (!problems.lines && debits !== credits) problems.lines = `Debits (${fmt.peso(debits)}) and credits (${fmt.peso(credits)}) must be equal.`;
    if (Object.keys(problems).length) {
      setFields(problems);
      setError(problems.lines ?? "Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await postEntry({
        date,
        memo: memo.trim(),
        reference: reference.trim() || null,
        lines: used.map((l) => ({ accountId: l.accountId, debitCentavos: cents(l.debit) ?? 0, creditCentavos: cents(l.credit) ?? 0, description: l.description.trim() || null })),
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(`${result.data.number} posted`, { description: "Waiting for approval: it counts in the books once someone else approves it." });
      setOpen(false);
      setMemo("");
      setReference("");
      setLines([blank(0), blank(1)]);
      setFields({});
      setError(null);
    });
  }

  if (!open) {
    return (
      <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
        New manual journal
      </Button>
    );
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-[3px] border border-rule bg-sheet p-4">
      <p className="text-sm font-semibold">New manual journal</p>
      <div className="grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)_12rem]">
        <Field label="Date" error={fields.date}>
          {(p) => <Input {...p} type="date" max={today} value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Memo" error={fields.memo}>
          {(p) => <Input {...p} value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="Accrual of September utilities" maxLength={300} />}
        </Field>
        <Field label="Reference" optional error={fields.reference}>
          {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}
        </Field>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="py-1.5 pr-2 font-semibold">Account</th>
              <th className="px-2 py-1.5 font-semibold">Description</th>
              <th className="w-32 px-2 py-1.5 text-right font-semibold">Debit</th>
              <th className="w-32 px-2 py-1.5 text-right font-semibold">Credit</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={l.key} className="align-top">
                <td className="py-1.5 pr-2">
                  <select suppressHydrationWarning
                    aria-label={`Line ${i + 1}: account`}
                    aria-invalid={fields[`lines.${i}.accountId`] ? true : undefined}
                    value={l.accountId}
                    onChange={(e) => set(l.key, { accountId: e.target.value })}
                    className="h-8 w-full rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm aria-[invalid=true]:border-danger"
                  >
                    <option value="">Select an account…</option>
                    <AccountOptions accounts={accounts} />
                  </select>
                </td>
                <td className="px-2 py-1.5">
                  <CellInput aria-label={`Line ${i + 1}: description`} value={l.description} onChange={(e) => set(l.key, { description: e.target.value })} className="w-full !text-left" />
                </td>
                <td className="px-2 py-1.5">
                  <CellInput aria-label={`Line ${i + 1}: debit`} inputMode="decimal" value={l.debit} onChange={(e) => set(l.key, { debit: e.target.value, credit: e.target.value ? "" : l.credit })} className="w-full" aria-invalid={fields[`lines.${i}.debitCentavos`] ? true : undefined} />
                </td>
                <td className="px-2 py-1.5">
                  <CellInput aria-label={`Line ${i + 1}: credit`} inputMode="decimal" value={l.credit} onChange={(e) => set(l.key, { credit: e.target.value, debit: e.target.value ? "" : l.debit })} className="w-full" />
                </td>
                <td className="py-1.5">
                  {lines.length > 2 && (
                    <Button size="sm" variant="quiet" className="!px-1.5 !text-ink-3 hover:!text-danger" aria-label={`Remove line ${i + 1}`} onClick={() => setLines(lines.filter((x) => x.key !== l.key))}>
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-rule font-semibold tabular-nums">
              <td className="py-2">
                <Button size="sm" variant="quiet" className="-ml-3" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([...lines, blank(Math.max(...lines.map((l) => l.key)) + 1)])}>
                  Add a line
                </Button>
              </td>
              <td className="px-2 py-2 text-right text-ink-2">Totals</td>
              <td className="px-2 py-2 text-right">{fmt.peso(debits)}</td>
              <td className="px-2 py-2 text-right">{fmt.peso(credits)}</td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
      {/* Typing in one side clears the other on purpose: a line is one side of the entry (found confusing in testing, 2026-10-22). */}
      <p className="text-meta text-ink-3">Each line is either a debit or a credit: typing in one clears the other. Pick an account on every line.</p>
      {debits !== credits && debits + credits > 0 && <p className="text-meta text-due-today">Out of balance by {fmt.peso(Math.abs(debits - credits))}.</p>}
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          Post entry
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** Undoing a posted entry: a new entry with every line's side swapped. */
export function ReverseButton({ id, number }: { id: string; number: string }) {
  return (
    <ConfirmButton
      label="Reverse"
      icon={<RotateCcw className="size-3.5" aria-hidden />}
      triggerVariant="quiet"
      triggerSize="sm"
      title={`Reverse ${number}?`}
      body="A reversing entry dated today is posted with every debit and credit swapped. Like any entry typed by hand, it counts once someone else approves it. The original entry remains in the journal; entries are never edited or deleted."
      confirmLabel="Post reversal"
      onConfirm={async () => {
        const result = await reverseEntry(id);
        if (!result.ok) {
          toast.error(result.error);
          return false;
        }
        toast.success(`${result.data.number} posted`, { description: `Reverses ${number} once it's approved.` });
      }}
    />
  );
}

/** A type's accounts in order, each under its parent (when the parent is the same type), with its depth. */
function nested(of: Account[]): { a: Account; depth: number }[] {
  const ids = new Set(of.map((a) => a.id));
  const children = new Map<string | null, Account[]>();
  for (const a of of) {
    const key = a.parentId && ids.has(a.parentId) ? a.parentId : null;
    children.set(key, [...(children.get(key) ?? []), a]);
  }
  const out: { a: Account; depth: number }[] = [];
  const seen = new Set<string>();
  const walk = (parent: string | null, depth: number) => {
    for (const a of children.get(parent) ?? []) {
      if (seen.has(a.id)) continue;
      seen.add(a.id);
      out.push({ a, depth });
      walk(a.id, Math.min(depth + 1, 4));
    }
  };
  walk(null, 0);
  return out;
}

/** The chart of accounts, by type, with adding and changing an account. */
export function ChartEditor({ accounts, canEdit, importer }: { accounts: Account[]; canEdit: boolean; importer?: React.ReactNode }) {
  const [editing, setEditing] = useState<Account | "new" | null>(null);
  const names = new Map(accounts.map((a) => [a.id, a]));
  return (
    <div className="space-y-5">
      {canEdit &&
        (editing ? (
          <AccountForm key={editing === "new" ? "new" : editing.id} account={editing === "new" ? null : editing} accounts={accounts} onDone={() => setEditing(null)} />
        ) : (
          <div className="flex flex-wrap items-start gap-2">
            <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
              Add an account
            </Button>
            {importer}
          </div>
        ))}
      {(Object.keys(TYPE_LABELS) as AccountType[]).map((t) => {
        const of = accounts.filter((a) => a.type === t);
        if (!of.length) return null;
        return (
          <section key={t}>
            <h2 className="mb-1 text-caps text-ink-3 uppercase">{TYPE_LABELS[t]}</h2>
            <ul className="divide-y divide-rule border-y border-rule">
              {nested(of).map(({ a, depth }) => (
                <li key={a.id} className={`flex items-center gap-3 py-2 ${a.isActive ? "" : "text-ink-3"}`} style={{ paddingLeft: `${depth * 1.25}rem` }}>
                  <span className="w-20 shrink-0 font-mono text-meta tabular-nums text-ink-2">{a.code}</span>
                  {/* Under a parent of another type (Oojeema's chart has some): said, since it can't be shown by place. */}
                  {a.parentId && names.get(a.parentId)?.type !== a.type && (
                    <span className="hidden text-meta text-ink-3 sm:inline">under {names.get(a.parentId)?.name} ·</span>
                  )}
                  <a href={`/finance/ledger/accounts/${a.id}`} className="min-w-0 flex-1 truncate text-sm font-medium hover:text-hema hover:underline">
                    {a.name}
                    {!a.isActive && <span className="ml-2 text-meta font-normal">inactive</span>}
                  </a>
                  {canEdit && (
                    <Button size="sm" variant="quiet" className="!px-1.5" aria-label={`Edit ${a.name}`} onClick={() => setEditing(a)}>
                      <Pencil className="size-3.5" aria-hidden />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function AccountForm({ account, accounts, onDone }: { account: Account | null; accounts: Account[]; onDone: () => void }) {
  const [code, setCode] = useState(account?.code ?? "");
  const [name, setName] = useState(account?.name ?? "");
  const [type, setType] = useState<AccountType>(account?.type ?? "expense");
  const [description, setDescription] = useState(account?.description ?? "");
  const [isActive, setActive] = useState(account?.isActive ?? true);
  const [parentId, setParentId] = useState(account?.parentId ?? "");
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    start(async () => {
      const result = await saveAccount(account?.id ?? null, { code: code.trim(), name: name.trim(), type, description: description.trim() || null, isActive, parentId: parentId || null });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(account ? "Account saved" : "Account added", { description: `${result.data.code} · ${result.data.name}` });
      onDone();
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-[3px] border border-rule p-4">
      <div className="grid gap-4 sm:grid-cols-[8rem_minmax(0,1fr)_12rem]">
        <Field label="Account code" error={fields.code}>
          {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} placeholder="6150" autoFocus />}
        </Field>
        <Field label="Account name" error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="Representation expense" />}
        </Field>
        <Field label="Account type" error={fields.type}>
          {(p) => (
            <Select {...p} value={type} onChange={(e) => setType(e.target.value as AccountType)}>
              {(Object.keys(TYPE_LABELS) as AccountType[]).map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t]}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <FormGrid>
        <Field label="Description" size="md" optional error={fields.description}>
          {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <Field label="Sits under" size="md" optional error={fields.parentId} hint="The account it's grouped under, as in Oojeema's chart.">
          {(p) => (
            <Select {...p} value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">Nothing (at the top)</option>
              <AccountOptions accounts={accounts.filter((a) => a.id !== account?.id)} />
            </Select>
          )}
        </Field>
      </FormGrid>
      <label className="flex items-center gap-2 text-sm">
        <input suppressHydrationWarning type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
        Active (available for new entries)
      </label>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {account ? "Save" : "Add account"}
        </Button>
        <Button variant="quiet" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** Which accounts the marketing request steps post to. */
export function PostingEditor({ posting, accounts }: { posting: Posting; accounts: Account[] }) {
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(posting.items.map((i) => [i.key, i.account?.id ?? ""])));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await savePosting(Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v || null])));
          if (!result.ok) {
            setError(result.error);
            setFields(result.fields ?? {});
            return;
          }
          setError(null);
          setFields({});
          toast.success("Default accounts saved");
        });
      }}
      className="space-y-4"
    >
      <FormGrid>
        {posting.items.map((i) => (
          <Field key={i.key} label={i.label} size="md" error={fields[i.key]}>
            {(p) => (
              <Select {...p} value={values[i.key]} disabled={!posting.canEdit} onChange={(e) => setValues({ ...values, [i.key]: e.target.value })}>
                <option value="">Not set</option>
                <AccountOptions accounts={accounts} only={i.type} />
              </Select>
            )}
          </Field>
        ))}
      </FormGrid>
      <FormError message={error} />
      {posting.canEdit && (
        <Button type="submit" variant="primary" loading={pending}>
          Save default accounts
        </Button>
      )}
    </form>
  );
}
