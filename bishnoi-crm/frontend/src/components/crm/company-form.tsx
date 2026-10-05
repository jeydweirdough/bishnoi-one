"use client";

import { Select as AntSelect } from "antd";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Choice, Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { createCompany, updateCompany, type CompanyInput } from "../../actions/crm";
import type { Assignable, CompanyDetail, CompanyStatus, CustomerType, Duplicate, FormFieldDef, FormLayout } from "@/src/platform/lib/types";
import { ChoiceSelect, LayoutForm, extraChanges, toDraft, type ExtraDraft } from "../extra/extra-fields";
import { forTeam, layoutForTeam } from "../extra/teams";
import { Duplicates } from "./duplicates";
import { Lookalikes } from "./lookalikes";
import { OwnerField } from "./owner-field";
import { typeOptions } from "./words";
import { useCan } from "../quick-add/can";
import { AddCustomerType } from "../quick-add/forms";
import { QuickAdd } from "../quick-add/quick-add";

const TEXT = ["name", "industry", "leadSource", "website", "email", "phone", "address", "city", "country", "notes"] as const;
type Text = (typeof TEXT)[number];

/** Adding a company, or changing one. The form is laid out as an admin set it (Settings → Forms). */
export function CompanyForm({
  people,
  types,
  layout: everyTeamsLayout,
  company,
  priceGroups = [],
  initialName = "",
  initialTeam,
  initialType,
  missingOnly = false,
  thenQuote = false,
}: {
  people: Assignable[];
  types: CustomerType[];
  layout: FormLayout;
  company?: CompanyDetail;
  /** Settings → Price rules. None: the field isn't shown. */
  priceGroups?: { code: string; name: string; isActive: boolean }[];
  /** A new customer's name, as typed where they weren't found. */
  initialName?: string;
  /** The division (a team) and type picked in the add-customer pop-up. */
  initialTeam?: string;
  initialType?: string;
  /** "Complete profile": only the profile fields still empty. */
  missingOnly?: boolean;
  /** Added from "New quote": open their quote once they're saved. */
  thenQuote?: boolean;
}) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [ownerId, setOwnerId] = useState(
    () =>
      company?.owner.id ??
      // In the division picked: oneself if one is in it, else its first person.
      (initialTeam
        ? (people.find((p) => p.isMe && p.team?.id === initialTeam) ?? people.find((p) => p.team?.id === initialTeam))?.id
        : undefined) ??
      people.find((p) => p.isMe)?.id ??
      people[0]?.id ??
      "",
  );
  // The form is the team's it's assigned to: the Rx team's has its own fields and types.
  const teamOf = (id: string) => people.find((p) => p.id === id)?.team?.id ?? (id === company?.owner.id ? (company?.team?.id ?? null) : null);
  const teamId = teamOf(ownerId);
  const offered = types.filter((t) => forTeam(t, teamId) || t.code === company?.status);
  const [status, setStatus] = useState<CompanyStatus>(
    company?.status ?? (offered.some((t) => t.code === initialType) ? initialType! : undefined) ?? offered.find((t) => t.isActive)?.code ?? "",
  );
  // And the kind of customer: a doctor is profiled, a hospital isn't asked a birthday.
  const ownLayout = layoutForTeam(everyTeamsLayout, teamId, status);
  const empty = (key: string) => {
    const v = company?.extra?.[key];
    return v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0);
  };
  // Kept as it opened, so a field filled in now doesn't jump off the form.
  const [missingKeys] = useState(() => new Set(ownLayout.sections.flatMap((s) => s.fields).filter((f) => !f.standard && empty(f.key)).map((f) => f.key)));
  const layout = missingOnly
    ? { ...ownLayout, sections: ownLayout.sections.map((s) => ({ ...s, fields: s.fields.filter((f) => missingKeys.has(f.key)) })).filter((s) => s.fields.length) }
    : ownLayout;
  const allFields = layout.sections.flatMap((s) => s.fields);
  const [values, setValues] = useState<Record<Text, string>>(() =>
    Object.fromEntries(TEXT.map((k) => [k, (company?.[k] as string | null) ?? (k === "name" ? initialName : "")])) as Record<Text, string>,
  );
  const can = useCan();
  const [priceGroup, setPriceGroup] = useState(company?.priceGroupCode ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [duplicates, setDuplicates] = useState<Duplicate[]>([]);
  const [dupMessage, setDupMessage] = useState("");
  const [extra, setExtra] = useState<ExtraDraft>(() => toDraft(everyTeamsLayout.sections.flatMap((s) => s.fields), company?.extra));

  /** A new person to assign it to: their team's form, and a type their team is offered. */
  function assign(id: string) {
    setOwnerId(id);
    const next = types.filter((t) => t.isActive && forTeam(t, teamOf(id)));
    if (!next.some((t) => t.code === status)) setStatus(next[0]?.code ?? status);
  }
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  // What isn't on the form (hidden in Settings) isn't sent, so it stays as it was.
  const shown = new Set(allFields.map((f) => f.key));

  function submit(allowDuplicate = false) {
    const input: CompanyInput = {
      ...(Object.fromEntries(TEXT.filter((k) => shown.has(k)).map((k) => [k, values[k].trim() || null])) as Record<Text, string | null>),
      name: values.name.trim(),
      status,
      ...(priceGroups.length ? { priceGroupCode: priceGroup || null } : {}),
      ownerId: ownerId || null,
      extra: extraChanges(allFields, extra),
    };
    start(async () => {
      let result;
      if (company) {
        const change: Partial<CompanyInput> = {};
        for (const k of TEXT) if (shown.has(k) && (input[k] ?? null) !== (company[k] ?? null)) (change as Record<string, unknown>)[k] = input[k];
        if (status !== company.status) change.status = status;
        if (priceGroups.length && (priceGroup || null) !== (company.priceGroupCode ?? null)) change.priceGroupCode = priceGroup || null;
        if (ownerId !== company.owner.id) change.ownerId = ownerId;
        const extraChange = extraChanges(allFields, extra, company.extra);
        if (extraChange) change.extra = extraChange;
        if (Object.keys(change).length === 0) {
          router.push(`/companies/${company.id}`);
          return;
        }
        result = await updateCompany(company.id, change);
      } else {
        result = await createCompany({ ...input, allowDuplicate });
      }
      if (result.ok) {
        toast.success(company ? "Changes saved" : "Customer added", { description: thenQuote ? `Now their quote: ${result.data.name}` : result.data.name });
        router.push(thenQuote && !company ? `/companies/${result.data.id}/quotes/new` : `/companies/${result.data.id}`);
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
    const hint = f.helpText ?? undefined;
    const placeholder = f.placeholder ?? undefined;
    switch (f.key) {
      case "status": {
        const options = typeOptions(offered, company?.status);
        return (
          <div>
            {options.length > 5 ? (
              <Field label={f.label} error={fields.status}>
                {(p) => (
                  <AntSelect
                    id={p.id}
                    className="w-full"
                    value={status || undefined}
                    onChange={(v) => setStatus(v)}
                    options={options}
                    showSearch={{ optionFilterProp: "label" }}
                    placeholder="Type to search"
                  />
                )}
              </Field>
            ) : (
              <Choice<CompanyStatus> name="status" legend={f.label} value={status} onChange={setStatus} options={options} />
            )}
            {can("admin.types") && (
              <QuickAdd label="New customer type" title="New customer type">
                {(done) => <AddCustomerType onAdded={setStatus} done={done} />}
              </QuickAdd>
            )}
          </div>
        );
      }
      case "ownerId":
        // Nobody else to assign it to: it's theirs, nothing to ask.
        return people.length > 1 ? <OwnerField people={people} value={ownerId} onChange={assign} error={fields.ownerId} label={f.label} /> : null;
      case "industry":
        return <ChoiceSelect field={f} value={values.industry} onChange={(v) => setValues({ ...values, industry: v })} error={fields.industry} />;
      case "leadSource":
        return <ChoiceSelect field={f} value={values.leadSource} onChange={(v) => setValues({ ...values, leadSource: v })} error={fields.leadSource} />;
      case "notes":
        return (
          <Field label={f.label} optional={!f.required} error={fields.notes} hint={hint}>
            {(p) => <Textarea {...p} rows={3} value={values.notes} onChange={set("notes")} placeholder={placeholder} />}
          </Field>
        );
      default: {
        if (!(TEXT as readonly string[]).includes(f.key)) return null;
        const k = f.key as Text;
        const kind = f.type === "email" ? "email" : f.type === "phone" ? "tel" : "text";
        const input = (
          <Field label={f.label} optional={!f.required} error={fields[k]} hint={hint}>
            {(p) => (
              <Input
                {...p}
                type={kind}
                inputMode={f.type === "email" ? "email" : f.type === "url" ? "url" : undefined}
                value={values[k]}
                onChange={set(k)}
                placeholder={placeholder}
                autoFocus={k === "name" && !company}
                required={f.required}
              />
            )}
          </Field>
        );
        if (k === "name" && !company) {
          return (
            <>
              {input}
              <Lookalikes name={values.name} phone={values.phone} email={values.email} />
            </>
          );
        }
        return input;
      }
    }
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
      <LayoutForm
        layout={layout}
        standard={standard}
        draft={extra}
        onChange={setExtra}
        errors={fields}
        linkNames={Object.fromEntries(Object.entries(company?.links ?? {}).map(([k, l]) => [k, l.name]))}
      />

      {priceGroups.length > 0 && (
        <Field label="Price group" optional error={fields.priceGroupCode} hint="Its group's prices come first on quotes (Settings → Price rules).">
          {(p) => (
            <Select {...p} value={priceGroup} onChange={(e) => setPriceGroup(e.target.value)}>
              <option value="">No group: list prices</option>
              {priceGroups
                .filter((g) => g.isActive || g.code === company?.priceGroupCode)
                .map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.name}
                    {g.isActive ? "" : " (switched off)"}
                  </option>
                ))}
            </Select>
          )}
        </Field>
      )}

      <FormError message={error} />
      {duplicates.length > 0 && (
        <Duplicates message={dupMessage} found={duplicates} base="/companies" pending={pending} onAddAnyway={() => submit(true)} quote={thenQuote} />
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" loading={pending}>
          {company ? "Save changes" : "Add customer"}
        </Button>
        <LinkButton href={company ? `/companies/${company.id}` : thenQuote ? "/quotes" : "/companies"} variant="quiet">
          Cancel
        </LinkButton>
      </div>
    </form>
  );
}
