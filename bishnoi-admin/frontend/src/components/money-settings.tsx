"use client";

import { useId, useState, useTransition } from "react";
import { toast } from "sonner";
import { Field, FormError, Input, Select } from "@/src/platform/ui/field";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { saveCompany, type CompanyInput } from "../actions/admin";
import { makeFormat, type Format } from "@/src/platform/lib/format";
import type { Company } from "@/src/platform/lib/types";
import { SaveBar } from "@/src/platform/ui/pick-list";

// Settings → Money & formats. Every screen reads its money, its dates and its
// times from this one record, so the change is shown as it will read before it
// is saved: a company moving to London sees London's clock here first.

type Draft = { currency: string; minorUnits: string; locale: string; timezone: string };

/** The amount the preview is written from. Whole minor units, like everything else. */
const SAMPLE = 123456;

const DECIMALS = [
  { value: "0", label: "None — like a yen" },
  { value: "1", label: "One" },
  { value: "2", label: "Two — like a peso, a dollar or a pound" },
  { value: "3", label: "Three — like a dinar" },
  { value: "4", label: "Four" },
];

function toDraft(c: Company): Draft {
  return { currency: c.currency, minorUnits: String(c.minorUnits ?? 2), locale: c.locale, timezone: c.timezone };
}

// Intl is the only thing that knows which of these are real, and it says so by
// refusing them. Asking it quietly here means the screen can name the mistake
// beside the field instead of the person finding out when they save.
function knownLocale(locale: string): boolean {
  try {
    return Intl.getCanonicalLocales(locale).length > 0;
  } catch {
    return false;
  }
}

function knownZone(zone: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: zone });
    return true;
  } catch {
    return false;
  }
}

