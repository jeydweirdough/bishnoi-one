"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createCustomer, updateCustomer, type CustomerInput } from "../actions/customers";
import { CUSTOMER_STATUSES, pickable } from "@/src/platform/lib/labels";
import type { Customer, CustomerStatus, Duplicate, ListItem, OrgTeam } from "@/src/platform/lib/types";

/** A team a customer can go in, and the division it belongs to. A team code is
 *  only unique inside its division, so both travel together. */
export type PickableTeam = OrgTeam & { division: string; divisionName: string };

type Props = {
  teams: PickableTeam[]; // teams this person may put a customer in
  kinds: ListItem[]; // the company's own kinds of customer, in its own order
  customer?: Customer; // editing when present
};

const TEXT_FIELDS = ["name", "specialty", "phone", "email", "address", "city", "notes"] as const;

export function CustomerForm({ teams, kinds, customer }: Props) {
  const router = useRouter();
  const form = useRef<HTMLFormElement>(null);
  const [pending, start] = useTransition();
  // A customer belongs to one division's team. When there is only one division
  // to choose from, it is filled in and never shown: nothing to decide.
  const divisions = [...new Map(teams.map((t) => [t.division, t.divisionName])).entries()].map(([code, name]) => ({ code, name }));
  const [division, setDivision] = useState(customer?.division ?? teams[0]?.division ?? "");
  const [team, setTeam] = useState(customer?.team ?? teams[0]?.code ?? "");
  const [headquarters, setHeadquarters] = useState(customer?.headquarters ?? "");
  const [kind, setKind] = useState(customer?.kind ?? kinds[0]?.code ?? "");
  const [status, setStatus] = useState<CustomerStatus>(customer?.status ?? "lead");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [duplicates, setDuplicates] = useState<Duplicate[]>([]);

  // A customer whose kind has since been switched off keeps it here, so saving
  // the phone number doesn't quietly turn it into something else.
  const choices = pickable(kinds, customer?.kind);
  // A customer never moves between divisions: its quotes, prices and retention
  // window all belong to the one it is in. So editing offers only its own.
  const canChooseDivision = !customer && divisions.length > 1;
  const inDivision = teams.filter((t) => t.division === division);
  const current = inDivision.find((t) => t.code === team);
  const hqs = current?.headquarters.filter((h) => h.isActive || h.code === customer?.headquarters) ?? [];
  const moving = customer && team !== customer.team;
  const cancelHref = customer ? `/customers/${customer.id}` : "/customers";

  function submit(allowDuplicate = false) {
    const data = new FormData(form.current!);
    const input: CustomerInput = { team, headquarters: headquarters || null, kind, status };
    // Only on create: the API refuses to move a customer between divisions.
    if (!customer) input.division = division;
    for (const name of TEXT_FIELDS) input[name] = String(data.get(name) ?? "").trim() || null;

    start(async () => {
      const result = customer
        ? await updateCustomer(customer.id, { ...input, rev: customer.rev })
        : await createCustomer({ ...input, allowDuplicate });
      if (result.ok) {
        toast.success(customer ? "Changes saved" : "Customer added", { description: String(input.name) });
        router.push(`/customers/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
      setDuplicates(result.duplicates ?? []);
    });
  }

  return (
    <form
      ref={form}
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-7"
    >
      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">Where it belongs</legend>
        {canChooseDivision && (
          <Field label="Division" error={fields.division}>
            {(p) => (
              <Select
                {...p}
                value={division}
                onChange={(e) => {
                  const next = e.target.value;
                  setDivision(next);
                  // Its teams are different ones, so the choice below restarts.
                  setTeam(teams.find((t) => t.division === next)?.code ?? "");
                  setHeadquarters("");
                }}
              >
                {divisions.map((d) => (
                  <option key={d.code} value={d.code}>
                    {d.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        {inDivision.length === 1 ? (
          <div>
            <p className="mb-1 text-meta font-medium text-ink-2">Team</p>
            <p className="flex h-9 items-center border-b border-rule text-sm">{inDivision[0].name}</p>
            <p className="mt-1 text-meta text-ink-3">The only team you can {customer ? "move it to" : "add customers to"}.</p>
          </div>
        ) : (
          <Field label="Team" error={fields.team}>
            {(p) => (
              <Select
                {...p}
                value={team}
                onChange={(e) => {
                  setTeam(e.target.value);
                  setHeadquarters("");
                }}
              >
                {inDivision.map((t) => (
                  <option key={t.code} value={t.code}>
                    {t.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        )}
        <Field label="Headquarters" optional error={fields.headquarters} hint={hqs.length === 0 ? "This team has no headquarters." : undefined}>
          {(p) => (
            <Select {...p} value={headquarters} onChange={(e) => setHeadquarters(e.target.value)} disabled={hqs.length === 0}>
              <option value="">None</option>
              {hqs.map((h) => (
                <option key={h.code} value={h.code}>
                  {h.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {moving && (
          <p className="animate-reshape rounded-lg bg-hema-tint px-3 py-2 text-meta text-ink-2 sm:col-span-2">
            Moving this customer to <strong>{current?.name}</strong> moves its calls, visits and follow-ups too. People who only
            work in {customer.teamName} won&apos;t see it anymore.
          </p>
        )}
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">Who</legend>
        <Field label="Name" error={fields.name} className="sm:col-span-2" hint="Write it the way it should read in the list, title and all.">
          {(p) => <Input {...p} name="name" defaultValue={customer?.name} required maxLength={120} autoComplete="off" />}
        </Field>
        <div className="sm:col-span-2">
          <Choice
            legend="Type"
            name="kind"
            value={kind}
            onChange={setKind}
            options={choices.map((k) => ({ value: k.code, label: k.name }))}
          />
        </div>
        <Field label="Specialty" optional error={fields.specialty} hint="The field they work in, if it helps tell them apart.">
          {(p) => <Input {...p} name="specialty" defaultValue={customer?.specialty ?? ""} maxLength={80} placeholder="e.g. Pediatrics" />}
        </Field>
        <div className="sm:col-span-2">
          <Choice
            legend="Status"
            name="status"
            value={status}
            onChange={setStatus}
            options={Object.entries(CUSTOMER_STATUSES).map(([value, label]) => ({ value: value as CustomerStatus, label }))}
          />
        </div>
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">How to reach them</legend>
        <Field label="Phone" optional error={fields.phone}>
          {(p) => <Input {...p} name="phone" type="tel" inputMode="tel" defaultValue={customer?.phone ?? ""} placeholder="0917 123 4567" />}
        </Field>
        <Field label="Email" optional error={fields.email}>
          {(p) => <Input {...p} name="email" type="email" inputMode="email" defaultValue={customer?.email ?? ""} />}
        </Field>
        <Field label="Address" optional error={fields.address}>
          {(p) => <Input {...p} name="address" defaultValue={customer?.address ?? ""} maxLength={240} />}
        </Field>
        <Field label="City" optional error={fields.city}>
          {(p) => <Input {...p} name="city" defaultValue={customer?.city ?? ""} maxLength={80} />}
        </Field>
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
          {(p) => <Textarea {...p} name="notes" defaultValue={customer?.notes ?? ""} maxLength={2000} rows={3} />}
        </Field>
      </fieldset>

      {duplicates.length > 0 ? (
        <div role="alert" className="animate-reshape rounded-lg border border-rule-strong px-4 py-3">
          <p className="font-semibold">{error}</p>
          <p className="mt-0.5 text-meta text-ink-2">Check these first. Two records for one customer splits their history.</p>
          <ul className="mt-2 space-y-1 text-sm">
            {duplicates.map((d) => (
              <li key={d.id}>
                <Link href={`/customers/${d.id}`} className="font-medium text-ink hover:underline" target="_blank">
                  {d.name}
                </Link>
                <span className="text-ink-3"> · {[d.teamName, d.phone].filter(Boolean).join(" · ")}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => submit(true)} loading={pending}>
              It&apos;s a different customer, add anyway
            </Button>
          </div>
        </div>
      ) : (
        <FormError message={error} />
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-rule pt-5">
        <Button type="submit" variant="primary" loading={pending && duplicates.length === 0}>
          {customer ? "Save changes" : "Add customer"}
        </Button>
        <LinkButton href={cancelHref} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
