"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, Input, Select, Textarea } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import type { CompanySettings } from "@/src/platform/lib/types";
import { saveCompanySettings } from "../../actions/settings";

const LOCALES = [
  { value: "en-PH", label: "English (Philippines)" },
  { value: "en-US", label: "English (United States)" },
  { value: "en-GB", label: "English (United Kingdom)" },
  { value: "en-SG", label: "English (Singapore)" },
  { value: "en-AU", label: "English (Australia)" },
];

const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Jakarta", "Asia/Bangkok", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "America/New_York", "UTC"];

/** The company as every screen shows it, and how quotes are numbered and worded. */
export function CompanySettingsForm({ initial }: { initial: CompanySettings }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [v, setV] = useState({
    orgName: initial.orgName,
    currency: initial.currency,
    locale: initial.locale,
    timezone: initial.timezone,
    quotePrefix: initial.quotePrefix,
    quoteValidDays: String(initial.quoteValidDays),
    quoteTerms: initial.quoteTerms ?? "",
  });
  const [fields, setFields] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const example = `${v.quotePrefix || "Q"}-${new Date().getFullYear()}${String(new Date().getMonth() + 1).padStart(2, "0")}-0001`;

  function save() {
    const days = Number(v.quoteValidDays);
    if (!Number.isInteger(days) || days < 1) return setFields({ quoteValidDays: "A whole number of days, 1 or more." });
    start(async () => {
      const r = await saveCompanySettings({
        orgName: v.orgName.trim(),
        currency: v.currency,
        locale: v.locale,
        timezone: v.timezone.trim(),
        quotePrefix: v.quotePrefix.trim().toUpperCase(),
        quoteValidDays: days,
        quoteTerms: v.quoteTerms.trim() || null,
      });
      if (!r.ok) {
        setError(r.fields ? null : r.error);
        setFields(r.fields ?? {});
        return;
      }
      setError(null);
      setFields({});
      toast.success("Settings saved", { description: "Every screen uses them from now on." });
      router.refresh();
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className="grid gap-5 lg:grid-cols-2 lg:items-start"
    >
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="company">Your business</SectionTitle>
        <div className="mt-3 grid gap-5 sm:grid-cols-2">
          <Field label="Name" error={fields.orgName} className="sm:col-span-2" hint="Shown on screens and quotes.">
            {(p) => <Input {...p} value={v.orgName} onChange={set("orgName")} />}
          </Field>
          <Field label="Currency" error={fields.currency} hint="Every amount is shown in it.">
            {(p) => (
              <Select {...p} value={v.currency} onChange={set("currency")}>
                {[...new Set([v.currency, ...initial.currencies])].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Number and date format" error={fields.locale}>
            {(p) => (
              <Select {...p} value={v.locale} onChange={set("locale")}>
                {[...LOCALES, ...(LOCALES.some((l) => l.value === v.locale) ? [] : [{ value: v.locale, label: v.locale }])].map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Timezone" error={fields.timezone} className="sm:col-span-2" hint="What counts as today: due dates, overdue tasks, promos starting.">
            {(p) => (
              <>
                <Input {...p} value={v.timezone} onChange={set("timezone")} list="zones" />
                <datalist id="zones">
                  {ZONES.map((z) => (
                    <option key={z} value={z} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
        </div>
      </Sheet>

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="quotes">Quotes</SectionTitle>
        <div className="mt-3 grid gap-5 sm:grid-cols-2">
          <Field label="Number starts with" error={fields.quotePrefix} hint={`Next ones look like ${example}. Quotes already made keep theirs.`}>
            {(p) => <Input {...p} value={v.quotePrefix} onChange={set("quotePrefix")} maxLength={10} className="uppercase" />}
          </Field>
          <Field label="Good for (days)" error={fields.quoteValidDays} hint="Each quote shows the day it runs out.">
            {(p) => <Input {...p} inputMode="numeric" value={v.quoteValidDays} onChange={set("quoteValidDays")} />}
          </Field>
          <Field label="Terms" optional error={fields.quoteTerms} className="sm:col-span-2" hint="Printed on every new quote: payment, delivery, what the price includes.">
            {(p) => <Textarea {...p} rows={5} value={v.quoteTerms} onChange={set("quoteTerms")} maxLength={5000} />}
          </Field>
        </div>
      </Sheet>

      <div className="lg:col-span-2">
        <FormError message={error} />
        <Button type="submit" variant="primary" loading={pending} className="mt-2">
          Save settings
        </Button>
      </div>
    </form>
  );
}
