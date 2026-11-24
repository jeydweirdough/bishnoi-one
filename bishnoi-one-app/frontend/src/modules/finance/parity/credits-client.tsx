"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/finance/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/modules/finance/platform/ui/field";
import { Amount } from "@/src/modules/finance/platform/ui/amount";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import type { Org } from "@/src/modules/finance/platform/lib/types";
import { CustomerPicker } from "./customer-picker";
import {
  applyCreditNote,
  applyVendorCredit,
  createCreditNote,
  createVendorCredit,
  issueCreditNote,
  recordVendorCredit,
  removeCreditAllocation,
  removeVendorAllocation,
  voidCreditNote,
  voidVendorCredit,
} from "./actions";
import type { CreditNoteItem, VendorCreditItem } from "./types";

type InvoiceChoice = { id: string; number: string; customerName: string; customerTin: string | null; balanceCentavos: number };
type BillChoice = { id: string; no: number | null; billNumber: string; supplierId: string; supplierName: string; owedCentavos: number };
type Option = { id: string; name: string; code?: string };

function pesoCentavos(v: string): number {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? Math.round(n * 100) : 0;
}

export function CreditNotesClient({
  org,
  today,
  items,
  invoices,
  incomeAccounts,
  canCreate,
  canIssue,
  canCollect,
  canVoid,
}: {
  org: Org;
  today: string;
  items: CreditNoteItem[];
  invoices: InvoiceChoice[];
  incomeAccounts: Option[];
  canCreate: boolean;
  canIssue: boolean;
  canCollect: boolean;
  canVoid: boolean;
}) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState("");
  const [customerId, setCustomerId] = useState<string | null>(null);
  const [customerName, setCustomerName] = useState("");
  const [customerTin, setCustomerTin] = useState("");
  const [customerAddress, setCustomerAddress] = useState("");
  const [creditDate, setCreditDate] = useState(today);
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [accountId, setAccountId] = useState(incomeAccounts[0]?.id ?? "");
  const [description, setDescription] = useState("Sales return / credit adjustment");
  const [amountPesos, setAmountPesos] = useState("");

  const [applyId, setApplyId] = useState<string | null>(null);
  const [applyInvId, setApplyInvId] = useState("");
  const [applyPesos, setApplyPesos] = useState("");

  function pickInvoice(id: string) {
    setInvoiceId(id);
    const inv = invoices.find((x) => x.id === id);
    if (inv) {
      setCustomerId(null);
      setCustomerName(inv.customerName);
      setCustomerTin(inv.customerTin ?? "");
    }
  }

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const unitPriceCentavos = pesoCentavos(amountPesos);
    if (!customerName.trim() || unitPriceCentavos <= 0) {
      setError("Enter the customer name and a positive amount.");
      return;
    }
    start(async () => {
      const res = await createCreditNote({
        invoiceId: invoiceId || null,
        customerId,
        customerName: customerName.trim(),
        customerTin: customerTin.trim() || null,
        customerAddress: customerAddress.trim() || null,
        creditDate,
        reference: reference.trim() || null,
        reason: reason.trim() || null,
        lines: [{ accountId: accountId || null, description: description.trim() || "Credit adjustment", quantity: 1, unitPriceCentavos }],
      });
      if (!res.ok) return setError(res.error);
      toast.success("Draft credit note created");
      setAmountPesos("");
      setReason("");
      setReference("");
    });
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rule bg-bench px-4 py-3 text-meta text-ink-2">
        <strong className="text-ink">How Customer Credit Notes work:</strong> Use this when a customer returns items or gets a post-invoice discount.
        {" "}1. Pick the invoice (or search CRM customer) &amp; save draft → 2. Click <strong>Issue</strong> → 3. If not auto-applied yet, click <strong>Apply to invoice</strong> to reduce what they owe.
      </div>
      {canCreate && (
        <form onSubmit={onCreate} className="rounded-lg border border-rule bg-sheet p-5 space-y-4">
          <h2 className="text-base font-semibold text-ink">New customer credit note</h2>
          {!invoiceId && (
            <CustomerPicker
              onSelect={(c) => {
                setCustomerId(c.id);
                setCustomerName(c.name);
                setCustomerTin(c.tin ?? "");
                setCustomerAddress(c.address ?? "");
              }}
            />
          )}
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Against invoice" optional>
              {(p) => (
                <Select {...p} value={invoiceId} onChange={(e) => pickInvoice(e.target.value)}>
                  <option value="">Standalone credit note</option>
                  {invoices.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.number} · {i.customerName}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Customer name">
              {(p) => <Input {...p} value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Customer name" />}
            </Field>
            <Field label="Customer TIN" optional>
              {(p) => <Input {...p} value={customerTin} onChange={(e) => setCustomerTin(e.target.value)} placeholder="000-000-000" />}
            </Field>
            <Field label="Credit date">
              {(p) => <Input {...p} type="date" value={creditDate} onChange={(e) => setCreditDate(e.target.value)} />}
            </Field>
            <Field label="Income account" optional>
              {(p) => (
                <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                  <option value="">Default sales account</option>
                  {incomeAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code ? `${a.code} · ` : ""}
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Amount (PHP, VAT-inclusive default)">
              {(p) => <Input {...p} type="number" step="0.01" min="0.01" value={amountPesos} onChange={(e) => setAmountPesos(e.target.value)} placeholder="0.00" />}
            </Field>
            <Field label="Line description">
              {(p) => <Input {...p} value={description} onChange={(e) => setDescription(e.target.value)} />}
            </Field>
            <Field label="Reference" optional>
              {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Return slip / RMA" />}
            </Field>
            <Field label="Reason" optional>
              {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why this credit is issued" />}
            </Field>
          </div>
          <FormError message={error} />
          <Button type="submit" variant="primary" loading={pending}>
            Save draft credit note
          </Button>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-rule bg-bench text-meta text-ink-2">
            <tr>
              <th className="px-4 py-3">Number</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Customer</th>
              <th className="px-4 py-3 text-right">Total</th>
              <th className="px-4 py-3 text-right">Remaining</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {items.map((cn) => (
              <tr key={cn.id} className="align-top">
                <td className="px-4 py-3 font-mono font-medium text-ink">{cn.number ?? "Draft"}</td>
                <td className="px-4 py-3 text-ink-2">{cn.date}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{cn.customer.name}</div>
                  {cn.reason && <div className="text-meta text-ink-3">{cn.reason}</div>}
                  {cn.allocations.filter((a) => !a.removedAt).length > 0 && (
                    <div className="mt-1 space-y-1 text-meta text-ink-2">
                      {cn.allocations
                        .filter((a) => !a.removedAt)
                        .map((a) => (
                          <div key={a.id} className="flex items-center gap-2">
                            <span>Applied {a.appliedOn}:</span>
                            <Amount text={fmt.peso(a.amountCentavos)} />
                            {canVoid && (
                              <button
                                type="button"
                                className="text-danger hover:underline"
                                onClick={() =>
                                  start(async () => {
                                    const r = await removeCreditAllocation(cn.id, a.id);
                                    if (!r.ok) toast.error(r.error);
                                    else toast.success("Allocation removed");
                                  })
                                }
                              >
                                Unapply
                              </button>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  <Amount text={fmt.peso(cn.totalCentavos)} />
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  <Amount text={fmt.peso(cn.remainingCentavos)} />
                </td>
                <td className="px-4 py-3 capitalize text-ink-2">{cn.status}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  {cn.status === "draft" && canIssue && (
                    <Button
                      size="sm"
                      variant="primary"
                      loading={pending}
                      onClick={() =>
                        start(async () => {
                          const r = await issueCreditNote(cn.id);
                          if (!r.ok) toast.error(r.error);
                          else toast.success(`Issued ${r.data.number}`);
                        })
                      }
                    >
                      Issue
                    </Button>
                  )}
                  {cn.status === "issued" && cn.remainingCentavos > 0 && canCollect && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setApplyId(applyId === cn.id ? null : cn.id);
                        setApplyPesos((cn.remainingCentavos / 100).toFixed(2));
                      }}
                    >
                      Apply to invoice
                    </Button>
                  )}
                  {cn.status === "issued" && cn.appliedCentavos === 0 && canVoid && (
                    <Button
                      size="sm"
                      onClick={() => {
                        const why = window.prompt("Reason for voiding this credit note?");
                        if (!why || why.trim().length < 3) return;
                        start(async () => {
                          const r = await voidCreditNote(cn.id, why.trim());
                          if (!r.ok) toast.error(r.error);
                          else toast.success("Credit note voided");
                        });
                      }}
                    >
                      Void
                    </Button>
                  )}
                  {applyId === cn.id && (
                    <div className="mt-2 flex flex-wrap justify-end gap-2 border-t border-rule pt-2">
                      <select
                        className="h-8 rounded border border-control bg-sheet px-2 text-meta"
                        value={applyInvId}
                        onChange={(e) => setApplyInvId(e.target.value)}
                      >
                        <option value="">Pick invoice…</option>
                        {invoices
                          .filter((i) => i.balanceCentavos > 0)
                          .map((i) => (
                            <option key={i.id} value={i.id}>
                              {i.number} ({(i.balanceCentavos / 100).toFixed(2)})
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
                            const amt = pesoCentavos(applyPesos);
                            if (!applyInvId || amt <= 0) return;
                            const r = await applyCreditNote(cn.id, { invoiceId: applyInvId, appliedOn: today, amountCentavos: amt });
                            if (!r.ok) toast.error(r.error);
                            else {
                              toast.success("Credit applied to invoice");
                              setApplyId(null);
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
                  No credit notes yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function VendorCreditsClient({
  org,
  today,
  items,
  bills,
  suppliers,
  accounts,
  canCreate,
  canApprove,
  canApply,
  canVoid,
}: {
  org: Org;
  today: string;
  items: VendorCreditItem[];
  bills: BillChoice[];
  suppliers: Option[];
  accounts: Option[];
  canCreate: boolean;
  canApprove: boolean;
  canApply: boolean;
  canVoid: boolean;
}) {
  const fmt = makeFormat(org);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [supplierId, setSupplierId] = useState(suppliers[0]?.id ?? "");
  const [billId, setBillId] = useState("");
  const [creditDate, setCreditDate] = useState(today);
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [accountId, setAccountId] = useState(accounts[0]?.id ?? "");
  const [vat, setVat] = useState("vat");
  const [amountPesos, setAmountPesos] = useState("");
  const [applyId, setApplyId] = useState<string | null>(null);
  const [applyBillId, setApplyBillId] = useState("");
  const [applyPesos, setApplyPesos] = useState("");

  function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const amountCentavos = pesoCentavos(amountPesos);
    if (!supplierId || !accountId || !reference.trim() || amountCentavos <= 0) {
      setError("Pick a supplier, expense/asset account, reference, and positive amount.");
      return;
    }
    start(async () => {
      const res = await createVendorCredit({
        supplierId,
        billId: billId || null,
        creditDate,
        reference: reference.trim(),
        reason: reason.trim() || null,
        amountsIncludeVat: true,
        lines: [{ accountId, description: reason.trim() || reference.trim(), amountCentavos, vat, purchaseType: "other_goods" }],
      });
      if (!res.ok) return setError(res.error);
      toast.success("Draft vendor credit saved");
      setAmountPesos("");
      setReference("");
      setReason("");
    });
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-rule bg-bench px-4 py-3 text-meta text-ink-2">
        <strong className="text-ink">How Supplier Vendor Credits work:</strong> Use this when a supplier sends a credit memo for returned goods or overbilling.
        {" "}1. Save the supplier&apos;s memo → 2. Finance Head clicks <strong>Record &amp; post</strong> → 3. Click <strong>Apply to bill</strong> so payment vouchers don&apos;t pay the credited amount twice.
      </div>
      {canCreate && (
        <form onSubmit={onCreate} className="rounded-lg border border-rule bg-sheet p-5 space-y-4">
          <h2 className="text-base font-semibold text-ink">New supplier vendor credit</h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Supplier">
              {(p) => (
                <Select {...p} value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                  <option value="">Pick supplier…</option>
                  {suppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="Against recorded bill" optional>
              {(p) => (
                <Select {...p} value={billId} onChange={(e) => setBillId(e.target.value)}>
                  <option value="">Standalone vendor credit</option>
                  {bills
                    .filter((b) => !supplierId || b.supplierId === supplierId)
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        Bill #{b.no} ({b.billNumber}) · {b.supplierName}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
            <Field label="Supplier credit ref">
              {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} placeholder="Supplier CM #" />}
            </Field>
            <Field label="Credit date">
              {(p) => <Input {...p} type="date" value={creditDate} onChange={(e) => setCreditDate(e.target.value)} />}
            </Field>
            <Field label="Account">
              {(p) => (
                <Select {...p} value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code ? `${a.code} · ` : ""}
                      {a.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="VAT treatment">
              {(p) => (
                <Select {...p} value={vat} onChange={(e) => setVat(e.target.value)}>
                  <option value="vat">VATable (12%)</option>
                  <option value="zero">Zero-rated</option>
                  <option value="exempt">VAT-exempt</option>
                  <option value="none">Non-VAT</option>
                </Select>
              )}
            </Field>
            <Field label="Amount (PHP)">
              {(p) => <Input {...p} type="number" step="0.01" min="0.01" value={amountPesos} onChange={(e) => setAmountPesos(e.target.value)} placeholder="0.00" />}
            </Field>
            <Field label="Reason" optional>
              {(p) => <Input {...p} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Short delivery / price adjustment" />}
            </Field>
          </div>
          <FormError message={error} />
          <Button type="submit" variant="primary" loading={pending}>
            Save draft vendor credit
          </Button>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-rule bg-bench text-meta text-ink-2">
            <tr>
              <th className="px-4 py-3">Number</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Supplier &amp; Ref</th>
              <th className="px-4 py-3 text-right">Credit</th>
              <th className="px-4 py-3 text-right">Remaining</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {items.map((vc) => (
              <tr key={vc.id} className="align-top">
                <td className="px-4 py-3 font-mono font-medium text-ink">{vc.number ?? "Draft"}</td>
                <td className="px-4 py-3 text-ink-2">{vc.date}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-ink">{vc.supplier.name}</div>
                  <div className="text-meta text-ink-3">Ref: {vc.reference}{vc.reason ? ` · ${vc.reason}` : ""}</div>
                  {vc.allocations
                    .filter((a) => !a.removedAt)
                    .map((a) => (
                      <div key={a.id} className="mt-1 flex items-center gap-2 text-meta text-ink-2">
                        <span>Applied {a.appliedOn}:</span>
                        <Amount text={fmt.peso(a.amountCentavos)} />
                        {canVoid && (
                          <button
                            type="button"
                            className="text-danger hover:underline"
                            onClick={() =>
                              start(async () => {
                                const r = await removeVendorAllocation(vc.id, a.id);
                                if (!r.ok) toast.error(r.error);
                                else toast.success("Allocation removed");
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
                  <Amount text={fmt.peso(vc.creditCentavos)} />
                </td>
                <td className="px-4 py-3 text-right font-mono">
                  <Amount text={fmt.peso(vc.remainingCentavos)} />
                </td>
                <td className="px-4 py-3 capitalize text-ink-2">{vc.status}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  {vc.status === "draft" && canApprove && (
                    <Button
                      size="sm"
                      variant="primary"
                      loading={pending}
                      onClick={() =>
                        start(async () => {
                          const r = await recordVendorCredit(vc.id);
                          if (!r.ok) toast.error(r.error);
                          else toast.success(`Recorded ${r.data.number}`);
                        })
                      }
                    >
                      Record &amp; post
                    </Button>
                  )}
                  {vc.status === "recorded" && vc.remainingCentavos > 0 && canApply && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setApplyId(applyId === vc.id ? null : vc.id);
                        setApplyPesos((vc.remainingCentavos / 100).toFixed(2));
                      }}
                    >
                      Apply to bill
                    </Button>
                  )}
                  {vc.status === "recorded" && vc.appliedCentavos === 0 && canVoid && (
                    <Button
                      size="sm"
                      onClick={() => {
                        const why = window.prompt("Reason for voiding this vendor credit?");
                        if (!why || why.trim().length < 3) return;
                        start(async () => {
                          const r = await voidVendorCredit(vc.id, why.trim());
                          if (!r.ok) toast.error(r.error);
                          else toast.success("Vendor credit voided");
                        });
                      }}
                    >
                      Void
                    </Button>
                  )}
                  {applyId === vc.id && (
                    <div className="mt-2 flex flex-wrap justify-end gap-2 border-t border-rule pt-2">
                      <select
                        className="h-8 rounded border border-control bg-sheet px-2 text-meta"
                        value={applyBillId}
                        onChange={(e) => setApplyBillId(e.target.value)}
                      >
                        <option value="">Pick bill…</option>
                        {bills
                          .filter((b) => b.supplierId === vc.supplier.id && b.owedCentavos > 0)
                          .map((b) => (
                            <option key={b.id} value={b.id}>
                              #{b.no} {b.billNumber} ({(b.owedCentavos / 100).toFixed(2)})
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
                            const amt = pesoCentavos(applyPesos);
                            if (!applyBillId || amt <= 0) return;
                            const r = await applyVendorCredit(vc.id, { billId: applyBillId, appliedOn: today, amountCentavos: amt });
                            if (!r.ok) toast.error(r.error);
                            else {
                              toast.success("Vendor credit applied to bill");
                              setApplyId(null);
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
                  No vendor credits yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
