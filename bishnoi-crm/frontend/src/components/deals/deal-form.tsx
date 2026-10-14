"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAnticipation } from "@/src/platform/lib/anticipation";
import { toast } from "sonner";
import { Button, LinkButton, IconButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import { Combobox } from "@/src/platform/ui/pickers";
import { BundleTag, PromoTags, bundlesWith, promosFor, startingPromo, withPromoFlag } from "../catalogue/promo-tag";
import type { DealPriority, Assignable, Deal, DealLists, DealStage, ForecastCategory, Org, PriceList } from "@/src/platform/lib/types";
import { createDeal, howLikely, updateDeal, type DealInput } from "../../actions/deals";
import { OwnerField } from "../crm/owner-field";
import { PRIORITIES } from "./words";

/** promoId: the promo the product is sold under ("" none); it goes on to the deal's quote. */
type LineDraft = { key: number; productId: string; quantity: string; promoId: string };

/** A new deal's close, until changed: as the API does it (CLOSE_IN_DAYS). */
const CLOSE_IN_DAYS = 30;
function inDays(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** The name the API gives a new deal (deal_name in app/routers/deals.py), shown before it's saved. */
function suggestedName(customer: string, productNames: string[], closeOn: string): string {
  if (productNames.length) {
    const what = productNames.length === 1 ? productNames[0] : productNames.length === 2 ? `${productNames[0]} and ${productNames[1]}` : `${productNames[0]} and ${productNames.length - 1} more`;
    return `${what} for ${customer}`;
  }
  const month = closeOn ? new Date(`${closeOn}T00:00:00`).toLocaleDateString("en-PH", { month: "long", year: "numeric" }) : "";
  return month ? `${customer} · ${month}` : customer;
}

/**
 * Adding a deal to a customer, or changing one. Its value is either the
 * products on it, priced by the price rules as a quote would be (shown once
 * saved), or a figure typed in. Moving it to another stage brings that
 * stage's probability and forecast category unless they're changed here too.
 *
 * A new deal asks only what the rep decides: what they're buying, the stage
 * and when it should close (30 days from today, to start). The rest is filled
 * in and said in one line, with Change to open it: the name from the products
 * and the customer, the customer's only contact, the stage's probability and
 * forecast, the customer's lead source, and the rep as owner.
 *
 * Nothing worked out is typed: the forecast category follows the stage; the
 * lead source is the customer's; how likely it is comes from the stage and the
 * owner's record (app/likely.py), shown under the stage with why. The priority
 * is a switch at the top.
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
  const {
    pending,
    shakeClass,
    anticipateClass,
    execute,
    triggerShake,
    error,
    fieldErrors: fields,
    setError,
    setFieldErrors: setFields,
  } = useAnticipation<{
    name: string;
    contactId: string;
    stageCode: string;
    closeOn: string;
    value: string;
    priority: DealPriority | "";
    notes: string;
    ownerId: string;
    priceType: string;
    lines: LineDraft[];
  }>();
  const open = stages.filter((s) => s.outcome === "open" && (s.isActive || s.code === deal?.stage.code));
  const priceTypes = priceList?.usesPriceList ? priceList.priceTypes.filter((t) => t.entry !== "entered" && t.rule === "always") : [];
  const [name, setName] = useState(deal?.name ?? "");
  // A new deal's name follows its products until someone types one.
  const [named, setNamed] = useState(Boolean(deal));
  const [details, setDetails] = useState(Boolean(deal));
  const [contactId, setContactId] = useState(deal?.contact?.id ?? (contacts.length === 1 ? contacts[0].id : ""));
  const [stageCode, setStageCode] = useState(deal?.stage.code ?? open[0]?.code ?? "");
  // How likely, worked out for this stage and owner (null: not asked yet).
  const [likely, setLikely] = useState<{ probability: number; why: string } | null>(null);
  const [closeOn, setCloseOn] = useState(deal?.expectedCloseOn ?? inDays(CLOSE_IN_DAYS));
  const [value, setValue] = useState(deal && !deal.lines.length ? fmt.pesosText(deal.valueCentavos) : "");
  const [priority, setPriority] = useState<DealPriority | "">(deal?.priority ?? "");
  const [notes, setNotes] = useState(deal?.notes ?? "");
  const [ownerId, setOwnerId] = useState(deal?.owner?.id ?? people.find((p) => p.isMe)?.id ?? people[0]?.id ?? "");
  const [priceType, setPriceType] = useState(deal?.priceType ?? priceTypes[0]?.code ?? "");
  const [lines, setLines] = useState<LineDraft[]>(() => (deal?.lines ?? []).map((l, i) => ({ key: i, productId: l.productId, quantity: String(l.quantity), promoId: l.promoId ?? "" })));
  const stage = stages.find((s) => s.code === stageCode);
  const products = priceList?.products.filter((p) => p.prices[priceType] != null) ?? [];
  const withProducts = lines.some((l) => l.productId);
  // Each line's value at the chosen price, before promos: the saved deal shows the priced figure.
  const promos = priceList?.promos ?? [];
  // Sets whose every product can be valued at this price.
  const bundles = (priceList?.bundles ?? []).filter((b) => b.items.every((i) => products.some((p) => p.id === i.productId)));
  const nameOf = (id: string) => priceList?.products.find((p) => p.id === id)?.name ?? "a product";
  const withPromos = lines.some((l) => l.productId && l.promoId);
  const estimate = lines.reduce((sum, l) => sum + (products.find((p) => p.id === l.productId)?.prices[priceType] ?? 0) * (Number(l.quantity) || 0), 0);
  const isOpen = !deal || deal.state === "open";
  const productNames = lines.map((l) => products.find((p) => p.id === l.productId)?.name).filter(Boolean) as string[];
  const autoName = suggestedName(company.name, productNames, closeOn);
  const shownName = named ? name : autoName;
  const owner = people.find((p) => p.id === ownerId);
  const contact = contacts.find((c) => c.id === contactId);

  // Asked again whenever the stage or the owner changes.
  useEffect(() => {
    if (!stageCode || !isOpen) return;
    let live = true;
    howLikely(stageCode, ownerId || null).then((r) => live && setLikely(r));
    return () => {
      live = false;
    };
  }, [stageCode, ownerId, isOpen]);

  function setLine(key: number, change: Partial<LineDraft>) {
    setLines(lines.map((l) => (l.key === key ? { ...l, ...change } : l)));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const problems: Record<string, string> = {};
    if (named && !name.trim()) problems.name = "Name the deal, e.g. what's being bought.";
    if (!closeOn) problems.expectedCloseOn = "Pick when you expect it to close.";
    const typedValue = value.trim() ? fmt.toCentavos(value) : 0;
    if (!withProducts && typedValue === null) problems.valueCentavos = "Enter an amount, like 25000 or 25,000.00.";
    if (Object.keys(problems).length) {
      if (problems.name) setDetails(true);
      setFields(problems);
      setError("Some fields need a look.");
      triggerShake();
      toast.error("Some fields need a look.");
      return;
    }
    const input: DealInput = {
      // Not typed on a new deal: the API names it from its products and customer.
      ...(named ? { name: name.trim() } : {}),
      companyId: company.id,
      contactId: contactId || null,
      stageCode: stageCode || null,
      valueCentavos: withProducts ? null : typedValue,
      expectedCloseOn: closeOn,
      priority: priority || null,
      priceType: withProducts ? priceType : null,
      lines: lines.filter((l) => l.productId).map((l) => ({ productId: l.productId, quantity: Number(l.quantity) || 0, promoId: l.promoId || null })),
      notes: notes.trim() || null,
      ownerId: ownerId || null,
    };

    execute({
      anticipate: () => ({
        name,
        contactId,
        stageCode,
        closeOn,
        value,
        priority,
        notes,
        ownerId,
        priceType,
        lines: [...lines],
      }),
      rollback: (prev) => {
        setName(prev.name);
        setContactId(prev.contactId);
        setStageCode(prev.stageCode);
        setCloseOn(prev.closeOn);
        setValue(prev.value);
        setPriority(prev.priority);
        setNotes(prev.notes);
        setOwnerId(prev.ownerId);
        setPriceType(prev.priceType);
        setLines(prev.lines);
      },
      request: async () => {
        if (deal) {
          const change: Partial<DealInput> = {};
          if (input.name !== deal.name) change.name = input.name;
          if (input.contactId !== (deal.contact?.id ?? null)) change.contactId = input.contactId;
          if (isOpen && input.stageCode !== deal.stage.code) change.stageCode = input.stageCode;
          if (input.expectedCloseOn !== deal.expectedCloseOn) change.expectedCloseOn = input.expectedCloseOn;
          if ((input.priority ?? null) !== (deal.priority ?? null)) change.priority = input.priority;
          if (input.notes !== deal.notes) change.notes = input.notes;
          if (input.ownerId && input.ownerId !== deal.owner?.id) change.ownerId = input.ownerId;
          const before = JSON.stringify(deal.lines.map((l) => [l.productId, l.quantity, l.promoId ?? null]));
          const after = JSON.stringify(input.lines.map((l) => [l.productId, l.quantity, l.promoId ?? null]));
          if (before !== after || (withProducts && priceType !== deal.priceType)) {
            change.lines = input.lines;
            change.priceType = input.priceType;
          }
          // A typed value counts once there are no products (any more) to value it.
          if (!withProducts && input.valueCentavos !== deal.valueCentavos) change.valueCentavos = input.valueCentavos;
          if (Object.keys(change).length === 0) {
            router.push(`/deals/${deal.id}`);
            return { ok: true, data: deal };
          }
          return await updateDeal(deal.id, change);
        } else {
          return await createDeal(input);
        }
      },
      successMessage: (data) => ({
        title: deal ? "Changes saved" : "Deal added",
        description: data.name,
      }),
      onSuccess: (data) => {
        router.push(`/deals/${data.id}`);
        router.refresh();
      },
    });
  }

  const nameField = (
    <Field label="Deal name" error={fields.name} hint={named ? "What's being bought, e.g. 'Q4 antibiotics restock'." : "Made from the products and the customer; type to change it."} className="sm:col-span-2">
      {(p) => (
        <Input
          {...p}
          value={shownName}
          onChange={(e) => {
            setNamed(true);
            setName(e.target.value);
          }}
          maxLength={160}
        />
      )}
    </Field>
  );

  const value_ = (
    <section aria-labelledby="deal-products" className="space-y-3">
      <h2 id="deal-products" className="text-sm font-semibold text-ink">
        {deal ? "Value" : "What are they buying?"}
      </h2>
      {priceTypes.length > 0 && (
        <p className="text-meta text-ink-3">Add the products and quantities: the deal is priced by the price rules, and named after them. Or type a value instead.</p>
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
                    // A product on promo says so in the list, before it's picked.
                    <Combobox<string>
                      id={p.id}
                      aria-describedby={p["aria-describedby"]}
                      status={p["aria-invalid"] ? "error" : undefined}
                      value={l.productId}
                      onChange={(id) => setLine(l.key, { productId: id, promoId: startingPromo(promos, id) })}
                      options={[
                        { value: "", label: "Pick a product", promos: 0 },
                        ...products.map((x) => ({ value: x.id, label: `${x.name} (${x.code})`, promos: promosFor(promos, x.id).length, bundles: bundlesWith(bundles, x.id).length })),
                      ]}
                      optionRender={(o) => withPromoFlag(o.data.label, Number(o.data.promos) || 0, Number(o.data.bundles) || 0)}
                    />
                  )}
                </Field>
                <Field label="Quantity" error={fields[`lines.${i}.quantity`]}>
                  {(p) => <Input {...p} inputMode="numeric" value={l.quantity} onChange={(e) => setLine(l.key, { quantity: e.target.value })} />}
                </Field>
                <IconButton onClick={() => setLines(lines.filter((x) => x.key !== l.key))} tone="danger" className="h-9" label={`Remove product ${i + 1}`}>
                  <Trash2 className="size-4" aria-hidden />
                </IconButton>
                {(promosFor(promos, l.productId).length > 0 || bundlesWith(bundles, l.productId).length > 0 || fields[`lines.${i}.promoId`]) && (
                  <div className="flex flex-wrap gap-2 sm:col-span-full">
                    <PromoTags promos={promosFor(promos, l.productId)} fmt={fmt} appliedId={l.promoId} onPick={(id) => setLine(l.key, { promoId: id })} label={`Product ${i + 1}`} />
                    {bundlesWith(bundles, l.productId).map((b) => (
                      <BundleTag key={b.id} bundle={b} nameOf={nameOf} fmt={fmt} />
                    ))}
                    {fields[`lines.${i}.promoId`] && <p className="mt-1 text-meta text-danger">{fields[`lines.${i}.promoId`]}</p>}
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-4">
            <Button type="button" size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setLines([...lines, { key: Date.now(), productId: "", quantity: "1", promoId: "" }])}>
              Add a product
            </Button>
            {withProducts && <span className="text-meta text-ink-2">About {fmt.peso(estimate)} at list price{withPromos ? ", before promos" : ""}</span>}
          </div>
        </>
      ) : (
        <div className="flex flex-wrap items-end gap-4">
          {priceTypes.length > 0 && (
            <Button type="button" variant="primary" icon={<Plus className="size-4" aria-hidden />} onClick={() => setLines([{ key: Date.now(), productId: "", quantity: "1", promoId: "" }])}>
              Add a product
            </Button>
          )}
          <Field label={priceTypes.length > 0 ? "Or type the expected value" : "Expected value"} error={fields.valueCentavos} className="max-w-xs">
            {(p) => <Input {...p} inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} placeholder="0.00" />}
          </Field>
        </div>
      )}
    </section>
  );

  return (
    <form noValidate onSubmit={submit} className={`space-y-6 rounded-xl transition-all duration-300 ${shakeClass} ${anticipateClass}`}>
      <FormError message={error} />

      <div role="radiogroup" aria-label="Priority" className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-sm font-medium text-ink">Priority</span>
        {PRIORITIES.map((x) => {
          const on = (priority || null) === x.value;
          return (
            <button
              key={x.label}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => setPriority((x.value ?? "") as DealPriority | "")}
              className={`inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm transition-colors ${
                on ? "border-ink bg-ink text-white" : "border-rule-strong bg-sheet text-ink-2 hover:border-ink hover:text-ink"
              }`}
            >
              <span aria-hidden className="size-2 rounded-full" style={{ background: x.color }} />
              {x.label}
            </button>
          );
        })}
      </div>

      {!deal && value_}

      <div className={`grid gap-5 sm:grid-cols-2 ${deal ? "" : "border-t border-rule pt-5"}`}>
        {deal && nameField}
        {deal && (
          <div>
            <p className="mb-1 text-meta font-medium text-ink-2">Customer</p>
            <p className="flex h-9 items-center border-b border-rule text-sm">{company.name}</p>
          </div>
        )}
        {isOpen && (
          <Field
            label="Stage"
            error={fields.stageCode}
            hint={likely ? `Likely: ${likely.probability}%. ${likely.why}` : stage ? `Likely: ${stage.probability}%, the stage's own.` : undefined}
          >
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
        <Field label="Expected close date" error={fields.expectedCloseOn} hint={deal ? undefined : `${CLOSE_IN_DAYS} days from today, to start.`}>
          {(p) => <Input {...p} type="date" value={closeOn} onChange={(e) => setCloseOn(e.target.value)} />}
        </Field>
      </div>

      {!deal && !details && (
        <section aria-labelledby="filled-in" className="rounded-xl bg-mint px-5 py-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="filled-in" className="text-sm font-semibold text-ink">
              Filled in for you
            </h2>
            <Button type="button" size="sm" variant="quiet" onClick={() => setDetails(true)}>
              Change
            </Button>
          </div>
          <dl className="mt-2 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
            {(
              [
                ["Name", shownName],
                ["Contact", contact?.name ?? "No one in particular"],
                ["Likely", `${likely?.probability ?? stage?.probability ?? 0}%, worked out`],
                ["Lead source", company.leadSource ? `${company.leadSource} (the customer's)` : "Not recorded for this customer"],
                ["Owner", owner ? (owner.isMe ? `${owner.name} (you)` : owner.name) : "You"],
                ["Forecast", "Follows the stage"],
              ] as [string, string][]
            ).map(([k, v]) => (
              <div key={k} className="flex min-w-0 gap-2">
                <dt className="w-24 shrink-0 text-ink-3">{k}</dt>
                <dd className="min-w-0 truncate text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {details && (
        <div className="grid gap-5 sm:grid-cols-2">
          {!deal && nameField}
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
          <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} />
          <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
            {(p) => <Textarea {...p} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />}
          </Field>
        </div>
      )}

      {deal && <div className="border-t border-rule pt-5">{value_}</div>}

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
