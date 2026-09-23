"use client";

import { Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input } from "@/src/platform/ui/field";
import { createPromo, updatePromo, type PromoInput } from "../actions/inventory";
import { makeFormat, percentText, toBasisPoints } from "@/src/platform/lib/format";
import { PROMO_KINDS } from "@/src/platform/lib/labels";
import type { InventoryReference, Org, Product, Promo, PromoKind } from "@/src/platform/lib/types";

type TierDraft = { key: number; minQty: string; percent: string };

const legend = "mb-1.5 text-meta font-medium text-ink-2";

export function PromoForm({
  module,
  reference,
  products,
  promo,
  canEdit = true,
  org,
}: {
  module: string;
  reference: InventoryReference;
  products: Product[];
  promo?: Promo;
  canEdit?: boolean;
  org: Org;
}) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const [kind, setKind] = useState<PromoKind>(promo?.kind ?? "percent");
  const [tiers, setTiers] = useState<TierDraft[]>(
    promo?.tiers.length
      ? promo.tiers.map((t, i) => ({ key: i, minQty: String(t.minQty), percent: percentText(t.percentBp) }))
      : [{ key: 0, minQty: "", percent: "" }],
  );
  const [everyProduct, setEveryProduct] = useState(promo ? promo.productIds === null : false);
  const [chosen, setChosen] = useState<Set<string>>(new Set(promo?.productIds ?? []));
  const [divisions, setDivisions] = useState<Set<string>>(new Set(promo?.divisionCodes ?? []));
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  const toggle = (set: Set<string>, value: string, on: boolean) => {
    const next = new Set(set);
    if (on) next.add(value);
    else next.delete(value);
    return next;
  };

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const whole = (name: string) => (/^\d+$/.test(text(name)) ? Number(text(name)) : null);
    const problems: Record<string, string> = {};

    const input: PromoInput = {
      name: text("name"),
      kind,
      percentBp: kind === "percent" ? toBasisPoints(text("percent")) : null,
      amountCentavos: kind === "amount" ? fmt.toCentavos(text("amount")) : null,
      buyQty: kind === "free_goods" ? whole("buyQty") : null,
      freeQty: kind === "free_goods" ? whole("freeQty") : null,
      tiers: [],
      startsOn: text("startsOn"),
      endsOn: text("endsOn") || null,
      productIds: everyProduct ? null : [...chosen],
      divisionCodes: [...divisions],
    };
    if (kind === "percent" && (!input.percentBp || input.percentBp > 10_000)) problems.percentBp = "Enter a percent from 0.01 to 100.";
    if (kind === "amount" && !input.amountCentavos) problems.amountCentavos = "Enter an amount like 10.00.";
    if (kind === "free_goods" && !input.buyQty) problems.buyQty = "Enter a whole number.";
    if (kind === "free_goods" && !input.freeQty) problems.freeQty = "Enter a whole number.";
    if (kind === "tiered") {
      for (const t of tiers) {
        const minQty = /^\d+$/.test(t.minQty.trim()) ? Number(t.minQty) : null;
        const bp = toBasisPoints(t.percent);
        if (!minQty || !bp || bp > 10_000) {
          problems.tiers = "Each tier needs a minimum quantity and a percent from 0.01 to 100.";
          break;
        }
        input.tiers.push({ minQty, percentBp: bp });
      }
    }
    if (!everyProduct && chosen.size === 0) problems.productIds = "Pick at least one product, or choose every product.";
    if (divisions.size === 0) problems.divisionCodes = "Pick at least one division.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }

    start(async () => {
      const result = promo ? await updatePromo(promo.id, input) : await createPromo(input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success(promo ? `${input.name} saved` : `${input.name} added`, {
        description: "Quotes already made keep the discount they had.",
      });
      if (!promo) {
        router.push(`/m/${module}/promos`);
        router.refresh();
      }
    });
  }

  const onSale = products.filter((p) => p.isActive || chosen.has(p.id));

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <fieldset disabled={!canEdit} className="space-y-5">
        <Field label="Name" hint="Reps pick it by this name" error={fields.name}>
          {(p) => <Input {...p} name="name" defaultValue={promo?.name} maxLength={120} required placeholder="e.g. Vitamin C 10% off" />}
        </Field>

        <Choice
          legend="Kind"
          name="kind"
          value={kind}
          onChange={setKind}
          options={Object.entries(PROMO_KINDS).map(([value, label]) => ({ value: value as PromoKind, label }))}
        />

        <div className="animate-reshape grid gap-4 border-l-2 border-rule pl-4 sm:grid-cols-2" key={kind}>
          {kind === "percent" && (
            <Field label="Percent off the line" error={fields.percentBp}>
              {(p) => <Input {...p} name="percent" inputMode="decimal" defaultValue={percentText(promo?.percentBp)} placeholder="10" />}
            </Field>
          )}
          {kind === "amount" && (
            <Field label="Pesos off each unit" error={fields.amountCentavos}>
              {(p) => <Input {...p} name="amount" inputMode="decimal" defaultValue={fmt.pesosText(promo?.amountCentavos)} placeholder="10.00" />}
            </Field>
          )}
          {kind === "free_goods" && (
            <>
              <Field label="For every … bought" error={fields.buyQty}>
                {(p) => <Input {...p} name="buyQty" inputMode="numeric" defaultValue={promo?.buyQty ?? ""} placeholder="10" />}
              </Field>
              <Field label="… this many free" error={fields.freeQty}>
                {(p) => <Input {...p} name="freeQty" inputMode="numeric" defaultValue={promo?.freeQty ?? ""} placeholder="1" />}
              </Field>
            </>
          )}
          {kind === "tiered" && (
            <div className="sm:col-span-2">
              <p className={legend}>Tiers: the highest one the quantity reaches applies</p>
              <ul className="space-y-2">
                {tiers.map((t, i) => (
                  <li key={t.key} className="flex items-center gap-2 text-sm">
                    <span className="text-ink-3">From</span>
                    <input
                      aria-label={`Tier ${i + 1}: minimum quantity`}
                      inputMode="numeric"
                      value={t.minQty}
                      onChange={(e) => setTiers(tiers.map((x) => (x.key === t.key ? { ...x, minQty: e.target.value } : x)))}
                      className="h-8 w-20 border-b border-control bg-transparent text-right focus:border-hema focus:outline-none"
                    />
                    <span className="text-ink-3">units,</span>
                    <input
                      aria-label={`Tier ${i + 1}: percent off`}
                      inputMode="decimal"
                      value={t.percent}
                      onChange={(e) => setTiers(tiers.map((x) => (x.key === t.key ? { ...x, percent: e.target.value } : x)))}
                      className="h-8 w-16 border-b border-control bg-transparent text-right focus:border-hema focus:outline-none"
                    />
                    <span className="text-ink-3">% off</span>
                    {tiers.length > 1 && (
                      <Button size="sm" variant="quiet" className="!px-2" onClick={() => setTiers(tiers.filter((x) => x.key !== t.key))}>
                        <X className="size-4" aria-hidden />
                        <span className="sr-only">Remove tier {i + 1}</span>
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
              {tiers.length < 10 && (
                <Button
                  size="sm"
                  variant="quiet"
                  className="mt-1 -ml-3"
                  icon={<Plus className="size-4" aria-hidden />}
                  onClick={() => setTiers([...tiers, { key: Math.max(...tiers.map((x) => x.key)) + 1, minQty: "", percent: "" }])}
                >
                  Add tier
                </Button>
              )}
              {fields.tiers && <p className="mt-1 text-meta text-danger">{fields.tiers}</p>}
            </div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Starts" error={fields.startsOn}>
            {(p) => <Input {...p} name="startsOn" type="date" defaultValue={promo?.startsOn ?? fmt.todayKey()} required />}
          </Field>
          <Field label="Ends" optional hint="Leave empty to keep it running" error={fields.endsOn}>
            {(p) => <Input {...p} name="endsOn" type="date" defaultValue={promo?.endsOn ?? ""} />}
          </Field>
        </div>

        <fieldset>
          <legend className={legend}>Products</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={everyProduct} onChange={(e) => setEveryProduct(e.target.checked)} className="size-4 accent-hema" />
            Every product
          </label>
          {!everyProduct && (
            <div className="animate-reshape mt-2 grid max-h-64 gap-1.5 overflow-y-auto rounded-[3px] border border-rule p-3 sm:grid-cols-2">
              {onSale.map((p) => (
                <label key={p.id} className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={chosen.has(p.id)}
                    onChange={(e) => setChosen(toggle(chosen, p.id, e.target.checked))}
                    className="mt-0.5 size-4 accent-hema"
                  />
                  <span>
                    {p.name}
                    <span className="block text-meta text-ink-3">{p.code} · {p.unit}</span>
                  </span>
                </label>
              ))}
            </div>
          )}
          {fields.productIds && <p className="mt-1 text-meta text-danger">{fields.productIds}</p>}
        </fieldset>

        <fieldset>
          <legend className={legend}>Divisions that can use it</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {reference.divisions.map((d) => (
              <label key={d.code} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={divisions.has(d.code)}
                  onChange={(e) => setDivisions(toggle(divisions, d.code, e.target.checked))}
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
          {promo ? "Save promo" : "Add promo"}
        </Button>
      )}
    </form>
  );
}
