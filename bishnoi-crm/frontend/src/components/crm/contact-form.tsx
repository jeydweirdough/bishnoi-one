"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createContact, updateContact, type ContactInput } from "../../actions/crm";
import type { Assignable, ContactDetail, Duplicate, FormFieldDef, FormLayout, Ref } from "@/src/platform/lib/types";
import { LayoutForm, extraChanges, toDraft, type ExtraDraft } from "../extra/extra-fields";
import { Duplicates } from "./duplicates";
import { OwnerField } from "./owner-field";
import { useCan } from "../quick-add/can";
import { AddCustomer } from "../quick-add/forms";
import { QuickAdd } from "../quick-add/quick-add";

const TEXT = ["firstName", "lastName", "jobTitle", "email", "phone", "mobile", "notes"] as const;
type Text = (typeof TEXT)[number];

/** Adding a contact, or changing one. `companyId` puts a new contact straight into a company. */
export function ContactForm({
  people,
  companies,
  contact,
  companyId,
  layout,
}: {
  people: Assignable[];
  companies: Ref[];
  /** The form as an admin laid it out (Settings → Forms). */
  layout: FormLayout;
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
  const [duplicates, setDuplicates] = useState<Duplicate[]>([]);
  const [dupMessage, setDupMessage] = useState("");
  const allFields = layout.sections.flatMap((s) => s.fields);
  const [extra, setExtra] = useState<ExtraDraft>(() => toDraft(allFields, contact?.extra));
  // What isn't on the form (hidden in Settings) isn't sent, so it stays as it was.
  const shown = new Set(allFields.map((f) => f.key));
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  // Their current company stays offered even if it's no longer on the list.
  const can = useCan();
  // Customers made here (+ New customer) are on the list before the page reloads it.
  const [made, setMade] = useState<Ref[]>([]);
  const known = [...made.filter((m) => !companies.some((c) => c.id === m.id)), ...companies];
  const options = contact?.company && !known.some((c) => c.id === contact.company!.id) ? [contact.company, ...known] : known;

  function submit(allowDuplicate = false) {
    const input: ContactInput = {
      ...(Object.fromEntries(TEXT.filter((k) => shown.has(k)).map((k) => [k, values[k].trim() || null])) as Record<Text, string | null>),
      firstName: values.firstName.trim(),
      companyId: company || null,
      ownerId: ownerId || null,
      extra: extraChanges(allFields, extra),
    };
    start(async () => {
      let result;
      if (contact) {
        const change: Partial<ContactInput> = {};
        for (const k of TEXT) if (shown.has(k) && (input[k] ?? null) !== (contact[k] ?? null)) (change as Record<string, unknown>)[k] = input[k];
        if ((company || null) !== (contact.company?.id ?? null)) change.companyId = company || null;
        if (ownerId !== contact.owner.id) change.ownerId = ownerId;
        const extraChange = extraChanges(allFields, extra, contact.extra);
        if (extraChange) change.extra = extraChange;
        if (Object.keys(change).length === 0) {
          router.push(`/contacts/${contact.id}`);
          return;
        }
        result = await updateContact(contact.id, change);
      } else {
        result = await createContact({ ...input, allowDuplicate });
      }
      if (result.ok) {
        toast.success(contact ? "Changes saved" : "Customer added", { description: result.data.name });
        router.push(`/contacts/${result.data.id}`);
        router.refresh();
        return;
      }
      // "Looks like one already here" is a question, not an error: it gets its own panel.
      const found = result.duplicates ?? [];
      setDuplicates(found);
      setDupMessage(found.length ? result.error : "");
      setError(found.length ? null : result.error);
      setFields(result.fields ?? {});
    });
  }

  /** A built-in field, drawn with the label and hints the admin gave it. */
  function standard(f: FormFieldDef) {
    if (f.key === "ownerId") return people.length > 1 ? <OwnerField people={people} value={ownerId} onChange={setOwnerId} error={fields.ownerId} label={f.label} /> : null;
    if (f.key === "companyId") {
      return (
        <div>
        <Field label={f.label} optional={!f.required} error={fields.companyId} hint={f.helpText ?? undefined}>
          {(p) => (
            <Select {...p} value={company} onChange={(e) => setCompany(e.target.value)}>
              <option value="">No customer</option>
              {options.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {can("customers.create") && (
          <QuickAdd label="New customer" title="New customer">
            {(done) => <AddCustomer onAdded={(c) => (setMade([c, ...made]), setCompany(c.id))} done={done} />}
          </QuickAdd>
        )}
        </div>
      );
    }
    if (!(TEXT as readonly string[]).includes(f.key)) return null;
    const k = f.key as Text;
    return (
      <Field label={f.label} optional={!f.required} error={fields[k]} hint={f.helpText ?? undefined}>
        {(p) =>
          k === "notes" ? (
            <Textarea {...p} rows={3} value={values.notes} onChange={set("notes")} placeholder={f.placeholder ?? undefined} />
          ) : (
            <Input
              {...p}
              type={f.type === "email" ? "email" : f.type === "phone" ? "tel" : "text"}
              inputMode={f.type === "email" ? "email" : undefined}
              value={values[k]}
              onChange={set(k)}
              placeholder={f.placeholder ?? undefined}
              autoFocus={k === "firstName" && !contact}
              required={f.required}
            />
          )
        }
      </Field>
    );
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
      <LayoutForm layout={layout} standard={standard} draft={extra} onChange={setExtra} errors={fields} />

      <FormError message={error} />
      {duplicates.length > 0 && (
        <Duplicates message={dupMessage} found={duplicates} base="/contacts" pending={pending} onAddAnyway={() => submit(true)} />
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {contact ? "Save changes" : "Add customer"}
        </Button>
        <LinkButton href={cancel} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
