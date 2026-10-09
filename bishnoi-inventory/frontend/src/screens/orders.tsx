import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { deleteOrder, orderStep } from "../actions/inventory";
import { OrderForm } from "../components/document-forms";
import { PickForm, type PickLine } from "../components/pick-form";
import { RecordTools } from "../components/record-tools";
import { OrderStamp } from "../components/stamps";
import { StepButton } from "../components/step-button";
import { Chips, Filters, NoAccess, RowLink, Stamp, Table, Td, Trail } from "../components/ui";
import { ORDER_KINDS, param, query } from "../lib/labels";
import { canAddFrom, context, type Params, type Search } from "../lib/page";
import { batchChoices, given, referenceOf } from "../lib/reference";
import type { BatchRow, Order, OrderBrief, Reference, Reservation } from "../lib/types";

export async function OrdersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, day, at } = await context();
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status"), kind: param(s, "kind") };
  const { orders } = await loadQuery<{ orders: OrderBrief[] }>(`query Orders($q: String, $status: String, $kind: String) { orders(q: $q, status: $status, kind: $kind) }`, given(f), ["orders"]);
  const issued = f.status === "issued";
  const chip = (status: string, label: string) => ({ value: status, label, href: `/orders${query({ ...f, status })}` });
  return (
    <>
      <PageHeader
        title={issued ? "Issuance history" : "Orders"}
        actions={may("orders.create") && <LinkButton href="/orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New order</LinkButton>}
      >
        Stock going out: customer orders, and issues to departments and projects. Order → reserved → picked → issued.
      </PageHeader>
      {!issued && <Chips label="Status" current={f.status} options={[chip("", "All"), chip("draft", "Drafts"), chip("confirmed", "Reserved"), chip("picking", "Picking"), chip("cancelled", "Cancelled")]} />}
      <Filters q={f.q} placeholder="Order number or who it's for" keep={{ status: f.status }} />
      <Sheet>
        {orders.length === 0 ? (
          <Empty icon="issuance" title="No orders here" />
        ) : (
          <Table head={["Order", "For", "Kind", "From", "Status", issued ? "Issued" : "Needed by", " Units", " Value"]} min="56rem">
            {orders.map((o) => (
              <tr key={o.id} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/orders/${o.id}`}>{o.number}</RowLink></Td>
                <Td>{o.recipient}</Td>
                <Td className="text-ink-2">{ORDER_KINDS[o.kind]}</Td>
                <Td>{o.warehouse.code}</Td>
                <Td><OrderStamp status={o.status} /></Td>
                <Td className="whitespace-nowrap">{issued ? at(o.issuedAt) : day(o.neededOn)}</Td>
                <Td num>{fmt.count(o.units)}</Td>
                <Td num>{o.total ? fmt.peso(o.total) : "—"}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function OrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const { order: o } = await loadQuery<{ order: Order }>(`query Order($id: String!) { order(id: $id) }`, { id }, ["order"]);
  const held = o.status === "confirmed" || o.status === "picking";
  // The batches each batch-tracked line could come from, soonest to expire
  // first: the warehouse's batches in one read, rather than one per line.
  const picking = held && may("orders.issue");
  const { batches } = picking && o.lines.some((l) => l.product.trackBatches)
    ? await loadQuery<{ batches: BatchRow[] }>(`query Batches($w: String) { batches(warehouse: $w) }`, { w: o.warehouse.id }, ["batches"])
    : { batches: [] as BatchRow[] };
  const pickLines: PickLine[] = picking
    ? o.lines.map((l) => ({ id: l.id, product: l.product, quantity: l.quantity, batches: l.product.trackBatches ? batchChoices(batches, l.product.id, day) : [] }))
    : [];
  const short = o.lines.filter((l) => l.available !== null && l.available < l.quantity);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/orders", label: "Orders" }]}
        title={o.number}
        tools={o.status === "draft" && (
          <RecordTools what="order" name={o.number} editHref={may("orders.edit") ? `/orders/${o.id}/edit` : undefined} remove={may("orders.edit") ? deleteOrder.bind(null, o.id) : undefined} after="/orders" />
        )}
        actions={
          <>
            {o.status === "draft" && may("orders.approve") && (
              <StepButton run={orderStep.bind(null, o.id, "confirm")} label="Confirm & reserve stock" done="Stock reserved for this order" variant="primary" />
            )}
            {o.status === "confirmed" && (may("orders.issue") || may("orders.approve")) && (
              <StepButton run={orderStep.bind(null, o.id, "pick")} label="Start picking" done="Picking: the stock is allocated" />
            )}
            {(o.status === "draft" ? may("orders.edit") : held && may("orders.approve")) && (
              <StepButton run={orderStep.bind(null, o.id, "cancel")} label="Cancel order" done="Order cancelled" variant="quiet" confirm={{ title: `Cancel ${o.number}?`, body: held ? "The stock it holds is let go for others." : undefined, danger: true }} />
            )}
          </>
        }
      >
        <OrderStamp status={o.status} /> <span className="ml-1">{ORDER_KINDS[o.kind]} for <strong>{o.recipient}</strong>, from {o.warehouse.name}{o.neededOn && <>, needed by {day(o.neededOn)}</>}</span>
      </PageHeader>

      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Written up", who: o.createdBy, when: at(o.createdAt) },
          { label: "Confirmed & reserved", who: o.confirmedBy, when: o.confirmedAt ? at(o.confirmedAt) : null },
          { label: "Issued", who: o.issuedBy, when: o.issuedAt ? at(o.issuedAt) : null },
        ]} />
        {o.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{o.notes}</p>}
      </Sheet>

      <Sheet className="mt-5">
        <Table head={["Product", " Quantity", ...(o.status === "draft" ? [" Available now"] : []), ...(o.status === "issued" ? ["Taken from"] : []), " Unit price", " Amount"]}>
          {o.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
              <Td num>{fmt.count(l.quantity)} {l.product.unit}</Td>
              {o.status === "draft" && <Td num className={l.available !== null && l.available < l.quantity ? "font-semibold text-eosin" : "text-ink-2"}>{fmt.count(l.available ?? 0)}</Td>}
              {o.status === "issued" && (
                <Td className="text-meta text-ink-2">
                  {l.picks.map((p, i) => <span key={i} className="block">{p.quantity} from {p.locationCode}{p.batchNo && ` · ${p.batchNo}`}{p.expiresOn && ` (exp. ${day(p.expiresOn)})`}</span>)}
                  {l.serials.length > 0 && <span className="block font-mono">{l.serials.join(", ")}</span>}
                </Td>
              )}
              <Td num>{l.unitPrice ? fmt.peso(l.unitPrice) : "—"}</Td>
              <Td num>{l.total ? fmt.peso(l.total) : "—"}</Td>
            </tr>
          ))}
        </Table>
      </Sheet>
      {o.status === "draft" && short.length > 0 && (
        <p className="mt-3 text-meta text-eosin">Not enough is available for {short.map((l) => l.product.name).join(", ")}: it can&apos;t be confirmed until there is.</p>
      )}

      {held && may("orders.issue") && (
        <Sheet className="mt-6 px-5 pt-4 pb-5">
          <SectionTitle icon="issuance">Issue it</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">Stock leaves {o.warehouse.name} now, and the reservation is let go.</p>
          <PickForm kind="order" documentId={o.id} lines={pickLines} label="Issue & ship" />
        </Sheet>
      )}
      {o.status === "issued" && may("stock.view") && (
        <p className="mt-4 text-meta"><Link href={`/movements${query({ q: o.number })}`} className="text-hema hover:underline">See its movements</Link></p>
      )}
    </>
  );
}

/** The order form's lists, with what's free per product per warehouse ("productId:warehouseId" → units). */
const ORDER_FORM = `${referenceOf("products", "units", "warehouses")} availability`;
type OrderFormData = { reference: Pick<Reference, "products" | "units" | "warehouses">; availability: Record<string, number> };

export async function NewOrderPage() {
  const { me, may } = await context();
  if (!may("orders.create")) return <NoAccess what="writing orders" />;
  const { reference: ref, availability: available } = await loadQuery<OrderFormData>(`query NewOrder { ${ORDER_FORM} }`, {}, ["reference", "availability"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/orders", label: "Orders" }]} title="New order" />
      <OrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} available={available} />
    </>
  );
}

export async function EditOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("orders.edit")) return <NoAccess what="changing orders" />;
  const { order: o, reference: ref, availability: available } = await loadQuery<OrderFormData & { order: Order }>(
    `query EditOrder($id: String!) { order(id: $id) ${ORDER_FORM} }`,
    { id },
    ["order", "reference", "availability"],
  );
  return (
    <>
      <PageHeader crumbs={[{ href: "/orders", label: "Orders" }, { href: `/orders/${o.id}`, label: o.number }]} title={`Edit ${o.number}`} />
      <OrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} order={o} available={available} />
    </>
  );
}

export async function ReservationsPage() {
  const { fmt, may, day } = await context();
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const { reservations: rows } = await loadQuery<{ reservations: Reservation[] }>("query Reservations { reservations }", {}, ["reservations"]);
  return (
    <>
      <PageHeader title="Reservations">Stock held for open orders: reserved once confirmed, allocated while it&apos;s being picked. Nobody else can take it.</PageHeader>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="issuance" title="Nothing is held" />
        ) : (
          <Table head={["Product", "Order", "For", "Warehouse", "Needed by", "State", " Quantity"]} min="52rem">
            {rows.map((r, i) => (
              <tr key={i} className="relative hover:bg-bench/40">
                <Td><Link href={`/products/${r.product.id}`} className="font-semibold hover:text-hema hover:underline">{r.product.name}</Link></Td>
                <Td><RowLink href={`/orders/${r.order.id}`}>{r.order.number}</RowLink></Td>
                <Td>{r.order.recipient}</Td>
                <Td>{r.warehouse.code}</Td>
                <Td>{day(r.order.neededOn)}</Td>
                <Td><Stamp tone="active">{r.state === "reserved" ? "Reserved" : "Allocated"}</Stamp></Td>
                <Td num>{fmt.count(r.quantity)} {r.product.unit}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}