export function MoneySettings({ data, now }: { data: Company; now: string }) {
  const currencies = useId();
  const [draft, setDraft] = useState<Draft>(() => toDraft(data));
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, start] = useTransition();

  const saved = toDraft(data);
  const changed = (Object.keys(saved) as (keyof Draft)[]).filter((k) => draft[k].trim() !== saved[k]);
  const change = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch });

  function save() {
    const found: Record<string, string> = {};
    if (!/^[A-Za-z]{3}$/.test(draft.currency.trim())) found.currency = "Use a three-letter code, like PHP or USD.";
    if (!knownLocale(draft.locale.trim())) found.locale = "That isn't a language and country. Use one like en-PH or en-GB.";
    if (!knownZone(draft.timezone.trim())) found.timezone = "That isn't a time zone. Use one like Asia/Manila or Europe/London.";
    setProblems(found);
    if (Object.keys(found).length) return setError("Some fields need a look.");

    // Only what they touched travels: a PATCH that mentions a field sets it.
    const sent = (key: Exclude<keyof Draft, "minorUnits">) => (changed.includes(key) ? draft[key].trim() : undefined);
    const input: CompanyInput = {
      currency: sent("currency"),
      locale: sent("locale"),
      timezone: sent("timezone"),
      minorUnits: changed.includes("minorUnits") ? Number(draft.minorUnits) : undefined,
    };
    start(async () => {
      const result = await saveCompany(input);
      if (!result.ok) {
        setProblems(result.fields ?? {});
        return setError(result.error);
      }
      setError(null);
      toast.success("Money and formats saved", { description: "Every screen reads its money, dates and times from them." });
    });
  }

  // The preview is only drawn from settings Intl will accept; anything else is
  // named on its own field, and the preview holds the last good one.
  const after = makeFormat({
    currency: /^[A-Za-z]{3}$/.test(draft.currency.trim()) ? draft.currency.trim().toUpperCase() : data.currency,
    locale: knownLocale(draft.locale.trim()) ? draft.locale.trim() : data.locale,
    timezone: knownZone(draft.timezone.trim()) ? draft.timezone.trim() : data.timezone,
    minorUnits: Number(draft.minorUnits),
  });

  return (
    <>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,32rem)_minmax(0,22rem)] lg:items-start">
        <Sheet className="min-w-0 px-5 pt-4 pb-5">
          <SectionTitle icon="money">How this company writes things down</SectionTitle>
          <div className="mt-3 space-y-5">
            <Field
              label="Money"
              error={problems.currency}
              hint={`A three-letter code. Bishnoi One draws a symbol for ${data.knownCurrencies.length} of them; any other is written as its code.`}
            >
              {(p) => (
                <>
                  <Input
                    {...p}
                    list={currencies}
                    value={draft.currency}
                    maxLength={3}
                    autoCapitalize="characters"
                    onChange={(e) => change({ currency: e.target.value.toUpperCase().replace(/[^A-Z]/g, "") })}
                    className="max-w-24 uppercase"
                  />
                  <datalist id={currencies}>
                    {data.knownCurrencies.map((code) => (
                      <option key={code} value={code} />
                    ))}
                  </datalist>
                </>
              )}
            </Field>
            <Field
              label="Decimal places"
              error={problems.minorUnits}
              hint="How many decimals this money has — two for a peso, none for a yen. Amounts are kept as whole minor units, so this is what decides where the point goes when one is shown."
            >
              {(p) => (
                <Select {...p} value={draft.minorUnits} onChange={(e) => change({ minorUnits: e.target.value })} className="max-w-xs">
                  {DECIMALS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field
              label="Language and country"
              error={problems.locale}
              hint="Decides the order and the words a date reads in, and how numbers are grouped. Like en-PH, en-GB or ja-JP."
            >
              {(p) => <Input {...p} value={draft.locale} maxLength={16} onChange={(e) => change({ locale: e.target.value })} className="max-w-36" />}
            </Field>
            <Field
              label="Time zone"
              error={problems.timezone}
              hint="Where the working day is. It decides what “today” means, so follow-ups and figures are counted by your own clock. Like Asia/Manila or Europe/London."
            >
              {(p) => <Input {...p} value={draft.timezone} maxLength={64} onChange={(e) => change({ timezone: e.target.value })} className="max-w-56" />}
            </Field>
          </div>
        </Sheet>

        <Preview data={data} after={after} now={now} changed={changed.length > 0} />
      </div>

      {changed.length > 0 && (
        <SaveBar
          what="Unsaved changes to money and formats"
          saving={saving}
          onSave={save}
          onDiscard={() => {
            setDraft(saved);
            setProblems({});
            setError(null);
          }}
          error={<FormError message={error} />}
        />
      )}
    </>
  );
}

/** The same amount, day and instant, written both ways, so a change is read before it is made. */
function Preview({ data, after, now, changed }: { data: Company; after: Format; now: string; changed: boolean }) {
  const before = makeFormat(data);
  const at = new Date(now);
  const rows: [string, string, string][] = [
    ["An amount", before.peso(SAMPLE), after.peso(SAMPLE)],
    ["A date", before.dateLabel(before.todayKey(at)), after.dateLabel(after.todayKey(at))],
    ["A time", before.whenLabel(now, before.todayKey(at)), after.whenLabel(now, after.todayKey(at))],
  ];
  return (
    <Sheet className="px-5 pt-4 pb-5 lg:sticky lg:top-5">
      <SectionTitle icon="particulars">How it will read</SectionTitle>
      <p className="text-meta text-ink-3">{changed ? "As it reads now, and as it will read once saved." : "Nothing changed yet, so both read the same."}</p>
      <table className="mt-3 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-rule text-caps text-ink-3 uppercase">
            <th scope="col" className="w-full py-2 pr-3 font-semibold">
              <span className="sr-only">What</span>
            </th>
            <th scope="col" className="px-3 py-2 font-semibold">Now</th>
            <th scope="col" className="py-2 pl-3 font-semibold">After saving</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {rows.map(([what, was, will]) => (
            <tr key={what}>
              <th scope="row" className="py-2.5 pr-3 text-left font-normal whitespace-nowrap text-ink-3">
                {what}
              </th>
              <td className="px-3 py-2.5 whitespace-nowrap text-ink-3">{was}</td>
              <td className="py-2.5 pl-3 font-semibold whitespace-nowrap text-ink">{will}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-meta text-ink-3">
        Money is kept as whole minor units — {before.count(SAMPLE)} above. The API writes that amount {data.example} in the messages
        it sends.
      </p>
    </Sheet>
  );
}
