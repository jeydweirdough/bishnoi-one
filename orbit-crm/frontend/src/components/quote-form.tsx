"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FileInput, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createQuote, previewQuote, type QuoteFor, type QuoteInput } from "../actions/customers";
import { makeFormat, percent, toBasisPoints, type Format } from "@/src/platform/lib/format";
import { promoTerms } from "@/src/platform/lib/labels";
import type { CustomField, Org, PriceList, QuotePreview } from "@/src/platform/lib/types";
import { ExtraFields, extraChanges, toDraft, type ExtraDraft } from "./extra/extra-fields";

const MAX_LETTER_BYTES = 8 * 1024 * 1024;

type LineDraft = {
  key: number;
  // A line is either a product or a bundle, never both. The picker below sets
  // one and clears the other.
  productId: string;
  bundleId: string;
  quantity: string;
  unitPrice: string; // only for price types typed on the quote
  promoId: string;
  discountKind: "" | "percent" | "amount";
  discountValue: string;
};

type Draft = {
  priceType: string;
  rx: boolean;
  payer: string;
  notes: string;
  lines: LineDraft[];
};

const blankLine = (key: number): LineDraft => ({
  key,
  productId: "",
  bundleId: "",
  quantity: "1",
  unitPrice: "",
  promoId: "",
  discountKind: "",
  discountValue: "",
});

// Desktop reads the lines as a table under one header row; phones stack each field with its own label.
const LINE_GRID = "sm:grid-cols-[minmax(0,2.2fr)_4.5rem_minmax(0,1.6fr)_minmax(0,1.4fr)_7rem_2.25rem]";
const mobileLabel = "mb-0.5 block text-meta text-ink-3 sm:sr-only";

const cell = "h-9 w-full min-w-0 border-0 border-b border-control bg-transparent px-0 text-sm focus:border-hema focus:outline-none aria-[invalid=true]:border-danger";

/** The quote as the API takes it. `null` in place of a number the rep hasn't typed properly yet. */
function toInput(fmt: Format, d: Draft, entered: boolean, letter: QuoteInput["letter"]): QuoteInput {
  return {
    priceType: d.priceType,
    rx: d.rx,
    payer: d.payer,
    notes: d.notes.trim() || null,
    lines: d.lines
      .filter((l) => l.productId || l.bundleId)
      .map((l) =>
        l.bundleId
          ? // A bundle's price is the price: no typed amount, no promo, no discount.
            { bundleId: l.bundleId, quantity: /^\d+$/.test(l.quantity.trim()) ? Number(l.quantity) : 0 }
          : {
              productId: l.productId,
              quantity: /^\d+$/.test(l.quantity.trim()) ? Number(l.quantity) : 0,
              unitPriceCentavos: entered ? fmt.toCentavos(l.unitPrice) : null,
              promoId: l.promoId || null,
              discount: discountOf(fmt, l),
            },
      ),
    letter,
  };
}

type ManualDiscount = { kind: "percent" | "amount"; value: number } | null;

function discountOf(fmt: Format, l: LineDraft): ManualDiscount {
  if (!l.discountKind || !l.discountValue.trim()) return null;
  const value = l.discountKind === "percent" ? toBasisPoints(l.discountValue) : fmt.toCentavos(l.discountValue);
  return value ? { kind: l.discountKind, value } : null;
}

