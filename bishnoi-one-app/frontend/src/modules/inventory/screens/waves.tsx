import Link from "next/link";
import { load } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess, Table, Td } from "@/src/modules/inventory/components/ui";
import { NewWave, WaveSteps } from "@/src/modules/inventory/components/packing";
import { context, type Params } from "@/src/modules/inventory/lib/page";
import type { OrderBrief, Wave, WaveBrief } from "@/src/modules/inventory/lib/types";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";

// Wave picking (feature plan step 14d): several held deliveries from one warehouse, one walk through the shelves.

export async function WavesPage() {
  const { may, at } = await context();
  if (!may("orders.view")) return <NoAccess what="waves" />;
  const [{ items }, held] = await Promise.all([
    load<{ items: WaveBrief[] }>("/inventory/waves"),
    may("orders.issue") ? load<OrderBrief[]>("/inventory/orders?status=confirmed,picking") : Promise.resolve([] as OrderBrief[]),
  ]);
  const waiting = held.filter((o) => !o.waveId).map((o) => ({ id: o.id, number: o.number, recipient: o.recipient, warehouse: o.warehouse.name, units: o.units }));
  return (
    <>
      <PageHeader title="Waves">Pick several deliveries together from one list: each product once, where to take it, and which delivery each part goes to.</PageHeader>
      {may("orders.issue") && (
        <Sheet className="mb-5 px-5 py-4">
          <NewWave orders={waiting} />
        </Sheet>
      )}
      <Sheet>
        {items.length === 0 ? (
          <Empty icon="lists" title="No waves yet" source="Deliveries whose stock is held (confirmed), chosen above." />
        ) : (
          <Table head={["Wave", "Warehouse", "Deliveries", " Units", "Started"]} min="40rem">
            {items.map((w) => (
              <tr key={w.id} className="relative hover:bg-bench/40">
                <Td>
                  <Link href={`/inventory/waves/${w.id}`} className="font-semibold text-ink hover:underline after:absolute after:inset-0">{w.number}</Link>
                  <span className="block text-meta text-ink-3">{w.status === "open" ? "Picking" : `Picked ${at(w.doneAt)}`}</span>
                </Td>
                <Td>{w.warehouse.name}</Td>
                <Td>{w.orders.map((o) => o.number).join(", ")}</Td>
                <Td num>{w.units}</Td>
                <Td>{at(w.createdAt)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function WavePage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { may, at, day } = await context();
  if (!may("orders.view")) return <NoAccess what="waves" />;
  const w = await load<Wave>(`/inventory/waves/${encodeURIComponent(id)}`);
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/waves", label: "Waves" }]}
        title={w.number}
        actions={
          <>
            <LinkButton href={`/inventory/print/waves/${w.id}`}>Print pick list</LinkButton>
            {may("orders.issue") && <WaveSteps waveId={w.id} open={w.status === "open"} orders={w.orders.map((o) => ({ id: o.id, number: o.number }))} />}
          </>
        }
      >
        {w.status === "open" ? "Picking" : `Picked ${at(w.doneAt)}`} · {w.warehouse.name} · {w.orders.length} deliveries, {w.units} units
      </PageHeader>
      <Sheet className="mb-5">
        <Table head={["Product", " Total", "Take from", "For"]} min="48rem">
          {w.pickList.map((r) => (
            <tr key={r.product.id} className="align-top">
              <Td><span className="font-medium">{r.product.name}</span><span className="block text-meta text-ink-3">{r.product.sku}</span></Td>
              <Td num className="font-semibold">{r.total}</Td>
              <Td>
                {r.short > 0 ? <span className="text-danger">Not enough on hand to suggest where</span> : r.from.map((f, i) => (
                  <span key={i} className="block">
                    {f.quantity} from <span className="font-mono">{f.location.code}</span>
                    {f.batch && <span className="text-ink-3"> · {f.batch.batchNo}{f.batch.expiresOn && ` (exp. ${day(f.batch.expiresOn)})`}</span>}
                  </span>
                ))}
              </Td>
              <Td>
                {r.orders.map((o) => (
                  <span key={o.orderId} className="block">
                    {o.quantity} → <Link href={`/inventory/orders/${o.orderId}`} className="font-mono text-hema hover:underline">{o.number}</Link> <span className="text-ink-3">{o.recipient}</span>
                  </span>
                ))}
              </Td>
            </tr>
          ))}
        </Table>
      </Sheet>
      <p className="text-meta text-ink-3">When it&apos;s picked, pack and issue each delivery from its own page.</p>
    </>
  );
}
