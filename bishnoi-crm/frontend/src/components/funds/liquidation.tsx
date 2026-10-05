"use client";

import { Camera, FileText, Plus, Send, Trash2 } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FileInput, FormError, Input, Select } from "@/src/platform/ui/field";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { addReceipt, removeReceipt, sendLiquidation } from "../../actions/funds";
import type { ExpenseCategory, FundExpense, FundRequest } from "./types";

// A phone photo is several megabytes; a receipt reads fine at this size, and
// a smaller file goes up faster on mobile data.
const LONGEST_SIDE = 1600;
const MAX_BYTES = 4 * 1024 * 1024;

/** A photo, made small enough to send: JPEG, its longest side LONGEST_SIDE.
 *  Anything the browser can't draw (a PDF, HEIC on most browsers) goes as it is. */
async function shrink(file: File): Promise<File> {
  if (!file.type.startsWith("image/") || file.type === "image/heic") return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, LONGEST_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, "image/jpeg", 0.82));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

/** What the receipts come to: covered, the person's own, refused, and the
 *  unused funds or the amount owed back. `checked`: Finance's final word. */
export function Tally({ request, org }: { request: FundRequest; org: Org }) {
  const fmt = makeFormat(org);
  const f = request.finance;
  if (!f?.release) return null;
  const t = f.tally;
  const checked = f.checkedAt !== null;
  const rows: [string, number, string?][] = [
    ["Cash advance", f.release.amountCentavos],
    ["Total expenses", t.spentCentavos],
    ["Charged to company (reimbursable)", t.coveredCentavos, "Expenses in a reimbursable category and not rejected."],
  ];
  if (t.ownCentavos) rows.push(["Personal (non-reimbursable)", t.ownCentavos, "Expenses in a category the company does not reimburse."]);
  if (t.refusedCentavos) rows.push(["Rejected by Finance", t.refusedCentavos]);
  const balance = checked ? f.returnDueCentavos - f.reimburseDueCentavos : t.balanceCentavos;
  return (
    <dl className="space-y-1 text-sm">
      {rows.map(([label, amount, hint]) => (
        <div key={label} className="flex justify-between gap-4" title={hint}>
          <dt className="text-ink-2">{label}</dt>
          <dd className="tabular-nums">{fmt.peso(amount)}</dd>
        </div>
      ))}
      <div className="flex justify-between gap-4 border-t border-rule pt-1.5 font-semibold">
        <dt>{request.status === "closed"
            ? balance > 0
              ? "Refund received by Finance"
              : balance < 0
                ? "Reimbursement paid to you"
                : "Fully liquidated"
            : balance > 0
              ? "Refund due to Finance"
              : balance < 0
                ? "Reimbursement due to you"
                : "Fully liquidated"}</dt>
        <dd className="tabular-nums">{fmt.peso(Math.abs(balance))}</dd>
      </div>
      {!checked && <p className="text-meta text-ink-3">So far: Finance has the final word when it checks the receipts.</p>}
      {f.returnedCentavos > 0 && <p className="text-meta text-ink-2">Refund received: {fmt.peso(f.returnedCentavos)}</p>}
      {f.reimbursedCentavos > 0 && <p className="text-meta text-ink-2">Reimbursement paid: {fmt.peso(f.reimbursedCentavos)}</p>}
    </dl>
  );
}

/** The receipts, one row each, with Finance's check once it's done. */
export function Receipts({ request, org, editable }: { request: FundRequest; org: Org; editable: boolean }) {
  const fmt = makeFormat(org);
  const expenses = request.finance?.expenses ?? [];
  if (expenses.length === 0) return <p className="text-meta text-ink-3">No expenses added yet.</p>;
  return (
    <ul className="divide-y divide-rule">
      {expenses.map((e) => (
        <ReceiptRow key={e.id} request={request} expense={e} fmt={fmt} editable={editable} />
      ))}
    </ul>
  );
}

