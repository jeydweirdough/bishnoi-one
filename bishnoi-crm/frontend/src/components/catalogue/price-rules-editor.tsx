"use client";

import { Pencil, Plus, Trash2, X } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, IconButton, TextButton } from "@/src/platform/ui/button";
import { ConfirmButton } from "@/src/platform/ui/confirm";
import { CellInput, Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { makeFormat, percentText, toBasisPoints, type Format } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { addPriceGroup, deletePriceGroup, deleteRule, saveRule, updatePriceGroup, type RuleInput } from "../../actions/price-rules";
import { StateTag } from "./state-tag";
import type { ConditionKind, PriceRule, PriceRules } from "./price-rules-types";

type ProductRef = { id: string; name: string; code: string };
type TypeRef = { code: string; name: string };

const KIND_WORDS: Record<ConditionKind, { one: string; hint: string }> = {
  group_price: { one: "Group price", hint: "A price group's own price for one product." },
  volume: { one: "Volume scale", hint: "A percent off that grows with quantity." },
  surcharge: { one: "Surcharge", hint: "An amount added per unit, or a percent of the line: cold chain, handling." },
};

/** Price groups: the kinds of customer priced alike. */
export function PriceGroupsEditor({ rules }: { rules: PriceRules }) {
  const [pending, start] = useTransition();
  const [adding, setAdding] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const edit = rules.can.edit;

  function add() {
    start(async () => {
      const r = await addPriceGroup({ code: code.trim(), name: name.trim() });
      if (r.ok) {
        toast.success("Price group added", { description: name.trim() });
        setAdding(false);
        setCode("");
        setName("");
        setError(null);
        return;
      }
      setError(r.fields?.code ?? r.fields?.name ?? r.error);
    });
  }

  return (
    <Sheet>
      {rules.groups.length === 0 && !adding ? (
        <Empty icon="customers" title="No price groups yet">
          A price group is a kind of customer priced alike: Hospital, Drugstore chain, Clinic. Put customers in one, then give it its own prices.
        </Empty>
      ) : (
        <ul className="divide-y divide-rule">
          {rules.groups.map((g) => (
            <li key={g.code} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <span className="flex min-w-0 items-center gap-1.5">
                <span className={`font-semibold ${g.isActive ? "" : "text-ink-3"}`}>{g.name}</span>
                <span className="font-mono text-meta text-ink-3">{g.code}</span>
                {edit && g.customers === 0 && (
                  <ConfirmButton
                    label=""
                    icon={<Trash2 className="size-3.5" aria-hidden />}
                    triggerVariant="quiet"
                    triggerSize="sm"
                    triggerClassName="!h-7 !px-1.5 text-ink-3"
                    triggerTitle={`Delete the ${g.name} price group`}
                    title={`Delete ${g.name}?`}
                    body="Its group prices go with it. Quotes already made keep their prices."
                    confirmLabel="Delete price group"
                    onConfirm={async () => {
                      const r = await deletePriceGroup(g.code);
                      if (!r.ok) toast.error(r.error);
                      return r.ok;
                    }}
                  />
                )}
              </span>
              <span className="flex items-center gap-3 text-meta text-ink-3">
                {g.customers} customer{g.customers === 1 ? "" : "s"}
                {edit && (
                  <TextButton
                   
                    size="inherit" className="font-semibold"
                    onClick={() =>
                      start(async () => {
                        const r = await updatePriceGroup(g.code, { isActive: !g.isActive });
                        if (!r.ok) toast.error(r.error);
                      })
                    }
                  >
                    {g.isActive ? `Switch ${g.name} off` : `Switch ${g.name} on`}
                  </TextButton>
                )}
              </span>
            </li>
          ))}
          {adding && (
            <li className="flex flex-wrap items-end gap-2 px-5 py-3">
              <CellInput className="w-28 !text-left" aria-label="Code" placeholder="HOSP" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} autoFocus />
              <CellInput className="w-56 !text-left" aria-label="Name" placeholder="Wholesale" value={name} onChange={(e) => setName(e.target.value)} />
              <Button size="sm" variant="primary" loading={pending} onClick={add} disabled={!code.trim() || !name.trim()}>
                Add
              </Button>
              <Button size="sm" variant="quiet" onClick={() => setAdding(false)} icon={<X className="size-4" aria-hidden />}>
                Cancel
              </Button>
            </li>
          )}
        </ul>
      )}
      <div className="border-t border-rule px-5 py-3">
        <FormError message={error} />
        {edit && !adding && (
          <Button size="sm" onClick={() => setAdding(true)} icon={<Plus className="size-4" aria-hidden />}>
            Add price group
          </Button>
        )}
      </div>
    </Sheet>
  );
}

