"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { createCompany, updateCompany, type CompanyInput } from "../../actions/crm";
import type { Assignable, CompanyDetail, CompanyStatus } from "@/src/platform/lib/types";
import { OwnerField } from "./owner-field";
import { STATUSES } from "./words";

const TEXT = ["name", "industry", "website", "email", "phone", "address", "city", "country", "notes"] as const;
type Text = (typeof TEXT)[number];

/** Adding a company, or changing one. */
export function CompanyForm({ people, company }: { people: Assignable[]; company?: CompanyDetail }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [values, setValues] = useState<Record<Text, string>>(() =>
    Object.fromEntries(TEXT.map((k) => [k, (company?.[k] as string | null) ?? ""])) as Record<Text, string>,
  );
  const [status, setStatus] = useState<CompanyStatus>(company?.status ?? "prospect");
  const [ownerId, setOwnerId] = useState(company?.owner.id ?? people.find((p) => p.isMe)?.id ?? people[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });

  function submit() {
    const input: CompanyInput = {
      ...(Object.fromEntries(TEXT.map((k) => [k, values[k].trim() || null])) as Record<Text, string | null>),
      name: values.name.trim(),
      status,
      ownerId: ownerId || null,
    };
    start(async () => {
      let result;
      if (company) {
        const change: Partial<CompanyInput> = {};
        for (const k of TEXT) if ((input[k] ?? null) !== (company[k] ?? null)) (change as Record<string, unknown>)[k] = input[k];
        if (status !== company.status) change.status = status;
        if (ownerId !== company.owner.id) change.ownerId = ownerId;
        if (Object.keys(change).length === 0) {
          router.push(`/companies/${company.id}`);
          return;
        }
        result = await updateCompany(company.id, change);
      } else {
        result = await createCompany(input);
      }
      if (result.ok) {
        toast.success(company ? "Changes saved" : "Company added", { description: result.data.name });
        router.push(`/companies/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-7"
    >
      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">The company</legend>
        <Field label="Name" error={fields.name} className="sm:col-span-2">
          {(p) => <Input {...p} value={values.name} onChange={set("name")} autoFocus={!company} required />}
        </Field>
        <div className="sm:col-span-2">
          <Choice<CompanyStatus> name="status" legend="Status" value={status} onChange={setStatus} options={STATUSES} />
        </div>
        <Field label="Industry" optional error={fields.industry}>
          {(p) => <Input {...p} value={values.industry} onChange={set("industry")} placeholder="Hospital, retail pharmacy…" />}
        </Field>
        <Field label="Website" optional error={fields.website}>
          {(p) => <Input {...p} value={values.website} onChange={set("website")} inputMode="url" placeholder="example.com" />}
        </Field>
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">How to reach them</legend>
        <Field label="Email" optional error={fields.email}>
          {(p) => <Input {...p} type="email" inputMode="email" value={values.email} onChange={set("email")} />}
        </Field>
        <Field label="Phone" optional error={fields.phone}>
          {(p) => <Input {...p} type="tel" value={values.phone} onChange={set("phone")} />}
        </Field>
        <Field label="Address" optional error={fields.address} className="sm:col-span-2">
          {(p) => <Input {...p} value={values.address} onChange={set("address")} />}
        </Field>
        <Field label="City" optional error={fields.city}>
          {(p) => <Input {...p} value={values.city} onChange={set("city")} />}
        </Field>
        <Field label="Country" optional error={fields.country}>
          {(p) => <Input {...p} value={values.country} onChange={set("country")} />}
        </Field>
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">Who looks after it</legend>
        <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} />
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
          {(p) => <Textarea {...p} rows={3} value={values.notes} onChange={set("notes")} />}
        </Field>
      </fieldset>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {company ? "Save changes" : "Add company"}
        </Button>
        <LinkButton href={company ? `/companies/${company.id}` : "/companies"} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
