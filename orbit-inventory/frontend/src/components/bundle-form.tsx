"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { createBundle, updateBundle, type BundleInput } from "../actions/inventory";
import { makeFormat } from "@/src/platform/lib/format";
import type { Bundle, InventoryReference, Org, Product } from "@/src/platform/lib/types";

type ItemDraft = { key: number; productId: string; qty: string };

const legend = "mb-1.5 text-meta font-medium text-ink-2";

/** What the set's products come to at their own prices, so the person setting
 *  the bundle price can see what they are giving away. Uses the first price
 *  type every product in the set has, which is the only honest comparison. */
function listValue(items: ItemDraft[], products: Map<string, Product>, codes: string[]) {
  const chosen = items.map((i) => products.get(i.productId)).filter((p): p is Product => !!p);
  if (!chosen.length || chosen.length !== items.length) return null;
  const code = codes.find((c) => chosen.every((p) => typeof p.prices[c] === "number"));
  if (!code) return null;
  const total = items.reduce((sum, item) => {
    const price = products.get(item.productId)?.prices[code] ?? 0;
    return sum + price * (Number(item.qty) || 0);
  }, 0);
  return total > 0 ? { code, total } : null;
}

export function BundleForm({
  module,
  reference,
  products,
  bundle,
  startsAsOneLine = true,
  canEdit = true,
  org,
}: {
  module: string;
  reference: InventoryReference;
  products: Product[];
  bundle?: Bundle;
  startsAsOneLine?: boolean;
  canEdit?: boolean;
  org: Org;
}) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [asOneLine, setAsOneLine] = useState(bundle ? bundle.asOneLine : startsAsOneLine);
  const [items, setItems] = useState<ItemDraft[]>(
    bundle?.items.length
      ? bundle.items.map((i, n) => ({ key: n, productId: i.productId, qty: String(i.qty) }))
      : [{ key: 0, productId: "", qty: "1" }],
  );
  const [divisions, setDivisions] = useState<Set<string>>(new Set(bundle?.divisionCodes ?? []));
  const [price, setPrice] = useState(fmt.pesosText(bundle?.priceCentavos) || "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const byId = useMemo(() => new Map(products.map((p) => [p.id, p])), [products]);
  const priceCodes = useMemo(() => reference.priceTypes.filter((t) => t.isActive).map((t) => t.code), [reference]);
  const onSale = products.filter((p) => p.isActive || items.some((i) => i.productId === p.id));

  const value = listValue(items, byId, priceCodes);
  const setPriceCentavos = fmt.toCentavos(price);
  const saving = value && setPriceCentavos && value.total > setPriceCentavos ? value.total - setPriceCentavos : null;
  const valueTypeName = value ? (reference.priceTypes.find((t) => t.code === value.code)?.name ?? value.code) : null;

  const change = (key: number, patch: Partial<ItemDraft>) =>
    setItems(items.map((i) => (i.key === key ? { ...i, ...patch } : i)));

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const problems: Record<string, string> = {};

    const cleaned = items
      .filter((i) => i.productId)
      .map((i) => ({ productId: i.productId, qty: /^\d+$/.test(i.qty.trim()) ? Number(i.qty) : 0 }));

    const input: BundleInput = {
      code: text("code"),
      name: text("name"),
      priceCentavos: setPriceCentavos ?? 0,
      asOneLine,
      items: cleaned,
      startsOn: text("startsOn"),
      endsOn: text("endsOn") || null,
      divisionCodes: [...divisions],
    };

    if (!input.priceCentavos) problems.priceCentavos = "Enter what the whole set costs, like 1800.00.";
    if (!cleaned.length) problems.items = "Put at least one product in the set.";
    else if (cleaned.some((i) => !i.qty)) problems.items = "Say how many of each the set contains.";
    else if (new Set(cleaned.map((i) => i.productId)).size !== cleaned.length) {
      problems.items = "Each product goes in once, with how many of it the set contains.";
    }
    if (divisions.size === 0) problems.divisionCodes = "Pick at least one division.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }

    start(async () => {
      const result = bundle ? await updateBundle(bundle.id, input) : await createBundle(input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success(bundle ? `${input.name} saved` : `${input.name} added`, {
        description: "Quotes already made keep the price they had.",
      });
      if (!bundle) {
        router.push(`/m/${module}/bundles`);
        router.refresh();
      }
    });
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <fieldset disabled={!canEdit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" hint="Reps pick it by this name" error={fields.name}>
            {(p) => <Input {...p} name="name" defaultValue={bundle?.name} maxLength={120} required placeholder="e.g. Starter Pack" />}
          </Field>
          <Field label="Code" hint="Like a product code" error={fields.code}>
            {(p) => <Input {...p} name="code" defaultValue={bundle?.code} maxLength={40} required placeholder="e.g. BDL-START" />}
          </Field>
        </div>

        <Field label="What the whole set costs" error={fields.priceCentavos}>
          {(p) => (
            <Input
              {...p}
              name="price"
              inputMode="decimal"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="1800.00"
            />
          )}
        </Field>

        <fieldset>
          <legend className={legend}>What is in the set</legend>
          <ul className="space-y-2">
            {items.map((item, i) => (
              <li key={item.key} className="flex items-end gap-2">
                <div className="w-20 shrink-0">
                  <label className="sr-only" htmlFor={`qty-${item.key}`}>
                    How many, item {i + 1}
                  </label>
                  <input
                    id={`qty-${item.key}`}
                    inputMode="numeric"
                    value={item.qty}
                    onChange={(e) => change(item.key, { qty: e.target.value })}
                    className="h-9 w-full border-b border-control bg-transparent text-right focus:border-hema focus:outline-none"
                  />
                </div>
                <span className="pb-2 text-ink-3" aria-hidden>
                  ×
                </span>
                <div className="min-w-0 flex-1">
                  <label className="sr-only" htmlFor={`product-${item.key}`}>
                    Product, item {i + 1}
                  </label>
                  <Select
                    id={`product-${item.key}`}
                    value={item.productId}
                    onChange={(e) => change(item.key, { productId: e.target.value })}
                  >
                    <option value="">Pick a product…</option>
                    {onSale.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} · {p.code}
                      </option>
                    ))}
                  </Select>
                </div>
                {items.length > 1 && (
                  <Button size="sm" variant="quiet" className="!px-2 pb-1" onClick={() => setItems(items.filter((x) => x.key !== item.key))}>
                    <X className="size-4" aria-hidden />
                    <span className="sr-only">Take item {i + 1} out of the set</span>
                  </Button>
                )}
              </li>
            ))}
          </ul>
          {items.length < 50 && (
            <Button
              size="sm"
              variant="quiet"
              className="mt-1 -ml-3"
              icon={<Plus className="size-4" aria-hidden />}
              onClick={() => setItems([...items, { key: Math.max(...items.map((x) => x.key)) + 1, productId: "", qty: "1" }])}
            >
              Add a product
            </Button>
          )}
          {fields.items && <p className="mt-1 text-meta text-danger">{fields.items}</p>}
          {value && (
            <p className="mt-2 text-meta text-ink-3">
              At {valueTypeName} those come to <span className="font-semibold text-ink-2">{fmt.peso(value.total)}</span>
              {saving ? <> — the set saves the customer {fmt.peso(saving)}.</> : "."}
            </p>
          )}
        </fieldset>

        <Choice
          legend="On the quote, show it as"
          name="asOneLine"
          value={asOneLine ? "one" : "items"}
          onChange={(v) => setAsOneLine(v === "one")}
          options={[
            { value: "one", label: "One line for the set" },
            { value: "items", label: "Its items, one line each" },
          ]}
        />
        <p className="-mt-3 text-meta text-ink-3">
          {asOneLine
            ? "The quote shows one line at the set price, with its contents named underneath."
            : "The quote shows a line per product, with the set price shared across them by what each lists at. The total is the same either way."}
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Starts" error={fields.startsOn}>
            {(p) => <Input {...p} name="startsOn" type="date" defaultValue={bundle?.startsOn ?? fmt.todayKey()} required />}
          </Field>
          <Field label="Ends" optional hint="Leave empty to keep it running" error={fields.endsOn}>
            {(p) => <Input {...p} name="endsOn" type="date" defaultValue={bundle?.endsOn ?? ""} />}
          </Field>
        </div>

        <fieldset>
          <legend className={legend}>Divisions that can sell it</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {reference.divisions.map((d) => (
              <label key={d.code} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={divisions.has(d.code)}
                  onChange={(e) => {
                    const next = new Set(divisions);
                    if (e.target.checked) next.add(d.code);
                    else next.delete(d.code);
                    setDivisions(next);
                  }}
                  className="size-4 accent-hema"
                />
                {d.name}
              </label>
            ))}
          </div>
          {fields.divisionCodes && <p className="mt-1 text-meta text-danger">{fields.divisionCodes}</p>}
        </fieldset>
      </fieldset>

      <FormError message={error} />
      {canEdit && (
        <Button type="submit" variant="primary" loading={pending}>
          {bundle ? "Save bundle" : "Add bundle"}
        </Button>
      )}
    </form>
  );
}
