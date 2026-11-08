"use client";

import { Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Choice, Field, FormError, FormGrid, Input, Select, Textarea } from "@/src/modules/finance/platform/ui/field";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { savePettyCash } from "@/src/modules/finance/petty-cash/actions";
import { ReceiptSlot } from "@/src/modules/finance/petty-cash/receipt-slot";
import type { PettyCashChoices, PettyCashVoucher } from "@/src/modules/finance/petty-cash/types";

type Line = {
  key: number;
  /** A saved line keeps its id, and with it its receipt file. */
  id?: string;
  spentOn: string;
  store: string;
  storeTin: string;
  receiptNumber: string;
  accountId: string;
  description: string;
  purchaseType: string;
  vat: string;
  withholding: string;
  amount: string;
};

const blank = (key: number): Line => ({ key, spentOn: "", store: "", storeTin: "", receiptNumber: "", accountId: "", description: "", purchaseType: "", vat: "", withholding: "", amount: "" });

/**
 * A petty cash voucher, as the paper one reads: its number, the fund it's paid from, the date, who
 * spent it, then a line for each official receipt. Saved as a draft first; each saved line then
 * takes the photo or PDF of its receipt, and the voucher is submitted from its own page once every
 * receipt is attached. The totals are a guide while typing; the API works it out when it's saved.
 */