function ReceiptRow({ request, expense: e, fmt, editable }: { request: FundRequest; expense: FundExpense; fmt: Format; editable: boolean }) {
  const [pending, start] = useTransition();
  return (
    <li className="flex flex-wrap items-start gap-x-4 gap-y-1 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{e.description}</p>
        <p className="text-meta text-ink-3">
          {fmt.dateLabel(e.spentOn)} · {e.category?.name ?? "Unclassified"}
          {e.category && !e.category.reimbursable && " (non-reimbursable)"}
        </p>
        {e.receipt ? (
          <a href={`/funds/${request.id}/receipts/${e.id}`} target="_blank" rel="noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-meta text-hema hover:underline">
            <FileText className="size-3.5" aria-hidden />
            {e.receipt.name}
          </a>
        ) : (
          <p className="mt-0.5 text-meta text-ink-2">No official receipt: {e.noReceiptReason}</p>
        )}
        {e.accepted === false && <p className="mt-0.5 text-meta text-danger">Rejected: {e.refusedReason}</p>}
        {e.accepted === true && <p className="mt-0.5 text-meta text-filed">Accepted by Finance</p>}
      </div>
      <p className={`text-sm tabular-nums ${e.covered ? "" : "text-ink-3 line-through"}`}>{fmt.peso(e.amountCentavos)}</p>
      {editable && (
        <Button
          size="sm"
          variant="quiet"
          loading={pending}
          className="!px-1.5 !text-ink-3 hover:!text-danger"
          aria-label={`Remove ${e.description}`}
          onClick={() =>
            start(async () => {
              const result = await removeReceipt(request.id, e.id);
              if (!result.ok) toast.error(result.error);
            })
          }
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      )}
    </li>
  );
}

