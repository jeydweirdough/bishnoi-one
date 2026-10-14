"use client";

import { Pencil, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { percent, percentText, toBasisPoints } from "@/src/platform/lib/format";
import type { PriceEntry, PriceRule, SalesRules } from "@/src/platform/lib/types";
import { saveIssuer, savePriceType, saveSalesSettings } from "../../actions/catalogue";

type PriceType = SalesRules["priceTypes"][number];

const describe = (t: PriceType) =>
  [
    t.entry === "list" ? "From the price list" : "Typed on the quote",
    t.rule === "with_rx" ? "only with a prescription" : null,
    t.requiresNotes ? "needs notes" : null,
    t.needsApproval ? "needs approval" : null,
  ]
    .filter(Boolean)
    .join(" · ");

/** The rules quotes are priced by: price types, who may pay with a guarantee letter, and when a discount needs approval. */
export function RulesEditor({ rules }: { rules: SalesRules }) {
  const mayEdit = rules.can.edit;
  const [editing, setEditing] = useState<PriceType | "new" | null>(null);
  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
      <Sheet className="px-5 pt-4 pb-4">
        <SectionTitle
          icon="pricing"
          action={
            mayEdit &&
            !editing && (
              <Button size="sm" variant="quiet" icon={<Plus className="size-3.5" aria-hidden />} onClick={() => setEditing("new")}>
                Add
              </Button>
            )
          }
        >
          Price types
        </SectionTitle>
        <p className="text-meta text-ink-3">The prices a quote can be made at. A team may narrow these for its own quotes on its Prices page.</p>
        {editing && <PriceTypeForm key={editing === "new" ? "new" : editing.code} kind={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
        <ul className="mt-3 divide-y divide-rule border-t border-rule">
          {rules.priceTypes.map((t) => (
            <li key={t.code} className={`flex items-start justify-between gap-3 py-2.5 ${t.isActive ? "" : "text-ink-3"}`}>
              <div className="min-w-0">
                <p className="font-medium">
                  {t.name} <span className="text-meta text-ink-3">{t.code}</span>
                  {!t.isActive && <span className="ml-2 rounded-md bg-bench px-2 py-0.5 text-meta">Off</span>}
                </p>
                <p className="text-meta text-ink-3">{describe(t)}</p>
              </div>
              {mayEdit && (
                <Button size="sm" variant="quiet" icon={<Pencil className="size-3.5" aria-hidden />} onClick={() => setEditing(t)} aria-label={`Change ${t.name}`}>
                  Change
                </Button>
              )}
            </li>
          ))}
        </ul>
      </Sheet>

      <div className="space-y-5">
        <SettingsForm rules={rules} />
        <Issuers rules={rules} />
      </div>
    </div>
  );
}

function PriceTypeForm({ kind, onDone }: { kind: PriceType | null; onDone: () => void }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [code, setCode] = useState(kind?.code ?? "");
  const [name, setName] = useState(kind?.name ?? "");
  const [entry, setEntry] = useState<PriceEntry>(kind?.entry ?? "list");
  const [rule, setRule] = useState<PriceRule>(kind?.rule ?? "always");
  const [requiresNotes, setNotes] = useState(kind?.requiresNotes ?? false);
  const [needsApproval, setApproval] = useState(kind?.needsApproval ?? false);
  const [isActive, setActive] = useState(kind?.isActive ?? true);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function submit() {
    start(async () => {
      const input = { name: name.trim(), entry, rule, requiresNotes, needsApproval, isActive, ...(kind ? {} : { code: code.trim() }) };
      const result = await savePriceType(kind?.code ?? null, input);
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      toast.success(kind ? "Price type saved" : "Price type added", { description: input.name });
      onDone();
      router.refresh();
    });
  }

  const box = (label: string, value: boolean, set: (v: boolean) => void) => (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={value} onChange={(e) => set(e.target.checked)} className="size-4 accent-hema" />
      {label}
    </label>
  );

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="mt-3 space-y-4 rounded-xl bg-bench px-4 py-4"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {!kind && (
          <Field label="Code" error={fields.code} hint="Short and unique, e.g. PATIENT">
            {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} autoFocus />}
          </Field>
        )}
        <Field label="Name" error={fields.name}>
          {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} autoFocus={!!kind} />}
        </Field>
        <Field label="The price comes from" error={fields.entry}>
          {(p) => (
            <Select {...p} value={entry} onChange={(e) => setEntry(e.target.value as PriceEntry)}>
              <option value="list">The price list</option>
              <option value="entered">The rep, typed on the quote</option>
            </Select>
          )}
        </Field>
        <Field label="Offered" error={fields.rule}>
          {(p) => (
            <Select {...p} value={rule} onChange={(e) => setRule(e.target.value as PriceRule)}>
              <option value="always">On every quote</option>
              <option value="with_rx">Only with a prescription</option>
            </Select>
          )}
        </Field>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {box("Needs notes", requiresNotes, setNotes)}
        {box("Needs approval", needsApproval, setApproval)}
        {box("Switched on", isActive, setActive)}
      </div>
      <FormError message={error} />
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={pending}>
          {kind ? "Save" : "Add price type"}
        </Button>
        <Button variant="quiet" size="sm" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function SettingsForm({ rules }: { rules: SalesRules }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const s = rules.settings;
  const [limit, setLimit] = useState(percentText(s.discountApprovalBp));
  const [letters, setLetters] = useState(s.allowsGuaranteeLetters);
  const [atRisk, setAtRisk] = useState(String(s.atRiskDays));
  const [lost, setLost] = useState(String(s.lostDays));
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const bp = toBasisPoints(limit);
    if (bp === null) return setFields({ discountApprovalBp: "A percent like 10." });
    start(async () => {
      const result = await saveSalesSettings({ discountApprovalBp: bp, allowsGuaranteeLetters: letters, atRiskDays: Number(atRisk), lostDays: Number(lost) });
      if (!result.ok) {
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success("Rules saved");
      router.refresh();
    });
  }

  if (!rules.can.edit) {
    return (
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="approvals">Approvals</SectionTitle>
        <p className="mt-2 text-sm text-ink-2">
          Extra discounts over {percent(s.discountApprovalBp)} need approval. Guarantee letters are {s.allowsGuaranteeLetters ? "accepted" : "not accepted"}.
        </p>
      </Sheet>
    );
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="approvals">Approvals and retention</SectionTitle>
      <form
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="mt-3 space-y-4"
      >
        <Field label="Extra discount that needs approval, above (%)" error={fields.discountApprovalBp}>
          {(p) => <Input {...p} inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} />}
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={letters} onChange={(e) => setLetters(e.target.checked)} className="size-4 accent-hema" />
          Accept guarantee letters (DSWD, PCSO…) as payment
        </label>
        <div className="grid grid-cols-2 gap-4">
          <Field label="At risk after (days)" error={fields.atRiskDays}>
            {(p) => <Input {...p} inputMode="numeric" value={atRisk} onChange={(e) => setAtRisk(e.target.value)} />}
          </Field>
          <Field label="Lost after (days)" error={fields.lostDays}>
            {(p) => <Input {...p} inputMode="numeric" value={lost} onChange={(e) => setLost(e.target.value)} />}
          </Field>
        </div>
        <p className="text-meta text-ink-3">A customer with no quote in that long is at risk, then lost.</p>
        <FormError message={error} />
        <Button type="submit" variant="primary" size="sm" loading={pending}>
          Save rules
        </Button>
      </form>
    </Sheet>
  );
}

