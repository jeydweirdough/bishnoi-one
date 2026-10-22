import Link from "next/link";
import { Suspense, type ReactNode } from "react";
import { Figure } from "@/src/platform/ui/figure";
import { Amount } from "@/src/platform/ui/amount";
import { SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import type { Org } from "@/src/platform/lib/types";
import { CashBalances } from "./cash";
import type { Section, WaitingPrices } from "./types";

type Fmt = ReturnType<typeof makeFormat>;

// The dashboard's sections (src/screens/finance-home.tsx shows the ones the API
// sends). Money on the cards is short (₱1.25M) with the whole amount on hover,
// as every Bishnoi One overview does (ui/amount.tsx).

/** An amount on a card, under what it counts. */
function Money({ fmt, centavos, label, href, note }: { fmt: Fmt; centavos: number; label: string; href?: string; note?: string }) {
  const amount = <span className="block text-figure text-ink"><Amount text={fmt.peso(centavos)} /></span>;
  return (
    <div className="min-w-0 px-5 py-4">
      {href ? <Link href={href} className="block hover:[&>span:first-child]:text-hema">{amount}</Link> : amount}
      <span className="mt-0.5 block text-meta text-ink-3">{label}</span>
      {note && <span className="block text-meta text-ink-3">{note}</span>}
    </div>
  );
}

/** Said under any figure that counts only what was done in the Hub (decided 2026-10-22). */
const HUB_ONLY =
  "Only invoices issued in the Hub. 2MG's official invoices are still printed from Oojeema, so this stays low until the Hub issues them.";

function Grid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 divide-x divide-rule sm:grid-cols-3">{children}</div>;
}

/** The CRM's prices and quotes waiting for Finance: asked on their own, so the page doesn't wait (kept a minute by the API). */
async function PricesWaiting() {
  const w = await load<WaitingPrices>("/finance/dashboard/waiting-prices");
  if (!w.available) {
    return (
      <div className="min-w-0 px-5 py-4">
        <span className="block text-figure text-ink-3">—</span>
        <span className="mt-0.5 block text-meta text-ink-3">Prices to approve: {w.message}</span>
      </div>
    );
  }
  return <Figure label="Prices and quotes to approve" value={w.prices + w.quotes} href="/prices" flag />;
}

function Asking() {
  return (
    <div className="min-w-0 px-5 py-4">
      <span className="block text-figure text-ink-3">…</span>
      <span className="mt-0.5 block text-meta text-ink-3">Asking the CRM for prices to approve</span>
    </div>
  );
}

function Waiting({ s }: { s: Extract<Section, { key: "waiting" }> }) {
  return (
    <Sheet>
      <div className="px-5 pt-4">
        <SectionTitle icon="approvals">Waiting for you</SectionTitle>
      </div>
      <Grid>
        {s.canRelease && <Figure label="Cash advances to release" value={s.toRelease} href="/funds" flag />}
        {s.canApprovePrices && (
          <Suspense fallback={<Asking />}>
            <PricesWaiting />
          </Suspense>
        )}
        {s.canReview && <Figure label="Liquidations to review" value={s.toReview} href="/funds/review" flag />}
        {s.canSettle && <Figure label="Refunds and reimbursements to settle" value={s.toSettle} href="/funds/settlement" flag />}
        <Figure label="Overdue liquidations" value={s.overdueLiquidations} href="/funds/outstanding" flag />
      </Grid>
    </Sheet>
  );
}

