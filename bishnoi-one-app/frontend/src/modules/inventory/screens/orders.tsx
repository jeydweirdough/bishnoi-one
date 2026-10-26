import { Ban, ClipboardList, ExternalLink, PackageOpen, Pencil, Plus, Printer, Trash2 } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { FigureStrip, ListFrame, ListToolbar, StatusPill, UnderlineTabs, type Figure, type PillTone } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";

import Link from "next/link";
import { notFound } from "next/navigation";
import { Icon } from "@/src/modules/inventory/platform/ui/icons";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deleteOrder, orderStep } from "@/src/modules/inventory/actions/inventory";
import { OrderForm } from "@/src/modules/inventory/components/document-forms";
import { PrintLink } from "@/src/modules/inventory/components/print-button";
import { PickForm, type PickLine } from "@/src/modules/inventory/components/pick-form";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { OrderStamp } from "@/src/modules/inventory/components/stamps";
import { StepButton } from "@/src/modules/inventory/components/step-button";
import { Chips, Filters, NoAccess, RowLink, Stamp, Table, Td, Trail } from "@/src/modules/inventory/components/ui";
import { ORDER_KINDS, param, query } from "@/src/modules/inventory/lib/labels";
import { FirstStep, NeedsFirst } from "@/src/modules/inventory/components/setup";
import { KINDS, kindBySlug, kindOf, listHref, newHref } from "@/src/modules/inventory/lib/order-kinds";
import { ToggleLinks } from "@/src/modules/inventory/platform/ui/toggle-links";
import { OrdersBoard } from "@/src/modules/inventory/screens/boards";
import { loadSetup } from "@/src/modules/inventory/lib/setup";
import { Pager } from "@/src/modules/inventory/platform/ui/pager";
import { canAddFrom, context, keepInRange, paging, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { batchChoices, given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { BatchRow, Order, OrderBrief, Paged, Reference, Reservation } from "@/src/modules/inventory/lib/types";

type OrderFigures = { openCount: number; issuedThisMonth: number; issuedLastMonth: number };

const ORDER_TABS: [string, string][] = [["", "All"], ["draft", "Drafts"], ["confirmed", "Reserved"], ["picking", "Picking"], ["issued", "Issued"], ["cancelled", "Cancelled"]];

const ORDER_PILL: Record<OrderBrief["status"], [PillTone, string]> = {
  draft: ["plain", "Draft"],
  confirmed: ["info", "Reserved"],
  picking: ["warn", "Picking"],
  issued: ["good", "Issued"],
  cancelled: ["bad", "Cancelled"],
};

/** This month against last, in words: "12% vs last month". */
function change(now: number, before: number): Figure["change"] {
  if (!before) return now ? { text: "New this month", tone: "flat" } : undefined;
  const pct = Math.round(((now - before) / before) * 100);
  return { text: `${Math.abs(pct)}% vs last month`, tone: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

export async function OrdersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, day, at } = await context();
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status"), kind: param(s, "kind") };
  // A board unless asked for the list, or for one status (which is a column, read as a list).
  const board = param(s, "view") !== "list" && !f.status;
  // The board shows every open one in its columns; the list is read a page at a time.
  const { page, size, vars } = paging(s);
  const base = `/inventory/orders${query({ ...f, view: board ? "" : "list" })}`;
  const { orders: got } = await loadQuery<{ orders: OrderBrief[] | Paged<OrderBrief> }>(
    `query Orders($q: String, $status: String, $kind: String, $limit: Int, $offset: Int) { orders(q: $q, status: $status, kind: $kind, limit: $limit, offset: $offset) }`,
    { ...given(f), ...(board ? {} : vars) },
    ["orders"],
  );
  const list: Paged<OrderBrief> = Array.isArray(got) ? { items: got, total: got.length } : got;
  const figures = board ? null : (await loadQuery<{ orderFigures: OrderFigures }>("query($kind: String) { orderFigures(kind: $kind) }", { kind: f.kind || null }, ["orderFigures"])).orderFigures;
  if (!board) keepInRange(list.items.length, list.total, page, base);
  const orders = list.items;
  const issued = f.status === "issued";
  const info = kindOf(f.kind);
  const chip = (status: string, label: string) => ({ value: status, label, href: `/inventory/orders${query({ ...f, status })}` });
  return (
    <>
      <PageHeader
        title={issued ? (info ? `${info.plural}: issued` : "Issuance history") : info ? info.plural : "All orders"}
        actions={may("orders.create") && <LinkButton href={info ? newHref(info) : "/inventory/orders/new"} variant="primary" icon={<Plus className="size-4" aria-hidden />}>{info ? info.newLabel : "New order"}</LinkButton>}
      >
        {info ? `${info.intro} Reserved, picked, then issued.` : "Outbound stock: customer orders and issues to departments and projects. Order → reserved → picked → issued."}
      </PageHeader>
      {board && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <ToggleLinks
            current="board"
            options={[
              { value: "board", label: "Board", href: `/inventory/orders${query({ ...f, status: "", view: "" })}` },
              { value: "list", label: "List", href: `/inventory/orders${query({ ...f, view: "list" })}` },
              { value: "reservations", label: "Reservations", href: "/inventory/reservations" },
            ]}
          />
        </div>
      )}
      <Chips label="Type" current={f.kind} options={[{ value: "", label: "All types", href: `/inventory/orders${query({ ...f, kind: "" })}` }, ...KINDS.map((k) => ({ value: k.kind, label: k.plural, href: `/inventory/orders${query({ ...f, kind: k.kind })}` }))]} />
      {board ? (
        <>
          <Filters q={f.q} placeholder={info ? `Order number or ${info.recipient.label.toLowerCase()}` : "Order number or recipient"} keep={{ status: f.status, kind: f.kind, view: "" }} />
          {orders.length > 0 ? (
            <OrdersBoard orders={orders} fmt={fmt} day={day} may={may} kind={f.kind || undefined} />
          ) : (
            <Sheet>
              <FirstStep icon={info?.icon ?? "issuance"} title={info ? `No ${info.plural.toLowerCase()}` : "No orders"} body={info ? info.intro : "An order reserves stock for a customer or department until it is issued."} needs={["warehouse", "stock"]} href={info ? newHref(info) : "/inventory/orders/new"} action={info ? info.newLabel : "New order"} permission="orders.create" filtered={Boolean(f.q)} clear={info ? listHref(info) : "/inventory/orders"} may={may} />
            </Sheet>
          )}
        </>
      ) : (
        <ListFrame>
          {figures && (
            <FigureStrip
              figures={[
                { label: "Open orders", value: fmt.count(figures.openCount), icon: <ClipboardList className="size-5" aria-hidden /> },
                ...(!info || info.priced ? [{ label: "Issued this month", value: fmt.peso(figures.issuedThisMonth), icon: <PackageOpen className="size-5" aria-hidden />, change: change(figures.issuedThisMonth, figures.issuedLastMonth) }] : []),
              ]}
            />
          )}
          <UnderlineTabs tabs={ORDER_TABS.map(([value, label]) => ({ href: `/inventory/orders${query({ q: f.q, kind: f.kind, status: value, view: "list" })}`, label, current: f.status === value }))} />
          <ListToolbar q={f.q} placeholder={info ? `Search order number or ${info.recipient.label.toLowerCase()}` : "Search order number or recipient"} keep={{ status: f.status, kind: f.kind, view: "list" }}>
            <ToggleLinks
              current="list"
              options={[
                { value: "board", label: "Board", href: `/inventory/orders${query({ q: f.q, kind: f.kind })}` },
                { value: "list", label: "List", href: `/inventory/orders${query({ ...f, view: "list" })}` },
                { value: "reservations", label: "Reservations", href: "/inventory/reservations" },
              ]}
            />
          </ListToolbar>
          {orders.length === 0 ? (
            <FirstStep icon={info?.icon ?? "issuance"} title={info ? `No ${info.plural.toLowerCase()}` : "No orders"} body={info ? info.intro : "An order reserves stock for a customer or department until it is issued."} needs={["warehouse", "stock"]} href={info ? newHref(info) : "/inventory/orders/new"} action={info ? info.newLabel : "New order"} permission="orders.create" filtered={Boolean(f.q || f.status)} clear={`/inventory/orders${query({ kind: f.kind, view: "list" })}`} may={may} />
          ) : (
            <ExpandableTable
              minWidth="52rem"
              columns={[
                { key: "order", label: "Order" },
                { key: "to", label: info ? info.recipient.label : "Recipient" },
                ...(info ? [] : [{ key: "kind", label: "Type" }]),
                { key: "when", label: issued ? "Issued" : "Required date" },
                { key: "units", label: "Units", align: "right" as const },
                ...(!info || info.priced ? [{ key: "value", label: "Value", align: "right" as const }] : []),
                { key: "status", label: "Status" },
              ]}
              rows={orders.map((o) => {
                const st = ORDER_PILL[o.status];
                const priced = !info || info.priced;
                return {
                  id: o.id,
                  muted: o.status === "cancelled",
                  actions: (
                    <RowMenu
                      label={`Actions for ${o.number}`}
                      items={[
                        { label: "Open", icon: <ExternalLink />, href: `/inventory/orders/${o.id}` },
                        ...(o.status === "draft" && may("orders.edit") ? [{ label: "Edit", icon: <Pencil />, href: `/inventory/orders/${o.id}/edit` }] : []),
                        "divider" as const,
                        { label: "Print", icon: <Printer />, href: `/inventory/print/orders/${o.id}` },
                        ...((o.status === "draft" ? may("orders.edit") : (o.status === "confirmed" || o.status === "picking") && may("orders.approve"))
                          ? [
                              "divider" as const,
                              { label: "Cancel order", icon: <Ban />, run: orderStep.bind(null, o.id, "cancel" as const), danger: true, confirm: `Cancel ${o.number}?`, done: "Order cancelled" },
                            ]
                          : []),
                        ...(o.status === "draft" && may("orders.edit")
                          ? [{ label: "Delete", icon: <Trash2 />, run: deleteOrder.bind(null, o.id), danger: true, confirm: `Delete ${o.number}? This can't be undone.`, done: `${o.number} deleted` }]
                          : []),
                      ]}
                    />
                  ),
                  cells: [
                    <Link key="n" href={`/inventory/orders/${o.id}`} className="font-mono text-meta font-semibold text-ink hover:text-sage-deep hover:underline">{o.number}</Link>,
                    <span key="r" className="font-medium text-ink">{o.recipient}</span>,
                    ...(info ? [] : [<span key="k" className="text-ink-2">{ORDER_KINDS[o.kind]}</span>]),
                    <span key="w" className="whitespace-nowrap text-ink-2">{issued ? at(o.issuedAt) : day(o.neededOn)}</span>,
                    <span key="u">{fmt.count(o.units)}</span>,
                    ...(priced ? [<span key="v" className="font-medium">{o.total ? fmt.peso(o.total) : ""}</span>] : []),
                    <StatusPill key="s" tone={st[0]}>{st[1]}</StatusPill>,
                  ],
                  detail: (
                    <div className="space-y-3">
                      <table className="w-full text-meta">
                        <thead>
                          <tr className="text-left text-ink-3">
                            <th className="py-1 pr-3 font-medium">SKU</th>
                            <th className="px-3 py-1 font-medium">Item</th>
                            <th className="px-3 py-1 text-right font-medium">Quantity</th>
                            {priced && <th className="px-3 py-1 text-right font-medium">Unit price</th>}
                            {priced && <th className="py-1 pl-3 text-right font-medium">Amount</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {o.items.map((l) => (
                            <tr key={l.sku} className="border-t border-rule/70">
                              <td className="py-1.5 pr-3 font-mono text-ink-2">{l.sku}</td>
                              <td className="px-3 py-1.5 text-ink">{l.product}</td>
                              <td className="px-3 py-1.5 text-right tabular-nums">{fmt.count(l.quantity)}</td>
                              {priced && <td className="px-3 py-1.5 text-right tabular-nums text-ink-2">{fmt.peso(l.unitPrice)}</td>}
                              {priced && <td className="py-1.5 pl-3 text-right font-medium tabular-nums">{fmt.peso(l.quantity * l.unitPrice)}</td>}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule/70 pt-3">
                        <LinkButton href={`/inventory/orders/${o.id}`}>Open order</LinkButton>
                      </div>
                    </div>
                  ),
                };
              })}
            />
          )}
        </ListFrame>
      )}
      {!board && <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "order" : "orders"} />}
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
        crumbs={[{ href: listHref(kindOf(o.kind)!), label: kindOf(o.kind)!.plural }]}
        title={o.number}
        tools={o.status === "draft" && (
          <RecordTools what="order" name={o.number} editHref={may("orders.edit") ? `/inventory/orders/${o.id}/edit` : undefined} remove={may("orders.edit") ? deleteOrder.bind(null, o.id) : undefined} after="/inventory/orders" />
        )}
        actions={
          <>
            <PrintLink href={`/inventory/print/orders/${o.id}`} />
            {o.status === "draft" && may("orders.approve") && (
              <StepButton run={orderStep.bind(null, o.id, "confirm")} label="Confirm and reserve stock" done="Stock reserved for this order" variant="primary" />
            )}
            {o.status === "confirmed" && (may("orders.issue") || may("orders.approve")) && (
              <StepButton run={orderStep.bind(null, o.id, "pick")} label="Start picking" done="Picking started; stock allocated" />
            )}
            {(o.status === "draft" ? may("orders.edit") : held && may("orders.approve")) && (
              <StepButton run={orderStep.bind(null, o.id, "cancel")} label="Cancel order" done="Order cancelled" variant="quiet" confirm={{ title: `Cancel ${o.number}?`, body: held ? "Its reserved stock is released." : undefined, danger: true }} />
            )}
          </>
        }
      >
        <OrderStamp status={o.status} /> <span className="ml-1">{ORDER_KINDS[o.kind]} for <strong>{o.recipient}</strong>, from {o.warehouse.name}{o.neededOn && <>, required by {day(o.neededOn)}</>}</span>
      </PageHeader>

      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Created", who: o.createdBy, when: at(o.createdAt) },
          { label: "Confirmed and reserved", who: o.confirmedBy, when: o.confirmedAt ? at(o.confirmedAt) : null },
          { label: "Issued", who: o.issuedBy, when: o.issuedAt ? at(o.issuedAt) : null },
        ]} />
        {o.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{o.notes}</p>}
      </Sheet>

      <Sheet className="mt-5">
        <Table head={["Product", " Quantity", ...(o.status === "draft" ? [" Available now"] : []), ...(o.status === "issued" ? ["Picked from"] : []), " Unit price", " Amount"]}>
          {o.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/inventory/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
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
        <p className="mt-3 text-meta text-eosin">Insufficient stock available for {short.map((l) => l.product.name).join(", ")}. The order cannot be confirmed until stock is available.</p>
      )}

      {held && may("orders.issue") && (
        <Sheet className="mt-6 scroll-mt-6 px-5 pt-4 pb-5" id="issue">
          <SectionTitle icon="issuance">Issue stock</SectionTitle>
          <p className="mb-3 text-meta text-ink-3">Stock is issued from {o.warehouse.name} and the reservation is released.</p>
          <PickForm kind="order" documentId={o.id} lines={pickLines} label="Issue and ship" />
        </Sheet>
      )}
      {o.status === "issued" && may("stock.view") && (
        <p className="mt-4 text-meta"><Link href={`/inventory/movements${query({ q: o.number })}`} className="text-ink hover:underline">View stock movements</Link></p>
      )}
    </>
  );
}

/** The order form's lists, with what's free per product per warehouse ("productId:warehouseId" → units). */
const ORDER_FORM = `${referenceOf("products", "units", "warehouses")} availability`;
type OrderFormData = { reference: Pick<Reference, "products" | "units" | "warehouses">; availability: Record<string, number> };

/** New order with no kind: which one, each with what it's for, as the CRM's Add customer asks the type first. */
export async function NewOrderChooser() {
  const { may } = await context();
  if (!may("orders.create")) return <NoAccess what="creating orders" />;
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/orders", label: "Sales orders" }]} title="New order">
        Select the order type.
      </PageHeader>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {KINDS.map((k) => (
          <Link key={k.kind} href={newHref(k)} className="group flex gap-4 rounded-xl border border-rule bg-sheet px-5 py-4 transition-colors hover:border-ink">
            <span className="grid size-11 shrink-0 place-items-center rounded-lg bg-hema-tint text-sage-deep">
              <Icon name={k.icon} className="size-5" />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-ink group-hover:underline">{k.newLabel}</span>
              <span className="mt-0.5 block text-meta text-ink-3">{k.intro}</span>
            </span>
          </Link>
        ))}
      </div>
    </>
  );
}

