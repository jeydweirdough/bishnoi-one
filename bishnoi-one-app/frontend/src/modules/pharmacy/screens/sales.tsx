import { ShoppingCart } from "lucide-react";
import Link from "next/link";
import { Button, LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { FilterInput, Head, NoAccess, Tabs } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import { PAYMENT_METHODS } from "@/src/modules/pharmacy/lib/words";
import type { SaleList, SaleReturn } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Sales" };

const VIEWS = { today: "Sales transactions", history: "Sales history", returns: "Returns", refunds: "Refunds" } as const;
type View = keyof typeof VIEWS;

export default async function SalesPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("sales.view");
  if (!allowed) return <NoAccess what="sales" />;
  const search = await searchParams;
  const view = (param(search, "view", "today") in VIEWS ? param(search, "view", "today") : "today") as View;
  const today = fmt.todayKey();
  const from = param(search, "from") || today.slice(0, 8) + "01";
  const to = param(search, "to") || today;
  const q = param(search, "q");

  const header = (
    <>
      <PageHeader
        title="Sales"
        actions={
          may("sales.create") && (
            <LinkButton href="/pharmacy/sales/new" variant="primary" icon={<ShoppingCart className="size-4" aria-hidden />}>
              Counter sale
            </LinkButton>
          )
        }
      >
        Over-the-counter sales, and the sales dispensing records. Prescription medicines are sold only through dispensing.
      </PageHeader>
      <Tabs label="Sales" current={view} tabs={(Object.keys(VIEWS) as View[]).map((v) => ({ value: v, label: VIEWS[v], href: `/pharmacy/sales?view=${v}` }))} />
    </>
  );

  if (view === "returns" || view === "refunds") {
    const rows = await load<SaleReturn[]>(`/sales/returns?view=${view}`);
    return (
      <>
        {header}
        <Sheet>
          {rows.length === 0 ? (
            <Empty icon="returns" title={view === "refunds" ? "No refunds yet" : "Nothing returned yet"}>
              Returns are made from the sale itself: open it and choose what came back.
            </Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-left text-sm">
                <Head columns={["Return", "On sale", "Reason", { label: "Units", right: true }, { label: "Refund", right: true }, { label: "When", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="py-3 pr-3 pl-5 font-semibold">{r.number}</td>
                      <td className="px-3 py-3">
                        <Link href={`/pharmacy/sales/${r.sale.id}`} className="text-hema hover:underline">
                          {r.sale.number}
                        </Link>
                        {r.patient && <span className="block text-meta text-ink-3">{r.patient.fullName}</span>}
                      </td>
                      <td className="px-3 py-3 text-ink-2">
                        {r.reason}
                        <span className="block text-meta text-ink-3">{r.restocked ? "Back on the shelf" : "Not restocked"}</span>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{r.units}</td>
                      <td className="px-3 py-3 text-right tabular-nums">
                        {r.refundCentavos ? fmt.peso(r.refundCentavos) : <span className="text-ink-3">None</span>}
                        {r.refundMethod && <span className="block text-meta text-ink-3">{PAYMENT_METHODS[r.refundMethod]}</span>}
                      </td>
                      <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">
                        {fmt.whenLabel(r.at)}
                        {r.by && <span className="block">{r.by.name}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Sheet>
      </>
    );
  }

  const list = await load<SaleList>(
    view === "today" ? "/sales?view=today" : `/sales?view=history&from=${enc(from)}&to=${enc(to)}${q ? `&q=${enc(q)}` : ""}`,
  );

  return (
    <>
      {header}
      {view === "history" && (
        <form className="mb-3 flex flex-wrap items-end gap-3" role="search">
          <input suppressHydrationWarning type="hidden" name="view" value="history" />
          <FilterInput label="From" type="date" name="from" defaultValue={from} max={today} />
          <FilterInput label="To" type="date" name="to" defaultValue={to} max={today} />
          <FilterInput label="Sale no. or customer" name="q" defaultValue={q} />
          <Button type="submit" size="sm">
            Show
          </Button>
        </form>
      )}
      <p className="mb-3 text-meta text-ink-2">
        {list.count} sale{list.count === 1 ? "" : "s"} {view === "today" ? "today" : `from ${fmt.dateLabel(from)} to ${fmt.dateLabel(to)}`} ·{" "}
        <span className="font-semibold text-ink">{fmt.peso(list.totalCentavos)}</span>
        {list.refundedCentavos > 0 && ` · ${fmt.peso(list.refundedCentavos)} refunded`}
      </p>
      <Sheet>
        {list.items.length === 0 ? (
          <Empty icon="sales" title={view === "today" ? "No sales yet today" : "No sales in these days"} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <Head columns={["Sale", "Customer", "Items", "Paid by", { label: "Total", right: true }, { label: "When", right: true }]} />
              <tbody className="divide-y divide-rule">
                {list.items.map((s) => (
                  <tr key={s.id} className="relative hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5">
                      <Link href={`/pharmacy/sales/${s.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {s.number}
                      </Link>
                      <span className="block text-meta text-ink-3">{s.source === "dispensing" ? "Dispensing" : "Counter"}</span>
                    </td>
                    <td className="px-3 py-3 text-ink-2">{s.patient?.fullName ?? "Walk-in"}</td>
                    <td className="max-w-[16rem] px-3 py-3 text-ink-2">
                      <span className="line-clamp-2">{s.lines.map((l) => `${l.medicine} × ${l.quantity}`).join(" · ")}</span>
                    </td>
                    <td className="px-3 py-3 text-ink-2">{PAYMENT_METHODS[s.paymentMethod]}</td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      {fmt.peso(s.totalCentavos)}
                      {s.refundedCentavos > 0 && <span className="block text-meta text-ink-3">−{fmt.peso(s.refundedCentavos)} refunded</span>}
                    </td>
                    <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">{fmt.whenLabel(s.soldAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}
