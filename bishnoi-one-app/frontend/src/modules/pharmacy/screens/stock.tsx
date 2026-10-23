import { PackagePlus, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/pharmacy/platform/ui/button";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { Head, NoAccess, Qty, RxClassMark, SearchBar, Tabs } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import { MOVEMENT_KINDS } from "@/src/modules/pharmacy/lib/words";
import type { Movement, Receiving, StockRow } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Stock" };

const VIEWS = {
  current: "Current stock",
  low: "Low stock",
  receiving: "Stock receiving",
  adjustment: "Stock adjustment",
  movement: "Stock movement",
} as const;
type View = keyof typeof VIEWS;

export default async function StockPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("stock.view");
  if (!allowed) return <NoAccess what="stock" />;
  const search = await searchParams;
  const view = (param(search, "view", "current") in VIEWS ? param(search, "view", "current") : "current") as View;
  const q = param(search, "q");
  const before = param(search, "before");

  const header = (
    <>
      <PageHeader
        title="Stock"
        actions={
          <>
            {may("stock.adjust") && (
              <LinkButton href="/pharmacy/stock/adjust" icon={<SlidersHorizontal className="size-4" aria-hidden />}>
                Adjust stock
              </LinkButton>
            )}
            {may("stock.receive") && (
              <LinkButton href="/pharmacy/stock/receive" variant="primary" icon={<PackagePlus className="size-4" aria-hidden />}>
                Receive stock
              </LinkButton>
            )}
          </>
        }
      >
        On hand counts every unit on the shelf; available only what can be given out today.
      </PageHeader>
      <Tabs label="Stock" current={view} tabs={(Object.keys(VIEWS) as View[]).map((v) => ({ value: v, label: VIEWS[v], href: `/pharmacy/stock?view=${v}` }))} />
    </>
  );

  if (view === "current" || view === "low") {
    const { items, valueCentavos } = await load<{ items: StockRow[]; valueCentavos: number }>(`/stock?view=${view}${q ? `&q=${enc(q)}` : ""}`);
    return (
      <>
        {header}
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <SearchBar q={q} placeholder="Medicine or code" keep={{ view }} />
          <p className="text-meta text-ink-3">
            {view === "low" ? "At or below the reorder level. " : ""}Value at cost: {fmt.peso(valueCentavos)}.
          </p>
        </div>
        <Sheet>
          {items.length === 0 ? (
            <Empty icon="stock" title={view === "low" ? "Nothing is running low" : "No medicines yet"} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[50rem] text-left text-sm">
                <Head columns={["Medicine", { label: "On hand", right: true }, { label: "Available", right: true }, { label: "Reorder at", right: true }, "Nearest expiry", { label: "Value", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {items.map((r) => (
                    <tr key={r.medicine.id} className="relative hover:bg-bench/40">
                      <td className="py-3 pr-3 pl-5">
                        <span className="flex flex-wrap items-center gap-2">
                          <Link href={`/pharmacy/medicines/${r.medicine.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                            {r.medicine.label}
                          </Link>
                          <RxClassMark rxClass={r.medicine.rxClass} />
                        </span>
                        <span className="block text-meta text-ink-3">{r.medicine.code}</span>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <Qty n={r.onHand} />
                      </td>
                      <td className="px-3 py-3 text-right">{r.low && r.medicine.status === "active" ? <Flag letter="!">{r.available}</Flag> : <Qty n={r.available} />}</td>
                      <td className="px-3 py-3 text-right text-ink-2 tabular-nums">{r.reorderLevel}</td>
                      <td className="px-3 py-3 text-ink-2">{r.nearestExpiry ? fmt.dateLabel(r.nearestExpiry) : "—"}</td>
                      <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(r.valueCentavos)}</td>
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

  if (view === "receiving") {
    const rows = await load<Receiving[]>("/stock/receivings");
    return (
      <>
        {header}
        <Sheet>
          {rows.length === 0 ? (
            <Empty icon="receive" title="No deliveries taken in yet" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <Head columns={["Delivery", "Supplier", { label: "Lines", right: true }, { label: "Units", right: true }, { label: "Received", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {rows.map((r) => (
                    <tr key={r.id} className="relative hover:bg-bench/40">
                      <td className="py-3 pr-3 pl-5">
                        <Link href={`/pharmacy/stock/receivings/${r.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {r.number}
                        </Link>
                        {r.reference && <span className="block text-meta text-ink-3">Invoice {r.reference}</span>}
                      </td>
                      <td className="px-3 py-3 text-ink-2">{r.supplier?.name ?? "—"}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{r.lineCount}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{r.units}</td>
                      <td className="py-3 pr-5 pl-3 text-right text-meta text-ink-2">
                        {fmt.dateLabel(r.receivedOn)}
                        {r.receivedBy && <span className="block">{r.receivedBy.name}</span>}
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

  const kind = view === "adjustment" ? "&kind=adjust" : "";
  const page = await load<{ items: Movement[]; more: boolean }>(`/stock/movements?limit=100${kind}${before ? `&before=${enc(before)}` : ""}`);
  return (
    <>
      {header}
      <Sheet>
        {page.items.length === 0 ? (
          <Empty icon="movements" title={view === "adjustment" ? "No adjustments yet" : "No stock has moved yet"} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[52rem] text-left text-sm">
              <Head columns={["When", "Medicine & lot", "What", { label: "Change", right: true }, { label: "Left in lot", right: true }, "By"]} />
              <tbody className="divide-y divide-rule">
                {page.items.map((m) => (
                  <tr key={m.id}>
                    <td className="py-3 pr-3 pl-5 text-meta whitespace-nowrap text-ink-2">{fmt.whenLabel(m.at)}</td>
                    <td className="px-3 py-3">
                      <Link href={`/pharmacy/medicines/${m.medicine.id}`} className="font-semibold text-hema hover:underline">
                        {m.medicine.label}
                      </Link>
                      <span className="block text-meta text-ink-3">Lot {m.batch.lotNo}</span>
                    </td>
                    <td className="px-3 py-3 text-ink-2">
                      {MOVEMENT_KINDS[m.kind]}
                      {m.reference && <span className="text-ink-3"> · {m.reference}</span>}
                      {m.reason && <span className="block text-meta text-ink-3">{m.reason}</span>}
                    </td>
                    <td className={`px-3 py-3 text-right font-semibold tabular-nums ${m.quantity < 0 ? "text-ink" : "text-hema"}`}>
                      {m.quantity > 0 ? `+${m.quantity}` : m.quantity}
                    </td>
                    <td className="px-3 py-3 text-right text-ink-2 tabular-nums">{m.balance}</td>
                    <td className="py-3 pr-5 pl-3 text-ink-2">{m.by?.name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {page.more && (
          <div className="border-t border-rule px-5 py-3 text-right">
            <Link href={`/pharmacy/stock?view=${view}&before=${page.items[page.items.length - 1].id}`} className="text-meta font-semibold text-hema hover:underline">
              Older movements
            </Link>
          </div>
        )}
      </Sheet>
    </>
  );
}
