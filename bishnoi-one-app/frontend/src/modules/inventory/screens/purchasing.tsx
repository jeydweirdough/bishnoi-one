import { DocumentHeaderStrip } from "@/src/platform/ui/document-header";
import { HeaderFilters, type OperationTypeRow } from "@/src/modules/inventory/components/document-header";
import { Ban, ExternalLink, FileText, PackageCheck, Pencil, Plus, Printer, Trash2, Truck } from "lucide-react";
import { RowMenu } from "@/src/platform/ui/row-menu";
import { FigureStrip, ListFrame, ListToolbar, StatusPill, UnderlineTabs, type Figure, type PillTone } from "@/src/platform/ui/list-layout";
import { ExpandableTable } from "@/src/platform/ui/expandable-table";

import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { enc, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deletePurchaseOrder, purchaseOrderStep } from "@/src/modules/inventory/actions/inventory";
import { PurchaseOrderForm } from "@/src/modules/inventory/components/document-forms";
import { PrintLink } from "@/src/modules/inventory/components/print-button";
import { ReceiveForm } from "@/src/modules/inventory/components/receive-form";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { POStamp } from "@/src/modules/inventory/components/stamps";
import { StepButton } from "@/src/modules/inventory/components/step-button";
import { Chips, ExpiryMark, Filters, NoAccess, RowLink, Table, Td, Trail } from "@/src/modules/inventory/components/ui";
import { param, query } from "@/src/modules/inventory/lib/labels";
import { FirstStep, NeedsFirst } from "@/src/modules/inventory/components/setup";
import { loadSetup } from "@/src/modules/inventory/lib/setup";
import { ToggleLinks } from "@/src/modules/inventory/platform/ui/toggle-links";
import { PurchaseOrdersBoard } from "@/src/modules/inventory/screens/boards";
import { Pager } from "@/src/modules/inventory/platform/ui/pager";
import { canAddFrom, context, keepInRange, paging, type Params, type Search } from "@/src/modules/inventory/lib/page";
import { given, referenceOf } from "@/src/modules/inventory/lib/reference";
import type { Backorder, Paged, PO, POBrief, Receipt, ReceiptBrief, Reference } from "@/src/modules/inventory/lib/types";

// The purchase order and receiving forms pick from the same lists.
const FORM_LISTS = referenceOf("products", "suppliers", "units", "warehouses");

type POFigures = { pendingCount: number; pendingValue: number; lateCount: number; receivedThisMonth: number; receivedLastMonth: number };

const STATUS_TABS: [string, string][] = [["", "All"], ["draft", "Drafts"], ["ordered,partial", "Pending delivery"], ["partial", "Partially received"], ["received", "Received"], ["cancelled", "Cancelled"]];

/** Where a purchase order stands, as one word. */
function poStanding(po: POBrief): { tone: PillTone; label: string } {
  if (po.status === "cancelled") return { tone: "bad", label: "Cancelled" };
  if (po.status === "received") return { tone: "good", label: "Received" };
  if (po.late) return { tone: "bad", label: "Late" };
  if (po.status === "partial") return { tone: "warn", label: "Partially received" };
  if (po.status === "ordered") return { tone: "info", label: "Ordered" };
  return { tone: "plain", label: "Draft" };
}

/** This month against last, in words: "12% vs last month". */
function change(now: number, before: number): Figure["change"] {
  if (!before) return now ? { text: "New this month", tone: "flat" } : undefined;
  const pct = Math.round(((now - before) / before) * 100);
  return { text: `${Math.abs(pct)}% vs last month`, tone: pct > 0 ? "up" : pct < 0 ? "down" : "flat" };
}

