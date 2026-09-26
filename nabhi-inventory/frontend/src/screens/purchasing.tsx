import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { deletePurchaseOrder, purchaseOrderStep } from "../actions/inventory";
import { PurchaseOrderForm } from "../components/document-forms";
import { ReceiveForm } from "../components/receive-form";
import { RecordTools } from "../components/record-tools";
import { POStamp } from "../components/stamps";
import { StepButton } from "../components/step-button";
import { Chips, ExpiryMark, Filters, NoAccess, RowLink, Table, Td, Trail } from "../components/ui";
import { param, query } from "../lib/labels";
import { canAddFrom, context, type Params, type Search } from "../lib/page";
import type { Backorder, PO, POBrief, Receipt, ReceiptBrief, Reference } from "../lib/types";

export async function PurchaseOrdersPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status") };
  const orders = await load<POBrief[]>(`/inventory/purchase-orders${query(f)}`);
  const chip = (status: string, label: string) => ({ value: status, label, href: `/purchase-orders${query({ q: f.q, status })}` });
  return (
    <>
      <PageHeader
        title="Purchase orders"
        actions={
          <>
            {may("receiving.receive") && <LinkButton href="/receipts/new">Receive without an order</LinkButton>}
            {may("purchasing.create") && <LinkButton href="/purchase-orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New purchase order</LinkButton>}
          </>
        }
      >
        Purchase order → supplier delivers → receiving → stock.
      </PageHeader>
      <Chips label="Status" current={f.status} options={[chip("", "All"), chip("draft", "Drafts"), chip("ordered,partial", "Pending delivery"), chip("partial", "Partly received"), chip("received", "Received"), chip("cancelled", "Cancelled")]} />
      <Filters q={f.q} placeholder="PO number or supplier" keep={{ status: f.status }} />
      <Sheet>
        {orders.length === 0 ? (
          <Empty icon="purchaseOrders" title="No purchase orders here" />
        ) : (
          <Table head={["Order", "Supplier", "Deliver to", "Status", "Ordered", "Expected", " Received", " Total"]} min="56rem">
            {orders.map((po) => (
              <tr key={po.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/purchase-orders/${po.id}`} sub={`${po.lineCount} line${po.lineCount === 1 ? "" : "s"}`}>{po.number}</RowLink></Td>
                <Td>{po.supplier.name}</Td>
                <Td>{po.warehouse.code}</Td>
                <Td><POStamp status={po.status} late={po.late} /></Td>
                <Td>{day(po.orderedOn)}</Td>
                <Td>{day(po.expectedOn)}</Td>
                <Td num>{fmt.count(po.received)} / {fmt.count(po.ordered)}</Td>
                <Td num>{fmt.peso(po.total)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function PurchaseOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, fmt, may, at, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const [po, ref] = await Promise.all([load<PO>(`/inventory/purchase-orders/${enc(id)}`), load<Reference>("/inventory/reference")]);
  const open = po.status === "ordered" || po.status === "partial";
  const outstanding = po.lines.reduce((n, l) => n + l.outstanding, 0);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/purchase-orders", label: "Purchase orders" }]}
        title={po.number}
        tools={
          po.status === "draft" && (
            <RecordTools
              what="purchase order"
              name={po.number}
              editHref={may("purchasing.edit") ? `/purchase-orders/${po.id}/edit` : undefined}
              remove={may("purchasing.edit") ? deletePurchaseOrder.bind(null, po.id) : undefined}
              after="/purchase-orders"
            />
          )
        }
        actions={
          <>
            {po.status === "draft" && may("purchasing.approve") && (
              <StepButton run={purchaseOrderStep.bind(null, po.id, "place")} label="Approve & place order" done={`${po.number} placed`} variant="primary" confirm={{ title: `Place ${po.number} with ${po.supplier.name}?`, body: "It can't be changed once placed, only received against or cancelled.", danger: false }} />
            )}
            {(po.status === "draft" || open) && may("purchasing.approve") && (
              <StepButton
                run={purchaseOrderStep.bind(null, po.id, "cancel")}
                label={po.status === "partial" ? "Close (stop waiting)" : "Cancel order"}
                done={po.status === "partial" ? "Closed: the rest won't come" : "Cancelled"}
                variant="quiet"
                confirm={{ title: po.status === "partial" ? `Close ${po.number}?` : `Cancel ${po.number}?`, body: po.status === "partial" ? `${outstanding} units still owed won't be waited for. What came stays in stock.` : "Nothing will be received against it.", danger: true }}
              />
            )}
          </>
        }
      >
        <POStamp status={po.status} late={po.late} /> <span className="ml-1">{po.supplier.name} → {po.warehouse.name}</span>
      </PageHeader>

      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Written up", who: po.createdBy, when: at(po.createdAt) },
          { label: "Approved & placed", who: po.orderedBy, when: po.orderedOn ? day(po.orderedOn) : null },
          { label: "Expected", who: null, when: po.expectedOn ? day(po.expectedOn) : null },
        ]} />
        {po.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{po.notes}</p>}
      </Sheet>

      <Sheet className="mt-5">
        <Table head={["Product", " Ordered", " Received", " Still owed", " Unit cost", " Amount"]}>
          {po.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td num>{fmt.count(l.quantity)} {l.product.unit}</Td>
              <Td num>{fmt.count(l.received)}</Td>
              <Td num className={l.outstanding ? "font-semibold" : "text-ink-3"}>{l.outstanding ? fmt.count(l.outstanding) : "—"}</Td>
              <Td num>{fmt.peso(l.unitCost)}</Td>
              <Td num>{fmt.peso(l.total)}</Td>
            </tr>
          ))}
          <tr className="border-t-2 border-rule-strong font-semibold">
            <Td>Total</Td>
            <Td num>{fmt.count(po.ordered)}</Td>
            <Td num>{fmt.count(po.received)}</Td>
            <Td num>{open ? fmt.count(outstanding) : "—"}</Td>
            <Td>{""}</Td>
            <Td num>{fmt.peso(po.total)}</Td>
          </tr>
        </Table>
      </Sheet>

      {open && may("receiving.receive") && (
        <section className="mt-6">
          <h2 className="mb-3 text-heading">Receive a delivery</h2>
          <ReceiveForm org={me.org} reference={ref} order={po} canAdd={canAddFrom(may)} />
        </section>
      )}

      {po.receipts.length > 0 && (
        <Sheet className="mt-6">
          <div className="px-5 pt-4"><SectionTitle icon="receiving">Deliveries received</SectionTitle></div>
          <ReceiptsTable receipts={po.receipts} at={at} count={fmt.count} peso={fmt.peso} />
        </Sheet>
      )}
    </>
  );
}

