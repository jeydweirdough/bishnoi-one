import Link from "next/link";
import { Flag } from "@/src/platform/ui/marks";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { OnRecord, RegistrationHistory } from "../tax/on-record";
import { RateChangeForm } from "../tax/rate-change-form";
import { RegistrationForm } from "../tax/registration-form";
import { SaleTryout } from "../tax/sale-tryout";
import type { TaxSetup } from "../tax/types";

export const metadata = { title: "Tax" };

const TABS = { registration: "Registration", rates: "Rates", try: "Tax calculator" } as const;
type Tab = keyof typeof TABS;

const BUCKETS = { taxable: "VATable", zero_rated: "Zero-rated", exempt: "VAT-exempt", non_taxable: "Non-VAT" };

/**
 * Tax: the company's registration, the dated rates, and a place to see what a
 * sale comes to. Finance owns tax for every Bishnoi One app; the CRM and Pharmacy
 * ask it for the same answer (benchmarks/decisions.md, D8).
 */
export default async function TaxPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { tab: raw } = await searchParams;
  const tab = (typeof raw === "string" && raw in TABS ? raw : "registration") as Tab;
  const setup = await load<TaxSetup>("/tax/setup");
  const { profile, pack } = setup;
  const percent = (bp: number) => `${(bp / 100).toLocaleString(me.org.locale, { maximumFractionDigits: 2 })}%`;

  return (
    <>
      <PageHeader title="Tax">
        {pack.name} · {profile.regimeName}. Every quote, sale and invoice in Bishnoi One is taxed by these rules.
        {!profile.complete && (
          <span className="mt-1 block">
            <Flag letter="!">
              {profile.missingSentence || `Fill in the registration: every ${pack.document} needs the registered name, TIN and address.`} {setup.canEdit ? `Fill ${profile.missing?.length === 1 ? "it" : "them"} in under Registration, below.` : "A Finance administrator can fill it in."}
            </Flag>
          </span>
        )}
      </PageHeader>
      <nav aria-label="Tax" className="mb-5 flex flex-wrap gap-x-6 gap-y-1 border-b border-rule">
        {(Object.keys(TABS) as Tab[]).map((t) => (
          <Link
            key={t}
            href={`/tax?tab=${t}`}
            scroll={false}
            aria-current={t === tab ? "page" : undefined}
            className={`-mb-px border-b-2 px-1 pb-2 text-sm ${t === tab ? "border-hema font-semibold text-hema" : "border-transparent text-ink-2 hover:text-ink"}`}
          >
            {TABS[t]}
          </Link>
        ))}
      </nav>

      {tab === "registration" && (
        <div className="space-y-5">
          <OnRecord profile={profile} fmt={fmt} canEdit={setup.canEdit} />
          {/* The form is for changing it; someone who can't sees the summary above instead. */}
          {setup.canEdit && (
            <Sheet className="max-w-[50rem] px-5 py-6 sm:px-8">
              <SectionTitle>Change the registration</SectionTitle>
              <RegistrationForm key={profile.updatedAt ?? "new"} setup={setup} />
            </Sheet>
          )}
          <RegistrationHistory history={setup.history ?? []} fmt={fmt} />
        </div>
      )}

      {tab === "rates" && (
        <div className="space-y-4">
          <p className="max-w-[65ch] text-sm text-ink-2">
            Each rate applies from its first day to its last, so a sale is taxed at the rate of its own day. They come from the {pack.name} pack;
            a change in the law can be entered here ahead of an update.
          </p>
          {pack.codes.map((c) => (
            <Sheet key={c.code} className="px-5 py-4">
              <SectionTitle
                action={<span className="text-sm font-semibold tabular-nums">{c.rated ? (c.rateTodayBp === null ? "No current rate" : `${percent(c.rateTodayBp)} today`) : "No rate"}</span>}
              >
                {c.name}
              </SectionTitle>
              <p className="text-meta text-ink-3">
                {BUCKETS[c.bucket]} · <span className="font-mono">{c.code}</span>
              </p>
              {c.rates.length > 0 && (
                <ul className="mt-3 divide-y divide-rule border-t border-rule text-sm">
                  {c.rates.map((r) => (
                    <li key={r.id} className="grid gap-1 py-2 sm:grid-cols-[6rem_minmax(0,14rem)_minmax(0,1fr)] sm:gap-4">
                      <span className="font-semibold tabular-nums">{percent(r.rateBp)}</span>
                      <span className="text-ink-2 tabular-nums">
                        {fmt.dateLabel(r.validFrom)} – {r.validTo ? fmt.dateLabel(r.validTo) : "now"}
                      </span>
                      <span className="text-meta text-ink-3">
                        {r.basis}
                        {r.source === "admin" ? " · entered here" : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>
          ))}
          {setup.canEdit && <RateChangeForm codes={pack.codes} today={setup.today} />}
        </div>
      )}

      {tab === "try" && (
        <Sheet className="px-5 py-6 sm:px-8">
          <SaleTryout setup={setup} org={me.org} />
        </Sheet>
      )}
    </>
  );
}
