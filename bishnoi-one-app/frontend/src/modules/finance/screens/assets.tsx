import Link from "next/link";
import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { AddAsset, BudgetLine, Depreciate, DisposeAsset, RemoveBudget } from "@/src/modules/finance/banking/assets";

// Fixed assets and budgets (feature plan step 17).

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;
const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");

type Acc = { id: string; code: string; name: string; type: string; isActive: boolean };
type Asset = { id: string; name: string; costCentavos: number; accumulatedCentavos: number; bookValueCentavos: number; monthlyCentavos: number; acquiredOn: string;
               usefulMonths: number; depreciatedUntil: string | null; status: string; divisionName: string | null; assetAccount: { code: string; name: string } | null };

export async function FixedAssetsPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const [{ items, totals }, { items: accounts }] = await Promise.all([
    load<{ items: Asset[]; totals: { costCentavos: number; accumulatedCentavos: number; bookValueCentavos: number } }>("/finance/fixed-assets"),
    load<{ items: Acc[] }>("/finance/ledger/accounts"),
  ]);
  const active = accounts.filter((a) => a.isActive);
  return (
    <>
      <PageHeader title="Fixed assets">
        What the company owns for years, depreciated straight-line each month: (cost − worth at the end) ÷ useful months. Buying one is its bill or journal entry; this keeps the register and posts the depreciation.
      </PageHeader>
      <div className="mb-5 grid gap-5 lg:grid-cols-2">
        {may(me, "accounts.manage") && <Sheet className="px-5 py-4"><AddAsset accounts={active} today={fmt.todayKey()} /></Sheet>}
        {may(me, "journal.post") && <Sheet className="px-5 py-4"><Depreciate today={fmt.todayKey()} /></Sheet>}
      </div>
      <Sheet>
        {items.length === 0 ? (
          <Empty title="No fixed assets yet" icon="lists">Add vehicles, equipment and computers above.</Empty>
        ) : (
          <table className="w-full min-w-[52rem] text-sm">
            <thead><tr className="border-b border-rule text-left text-meta text-ink-3">
              <th className="px-5 py-2">Asset</th><th className="py-2">Bought</th><th className="py-2 text-right">Cost</th><th className="py-2 text-right">A month</th>
              <th className="py-2 text-right">Depreciated</th><th className="py-2 text-right">Book value</th><th className="px-5 py-2" />
            </tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id} className={`border-b border-rule ${a.status === "active" ? "" : "opacity-60"}`}>
                  <td className="px-5 py-2"><span className="font-medium text-ink">{a.name}</span><span className="block text-meta text-ink-3">{a.assetAccount?.name}{a.divisionName && ` · ${a.divisionName}`}{a.depreciatedUntil && ` · to ${fmt.dateLabel(a.depreciatedUntil)}`}</span></td>
                  <td className="py-2">{fmt.dateLabel(a.acquiredOn)}</td>
                  <td className="py-2 text-right tabular-nums">{fmt.peso(a.costCentavos)}</td>
                  <td className="py-2 text-right tabular-nums">{fmt.peso(a.monthlyCentavos)}</td>
                  <td className="py-2 text-right tabular-nums">{fmt.peso(a.accumulatedCentavos)}</td>
                  <td className="py-2 text-right font-semibold tabular-nums">{fmt.peso(a.bookValueCentavos)}</td>
                  <td className="px-5 py-2 text-right">{a.status === "active" ? may(me, "accounts.manage") && <DisposeAsset id={a.id} name={a.name} /> : <span className="text-meta text-ink-3">Disposed</span>}</td>
                </tr>
              ))}
              <tr className="font-semibold"><td className="px-5 py-2">Active assets</td><td /><td className="py-2 text-right tabular-nums">{fmt.peso(totals.costCentavos)}</td><td />
                <td className="py-2 text-right tabular-nums">{fmt.peso(totals.accumulatedCentavos)}</td><td className="py-2 text-right tabular-nums">{fmt.peso(totals.bookValueCentavos)}</td><td /></tr>
            </tbody>
          </table>
        )}
      </Sheet>
    </>
  );
}

type BudgetRow = { id: string; account: { code: string; name: string; type: string }; divisionName: string | null; totalCentavos: number };

export async function BudgetsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const closing = await load<{ years: { yearEnd: string }[] }>("/finance/closing");
  // This fiscal year and the next, besides the ones that ended.
  const ended = closing.years.map((y) => y.yearEnd);
  const next = (d: string) => `${Number(d.slice(0, 4)) + 1}${d.slice(4)}`;
  const years = [next(next(ended[0])), next(ended[0]), ...ended.slice(0, 2)];
  const chosen = one((await searchParams).year) || years[1];
  const [{ items }, { items: accounts }] = await Promise.all([
    load<{ items: BudgetRow[] }>(`/finance/budgets?yearEnd=${chosen}`),
    load<{ items: Acc[] }>("/finance/ledger/accounts"),
  ]);
  return (
    <>
      <PageHeader title="Budgets">
        Each income and expense account&apos;s budget for a fiscal year (and a division, when set), spread over its months. Compared with what happened in Reports: Budget against actual.
      </PageHeader>
      <div className="mb-3 flex flex-wrap gap-3 text-sm">
        {years.map((y) => <Link key={y} href={`/finance/ledger/budgets?year=${y}`} className={y === chosen ? "font-semibold text-ink" : "text-hema hover:underline"}>Year ending {fmt.dateLabel(y)}</Link>)}
      </div>
      {may(me, "accounts.manage") && <Sheet className="mb-5 px-5 py-4"><BudgetLine yearEnd={chosen} accounts={accounts.filter((a) => a.isActive)} /></Sheet>}
      <Sheet className="px-5 py-4">
        <SectionTitle icon="lists">Year ending {fmt.dateLabel(chosen)}</SectionTitle>
        {items.length === 0 ? <p className="text-meta text-ink-3">No budget for this year yet.</p> : (
          <ul className="divide-y divide-rule text-sm">
            {items.map((b) => (
              <li key={b.id} className="flex items-center gap-3 py-1.5">
                <span className="flex-1">{b.account.code} · {b.account.name}{b.divisionName && <span className="text-ink-3"> · {b.divisionName}</span>}</span>
                <span className="tabular-nums">{fmt.peso(b.totalCentavos)}</span>
                {may(me, "accounts.manage") && <RemoveBudget id={b.id} />}
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