function Receivables({ s, fmt }: { s: Extract<Section, { key: "receivables" }>; fmt: Fmt }) {
  return (
    <Sheet>
      <div className="px-5 pt-4">
        <SectionTitle icon="money">Receivables</SectionTitle>
      </div>
      <Grid>
        <Money fmt={fmt} centavos={s.totalCentavos} label={`Owed by ${s.customers} ${s.customers === 1 ? "customer" : "customers"}`} href="/invoices/receivables" />
        {s.buckets
          .filter((b) => b.key !== "current" && b.amountCentavos > 0)
          .map((b) => (
            <Money key={b.key} fmt={fmt} centavos={b.amountCentavos} label={b.label} href="/invoices/receivables" />
          ))}
      </Grid>
      {s.mostOverdue.length > 0 && (
        <div className="border-t border-rule px-5 py-3 text-sm">
          <p className="mb-1 text-meta font-semibold text-ink-2">Most overdue</p>
          <ul className="space-y-1">
            {s.mostOverdue.map((c) => (
              <li key={c.name} className="flex items-baseline justify-between gap-4">
                <span className="min-w-0 truncate">{c.name}</span>
                <span className="shrink-0 tabular-nums text-ink-2">
                  {c.oldestDaysLate} {c.oldestDaysLate === 1 ? "day" : "days"} late · {fmt.peso(c.owedCentavos)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="border-t border-rule px-5 py-2 text-meta text-ink-3">{HUB_ONLY}</p>
    </Sheet>
  );
}

function Sales({ s, fmt }: { s: Extract<Section, { key: "sales" }>; fmt: Fmt }) {
  const n = (k: number) => `${k} ${k === 1 ? "invoice" : "invoices"}`;
  return (
    <Sheet>
      <div className="px-5 pt-4">
        <SectionTitle icon="trend">Sales invoiced in the Hub</SectionTitle>
      </div>
      <Grid>
        <Money fmt={fmt} centavos={s.month.totalCentavos} label="This month" note={n(s.month.count)} href="/invoices" />
        <Money fmt={fmt} centavos={s.year.totalCentavos} label="This year" note={n(s.year.count)} href="/invoices" />
      </Grid>
      <p className="border-t border-rule px-5 py-2 text-meta text-ink-3">{HUB_ONLY}</p>
    </Sheet>
  );
}

function Spending({ s, fmt }: { s: Extract<Section, { key: "spending" }>; fmt: Fmt }) {
  return (
    <Sheet className="px-5 py-4">
      <SectionTitle icon="divisions">Marketing spending by team</SectionTitle>
      {s.teams.length === 0 ? (
        <p className="text-sm text-ink-2">No reviewed marketing spending this year yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-meta text-ink-3">
              <th className="py-1 font-medium">Team</th>
              <th className="py-1 text-right font-medium">This month</th>
              <th className="py-1 text-right font-medium">This year</th>
            </tr>
          </thead>
          <tbody>
            {s.teams.map((t) => (
              <tr key={t.team} className="border-t border-rule">
                <td className="py-1.5">{t.team}</td>
                <td className="py-1.5 text-right tabular-nums">{fmt.peso(t.monthCentavos)}</td>
                <td className="py-1.5 text-right tabular-nums">{fmt.peso(t.yearCentavos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-3 text-meta text-ink-3">
        Accepted receipts in categories the company covers, from reviewed liquidations. Sales per division aren&apos;t in the Hub yet (orders are in Odoo), so they can&apos;t be set beside these.
      </p>
    </Sheet>
  );
}

function Journal({ s, fmt }: { s: Extract<Section, { key: "journal" }>; fmt: Fmt }) {
  return (
    <Sheet className="px-5 py-4">
      <SectionTitle icon="history">Journal</SectionTitle>
      <p className={`mb-2 text-sm ${s.balanced ? "text-ink-2" : "text-danger"}`}>
        {s.balanced ? "The books balance." : "Debits and credits don't match. Check the trial balance."} {s.thisMonth} {s.thisMonth === 1 ? "entry" : "entries"} this month.
      </p>
      {s.latest.length === 0 ? (
        <p className="text-sm text-ink-2">No journal entries yet.</p>
      ) : (
        <ul className="divide-y divide-rule text-sm">
          {s.latest.map((e) => (
            <li key={e.id} className="flex items-baseline justify-between gap-4 py-1.5">
              <span className="min-w-0">
                <span className="font-medium">{e.number}</span> · {e.memo}
                <span className="block text-meta text-ink-3">
                  {fmt.dateLabel(e.date)} · posted by {e.postedBy}
                  {e.source === "fund" ? " (from a marketing request)" : ""}
                </span>
              </span>
              <span className="shrink-0 tabular-nums">{fmt.peso(e.totalCentavos)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-meta text-ink-3">
        <Link href="/ledger" className="text-hema hover:underline">All journal entries</Link>
      </p>
    </Sheet>
  );
}

/** What isn't set up, in the words the sidebar uses, and where to fix it. */
const NOT_SET_UP: Record<string, { says: (n: number) => string; href: string }> = {
  taxProfile: { says: () => "The company's tax registration isn't complete", href: "/tax" },
  invoiceSeries: { says: () => "There are no invoice numbers left: add the series from the BIR's Authority to Print", href: "/invoices/series" },
  postingAccounts: { says: (n) => `${n} default ${n === 1 ? "account isn't" : "accounts aren't"} set, so some fund steps can't be posted`, href: "/ledger/posting" },
  categoryAccounts: { says: (n) => `${n} expense ${n === 1 ? "category has" : "categories have"} no account`, href: "/ledger/categories" },
};

function Tax({ s, fmt }: { s: Extract<Section, { key: "tax" }>; fmt: Fmt }) {
  const missing = Object.entries(s.notSetUp).filter(([k]) => NOT_SET_UP[k]);
  return (
    <Sheet>
      <div className="px-5 pt-4">
        <SectionTitle icon="particulars">Tax and setup</SectionTitle>
      </div>
      <Grid>
        <Money
          fmt={fmt}
          centavos={s.quarterTaxCentavos}
          label={`Output tax on invoices, ${s.quarter}`}
          note={`${s.quarterInvoices} ${s.quarterInvoices === 1 ? "invoice" : "invoices"} issued in the Hub`}
          href="/invoices"
        />
      </Grid>
      <div className="border-t border-rule px-5 py-3 text-sm">
        {missing.length === 0 ? (
          <p className="text-ink-2">Everything you look after is set up.</p>
        ) : (
          <ul className="space-y-1">
            {missing.map(([k, n]) => (
              <li key={k}>
                <Link href={NOT_SET_UP[k].href} className="text-danger hover:underline">{NOT_SET_UP[k].says(n)}</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="border-t border-rule px-5 py-2 text-meta text-ink-3">{HUB_ONLY}</p>
    </Sheet>
  );
}

/** One section, as the API sent it. */
export function DashboardSection({ section, org }: { section: Section; org: Org }) {
  const fmt = makeFormat(org);
  switch (section.key) {
    case "waiting":
      return <Waiting s={section} />;
    case "receivables":
      return <Receivables s={section} fmt={fmt} />;
    case "sales":
      return <Sales s={section} fmt={fmt} />;
    case "spending":
      return <Spending s={section} fmt={fmt} />;
    case "journal":
      return <Journal s={section} fmt={fmt} />;
    case "tax":
      return <Tax s={section} fmt={fmt} />;
    case "cash":
      return <CashBalances org={org} />;
  }
}
