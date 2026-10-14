"use client";

import { ArrowDown, ArrowUp } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, FormError } from "@/src/platform/ui/field";
import { Flag } from "@/src/platform/ui/marks";
import { saveProcedure } from "../../actions/price-rules";
import type { PriceRules } from "./price-rules-types";

const moved = <T,>(list: T[], from: number, by: number): T[] => {
  const to = from + by;
  if (to < 0 || to >= list.length) return list;
  const next = [...list];
  [next[from], next[to]] = [next[to], next[from]];
  return next;
};

function OrderList({
  items,
  names,
  onMove,
  toggle,
  disabled,
  locked,
}: {
  items: string[];
  names: Record<string, string>;
  onMove: (from: number, by: number) => void;
  toggle?: { off: string[]; set: (key: string, on: boolean) => void };
  disabled: boolean;
  locked?: (key: string) => string | null;
}) {
  const all = toggle ? [...items, ...toggle.off] : items;
  return (
    <ol className="divide-y divide-rule rounded-xl border border-rule">
      {all.map((key) => {
        const on = items.includes(key);
        const n = items.indexOf(key);
        const why = locked?.(key);
        return (
          <li key={key} className={`flex items-center gap-3 px-3 py-2 text-sm ${on ? "" : "text-ink-3"}`}>
            <span className="w-5 text-right font-semibold tabular-nums text-ink-3">{on ? n + 1 : "–"}</span>
            <span className="min-w-0 flex-1">
              {names[key] ?? key}
              {why && <span className="block text-meta text-ink-3">{why}</span>}
            </span>
            {toggle && (
              <label className="flex items-center gap-1.5 text-meta">
                <input type="checkbox" checked={on} disabled={disabled || Boolean(why)} onChange={(e) => toggle.set(key, e.target.checked)} className="size-4 accent-hema" />
                On
              </label>
            )}
            <span className="flex">
              <Button size="sm" variant="quiet" disabled={disabled || !on || n === 0} onClick={() => onMove(n, -1)} aria-label={`Move ${names[key]} up`} title="Earlier" icon={<ArrowUp className="size-4" aria-hidden />} />
              <Button size="sm" variant="quiet" disabled={disabled || !on || n === items.length - 1} onClick={() => onMove(n, 1)} aria-label={`Move ${names[key]} down`} title="Later" icon={<ArrowDown className="size-4" aria-hidden />} />
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * How a quote line is priced: where its price comes from (the first that has
 * one), the adjustments after it in order, and whether Finance adds tax.
 */
export function ProcedureEditor({ rules }: { rules: PriceRules }) {
  const [pending, start] = useTransition();
  const [price, setPrice] = useState(rules.procedure.price);
  const [adjust, setAdjust] = useState(rules.procedure.adjust);
  const [tax, setTax] = useState(rules.procedure.tax);
  const [inclusive, setInclusive] = useState(rules.pricesIncludeTax ? "yes" : "no");
  const [error, setError] = useState<string | null>(null);
  const edit = rules.can.edit;
  const sourceNames = Object.fromEntries(rules.sources.map((s) => [s.key, s.name]));
  const adjustNames = Object.fromEntries(rules.adjustments.map((a) => [a.key, a.name]));
  const offSources = rules.sources.map((s) => s.key).filter((k) => !price.includes(k));
  const offAdjust = rules.adjustments.map((a) => a.key).filter((k) => !adjust.includes(k));
  const changed =
    price.join() !== rules.procedure.price.join() ||
    adjust.join() !== rules.procedure.adjust.join() ||
    tax !== rules.procedure.tax ||
    (inclusive === "yes") !== rules.pricesIncludeTax;

  function save() {
    start(async () => {
      const result = await saveProcedure({ price, adjust, tax, pricesIncludeTax: inclusive === "yes" });
      if (result.ok) {
        toast.success("Price order saved", { description: "New quotes are priced this way." });
        setError(null);
        return;
      }
      setError(result.fields?.price ?? result.fields?.adjust ?? result.fields?.tax ?? result.error);
    });
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-3">
        <section>
          <h3 className="text-sm font-semibold">1 · The price</h3>
          <p className="mb-2 text-meta text-ink-3">The first of these that has a price for the customer and product. The list price is always there.</p>
          <OrderList
            items={price}
            names={sourceNames}
            disabled={!edit}
            onMove={(from, by) => setPrice(moved(price, from, by))}
            toggle={{ off: offSources, set: (key, on) => setPrice(on ? [...price.filter((k) => k !== "list_price"), key, "list_price"] : price.filter((k) => k !== key)) }}
            locked={(key) => (key === "list_price" ? "Always on: the price when nothing else has one." : null)}
          />
        </section>
        <section>
          <h3 className="text-sm font-semibold">2 · Then, in this order</h3>
          <p className="mb-2 text-meta text-ink-3">Each on what the line comes to so far. One switched off isn&apos;t applied.</p>
          <OrderList
            items={adjust}
            names={adjustNames}
            disabled={!edit}
            onMove={(from, by) => setAdjust(moved(adjust, from, by))}
            toggle={{ off: offAdjust, set: (key, on) => setAdjust(on ? [...adjust, key] : adjust.filter((k) => k !== key)) }}
          />
        </section>
        <section>
          <h3 className="text-sm font-semibold">3 · Tax, last</h3>
          <p className="mb-2 text-meta text-ink-3">Worked out by Finance, by its tax rules, and kept on the quote as the invoice will show it.</p>
          <label className={`flex items-center gap-2 rounded-lg border border-rule px-3 py-2 text-sm ${rules.financeLinked ? "" : "text-ink-3"}`}>
            <input type="checkbox" checked={tax} disabled={!edit || !rules.financeLinked} onChange={(e) => setTax(e.target.checked)} className="size-4 accent-hema" />
            Add tax from Finance
          </label>
          {!rules.financeLinked && (
            <p className="mt-2">
              <Flag letter="!">Not linked to Finance yet (FINANCE_API_URL, FINANCE_API_KEY)</Flag>
            </p>
          )}
          <div className="mt-3">
            <Choice
              name="inclusive"
              legend="Catalogue prices"
              value={inclusive}
              onChange={setInclusive}
              options={[
                { value: "yes", label: "Include VAT" },
                { value: "no", label: "Are before VAT" },
              ]}
            />
          </div>
        </section>
      </div>
      <FormError message={error} />
      {edit && (
        <Button variant="primary" loading={pending} disabled={!changed} onClick={save}>
          Save price order
        </Button>
      )}
    </div>
  );
}
