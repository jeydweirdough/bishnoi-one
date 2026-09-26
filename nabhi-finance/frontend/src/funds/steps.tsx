"use client";

import { Check, CornerUpLeft, FileText, HandCoins, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { checkReceipt, finishCheck, recordMoney, refuseRelease, releaseFunds, sendBack } from "./actions";
import { METHODS, type ExpenseCategory, type FundExpense, type FundRequest, type Method } from "./types";

// Finance's steps on a request, each where it's done: the release on a
// request to release, the check on a liquidation, the money in or out on a
// settled one.

type Done = { ok: true; data: FundRequest } | { ok: false; error: string; fields?: Record<string, string> };

function useStep() {
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  function run(work: () => Promise<Done>, said: string) {
    start(async () => {
      const result = await work();
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success(said);
    });
  }
  return { pending, error, fields, setFields, run };
}

function MethodFields({ method, setMethod, reference, setReference, fields }: { method: Method; setMethod: (m: Method) => void; reference: string; setReference: (r: string) => void; fields: Record<string, string> }) {
  return (
    <>
      <Field label="Payment method" error={fields.method}>
        {(p) => (
          <Select {...p} value={method} onChange={(e) => setMethod(e.target.value as Method)}>
            {METHODS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="Reference" optional error={fields.reference} hint="Voucher, check or transfer reference number.">
        {(p) => <Input {...p} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={80} />}
      </Field>
    </>
  );
}

/** Handing the money over: how much (up to what was approved), how, and when
 *  the receipts are due back. Or not releasing it at all, with the reason. */
export function Release({ request, org, today }: { request: FundRequest; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const [amount, setAmount] = useState(fmt.pesosText(request.approvedCentavos));
  const [method, setMethod] = useState<Method>("cash");
  const [reference, setReference] = useState("");
  const [liquidateBy, setLiquidateBy] = useState("");
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState("");
  const { pending, error, fields, setFields, run } = useStep();

  if (refusing) {
    return (
      <div className="space-y-3">
        <Field label="Reason for declining" error={fields.reason} hint={`Visible to ${request.requester.name} in the CRM.`}>
          {(p) => <Textarea {...p} value={reason} onChange={(e) => setReason(e.target.value)} className="min-h-16" />}
        </Field>
        <FormError message={error} />
        <div className="flex gap-2">
          <Button
            variant="danger"
            loading={pending}
            onClick={() => (reason.trim() ? run(() => refuseRelease(request.id, reason.trim()), `${request.number}: release declined`) : setFields({ reason: "Enter the reason for declining." }))}
          >
            Decline release
          </Button>
          <Button variant="quiet" onClick={() => setRefusing(false)}>
            Back
          </Button>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={`Amount to release (${fmt.symbol})`} error={fields.amountCentavos} hint={`Approved amount: ${fmt.peso(request.approvedCentavos)}.`}>
          {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <MethodFields method={method} setMethod={setMethod} reference={reference} setReference={setReference} fields={fields} />
        {request.liquidate && (
          <Field label="Liquidation due date" optional error={fields.liquidateBy} hint="Leave blank for the standard liquidation period.">
            {(p) => <Input {...p} type="date" min={today} value={liquidateBy} onChange={(e) => setLiquidateBy(e.target.value)} />}
          </Field>
        )}
      </div>
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          loading={pending}
          icon={<HandCoins className="size-4" aria-hidden />}
          onClick={() => {
            const centavos = fmt.toCentavos(amount);
            if (!centavos) return setFields({ amountCentavos: "Enter a valid amount, e.g. 2,500.00." });
            run(() => releaseFunds(request.id, { amountCentavos: centavos, method, reference: reference.trim() || null, liquidateBy: liquidateBy || null }), `${request.number} released`);
          }}
        >
          Release cash advance
        </Button>
        <Button variant="quiet" onClick={() => setRefusing(true)}>
          Decline release…
        </Button>
      </div>
    </div>
  );
}

/** Categories for a picker: each category with its sub-categories under it. */
function CategoryOptions({ categories }: { categories: ExpenseCategory[] }) {
  return (
    <>
      {categories
        .filter((c) => c.parentId === null)
        .map((top) => {
          const subs = categories.filter((c) => c.parentId === top.id);
          const tag = top.reimbursable ? "" : " (non-reimbursable)";
          return subs.length ? (
            <optgroup key={top.id} label={top.name + tag}>
              <option value={top.id}>{top.name}: general</option>
              {subs.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </optgroup>
          ) : (
            <option key={top.id} value={top.id}>
              {top.name}
              {tag}
            </option>
          );
        })}
    </>
  );
}

/** One receipt, checked: its category (only a reimbursable one is covered),
 *  and accepted, or refused with the reason the requester reads. */
function CheckRow({ request, expense: e, categories, org }: { request: FundRequest; expense: FundExpense; categories: ExpenseCategory[]; org: Org }) {
  const fmt = makeFormat(org);
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState(e.refusedReason ?? "");
  const { pending, error, run } = useStep();
  return (
    <li className="space-y-2 py-3">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-1">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{e.description}</p>
          <p className="text-meta text-ink-3">{fmt.dateLabel(e.spentOn)}</p>
          {e.receipt ? (
            <a href={`/funds/${request.id}/receipts/${e.id}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-meta text-hema hover:underline">
              <FileText className="size-3.5" aria-hidden />
              {e.receipt.name}
            </a>
          ) : (
            <p className="text-meta text-due-today">No receipt: {e.noReceiptReason}</p>
          )}
        </div>
        <p className="text-sm font-semibold tabular-nums">{fmt.peso(e.amountCentavos)}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label={`${e.description}: category`}
          value={e.category?.id ?? ""}
          disabled={pending}
          onChange={(ev) => run(() => checkReceipt(request.id, e.id, { categoryId: ev.target.value }), "Expense reclassified")}
          className="h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-meta"
        >
          {!e.category && <option value="">Unclassified</option>}
          <CategoryOptions categories={categories} />
        </select>
        <Button
          size="sm"
          variant={e.accepted === true ? "primary" : "default"}
          loading={pending}
          icon={<Check className="size-3.5" aria-hidden />}
          onClick={() => run(() => checkReceipt(request.id, e.id, { accepted: e.accepted === true ? null : true }), e.accepted === true ? "Review cleared" : "Accepted")}
        >
          {e.accepted === true ? "Accepted" : "Accept"}
        </Button>
        <Button
          size="sm"
          variant={e.accepted === false ? "danger" : "default"}
          icon={<X className="size-3.5" aria-hidden />}
          onClick={() => (e.accepted === false ? run(() => checkReceipt(request.id, e.id, { accepted: null }), "Review cleared") : setRefusing(true))}
        >
          {e.accepted === false ? "Rejected" : "Reject…"}
        </Button>
      </div>
      {e.accepted === false && e.refusedReason && <p className="text-meta text-danger">Rejected: {e.refusedReason}</p>}
      {refusing && e.accepted !== false && (
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Reason for rejection" className="min-w-60 flex-1">
            {(p) => <Input {...p} value={reason} onChange={(ev) => setReason(ev.target.value)} placeholder="Not a business expense" maxLength={300} />}
          </Field>
          <Button
            size="sm"
            variant="danger"
            loading={pending}
            onClick={() => {
              if (!reason.trim()) return;
              run(() => checkReceipt(request.id, e.id, { accepted: false, refusedReason: reason.trim() }), "Rejected");
              setRefusing(false);
            }}
          >
            Reject
          </Button>
          <Button size="sm" variant="quiet" onClick={() => setRefusing(false)}>
            Back
          </Button>
        </div>
      )}
      <FormError message={error} />
    </li>
  );
}

/** Checking a liquidation, receipt by receipt, then finishing it (or sending it back). */
export function CheckLiquidation({ request, categories, org }: { request: FundRequest; categories: ExpenseCategory[]; org: Org }) {
  const fmt = makeFormat(org);
  const [note, setNote] = useState("");
  const [backing, setBacking] = useState(false);
  const { pending, error, fields, setFields, run } = useStep();
  const undecided = request.expenses.filter((e) => e.accepted === null).length;
  const t = request.tally;
  return (
    <div className="space-y-4">
      {request.expenses.length === 0 ? (
        <p className="text-meta text-ink-3">No expenses submitted: the full cash advance is due as a refund.</p>
      ) : (
        <ul className="divide-y divide-rule">
          {request.expenses.map((e) => (
            <CheckRow key={e.id} request={request} expense={e} categories={categories} org={org} />
          ))}
        </ul>
      )}
      <p className="text-sm">
        {t.balanceCentavos > 0
          ? `Current balance: refund due of ${fmt.peso(t.balanceCentavos)}.`
          : t.balanceCentavos < 0
            ? `Current balance: reimbursement due of ${fmt.peso(-t.balanceCentavos)}.`
            : "Current balance: fully liquidated."}
        {undecided > 0 && <span className="text-ink-3"> {undecided} expense{undecided === 1 ? "" : "s"} still to accept or reject.</span>}
      </p>
      {backing && (
        <Field label="Corrections needed" error={fields.note} hint={`Visible to ${request.requester.name}, who can revise the liquidation and resubmit it.`}>
          {(p) => <Textarea {...p} value={note} onChange={(e) => setNote(e.target.value)} className="min-h-16" placeholder="The dinner receipt is unreadable: please upload a clearer copy." />}
        </Field>
      )}
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        {backing ? (
          <>
            <Button
              loading={pending}
              icon={<CornerUpLeft className="size-4" aria-hidden />}
              onClick={() => (note.trim() ? run(() => sendBack(request.id, note.trim()), "Returned for correction") : setFields({ note: "State the corrections needed." }))}
            >
              Send back
            </Button>
            <Button variant="quiet" onClick={() => setBacking(false)}>
              Back
            </Button>
          </>
        ) : (
          <>
            <Button variant="primary" loading={pending} disabled={undecided > 0} icon={<Check className="size-4" aria-hidden />} onClick={() => run(() => finishCheck(request.id), "Liquidation reviewed")}>
              Complete review
            </Button>
            <Button variant="quiet" icon={<CornerUpLeft className="size-4" aria-hidden />} onClick={() => setBacking(true)}>
              Return for correction…
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

/** The unused funds coming back, or the reimbursement going out: all at once or in parts. */
export function RecordMoney({ request, org, kind }: { request: FundRequest; org: Org; kind: "returned" | "reimbursed" }) {
  const fmt = makeFormat(org);
  const left = kind === "returned" ? request.returnDueCentavos - request.returnedCentavos : request.reimburseDueCentavos - request.reimbursedCentavos;
  const [amount, setAmount] = useState(fmt.pesosText(left));
  const [method, setMethod] = useState<Method>("cash");
  const [reference, setReference] = useState("");
  const { pending, error, fields, setFields, run } = useStep();
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={`${kind === "returned" ? "Amount received" : "Amount paid"} (${fmt.symbol})`} error={fields.amountCentavos} hint={`Outstanding: ${fmt.peso(left)}.`}>
          {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />}
        </Field>
        <MethodFields method={method} setMethod={setMethod} reference={reference} setReference={setReference} fields={fields} />
      </div>
      <FormError message={error} />
      <Button
        variant="primary"
        loading={pending}
        icon={<HandCoins className="size-4" aria-hidden />}
        onClick={() => {
          const centavos = fmt.toCentavos(amount);
          if (!centavos) return setFields({ amountCentavos: "Enter a valid amount, e.g. 500.00." });
          run(() => recordMoney(request.id, kind, { amountCentavos: centavos, method, reference: reference.trim() || null }), kind === "returned" ? "Refund recorded" : "Reimbursement recorded");
        }}
      >
        {kind === "returned" ? "Record refund" : "Record reimbursement"}
      </Button>
    </div>
  );
}
