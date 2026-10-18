"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button, LinkButton } from "@/src/platform/ui/button";
import { Field, FormError, Input, Textarea } from "@/src/platform/ui/field";
import { Subheading } from "@/src/platform/ui/sheet";
import { addCompany, updateCompany, type CompanyPatch } from "../../actions/organizations";
import type { Company, Options } from "../../lib/types";

// The address other applications know a company by, made from its name the
// way the API makes it (app/routers/companies.py as_slug).
const asSlug = (name: string) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/g, "");

const TEXT = ["name", "slug", "currency", "timezone", "contactEmail", "notes"] as const;
type Text = (typeof TEXT)[number];

/** Adding a company (with its applications and, optionally, who runs it), or changing its particulars. */
export function CompanyForm({ company, applications }: { company?: Company; applications: Options["applications"] }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [values, setValues] = useState<Record<Text, string>>({
    name: company?.name ?? "",
    slug: company?.slug ?? "",
    currency: company?.currency ?? "PHP",
    timezone: company?.timezone ?? "Asia/Manila",
    contactEmail: company?.contactEmail ?? "",
    notes: company?.notes ?? "",
  });
  const [apps, setApps] = useState<string[]>([]);
  const [admin, setAdmin] = useState({ name: "", email: "" });
  const [error, setError] = useState<string | null>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const set = (k: Text) => (e: { target: { value: string } }) => setValues({ ...values, [k]: e.target.value });
  const slug = asSlug(values.name);

  function submit() {
    start(async () => {
      const clean = (v: string) => v.trim() || null;
      if (company) {
        const change: CompanyPatch = {};
        const next = {
          name: values.name.trim(),
          slug: values.slug.trim(),
          currency: values.currency.trim().toUpperCase(),
          timezone: values.timezone.trim(),
          contactEmail: clean(values.contactEmail),
          notes: clean(values.notes),
        };
        for (const k of TEXT) if ((next[k] ?? null) !== (company[k] ?? null)) (change as Record<string, unknown>)[k] = next[k];
        if (Object.keys(change).length === 0) {
          router.push(`/companies/${company.id}`);
          return;
        }
        const result = await updateCompany(company.id, change);
        if (result.ok) {
          toast.success("Changes saved", { description: next.name });
          router.push(`/companies/${company.id}`);
          return;
        }
        setError(result.error);
        setFields(result.fields ?? {});
        return;
      }
      const result = await addCompany({
        name: values.name.trim(),
        currency: values.currency.trim().toUpperCase(),
        timezone: values.timezone.trim(),
        contactEmail: clean(values.contactEmail),
        notes: clean(values.notes),
        applicationIds: apps,
        adminName: clean(admin.name),
        adminEmail: clean(admin.email),
      });
      if (result.ok) {
        toast.success("Company added", { description: result.data.name });
        router.push(`/companies/${result.data.id}`);
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
      <div className="grid gap-5 sm:grid-cols-2">
        <Field
          label="Name"
          error={fields.name}
          hint={!company && (slug ? <>Company code: <b className="font-semibold text-ink-2">{slug}</b>.</> : "The company code is generated from the name.")}
          className="sm:col-span-2"
        >
          {(p) => <Input {...p} value={values.name} onChange={set("name")} autoFocus={!company} required />}
        </Field>
        {company && (
          <Field
            label="Company code"
            error={fields.slug}
            hint="Other applications identify the company by this code. Change it only after informing them."
            className="sm:col-span-2"
          >
            {(p) => <Input {...p} value={values.slug} onChange={set("slug")} autoCapitalize="none" spellCheck={false} />}
          </Field>
        )}
        <Field label="Currency" error={fields.currency} hint="Three-letter code, e.g. PHP.">
          {(p) => <Input {...p} value={values.currency} onChange={set("currency")} maxLength={3} autoCapitalize="characters" />}
        </Field>
        <Field label="Time zone" error={fields.timezone} hint="E.g. Asia/Manila.">
          {(p) => <Input {...p} value={values.timezone} onChange={set("timezone")} spellCheck={false} />}
        </Field>
        <Field label="Contact email" optional error={fields.contactEmail} className="sm:col-span-2">
          {(p) => <Input {...p} type="email" inputMode="email" value={values.contactEmail} onChange={set("contactEmail")} />}
        </Field>
        <Field label="Notes" optional error={fields.notes} className="sm:col-span-2">
          {(p) => <Textarea {...p} rows={3} value={values.notes} onChange={set("notes")} />}
        </Field>
      </div>

      {!company && (
        <>
          <fieldset className="space-y-2">
            <legend className="mb-1">
              <Subheading>Assigned applications</Subheading>
            </legend>
            <p className="text-meta text-ink-3">Users can only be given access to these. This can be changed later.</p>
            {applications.length === 0 ? (
              <p className="text-meta text-ink-3">No applications are registered yet.</p>
            ) : (
              <div className="flex flex-wrap gap-x-5 gap-y-2">
                {applications.map((a) => (
                  <label key={a.id} className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink">
                    <input
                      type="checkbox"
                      className="size-4 accent-hema"
                      checked={apps.includes(a.id)}
                      onChange={(e) => setApps(e.target.checked ? [...apps, a.id] : apps.filter((id) => id !== a.id))}
                    />
                    {a.name}
                  </label>
                ))}
              </div>
            )}
            {fields.applicationIds && <p className="text-meta text-danger">{fields.applicationIds}</p>}
          </fieldset>

          <fieldset className="space-y-3">
            <legend className="mb-1">
              <Subheading>Company admin</Subheading>
            </legend>
            <p className="text-meta text-ink-3">Optional. Added as the first company admin. Enter both, or leave both blank.</p>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Admin name" optional error={fields.adminName}>
                {(p) => <Input {...p} value={admin.name} onChange={(e) => setAdmin({ ...admin, name: e.target.value })} />}
              </Field>
              <Field label="Admin email" optional error={fields.adminEmail}>
                {(p) => <Input {...p} type="email" inputMode="email" value={admin.email} onChange={(e) => setAdmin({ ...admin, email: e.target.value })} />}
              </Field>
            </div>
          </fieldset>
        </>
      )}

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