export async function PurchaseOrdersPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status") };
  const board = param(s, "view") !== "list" && !f.status;
  // The board shows every open order in its columns; the list is read a page at a time.
  const { page, size, vars } = paging(s);
  const base = `/inventory/purchase-orders${query({ ...f, view: board ? "" : "list" })}`;
  const { orders: got } = await loadQuery<{ orders: POBrief[] | Paged<POBrief> }>(
    `query PurchaseOrders($q: String, $status: String, $limit: Int, $offset: Int) { orders: purchaseOrders(q: $q, status: $status, limit: $limit, offset: $offset) }`,
    { ...given(f), ...(board ? {} : vars) },
    ["orders"],
  );
  const list: Paged<POBrief> = Array.isArray(got) ? { items: got, total: got.length } : got;
  const figures = board ? null : (await loadQuery<{ purchaseOrderFigures: POFigures }>("query { purchaseOrderFigures }", {}, ["purchaseOrderFigures"])).purchaseOrderFigures;
  if (!board) keepInRange(list.items.length, list.total, page, base);
  const orders = list.items;
  const chip = (status: string, label: string) => ({ value: status, label, href: `/inventory/purchase-orders${query({ q: f.q, status })}` });
  return (
    <>
      <PageHeader
        title="Purchase orders"
        actions={
          <>
            {may("receiving.receive") && <LinkButton href="/inventory/receipts/new">Receive without purchase order</LinkButton>}
            {may("purchasing.create") && <LinkButton href="/inventory/purchase-orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New purchase order</LinkButton>}
          </>
        }
      >
        Purchase order → supplier delivery → goods receipt → stock.
      </PageHeader>
      {board && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <ToggleLinks
            current="board"
            options={[
              { value: "board", label: "Board", href: `/inventory/purchase-orders${query({ ...f, status: "", view: "" })}` },
              { value: "list", label: "List", href: `/inventory/purchase-orders${query({ ...f, view: "list" })}` },
              { value: "backorders", label: "Backorders", href: "/inventory/backorders" },
            ]}
          />
        </div>
      )}
      {board ? (
        <>
          <Filters q={f.q} placeholder="PO number or vendor" keep={{ status: f.status, view: "" }} />
          {orders.length > 0 ? (
            <PurchaseOrdersBoard orders={orders} fmt={fmt} day={day} may={may} />
          ) : (
            <Sheet>
              <FirstStep icon="purchaseOrders" title="No purchase orders" body="Order stock from a vendor. Goods receipts are recorded against the order." needs={["warehouse", "supplier", "product"]} href="/inventory/purchase-orders/new" action="New purchase order" permission="purchasing.create" filtered={Boolean(f.q)} clear="/inventory/purchase-orders" may={may} />
            </Sheet>
          )}
        </>
      ) : (
        <ListFrame>
          {figures && (
            <FigureStrip
              figures={[
                { label: "Pending delivery", value: fmt.peso(figures.pendingValue), icon: <Truck className="size-5" aria-hidden />, change: { text: `${fmt.count(figures.pendingCount)} orders${figures.lateCount ? `, ${fmt.count(figures.lateCount)} late` : ""}`, tone: "flat" } },
                { label: "Received this month", value: fmt.peso(figures.receivedThisMonth), icon: <PackageCheck className="size-5" aria-hidden />, change: change(figures.receivedThisMonth, figures.receivedLastMonth) },
              ]}
            />
          )}
          <UnderlineTabs tabs={STATUS_TABS.map(([value, label]) => ({ href: `/inventory/purchase-orders${query({ q: f.q, status: value, view: "list" })}`, label, current: f.status === value }))} />
          <ListToolbar q={f.q} placeholder="Search PO number or vendor" keep={{ status: f.status, view: "list" }}>
            <ToggleLinks
              current="list"
              options={[
                { value: "board", label: "Board", href: `/inventory/purchase-orders${query({ q: f.q })}` },
                { value: "list", label: "List", href: `/inventory/purchase-orders${query({ ...f, view: "list" })}` },
                { value: "backorders", label: "Backorders", href: "/inventory/backorders" },
              ]}
            />
          </ListToolbar>
          {orders.length === 0 ? (
            <FirstStep icon="purchaseOrders" title="No purchase orders" body="Order stock from a vendor. Goods receipts are recorded against the order." needs={["warehouse", "supplier", "product"]} href="/inventory/purchase-orders/new" action="New purchase order" permission="purchasing.create" filtered={Boolean(f.q || f.status)} clear="/inventory/purchase-orders?view=list" may={may} />
          ) : (
            <ExpandableTable
              minWidth="56rem"
              columns={[
                { key: "order", label: "Order" },
                { key: "supplier", label: "Vendor" },
                { key: "to", label: "Deliver to" },
                { key: "expected", label: "Expected" },
                { key: "received", label: "Received", align: "right" },
                { key: "total", label: "Total", align: "right" },
                { key: "status", label: "Status" },
              ]}
              rows={orders.map((po) => {
                const st = poStanding(po);
                return {
                  id: po.id,
                  muted: po.status === "cancelled",
                  actions: (
                    <RowMenu
                      label={`Actions for ${po.number}`}
                      items={[
                        { label: "Open", icon: <ExternalLink />, href: `/inventory/purchase-orders/${po.id}` },
                        ...(po.status === "draft" && may("purchasing.edit") ? [{ label: "Edit", icon: <Pencil />, href: `/inventory/purchase-orders/${po.id}/edit` }] : []),
                        "divider" as const,
                        ...((po.status === "ordered" || po.status === "partial") && may("receiving.receive")
                          ? [{ label: "Receive delivery", icon: <PackageCheck />, href: `/inventory/purchase-orders/${po.id}#receive` }]
                          : []),
                        { label: "Print", icon: <Printer />, href: `/inventory/print/purchase-orders/${po.id}` },
                        ...((po.status === "draft" || po.status === "ordered") && may("purchasing.approve")
                          ? [
                              "divider" as const,
                              { label: "Cancel order", icon: <Ban />, run: purchaseOrderStep.bind(null, po.id, "cancel" as const), danger: true, confirm: `Cancel ${po.number}? No further receipts can be recorded against it.`, done: "Cancelled" },
                            ]
                          : []),
                        ...(po.status === "draft" && may("purchasing.edit")
                          ? [{ label: "Delete", icon: <Trash2 />, run: deletePurchaseOrder.bind(null, po.id), danger: true, confirm: `Delete ${po.number}? This can't be undone.`, done: `${po.number} deleted` }]
                          : []),
                      ]}
                    />
                  ),
                  cells: [
                    <Link key="n" href={`/inventory/purchase-orders/${po.id}`} className="font-mono text-meta font-semibold text-ink hover:text-sage-deep hover:underline">{po.number}</Link>,
                    <span key="s" className="font-medium text-ink">{po.supplier.name}</span>,
                    <span key="w" className="text-ink-2">{po.warehouse.code}</span>,
                    <span key="e" className={po.late ? "font-medium text-danger" : "text-ink-2"}>{day(po.expectedOn)}</span>,
                    <span key="r">{fmt.count(po.received)} / {fmt.count(po.ordered)}</span>,
                    <span key="t" className="font-medium">{fmt.peso(po.total)}</span>,
                    <StatusPill key="p" tone={st.tone}>{st.label}</StatusPill>,
                  ],
                  detail: (
                    <div className="space-y-3">
                      <table className="w-full text-meta">
                        <thead>
                          <tr className="text-left text-ink-3">
                            <th className="py-1 pr-3 font-medium">SKU</th>
                            <th className="px-3 py-1 font-medium">Item</th>
                            <th className="px-3 py-1 text-right font-medium">Ordered</th>
                            <th className="px-3 py-1 text-right font-medium">Received</th>
                            <th className="px-3 py-1 text-right font-medium">Unit cost</th>
                            <th className="py-1 pl-3 text-right font-medium">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {po.items.map((l) => (
                            <tr key={l.sku} className="border-t border-rule/70">
                              <td className="py-1.5 pr-3 font-mono text-ink-2">{l.sku}</td>
                              <td className="px-3 py-1.5 text-ink">{l.product}</td>
                              <td className="px-3 py-1.5 text-right tabular-nums">{fmt.count(l.quantity)}</td>
                              <td className={`px-3 py-1.5 text-right tabular-nums ${l.received < l.quantity && po.status !== "draft" ? "text-[#8a5a00]" : ""}`}>{fmt.count(l.received)}</td>
                              <td className="px-3 py-1.5 text-right tabular-nums text-ink-2">{fmt.peso(l.unitCost)}</td>
                              <td className="py-1.5 pl-3 text-right font-medium tabular-nums">{fmt.peso(l.quantity * l.unitCost)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-rule/70 pt-3">
                        {/* Deliveries are received on the order's own page, where the receive form is. */}
                        <LinkButton href={`/inventory/purchase-orders/${po.id}`}>{may("receiving.receive") && (po.status === "ordered" || po.status === "partial") ? "Open to receive" : "Open purchase order"}</LinkButton>
                      </div>
                    </div>
                  ),
                };
              })}
            />
          )}
        </ListFrame>
      )}
      {!board && <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "purchase order" : "purchase orders"} />}
    </>
  );
}

export async function PurchaseOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, fmt, may, at, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const { po, reference: ref } = await loadQuery<{ po: PO; reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses"> }>(
    `query PurchaseOrder($id: String!) { po: purchaseOrder(id: $id) ${FORM_LISTS} }`,
    { id },
    ["po", "reference"],
  );
  const open = po.status === "ordered" || po.status === "partial";
  const outstanding = po.lines.reduce((n, l) => n + l.outstanding, 0);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/purchase-orders", label: "Purchase orders" }]}
        title={po.number}
        tools={
          po.status === "draft" && (
            <RecordTools
              what="purchase order"
              name={po.number}
              editHref={may("purchasing.edit") ? `/inventory/purchase-orders/${po.id}/edit` : undefined}
              remove={may("purchasing.edit") ? deletePurchaseOrder.bind(null, po.id) : undefined}
              after="/inventory/purchase-orders"
            />
          )
        }
        actions={
          <>
            <PrintLink href={`/inventory/print/purchase-orders/${po.id}`} />
            {po.status === "draft" && may("purchasing.approve") && (
              <StepButton run={purchaseOrderStep.bind(null, po.id, "place")} label="Approve and place order" done={`${po.number} placed`} variant="primary" confirm={{ title: `Place ${po.number} with ${po.supplier.name}?`, body: "Once placed, it cannot be edited, only received or cancelled.", danger: false }} />
            )}
            {(po.status === "draft" || open) && may("purchasing.approve") && (
              <StepButton
                run={purchaseOrderStep.bind(null, po.id, "cancel")}
                label={po.status === "partial" ? "Close order" : "Cancel order"}
                done={po.status === "partial" ? "Order closed; balance cancelled" : "Cancelled"}
                variant="quiet"
                confirm={{ title: po.status === "partial" ? `Close ${po.number}?` : `Cancel ${po.number}?`, body: po.status === "partial" ? `${outstanding} outstanding units will be cancelled. Received stock is unchanged.` : "No further receipts can be recorded against it.", danger: true }}
              />
            )}
          </>
        }
      >
        <POStamp status={po.status} late={po.late} /> <span className="ml-1">{po.supplier.name} → {po.warehouse.name}</span>
      </PageHeader>

      <Sheet className="px-5 py-4">
        <Trail steps={[
          { label: "Created", who: po.createdBy, when: at(po.createdAt) },
          { label: "Approved and placed", who: po.orderedBy, when: po.orderedOn ? day(po.orderedOn) : null },
          { label: "Expected", who: null, when: po.expectedOn ? day(po.expectedOn) : null },
        ]} />
        {po.notes && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{po.notes}</p>}
      </Sheet>

      <Sheet className="mt-5">
        <Table head={["Product", " Ordered", " Received", " Outstanding", " Unit cost", " Amount"]}>
          {po.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/inventory/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
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
        <section className="mt-6 scroll-mt-6" id="receive">
          <h2 className="mb-3 text-heading">Receive delivery</h2>
          <ReceiveForm org={me.org} reference={ref} order={po} canAdd={canAddFrom(may)} />
        </section>
      )}

      {po.receipts.length > 0 && (
        <Sheet className="mt-6">
          <div className="px-5 pt-4"><SectionTitle icon="receiving">Goods receipts</SectionTitle></div>
          <ReceiptsTable receipts={po.receipts} at={at} count={fmt.count} peso={fmt.peso} />
        </Sheet>
      )}
    </>
  );
}