function ReceiptsTable({ receipts, at, count, peso }: { receipts: ReceiptBrief[]; at: (iso: string | null) => string; count: (n: number) => string; peso: (n: number) => string }) {
  return (
    <Table head={["Receipt", "Received", "Supplier", "Into", "Order", " Units", " Value"]} min="52rem">
      {receipts.map((r) => (
        <tr key={r.id} className="relative hover:bg-bench/40">
          <Td><RowLink href={`/receipts/${r.id}`} sub={r.deliveryRef ?? undefined}>{r.number}</RowLink></Td>
          <Td className="whitespace-nowrap">{at(r.receivedAt)}<span className="block text-meta text-ink-3">{r.receivedBy?.name}</span></Td>
          <Td>{r.supplier?.name ?? "—"}</Td>
          <Td>{r.warehouse.code} · {r.location.code}</Td>
          <Td>{r.order ? <Link href={`/purchase-orders/${r.order.id}`} className="relative z-10 hover:text-hema hover:underline">{r.order.number}</Link> : "—"}</Td>
          <Td num>{count(r.units)}</Td>
          <Td num>{peso(r.total)}</Td>
        </tr>
      ))}
    </Table>
  );
}

export async function NewPurchaseOrderPage({ searchParams }: { searchParams: Search }) {
  const { me, may } = await context();
  if (!may("purchasing.create")) return <NoAccess what="writing purchase orders" />;
  const s = await searchParams;
  const ref = await load<Reference>("/inventory/reference");
  return (
    <>
      <PageHeader crumbs={[{ href: "/purchase-orders", label: "Purchase orders" }]} title="New purchase order" />
      <PurchaseOrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} preset={{ supplierId: param(s, "supplier") || undefined, productId: param(s, "product") || undefined, quantity: param(s, "quantity") || undefined }} />
    </>
  );
}

export async function EditPurchaseOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("purchasing.edit")) return <NoAccess what="changing purchase orders" />;
  const [po, ref] = await Promise.all([load<PO>(`/inventory/purchase-orders/${enc(id)}`), load<Reference>("/inventory/reference")]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/purchase-orders", label: "Purchase orders" }, { href: `/purchase-orders/${po.id}`, label: po.number }]} title={`Edit ${po.number}`} />
      <PurchaseOrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} order={po} />
    </>
  );
}

