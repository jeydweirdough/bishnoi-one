"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Amount } from "@/src/modules/finance/platform/ui/amount";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { applyAdvance, createAdvance, removeAdvanceApplication, voidAdvance } from "./actions";
import { CustomerPicker } from "./customer-picker";
import type { AdvanceItem } from "./types";

type BankOption = { id: string; name: string; kind: string };
type SupplierOption = { id: string; name: string };
type BillOption = { id: string; no: number | null; billNumber: string; supplierId: string; supplierName: string; owedCentavos: number };
type InvoiceOption = { id: string; number: string; customerName: string; owedCentavos: number };

function toCentavos(v: string): number {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) : 0;
}

export function AdvancesClient({
  org,
  today,
  items,
  banks,
  suppliers,
  bills,
  invoices,
  canPrepare,
  canVoid,
}: {
  org: Org;
  today: string;
  items: AdvanceItem[];
  banks: BankOption[];
  suppliers: SupplierOption[];
  bills: BillOption[];
  invoices: InvoiceOption[];
  canPrepare: boolean;
  canVoid: boolean;
}) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<"supplier" | "customer">("supplier");
  const [partyId, setPartyId] = useState(suppliers[0]?.id ?? "");
  const [customerPartyId, setCustomerPartyId] = useState<string | null>(null);
  const [partyName, setPartyName] = useState("");
  const [advanceDate, setAdvanceDate] = useState(today);
  const [method, setMethod] = useState("bank");
  const [bankAccountId, setBankAccountId] = useState(banks[0]?.id ?? "");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [amountPesos, setAmountPesos] = useState("");

  const [applyForId, setApplyForId] = useState<string | null>(null);
  const [targetId, setTargetId] = useState("");
  const [applyPesos, setApplyPesos] = useState("");

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amountCentavos = toCentavos(amountPesos);
    const resolvedName =
      kind === "supplier" ? suppliers.find((s) => s.id === partyId)?.name ?? partyName.trim() : partyName.trim();
    if (!resolvedName || amountCentavos <= 0) {
      setError("Enter the party and a positive amount.");
      return;
    }
    start(async () => {
      const res = await createAdvance({
        kind,
        partyId: kind === "supplier" ? partyId || null : customerPartyId,
        partyName: resolvedName,
        advanceDate,
        method,
        bankAccountId: bankAccountId || null,
        reference: reference.trim() || null,
        notes: notes.trim() || null,
        amountCentavos,
      });
      if (!res.ok) return setError(res.error);
      toast.success(`Posted ${res.data.number}`);
      setAmountPesos("");
      setReference("");
      setNotes("");
    });
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rule bg-bench px-4 py-3 text-meta text-ink-2">
        <strong className="text-ink">How Advances &amp; Deposits work:</strong> Record money paid early <em>before</em> an invoice or bill arrives (no VAT yet).
        {" "}1. Record the prepayment or deposit → 2. When the final bill or invoice is posted later, click <strong>Apply to bill / invoice</strong> to deduct what was already paid.
      </div>
      {canPrepare && (
        <form onSubmit={onCreate} className="rounded-lg border border-rule bg-sheet p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold text-ink">Record early payment or deposit</h2>
            <div className="flex gap-2">
              <Button type="button" size="sm" variant={kind === "supplier" ? "primary" : "default"} onClick={() => setKind("supplier")}>
                Paid early to supplier (Prepayment)
              </Button>
              <Button type="button" size="sm" variant={kind === "customer" ? "primary" : "default"} onClick={() => setKind("customer")}>
                Received early from customer (Deposit)
              </Button>
            </div>
          </div>

          {kind === "customer" && (
            <CustomerPicker
              onSelect={(c) => {
                setCustomerPartyId(c.id);
                setPartyName(c.name);
              }}
            />
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            {kind === "supplier" ? (
              <Field label="Supplier">
                {(p) => (
                  <Select {...p} value={partyId} onChange={(e) => setPartyId(e.target.value)}>
                    <option value="">Pick supplier…</option>
                    {suppliers.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            ) : (
              <Field label="Customer name">
                {(p) => <Input {...p} value={partyName} onChange={(e) => setPartyName(e.target.value)} placeholder="Customer name" />}
              </Field>
            )}
            <Field label="Date">
              {(p) => <Input {...p} type="date" value={advanceDate} onChange={(e) => setAdvanceDate(e.target.value)} />}
            </Field>
            <Field label="Amount (PHP)">
              {(p) => <Input {...p} type="number" step="0.01" min="0.01" value={amountPesos} onChange={(e) => setAmountPesos(e.target.value)} placeholder="0.00" />}
            </Field>
            <Field label="Method">
              {(p) => (
                <Select {...p} value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="bank">Bank transfer</option>
                  <option value="check">Check</option>
                  <option value="cash">Cash</option>
                  <option value="ewallet">E-wallet</option>
                </Select>
              )}
            </Field>
            <Field label="Bank / Cash account" optional>
              {(p) => (
                <Select {...p} value={bankAccountId} onChange={(e) => setBankAccountId(e.target.value)}>
                  <option value="">Default money account</option>
                  {banks.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Reference" optional>
              {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Check / deposit slip" />}
            </Field>
          </div>
          <Field label="Notes" optional>
            {(p) => <Input {...p} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Downpayment terms or PO reference" />}
          </Field>
          <FormError message={error} />
          <Button type="submit" variant="primary" loading={pending}>
            Post {kind === "supplier" ? "supplier prepayment" : "customer deposit"}
          </Button>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-rule bg-bench text-meta text-ink-2">
            <tr>
              <th className="px-4 py-3">Number</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Party</th>
              <th className="px-4 py-3 text-right">Amount</th>
              <th className="px-4 py-3 text-right">Unapplied</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {items.map((adv) => (
              <tr key={adv.id} className="align-top">
                <td className="px-4 py-3 font-mono font-medium text-ink">{adv.number}</td>
                <td className="px-4 py-3 text-ink-2">{adv.kind === "supplier" ? "Supplier prepayment" : "Customer deposit"}</td>
                <td className="px-4 py-3 text-ink-2">{adv.date}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{adv.partyName}</div>
                  {adv.reference && <div className="text-meta text-ink-3">Ref: {adv.reference}</div>}
                  {adv.applications
                    .filter((a) => !a.removedAt)
                    .map((a) => (
                      <div key={a.id} className="mt-1 flex items-center gap-2 text-meta text-ink-2">
                        <span>Applied {a.appliedOn} to {a.targetKind}:</span>
                        <Amount text={fmt.peso(a.amountCentavos)} />
                        {canVoid && (
                          <button
                            type="button"
                            className="text-danger hover:underline"
                            onClick={() =>
                              start(async () => {
                                const r = await removeAdvanceApplication(adv.id, a.id);
                                if (!r.ok) toast.error(r.error);
                                else toast.success("Application reversed");
                              })
                            }
                          >
                            Unapply
                          </button>
                        )}
                      </div>
                    ))}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  <Amount text={fmt.peso(adv.amountCentavos)} />
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  <Amount text={fmt.peso(adv.remainingCentavos)} />
                </td>
                <td className="px-4 py-3 text-right space-x-2">
                  {adv.status === "posted" && adv.remainingCentavos > 0 && canPrepare && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setApplyForId(applyForId === adv.id ? null : adv.id);
                        setApplyPesos((adv.remainingCentavos / 100).toFixed(2));
                        setTargetId("");
                      }}
                    >
                      Apply to {adv.kind === "supplier" ? "bill" : "invoice"}
                    </Button>
                  )}
                  {adv.status === "posted" && adv.appliedCentavos === 0 && canVoid && (
                    <Button
                      size="sm"
                      onClick={() => {
                        const why = window.prompt("Reason for voiding this advance/deposit?");
                        if (!why || why.trim().length < 3) return;
                        start(async () => {
                          const r = await voidAdvance(adv.id, why.trim());
                          if (!r.ok) toast.error(r.error);
                          else toast.success("Voided and reversed");
                        });
                      }}
                    >
                      Void
                    </Button>
                  )}
                  {applyForId === adv.id && (
                    <div className="mt-2 flex flex-wrap justify-end gap-2 border-t border-rule pt-2">
                      <select
                        className="h-8 rounded border border-control bg-sheet px-2 text-meta"
                        value={targetId}
                        onChange={(e) => setTargetId(e.target.value)}
                      >
                        <option value="">Pick {adv.kind === "supplier" ? "bill" : "invoice"}…</option>
                        {adv.kind === "supplier"
                          ? bills
                              .filter((b) => (!adv.partyId || b.supplierId === adv.partyId) && b.owedCentavos > 0)
                              .map((b) => (
                                <option key={b.id} value={b.id}>
                                  Bill #{b.no} {b.billNumber} ({(b.owedCentavos / 100).toFixed(2)})
                                </option>
                              ))
                          : invoices
                              .filter((i) => i.owedCentavos > 0)
                              .map((i) => (
                                <option key={i.id} value={i.id}>
                                  {i.number} · {i.customerName} ({(i.owedCentavos / 100).toFixed(2)})
                                </option>
                              ))}
                      </select>
                      <input
                        type="number"
                        step="0.01"
                        className="h-8 w-28 rounded border border-control bg-sheet px-2 text-meta"
                        value={applyPesos}
                        onChange={(e) => setApplyPesos(e.target.value)}
                      />
                      <Button
                        size="sm"
                        variant="primary"
                        loading={pending}
                        onClick={() =>
                          start(async () => {
                            const amt = toCentavos(applyPesos);
                            if (!targetId || amt <= 0) return;
                            const r = await applyAdvance(adv.id, { targetId, appliedOn: today, amountCentavos: amt });
                            if (!r.ok) toast.error(r.error);
                            else {
                              toast.success("Advance applied");
                              setApplyForId(null);
                            }
                          })
                        }
                      >
                        Confirm
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-ink-3">
                  No supplier prepayments or customer deposits recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