function ReceiptsTable({ receipts, at, count, peso }: { receipts: ReceiptBrief[]; at: (iso: string | null) => string; count: (n: number) => string; peso: (n: number) => string }) {
  return (
    <Table head={["Receipt", "Received date", "Vendor", "Warehouse", "Order", " Units", " Value", <span key="a" className="sr-only">Actions</span>]} min="52rem">
      {receipts.map((r) => (
        <tr key={r.id} className="relative hover:bg-bench/40">
          <Td><RowLink href={`/inventory/receipts/${r.id}`} sub={r.deliveryRef ?? undefined}>{r.number}</RowLink></Td>
          <Td className="whitespace-nowrap">{at(r.receivedAt)}<span className="block text-meta text-ink-3">{r.receivedBy?.name}</span></Td>
          <Td>{r.supplier?.name ?? "—"}</Td>
          <Td>{r.warehouse.code} · {r.location.code}</Td>
          <Td>{r.order ? <Link href={`/inventory/purchase-orders/${r.order.id}`} className="relative z-10 hover:text-ink hover:underline">{r.order.number}</Link> : "—"}</Td>
          <Td num>{count(r.units)}</Td>
          <Td num>{peso(r.total)}</Td>
          <td className="px-2 py-2 text-right">
            <RowMenu
              label={`Actions for ${r.number}`}
              items={[
                { label: "Open", icon: <ExternalLink />, href: `/inventory/receipts/${r.id}` },
                { label: "Print", icon: <Printer />, href: `/inventory/print/receipts/${r.id}` },
                ...(r.order ? ["divider" as const, { label: "Open purchase order", icon: <FileText />, href: `/inventory/purchase-orders/${r.order.id}` }] : []),
              ]}
            />
          </td>
        </tr>
      ))}
    </Table>
  );
}

