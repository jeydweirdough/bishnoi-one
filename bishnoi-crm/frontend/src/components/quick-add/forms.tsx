"use client";

import { useMemo, useState, useTransition, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input } from "@/src/platform/ui/field";
import { makeFormat } from "@/src/platform/lib/format";
import type { CustomEntity, Org } from "@/src/platform/lib/types";
import { saveCustomerType, createTeam } from "../../actions/admin";
import { saveIssuer, saveProduct } from "../../actions/catalogue";
import { quickCustomer } from "../../actions/crm";
import { addChoice } from "../../actions/settings";

// The small forms a "+ Add" opens (components/quick-add/quick-add.tsx): the
// least that makes the thing usable in the form behind, which picks it once
// it's made. The rest can be filled in later, where that thing lives.

type Failed = { error: string; fields?: Record<string, string> };

function useSave() {
  const [pending, start] = useTransition();
  const [failed, setFailed] = useState<Failed | null>(null);
  const run = (work: () => Promise<Failed | void>) =>
    start(async () => {
      const outcome = await work();
      setFailed(outcome ?? null);
    });
  return { pending, failed, run };
}

function Shell({ onSubmit, pending, failed, saveLabel, cancel, children }: { onSubmit: () => void; pending: boolean; failed: Failed | null; saveLabel: string; cancel?: () => void; children: React.ReactNode }) {
  return (
    <form
      noValidate
      className="space-y-4"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        e.stopPropagation();
        onSubmit();
      }}
    >
      {children}
      <FormError message={failed && !Object.keys(failed.fields ?? {}).length ? failed.error : null} />
      <div className="dialog-actions">
        {cancel && (
          <Button type="button" onClick={cancel} disabled={pending}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" loading={pending}>
          {saveLabel}
        </Button>
      </div>
    </form>
  );
}

/** A choice on a pick-list (Settings → Forms), added from the form it's missing from. */
export function AddChoice({ entity, fieldKey, fieldLabel, onAdded, done }: { entity: CustomEntity; fieldKey: string; fieldLabel: string; onAdded: (option: string) => void; done: () => void }) {
  const [label, setLabel] = useState("");
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and pick it"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const r = await addChoice(entity, fieldKey, label.trim());
          if (!r.ok) return { error: r.error, fields: r.fields };
          onAdded(r.data.option);
          toast.success(`Added to ${fieldLabel}`, { description: r.data.option });
          done();
        })
      }
    >
      <Field label={`New choice for ${fieldLabel}`} hint="Everyone sees it on this list from now on." error={failed?.fields?.label}>
        {(p) => <Input {...p} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={80} autoFocus />}
      </Field>
    </Shell>
  );
}

/** A customer type (Settings → Customer types). */
export function AddCustomerType({ onAdded, done }: { onAdded: (code: string) => void; done: () => void }) {
  const [name, setName] = useState("");
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and pick it"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const r = await saveCustomerType(null, { name: name.trim() });
          if (!r.ok) return { error: r.error, fields: r.fields };
          const made = r.data.find((t) => t.name.toLowerCase() === name.trim().toLowerCase());
          if (made) onAdded(made.code);
          toast.success("Customer type added", { description: name.trim() });
          done();
        })
      }
    >
      <Field label="Name" hint="Its colour and order can be set later, in Settings → Customer types." error={failed?.fields?.name}>
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={60} autoFocus placeholder="e.g. Distributor" />}
      </Field>
    </Shell>
  );
}

/** A customer, by name: the rest can be filled in on their page. */
export function AddCustomer({ onAdded, done, initialName = "" }: { onAdded: (customer: { id: string; name: string }) => void; done: () => void; initialName?: string }) {
  const [name, setName] = useState(initialName);
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and pick them"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const r = await quickCustomer(name.trim());
          if (!r.ok) return { error: r.error, fields: r.fields };
          onAdded(r.data);
          toast.success("Customer added", { description: `${r.data.name}. Their details can be filled in on their page.` });
          done();
        })
      }
    >
      <Field label="Customer's name" hint="Just the name for now: their details can follow on their page." error={failed?.fields?.name}>
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={160} autoFocus />}
      </Field>
    </Shell>
  );
}