export async function NewOrderPage({ params }: { params: Params<{ kind: string }> }) {
  const info = kindBySlug((await params).kind);
  if (!info) notFound();
  const { me, may } = await context();
  if (!may("orders.create")) return <NoAccess what="creating orders" />;
  const crumbs = [{ href: listHref(info), label: info.plural }];
  // What this page needs first; if any is missing, that instead of a form that can't be finished.
  const gate = NeedsFirst({ setup: await loadSetup(), needs: ["warehouse", "stock"], then: newHref(info), title: info.newLabel, doing: `create a ${info.one}`, crumbs, may });
  if (gate) return gate;
  const { reference: ref, availability: available } = await loadQuery<OrderFormData>(`query NewOrder { ${ORDER_FORM} }`, {}, ["reference", "availability"]);
  return (
    <>
      <PageHeader crumbs={crumbs} title={info.newLabel}>
        {info.intro}
      </PageHeader>
      <OrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} available={available} kind={info.kind} />
    </>
  );
}

export async function EditOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("orders.edit")) return <NoAccess what="editing orders" />;
  const { order: o, reference: ref, availability: available } = await loadQuery<OrderFormData & { order: Order }>(
    `query EditOrder($id: String!) { order(id: $id) ${ORDER_FORM} }`,
    { id },
    ["order", "reference", "availability"],
  );
  return (
    <>
      <PageHeader crumbs={[{ href: listHref(kindOf(o.kind)!), label: kindOf(o.kind)!.plural }, { href: `/inventory/orders/${o.id}`, label: o.number }]} title={`Edit ${o.number}`} />
      <OrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} order={o} available={available} kind={o.kind} />
    </>
  );
}

export async function ReservationsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, day } = await context();
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const { page, size, vars } = paging(await searchParams);
  const base = "/inventory/reservations";
  const { reservations: list } = await loadQuery<{ reservations: Paged<Reservation> }>("query Reservations($limit: Int, $offset: Int) { reservations(limit: $limit, offset: $offset) }", vars, ["reservations"]);
  keepInRange(list.items.length, list.total, page, base);
  const rows = list.items;
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/orders", label: "Sales orders" }]} title="Reservations">Stock reserved for open orders: reserved on confirmation and allocated during picking. Reserved stock is not available to other orders.</PageHeader>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="issuance" title="No reservations" />
        ) : (
          <Table head={["Product", "Order", "Recipient", "Warehouse", "Required date", "Status", " Quantity"]} min="52rem">
            {rows.map((r, i) => (
              <tr key={i} className="relative hover:bg-bench/40">
                <Td><Link href={`/inventory/products/${r.product.id}`} className="font-semibold hover:text-ink hover:underline">{r.product.name}</Link></Td>
                <Td><RowLink href={`/inventory/orders/${r.order.id}`}>{r.order.number}</RowLink></Td>
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
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "line" : "lines"} />
    </>
  );
}
