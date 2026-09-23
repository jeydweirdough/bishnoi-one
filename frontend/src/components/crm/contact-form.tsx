"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createContact, updateContact, type ContactInput } from "../../actions/crm";
import type { Assignable, ContactDetail, Ref } from "@/src/platform/lib/types";
import { OwnerField } from "./owner-field";

const TEXT = ["firstName", "lastName", "jobTitle", "email", "phone", "mobile", "notes"] as const;
type Text = (typeof TEXT)[number];

/** Adding a contact, or changing one. `companyId` puts a new contact straight into a company. */
export function ContactForm({
  people,
  companies,
  contact,
  companyId,
}: {
  people: Assignable[];
  companies: Ref[];
  contact?: ContactDetail;
  companyId?: string;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [values, setValues] = useState<Record<Text, string>>(() =>
    Object.fromEntries(TEXT.map((k) => [k, (contact?.[k] as string | null) ?? ""])) as Record<Text, string>,
  );
  const [company, setCompany] = useState(contact?.company?.id ?? companyId ?? "");
  const [ownerId, setOwnerId] = useState(contact?.owner.id ?? people.find((p) => p.isMe)?.id ?? people[0]?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  // Their current company stays offered even if it's no longer on the list.
  const options = contact?.company && !companies.some((c) => c.id === contact.company!.id) ? [contact.company, ...companies] : companies;

  function submit() {
    const input: ContactInput = {
      ...(Object.fromEntries(TEXT.map((k) => [k, values[k].trim() || null])) as Record<Text, string | null>),
      firstName: values.firstName.trim(),
      companyId: company || null,
      ownerId: ownerId || null,
    };
    start(async () => {
      let result;
      if (contact) {
        const change: Partial<ContactInput> = {};
        for (const k of TEXT) if ((input[k] ?? null) !== (contact[k] ?? null)) (change as Record<string, unknown>)[k] = input[k];
        if ((company || null) !== (contact.company?.id ?? null)) change.companyId = company || null;
        if (ownerId !== contact.owner.id) change.ownerId = ownerId;
        if (Object.keys(change).length === 0) {
          router.push(`/contacts/${contact.id}`);
          return;
        }
        result = await updateContact(contact.id, change);
      } else {
        result = await createContact(input);
      }
      if (result.ok) {
        toast.success(contact ? "Changes saved" : "Contact added", { description: result.data.name });
        router.push(`/contacts/${result.data.id}`);
        router.refresh();
        return;
      }
      setError(result.error);
      setFields(result.fields ?? {});
    });
  }

  const cancel = contact ? `/contacts/${contact.id}` : companyId ? `/companies/${companyId}` : "/contacts";

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
        <legend className="mb-3 text-sm font-semibold text-ink">The person</legend>
        <Field label="First name" error={fields.firstName}>
          {(p) => <Input {...p} value={values.firstName} onChange={set("firstName")} autoFocus={!contact} required />}
        </Field>
        <Field label="Last name" optional error={fields.lastName}>
          {(p) => <Input {...p} value={values.lastName} onChange={set("lastName")} />}
        </Field>
        <Field label="Company" optional error={fields.companyId}>
          {(p) => (
            <Select {...p} value={company} onChange={(e) => setCompany(e.target.value)}>
              <option value="">No company</option>
              {options.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="Job title" optional error={fields.jobTitle}>
          {(p) => <Input {...p} value={values.jobTitle} onChange={set("jobTitle")} />}
        </Field>
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-3">
        <legend className="mb-3 text-sm font-semibold text-ink">How to reach them</legend>
        <Field label="Email" optional error={fields.email}>
          {(p) => <Input {...p} type="email" inputMode="email" value={values.email} onChange={set("email")} />}
        </Field>
        <Field label="Phone" optional error={fields.phone}>
          {(p) => <Input {...p} type="tel" value={values.phone} onChange={set("phone")} />}
        </Field>
        <Field label="Mobile" optional error={fields.mobile}>
          {(p) => <Input {...p} type="tel" value={values.mobile} onChange={set("mobile")} />}
        </Field>
      </fieldset>

      <fieldset className="grid gap-5 sm:grid-cols-2">
        <legend className="mb-3 text-sm font-semibold text-ink">Who looks after them</legend>
        <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} />
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
          {(p) => <Textarea {...p} rows={3} value={values.notes} onChange={set("notes")} />}
        </Field>
      </fieldset>

      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {contact ? "Save changes" : "Add contact"}
        </Button>
        <LinkButton href={cancel} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