/** A team (People and access → Teams). */
export function AddTeam({ onAdded, done }: { onAdded: (team: { id: string; name: string }) => void; done: () => void }) {
  const [name, setName] = useState("");
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and pick it"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const r = await createTeam({ name: name.trim(), description: null, headquarters: [] });
          if (!r.ok) return { error: r.error, fields: r.fields };
          onAdded({ id: r.data.id, name: r.data.name });
          toast.success("Team added", { description: r.data.name });
          done();
        })
      }
    >
      <Field label="Team's name" hint="Its headquarters can be added later, in People and access → Teams." error={failed?.fields?.name}>
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={80} autoFocus />}
      </Field>
    </Shell>
  );
}

/** Who pays with a guarantee letter (Settings → Pricing): PCSO, DSWD... */
export function AddIssuer({ onAdded, done }: { onAdded: (code: string) => void; done: () => void }) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [touched, setTouched] = useState(false);
  // A code from the name's initials until it's typed over: "Philippine Charity Sweepstakes Office" -> "PCSO".
  const guess = name
    .split(/\s+/)
    .filter((w) => /^[A-Za-z]/.test(w) && !/^(of|the|and|for)$/i.test(w))
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 12);
  const shown = touched ? code : guess;
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and pick it"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const r = await saveIssuer(null, { code: shown.trim(), name: name.trim() });
          if (!r.ok) return { error: r.error, fields: r.fields };
          onAdded(shown.trim());
          toast.success("Issuer added", { description: name.trim() });
          done();
        })
      }
    >
      <Field label="Who issues the letters" error={failed?.fields?.name}>
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoFocus placeholder="e.g. Philippine Charity Sweepstakes Office" />}
      </Field>
      <Field label="Short code" hint="Letters and numbers, as it's shown on quotes." error={failed?.fields?.code}>
        {(p) => (
          <Input
            {...p}
            value={shown}
            onChange={(e) => {
              setTouched(true);
              setCode(e.target.value.toUpperCase());
            }}
            maxLength={40}
          />
        )}
      </Field>
    </Shell>
  );
}

/** A product with its price for the quote's price type, so it can go on the line straight away. */
export function AddProduct({
  org,
  priceType,
  onAdded,
  done,
}: {
  org: Org;
  priceType: { code: string; name: string } | null;
  onAdded: (id: string) => void;
  done: () => void;
}) {
  const fmt = useMemo(() => makeFormat(org), [org]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("");
  const [price, setPrice] = useState("");
  const { pending, failed, run } = useSave();
  return (
    <Shell
      cancel={done}
      saveLabel="Add and put it on the quote"
      pending={pending}
      failed={failed}
      onSubmit={() =>
        run(async () => {
          const cents = priceType ? fmt.toCentavos(price) : null;
          if (priceType && !cents) return { error: "Enter its price.", fields: { price: `Enter its ${priceType.name.toLowerCase()}.` } };
          const r = await saveProduct(null, {
            code: code.trim().toUpperCase(),
            name: name.trim(),
            genericName: null,
            strength: null,
            form: null,
            unit: unit.trim(),
            isActive: true,
            prices: priceType && cents ? { [priceType.code]: cents } : {},
          });
          if (!r.ok) return { error: r.error, fields: r.fields };
          onAdded(r.data.id);
          toast.success("Product added", { description: `${r.data.name}. Its other prices can be set in Products.` });
          done();
        })
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Code" error={failed?.fields?.code}>
          {(p) => <Input {...p} value={code} onChange={(e) => setCode(e.target.value)} maxLength={40} autoFocus placeholder="e.g. AMX-500" />}
        </Field>
        <Field label="Sold by" hint="e.g. box of 100" error={failed?.fields?.unit}>
          {(p) => <Input {...p} value={unit} onChange={(e) => setUnit(e.target.value)} maxLength={40} />}
        </Field>
      </div>
      <Field label="Name" error={failed?.fields?.name}>
        {(p) => <Input {...p} value={name} onChange={(e) => setName(e.target.value)} maxLength={160} />}
      </Field>
      {priceType && (
        <Field label={priceType.name} hint="Its other prices can be set later, in Products." error={failed?.fields?.price ?? failed?.fields?.prices}>
          {(p) => <Input {...p} inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" />}
        </Field>
      )}
    </Shell>
  );
}
