"use client";

import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/modules/admin/platform/ui/button";
import { Choice, Field, FormError, Input } from "@/src/modules/admin/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/modules/admin/platform/ui/sheet";
import {
  addIssuer,
  addPriceType,
  saveDivisionRules,
  saveSellingDefaults,
  updateIssuer,
  updatePriceType,
  type DivisionRulesInput,
} from "@/src/modules/admin/actions/pricing";
import { percentText, toBasisPoints } from "@/src/modules/admin/platform/lib/format";
import type { DivisionPricing, Issuer, PriceEntry, PriceRule, PriceType, PricingRules } from "@/src/modules/admin/platform/lib/types";
import { PickList, SaveBar } from "@/src/modules/admin/platform/ui/pick-list";

// Pricing rules, one question at a time: pick a division and see only its
// choices; price types and guarantee-letter issuers are their own views
// (the page's switch above). Nothing here shows every division's every
// choice at once.

export type PricingView = "divisions" | "types" | "issuers" | "defaults";

export function PricingRulesEditor({ data, view }: { data: PricingRules; view: PricingView }) {
  if (view === "types") return <PriceTypes types={data.priceTypes} />;
  if (view === "issuers") return <Issuers issuers={data.issuers} />;
  if (view === "defaults") return <SellingDefaults bundlesAsOneLine={data.bundlesAsOneLine} />;
  return <DivisionRules data={data} />;
}

// --- company-wide defaults -----------------------------------------------------------
//
// Only what a new row starts as. Saving here never reaches back and changes
// something someone already set up, which is why it is its own view rather
// than a switch tucked into a division's rules.

function SellingDefaults({ bundlesAsOneLine }: { bundlesAsOneLine: boolean }) {
  const [oneLine, setOneLine] = useState(bundlesAsOneLine);
  const [saving, start] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const dirty = oneLine !== bundlesAsOneLine;

  const save = () =>
    start(async () => {
      const result = await saveSellingDefaults({ bundlesAsOneLine: oneLine });
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setError(null);
      toast.success("Saved", { description: "Bundles already made are unchanged." });
    });

  return (
    <>
      <Sheet className="max-w-2xl px-5 pt-4 pb-5">
        <SectionTitle icon="bundles">New bundles</SectionTitle>
        <p className="mb-4 text-meta text-ink-3">
          A bundle is a set of products at one price. This is only how a new one starts — whoever adds it can still choose, and
          bundles that already exist are never changed by what you set here.
        </p>
        <Choice
          legend="On the quote, a new bundle shows as"
          name="bundlesAsOneLine"
          value={oneLine ? "one" : "items"}
          onChange={(v) => setOneLine(v === "one")}
          options={[
            { value: "one", label: "One line for the set" },
            { value: "items", label: "Its items, one line each" },
          ]}
        />
        <p className="mt-2 text-meta text-ink-3">
          {oneLine
            ? "One line at the set price, with its contents named underneath. Shorter to read, one code to quote."
            : "A line per product, with the set price shared across them by what each lists at. The customer sees what they got."}
        </p>
      </Sheet>
      {dirty && (
        <SaveBar
          what="Unsaved change to how new bundles start"
          saving={saving}
          onSave={save}
          onDiscard={() => (setOneLine(bundlesAsOneLine), setError(null))}
          error={<FormError message={error} />}
        />
      )}
    </>
  );
}

// --- divisions -----------------------------------------------------------------------

type Draft = {
  usesPriceList: boolean;
  allowsGuaranteeLetters: boolean;
  discountText: string;
  priceTypes: Record<string, PriceRule>;
};

function toDraft(d: DivisionPricing): Draft {
  return {
    usesPriceList: d.usesPriceList,
    allowsGuaranteeLetters: d.allowsGuaranteeLetters,
    discountText: percentText(d.discountApprovalBp),
    priceTypes: { ...d.priceTypes },
  };
}