export async function NewPurchaseOrderPage({ searchParams }: { searchParams: Search }) {
  const { me, may } = await context();
  if (!may("purchasing.create")) return <NoAccess what="creating purchase orders" />;
  // What this page needs first; if any is missing, that instead of a form that can't be finished.
  const gate = NeedsFirst({ setup: await loadSetup(), needs: ["warehouse", "supplier", "product"], then: "/inventory/purchase-orders/new", title: "New purchase order", doing: "create a purchase order", crumbs: [{ href: "/inventory/purchase-orders", label: "Purchase orders" }], may });
  if (gate) return gate;
  const s = await searchParams;
  const { reference: ref } = await loadQuery<{ reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses"> }>(`query NewPurchaseOrder { ${FORM_LISTS} }`, {}, ["reference"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/purchase-orders", label: "Purchase orders" }]} title="New purchase order" />
      <PurchaseOrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} preset={{ supplierId: param(s, "supplier") || undefined, productId: param(s, "product") || undefined, quantity: param(s, "quantity") || undefined }} />
    </>
  );
}

export async function EditPurchaseOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("purchasing.edit")) return <NoAccess what="editing purchase orders" />;
  const { po, reference: ref } = await loadQuery<{ po: PO; reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses"> }>(
    `query EditPurchaseOrder($id: String!) { po: purchaseOrder(id: $id) ${FORM_LISTS} }`,
    { id },
    ["po", "reference"],
  );
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/purchase-orders", label: "Purchase orders" }, { href: `/inventory/purchase-orders/${po.id}`, label: po.number }]} title={`Edit ${po.number}`} />
      <PurchaseOrderForm canAdd={canAddFrom(may)} org={me.org} reference={ref} order={po} />
    </>
  );
}

