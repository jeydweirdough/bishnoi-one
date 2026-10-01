import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { ChartEditor, JournalForm, PostingEditor, ReverseButton } from "../ledger/forms";
import { TYPE_LABELS, type AccountLedger, type AccountType, type Chart, type Entry, type Posting, type TrialBalance } from "../ledger/types";

// The ledger: the journal, the chart of accounts, each account's ledger, the
// trial balance, and the accounts marketing requests post to. Each a sub-page of
// Ledger in the sidebar.

type Search = Promise<Record<string, string | string[] | undefined>>;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const isDate = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

/** Every entry, newest first, with its lines: manual journals and those the fund steps post. */
export default async function JournalPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const source = one(sp.source);
  const query = new URLSearchParams({ limit: "200" });
  if (source === "manual" || source === "fund" || source === "invoice") query.set("source", source);
  const [entries, chart] = await Promise.all([load<{ items: Entry[] }>(`/finance/ledger/entries?${query}`), load<Chart>("/finance/ledger/accounts")]);
  const filters = [
    { value: "", label: "All" },
    { value: "manual", label: "Manual journals" },
    { value: "fund", label: "Marketing requests" },
    { value: "invoice", label: "Invoices" },
  ];
  return (
    <>
      <PageHeader title="Journal entries">
        All posted entries, newest first. Marketing requests post their entries automatically at release, liquidation, refund and reimbursement, and invoices when issued or voided. Posted entries
        are never edited: reverse an entry and post the correction.
      </PageHeader>
      {me.permissions?.includes("journal.post") && (
        <div className="mb-4">
          <JournalForm accounts={chart.items} org={me.org} today={fmt.todayKey()} />
        </div>
      )}
      <nav aria-label="Show" className="mb-3 flex flex-wrap gap-1.5">
        {filters.map((f) => (
          <Link
            key={f.value}
            href={f.value ? `/ledger?source=${f.value}` : "/ledger"}
            aria-current={source === f.value ? "page" : undefined}
            className={`rounded-[3px] border px-3 py-1 text-meta ${source === f.value ? "border-hema bg-hema-tint font-semibold text-hema" : "border-rule-strong text-ink-2 hover:border-control"}`}
          >
            {f.label}
          </Link>
        ))}
      </nav>
      {entries.items.length === 0 ? (
        <Sheet>
          <Empty title="No entries yet" icon="lists">
            Entries appear as cash advances are released and liquidated, or as manual journals are posted.
          </Empty>
        </Sheet>
      ) : (
        <div className="space-y-3">
          {entries.items.map((e) => (
            <Sheet key={e.id} className="scroll-mt-4 px-5 py-3">
              <span id={e.number} />
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="font-mono text-meta font-semibold">{e.number}</p>
                <p className="text-meta text-ink-3">{fmt.dateLabel(e.date)}</p>
                <p className="min-w-0 flex-1 text-sm">
                  {e.memo}
                  {e.reference && <span className="text-ink-3"> · Ref. {e.reference}</span>}
                </p>
                {e.fundRequestId && (
                  <Link href={`/funds/${e.fundRequestId}`} className="text-meta text-hema hover:underline">
                    Marketing request
                  </Link>
                )}
                {e.reversedById && <span className="rounded-full bg-bench px-2 py-0.5 text-meta text-ink-2">Reversed</span>}
                {!e.reversedById && !e.reversesId && me.permissions?.includes("journal.reverse") && <ReverseButton id={e.id} number={e.number} />}
              </div>
              <table className="mt-2 w-full text-sm">
                <tbody>
                  {e.lines.map((ln, i) => (
                    <tr key={i} className="border-t border-rule">
                      <td className={`py-1.5 ${ln.creditCentavos ? "pl-8" : ""}`}>
                        <Link href={`/ledger/accounts/${ln.account.id}`} className="hover:text-hema hover:underline">
                          {ln.account.code} · {ln.account.name}
                        </Link>
                        {ln.description && <span className="text-ink-3"> · {ln.description}</span>}
                      </td>
                      <td className="w-36 py-1.5 text-right tabular-nums">{ln.debitCentavos ? fmt.peso(ln.debitCentavos) : ""}</td>
                      <td className="w-36 py-1.5 text-right tabular-nums">{ln.creditCentavos ? fmt.peso(ln.creditCentavos) : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-meta text-ink-3">Posted by {e.postedBy}</p>
            </Sheet>
          ))}
        </div>
      )}
    </>
  );
}

export async function ChartPage() {
  const chart = await load<Chart>("/finance/ledger/accounts");
  return (
    <>
      <PageHeader title="Chart of accounts">
        The accounts all journal entries post to. An account with entries keeps its type: deactivate it rather than deleting it. Each expense category posts to
        one of the expense accounts.
      </PageHeader>
      <Sheet className="px-5 py-4">
        <ChartEditor accounts={chart.items} canEdit={chart.canEdit} />
      </Sheet>
    </>
  );
}

/** One account's lines, with the balance after each. */
export async function AccountPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const { id } = await params;
  const sp = await searchParams;
  const [from, to] = [one(sp.from), one(sp.to)];
  const query = new URLSearchParams();
  if (isDate(from)) query.set("from", from);
  if (isDate(to)) query.set("to", to);
  const ledger = await load<AccountLedger>(`/finance/ledger/accounts/${enc(id)}${query.size ? `?${query}` : ""}`);
  const a = ledger.account;
  return (
    <>
      <PageHeader crumbs={[{ href: "/ledger/accounts", label: "Chart of accounts" }]} title={`${a.code} · ${a.name}`}>
        {TYPE_LABELS[a.type as AccountType]} · balance {fmt.peso(ledger.closingCentavos)}
      </PageHeader>
      <form className="mb-4 flex flex-wrap items-end gap-3" action={`/ledger/accounts/${a.id}`}>
        <label className="text-meta text-ink-2">
          From
          <input type="date" name="from" defaultValue={from} className="ml-2 h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </label>
        <label className="text-meta text-ink-2">
          To
          <input type="date" name="to" defaultValue={to} className="ml-2 h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </label>
        <button type="submit" className="h-8 rounded-[3px] border border-rule-strong bg-sheet px-3 text-meta font-semibold hover:border-control">
          Show
        </button>
      </form>
      <Sheet className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-sm">
          <thead>
            <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
              <th className="px-5 py-2.5 font-semibold">Date</th>
              <th className="px-3 py-2.5 font-semibold">Entry</th>
              <th className="px-3 py-2.5 text-right font-semibold">Debit</th>
              <th className="px-3 py-2.5 text-right font-semibold">Credit</th>
              <th className="px-5 py-2.5 text-right font-semibold">Balance</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {isDate(from) && (
              <tr className="text-ink-2">
                <td className="px-5 py-2" colSpan={4}>
                  Opening balance
                </td>
                <td className="px-5 py-2 text-right tabular-nums">{fmt.peso(ledger.openingCentavos)}</td>
              </tr>
            )}
            {ledger.lines.map((ln, i) => (
              <tr key={i}>
                <td className="px-5 py-2 whitespace-nowrap text-ink-2">{fmt.dateLabel(ln.date)}</td>
                <td className="px-3 py-2">
                  <span className="font-mono text-meta">{ln.number}</span> {ln.memo}
                  {ln.description && <span className="text-ink-3"> · {ln.description}</span>}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{ln.debitCentavos ? fmt.peso(ln.debitCentavos) : ""}</td>
                <td className="px-3 py-2 text-right tabular-nums">{ln.creditCentavos ? fmt.peso(ln.creditCentavos) : ""}</td>
                <td className="px-5 py-2 text-right font-medium tabular-nums">{fmt.peso(ln.balanceCentavos)}</td>
              </tr>
            ))}
            {ledger.lines.length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-6 text-center text-meta text-ink-3">
                  No entries in this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Sheet>
    </>
  );
}

/** Every account's debits and credits up to a day: they must be equal. */
export async function TrialBalancePage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const sp = await searchParams;
  const to = one(sp.to);
  const tb = await load<TrialBalance>(`/finance/ledger/trial-balance${isDate(to) ? `?to=${to}` : ""}`);
  const balanced = tb.debitCentavos === tb.creditCentavos;
  return (
    <>
      <PageHeader title="Trial balance">
        As of {fmt.dateLabel(tb.to)}. {balanced ? "Debits and credits are equal." : "Debits and credits do not agree: review the journal entries."}
      </PageHeader>
      <form className="mb-4 flex items-end gap-3" action="/ledger/trial-balance">
        <label className="text-meta text-ink-2">
          As of
          <input type="date" name="to" defaultValue={tb.to} className="ml-2 h-8 rounded-[3px] border border-rule-strong bg-sheet px-2 text-sm" />
        </label>
        <button type="submit" className="h-8 rounded-[3px] border border-rule-strong bg-sheet px-3 text-meta font-semibold hover:border-control">
          Show
        </button>
      </form>
      <Sheet className="overflow-x-auto">
        {tb.rows.length === 0 ? (
          <Empty title="No entries yet" icon="lists" />
        ) : (
          <table className="w-full min-w-[36rem] text-sm">
            <thead>
              <tr className="border-b border-rule text-left text-caps text-ink-3 uppercase">
                <th className="px-5 py-2.5 font-semibold">Account</th>
                <th className="px-3 py-2.5 text-right font-semibold">Debit</th>
                <th className="px-5 py-2.5 text-right font-semibold">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {tb.rows.map((r) => (
                <tr key={r.account.id}>
                  <td className="px-5 py-2">
                    <Link href={`/ledger/accounts/${r.account.id}`} className="hover:text-hema hover:underline">
                      <span className="font-mono text-meta text-ink-2">{r.account.code}</span> {r.account.name}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{r.debitCentavos ? fmt.peso(r.debitCentavos) : ""}</td>
                  <td className="px-5 py-2 text-right tabular-nums">{r.creditCentavos ? fmt.peso(r.creditCentavos) : ""}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className={`border-t-2 border-ink font-semibold tabular-nums ${balanced ? "" : "text-danger"}`}>
                <td className="px-5 py-2.5">Total</td>
                <td className="px-3 py-2.5 text-right">{fmt.peso(tb.debitCentavos)}</td>
                <td className="px-5 py-2.5 text-right">{fmt.peso(tb.creditCentavos)}</td>
              </tr>
            </tfoot>
          </table>
        )}
      </Sheet>
    </>
  );
}

export async function PostingPage() {
  const [posting, chart] = await Promise.all([load<Posting>("/finance/ledger/posting"), load<Chart>("/finance/ledger/accounts")]);
  return (
    <>
      <PageHeader title="Default accounts">
        The accounts used by the automatic entries for marketing requests. On release: debit Advances to employees, credit the cash or bank account used. On
        liquidation: debit each category&apos;s expense account, credit Advances to employees, and credit Due to employees for any excess spent. Refunds and
        reimbursements settle these same accounts.
      </PageHeader>
      <Sheet className="px-5 py-4">
        <PostingEditor posting={posting} accounts={chart.items} />
      </Sheet>
    </>
  );
}
