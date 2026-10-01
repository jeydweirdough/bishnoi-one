"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { Assignable, Deal, DealLists, DealStage, ForecastCategory, Org, PriceList } from "@/src/platform/lib/types";
import { createDeal, updateDeal, type DealInput } from "../../actions/deals";
import { OwnerField } from "../crm/owner-field";
import { OPEN_CATEGORIES } from "./words";

type LineDraft = { key: number; productId: string; quantity: string };
type OpenCategory = Exclude<ForecastCategory, "closed">;

/**
 * Adding a deal to a customer, or changing one. Its value is either the
 * products on it, priced by the price rules as a quote would be (shown once
 * saved), or a figure typed in. Moving it to another stage brings that
 * stage's probability and forecast category unless they're changed here too.
 */
export function DealForm({
  org,
  company,
  contacts,
  stages,
  lists,
  people,
  priceList,
  deal,
}: {
  org: Org;
  /** leadSource: the customer's own, which a new deal starts with. */
  company: { id: string; name: string; leadSource?: string | null };
  contacts: { id: string; name: string }[];
  stages: DealStage[];
  lists: DealLists;
  people: Assignable[];
  /** The customer's price list, when this person may see prices; else only a typed value. */
  priceList: PriceList | null;
  deal?: Deal;
}) {
  const fmt = makeFormat(org);
  const router = useRouter();
  const [pending, start] = useTransition();
  const open = stages.filter((s) => s.outcome === "open" && (s.isActive || s.code === deal?.stage.code));
  const priceTypes = priceList?.usesPriceList ? priceList.priceTypes.filter((t) => t.entry !== "entered" && t.rule === "always") : [];
  const [name, setName] = useState(deal?.name ?? "");
  const [contactId, setContactId] = useState(deal?.contact?.id ?? "");
  const [stageCode, setStageCode] = useState(deal?.stage.code ?? open[0]?.code ?? "");
  const [category, setCategory] = useState<OpenCategory | "">(deal && deal.forecastCategory !== "closed" ? deal.forecastCategory : "");
  const [probability, setProbability] = useState(deal ? String(deal.probability) : "");
  const [closeOn, setCloseOn] = useState(deal?.expectedCloseOn ?? "");
  const [value, setValue] = useState(deal && !deal.lines.length ? fmt.pesosText(deal.valueCentavos) : "");
  const [source, setSource] = useState(deal ? (deal.leadSource ?? "") : (company.leadSource ?? ""));
  const [notes, setNotes] = useState(deal?.notes ?? "");
  const [ownerId, setOwnerId] = useState(deal?.owner?.id ?? people.find((p) => p.isMe)?.id ?? people[0]?.id ?? "");
  const [priceType, setPriceType] = useState(deal?.priceType ?? priceTypes[0]?.code ?? "");
  const [lines, setLines] = useState<LineDraft[]>(() => (deal?.lines ?? []).map((l, i) => ({ key: i, productId: l.productId, quantity: String(l.quantity) })));
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const stage = stages.find((s) => s.code === stageCode);
  const products = priceList?.products.filter((p) => p.prices[priceType] != null) ?? [];
  const withProducts = lines.some((l) => l.productId);
  // Each line's value at the chosen price, before promos: the saved deal shows the priced figure.
  const estimate = lines.reduce((sum, l) => sum + (products.find((p) => p.id === l.productId)?.prices[priceType] ?? 0) * (Number(l.quantity) || 0), 0);
  const isOpen = !deal || deal.state === "open";

  function setLine(key: number, change: Partial<LineDraft>) {
    setLines(lines.map((l) => (l.key === key ? { ...l, ...change } : l)));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const problems: Record<string, string> = {};
    if (!name.trim()) problems.name = "Name the deal, e.g. what's being bought.";
    if (!closeOn) problems.expectedCloseOn = "Pick when you expect it to close.";
    const typedValue = value.trim() ? fmt.toCentavos(value) : 0;
    if (!withProducts && typedValue === null) problems.valueCentavos = "Enter an amount, like 25000 or 25,000.00.";
    const probabilityNumber = probability.trim() === "" ? null : Number(probability);
    if (probabilityNumber !== null && !(Number.isInteger(probabilityNumber) && probabilityNumber >= 0 && probabilityNumber <= 100))
      problems.probability = "A whole number from 0 to 100.";
    if (Object.keys(problems).length) {
      setFields(problems);
      setError("Some fields need a look.");
      return;
    }
    const input: DealInput = {
      name: name.trim(),
      companyId: company.id,
      contactId: contactId || null,
      stageCode: stageCode || null,
      valueCentavos: withProducts ? null : typedValue,
      expectedCloseOn: closeOn,
      leadSource: source || null,
      priceType: withProducts ? priceType : null,
      lines: lines.filter((l) => l.productId).map((l) => ({ productId: l.productId, quantity: Number(l.quantity) || 0 })),
      notes: notes.trim() || null,
      ownerId: ownerId || null,
    };
    start(async () => {
      let result;
      if (deal) {
        const change: Partial<DealInput> = {};
        if (input.name !== deal.name) change.name = input.name;
        if (input.contactId !== (deal.contact?.id ?? null)) change.contactId = input.contactId;
        if (isOpen && input.stageCode !== deal.stage.code) change.stageCode = input.stageCode;
        if (isOpen && category && category !== deal.forecastCategory) change.forecastCategory = category;
        if (isOpen && probabilityNumber !== null && probabilityNumber !== deal.probability) change.probability = probabilityNumber;
        if (input.expectedCloseOn !== deal.expectedCloseOn) change.expectedCloseOn = input.expectedCloseOn;
        if (input.leadSource !== deal.leadSource) change.leadSource = input.leadSource;
        if (input.notes !== deal.notes) change.notes = input.notes;
        if (input.ownerId && input.ownerId !== deal.owner?.id) change.ownerId = input.ownerId;
        const before = JSON.stringify(deal.lines.map((l) => [l.productId, l.quantity]));
        const after = JSON.stringify(input.lines.map((l) => [l.productId, l.quantity]));
        if (before !== after || (withProducts && priceType !== deal.priceType)) {
          change.lines = input.lines;
          change.priceType = input.priceType;
        }
        // A typed value counts once there are no products (any more) to value it.
        if (!withProducts && input.valueCentavos !== deal.valueCentavos) change.valueCentavos = input.valueCentavos;
        if (Object.keys(change).length === 0) {
          router.push(`/deals/${deal.id}`);
          return;
        }
        result = await updateDeal(deal.id, change);
      } else {
        result = await createDeal({
          ...input,
          forecastCategory: category || null,
          probability: probabilityNumber,
        });
      }
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(deal ? "Changes saved" : "Deal added", { description: result.data.name });
      router.push(`/deals/${result.data.id}`);
      router.refresh();
    });
  }

  return (
    <form noValidate onSubmit={submit} className="space-y-6">
      <FormError message={error} />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field label="Deal name" error={fields.name} hint="What's being bought, e.g. 'Q4 antibiotics restock'." className="sm:col-span-2">
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus={!deal} maxLength={160} />}
        </Field>
        <div>
          <p className="mb-1 text-meta font-medium text-ink-2">Customer</p>
          <p className="flex h-9 items-center border-b border-rule text-sm">{company.name}</p>
        </div>
        <Field label="Contact" optional error={fields.contactId}>
          {(p) => (
            <Select {...p} value={contactId} onChange={(e) => setContactId(e.target.value)}>
              <option value="">No one in particular</option>
              {contacts.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {isOpen && (
          <Field label="Stage" error={fields.stageCode} hint={stage ? `${stage.probability}% likely when it enters this stage.` : undefined}>
            {(p) => (
              <Select {...p} value={stageCode} onChange={(e) => setStageCode(e.target.value)}>
                {open.map((s) => (
                  <option key={s.code} value={s.code}>
                    {s.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <Field label="Expected close date" error={fields.expectedCloseOn}>
          {(p) => <Input {...p} type="date" value={closeOn} onChange={(e) => setCloseOn(e.target.value)} />}
        </Field>
        {isOpen && (
          <Field label="Forecast category" optional error={fields.forecastCategory} hint={OPEN_CATEGORIES.find((c) => c.value === category)?.hint ?? "The stage's own, unless you pick one."}>
            {(p) => (
              <Select {...p} value={category} onChange={(e) => setCategory(e.target.value as OpenCategory | "")}>
                <option value="">{deal ? "Keep as it is" : "The stage's own"}</option>
                {OPEN_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {isOpen && (
          <Field label="Probability (%)" optional error={fields.probability}>
            {(p) => (
              <Input {...p} inputMode="numeric" value={probability} onChange={(e) => setProbability(e.target.value)} placeholder={stage ? String(stage.probability) : ""} />
            )}
          </Field>
        )}
        <Field label="Lead source" optional error={fields.leadSource} hint="Where the business came from.">
          {(p) => (
            <Select {...p} value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">Not said</option>
              {[...new Set([...lists.sources, ...(deal?.leadSource ? [deal.leadSource] : [])])].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} />
      </div>

      <section aria-labelledby="deal-products" className="space-y-3 border-t border-rule pt-5">
        <h2 id="deal-products" className="text-sm font-semibold text-ink">
          Value
        </h2>
        {priceTypes.length > 0 && (
          <p className="text-meta text-ink-3">Add the products being discussed and the deal is valued by the price rules. Or leave them out and type the value.</p>
        )}
        {withProducts || lines.length ? (
          <>
            <Field label="Valued at" error={fields.priceType} className="max-w-xs">
              {(p) => (
                <Select {...p} value={priceType} onChange={(e) => setPriceType(e.target.value)}>
                  {priceTypes.map((t) => (
                    <option key={t.code} value={t.code}>
                      {t.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <ul className="divide-y divide-rule">
              {lines.map((l, i) => (
                <li key={l.key} className="grid items-end gap-3 py-2 sm:grid-cols-[minmax(0,1fr)_6rem_2.25rem]">
                  <Field label={`Product ${i + 1}`} error={fields[`lines.${i}.productId`]}>
                    {(p) => (
                      <Select {...p} value={l.productId} onChange={(e) => setLine(l.key, { productId: e.target.value })}>
                        <option value="">Pick a product</option>
                        {products.map((x) => (
                          <option key={x.id} value={x.id}>
                            {x.name} ({x.code})
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label="Quantity" error={fields[`lines.${i}.quantity`]}>
                    {(p) => <Input {...p} inputMode="numeric" value={l.quantity} onChange={(e) => setLine(l.key, { quantity: e.target.value })} />}
                  </Field>
                  <button
                    type="button"
                    onClick={() => setLines(lines.filter((x) => x.key !== l.key))}
                    className="flex h-9 items-center justify-center text-ink-3 hover:text-danger"
                    aria-label={`Remove product ${i + 1}`}
                  >
                    <Trash2 className="size-4" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-4">
              <Button type="button" size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setLines([...lines, { key: Date.now(), productId: "", quantity: "1" }])}>
                Add a product
              </Button>
              {withProducts && <span className="text-meta text-ink-2">About {fmt.peso(estimate)} at list price</span>}
            </div>
          </>
        ) : (
          <div className="flex flex-wrap items-end gap-4">
            <Field label="Expected value" error={fields.valueCentavos} className="max-w-xs">
              {(p) => <Input {...p} inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} placeholder="0.00" />}
            </Field>
            {priceTypes.length > 0 && (
              <Button type="button" size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setLines([{ key: Date.now(), productId: "", quantity: "1" }])}>
                Value it by products instead
              </Button>
            )}
          </div>
        )}
      </section>

      <Field label="Notes" optional error={fields.notes}>
        {(p) => <Textarea {...p} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />}
      </Field>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="primary" loading={pending}>
          {deal ? "Save changes" : "Add deal"}
        </Button>
        <LinkButton href={deal ? `/deals/${deal.id}` : `/companies/${company.id}`} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
