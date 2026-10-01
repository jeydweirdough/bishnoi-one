import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Bars } from "@/src/platform/ui/bars";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { AlertList } from "../components/alerts";
import { Figures, NoAccess } from "../components/ui";
import { MOVEMENT_KINDS, ORDER_KINDS, referenceHref, signed } from "../lib/labels";
import { context } from "../lib/page";
import type { Dashboard } from "../lib/types";

export const metadata = { title: "Dashboard" };

export default async function DashboardPage() {
  const { fmt, may, at } = await context();
  if (!may("dashboard.view")) return <NoAccess what="the dashboard" />;
  const d = await load<Dashboard>("/inventory/dashboard");
  const t = d.totals;

  return (
    <>
      <PageHeader
        title="Inventory"
        actions={
          <>
            {may("receiving.receive") && (
              <LinkButton href="/receipts/new" icon={<Plus className="size-4" aria-hidden />}>
                Receive stock
              </LinkButton>
            )}
            {may("orders.create") && (
              <LinkButton href="/orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
                New order
              </LinkButton>
            )}
          </>
        }
      >
        What you have, where it is, what&apos;s moving, and what needs attention.
      </PageHeader>

      <Figures
        items={[
          { label: "Products", value: fmt.count(t.products), href: "/products" },
          { label: "Units on hand", value: fmt.count(t.units), href: "/stock" },
          { label: "Stock value (at cost)", value: fmt.pesoCompact(t.value), href: "/reports/valuation" },
          { label: "Low stock", value: fmt.count(t.low), flag: t.low > 0, href: "/stock?state=low" },
          { label: "Out of stock", value: fmt.count(t.out), flag: t.out > 0, href: "/stock?state=out" },
          { label: "Batches expiring", value: fmt.count(t.expiring), flag: t.expiring > 0, href: "/batches?expiry=expiring" },
        ]}
      />

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Sheet className="px-5 pt-4 pb-4">
          <SectionTitle icon="alerts" action={<Link href="/alerts" className="text-meta text-hema hover:underline">All alerts</Link>}>
            Needs attention
          </SectionTitle>
          <AlertList alerts={d.alerts} compact />
        </Sheet>

        <Sheet className="px-5 pt-4 pb-4">
          <SectionTitle icon="warehouses" action={<Link href="/warehouses" className="text-meta text-hema hover:underline">Warehouses</Link>}>
            Stock by warehouse
          </SectionTitle>
          {d.warehouses.length === 0 ? (
            <Empty title="No warehouses yet" icon="warehouses">
              Add a warehouse, then receive stock into it.
            </Empty>
          ) : (
            <>
              <Bars rows={d.warehouses.map((w) => ({ label: `${w.name} · ${fmt.pesoCompact(w.value)}`, value: w.units, href: `/warehouses/${w.id}` }))} unit="units" />
              <p className="mt-3 text-meta text-ink-3">
                {fmt.count(t.reserved)} units held for orders · {fmt.count(t.inTransit)} in transit
              </p>
            </>
          )}
        </Sheet>
      </div>

      {d.recentMovements.length > 0 && (
        <Sheet className="mt-5 px-5 pt-4 pb-3">
          <SectionTitle icon="history" action={<Link href="/movements" className="text-meta text-hema hover:underline">Every movement</Link>}>
            Recent stock movements
          </SectionTitle>
          <ul className="mt-1 divide-y divide-rule">
            {d.recentMovements.map((m) => {
              const href = referenceHref(m.referenceType, m.referenceId);
              return (
                <li key={m.id} className="grid gap-x-4 py-2.5 text-sm sm:grid-cols-[10rem_minmax(0,1fr)_6rem]">
                  <span className="text-meta text-ink-3 tabular-nums">{at(m.at)}</span>
                  <span className="min-w-0">
                    <Link href={`/products/${m.product.id}`} className="font-semibold hover:text-hema hover:underline">
                      {m.product.name}
                    </Link>
                    <span className="text-ink-2"> · {MOVEMENT_KINDS[m.kind]} · {m.warehouse.code}</span>
                    <span className="block text-meta text-ink-3">
                      {href ? <Link href={href} className="hover:text-hema hover:underline">{m.reference}</Link> : m.reference} · {m.user}
                    </span>
                  </span>
                  <span className={`text-right font-semibold tabular-nums ${m.quantity < 0 ? "text-ink" : "text-hema"}`}>{signed(m.quantity, fmt.count)}</span>
                </li>
              );
            })}
          </ul>
        </Sheet>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        {may("receiving.view") && (
          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle icon="receiving" action={<Link href="/receipts" className="text-meta text-hema hover:underline">All receiving</Link>}>
              Recently received
            </SectionTitle>
            {d.recentReceipts.length === 0 ? (
              <p className="py-3 text-meta text-ink-3">Nothing received yet.</p>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {d.recentReceipts.map((r) => (
                  <li key={r.id} className="flex items-baseline justify-between gap-3 py-2.5 text-sm">
                    <span className="min-w-0">
                      <Link href={`/receipts/${r.id}`} className="font-semibold hover:text-hema hover:underline">
                        {r.number}
                      </Link>
                      <span className="text-ink-2"> · {r.supplier?.name ?? "No supplier"}</span>
                      <span className="block text-meta text-ink-3">
                        {at(r.receivedAt)} · {r.warehouse.code}
                        {r.order && <> · {r.order.number}</>}
                      </span>
                    </span>
                    <span className="shrink-0 tabular-nums">{fmt.count(r.units)} units</span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        )}
        {may("orders.view") && (
          <Sheet className="px-5 pt-4 pb-3">
            <SectionTitle icon="issuance" action={<Link href="/orders?status=issued" className="text-meta text-hema hover:underline">All issued</Link>}>
              Recently issued
            </SectionTitle>
            {d.recentIssues.length === 0 ? (
              <p className="py-3 text-meta text-ink-3">Nothing issued yet.</p>
            ) : (
              <ul className="mt-1 divide-y divide-rule">
                {d.recentIssues.map((o) => (
                  <li key={o.id} className="flex items-baseline justify-between gap-3 py-2.5 text-sm">
                    <span className="min-w-0">
                      <Link href={`/orders/${o.id}`} className="font-semibold hover:text-hema hover:underline">
                        {o.number}
                      </Link>
                      <span className="text-ink-2"> · {o.recipient}</span>
                      <span className="block text-meta text-ink-3">
                        {at(o.issuedAt)} · {ORDER_KINDS[o.kind]} · {o.warehouse.code}
                      </span>
                    </span>
                    <span className="shrink-0 tabular-nums">{fmt.count(o.units)} units</span>
                  </li>
                ))}
              </ul>
            )}
          </Sheet>
        )}
      </div>
    </>
  );
}