export function QuoteForm({ to, priceList, org, fields: custom = [] }: { to: QuoteFor; priceList: PriceList; org: Org; fields?: CustomField[] }) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const always = priceList.priceTypes.filter((t) => t.rule === "always");
  const withRx = priceList.priceTypes.filter((t) => t.rule === "with_rx");
  const [draft, setDraft] = useState<Draft>({
    priceType: always[0]?.code ?? "",
    rx: false,
    payer: "self",
    notes: "",
    lines: [blankLine(0)],
  });
  const [preview, setPreview] = useState<QuotePreview | null>(null);
  const [previewFields, setPreviewFields] = useState<Record<string, string>>({});
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, startSave] = useTransition();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const asked = useRef(0);
  const letterFile = useRef<HTMLInputElement>(null);
  const [extra, setExtra] = useState<ExtraDraft>(() => toDraft(custom, undefined));
  const today = fmt.todayKey();

  const offered = draft.rx && withRx.length ? withRx : always;
  const priceType = priceList.priceTypes.find((t) => t.code === draft.priceType);
  const entered = priceType?.entry === "entered";
  const withLetter = draft.payer !== "self";

  /** Change the draft and, a moment after the rep stops typing, ask the API what it comes to. */
  function update(next: Draft) {
    setDraft(next);
    if (timer.current) clearTimeout(timer.current);
    const typed = priceList.priceTypes.find((t) => t.code === next.priceType)?.entry === "entered";
    const input = toInput(fmt, next, typed, null);
    // Only ask once every line has a quantity (and, for a typed price, an amount); half-typed numbers aren't errors yet.
    const ready = input.lines.every((l) => l.quantity >= 1 && (!typed || "bundleId" in l || l.unitPriceCentavos));
    if (!input.priceType || input.lines.length === 0 || !ready) {
      setPreview(null);
      setPreviewFields({});
      return;
    }
    timer.current = setTimeout(async () => {
      const ask = ++asked.current;
      const result = await previewQuote(to, input);
      if (ask !== asked.current) return; // a newer change is on its way
      if (result.ok) {
        setPreview(result.data);
        setPreviewFields({});
      } else {
        setPreview(null);
        setPreviewFields(result.fields ?? {});
      }
    }, 350);
  }

  function setRx(rx: boolean) {
    // With an Rx, the Rx-only price (B2C: Doctor's Price) is the one to use; without one, it isn't allowed.
    const pool = rx && withRx.length ? withRx : always;
    const priceTypeCode = pool.some((t) => t.code === draft.priceType) ? draft.priceType : (pool[0]?.code ?? "");
    update({ ...draft, rx, priceType: priceTypeCode });
  }

  function setLine(key: number, patch: Partial<LineDraft>) {
    update({ ...draft, lines: draft.lines.map((l) => (l.key === key ? { ...l, ...patch } : l)) });
  }

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const problems: Record<string, string> = {};
    const file = letterFile.current?.files?.[0];

    draft.lines.forEach((l, i) => {
      if (!l.productId && !l.bundleId) {
        problems[`lines.${i}.productId`] = `Pick a ${priceList.bundles.length > 0 ? "product or bundle" : "product"}, or remove this line.`;
      }
      if (!/^\d+$/.test(l.quantity.trim()) || Number(l.quantity) < 1) problems[`lines.${i}.quantity`] = "Enter a whole number.";
      // A bundle is priced whole, so there is no per-unit amount to type.
      if (entered && !l.bundleId && !fmt.toCentavos(l.unitPrice)) {
        problems[`lines.${i}.unitPriceCentavos`] = "Enter an amount like 1,250.00.";
      }
      if (l.discountKind && l.discountValue.trim() && !discountOf(fmt, l)) {
        problems[`lines.${i}.discount`] = l.discountKind === "percent" ? "Enter a percent like 5." : "Enter an amount like 100.00.";
      }
    });
    let letter: QuoteInput["letter"] = null;
    if (withLetter) {
      letter = { number: text("letterNumber"), issuedOn: text("letterIssuedOn"), amountCentavos: fmt.toCentavos(text("letterAmount")) };
      if (!letter.number) problems.number = "Enter the letter's number.";
      if (!letter.issuedOn) problems.issuedOn = "Pick the date on the letter.";
      if (!letter.amountCentavos) problems.amountCentavos = "Enter the amount the letter covers.";
      if (!file) problems.letterFile = "Attach the letter: a PDF, or a photo (JPG or PNG).";
      else if (file.size > MAX_LETTER_BYTES) problems.letterFile = "The file is over 8 MB. Scan it at a lower resolution.";
    }
    if (priceType?.requiresNotes && !draft.notes.trim()) problems.notes = `${priceType.name} needs notes.`;
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }

    const form = new FormData();
    form.set("quote", JSON.stringify({ ...toInput(fmt, draft, entered, letter), extra: extraChanges(custom, extra) }));
    if (withLetter && file) form.set("letterFile", file);
    startSave(async () => {
      const result = await createQuote(to, form);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success("Quote saved", {
        description: preview?.approvalReasons.length || withLetter ? "It's waiting for approval now." : undefined,
      });
      router.push(`/quotes/${result.data.id}`);
      router.refresh();
    });
  }

  if (!priceList.usesPriceList || priceList.priceTypes.length === 0) {
    return (
      <p className="text-ink-2">
        There are no prices to quote with yet. An administrator sets them up in Administration → Settings → Pricing &amp; retention.
      </p>
    );
  }

  const productsFor = (code: string | undefined) =>
    entered ? priceList.products : priceList.products.filter((p) => code && p.prices[code] !== undefined);
  const promosFor = (productId: string) => priceList.promos.filter((p) => p.productIds === null || p.productIds.includes(productId));
  const errorFor = (key: string) => fields[key] ?? previewFields[key];
  const previewLine = (l: LineDraft) =>
    l.bundleId
      ? // One bundle makes one line or several; what the rep wants on its row
        // is what the whole set comes to.
        (preview?.lines.filter((x) => x.bundleId === l.bundleId) ?? [])
      : (preview?.lines.filter((x) => x.productId === l.productId && !x.bundleId) ?? []);
  const lineTotal = (rows: QuotePreview["lines"]) => (rows.length ? rows.reduce((sum, r) => sum + r.totalCentavos, 0) : null);
  // A bundle is only offerable when every product in it can be priced this way.
  const bundlesFor = (code: string | undefined) =>
    entered
      ? []
      : priceList.bundles.filter((b) => code && b.items.every((i) => priceList.products.find((p) => p.id === i.productId)?.prices[code] !== undefined));

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-end">
        {withRx.length > 0 && (
          <label className="flex h-9 items-center gap-2 text-sm">
            <input type="checkbox" checked={draft.rx} onChange={(e) => setRx(e.target.checked)} className="size-4 accent-hema" />
            Has a prescription (Rx)
          </label>
        )}
        <Field
          label="Price"
          error={errorFor("priceType")}
          hint={draft.rx && withRx.length ? `With an Rx, quotes use ${withRx.map((t) => t.name).join(" or ")}.` : undefined}
        >
          {(p) => (
            <Select {...p} value={draft.priceType} onChange={(e) => update({ ...draft, priceType: e.target.value })}>
              {offered.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.name}
                  {t.needsApproval ? " (your team lead approves)" : ""}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      {/* Lines, set out like an invoice: product, quantity, promo, extra discount, line total. */}
      <fieldset>
        <legend className="mb-2 text-meta font-medium text-ink-2">{priceList.bundles.length > 0 ? "Products & bundles" : "Products"}</legend>
        <div aria-hidden className={`hidden gap-x-3 border-b border-rule pb-1.5 text-caps text-ink-3 uppercase sm:grid ${LINE_GRID}`}>
          <span>{priceList.bundles.length > 0 ? "Product or bundle" : "Product"}</span>
          <span className="text-right">Qty</span>
          <span>Promo</span>
          <span>Extra discount</span>
          <span className="text-right">Total</span>
          <span />
        </div>
        <ul className="divide-y divide-rule border-b border-rule">
          {draft.lines.map((l, i) => {
            const at = `lines.${i}`;
            const product = priceList.products.find((p) => p.id === l.productId);
            const bundle = priceList.bundles.find((b) => b.id === l.bundleId);
            const promos = l.productId ? promosFor(l.productId) : [];
            const rows = previewLine(l);
            const total = lineTotal(rows);
            const offeredBundles = bundlesFor(priceType?.code);
            return (
              <li key={l.key} className={`grid gap-x-3 gap-y-3 py-3 sm:items-start ${LINE_GRID}`}>
                <div className="min-w-0">
                  <span className={mobileLabel}>{priceList.bundles.length > 0 ? "Product or bundle" : "Product"}</span>
                  <select
                    aria-label={`Line ${i + 1}: ${offeredBundles.length ? "product or bundle" : "product"}`}
                    aria-invalid={errorFor(`${at}.productId`) || errorFor(`${at}.bundleId`) ? true : undefined}
                    value={l.bundleId ? `b:${l.bundleId}` : l.productId}
                    onChange={(e) => {
                      const picked = e.target.value;
                      const isBundle = picked.startsWith("b:");
                      setLine(l.key, {
                        productId: isBundle ? "" : picked,
                        bundleId: isBundle ? picked.slice(2) : "",
                        // A bundle takes neither, and a changed product's promo no longer applies.
                        promoId: "",
                        discountKind: "",
                        discountValue: "",
                        unitPrice: "",
                      });
                    }}
                    className={cell}
                  >
                    <option value="">Pick {offeredBundles.length ? "a product or bundle" : "a product"}…</option>
                    {productsFor(priceType?.code).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.unit}
                        {!entered && priceType ? ` · ${fmt.peso(p.prices[priceType.code])}` : ""}
                      </option>
                    ))}
                    {offeredBundles.length > 0 && (
                      <optgroup label="Bundles">
                        {offeredBundles.map((b) => (
                          <option key={b.id} value={`b:${b.id}`}>
                            {b.name} · the set · {fmt.peso(b.priceCentavos)}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                  {product?.genericName && <p className="mt-0.5 text-meta text-ink-3">{product.genericName}</p>}
                  {bundle && (
                    <p className="mt-0.5 text-meta text-ink-3">
                      {bundle.items
                        .map((i) => `${i.qty} × ${priceList.products.find((p) => p.id === i.productId)?.name ?? "a product"}`)
                        .join(", ")}
                      {bundle.asOneLine ? "" : " · shown as its items"}
                    </p>
                  )}
                  {errorFor(`${at}.productId`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.productId`)}</p>}
                  {errorFor(`${at}.bundleId`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.bundleId`)}</p>}
                  {entered && !l.bundleId && (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="text-meta text-ink-3">
                        {priceType?.name} per unit {fmt.symbol}
                      </span>
                      <input
                        aria-label={`Line ${i + 1}: ${priceType?.name} per unit`}
                        inputMode="decimal"
                        value={l.unitPrice}
                        onChange={(e) => setLine(l.key, { unitPrice: e.target.value })}
                        className={`${cell} w-28 text-right`}
                        placeholder="0.00"
                      />
                    </div>
                  )}
                  {errorFor(`${at}.unitPriceCentavos`) && (
                    <p className="mt-1 text-meta text-danger">{errorFor(`${at}.unitPriceCentavos`)}</p>
                  )}
                </div>

                <div>
                  <span className={mobileLabel}>Quantity</span>
                  <input
                    aria-label={`Line ${i + 1}: quantity`}
                    aria-invalid={errorFor(`${at}.quantity`) ? true : undefined}
                    inputMode="numeric"
                    value={l.quantity}
                    onChange={(e) => setLine(l.key, { quantity: e.target.value })}
                    className={`${cell} sm:text-right`}
                  />
                  {rows.some((r) => r.freeQuantity > 0) && (
                    <p className="mt-0.5 text-meta text-ink-2 sm:text-right">+{rows.reduce((n, r) => n + r.freeQuantity, 0)} free</p>
                  )}
                  {errorFor(`${at}.quantity`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.quantity`)}</p>}
                </div>

                <div className="min-w-0">
                  <span className={mobileLabel}>Promo</span>
                  {/* A picker only when there's something to pick. */}
                  {l.bundleId ? (
                    <p className="text-meta text-ink-3 sm:h-9 sm:leading-9">The set price</p>
                  ) : promos.length > 0 ? (
                    <select aria-label={`Line ${i + 1}: promo`} value={l.promoId} onChange={(e) => setLine(l.key, { promoId: e.target.value })} className={cell}>
                      <option value="">No promo</option>
                      {promos.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({promoTerms(fmt, p)})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <p className="text-meta text-ink-3 sm:h-9 sm:leading-9">{l.productId ? "None for this product" : "—"}</p>
                  )}
                  {errorFor(`${at}.promoId`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.promoId`)}</p>}
                </div>

                <div className="min-w-0">
                  <span className={mobileLabel}>Extra discount</span>
                  {/* Most lines have none, so it waits behind a link instead of asking on every line. */}
                  {l.bundleId ? (
                    <p className="text-meta text-ink-3 sm:h-9 sm:leading-9">—</p>
                  ) : l.discountKind ? (
                    <div className="flex items-end gap-1.5">
                      <select
                        aria-label={`Line ${i + 1}: extra discount`}
                        value={l.discountKind}
                        onChange={(e) => setLine(l.key, { discountKind: e.target.value as LineDraft["discountKind"] })}
                        className={`${cell} w-auto`}
                      >
                        <option value="percent">% off</option>
                        <option value="amount">{fmt.symbol} off</option>
                      </select>
                      <input
                        aria-label={`Line ${i + 1}: discount ${l.discountKind === "percent" ? "percent" : "amount"}`}
                        inputMode="decimal"
                        value={l.discountValue}
                        onChange={(e) => setLine(l.key, { discountValue: e.target.value })}
                        className={`${cell} w-20 text-right`}
                        placeholder={l.discountKind === "percent" ? "5" : "100.00"}
                      />
                      <Button
                        size="sm"
                        variant="quiet"
                        className="!px-1.5 !text-ink-3 hover:!text-danger"
                        onClick={() => setLine(l.key, { discountKind: "", discountValue: "" })}
                      >
                        <X className="size-3.5" aria-hidden />
                        <span className="sr-only">Remove the discount on line {i + 1}</span>
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="quiet"
                      className="-ml-3 sm:mt-0.5"
                      icon={<Plus className="size-3.5" aria-hidden />}
                      onClick={() => setLine(l.key, { discountKind: "percent" })}
                      aria-label={`Add an extra discount to line ${i + 1}`}
                    >
                      Discount
                    </Button>
                  )}
                  {errorFor(`${at}.discount`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.discount`)}</p>}
                </div>

                <p className="flex items-baseline justify-between font-semibold tabular-nums sm:block sm:h-9 sm:text-right sm:leading-9">
                  <span className="text-meta font-normal text-ink-3 sm:hidden">Line total</span>
                  {total !== null ? fmt.peso(total) : <span className="font-normal text-ink-3">—</span>}
                </p>

                <div className="sm:text-right">
                  {draft.lines.length > 1 && (
                    <Button
                      size="sm"
                      variant="quiet"
                      className="-ml-3 !text-ink-3 hover:!text-danger sm:ml-0 sm:!px-2"
                      onClick={() => update({ ...draft, lines: draft.lines.filter((x) => x.key !== l.key) })}
                    >
                      <X className="size-4" aria-hidden />
                      <span className="sm:sr-only">Remove line {i + 1}</span>
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
        {draft.lines.length < 50 && (
          <Button
            size="sm"
            variant="quiet"
            className="mt-1 -ml-3"
            icon={<Plus className="size-4" aria-hidden />}
            onClick={() => update({ ...draft, lines: [...draft.lines, blankLine(Math.max(...draft.lines.map((l) => l.key)) + 1)] })}
          >
            {priceList.bundles.length > 0 ? "Add product or bundle" : "Add product"}
          </Button>
        )}
      </fieldset>

      {/* Totals */}
      <div className="ml-auto max-w-sm space-y-1 text-sm">
        {preview ? (
          <>
            <p className="flex justify-between text-ink-2">
              <span>List value</span>
              <span className="tabular-nums">{fmt.peso(preview.grossCentavos)}</span>
            </p>
            {preview.promoDiscountCentavos > 0 && (
              <p className="flex justify-between text-ink-2">
                <span>Promos</span>
                <span className="tabular-nums">−{fmt.peso(preview.promoDiscountCentavos)}</span>
              </p>
            )}
            {preview.discountCentavos > 0 && (
              <p className="flex justify-between text-ink-2">
                <span>Extra discounts</span>
                <span className="tabular-nums">−{fmt.peso(preview.discountCentavos)}</span>
              </p>
            )}
          </>
        ) : (
          <p className="text-right text-meta text-ink-3">Pick products to see the total.</p>
        )}
      </div>
      {preview && preview.approvalReasons.length > 0 && (
        <p className="animate-reshape rounded-[3px] bg-hema-tint px-3 py-2 text-meta text-ink-2">
          Your team lead approves this quote before it goes out:{" "}
          {preview.approvalReasons
            .map((r) => (r === "price" ? `${priceType?.name} needs approval` : `extra discounts are over ${percent(priceList.discountApprovalBp)}`))
            .join(", and ")}
          .
        </p>
      )}

      {/* Who pays */}
      {priceList.allowsGuaranteeLetters && priceList.issuers.length > 0 && (
        <Field label="Who pays" error={errorFor("payer")}>
          {(p) => (
            <Select {...p} value={draft.payer} onChange={(e) => update({ ...draft, payer: e.target.value })}>
              <option value="self">The customer</option>
              {priceList.issuers.map((i) => (
                <option key={i.code} value={i.code}>
                  {i.name}, with a guarantee letter
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}
      {withLetter && (
        <fieldset className="animate-reshape space-y-4 border-l-2 border-rule pl-4">
          <legend className="mb-2 text-meta font-medium text-ink-2">
            {priceList.issuers.find((i) => i.code === draft.payer)?.name} guarantee letter
          </legend>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Letter number" error={fields.number}>
              {(p) => <Input {...p} name="letterNumber" maxLength={60} />}
            </Field>
            <Field label="Date on the letter" error={fields.issuedOn}>
              {(p) => <Input {...p} name="letterIssuedOn" type="date" max={today} />}
            </Field>
            <Field label="Amount it covers" error={fields.amountCentavos}>
              {(p) => <Input {...p} name="letterAmount" inputMode="decimal" placeholder="0.00" />}
            </Field>
          </div>
          <Field label="The letter" hint="A PDF, or a clear photo (JPG or PNG), up to 8 MB" error={fields.letterFile ?? fields.letter}>
            {(p) => <FileInput {...p} ref={letterFile} accept="application/pdf,image/jpeg,image/png" />}
          </Field>
        </fieldset>
      )}

      <Field label="Notes" optional={!priceType?.requiresNotes} error={errorFor("notes")} hint={priceType?.requiresNotes ? `Say why this ${priceType.name} applies.` : undefined}>
        {(p) => (
          <Textarea {...p} value={draft.notes} onChange={(e) => update({ ...draft, notes: e.target.value })} rows={3} maxLength={2000} />
        )}
      </Field>

      {custom.length > 0 && (
        <fieldset>
          <legend className="mb-2 text-meta font-medium text-ink-2">More about this quote</legend>
          <ExtraFields fields={custom} draft={extra} onChange={setExtra} errors={fields} />
        </fieldset>
      )}

      <FormError message={error} />
      {/* The total and the button that commits to it, together, pinned where the hand already is. */}
      <div className="sticky bottom-3 z-10 -mx-2 flex flex-wrap items-center justify-between gap-3 rounded-[3px] bg-sheet px-4 py-3 shadow-overlay sm:-mx-4">
        <div className="min-w-0">
          <p className="text-meta text-ink-3">Total</p>
          <p className="text-figure tabular-nums">{preview ? fmt.peso(preview.totalCentavos) : "—"}</p>
          {preview && preview.approvalReasons.length > 0 && <p className="text-meta text-ink-2">Goes to your team lead for approval</p>}
        </div>
        <Button type="submit" variant="primary" loading={saving} className="!h-10 !px-6">
          Save quote
        </Button>
      </div>
    </form>
  );
}
