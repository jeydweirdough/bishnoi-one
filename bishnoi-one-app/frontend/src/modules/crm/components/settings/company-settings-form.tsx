"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAnticipation } from "@/src/platform/lib/anticipation";
import { toast } from "sonner";
import { Button } from "@/src/platform/ui/button";
import { Field, FormError, FormGrid, Input, Select, Textarea } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import type { CompanySettings } from "@/src/platform/lib/types";
import { saveCompanySettings } from "@/src/modules/crm/actions/settings";
import { LOCALES } from "@/src/platform/lib/locales";
import { LinkButton } from "@/src/platform/ui/ant-button";


const ZONES = ["Asia/Manila", "Asia/Singapore", "Asia/Hong_Kong", "Asia/Jakarta", "Asia/Bangkok", "Asia/Tokyo", "Australia/Sydney", "Europe/London", "America/New_York", "UTC"];

/** The company as every screen shows it, and how quotes are numbered and worded. */
export function CompanySettingsForm({ initial }: { initial: CompanySettings }) {
  const router = useRouter();
  const [v, setV] = useState({
    orgName: initial.orgName,
    currency: initial.currency,
    locale: initial.locale,
    timezone: initial.timezone,
    quotePrefix: initial.quotePrefix,
    quoteValidDays: String(initial.quoteValidDays),
    quoteTerms: initial.quoteTerms ?? "",
    companyAddress: initial.companyAddress ?? "",
    companyTin: initial.companyTin ?? "",
    companyContact: initial.companyContact ?? "",
  });
  const {
    pending,
    shakeClass,
    anticipateClass,
    execute,
    triggerShake,
    error,
    fieldErrors: fields,
    setFieldErrors: setFields,
  } = useAnticipation<typeof v>();
  // Connected to Bishnoi One: the company's name, currency, format, time zone and letterhead are the Admin
  // Console's Company profile (2026-10-31); only the quote settings are this page's.
  const onPlatform = initial.onPlatform === true;
  const set = (k: keyof typeof v) => (e: { target: { value: string } }) => setV({ ...v, [k]: e.target.value });
  const example = `${v.quotePrefix || "Q"}-${new Date().getFullYear()}${String(new Date().getMonth() + 1).padStart(2, "0")}-0001`;

  function save() {
    const days = Number(v.quoteValidDays);
    if (!Number.isInteger(days) || days < 1) {
      setFields({ quoteValidDays: "A whole number of days, 1 or more." });
      triggerShake();
      toast.error("A whole number of days, 1 or more.");
      return;
    }
    execute({
      anticipate: () => ({ ...v }),
      rollback: (prev) => setV(prev),
      request: () =>
        saveCompanySettings(
          onPlatform
            ? { quotePrefix: v.quotePrefix.trim().toUpperCase(), quoteValidDays: days, quoteTerms: v.quoteTerms.trim() || null }
            : {
          orgName: v.orgName.trim(),
          currency: v.currency,
          locale: v.locale,
          timezone: v.timezone.trim(),
          quotePrefix: v.quotePrefix.trim().toUpperCase(),
          quoteValidDays: days,
          quoteTerms: v.quoteTerms.trim() || null,
          companyAddress: v.companyAddress.trim() || null,
          companyTin: v.companyTin.trim() || null,
          companyContact: v.companyContact.trim() || null,
              },
        ),
      successMessage: () => ({
        title: "Settings saved",
        description: "Every screen uses them from now on.",
      }),
      onSuccess: () => {
        router.refresh();
      },
    });
  }

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
      className={`grid gap-5 rounded-xl transition-all duration-300 lg:grid-cols-2 lg:items-start ${shakeClass} ${anticipateClass}`}
    >
      {onPlatform ? (
        <Sheet className="px-5 pt-4 pb-5">
          <SectionTitle icon="company">Business details</SectionTitle>
          <p className="mt-2 text-sm text-ink-2">
            {initial.orgName} · {initial.currency} · {initial.timezone.replace("_", " ")}
          </p>
          <p className="mt-1 text-meta text-ink-3">
            The name, currency, number format, time zone, address, TIN and phone are set on the Company profile, for every app and every printed document.
          </p>
          <LinkButton href="/platform/company" className="mt-3">
            Open Company profile
          </LinkButton>
        </Sheet>
      ) : (
      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="company">Business details</SectionTitle>
        <FormGrid className="mt-3">
          <Field label="Name" size="md" error={fields.orgName} hint="Shown on screens and quotes.">
            {(p) => <Input {...p} value={v.orgName} onChange={set("orgName")} />}
          </Field>
          <Field label="Currency" size="sm" error={fields.currency} hint="Every amount is shown in it.">
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
          <Field label="Number and date format" size="lg" error={fields.locale}>
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
          <Field label="Timezone" size="md" error={fields.timezone} hint="What counts as today: due dates, overdue tasks, promos starting.">
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
        </FormGrid>
      </Sheet>
      )}

      <Sheet className="px-5 pt-4 pb-5">
        <SectionTitle icon="quotes">Quotes</SectionTitle>
        <FormGrid className="mt-3">
          <Field label="Number starts with" size="md" error={fields.quotePrefix} hint={`Next ones look like ${example}. Quotes already made keep theirs.`}>
            {(p) => <Input {...p} value={v.quotePrefix} onChange={set("quotePrefix")} maxLength={10} className="uppercase" />}
          </Field>
          <Field label="Good for (days)" size="md" error={fields.quoteValidDays} hint="Each quote shows the day it runs out.">
            {(p) => <Input {...p} inputMode="numeric" value={v.quoteValidDays} onChange={set("quoteValidDays")} />}
          </Field>
          <Field label="Terms" optional error={fields.quoteTerms} size="full" hint="Printed on every new quote: payment, delivery, what the price includes.">
            {(p) => <Textarea {...p} rows={5} value={v.quoteTerms} onChange={set("quoteTerms")} maxLength={5000} />}
          </Field>
          {!onPlatform && (
          <>
          <Field label="Business address" optional error={fields.companyAddress} size="full" hint="On the letterhead of a printed quotation.">
            {(p) => <Textarea {...p} rows={2} value={v.companyAddress} onChange={set("companyAddress")} maxLength={300} />}
          </Field>
          <Field label="TIN" size="sm" optional error={fields.companyTin}>
            {(p) => <Input {...p} value={v.companyTin} onChange={set("companyTin")} maxLength={40} placeholder="000-000-000-000" />}
          </Field>
          <Field label="Phone or email" size="lg" optional error={fields.companyContact}>
            {(p) => <Input {...p} value={v.companyContact} onChange={set("companyContact")} maxLength={200} />}
          </Field>
          </>
          )}
        </FormGrid>
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
