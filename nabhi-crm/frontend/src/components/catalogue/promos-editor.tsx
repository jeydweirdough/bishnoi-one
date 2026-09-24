"use client";

import { Pencil, Plus, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { makeFormat, percentText, toBasisPoints, type Format } from "@/src/platform/lib/format";
import { PROMO_KINDS, promoTerms } from "@/src/platform/lib/labels";
import type { Org, PromoKind, PromoRow } from "@/src/platform/lib/types";
import { deletePromo, savePromo, type PromoInput } from "../../actions/catalogue";
import { StateTag } from "./catalogue-tabs";

type ProductRef = { id: string; name: string; code: string };

/** Promos: what's running, what's coming, and adding or changing one. */
export function PromosEditor({ promos, products, org, mayEdit }: { promos: PromoRow[]; products: ProductRef[]; org: Org; mayEdit: boolean }) {
  const fmt = makeFormat(org);
  const [editing, setEditing] = useState<PromoRow | "new" | null>(null);
  const name = (id: string) => products.find((p) => p.id === id)?.name ?? "a product no longer here";

  return (
    <div className="space-y-5">
      {editing ? (
        <PromoForm key={editing === "new" ? "new" : editing.id} fmt={fmt} promo={editing === "new" ? null : editing} products={products} onDone={() => setEditing(null)} />
      ) : (
        mayEdit && (
          <Button variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing("new")}>
            Add promo
          </Button>
        )
      )}
      <Sheet>
        {promos.length === 0 ? (
          <Empty icon="promos" title="No promos yet">
            A promo is picked per line on a quote: a percent off, an amount off each, buy some and get some free, or a discount that grows with quantity.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {promos.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="font-medium">
                    {p.name} <StateTag state={p.state} />
                  </p>
                  <p className="text-meta text-ink-2">{promoTerms(fmt, p)}</p>
                  <p className="text-meta text-ink-3">
                    {p.productIds === null ? "Every product" : p.productIds.map(name).join(", ")}
                    {" · "}
                    {p.startsOn || p.endsOn
                      ? `${p.startsOn ? fmt.dateLabel(p.startsOn) : "Now"} to ${p.endsOn ? fmt.dateLabel(p.endsOn) : "no end"}`
                      : "No end date"}
                  </p>
                </div>
                {mayEdit && (
                  <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(p)} aria-label={`Change ${p.name}`}>
                    Change
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

type Tier = { minQty: string; percent: string };

function PromoForm({ fmt, promo, products, onDone }: { fmt: Format; promo: PromoRow | null; products: ProductRef[]; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [name, setName] = useState(promo?.name ?? "");
  const [kind, setKind] = useState<PromoKind>(promo?.kind ?? "percent");
  const [percent, setPercent] = useState(promo?.percentBp ? percentText(promo.percentBp) : "");
  const [amount, setAmount] = useState(fmt.pesosText(promo?.amountCentavos ?? null));
  const [buy, setBuy] = useState(String(promo?.buyQty ?? ""));
  const [free, setFree] = useState(String(promo?.freeQty ?? ""));
  const [tiers, setTiers] = useState<Tier[]>(
    promo?.tiers.length ? promo.tiers.map((t) => ({ minQty: String(t.minQty), percent: percentText(t.percentBp) })) : [{ minQty: "", percent: "" }],
  );
  const [every, setEvery] = useState(promo ? promo.productIds === null : true);
  const [picked, setPicked] = useState<string[]>(promo?.productIds ?? []);
  const [startsOn, setStartsOn] = useState(promo?.startsOn ?? "");
  const [endsOn, setEndsOn] = useState(promo?.endsOn ?? "");
  const [isActive, setActive] = useState(promo?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const whole = (text: string) => (/^\d+$/.test(text.trim()) ? Number(text) : null);

  function submit() {
    const problems: Record<string, string> = {};
    const input: PromoInput = {
      name: name.trim(),
      kind,
      percentBp: kind === "percent" ? toBasisPoints(percent) : null,
      amountCentavos: kind === "amount" ? fmt.toCentavos(amount) : null,
      buyQty: kind === "free_goods" ? whole(buy) : null,
      freeQty: kind === "free_goods" ? whole(free) : null,
      tiers:
        kind === "tiered"
          ? tiers.filter((t) => t.minQty.trim() || t.percent.trim()).map((t) => ({ minQty: whole(t.minQty) ?? 0, percentBp: toBasisPoints(t.percent) ?? 0 }))
          : [],
      productIds: every ? null : picked,
      startsOn: startsOn || null,
      endsOn: endsOn || null,
      isActive,
    };
    if (!input.name) problems.name = "Give it a name.";
    if (kind === "percent" && !input.percentBp) problems.percent = "A percent like 10.";
    if (kind === "amount" && !input.amountCentavos) problems.amount = "An amount like 25.00.";
    if (kind === "free_goods" && !input.buyQty) problems.buy = "A whole number.";
    if (kind === "free_goods" && !input.freeQty) problems.free = "A whole number.";
    if (kind === "tiered" && (!input.tiers.length || input.tiers.some((t) => !t.minQty || !t.percentBp))) problems.tiers = "Each tier needs a quantity and a percent.";
    if (!every && picked.length === 0) problems.productIds = "Pick at least one product, or choose every product.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }
    start(async () => {
      const result = await savePromo(promo?.id ?? null, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(promo ? "Promo saved" : "Promo added", { description: result.data.name });
      onDone();
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <h2 className="mb-4 font-semibold">{promo ? `Change ${promo.name}` : "Add a promo"}</h2>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="space-y-5"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus={!promo} />}
          </Field>
          <Field label="Kind" error={fields.kind}>
            {(p) => (
              <Select {...p} value={kind} onChange={(e) => setKind(e.target.value as PromoKind)}>
                {(Object.keys(PROMO_KINDS) as PromoKind[]).map((k) => (
                  <option key={k} value={k}>
                    {PROMO_KINDS[k]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {kind === "percent" && (
            <Field label="Percent off" error={fields.percent ?? fields.percentBp}>
              {(p) => <Input {...p} inputMode="decimal" value={percent} onChange={(e) => setPercent(e.target.value)} placeholder="10" />}
            </Field>
          )}
          {kind === "amount" && (
            <Field label={`Off each unit (${fmt.symbol})`} error={fields.amount ?? fields.amountCentavos}>
              {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="25.00" />}
            </Field>
          )}
          {kind === "free_goods" && (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Buy" error={fields.buy ?? fields.buyQty}>
                {(p) => <Input {...p} inputMode="numeric" value={buy} onChange={(e) => setBuy(e.target.value)} placeholder="10" />}
              </Field>
              <Field label="Get free" error={fields.free ?? fields.freeQty}>
                {(p) => <Input {...p} inputMode="numeric" value={free} onChange={(e) => setFree(e.target.value)} placeholder="1" />}
              </Field>
            </div>
          )}
        </div>

        {kind === "tiered" && (
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Tiers</legend>
            <ul className="space-y-2">
              {tiers.map((t, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  From
                  <input
                    aria-label={`Tier ${i + 1}: from quantity`}
                    inputMode="numeric"
                    value={t.minQty}
                    onChange={(e) => setTiers(tiers.map((x, j) => (j === i ? { ...x, minQty: e.target.value } : x)))}
                    className="h-9 w-20 rounded-[3px] border border-control px-2 text-right"
                  />
                  units,
                  <input
                    aria-label={`Tier ${i + 1}: percent off`}
                    inputMode="decimal"
                    value={t.percent}
                    onChange={(e) => setTiers(tiers.map((x, j) => (j === i ? { ...x, percent: e.target.value } : x)))}
                    className="h-9 w-20 rounded-[3px] border border-control px-2 text-right"
                  />
                  % off
                  {tiers.length > 1 && (
                    <Button size="sm" variant="quiet" onClick={() => setTiers(tiers.filter((_, j) => j !== i))} aria-label={`Remove tier ${i + 1}`}>
                      <X className="size-3.5" aria-hidden />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
            {tiers.length < 10 && (
              <Button size="sm" variant="quiet" className="mt-1 -ml-3" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setTiers([...tiers, { minQty: "", percent: "" }])}>
                Add tier
              </Button>
            )}
            {fields.tiers && <p className="mt-1 text-meta text-danger">{fields.tiers}</p>}
          </fieldset>
        )}

        <fieldset>
          <legend className="mb-2 text-sm font-semibold">Products</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={every} onChange={(e) => setEvery(e.target.checked)} className="size-4 accent-hema" />
            Every product
          </label>
          {!every && (
            <ul className="mt-2 grid max-h-64 gap-1 overflow-y-auto rounded-[3px] border border-rule p-2 sm:grid-cols-2">
              {products.map((p) => (
                <li key={p.id}>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={picked.includes(p.id)}
                      onChange={(e) => setPicked(e.target.checked ? [...picked, p.id] : picked.filter((x) => x !== p.id))}
                      className="size-4 accent-hema"
                    />
                    {p.name} <span className="text-meta text-ink-3">{p.code}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
          {fields.productIds && <p className="mt-1 text-meta text-danger">{fields.productIds}</p>}
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Starts" optional error={fields.startsOn}>
            {(p) => <Input {...p} type="date" value={startsOn} onChange={(e) => setStartsOn(e.target.value)} />}
          </Field>
          <Field label="Ends" optional error={fields.endsOn}>
            {(p) => <Input {...p} type="date" value={endsOn} onChange={(e) => setEndsOn(e.target.value)} />}
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
            Switched on
          </label>
        </div>

        <FormError message={error} />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {promo ? "Save changes" : "Add promo"}
          </Button>
          <Button variant="quiet" onClick={onDone}>
            Cancel
          </Button>
          {promo && (
            <span className="ml-auto">
              <ConfirmButton
                label="Delete"
                title={`Delete ${promo.name}?`}
                body="Quotes already made keep the discount they were given."
                confirmLabel="Delete promo"
                onConfirm={async () => {
                  const result = await deletePromo(promo.id);
                  if (!result.ok) {
                    toast.error(result.error);
                    return false;
                  }
                  toast.success(`${promo.name} deleted`);
                  onDone();
                  router.refresh();
                }}
              />
            </span>
          )}
        </div>
      </form>
    </Sheet>
  );
}