export async function ReceiptsPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, at } = await context();
  if (!may("receiving.view")) return <NoAccess what="receiving" />;
  const s = await searchParams;
  const q = param(s, "q");
  const h = { operationType: param(s, "operationType"), timing: param(s, "timing") };
  const { page, size, vars } = paging(s);
  const base = `/inventory/receipts${query({ q, ...h })}`;
  const { receipts: list, operationTypes } = await loadQuery<{ receipts: Paged<ReceiptBrief>; operationTypes: OperationTypeRow[] }>(
    `query Receipts($q: String, $operationType: String, $timing: String, $limit: Int, $offset: Int) { receipts(q: $q, operationType: $operationType, timing: $timing, limit: $limit, offset: $offset) operationTypes }`,
    { ...given({ q, ...h }), ...vars },
    ["receipts", "operationTypes"],
  );
  keepInRange(list.items.length, list.total, page, base);
  const receipts = list.items;
  return (
    <>
      <PageHeader
        title="Purchase receives"
        actions={may("receiving.receive") && <LinkButton href="/inventory/receipts/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>Receive stock</LinkButton>}
      >
        All goods receipts. To receive against a purchase order, open the order.
      </PageHeader>
      <Filters q={q} placeholder="Receipt or delivery number">
        <HeaderFilters types={operationTypes} kinds={["receipt", "return"]} operationType={h.operationType} timing={h.timing} />
      </Filters>
      <Sheet>
        {receipts.length === 0 ? <FirstStep icon="receiving" title="No purchase receives" body="Stock is received through a goods receipt, with or without a purchase order." needs={["warehouse", "product"]} href="/inventory/receipts/new" action="Receive stock" permission="receiving.receive" filtered={Boolean(q)} clear="/inventory/receipts" may={may} /> : <ReceiptsTable receipts={receipts} at={at} count={fmt.count} peso={fmt.peso} />}
      </Sheet>
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "goods receipt" : "goods receipts"} />
    </>
  );
}

