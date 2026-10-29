import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { AddBankAccount, BankActions, BankBadge, CloseYear, EquityForm, LockForm, RateForm, type Bank, type Provider } from "@/src/modules/finance/banking/forms";

// Banks, payments and equity (feature plan step 16): the company's bank accounts and e-wallets, exchange rates,
// owner's equity, closing the year and the period lock.

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

type AccountRow = { id: string; code: string; name: string; type: string; isActive: boolean };

export async function BankAccountsPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [{ items, providers }, { items: accounts }, usd] = await Promise.all([
    load<{ items: Bank[]; providers: Provider[] }>("/finance/bank-accounts"),
    load<{ items: AccountRow[] }>("/finance/ledger/accounts"),
    load<{ items: { on: string; rate: number; createdBy: string }[] }>("/finance/exchange-rates?currency=USD"),
  ]);
  const manage = may(me, "accounts.manage");
  const assets = accounts.filter((a) => a.type === "asset" && a.isActive);
  return (
    <>
      <PageHeader title="Bank accounts and payment channels">
        The company&apos;s bank accounts and e-wallets (GCash, Maya), each with the ledger account its money is kept in. Payments name where the money went; vouchers, where it came from.
      </PageHeader>
      {manage && (
        <Sheet className="mb-5 px-5 py-4">
          <AddBankAccount providers={providers} accounts={assets} />
        </Sheet>
      )}
      <Sheet className="mb-5">
        {items.length === 0 ? (
          <Empty title="No bank accounts yet" icon="money">Add the company&apos;s bank accounts and e-wallets above.</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((b) => (
              <li key={b.id} className={`flex flex-wrap items-center gap-3 px-5 py-3 ${b.isActive ? "" : "opacity-60"}`}>
                <BankBadge provider={b.provider} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-ink">
                    {b.name}
                    {b.isDefault && <span className="ml-2 rounded-full bg-hema-tint px-1.5 text-stamp text-hema uppercase">Usual</span>}
                  </span>
                  <span className="block text-meta text-ink-3">
                    {b.provider.name}{b.accountNumber && ` · ${b.accountNumber}`}{b.accountName && ` · ${b.accountName}`} · {b.currency} · {b.account.code} {b.account.name}
                  </span>
                </span>
                {manage && <BankActions bank={b} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
      <Sheet className="px-5 py-4">
        <SectionTitle icon="money">Exchange rates</SectionTitle>
        <p className="mb-3 text-meta text-ink-3">Pesos per unit, by day: foreign-currency supplier bills are booked at the rate on their day and paid at the rate on the day paid; the difference is an exchange gain or loss.</p>
        {manage && <RateForm today={fmt.todayKey()} />}
        {usd.items.length > 0 && (
          <ul className="mt-3 grid gap-1 text-sm sm:grid-cols-3">
            {usd.items.slice(0, 12).map((r) => (
              <li key={r.on} className="flex justify-between rounded border border-rule px-3 py-1.5">
                <span className="text-ink-3">{fmt.dateLabel(r.on)}</span>
                <span className="tabular-nums">USD {r.rate.toFixed(4)}</span>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

type Closing = { lockedUntil: string | null; years: { yearEnd: string; closed: boolean; closedBy: string | null; netIncomeCentavos: number | null }[]; accountsSet: boolean };
type Statement = { start: string; end: string; closed: boolean; rows: { label: string; amountCentavos: number }[] };

export async function ClosingPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [closing, banks] = await Promise.all([
    load<Closing>("/finance/closing"),
    load<{ items: Bank[] }>("/finance/bank-accounts").then((r) => r.items.filter((b) => b.isActive)),
  ]);
  const last = closing.years[0];
  const statement = await load<Statement>(`/finance/equity/statement?yearEnd=${last.yearEnd}`);
  const manage = may(me, "accounts.manage");
  return (
    <>
      <PageHeader title="Closing and owner's equity">
        Capital put in and drawings taken out; each fiscal year closed into retained earnings; and the books locked so nothing is posted into a closed period.
      </PageHeader>
      <div className="grid gap-5 lg:grid-cols-2">
        <Sheet className="px-5 py-4">
          <SectionTitle icon="money">Statement of changes in equity</SectionTitle>
          <p className="mb-2 text-meta text-ink-3">Fiscal year {fmt.dateLabel(statement.start)} to {fmt.dateLabel(statement.end)}{statement.closed ? " (closed)" : ""}</p>
          <table className="w-full text-sm">
            <tbody>
              {statement.rows.map((r, i) => (
                <tr key={r.label} className={i === statement.rows.length - 1 ? "border-t-2 border-rule-strong font-semibold" : "border-b border-rule"}>
                  <td className="py-1.5">{r.label}</td>
                  <td className="py-1.5 text-right tabular-nums">{fmt.peso(r.amountCentavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="money">Capital and drawings</SectionTitle>
          {may(me, "journal.post") ? <EquityForm banks={banks.map((b) => ({ id: b.id, name: b.name }))} today={fmt.todayKey()} /> : <p className="text-meta text-ink-3">Finance records these.</p>}
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="lists">Closing the year</SectionTitle>
          {!closing.accountsSet && <p className="mb-2 text-meta text-danger">Set the capital, drawings and retained earnings accounts under Default accounts first.</p>}
          <ul className="divide-y divide-rule text-sm">
            {closing.years.map((y) => (
              <li key={y.yearEnd} className="flex flex-wrap items-center gap-3 py-2">
                <span className="flex-1">Fiscal year ended {fmt.dateLabel(y.yearEnd)}</span>
                {y.closed ? (
                  <span className="text-meta text-ink-3">Closed by {y.closedBy} · net income {fmt.peso(y.netIncomeCentavos ?? 0)}</span>
                ) : (
                  manage && closing.accountsSet && <CloseYear yearEnd={y.yearEnd} label={fmt.dateLabel(y.yearEnd)} />
                )}
              </li>
            ))}
          </ul>
        </Sheet>
        <Sheet className="px-5 py-4">
          <SectionTitle icon="settings">Period lock</SectionTitle>
          <p className="mb-2 text-meta text-ink-3">
            {closing.lockedUntil ? `Nothing can be posted on or before ${fmt.dateLabel(closing.lockedUntil)}.` : "The books are open: entries can be dated any day."}
          </p>
          {manage ? <LockForm lockedUntil={closing.lockedUntil} today={fmt.todayKey()} /> : null}
        </Sheet>
      </div>
    </>
  );
}
