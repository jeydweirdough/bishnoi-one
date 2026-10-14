"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAnticipation } from "@/src/platform/lib/anticipation";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { FileDrop } from "@/src/platform/ui/file-drop";
import { createQuote, previewQuote, type QuoteFor, type QuoteInput } from "../actions/customers";
import { makeFormat, percent, toBasisPoints, type Format } from "@/src/platform/lib/format";
import type { CustomField, Org, PriceList, QuotePreview, StockAnswer } from "@/src/platform/lib/types";
import { Flag } from "@/src/platform/ui/marks";
import { Combobox } from "@/src/platform/ui/pickers";
import { BundleTag, PromoTags, bundlesWith, promosFor, startingPromo, withPromoFlag } from "./catalogue/promo-tag";
import { TaxSummary } from "./tax-summary";
import { StockBadge } from "./catalogue/stock";
import { ExtraFields, extraChanges, toDraft, type ExtraDraft } from "./extra/extra-fields";
import { FormEntityProvider, useCan } from "./quick-add/can";
import { AddIssuer, AddProduct } from "./quick-add/forms";
import { QuickAdd } from "./quick-add/quick-add";

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
const LINE_GRID = "sm:grid-cols-[minmax(0,2.8fr)_4.5rem_minmax(0,1.6fr)_7rem_2.25rem]";
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

