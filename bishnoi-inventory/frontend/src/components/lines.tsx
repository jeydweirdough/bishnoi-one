"use client";

import { Plus, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { CellInput, Select } from "@/src/platform/ui/field";
import { QuantityInput } from "./quantity";
import type { Format } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { QuickAdd, type Added } from "./quick-add";

export type PickableProduct = { id: string; sku: string; name: string; unit: string; costPrice: number; sellingPrice: number; status: string };
export type Line = { productId: string; quantity: string; money: string };

type Failure = { ok: false; error: string; fields?: Record<string, string> };
type Outcome<T> = { ok: true; data: T } | Failure;

/**
 * Saving a form: runs the action, keeps the API's words for what's wrong
 * (overall and per field), and on success says so and moves on.
 * Uses Anticipation Method with rollback and shake animations on error.
 */
export function useSave() {
  const router = useRouter();
  // Sent here to make something another page needs first (?then=/receipts/new):
  // once it's saved, back to that page. Only an address inside this app.
  const then = useSearchParams().get("then");
  const back = then && then.startsWith("/") && !then.startsWith("//") ? then : null;
  const [pending, start] = useTransition();
  const [shaking, setShaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const shakeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const triggerShake = useCallback(() => {
    if (shakeTimeoutRef.current) clearTimeout(shakeTimeoutRef.current);
    setShaking(true);
    shakeTimeoutRef.current = setTimeout(() => {
      setShaking(false);
    }, 480);
  }, []);

  function fail(message: string, fieldProblems?: Record<string, string>) {
    setError(message);
    if (fieldProblems) setFields(fieldProblems);
    triggerShake();
    toast.error(message);
  }

  function save<T>(run: () => Promise<Outcome<T>>, done: (data: T) => { message: string; go?: string }) {
    setError(null);
    setFields({});
    start(async () => {
      try {
        const result = await run();
        if (!result.ok) {
          setError(result.error);
          setFields(result.fields ?? {});
          triggerShake();
          toast.error(result.error || "Action could not be completed.");
          return;
        }
        setError(null);
        setFields({});
        const next = done(result.data);
        toast.success(next.message);
        if (back) router.push(back);
        else if (next.go) router.push(next.go);
        else router.refresh();
      } catch (err) {
        const errText = err instanceof Error ? err.message : "Connection failed. Please try again.";
        setError(errText);
        triggerShake();
        toast.error(errText);
      }
    });
  }

  return {
    pending,
    shaking,
    error,
    fields,
    save,
    fail,
    triggerShake,
    shakeClass: shaking ? "animate-shake ring-2 ring-danger/40 ring-offset-2 transition-all duration-300" : "",
    anticipateClass: pending ? "animate-anticipate pointer-events-none opacity-90" : "",
  };
}

/**
 * The lines of a document: a product and a quantity each, and (for purchase
 * orders and customer orders) a unit amount that starts at the product's own.
 */
export function LinesEditor({
  products,
  lines,
  onChange,
  errors,
  money,
  fmt,
  note,
  addProduct,
  limit,
}: {
  products: PickableProduct[];
  lines: Line[];
  onChange: (lines: Line[]) => void;
  errors: Record<string, string>;
  /** A unit amount column, and which price it starts from. */
  money?: { label: string; from: "costPrice" | "sellingPrice" };
  fmt: Format;
  /** Something to say under a line: what's available, for example. */
  note?: (productId: string) => string | null;
  /** "+ New product", for someone who may add one: it goes on the first empty line. */
  addProduct?: { org: Org; units: { code: string; name: string }[] };
  /** The most a line may ask for (what's available to send); none for stock coming in. */
  limit?: (productId: string) => number | undefined;
}) {
  // Products added from here, listed until the page's own list has them.
  const [fresh, setFresh] = useState<PickableProduct[]>([]);
  const known = new Set(products.map((p) => p.id));
  const all = [...products, ...fresh.filter((p) => !known.has(p.id))];
  const byId = new Map(all.map((p) => [p.id, p]));
  const offered = all.filter((p) => p.status === "active");

  function added(a: Added) {
    if (!a.product) return;
    const p: PickableProduct = { id: a.value, sku: a.product.sku, name: a.product.name, unit: a.product.unit, costPrice: a.product.costPrice, sellingPrice: a.product.sellingPrice, status: "active" };
    setFresh((list) => [...list, p]);
    const line = { productId: p.id, quantity: "", money: money ? fmt.pesosText(p[money.from]) : "" };
    const empty = lines.findIndex((l) => !l.productId);
    onChange(empty >= 0 ? lines.map((l, j) => (j === empty ? { ...line, quantity: l.quantity } : l)) : [...lines, line]);
  }

  function set(i: number, change: Partial<Line>) {
    const next = lines.map((line, j) => (j === i ? { ...line, ...change } : line));
    // Picking a product fills in its usual amount, when none has been typed.
    if (change.productId && money) {
      const p = byId.get(change.productId);
      if (p && !lines[i].money) next[i].money = fmt.pesosText(p[money.from]);
    }
    onChange(next);
  }

  // When the most changes under a line (another warehouse picked), it comes down to it.
  const limits = lines.map((l) => (l.productId && limit ? limit(l.productId) : undefined));
  const key = limits.join(",");
  useEffect(() => {
    if (!limit) return;
    const over = lines.some((l, i) => limits[i] !== undefined && Number(l.quantity) > limits[i]!);
    if (over) onChange(lines.map((l, i) => (limits[i] !== undefined && Number(l.quantity) > limits[i]! ? { ...l, quantity: String(Math.max(0, limits[i]!)) } : l)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const total = money ? lines.reduce((sum, l) => sum + (Number(l.quantity) || 0) * (fmt.toCentavos(l.money) ?? 0), 0) : 0;

  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-meta text-ink-3">
              <th scope="col" className="w-8 py-2 pr-2 font-semibold">#</th>
              <th scope="col" className="py-2 pr-3 font-semibold">Product</th>
              <th scope="col" className="w-28 px-3 py-2 text-right font-semibold">Quantity</th>
              {money && <th scope="col" className="w-36 px-3 py-2 text-right font-semibold">{money.label} ({fmt.symbol})</th>}
              {money && <th scope="col" className="w-32 px-3 py-2 text-right font-semibold">Amount</th>}
              <th scope="col" className="w-10 py-2">
                <span className="sr-only">Remove</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {lines.map((line, i) => {
              const p = byId.get(line.productId);
              const productError = errors[`lines.${i}.productId`];
              const qtyError = errors[`lines.${i}.quantity`];
              const said = line.productId && note ? note(line.productId) : null;
              return (
                <tr key={i}>
                  <td className="py-2.5 pr-2 align-top text-meta text-ink-3 tabular-nums">
                    <span className="inline-flex h-10 items-center">{i + 1}</span>
                  </td>
                  <td className="py-2.5 pr-3 align-top">
                    <Select
                      aria-label={`Line ${i + 1} product`}
                      aria-invalid={productError ? true : undefined}
                      value={line.productId}
                      onChange={(e) => set(i, { productId: e.target.value })}
                      className="w-full"
                    >
                      <option value="">Select a product…</option>
                      {offered.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.name} · {o.sku}
                        </option>
                      ))}
                      {/* Kept, so a line already on a document still shows what it is. */}
                      {p && p.status !== "active" && <option value={p.id}>{p.name} · {p.sku} ({p.status})</option>}
                    </Select>
                    {(productError || qtyError) && <p className="mt-1 text-meta text-danger">{productError || qtyError}</p>}
                    {said && <p className="mt-1 text-meta text-ink-3">{said}</p>}
                  </td>
                  <td className="px-3 py-2.5 align-top">
                    <div className="flex items-center justify-end gap-1.5">
                      <QuantityInput
                        label={`Line ${i + 1} quantity`}
                        invalid={Boolean(qtyError)}
                        value={line.quantity}
                        onChange={(quantity) => set(i, { quantity })}
                        max={limits[i]}
                        unit={p?.unit}
                      />
                      <span className="w-10 text-meta text-ink-3">{p?.unit ?? ""}</span>
                    </div>
                  </td>
                  {money && (
                    <td className="px-3 py-2.5 align-top">
                      <CellInput aria-label={`Line ${i + 1} ${money.label}`} inputMode="decimal" placeholder="0.00" value={line.money} onChange={(e) => set(i, { money: e.target.value })} className="w-32" />
                    </td>
                  )}
                  {money && (
                    <td className="px-3 py-2.5 text-right align-top tabular-nums">
                      <span className="inline-flex h-10 items-center text-ink">
                        {line.productId && line.quantity ? fmt.peso((Number(line.quantity) || 0) * (fmt.toCentavos(line.money) ?? 0)) : <span className="text-ink-3">—</span>}
                      </span>
                    </td>
                  )}
                  <td className="py-2.5 text-right align-top">
                    {lines.length > 1 && (
                      <button type="button" onClick={() => onChange(lines.filter((_, j) => j !== i))} className="mt-1.5 rounded-md p-1.5 text-ink-3 hover:bg-bench hover:text-danger" title="Remove this line">
                        <X className="size-4" aria-hidden />
                        <span className="sr-only">Remove line {i + 1}</span>
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {money && (
            <tfoot>
              <tr className="border-t border-rule-strong">
                <td colSpan={4} className="py-3 pr-3 text-right text-sm font-semibold text-ink">
                  Total
                </td>
                <td className="px-3 py-3 text-right text-base font-semibold tabular-nums">{fmt.peso(total)}</td>
                <td />
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-rule pt-3">
        <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => onChange([...lines, { productId: "", quantity: "", money: "" }])}>
          Add line
        </Button>
        {addProduct && <QuickAdd kind="product" onAdded={added} context={{ org: addProduct.org, units: addProduct.units }} label="New product" />}
      </div>
    </div>
  );
}

/** The lines as the API takes them. Blank lines are left out. */
export function linesOut(lines: Line[], fmt: Format, moneyKey?: "unitCost" | "unitPrice") {
  return lines
    .filter((l) => l.productId || l.quantity)
    .map((l) => ({
      productId: l.productId,
      quantity: Number(l.quantity) || 0,
      ...(moneyKey ? { [moneyKey]: fmt.toCentavos(l.money) ?? 0 } : {}),
    }));
}

export const blankLine = (): Line => ({ productId: "", quantity: "", money: "" });
