import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { BatchActions } from "@/src/modules/pharmacy/components/batch-actions";
import { BatchStatusMark, ExpiryWords, Head, NoAccess, Qty, SearchBar, Tabs } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import type { BatchList } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Batch & expiry" };

const VIEWS = {
  all: { label: "Batch records", empty: "No batches yet", hint: "Every lot on record, by medicine and expiry." },
  expiring: { label: "Expiring medicines", empty: "Nothing expiring soon", hint: "" },
  expired: { label: "Expired medicines", empty: "Nothing expired on the shelf", hint: "Take them off the shelf with a stock adjustment." },
  held: { label: "Recall / quarantine", empty: "Nothing held back", hint: "Neither can be dispensed or sold." },
} as const;
type View = keyof typeof VIEWS;

export default async function BatchesPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("batches.view");
  if (!allowed) return <NoAccess what="batches" />;
  const search = await searchParams;
  const view = (param(search, "view", "all") in VIEWS ? param(search, "view", "all") : "all") as View;
  const q = param(search, "q");
  const medicine = param(search, "medicine");
  const list = await load<BatchList>(`/batches?view=${view}${q ? `&q=${enc(q)}` : ""}${medicine ? `&medicineId=${enc(medicine)}` : ""}`);
  const manage = may("batches.manage");
  const adjust = may("stock.adjust");
  const hint = view === "expiring" ? `Available batches expiring within ${list.withinDays} days, soonest first.` : VIEWS[view].hint;

  return (
    <>
      <PageHeader title="Batch & expiry">
        Every batch keeps its lot number and expiry. Only available, unexpired batches can be dispensed or sold.
      </PageHeader>
      <Tabs
        label="Batch & expiry"
        current={view}
        tabs={(Object.keys(VIEWS) as View[]).map((v) => ({ value: v, label: VIEWS[v].label, href: `/pharmacy/batches?view=${v}` }))}
      />
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SearchBar q={q} placeholder="Lot number, medicine or code" keep={{ view, ...(medicine ? { medicine } : {}) }} />
        <p className="text-meta text-ink-3">
          {hint}
          {list.items.length > 0 && ` Value at cost: ${fmt.peso(list.valueCentavos)}.`}
          {medicine && (
            <>
              {" "}
              <Link href={`/pharmacy/batches?view=${view}`} className="font-semibold text-hema hover:underline">
                Show every medicine
              </Link>
            </>
          )}
        </p>
      </div>

      <Sheet>
        {list.items.length === 0 ? (
          <Empty icon={view === "held" ? "held" : "batches"} title={q ? "No batches match" : VIEWS[view].empty} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-left text-sm">
              <Head columns={["Medicine & lot", "Expires", { label: "On hand", right: true }, "Supplier", "Status", { label: "", right: true }]} />
              <tbody className="divide-y divide-rule">
                {list.items.map((b) => (
                  <tr key={b.id} className="hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5 align-top">
                      <Link href={`/pharmacy/medicines/${b.medicine.id}`} className="font-semibold text-hema hover:underline">
                        {b.medicine.label}
                      </Link>
                      <span className="block text-meta text-ink-3">
                        Lot {b.lotNo} · received {b.qtyReceived}
                        {b.manufacturedOn ? ` · made ${fmt.dateLabel(b.manufacturedOn)}` : ""}
                      </span>
                    </td>
                    <td className="px-3 py-3 align-top whitespace-nowrap">
                      {fmt.dateLabel(b.expiresOn)}
                      <span className="block text-meta">
                        <ExpiryWords days={b.daysToExpiry} />
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right align-top">
                      <Qty n={b.qtyOnHand} unit={b.medicine.unit} />
                      <span className="block text-meta text-ink-3">{fmt.peso(b.valueCentavos)}</span>
                    </td>
                    <td className="px-3 py-3 align-top text-ink-2">{b.supplier?.name ?? "—"}</td>
                    <td className="px-3 py-3 align-top">
                      <BatchStatusMark status={b.status} expired={b.expired} />
                      {b.statusReason && <span className="mt-1 block max-w-[14rem] text-meta text-ink-3">{b.statusReason}</span>}
                    </td>
                    <td className="py-3 pr-5 pl-3 text-right align-top">
                      <span className="flex flex-col items-end gap-1">
                        {manage && <BatchActions id={b.id} lotNo={b.lotNo} status={b.status} />}
                        {adjust && b.qtyOnHand > 0 && (b.expired || b.status !== "available") && (
                          <Link href={`/pharmacy/stock/adjust?batch=${b.id}`} className="text-meta font-semibold text-hema hover:underline">
                            Take off the shelf
                          </Link>
                        )}
                      </span>
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