export function PettyCashEditor({ voucher, choices, org, today }: { voucher: PettyCashVoucher | null; choices: PettyCashChoices; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [v, setV] = useState({
    number: voucher?.number ?? "",
    fundAccountId: voucher?.fund.id ?? (choices.funds.filter((f) => f.active).length === 1 ? choices.funds.find((f) => f.active)!.id : ""),
    voucherDate: voucher?.voucherDate ?? today,
    personInCharge: voucher?.personInCharge ?? "",
    department: voucher?.department ?? "",
    includeVat: voucher ? (voucher.amountsIncludeVat ? "yes" : "no") : "yes",
    notes: voucher?.notes ?? "",
  });
  const [lines, setLines] = useState<Line[]>(
    voucher?.lines.length
      ? voucher.lines.map((l, i) => ({
          key: i,
          id: l.id,
          spentOn: l.spentOn,
          store: l.store,
          storeTin: l.storeTin ?? "",
          receiptNumber: l.receiptNumber,
          accountId: l.account.id,
          description: l.description ?? "",
          purchaseType: l.purchaseType,
          vat: l.vat,
          withholding: l.withholding ?? "",
          amount: fmt.pesosText(l.amountCentavos),
        }))
      : [blank(0)],
  );
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const set = (patch: Partial<typeof v>) => setV({ ...v, ...patch });
  const setLine = (key: number, patch: Partial<Line>) => setLines(lines.map((l) => (l.key === key ? { ...l, ...patch } : l)));
  // The receipt file comes from the saved voucher (refreshed after each attach), not from what's typed.
  const savedFile = (id?: string) => (id ? (voucher?.lines.find((l) => l.id === id)?.file ?? null) : null);
  const editable = !voucher || voucher.canEdit;

  // A guide while typing (12%): the API works the voucher out exactly when it's saved.
  const guide = lines.reduce(
    (t, l) => {
      const amount = fmt.toCentavos(l.amount) ?? 0;
      const base = l.vat === "vat" && v.includeVat === "yes" ? Math.round(amount / 1.12) : amount;
      const vat = l.vat === "vat" ? (v.includeVat === "yes" ? amount - base : Math.round(amount * 0.12)) : 0;
      const rate = choices.withholding.find((w) => w.code === l.withholding)?.rateBp ?? 0;
      return { net: t.net + base, vat: t.vat + vat, held: t.held + Math.round((base * rate) / 10_000) };
    },
    { net: 0, vat: 0, held: 0 },
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const problems: Record<string, string> = {};
    if (!v.number.trim()) problems.number = "Enter the number on the paper voucher.";
    if (!v.fundAccountId) problems.fundAccountId = "Pick the petty cash fund it was paid from.";
    if (!v.voucherDate) problems.voucherDate = "Pick the voucher's date.";
    lines.forEach((l, i) => {
      if (!l.spentOn) problems[`lines.${i}.spentOn`] = "Pick the receipt's date.";
      else if (v.voucherDate && l.spentOn > v.voucherDate) problems[`lines.${i}.spentOn`] = "A receipt can't be dated after its voucher.";
      if (!l.store.trim()) problems[`lines.${i}.store`] = "Enter the store or payee on the receipt.";
      if (!l.receiptNumber.trim()) problems[`lines.${i}.receiptNumber`] = "Enter the official receipt's number. No official receipt, no entry.";
      if (!l.accountId) problems[`lines.${i}.accountId`] = "Pick an account.";
      if (!l.purchaseType) problems[`lines.${i}.purchaseType`] = "Pick the purchase type.";
      if (!l.vat) problems[`lines.${i}.vat`] = "Pick the VAT on the receipt.";
      if (!fmt.toCentavos(l.amount)) problems[`lines.${i}.amountCentavos`] = "Enter the amount.";
    });
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const result = await savePettyCash(voucher?.id ?? null, {
        number: v.number.trim(),
        fundAccountId: v.fundAccountId,
        voucherDate: v.voucherDate,
        personInCharge: v.personInCharge.trim() || null,
        department: v.department.trim() || null,
        notes: v.notes.trim() || null,
        amountsIncludeVat: v.includeVat === "yes",
        lines: lines.map((l) => ({
          ...(l.id ? { id: l.id } : {}),
          spentOn: l.spentOn,
          store: l.store.trim(),
          storeTin: l.storeTin.trim() || null,
          receiptNumber: l.receiptNumber.trim(),
          accountId: l.accountId,
          description: l.description.trim() || null,
          purchaseType: l.purchaseType,
          vat: l.vat,
          withholding: l.withholding || null,
          amountCentavos: fmt.toCentavos(l.amount) ?? 0,
        })),
      });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const missing = result.data.missingReceipts;
      toast.success("Saved as a draft", {
        description: missing ? `Next: attach the receipt on ${missing === 1 ? "1 line" : `each of the ${missing} lines`}, then submit it for checking.` : "Every receipt is attached: submit it for checking.",
      });
      router.push(`/finance/petty-cash/${result.data.id}`);
    });
  }

  const accountsBy = (type: "expense" | "asset") => choices.accounts.filter((a) => a.type === type);
  const fundChoices = choices.funds.filter((f) => f.active || f.id === v.fundAccountId);

  return (
    <form onSubmit={submit} noValidate className="space-y-5">
      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <p className="text-sm text-ink-2">
          <span className="font-semibold text-ink">Step 1 of 3 · The voucher.</span> Copy what&apos;s on the paper petty cash voucher.
        </p>
        <FormGrid>
          <Field label="Paper voucher number" size="sm" error={fields.number} hint="As printed on the paper voucher, for example 2MG PCV 01682.">
            {(p) => <Input {...p} value={v.number} onChange={(e) => set({ number: e.target.value })} maxLength={60} placeholder="2MG PCV 01682" />}
          </Field>
          <Field
            label="Paid from"
            size="sm"
            error={fields.fundAccountId}
            hint={
              fundChoices.length ? undefined : (
                <>
                  No petty cash fund yet: an active account under Cash named Petty Cash is needed.{" "}
                  <Link href="/finance/ledger/accounts" className="font-semibold text-hema hover:underline">
                    Chart of accounts
                  </Link>
                </>
              )
            }
          >
            {(p) => (
              <Select {...p} value={v.fundAccountId} onChange={(e) => set({ fundAccountId: e.target.value })} placeholder="Pick a fund">
                {fundChoices.map((f) => (
                  <option key={f.id} value={f.id} disabled={!f.active}>
                    {f.code} · {f.name}
                    {f.active ? "" : " (switched off)"}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Voucher date" size="sm" error={fields.voucherDate}>
            {(p) => <Input {...p} type="date" max={today} value={v.voucherDate} onChange={(e) => set({ voucherDate: e.target.value })} />}
          </Field>
          <Field label="Person in charge" size="md" optional error={fields.personInCharge} hint="Who spent the money and holds the receipts.">
            {(p) => <Input {...p} list="petty-cash-people" value={v.personInCharge} onChange={(e) => set({ personInCharge: e.target.value })} maxLength={120} autoComplete="off" />}
          </Field>
          <Field label="Department" size="md" optional error={fields.department}>
            {(p) => <Input {...p} list="petty-cash-departments" value={v.department} onChange={(e) => set({ department: e.target.value })} maxLength={120} autoComplete="off" />}
          </Field>
        </FormGrid>
        <datalist id="petty-cash-people">
          {choices.people.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        <datalist id="petty-cash-departments">
          {choices.departments.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </section>

      <section className="space-y-4 rounded-[3px] border border-rule bg-sheet p-5">
        <p className="text-sm text-ink-2">
          <span className="font-semibold text-ink">Step 2 of 3 · The receipts.</span> One line for each official receipt. Every line needs its receipt number;
          without an official receipt it can&apos;t be entered.
        </p>
        <Choice
          name="includeVat"
          legend="The amounts below"
          value={v.includeVat}
          onChange={(includeVat) => set({ includeVat })}
          options={[
            { value: "yes", label: "Include VAT (as on the receipts)" },
            { value: "no", label: "Are before VAT" },
          ]}
        />
        <ol className="space-y-4">
          {lines.map((l, i) => {
            const err = (name: string) => fields[`lines.${i}.${name}`];
            const file = savedFile(l.id);
            return (
              <li key={l.key} className="rounded-[3px] border border-rule p-4">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold">Receipt {i + 1}</p>
                  {lines.length > 1 && (
                    <Button size="sm" variant="quiet" className="!text-ink-3 hover:!text-danger" icon={<Trash2 className="size-4" aria-hidden />} onClick={() => setLines(lines.filter((x) => x.key !== l.key))}>
                      Remove line
                    </Button>
                  )}
                </div>
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_15rem]">
                  <FormGrid>
                    <Field label="Receipt date" size="sm" error={err("spentOn")}>
                      {(p) => <Input {...p} type="date" max={v.voucherDate || today} value={l.spentOn} onChange={(e) => setLine(l.key, { spentOn: e.target.value })} />}
                    </Field>
                    <Field label="OR / receipt number" size="sm" error={err("receiptNumber")}>
                      {(p) => <Input {...p} value={l.receiptNumber} onChange={(e) => setLine(l.key, { receiptNumber: e.target.value })} maxLength={60} placeholder="OR 004512" />}
                    </Field>
                    <Field label="Amount" size="sm" error={err("amountCentavos")}>
                      {(p) => <Input {...p} inputMode="decimal" prefix={fmt.symbol} value={l.amount} onChange={(e) => setLine(l.key, { amount: e.target.value })} className="tabular-nums" />}
                    </Field>
                    <Field label="Store or payee" size="md" error={err("store")}>
                      {(p) => <Input {...p} value={l.store} onChange={(e) => setLine(l.key, { store: e.target.value })} maxLength={200} />}
                    </Field>
                    <Field label="Store TIN" size="md" optional error={err("storeTin")} hint="As printed on the receipt, with its branch code if shown.">
                      {(p) => <Input {...p} value={l.storeTin} onChange={(e) => setLine(l.key, { storeTin: e.target.value })} maxLength={20} placeholder="000-000-000-00000" />}
                    </Field>
                    <Field label="Account" size="md" error={err("accountId")}>
                      {(p) => (
                        <Select {...p} value={l.accountId} onChange={(e) => setLine(l.key, { accountId: e.target.value })} placeholder="Type to find an account">
                          {(["expense", "asset"] as const).map((t) =>
                            accountsBy(t).length ? (
                              <optgroup key={t} label={t === "expense" ? "Expenses" : "Assets"}>
                                {accountsBy(t).map((a) => (
                                  <option key={a.id} value={a.id}>
                                    {a.code} · {a.name}
                                  </option>
                                ))}
                              </optgroup>
                            ) : null,
                          )}
                        </Select>
                      )}
                    </Field>
                    <Field label="Description" size="md" optional error={err("description")}>
                      {(p) => <Input {...p} value={l.description} onChange={(e) => setLine(l.key, { description: e.target.value })} maxLength={200} placeholder="Taxi to the BIR office" />}
                    </Field>
                    <Field label="Purchase type" size="sm" error={err("purchaseType")}>
                      {(p) => (
                        <Select {...p} value={l.purchaseType} onChange={(e) => setLine(l.key, { purchaseType: e.target.value })} placeholder="Pick one">
                          {choices.purchaseTypes.map((k) => (
                            <option key={k.key} value={k.key}>
                              {k.label}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field label="VAT" size="sm" error={err("vat")}>
                      {(p) => (
                        <Select {...p} value={l.vat} onChange={(e) => setLine(l.key, { vat: e.target.value })} placeholder="Pick one">
                          {choices.vatKinds.map((k) => (
                            <option key={k.key} value={k.key}>
                              {k.label}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field label="Tax withheld" size="sm" optional error={err("withholding")}>
                      {(p) => (
                        <Select {...p} value={l.withholding} onChange={(e) => setLine(l.key, { withholding: e.target.value })}>
                          <option value="">None</option>
                          {choices.withholding.map((w) => (
                            <option key={w.code} value={w.code}>
                              {w.code} · {w.rateBp / 100}% · {w.name}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                  </FormGrid>
                  <div className="rounded-[3px] bg-bench/60 p-3">
                    <p className="mb-2 text-meta font-semibold text-ink-2">Step 3 · Its receipt</p>
                    {voucher && l.id && editable ? (
                      <ReceiptSlot voucherId={voucher.id} lineId={l.id} position={i + 1} file={file} />
                    ) : (
                      <p className="text-meta text-ink-3">Save the voucher first, then attach a photo or PDF of this receipt here.</p>
                    )}
                    {file && <p className="mt-2 truncate text-meta text-ink-2">Attached: {file.name}</p>}
                  </div>
                </div>
                {err("id") && <p className="mt-2 text-meta text-danger">{err("id")}</p>}
              </li>
            );
          })}
        </ol>
        <Button size="sm" variant="quiet" className="-ml-3" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([...lines, blank(Math.max(...lines.map((l) => l.key)) + 1)])}>
          Add a receipt
        </Button>
        <div className="ml-auto max-w-sm space-y-1 text-sm">
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">Before VAT</span>
            <span className="tabular-nums">{fmt.peso(guide.net)}</span>
          </p>
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">VAT (input)</span>
            <span className="tabular-nums">{fmt.peso(guide.vat)}</span>
          </p>
          <p className="flex justify-between gap-6 font-semibold">
            <span>Voucher total</span>
            <span className="tabular-nums">{fmt.peso(guide.net + guide.vat)}</span>
          </p>
          <p className="flex justify-between gap-6">
            <span className="text-ink-2">Tax withheld (EWT)</span>
            <span className="tabular-nums">({fmt.peso(guide.held)})</span>
          </p>
          <p className="flex justify-between gap-6 border-t border-ink pt-1 font-semibold">
            <span>Paid out of the fund</span>
            <span className="tabular-nums">{fmt.peso(guide.net + guide.vat - guide.held)}</span>
          </p>
          <p className="text-meta text-ink-3">A guide while typing; worked out exactly when it&apos;s saved.</p>
        </div>
      </section>

      <section className="rounded-[3px] border border-rule bg-sheet p-5">
        <Field label="Notes" optional error={fields.notes}>
          {(p) => <Textarea {...p} value={v.notes} onChange={(e) => set({ notes: e.target.value })} maxLength={500} />}
        </Field>
      </section>

      <FormError message={error} />
      <p className="text-meta text-ink-2">
        {voucher ? "Save your changes, then submit it for checking from the voucher's page once every receipt is attached." : "Save, then attach each receipt: every line gets an Attach receipt button once the voucher is saved."}
      </p>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {voucher ? "Save changes" : "Save as draft"}
        </Button>
        <Button type="button" variant="quiet" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
