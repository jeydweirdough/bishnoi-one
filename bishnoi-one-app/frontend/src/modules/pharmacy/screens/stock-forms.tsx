import Link from "next/link";
import { PageHeader, Particulars, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { AdjustForm } from "@/src/modules/pharmacy/components/adjust-form";
import { Head, NoAccess } from "@/src/modules/pharmacy/components/bits";
import { ReceiveForm } from "@/src/modules/pharmacy/components/receive-form";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import type { BatchList, Medicine, Receiving, Supplier } from "@/src/modules/pharmacy/lib/types";

// Stock's three pages below the list: taking a delivery in, correcting a
// batch, and one delivery on record.

export async function ReceivePage() {
  const { me, allowed } = await pageFor("stock.receive");
  if (!allowed) return <NoAccess what="receiving stock" />;
  const [medicines, suppliers] = await Promise.all([load<Medicine[]>("/medicines?state=all"), load<Supplier[]>("/suppliers")]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/stock?view=receiving", label: "Stock receiving" }]} title="Receive stock">
        Each lot becomes a batch with its own expiry. The same lot again tops that batch up.
      </PageHeader>
      <Sheet className="max-w-[60rem] px-5 py-6 sm:px-8">
        <ReceiveForm
          org={me.org}
          medicines={medicines.filter((m) => m.status !== "discontinued").map((m) => ({ id: m.id, label: `${m.label} · ${m.code}`, unit: m.unit }))}
          suppliers={suppliers.map((s) => ({ id: s.id, name: s.name }))}
        />
      </Sheet>
    </>
  );
}

export async function AdjustPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed } = await pageFor("stock.adjust");
  if (!allowed) return <NoAccess what="adjusting stock" />;
  const preset = param(await searchParams, "batch");
  const { items } = await load<BatchList>("/batches?view=all");
  const batches = items
    .filter((b) => b.qtyOnHand > 0 || b.id === preset)
    .map((b) => ({ id: b.id, label: `${b.medicine.label}, lot ${b.lotNo} (expires ${fmt.dateLabel(b.expiresOn)})`, qtyOnHand: b.qtyOnHand, unit: b.medicine.unit }));
  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/stock?view=adjustment", label: "Stock adjustment" }]} title="Adjust stock">
        Correct one batch by the difference counted: damage, a recount, expired or recalled stock leaving the shelf.
      </PageHeader>
      <Sheet className="max-w-[45rem] px-5 py-6 sm:px-8">
        <AdjustForm batches={batches} preset={preset || undefined} />
      </Sheet>
    </>
  );
}

export async function ReceivingPage({ params }: { params: Promise<{ id: string }> }) {
  const { fmt, allowed } = await pageFor("stock.view");
  if (!allowed) return <NoAccess what="stock" />;
  const { id } = await params;
  const r = await load<Receiving>(`/stock/receivings/${enc(id)}`);
  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/stock?view=receiving", label: "Stock receiving" }]} title={`Delivery ${r.number}`}>
        {r.units} units in {r.lineCount} lot{r.lineCount === 1 ? "" : "s"}
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <Sheet>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-sm">
              <Head columns={["Medicine", "Lot", "Expires", { label: "Quantity", right: true }, { label: "Unit cost", right: true }]} />
              <tbody className="divide-y divide-rule">
                {(r.lines ?? []).map((l) => (
                  <tr key={l.batchId}>
                    <td className="py-3 pr-3 pl-5">
                      <Link href={`/pharmacy/medicines/${l.medicineId}`} className="font-semibold text-hema hover:underline">
                        {l.medicine}
                      </Link>
                    </td>
                    <td className="px-3 py-3">{l.lotNo}</td>
                    <td className="px-3 py-3 text-ink-2">{fmt.dateLabel(l.expiresOn)}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{l.quantity}</td>
                    <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(l.costCentavos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Sheet>
        <Sheet className="h-fit px-5 py-5">
          <Particulars
            items={[
              ["Supplier", r.supplier ? <Link key="s" href={`/pharmacy/suppliers/${r.supplier.id}`} className="text-hema hover:underline">{r.supplier.name}</Link> : null],
              ["Invoice / DR", r.reference],
              ["Received on", fmt.dateLabel(r.receivedOn)],
              ["Received by", r.receivedBy?.name ?? null],
              ["Notes", r.notes],
            ]}
          />
        </Sheet>
      </div>
    </>
  );
}