function sameDraft(a: Draft, b: Draft) {
  const types = (d: Draft) => JSON.stringify(Object.entries(d.priceTypes).sort());
  return (
    a.usesPriceList === b.usesPriceList &&
    a.allowsGuaranteeLetters === b.allowsGuaranteeLetters &&
    toBasisPoints(a.discountText) === toBasisPoints(b.discountText) &&
    types(a) === types(b)
  );
}

/** "SRP, Patient's, Doctor's with Rx": the division's rules in one line, for the list. */
function summary(draft: Draft, types: PriceType[]): string {
  if (!draft.usesPriceList) return "Notes only, no price list";
  const on = types.filter((t) => draft.priceTypes[t.code]);
  if (!on.length) return "No prices picked yet";
  return on.map((t) => `${t.name.replace(/ Price$/, "")}${draft.priceTypes[t.code] === "with_rx" ? " with Rx" : ""}`).join(", ");
}

function DivisionRules({ data }: { data: PricingRules }) {
  const [selected, setSelected] = useState(data.divisions[0]?.code ?? "");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [saving, startSave] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const types = data.priceTypes.filter((t) => t.isActive);
  const issuers = data.issuers.filter((i) => i.isActive).map((i) => i.name);
  const saved = Object.fromEntries(data.divisions.map((d) => [d.code, toDraft(d)]));
  const current = (code: string) => drafts[code] ?? saved[code];
  const isDirty = (code: string) => Boolean(drafts[code] && !sameDraft(drafts[code], saved[code]));
  const dirty = data.divisions.filter((d) => isDirty(d.code));
  const division = data.divisions.find((d) => d.code === selected) ?? data.divisions[0];
  if (!division) return null;
  const draft = current(division.code);

  function change(patch: Partial<Draft>) {
    setDrafts({ ...drafts, [division.code]: { ...draft, ...patch } });
  }

  function setRule(type: string, rule: PriceRule | null) {
    const next = { ...draft.priceTypes };
    if (rule) next[type] = rule;
    else delete next[type];
    change({ priceTypes: next });
  }

  function save() {
    const body: Record<string, DivisionRulesInput> = {};
    for (const d of dirty) {
      const bp = toBasisPoints(drafts[d.code].discountText);
      if (bp === null || bp > 10_000) {
        setSelected(d.code);
        setError(`${d.name}: enter the discount limit as a percent from 0 to 100.`);
        return;
      }
      const { usesPriceList, allowsGuaranteeLetters, priceTypes } = drafts[d.code];
      body[d.code] = { usesPriceList, allowsGuaranteeLetters, discountApprovalBp: bp, priceTypes };
    }
    startSave(async () => {
      const result = await saveDivisionRules(body);
      if (!result.ok) return setError(result.error);
      setDrafts({});
      setError(null);
      toast.success("Pricing rules saved", { description: "Reps see the change on their next quote." });
    });
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-start">
      <PickList
        title="Divisions"
        icon="divisions"
        items={data.divisions.map((d) => ({ key: d.code, label: d.name, detail: summary(current(d.code), types), unsaved: isDirty(d.code) }))}
        selected={division.code}
        onSelect={setSelected}
      />

      <div className="min-w-0">
        <Sheet className="px-5 pt-4 pb-5">
          <h2 className="text-heading">{division.name}</h2>
          <p className="text-meta text-ink-3">How reps in {division.name} price a quote.</p>

          <div className="mt-5 space-y-6">
            <Choice
              legend="Quotes are priced from"
              name={`source-${division.code}`}
              value={draft.usesPriceList ? "list" : "notes"}
              options={[
                { value: "list", label: "The price list" },
                { value: "notes", label: "Notes only, no price list" },
              ]}
              onChange={(v) => change({ usesPriceList: v === "list" })}
            />

            {draft.usesPriceList && (
              <fieldset className="min-w-0">
                <legend className="text-meta font-medium text-ink-2">Prices reps can quote with</legend>
                <ul className="mt-1.5 divide-y divide-rule border-y border-rule">
                  {types.map((t) => {
                    const rule = draft.priceTypes[t.code];
                    const notes = [t.entry === "entered" && "typed on the quote", t.requiresNotes && "needs notes", t.needsApproval && "Finance approves"]
                      .filter(Boolean)
                      .join(" · ");
                    return (
                      <li key={t.code} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5">
                        <label className="flex min-w-0 cursor-pointer items-start gap-3">
                          <input suppressHydrationWarning
                            type="checkbox"
                            checked={Boolean(rule)}
                            onChange={(e) => setRule(t.code, e.target.checked ? "always" : null)}
                            className="mt-0.5 size-4 shrink-0 accent-hema"
                          />
                          <span className="min-w-0">
                            <span className={rule ? "font-semibold" : ""}>{t.name}</span>
                            {notes && <span className="block text-meta text-ink-3">{notes}</span>}
                          </span>
                        </label>
                        {/* Only asked once the price is on. */}
                        {rule && (
                          <label className="ml-7 inline-flex cursor-pointer items-center gap-2 text-meta text-ink-2 sm:ml-0">
                            <input suppressHydrationWarning
                              type="checkbox"
                              checked={rule === "with_rx"}
                              onChange={(e) => setRule(t.code, e.target.checked ? "with_rx" : "always")}
                              className="size-3.5 accent-hema"
                            />
                            Only when the quote has a prescription
                          </label>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </fieldset>
            )}

            <label className="flex cursor-pointer items-start gap-3">
              <input suppressHydrationWarning
                type="checkbox"
                checked={draft.allowsGuaranteeLetters}
                onChange={(e) => change({ allowsGuaranteeLetters: e.target.checked })}
                className="mt-0.5 size-4 shrink-0 accent-hema"
              />
              <span>
                <span className="font-medium">Takes guarantee letters</span>
                <span className="block text-meta text-ink-3">
                  A quote can be paid with a letter{issuers.length ? ` from ${issuers.join(" or ")}` : ""}.
                </span>
              </span>
            </label>

            <Field label="Finance approves a rep's own discount over" hint="Per line. Promos don't count toward it." className="max-w-xs">
              {(p) => (
                <span className="flex items-center gap-2">
                  <Input
                    {...p}
                    inputMode="decimal"
                    value={draft.discountText}
                    onChange={(e) => change({ discountText: e.target.value })}
                    className="max-w-20 text-right"
                  />
                  <span className="text-ink-3">%</span>
                </span>
              )}
            </Field>
          </div>
        </Sheet>

        {dirty.length > 0 && (
          <SaveBar
            what={`Unsaved changes to ${dirty.map((d) => d.name).join(", ")}`}
            saving={saving}
            onSave={save}
            onDiscard={() => (setDrafts({}), setError(null))}
            error={<FormError message={error} />}
          />
        )}
      </div>
    </div>
  );
}

// --- price types -------------------------------------------------------------------------

function flags(t: PriceType): string {
  return [
    t.entry === "list" ? "From the price list" : "Typed on the quote",
    t.requiresNotes && "needs notes",
    t.needsApproval && "Finance approves",
  ]
    .filter(Boolean)
    .join(" · ");
}

function PriceTypes({ types }: { types: PriceType[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Sheet className="px-5 pt-4 pb-3">
      <SectionTitle
        icon="pricing"
        action={
          open !== "new" && (
            <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen("new")}>
              Add price type
            </Button>
          )
        }
      >
        Price types
      </SectionTitle>
      <p className="text-meta text-ink-3">What each price is and where its amount comes from. Which divisions use it is set under Divisions.</p>
      {open === "new" && <NewPriceType onDone={() => setOpen(null)} />}
      <ul className="mt-2 divide-y divide-rule">
        {types.map((t) =>
          open === t.code ? (
            <li key={t.code} className="py-3">
              <EditPriceType type={t} onDone={() => setOpen(null)} />
            </li>
          ) : (
            <li key={t.code} className="flex items-center justify-between gap-3 py-3">
              <span className="min-w-0">
                <span className={`font-semibold ${t.isActive ? "" : "text-ink-3"}`}>{t.name}</span>
                {!t.isActive && <span className="ml-2 text-meta text-ink-3">switched off</span>}
                <span className="block text-meta text-ink-3">{flags(t)}</span>
              </span>
              <Button size="sm" variant="quiet" onClick={() => setOpen(t.code)} aria-label={`Edit ${t.name}`}>
                Edit
              </Button>
            </li>
          ),
        )}
      </ul>
    </Sheet>
  );
}

function EditPriceType({ type, onDone }: { type: PriceType; onDone: () => void }) {
  const [name, setName] = useState(type.name);
  const [notes, setNotes] = useState(type.requiresNotes);
  const [approval, setApproval] = useState(type.needsApproval);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function run(input: Parameters<typeof updatePriceType>[1], done: string) {
    start(async () => {
      const result = await updatePriceType(type.code, input);
      if (!result.ok) return setError(result.error);
      toast.success(done);
      onDone();
    });
  }

  return (
    <form
      noValidate
      className="animate-reshape space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        run({ name: name.trim(), requiresNotes: notes, needsApproval: approval }, `${name.trim()} saved`);
      }}
      onKeyDown={(e) => e.key === "Escape" && !pending && onDone()}
    >
      <Field label="Name" className="max-w-sm">
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus />}
      </Field>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-meta text-ink-2">
        <label className="inline-flex items-center gap-2">
          <input suppressHydrationWarning type="checkbox" checked={notes} onChange={(e) => setNotes(e.target.checked)} className="size-3.5 accent-hema" />
          Quote needs notes
        </label>
        <label className="inline-flex items-center gap-2">
          <input suppressHydrationWarning type="checkbox" checked={approval} onChange={(e) => setApproval(e.target.checked)} className="size-3.5 accent-hema" />
          Finance approves the quote
        </label>
      </div>
      <FormError message={error} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending} disabled={name.trim().length < 2}>
          Save
        </Button>
        <Button size="sm" variant="quiet" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
        <Button
          size="sm"
          className="ml-auto"
          disabled={pending}
          onClick={() => run({ isActive: !type.isActive }, `${type.name} switched ${type.isActive ? "off" : "on"}`)}
        >
          {type.isActive ? "Switch off" : "Switch on"}
        </Button>
      </div>
    </form>
  );
}

function NewPriceType({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [entry, setEntry] = useState<PriceEntry>("list");
  const [notes, setNotes] = useState(false);
  const [approval, setApproval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  return (
    <form
      noValidate
      className="mt-3 animate-reshape space-y-3 rounded-[12px] border border-rule p-4"
      onSubmit={(e) => {
        e.preventDefault();
        start(async () => {
          const result = await addPriceType({ name: name.trim(), entry, requiresNotes: notes, needsApproval: approval });
          if (!result.ok) return setError(result.error);
          toast.success(`${name.trim()} added`, { description: "Turn it on for divisions under Divisions." });
          onDone();
        });
      }}
      onKeyDown={(e) => e.key === "Escape" && !pending && onDone()}
    >
      <Field label="Name" className="max-w-sm">
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Senior Citizen Price" maxLength={80} autoFocus />}
      </Field>
      <Choice
        legend="Its amount comes from"
        name="new-entry"
        value={entry}
        options={[
          { value: "list", label: "The price list" },
          { value: "entered", label: "Typed on each quote" },
        ]}
        onChange={setEntry}
      />
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-meta text-ink-2">
        <label className="inline-flex items-center gap-2">
          <input suppressHydrationWarning type="checkbox" checked={notes} onChange={(e) => setNotes(e.target.checked)} className="size-3.5 accent-hema" />
          Quote needs notes
        </label>
        <label className="inline-flex items-center gap-2">
          <input suppressHydrationWarning type="checkbox" checked={approval} onChange={(e) => setApproval(e.target.checked)} className="size-3.5 accent-hema" />
          Finance approves the quote
        </label>
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending} disabled={name.trim().length < 2}>
          Add price type
        </Button>
        <Button size="sm" variant="quiet" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// --- guarantee letter issuers ---------------------------------------------------------------

function Issuers({ issuers }: { issuers: Issuer[] }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Sheet className="max-w-2xl px-5 pt-4 pb-3">
      <SectionTitle
        icon="letters"
        action={
          open !== "new" && (
            <Button size="sm" variant="quiet" icon={<Plus className="size-4" aria-hidden />} onClick={() => setOpen("new")}>
              Add issuer
            </Button>
          )
        }
      >
        Guarantee letter issuers
      </SectionTitle>
      <p className="text-meta text-ink-3">
        Who can pay a quote with a guarantee letter. The rep attaches the letter and types its number, date and amount.
      </p>
      {open === "new" && <IssuerForm onDone={() => setOpen(null)} />}
      <ul className="mt-2 divide-y divide-rule">
        {issuers.map((i) =>
          open === i.code ? (
            <li key={i.code} className="py-3">
              <IssuerForm issuer={i} onDone={() => setOpen(null)} />
            </li>
          ) : (
            <li key={i.code} className="flex items-center justify-between gap-3 py-3">
              <span className={`font-semibold ${i.isActive ? "" : "text-ink-3"}`}>
                {i.name}
                {!i.isActive && <span className="ml-2 text-meta font-normal">switched off</span>}
              </span>
              <Button size="sm" variant="quiet" onClick={() => setOpen(i.code)} aria-label={`Edit ${i.name}`}>
                Edit
              </Button>
            </li>
          ),
        )}
      </ul>
    </Sheet>
  );
}

/** Adding a new issuer, or (given one) renaming and switching it off. */
function IssuerForm({ issuer, onDone }: { issuer?: Issuer; onDone: () => void }) {
  const [name, setName] = useState(issuer?.name ?? "");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function run(work: Promise<{ ok: true } | { ok: false; error: string }>, done: string) {
    start(async () => {
      const result = await work;
      if (!result.ok) return setError(result.error);
      toast.success(done);
      onDone();
    });
  }

  return (
    <form
      noValidate
      className={`animate-reshape space-y-3 ${issuer ? "" : "mt-3 rounded-[12px] border border-rule p-4"}`}
      onSubmit={(e) => {
        e.preventDefault();
        const trimmed = name.trim();
        run(issuer ? updateIssuer(issuer.code, { name: trimmed }) : addIssuer(trimmed), issuer ? `${trimmed} saved` : `${trimmed} added`);
      }}
      onKeyDown={(e) => e.key === "Escape" && !pending && onDone()}
    >
      <Field label="Name" className="max-w-sm">
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Malasakit Center" maxLength={80} autoFocus />}
      </Field>
      <FormError message={error} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" variant="primary" loading={pending} disabled={name.trim().length < 2}>
          {issuer ? "Save" : "Add issuer"}
        </Button>
        <Button size="sm" variant="quiet" onClick={onDone} disabled={pending}>
          Cancel
        </Button>
        {issuer && (
          <Button
            size="sm"
            className="ml-auto"
            disabled={pending}
            onClick={() => run(updateIssuer(issuer.code, { isActive: !issuer.isActive }), `${issuer.name} switched ${issuer.isActive ? "off" : "on"}`)}
          >
            {issuer.isActive ? "Switch off" : "Switch on"}
          </Button>
        )}
      </div>
    </form>
  );
}