export async function ReceiptsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at } = await context();
  if (!may("receiving.view")) return <NoAccess what="receiving" />;
  const q = param(await searchParams, "q");
  const receipts = await load<ReceiptBrief[]>(`/inventory/receipts${query({ q })}`);
  return (
    <>
      <PageHeader
        title="Receiving"
        actions={may("receiving.receive") && <LinkButton href="/receipts/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>Receive stock</LinkButton>}
      >
        Every delivery taken in. To receive against a purchase order, open the order.
      </PageHeader>
      <Filters q={q} placeholder="Receipt or delivery number" />
      <Sheet>
        {receipts.length === 0 ? <Empty icon="receiving" title="Nothing received yet" /> : <ReceiptsTable receipts={receipts} at={at} count={fmt.count} peso={fmt.peso} />}
      </Sheet>
    </>
  );
}

export async function ReceiptPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("receiving.view")) return <NoAccess what="receiving" />;
  const r = await load<Receipt>(`/inventory/receipts/${enc(id)}`);
  return (
    <>
      <PageHeader crumbs={[{ href: "/receipts", label: "Receiving" }]} title={r.number} actions={may("stock.view") && <LinkButton href={`/movements?q=${enc(r.number)}`}>Its movements</LinkButton>}>
        Received {at(r.receivedAt)} by {r.receivedBy?.name ?? "—"} into {r.warehouse.name} · {r.location.code}
        {r.supplier && <> from {r.supplier.name}</>}
        {r.order && <> against <Link href={`/purchase-orders/${r.order.id}`} className="text-hema hover:underline">{r.order.number}</Link></>}
        {r.deliveryRef && <> · delivery {r.deliveryRef}</>}
      </PageHeader>
      <Sheet>
        <Table head={["Product", "Batch", "Expires", "Serial numbers", " Quantity", " Unit cost", " Amount"]} min="52rem">
          {r.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td className="font-mono">{l.batch?.batchNo ?? "—"}</Td>
              <Td>{l.batch?.expiresOn ? <ExpiryMark expiry={l.batch.expiry} label={day(l.batch.expiresOn)} /> : "—"}</Td>
              <Td className="font-mono text-meta">{l.serials.join(", ") || "—"}</Td>
              <Td num>{fmt.count(l.quantity)} {l.product.unit}</Td>
              <Td num>{fmt.peso(l.unitCost)}</Td>
              <Td num>{fmt.peso(l.total)}</Td>
            </tr>
          ))}
          <tr className="border-t-2 border-rule-strong font-semibold">
            <Td>Total</Td><Td>{""}</Td><Td>{""}</Td><Td>{""}</Td>
            <Td num>{fmt.count(r.units)}</Td><Td>{""}</Td>
            <Td num>{fmt.peso(r.total)}</Td>
          </tr>
        </Table>
      </Sheet>
      {r.notes && <p className="mt-4 text-sm whitespace-pre-line text-ink-2">{r.notes}</p>}
    </>
  );
}

export async function NewReceiptPage() {
  const { me, may } = await context();
  if (!may("receiving.receive")) return <NoAccess what="receiving stock" />;
  const ref = await load<Reference>("/inventory/reference");
  return (
    <>
      <PageHeader crumbs={[{ href: "/receipts", label: "Receiving" }]} title="Receive stock">
        A delivery with no purchase order: a donation, a return, stock found. For an order, receive it from the order.
      </PageHeader>
      <ReceiveForm org={me.org} reference={ref} canAdd={canAddFrom(may)} />
    </>
  );
}

export async function BackordersPage() {
  const { me, fmt, may, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const rows = await load<Backorder[]>("/inventory/backorders");
  return (
    <>
      <PageHeader title="Backorders">Everything still owed on placed purchase orders, soonest expected first.</PageHeader>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="purchaseOrders" title="Nothing is owed" />
        ) : (
          <Table head={["Product", "Order", "Supplier", "Expected", " Ordered", " Received", " Still owed", " Value"]} min="56rem">
            {rows.map((b, i) => (
              <tr key={i} className="relative hover:bg-bench/40">
                <Td><Link href={`/products/${b.product.id}`} className="font-semibold hover:text-hema hover:underline">{b.product.name}</Link><span className="block text-meta text-ink-3">{b.product.sku}</span></Td>
                <Td><RowLink href={`/purchase-orders/${b.order.id}`}>{b.order.number}</RowLink></Td>
                <Td>{b.supplier.name}</Td>
                <Td>{b.order.expectedOn ? day(b.order.expectedOn) : "—"}{b.order.late && <span className="ml-1 text-meta font-semibold text-eosin">Late</span>}</Td>
                <Td num>{fmt.count(b.ordered)}</Td>
                <Td num>{fmt.count(b.received)}</Td>
                <Td num className="font-semibold">{fmt.count(b.outstanding)}</Td>
                <Td num>{fmt.peso(b.value)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}