function Issuers({ rules }: { rules: SalesRules }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [fields, setFields] = useState<Record<string, string>>({});

  function run(work: () => ReturnType<typeof saveIssuer>, done: string) {
    start(async () => {
      const result = await work();
      if (!result.ok) {
        setFields(result.fields ?? {});
        toast.error(result.error);
        return;
      }
      setFields({});
      setCode("");
      setName("");
      toast.success(done);
      router.refresh();
    });
  }

  return (
    <Sheet className="px-5 pt-4 pb-5">
      <SectionTitle icon="letters">Guarantee letter issuers</SectionTitle>
      <p className="text-meta text-ink-3">Who may pay for a quote with a guarantee letter.</p>
      <ul className="mt-2 divide-y divide-rule border-y border-rule">
        {rules.issuers.map((i) => (
          <li key={i.code} className="flex items-center justify-between gap-3 py-2">
            <span className={i.isActive ? "" : "text-ink-3"}>
              {i.name} <span className="text-meta text-ink-3">{i.code}</span>
            </span>
            {rules.can.edit && (
              <Button size="sm" variant="quiet" disabled={pending} onClick={() => run(() => saveIssuer(i.code, { isActive: !i.isActive }), i.isActive ? `${i.name} switched off` : `${i.name} switched on`)}>
                {i.isActive ? "Switch off" : "Switch on"}
              </Button>
            )}
          </li>
        ))}
      </ul>
      {rules.can.edit && (
        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            run(() => saveIssuer(null, { code: code.trim(), name: name.trim() }), "Issuer added");
          }}
          className="mt-3 grid grid-cols-[6rem_minmax(0,1fr)_auto] items-end gap-2"
        >
          <Field label="Code" error={fields.code}>
            {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} />}
          </Field>
          <Field label="Name" error={fields.name}>
            {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} />}
          </Field>
          <Button type="submit" size="sm" loading={pending} className="mb-0.5">
            Add
          </Button>
        </form>
      )}
    </Sheet>
  );
}
