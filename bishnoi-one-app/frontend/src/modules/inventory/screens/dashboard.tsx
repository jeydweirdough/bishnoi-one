import { Plus } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Icon, type IconName } from "@/src/modules/inventory/platform/ui/icons";
import { Empty, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { ToggleLinks } from "@/src/modules/inventory/platform/ui/toggle-links";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { MonthBars, TrendLine } from "@/src/modules/inventory/components/home-charts";
import { POStamp, POStatusIcon } from "@/src/modules/inventory/components/stamps";
import { NoAccess, Table } from "@/src/modules/inventory/components/ui";
import { context, type Search } from "@/src/modules/inventory/lib/page";
import type { Dashboard, PurchaseHome } from "@/src/modules/inventory/lib/types";

export const metadata = { title: "Dashboard" };

// Home, read top to bottom: a greeting; four figures, each with how it compares
// with last month and its twelve-month line; the months as bars beside the
// latest purchase orders; then what's on its way beside what needs attention.

/** This month against last, in words: "+21% vs last month". */
function change(now: number, before: number): { text: string; tone: "up" | "down" | "flat" } {
  if (!before) return { text: now ? "New" : "—", tone: "flat" };
  const pct = Math.round(((now - before) / before) * 100);
  return { text: `${pct > 0 ? "+" : pct < 0 ? "−" : ""}${Math.abs(pct)}%`, tone: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

function Card({ icon, label, value, note, trend, href }: { icon: IconName; label: string; value: string; note: ReactNode; trend?: ReactNode; href: string }) {
  return (
    <Link href={href} className="group block rounded-xl border border-rule bg-sheet px-5 py-4 transition-colors hover:border-rule-strong">
      <p className="flex items-center gap-2.5 border-b border-dashed border-rule pb-3 text-sm font-medium text-ink">
        <span className="grid size-8 place-items-center rounded-lg border border-rule text-ink-2">
          <Icon name={icon} className="size-4" />
        </span>
        {label}
      </p>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[1.75rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums">{value}</p>
          <p className="mt-1 text-meta text-ink-3">{note}</p>
        </div>
        {trend}
      </div>
    </Link>
  );
}

function Change({ c }: { c: ReturnType<typeof change> }) {
  const tone = c.tone === "up" ? "text-sage-deep" : c.tone === "down" ? "text-danger" : "text-ink-3";
  return (
    <>
      <span className={`font-semibold ${tone}`}>{c.text}</span> vs last month
    </>
  );
}

function itemOf(po: PurchaseHome): string {
  if (!po.firstItem) return "No lines";
  return po.moreItems ? `${po.firstItem} and ${po.moreItems} more` : po.firstItem;
}

export default async function DashboardPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, day } = await context();
  if (!may("dashboard.view")) return <NoAccess what="the dashboard" />;
  const { dashboard: d } = await loadQuery<{ dashboard: Dashboard }>("query Dashboard { dashboard }", {}, ["dashboard"]);
  const t = d.totals;
  const chart = (await searchParams).chart === "received" ? "received" : "issued";
  const series = d.trend;
  const [now, last] = [series[series.length - 1], series[series.length - 2]];
  const average = Math.round(series.reduce((n, p) => n + p[chart], 0) / Math.max(1, series.length));
  const yearTotal = series.reduce((n, p) => n + p[chart], 0);
  const firstName = me.user.fullName.split(" ")[0];

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-ink">
            {fmt.greeting()}, {firstName}
          </h1>
          <p className="mt-1 text-sm text-ink-2">Stock, orders and deliveries across {fmt.plural(d.warehouses.length, "warehouse")}.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {may("receiving.receive") && (
            <LinkButton href="/inventory/receipts/new" icon={<Plus className="size-4" aria-hidden />}>
              Receive stock
            </LinkButton>
          )}
          {may("orders.create") && (
            <LinkButton href="/inventory/orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              New order
            </LinkButton>
          )}
        </div>
      </div>


      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card
          icon="issuance"
          label="Open orders"
          value={fmt.count(d.openOrders)}
          note={<Change c={change(now?.orders ?? 0, last?.orders ?? 0)} />}
          trend={<TrendLine values={series.map((p) => p.orders)} label="Orders per month, last 12 months" />}
          href="/inventory/orders?status=confirmed"
        />
        <Card
          icon="receiving"
          label="Received this month"
          value={`${fmt.count(now?.received ?? 0)} units`}
          note={<Change c={change(now?.received ?? 0, last?.received ?? 0)} />}
          trend={<TrendLine values={series.map((p) => p.received)} label="Units received per month, last 12 months" />}
          href="/inventory/receipts"
        />
        <Card
          icon="stock"
          label="Issued this month"
          value={`${fmt.count(now?.issued ?? 0)} units`}
          note={<Change c={change(now?.issued ?? 0, last?.issued ?? 0)} />}
          trend={<TrendLine values={series.map((p) => p.issued)} label="Units issued per month, last 12 months" />}
          href="/inventory/orders?status=issued"
        />
        <Card
          icon="warehouses"
          label="Stock value at cost"
          value={fmt.pesoCompact(t.value)}
          note={
            <>
              {fmt.count(t.units)} units ·{" "}
              <span className={t.out || t.low ? "font-semibold text-danger" : ""}>
                {t.out} out, {t.low} low
              </span>
            </>
          }
          href="/inventory/reports/valuation"
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-ink">Overview</h2>
                <p className="mt-2 text-meta text-ink-3">Monthly average, last 12 months</p>
                <p className="flex items-baseline gap-2">
                  <span className="text-[1.75rem] leading-tight font-semibold tracking-[-0.02em] text-ink tabular-nums">{fmt.count(average)} units</span>
                  <span className="rounded-md bg-hema-tint px-2.5 py-0.5 text-meta font-semibold text-sage-deep">{fmt.count(yearTotal)} in all</span>
                </p>
              </div>
              <ToggleLinks
                current={chart}
                options={[
                  { value: "issued", label: "Issued", href: "/inventory" },
                  { value: "received", label: "Received", href: "/inventory?chart=received" },
                ]}
              />
            </div>
            <div className="mt-6">
              <MonthBars
                unit="units"
                points={series.map((p) => ({ label: fmt.monthLabel(p.month).slice(0, 3), long: fmt.monthLabel(p.month), value: p[chart] }))}
              />
            </div>
          </Sheet>

          {may("purchasing.view") && (
            <Sheet className="overflow-hidden">
              <div className="px-5 pt-4">
                <SectionTitle icon="receiving" action={<Link href="/inventory/purchase-orders?status=ordered" className="text-meta text-ink hover:underline">View all</Link>}>
                  Upcoming deliveries
                </SectionTitle>
              </div>
              {d.upcoming.length === 0 ? (
                <div className="px-5 pb-4">
                  <Empty title="No open purchase orders" icon="purchaseOrders" actions={may("purchasing.create") && <LinkButton href="/inventory/purchase-orders/new" icon={<Plus className="size-4" aria-hidden />}>New purchase order</LinkButton>}>
                    Purchase orders placed with suppliers show here until they&apos;re received.
                  </Empty>
                </div>
              ) : (
                <Table head={["Order", "Product", " Quantity", "Expected", "Status"]} min="36rem">
                  {d.upcoming.map((po) => (
                    <tr key={po.id} className="hover:bg-bench/50">
                      <td className="px-3 py-3 pl-5">
                        <Link href={`/inventory/purchase-orders/${po.id}`} className="font-semibold whitespace-nowrap text-ink hover:underline">
                          {po.number}
                        </Link>
                        <span className="block text-meta text-ink-3">{po.supplier.name}</span>
                      </td>
                      <td className="px-3 py-3 text-ink-2">
                        {itemOf(po)}
                        <span className="block text-meta text-ink-3">To {po.warehouse.name}</span>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{fmt.count(Math.max(0, po.ordered - po.received))}</td>
                      <td className={`px-3 py-3 whitespace-nowrap ${po.late ? "font-semibold text-danger" : "text-ink-2"}`}>{day(po.expectedOn)}</td>
                      <td className="px-3 py-3 pr-5">
                        <POStamp status={po.status} late={po.late} />
                      </td>
                    </tr>
                  ))}
                </Table>
              )}
            </Sheet>
          )}
        </div>

        <div className="min-w-0 space-y-5">
          {may("purchasing.view") && (
            <Sheet className="px-5 pt-4 pb-3">
              <SectionTitle icon="purchaseOrders" action={<Link href="/inventory/purchase-orders" className="text-meta text-ink hover:underline">View all</Link>}>
                Purchase history
              </SectionTitle>
              {d.recentPurchases.length === 0 ? (
                <p className="py-3 text-meta text-ink-3">No purchase orders.</p>
              ) : (
                <ul className="divide-y divide-rule">
                  {d.recentPurchases.map((po) => (
                    <li key={po.id}>
                      <Link href={`/inventory/purchase-orders/${po.id}`} className="flex gap-3 py-3 hover:opacity-80">
                        <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-hema-tint text-sage-deep">
                          <Icon name="purchaseOrders" className="size-5" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex min-w-0 items-center gap-1.5">
                            <span className="truncate text-sm font-semibold text-ink">{itemOf(po)}</span>
                            <POStatusIcon status={po.status} late={po.late} />
                          </span>
                          <span className="mt-1.5 grid grid-cols-[5.5rem_minmax(0,1fr)] gap-y-0.5 text-meta">
                            <span className="text-ink-3">Order</span>
                            <span className="truncate text-ink-2">{po.number}</span>
                            <span className="text-ink-3">{po.status === "received" ? "Ordered" : "Expected"}</span>
                            <span className="text-ink-2">{day(po.status === "received" ? po.orderedOn : po.expectedOn)}</span>
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Sheet>
          )}

        </div>
      </div>
    </>
  );
}