/** Adding a receipt, and sending the liquidation once they're all in. */
export function Liquidate({ request, categories, org, today }: { request: FundRequest; categories: ExpenseCategory[]; org: Org; today: string }) {
  const fmt = makeFormat(org);
  const [open, setOpen] = useState((request.finance?.expenses.length ?? 0) === 0);
  const [noReceipt, setNoReceipt] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const form = useRef<HTMLFormElement>(null);
  const count = request.finance?.expenses.length ?? 0;

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (k: string) => String(data.get(k) ?? "").trim();
    const problems: Record<string, string> = {};
    const centavos = fmt.toCentavos(text("amount"));
    const file = data.get("receipt");
    if (!text("description")) problems.description = "Describe the expense.";
    if (!centavos) problems.amountCentavos = "Enter a valid amount, e.g. 1,250.00.";
    if (!text("categoryId")) problems.categoryId = "Select an expense category.";
    if (!text("spentOn")) problems.spentOn = "Select the date.";
    if (noReceipt ? !text("noReceiptReason") : !(file instanceof File && file.size > 0)) {
      problems[noReceipt ? "noReceiptReason" : "receipt"] = noReceipt ? "State why there is no official receipt." : "Attach the official receipt or take a photo of it.";
    }
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Please review the highlighted fields.");
      return;
    }
    start(async () => {
      const body = new FormData();
      body.set("spentOn", text("spentOn"));
      body.set("description", text("description"));
      body.set("categoryId", text("categoryId"));
      body.set("amountCentavos", String(centavos));
      if (noReceipt) body.set("noReceiptReason", text("noReceiptReason"));
      else {
        const small = await shrink(file as File);
        if (small.size > MAX_BYTES) {
          setFields({ receipt: "The file exceeds 4 MB. Retake the photo or scan it at a lower resolution." });
          return;
        }
        body.set("receipt", small, small.name);
      }
      const result = await addReceipt(request.id, body);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Expense added");
      form.current?.reset();
      setFields({});
      setError(null);
      setNoReceipt(false);
      setOpen(false);
    });
  }

  return (
    <div className="space-y-4">
      {open ? (
        <form ref={form} onSubmit={submit} noValidate className="space-y-4 rounded-[3px] border border-rule p-4">
          <p className="text-sm font-semibold">Add expense</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Description" error={fields.description}>
              {(p) => <Input {...p} name="description" placeholder="Dinner at Café Juanita" maxLength={200} />}
            </Field>
            <Field label={`Amount (${fmt.symbol})`} error={fields.amountCentavos}>
              {(p) => <Input {...p} name="amount" inputMode="decimal" placeholder="0.00" />}
            </Field>
            <Field label="Expense category" error={fields.categoryId} hint="Set by Finance. Only reimbursable categories are charged to the company.">
              {(p) => (
                <Select {...p} name="categoryId" defaultValue="">
                  <option value="" disabled>
                    Select a category…
                  </option>
                  {categories
                    .filter((c) => c.parentId === null)
                    .map((top) => {
                      const subs = categories.filter((c) => c.parentId === top.id);
                      const tag = top.reimbursable ? "" : " (non-reimbursable)";
                      return subs.length ? (
                        <optgroup key={top.id} label={top.name + tag}>
                          {subs.map((sub) => (
                            <option key={sub.id} value={sub.id}>
                              {sub.name}
                            </option>
                          ))}
                          <option value={top.id}>Other {top.name.toLowerCase()}</option>
                        </optgroup>
                      ) : (
                        <option key={top.id} value={top.id}>
                          {top.name}
                          {tag}
                        </option>
                      );
                    })}
                </Select>
              )}
            </Field>
            <Field label="Date" error={fields.spentOn}>
              {(p) => <Input {...p} name="spentOn" type="date" max={today} defaultValue={today} />}
            </Field>
          </div>
          {noReceipt ? (
            <Field label="Reason for no official receipt" error={fields.noReceiptReason}>
              {(p) => <Input {...p} name="noReceiptReason" placeholder="Public transport fare" maxLength={300} />}
            </Field>
          ) : (
            <Field label="Official receipt" error={fields.receipt} hint="Photo or PDF. On a phone, this opens the camera.">
              {(p) => <FileInput {...p} name="receipt" accept="image/*,application/pdf" capture="environment" />}
            </Field>
          )}
          <label className="flex items-center gap-2 text-meta text-ink-2">
            <input type="checkbox" checked={noReceipt} onChange={(e) => setNoReceipt(e.target.checked)} className="size-4 accent-hema" />
            No official receipt available
          </label>
          <FormError message={error} />
          <div className="flex flex-wrap gap-2">
            <Button type="submit" variant="primary" loading={pending} icon={<Camera className="size-4" aria-hidden />}>
              Add expense
            </Button>
            {count > 0 && (
              <Button variant="quiet" onClick={() => setOpen(false)}>
                Cancel
              </Button>
            )}
          </div>
        </form>
      ) : (
        <Button icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen(true)}>
          Add expense
        </Button>
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
        <ConfirmButton
          label="Submit the liquidation"
          icon={<Send className="size-4" aria-hidden />}
          triggerVariant="primary"
          danger={false}
          title="Submit the liquidation to Finance?"
          body={
            count === 0
              ? "No expenses have been added: the full cash advance will be due as a refund. Expenses cannot be changed after submission unless Finance returns the liquidation for correction."
              : `${count} receipt${count === 1 ? "" : "s"}. Receipts can't be added or removed once it's sent, unless Finance sends it back to fix.`
          }
          confirmLabel="Submit to Finance"
          onConfirm={async () => {
            const result = await sendLiquidation(request.id);
            if (!result.ok) {
              toast.error(result.error);
              return false;
            }
            toast.success("Liquidation submitted", { description: "Forwarded to Finance for review." });
          }}
        />
        <span className="text-meta text-ink-3">Submit once all expenses are added.</span>
      </div>
    </div>
  );
}