export async function ReceiptPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("receiving.view")) return <NoAccess what="receiving" />;
  const { receipt: r } = await loadQuery<{ receipt: Receipt }>(`query Receipt($id: String!) { receipt(id: $id) }`, { id }, ["receipt"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/receipts", label: "Purchase receives" }]} title={r.number} actions={<><PrintLink href={`/inventory/print/receipts/${r.id}`} />{may("stock.view") && <LinkButton href={`/inventory/movements?q=${enc(r.number)}`}>View stock movements</LinkButton>}</>}>
        Received {at(r.receivedAt)} by {r.receivedBy?.name ?? "—"} into {r.warehouse.name} · {r.location.code}
        {r.supplier && <> from {r.supplier.name}</>}
        {r.order && <> against <Link href={`/inventory/purchase-orders/${r.order.id}`} className="text-ink hover:underline">{r.order.number}</Link></>}
        {r.deliveryRef && <> · delivery {r.deliveryRef}</>}
      </PageHeader>
      <DocumentHeaderStrip header={r.header} source={r.order && <Link href={`/inventory/purchase-orders/${r.order.id}`} className="hover:underline">{r.order.number}</Link>} />
      <Sheet>
        <Table head={["Product", "Batch", "Expires", "Serial numbers", " Quantity", " Unit cost", " Amount"]} min="52rem">
          {r.lines.map((l) => (
            <tr key={l.id} className="relative hover:bg-bench/40">
              <Td><RowLink href={`/inventory/products/${l.product.id}`} sub={l.product.sku}>{l.product.name}</RowLink></Td>
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

export async function NewReceiptPage({ searchParams }: { searchParams: Search }) {
  const productId = param(await searchParams, "product");
  const { me, may } = await context();
  if (!may("receiving.receive")) return <NoAccess what="receiving stock" />;
  // What this page needs first; if any is missing, that instead of a form that can't be finished.
  const gate = NeedsFirst({ setup: await loadSetup(), needs: ["warehouse", "product"], then: "/inventory/receipts/new", title: "Receive stock", doing: "receive stock", crumbs: [{ href: "/inventory/receipts", label: "Purchase receives" }], may });
  if (gate) return gate;
  const { reference: ref } = await loadQuery<{ reference: Pick<Reference, "products" | "suppliers" | "units" | "warehouses"> }>(`query NewReceipt { ${FORM_LISTS} }`, {}, ["reference"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/receipts", label: "Purchase receives" }]} title="Receive stock">
        For deliveries without a purchase order, such as donations, returns or found stock. To receive against a purchase order, open the order.
      </PageHeader>
      <ReceiveForm org={me.org} reference={ref} canAdd={canAddFrom(may)} productId={productId} />
    </>
  );
}

export async function BackordersPage({ searchParams }: { searchParams: Search }) {
  const { me, fmt, may, day } = await context();
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const { page, size, vars } = paging(await searchParams);
  const base = "/inventory/backorders";
  const { backorders: list } = await loadQuery<{ backorders: Paged<Backorder> }>("query Backorders($limit: Int, $offset: Int) { backorders(limit: $limit, offset: $offset) }", vars, ["backorders"]);
  keepInRange(list.items.length, list.total, page, base);
  const rows = list.items;
  return (
    <>
      <PageHeader title="Backorders">Outstanding quantities on placed purchase orders, earliest expected date first.</PageHeader>
      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="purchaseOrders" title="No backorders" />
        ) : (
          <Table head={["Product", "Order", "Vendor", "Expected", " Ordered", " Received", " Outstanding", " Value"]} min="56rem">
            {rows.map((b, i) => (
              <tr key={i} className="relative hover:bg-bench/40">
                <Td><Link href={`/inventory/products/${b.product.id}`} className="font-semibold hover:text-ink hover:underline">{b.product.name}</Link><span className="block text-meta text-ink-3">{b.product.sku}</span></Td>
                <Td><RowLink href={`/inventory/purchase-orders/${b.order.id}`}>{b.order.number}</RowLink></Td>
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
      <Pager total={list.total} page={page} size={size} base={base} noun={list.total === 1 ? "line" : "lines"} />
    </>
  );
}