function ruleTerms(fmt: Format, r: PriceRule): string {
  if (r.kind === "group_price") return `${fmt.peso(r.amountCentavos ?? 0)} each`;
  if (r.kind === "volume") return r.tiers.map((t) => `${t.minQty}+: ${percentText(t.percentBp)}% off`).join(" · ");
  return r.amountCentavos !== null ? `+${fmt.peso(r.amountCentavos)} per unit` : `+${percentText(r.percentBp ?? 0)}% of the line`;
}

/** The dated rules: group prices, volume scales and surcharges. */
export function PriceRulesEditor({ rules, products, types, org }: { rules: PriceRules; products: ProductRef[]; types: TypeRef[]; org: Org }) {
  const fmt = makeFormat(org);
  const [editing, setEditing] = useState<PriceRule | ConditionKind | null>(null);
  const edit = rules.can.edit;
  const kinds = Object.keys(KIND_WORDS) as ConditionKind[];

  return (
    <div className="space-y-4">
      {editing ? (
        <RuleForm
          key={typeof editing === "string" ? editing : editing.id}
          fmt={fmt}
          rule={typeof editing === "string" ? null : editing}
          kind={typeof editing === "string" ? editing : editing.kind}
          rules={rules}
          products={products}
          types={types}
          onDone={() => setEditing(null)}
        />
      ) : (
        edit && (
          <div className="flex flex-wrap gap-2">
            {kinds.map((k) => (
              <Button
                key={k}
                icon={<Plus className="size-4" aria-hidden />}
                onClick={() => setEditing(k)}
                disabled={k === "group_price" && rules.groups.filter((g) => g.isActive).length === 0}
                title={k === "group_price" && rules.groups.length === 0 ? "Add a price group first" : KIND_WORDS[k].hint}
              >
                {KIND_WORDS[k].one}
              </Button>
            ))}
          </div>
        )
      )}
      <Sheet>
        {rules.conditions.length === 0 ? (
          <Empty icon="pricing" title="No price rules yet">
            Every quote is priced at the list price (or a team&apos;s own), then promos and the rep&apos;s discount. Add rules to price by customer group, by
            volume, or to add a surcharge.
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {rules.conditions.map((r) => (
              <li key={r.id} className="flex items-start justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-1.5 font-medium">
                    {r.name}
                    {edit && (
                      <IconButton onClick={() => setEditing(r)} label={`Change ${r.name}`} size="sm">
                        <Pencil className="size-3.5" aria-hidden />
                      </IconButton>
                    )}
                    <StateTag state={r.state} />
                  </p>
                  <p className="text-meta text-ink-2">
                    {KIND_WORDS[r.kind].one} · {ruleTerms(fmt, r)}
                  </p>
                  <p className="text-meta text-ink-3">
                    {r.product ? r.product.name : "Every product"} · {r.priceGroup ? r.priceGroup.name : "every customer"}
                    {r.priceType ? ` · at ${types.find((t) => t.code === r.priceType)?.name ?? r.priceType}` : ""} ·{" "}
                    {r.startsOn || r.endsOn ? `${r.startsOn ? fmt.dateLabel(r.startsOn) : "now"} to ${r.endsOn ? fmt.dateLabel(r.endsOn) : "no end"}` : "no end date"}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </div>
  );
}

type Tier = { minQty: string; percent: string };

function RuleForm({
  fmt,
  rule,
  kind,
  rules,
  products,
  types,
  onDone,
}: {
  fmt: Format;
  rule: PriceRule | null;
  kind: ConditionKind;
  rules: PriceRules;
  products: ProductRef[];
  types: TypeRef[];
  onDone: () => void;
}) {
  const [pending, start] = useTransition();
  const [name, setName] = useState(rule?.name ?? "");
  const [productId, setProductId] = useState(rule?.product?.id ?? "");
  const [group, setGroup] = useState(rule?.priceGroup?.code ?? "");
  const [priceType, setPriceType] = useState(rule?.priceType ?? "");
  const [amount, setAmount] = useState(fmt.pesosText(rule?.amountCentavos ?? null));
  const [percent, setPercent] = useState(rule?.percentBp ? percentText(rule.percentBp) : "");
  const [by, setBy] = useState<"amount" | "percent">(rule && rule.kind === "surcharge" && rule.percentBp !== null ? "percent" : "amount");
  const [tiers, setTiers] = useState<Tier[]>(rule?.tiers.length ? rule.tiers.map((t) => ({ minQty: String(t.minQty), percent: percentText(t.percentBp) })) : [{ minQty: "", percent: "" }]);
  const [startsOn, setStartsOn] = useState(rule?.startsOn ?? "");
  const [endsOn, setEndsOn] = useState(rule?.endsOn ?? "");
  const [isActive, setActive] = useState(rule?.isActive ?? true);
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});

  function submit() {
    const whole = (t: string) => (/^\d+$/.test(t.trim()) ? Number(t) : 0);
    const input: RuleInput = {
      kind,
      name: name.trim(),
      productId: productId || null,
      priceGroupCode: group || null,
      priceTypeCode: kind === "group_price" ? priceType || null : null,
      amountCentavos: kind === "group_price" || (kind === "surcharge" && by === "amount") ? fmt.toCentavos(amount) : null,
      percentBp: kind === "surcharge" && by === "percent" ? toBasisPoints(percent) : null,
      tiers: kind === "volume" ? tiers.filter((t) => t.minQty || t.percent).map((t) => ({ minQty: whole(t.minQty), percentBp: toBasisPoints(t.percent) ?? 0 })) : [],
      startsOn: startsOn || null,
      endsOn: endsOn || null,
      isActive,
    };
    start(async () => {
      const r = await saveRule(rule?.id ?? null, input);
      if (r.ok) {
        toast.success(rule ? "Rule saved" : "Rule added", { description: input.name });
        onDone();
        return;
      }
      setError(r.error);
      setFields(r.fields ?? {});
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <h2 className="mb-1 font-semibold">{rule ? `Change ${rule.name}` : `Add a ${KIND_WORDS[kind].one.toLowerCase()}`}</h2>
      <p className="mb-4 text-meta text-ink-3">{KIND_WORDS[kind].hint}</p>
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
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder={kind === "volume" ? "Bulk orders" : kind === "surcharge" ? "Cold chain" : "Brand X for distributors"} autoFocus />}
          </Field>
          <Field label="Product" optional={kind !== "group_price"} error={fields.productId}>
            {(p) => (
              <Select {...p} value={productId} onChange={(e) => setProductId(e.target.value)}>
                <option value="">{kind === "group_price" ? "Select a product" : "All products"}</option>
                {products.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.name} · {x.code}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Price group" optional={kind !== "group_price"} error={fields.priceGroupCode}>
            {(p) => (
              <Select {...p} value={group} onChange={(e) => setGroup(e.target.value)}>
                <option value="">{kind === "group_price" ? "Select a group" : "All customers"}</option>
                {rules.groups
                  .filter((g) => g.isActive || g.code === rule?.priceGroup?.code)
                  .map((g) => (
                    <option key={g.code} value={g.code}>
                      {g.name}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          {kind === "group_price" && (
            <>
              <Field label={`Price each (${fmt.symbol})`} error={fields.amountCentavos}>
                {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="1250.00" />}
              </Field>
              <Field label="At price type" optional hint="Empty: at every price type." error={fields.priceTypeCode}>
                {(p) => (
                  <Select {...p} value={priceType} onChange={(e) => setPriceType(e.target.value)}>
                    <option value="">Every price type</option>
                    {types.map((t) => (
                      <option key={t.code} value={t.code}>
                        {t.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </>
          )}
          {kind === "surcharge" && (
            <div className="grid grid-cols-[auto_minmax(0,1fr)] items-end gap-3 sm:col-span-2">
              <Select aria-label="Surcharge by" value={by} onChange={(e) => setBy(e.target.value as "amount" | "percent")}>
                <option value="amount">An amount per unit</option>
                <option value="percent">A percent of the line</option>
              </Select>
              {by === "amount" ? (
                <Field label={`Per unit (${fmt.symbol})`} error={fields.amountCentavos}>
                  {(p) => <Input {...p} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="5.00" />}
                </Field>
              ) : (
                <Field label="Percent" error={fields.percentBp}>
                  {(p) => <Input {...p} inputMode="decimal" value={percent} onChange={(e) => setPercent(e.target.value)} placeholder="2" />}
                </Field>
              )}
            </div>
          )}
        </div>
        {kind === "volume" && (
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">Tiers</legend>
            <ul className="space-y-2">
              {tiers.map((t, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  From
                  <CellInput className="w-20" aria-label={`Tier ${i + 1}: from quantity`} inputMode="numeric" value={t.minQty} onChange={(e) => setTiers(tiers.map((x, j) => (j === i ? { ...x, minQty: e.target.value } : x)))} />
                  units,
                  <CellInput className="w-20" aria-label={`Tier ${i + 1}: percent off`} inputMode="decimal" value={t.percent} onChange={(e) => setTiers(tiers.map((x, j) => (j === i ? { ...x, percent: e.target.value } : x)))} />
                  % off
                  {tiers.length > 1 && (
                    <Button size="sm" variant="quiet" onClick={() => setTiers(tiers.filter((_, j) => j !== i))} aria-label={`Remove tier ${i + 1}`} icon={<X className="size-3.5" aria-hidden />} />
                  )}
                </li>
              ))}
            </ul>
            {tiers.length < 10 && (
              <Button size="sm" variant="quiet" className="mt-1 -ml-3" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setTiers([...tiers, { minQty: "", percent: "" }])}>
                Add tier
              </Button>
            )}
          </fieldset>
        )}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Starts" optional error={fields.startsOn}>
            {(p) => <Input {...p} type="date" value={startsOn} onChange={(e) => setStartsOn(e.target.value)} />}
          </Field>
          <Field label="Ends" optional error={fields.endsOn}>
            {(p) => <Input {...p} type="date" value={endsOn} onChange={(e) => setEndsOn(e.target.value)} />}
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" checked={isActive} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-hema" />
            Active
          </label>
        </div>
        <FormError message={error} />
        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="primary" loading={pending}>
            {rule ? "Save changes" : "Add rule"}
          </Button>
          <Button variant="quiet" onClick={onDone}>
            Cancel
          </Button>
          {rule && (
            <span className="ml-auto">
              <ConfirmButton
                label="Delete rule"
                title={`Delete ${rule.name}?`}
                body="Quotes already made keep the prices they were given. To stop it for now, switch it off instead."
                confirmLabel="Delete rule"
                onConfirm={async () => {
                  const r = await deleteRule(rule.id);
                  if (!r.ok) {
                    toast.error(r.error);
                    return false;
                  }
                  onDone();
                }}
              />
            </span>
          )}
        </div>
      </form>
    </Sheet>
  );
}