export function QuoteForm({
  to,
  priceList,
  org,
  fields: custom = [],
  stock = null,
  deal = null,
}: {
  to: QuoteFor;
  /** The deal it's made for, when started from one: its products, at its price, under its promos, start the quote. */
  deal?: { id: string; name: string; priceType?: string | null; lines?: { productId: string; quantity: number; promoId?: string | null }[] } | null;
  priceList: PriceList;
  org: Org;
  fields?: CustomField[];
  /** How much Inventory has of each product, by code, as the page opened. */
  stock?: StockAnswer | null;
}) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const can = useCan();
  const always = priceList.priceTypes.filter((t) => t.rule === "always");
  const withRx = priceList.priceTypes.filter((t) => t.rule === "with_rx");
  const [draft, setDraft] = useState<Draft>(() => {
    // From a deal: its lines, keeping each promo that still applies to its product.
    const known = (deal?.lines ?? []).filter((l) => priceList.products.some((p) => p.id === l.productId));
    return {
      priceType: always.find((t) => t.code === deal?.priceType)?.code ?? always[0]?.code ?? "",
      rx: false,
      payer: "self",
      notes: "",
      lines: known.length
        ? known.map((l, i) => ({
            ...blankLine(i),
            productId: l.productId,
            quantity: String(l.quantity),
            promoId: promosFor(priceList.promos, l.productId).some((p) => p.id === l.promoId) ? (l.promoId ?? "") : "",
          }))
        : [blankLine(0)],
    };
  });
  const [preview, setPreview] = useState<QuotePreview | null>(null);
  const [previewFields, setPreviewFields] = useState<Record<string, string>>({});
  const {
    pending: saving,
    shakeClass,
    anticipateClass,
    execute,
    triggerShake,
    error,
    fieldErrors: fields,
    setError,
    setFieldErrors: setFields,
  } = useAnticipation<Draft>();
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

  // Started from a deal's products: priced at once, as if just picked.
  useEffect(() => {
    if (draft.lines.some((l) => l.productId)) update(draft);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
      setError("Some fields need attention.");
      triggerShake();
      toast.error("Some fields need attention.");
      return;
    }

    const form = new FormData();
    form.set("quote", JSON.stringify({ ...toInput(fmt, draft, entered, letter), extra: extraChanges(custom, extra), dealId: deal?.id ?? null }));
    if (withLetter && file) form.set("letterFile", file);

    execute({
      anticipate: () => ({ ...draft }),
      rollback: (prev) => setDraft(prev),
      request: () => createQuote(to, form),
      successMessage: () => ({
        title: "Quote saved",
        description: preview?.approvalReasons.length || withLetter ? "It's waiting for approval now." : undefined,
      }),
      onSuccess: (data) => {
        router.push(`/quotes/${data.id}`);
        router.refresh();
      },
    });
  }

  if (!priceList.usesPriceList || priceList.priceTypes.length === 0) {
    return (
      <p className="text-ink-2">
        There are no prices to quote with yet. An administrator sets them up in Administration → Settings → Pricing and retention.
      </p>
    );
  }

  const productsFor = (code: string | undefined) =>
    entered ? priceList.products : priceList.products.filter((p) => code && p.prices[code] !== undefined);
  const errorFor = (key: string) => fields[key] ?? previewFields[key];
  const previewLine = (l: LineDraft) =>
    l.bundleId
      ? // One bundle makes one line or several; what the rep wants on its row
        // is what the whole set comes to.
        (preview?.lines.filter((x) => x.bundleId === l.bundleId) ?? [])
      : (preview?.lines.filter((x) => x.productId === l.productId && !x.bundleId) ?? []);
  const levelOf = (productId: string) => {
    const code = priceList.products.find((p) => p.id === productId)?.code;
    return stock?.linked && code ? stock.items[code] : undefined;
  };
  /** More asked for than Inventory has available: said, never blocked (more may come in before it ships). */
  const shortOf = (l: LineDraft): string | null => {
    const qty = /^\d+$/.test(l.quantity.trim()) ? Number(l.quantity) : 0;
    if (!stock?.linked || qty < 1) return null;
    const wants = l.bundleId
      ? (priceList.bundles.find((b) => b.id === l.bundleId)?.items ?? []).map((i) => ({ id: i.productId, qty: i.qty * qty }))
      : l.productId
        ? [{ id: l.productId, qty }]
        : [];
    for (const w of wants) {
      const level = levelOf(w.id);
      if (level?.state && w.qty > level.available) {
        const name = priceList.products.find((p) => p.id === w.id)?.name ?? "a product";
        return level.available > 0
          ? `Only ${level.available.toLocaleString()} of ${l.bundleId ? name : "these"} available now${level.inTransit ? `, ${level.inTransit.toLocaleString()} on the way` : ""}.`
          : `${l.bundleId ? name : "It"} is out of stock${level.inTransit ? `: ${level.inTransit.toLocaleString()} on the way` : ""}.`;
      }
    }
    return null;
  };
  const lineTotal = (rows: QuotePreview["lines"]) => (rows.length ? rows.reduce((sum, r) => sum + r.totalCentavos, 0) : null);
  // A bundle is only offerable when every product in it can be priced this way.
  const bundlesFor = (code: string | undefined) =>
    entered
      ? []
      : priceList.bundles.filter((b) => code && b.items.every((i) => priceList.products.find((p) => p.id === i.productId)?.prices[code] !== undefined));

  return (
    <form onSubmit={submit} noValidate className={`space-y-6 rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
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
        <legend className="mb-2 text-meta font-medium text-ink-2">{priceList.bundles.length > 0 ? "Products and bundles" : "Products"}</legend>
        <div aria-hidden className={`hidden gap-x-3 border-b border-rule pb-1.5 text-caps text-ink-3 uppercase sm:grid ${LINE_GRID}`}>
          <span>{priceList.bundles.length > 0 ? "Product or bundle" : "Product"}</span>
          <span className="text-right">Qty</span>
          <span>Extra discount</span>
          <span className="text-right">Total</span>
          <span />
        </div>
        <ul className="divide-y divide-rule border-b border-rule">
          {draft.lines.map((l, i) => {
            const at = `lines.${i}`;
            const product = priceList.products.find((p) => p.id === l.productId);
            const bundle = priceList.bundles.find((b) => b.id === l.bundleId);
            const promos = l.bundleId ? [] : promosFor(priceList.promos, l.productId);
            const rows = previewLine(l);
            const total = lineTotal(rows);
            const offeredBundles = bundlesFor(priceType?.code);
            // The sets this product is part of, that can be quoted at this price.
            const inBundles = l.bundleId ? [] : bundlesWith(offeredBundles, l.productId);
            return (
              <li key={l.key} className={`grid gap-x-3 gap-y-3 py-3 sm:items-start ${LINE_GRID}`}>
                <div className="min-w-0">
                  <span className={mobileLabel}>{priceList.bundles.length > 0 ? "Product or bundle" : "Product"}</span>
                  {/* A product on promo says so in the list, before it's picked. */}
                  <Combobox<string>
                    aria-label={`Line ${i + 1}: ${offeredBundles.length ? "product or bundle" : "product"}`}
                    status={errorFor(`${at}.productId`) || errorFor(`${at}.bundleId`) ? "error" : undefined}
                    value={l.bundleId ? `b:${l.bundleId}` : l.productId}
                    onChange={(picked) => {
                      const isBundle = picked.startsWith("b:");
                      setLine(l.key, {
                        productId: isBundle ? "" : picked,
                        bundleId: isBundle ? picked.slice(2) : "",
                        // A bundle takes no promo; a product starts with its only promo, or none to choose between.
                        promoId: isBundle ? "" : startingPromo(priceList.promos, picked),
                        discountKind: "",
                        discountValue: "",
                        unitPrice: "",
                      });
                    }}
                    className={cell}
                    options={[
                      { value: "", label: `Select ${offeredBundles.length ? "a product or bundle" : "a product"}…`, promos: 0 },
                      ...productsFor(priceType?.code).map((p) => ({
                        value: p.id,
                        label: `${p.name} · ${p.unit}${!entered && priceType ? ` · ${fmt.peso(p.prices[priceType.code])}` : ""}${levelOf(p.id)?.state === "out" ? " · out of stock" : ""}`,
                        promos: promosFor(priceList.promos, p.id).length,
                        bundles: bundlesWith(offeredBundles, p.id).length,
                      })),
                      ...(offeredBundles.length
                        ? [
                            {
                              label: "Bundles",
                              options: offeredBundles.map((b) => ({ value: `b:${b.id}`, label: `${b.name} · the set · ${fmt.peso(b.priceCentavos)}`, promos: 0 })),
                            },
                          ]
                        : []),
                    ]}
                    optionRender={(o) => withPromoFlag(o.data.label, Number(o.data.promos) || 0, Number(o.data.bundles) || 0)}
                  />
                  {product?.genericName && <p className="mt-0.5 text-meta text-ink-3">{product.genericName}</p>}
                  {product && stock?.linked && !stock.error && (
                    <p className="mt-1">
                      <StockBadge level={levelOf(product.id)} />
                    </p>
                  )}
                  {shortOf(l) && (
                    <p className="mt-1 text-meta text-due-today" role="status">
                      {shortOf(l)} The quote can still be made.
                    </p>
                  )}
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
                  <span className={mobileLabel}>Extra discount</span>
                  {/* Most lines have none, so it waits behind a link instead of asking on every line. */}
                  {l.bundleId ? (
                    <p className="text-meta text-ink-3 sm:h-9 sm:leading-9">—</p>
                  ) : l.discountKind ? (
                    <div className="flex items-end gap-1.5">
                      <Select
                        aria-label={`Line ${i + 1}: extra discount`}
                        value={l.discountKind}
                        onChange={(e) => setLine(l.key, { discountKind: e.target.value as LineDraft["discountKind"] })}
                        className={`${cell} w-auto`}
                      >
                        <option value="percent">% off</option>
                        <option value="amount">{fmt.symbol} off</option>
                      </Select>
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

                {(promos.length > 0 || inBundles.length > 0 || errorFor(`${at}.promoId`)) && (
                  <div className="flex flex-wrap gap-2 sm:col-span-full">
                    <PromoTags promos={promos} fmt={fmt} appliedId={l.promoId} onPick={(id) => setLine(l.key, { promoId: id })} label={`Line ${i + 1}`} />
                    {inBundles.map((b) => (
                      <BundleTag
                        key={b.id}
                        bundle={b}
                        nameOf={(id) => priceList.products.find((p) => p.id === id)?.name ?? "a product"}
                        fmt={fmt}
                        // The line becomes the set: one of it, as the bundle's price is for the set.
                        onUse={() => setLine(l.key, { productId: "", bundleId: b.id, quantity: "1", promoId: "", discountKind: "", discountValue: "", unitPrice: "" })}
                      />
                    ))}
                    {errorFor(`${at}.promoId`) && <p className="mt-1 text-meta text-danger">{errorFor(`${at}.promoId`)}</p>}
                  </div>
                )}
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
        {/* Not in the catalogue yet: made here, priced for this quote, and put on a line. */}
        {can("products.create") && !stock?.linked && draft.lines.length < 50 && (
          <div className="-mt-1">
            <QuickAdd label="New product, not in the list yet" title="New product">
              {(done) => (
                <AddProduct
                  org={org}
                  priceType={priceType && priceType.entry !== "entered" ? { code: priceType.code, name: priceType.name } : null}
                  onAdded={(id) => {
                    const empty = draft.lines.find((l) => !l.productId && !l.bundleId);
                    const key = empty ? empty.key : Math.max(...draft.lines.map((l) => l.key)) + 1;
                    const lines = empty ? draft.lines : [...draft.lines, blankLine(key)];
                    update({ ...draft, lines: lines.map((l) => (l.key === key ? { ...l, productId: id, bundleId: "" } : l)) });
                  }}
                  done={done}
                />
              )}
            </QuickAdd>
          </div>
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
            {!!preview.volumeDiscountCentavos && (
              <p className="flex justify-between text-ink-2">
                <span>Volume discounts</span>
                <span className="tabular-nums">−{fmt.peso(preview.volumeDiscountCentavos)}</span>
              </p>
            )}
            {!!preview.surchargeCentavos && (
              <p className="flex justify-between text-ink-2">
                <span>Surcharges</span>
                <span className="tabular-nums">+{fmt.peso(preview.surchargeCentavos)}</span>
              </p>
            )}
            {preview.priceGroup && <p className="text-right text-meta text-ink-3">{preview.priceGroup.name} prices</p>}
            {preview.tax && <TaxSummary tax={preview.tax} fmt={fmt} />}
            {preview.taxError && (
              <p className="mt-2">
                <Flag letter="!">{preview.taxError}</Flag>
              </p>
            )}
            {(preview.clidpWarnings ?? []).map((w) => (
              <p key={w} className="mt-2 text-left">
                <Flag letter="!">{w}</Flag>
              </p>
            ))}
          </>
        ) : (
          <p className="text-right text-meta text-ink-3">Add products to see the total.</p>
        )}
      </div>
      {preview && preview.approvalReasons.length > 0 && (
        <p className="animate-reshape rounded-lg bg-hema-tint px-3 py-2 text-meta text-ink-2">
          Your team lead approves this quote before it goes out:{" "}
          {preview.approvalReasons
            .map((r) => {
              if (r === "price") return `${priceType?.name} needs approval`;
              if (r === "discount") return `extra discounts are over ${percent(priceList.discountApprovalBp)}`;
              if (r === "margin") return "gross margin is under the 48% target floor (requires GM approval)";
              if (r === "s2_license") return "contains S-2 controlled substance (requires valid PDEA license)";
              return r;
            })
            .join(", and ")}
          .
        </p>
      )}

      {/* Who pays */}
      {priceList.allowsGuaranteeLetters && (priceList.issuers.length > 0 || can("products.edit")) && (
        <div>
        <Field label="Payer" error={errorFor("payer")}>
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
        {can("products.edit") && (
          <QuickAdd label="New issuer" title="New guarantee letter issuer">
            {(done) => <AddIssuer onAdded={(code) => update({ ...draft, payer: code })} done={done} />}
          </QuickAdd>
        )}
        </div>
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
          <Field label="The letter" error={fields.letterFile ?? fields.letter}>
            {(p) => <FileDrop {...p} ref={letterFile} accept="application/pdf,image/jpeg,image/png" note="A PDF, or a clear photo (JPG or PNG), up to 8 MB" maxBytes={8 * 1024 * 1024} />}
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
          <FormEntityProvider entity="quote">
            <ExtraFields fields={custom} draft={extra} onChange={setExtra} errors={fields} />
          </FormEntityProvider>
        </fieldset>
      )}

      <FormError message={error} />
      {/* The total and the button that commits to it, together, pinned where the hand already is. */}
      <div className="sticky bottom-3 z-10 -mx-2 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-sheet px-4 py-3 shadow-overlay sm:-mx-4">
        <div className="min-w-0">
          <p className="text-meta text-ink-3">Total</p>
          <p className="text-figure tabular-nums">{preview ? fmt.peso(preview.tax?.totalDueCentavos ?? preview.totalCentavos) : "—"}</p>
          {preview?.tax && <p className="text-meta text-ink-3">Amount due, with tax from Finance</p>}
          {preview && preview.approvalReasons.length > 0 && <p className="text-meta text-ink-2">Goes to your team lead for approval</p>}
        </div>
        <Button type="submit" variant="primary" loading={saving} className="!h-10 !px-6">
          Save quote
        </Button>
      </div>
    </form>
  );
}
