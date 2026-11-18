import Link from "next/link";
import { Plus } from "lucide-react";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { load, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess, Table, Td } from "@/src/modules/inventory/components/ui";
import { referenceOf } from "@/src/modules/inventory/lib/reference";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import type { Reference } from "@/src/modules/inventory/lib/types";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { SalesOrderForm, SalesOrderSteps } from "./components";
import { SaleDocuments } from "@/src/modules/inventory/components/supply";
import type { ProductDocument } from "@/src/modules/inventory/lib/types";
import type { SalesOrder, SalesOrderBrief, SalesStatus } from "./types";

// The Sales app's screens (feature plan step 11): sales orders, made from approved CRM quotes or typed here at the
// price list's prices; each waits for approval, and approving makes its delivery in Inventory.

const one = (v: string | string[] | undefined) => (typeof v === "string" ? v : "");
const STATUSES: { value: "" | SalesStatus; label: string }[] = [
  { value: "", label: "All" },
  { value: "pending", label: "Waiting for approval" },
  { value: "draft", label: "Drafts" },
  { value: "confirmed", label: "Confirmed" },
  { value: "delivered", label: "Delivered" },
  { value: "rejected", label: "Rejected" },
];

const TONE: Record<SalesStatus, string> = {
  draft: "border-ink-3 text-ink-3", pending: "border-due-today text-due-today", confirmed: "border-hema text-hema",
  delivered: "border-sage-deep text-sage-deep", rejected: "border-danger text-danger", cancelled: "border-ink-3 text-ink-3",
};

function Stamp({ status, label, invoiceState }: { status: SalesStatus; label: string; invoiceState?: SalesOrderBrief["invoiceState"] }) {
  // Once invoiced the invoice's state shows (Step 4D): a voided invoice waits for its reissue.
  const tone = invoiceState === "voided" ? "border-due-today text-due-today" : invoiceState ? "border-sage-deep text-sage-deep" : TONE[status];
  return <span className={`inline-flex h-5 items-center rounded-full border px-2 text-stamp whitespace-nowrap uppercase ${tone}`}>{label}</span>;
}

export async function SalesOrdersPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, day } = await context();
  if (!may("sales.view")) return <NoAccess what="sales orders" />;
  const s = await searchParams;
  const status = one(s.status);
  const q = one(s.q);
  const params = new URLSearchParams({ ...(status && { status }), ...(q && { q }) });
  const orders = await load<SalesOrderBrief[]>(`/inventory/sales-orders?${params}`);
  return (
    <>
      <PageHeader
        title="Sales orders"
        tools={<ToggleLinks current={status} options={STATUSES.map((x) => ({ value: x.value, label: x.label, href: x.value ? `/crm/sales?status=${x.value}` : "/crm/sales" }))} />}
        actions={may("sales.create") && <LinkButton href="/crm/sales/orders/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>New sales order</LinkButton>}
      >
        Orders from approved quotes in the CRM, and orders taken here. Each waits for approval; approving it makes its delivery.
      </PageHeader>
      <Sheet>
        {orders.length === 0 ? (
          <Empty
            icon="issuance"
            title={status ? "Nothing here" : "No sales orders yet"}
            source="The CRM: Raise order on an approved quote makes its sales order here. Orders taken by phone are added with New sales order."
          />
        ) : (
          <Table head={["Order", "Customer", "Salesperson", "Status", "Scheduled", " Total"]} min="48rem">
            {orders.map((o) => (
              <tr key={o.id} className="relative hover:bg-bench/40">
                <Td>
                  <Link href={`/crm/sales/orders/${o.id}`} className="font-semibold text-ink hover:underline after:absolute after:inset-0">
                    {o.number}
                  </Link>
                  {o.quote && <span className="block text-meta text-ink-3">from {o.quote.number}</span>}
                </Td>
                <Td>{o.customer.name}</Td>
                <Td>
                  {o.salesperson?.name ?? "—"}
                  {o.division && <span className="block text-meta text-ink-3">{[o.division, o.team].filter(Boolean).join(" › ")}</span>}
                </Td>
                <Td><Stamp status={o.status} label={o.statusLabel} invoiceState={o.invoiceState} /></Td>
                <Td>{day(o.scheduledOn)}</Td>
                <Td num>{fmt.peso(o.totalCentavos)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

export async function SalesOrderPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { fmt, may, at, day } = await context();
  if (!may("sales.view")) return <NoAccess what="sales orders" />;
  const o = await load<SalesOrder>(`/inventory/sales-orders/${encodeURIComponent(id)}`);
  const docs = await load<(ProductDocument & { product: { name: string } })[]>(`/inventory/sales-orders/${encodeURIComponent(id)}/documents`);
  // The lines as ordered keep the order's own totals; the invoice's figures show above them once invoiced (Step 4D).
  const own = o.ordered ?? { discountCentavos: o.discountCentavos, totalCentavos: o.totalCentavos };
  return (
    <>
      <PageHeader
        crumbs={[{ href: "/crm/sales", label: "Sales orders" }]}
        title={o.number}
        actions={<SalesOrderSteps order={o} may={{ create: may("sales.create"), edit: may("sales.edit"), approve: may("sales.approve") }} />}
      >
        <Stamp status={o.status} label={o.statusLabel} invoiceState={o.invoiceState} /> <span className="ml-1">for <strong>{o.customer.name}</strong>, from {o.warehouse.name}{o.scheduledOn && <>, due {day(o.scheduledOn)}</>}</span>
      </PageHeader>
      {o.status === "rejected" && o.decisionNote && (
        <p className="mb-4 rounded-[3px] bg-danger-tint px-4 py-2 text-sm text-ink">
          Rejected by {o.decidedBy?.name ?? "an approver"}: {o.decisionNote}
        </p>
      )}
      {o.invoiceState === "voided" && o.invoice && (
        <p className="mb-4 rounded-[3px] bg-promo-tint px-4 py-2 text-sm text-ink">
          Invoice {o.invoice.number} was voided{o.invoice.voidReason ? `: ${o.invoice.voidReason}` : ""}. The order&apos;s own amounts show until Finance issues its replacement.
        </p>
      )}
      <div className="mb-5 grid gap-5 lg:grid-cols-3">
        <Sheet className="px-5 py-4">
          <p className="text-caps text-ink-3 uppercase">Customer</p>
          <p className="font-semibold text-ink">{o.customer.name}</p>
          {o.customer.address && <p className="text-sm text-ink-2">{o.customer.address}</p>}
          {o.customer.tin && <p className="text-sm text-ink-2">TIN {o.customer.tin}</p>}
          {o.payer?.kind === "guarantee_letter" && <p className="mt-1 text-meta text-ink-3">Paid by guarantee letter: {o.payer.issuer} {o.payer.letterNumber}</p>}
        </Sheet>
        <Sheet className="px-5 py-4">
          <p className="text-caps text-ink-3 uppercase">Sale</p>
          <p className="text-sm text-ink">{o.salesperson?.name ?? "No salesperson"}</p>
          {(o.division || o.team) && <p className="text-meta text-ink-3">{[o.division, o.team].filter(Boolean).join(" › ")}</p>}
          {o.quote && <p className="mt-1 text-meta text-ink-3">From quote {o.quote.number}</p>}
          <p className="text-meta text-ink-3">Made {at(o.createdAt)}{o.createdBy ? ` by ${o.createdBy}` : ""}</p>
        </Sheet>
        <Sheet className="px-5 py-4">
          <p className="text-caps text-ink-3 uppercase">Delivery</p>
          {o.deliveries.length === 0 ? (
            <p className="text-sm text-ink-3">{o.status === "pending" ? "Made when the order is approved." : "None yet."}</p>
          ) : (
            o.deliveries.map((d) => (
              <p key={d.id} className="text-sm">
                <Link href={`/inventory/orders/${d.id}`} className="font-semibold text-hema hover:underline">{d.number}</Link>{" "}
                <span className="text-ink-3">· {d.shipping?.statusLabel ?? (d.status === "issued" ? `issued ${at(d.issuedAt)}` : d.status)}</span>
                {/* The courier and its tracking (step 12). */}
                {d.shipping?.trackingNumber && (
                  <span className="block text-meta text-ink-3">
                    {d.shipping.courier?.name ?? "Courier"}{" "}
                    {d.shipping.trackingUrl ? <a href={d.shipping.trackingUrl} target="_blank" rel="noreferrer" className="text-hema hover:underline">{d.shipping.trackingNumber}</a> : d.shipping.trackingNumber}
                  </span>
                )}
              </p>
            ))
          )}
          {o.decidedBy && o.status !== "rejected" && <p className="mt-1 text-meta text-ink-3">Approved by {o.decidedBy.name}, {at(o.decidedAt)}</p>}
          {/* Invoiced by Finance from the delivery, and paid (step 13). */}
          {o.invoice ? (
            <p className="mt-2 text-sm">
              <Link href={`/finance/invoices/${o.invoice.id}`} className="font-semibold text-hema hover:underline">{o.invoice.number ?? "Invoice"}</Link>{" "}
              <span className="text-ink-3">· {o.invoice.paidAt ? `paid ${at(o.invoice.paidAt)}` : `invoiced ${at(o.invoice.invoicedAt)}`}</span>
            </p>
          ) : o.status === "delivered" ? (
            <p className="mt-2 text-meta text-ink-3">Finance invoices it from the delivery.</p>
          ) : null}
        </Sheet>
      </div>
      {/* The purchase orders it raised (15b), and the documents to send with it (15e). */}
      {(o.purchaseOrders ?? []).length > 0 || docs.length > 0 ? (
        <Sheet className="mb-5 space-y-3 px-5 py-4">
          {(o.purchaseOrders ?? []).length > 0 && (
            <p className="text-sm">
              <span className="text-ink-3">Ordered for it (not enough stock): </span>
              {o.purchaseOrders!.map((po, i) => (
                <span key={po.id}>
                  {i > 0 && ", "}
                  <Link href={`/inventory/purchase-orders/${po.id}`} className="font-semibold text-hema hover:underline">{po.number}</Link>
                  <span className="text-ink-3"> ({po.supplier}, {po.status})</span>
                </span>
              ))}
            </p>
          )}
          <SaleDocuments documents={docs} send={{ kind: "sales-orders", id: o.id }} />
        </Sheet>
      ) : null}
      {o.amountsFrom === "invoice" && o.invoice && <InvoiceAmounts order={o} peso={fmt.peso} count={fmt.count} />}
      <Sheet>
        {o.amountsFrom === "invoice" && <p className="px-5 pt-4 text-caps text-ink-3 uppercase">As ordered</p>}
        <Table head={["Product", " Quantity", " Free", " Unit price", " Discount", " Amount", " Delivered"]} min="48rem">
          {o.lines.map((l) => (
            <tr key={l.id}>
              <Td>
                <span className="font-medium">{l.product.name}</span>
                <span className="block text-meta text-ink-3">{l.product.sku} · {l.product.unit}</span>
              </Td>
              {/* In the base unit, with the unit sold (step 4A): "2 Boxes of 10". */}
              <Td num>{fmt.count(l.quantity)}{l.unit?.soldAs && <span className="block text-meta text-ink-3">{l.unit.soldAs}</span>}</Td>
              <Td num>{l.freeQuantity ? fmt.count(l.freeQuantity) : "—"}</Td>
              <Td num>{fmt.peso(l.unitPrice)}</Td>
              <Td num>{l.discount ? fmt.peso(l.discount) : "—"}</Td>
              <Td num>{fmt.peso(l.total)}</Td>
              <Td num>{fmt.count(l.delivered)}</Td>
            </tr>
          ))}
          <tr className="border-t-2 border-rule-strong font-semibold">
            <Td>Total</Td><Td num>{fmt.count(o.units)}</Td><Td>{""}</Td><Td>{""}</Td><Td num>{own.discountCentavos ? fmt.peso(own.discountCentavos) : "—"}</Td>
            <Td num>{fmt.peso(own.totalCentavos)}</Td><Td>{""}</Td>
          </tr>
        </Table>
      </Sheet>
      {o.notes && <p className="mt-4 text-sm whitespace-pre-line text-ink-2">{o.notes}</p>}
    </>
  );
}

export async function NewSalesOrderPage() {
  const { me, may } = await context();
  if (!may("sales.create")) return <NoAccess what="creating sales orders" />;
  const { reference: ref } = await loadQuery<{ reference: Pick<Reference, "products" | "warehouses"> }>(`query NewSalesOrder { ${referenceOf("products", "warehouses")} }`, {}, ["reference"]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/crm/sales", label: "Sales orders" }]} title="New sales order">
        For an order taken by phone or in person. Prices are the price list&apos;s; anything else goes through a quote in the CRM. It waits for approval.
      </PageHeader>
      <SalesOrderForm org={me.org} reference={ref} />
    </>
  );
}

/** Once invoiced, the invoice is the order's source of truth (Step 4D): its figures and lines, read only. To change
 *  them, Finance voids and reissues the invoice. */
function InvoiceAmounts({ order: o, peso, count }: { order: SalesOrder; peso: (v: number) => string; count: (v: number) => string }) {
  const inv = o.invoice!;
  const figures: [string, number | null | undefined][] = [
    ["Gross", o.grossCentavos], ["Discount", o.discountCentavos], ["VAT", o.taxCentavos], ["Total", o.totalCentavos],
  ];
  const lines = inv.lines ?? [];
  return (
    <Sheet className="mb-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-5 pt-4">
        <p className="text-sm">
          Amounts from invoice{" "}
          <Link href={`/finance/invoices/${inv.id}`} className="font-semibold text-hema hover:underline">{inv.number ?? "Invoice"}</Link>
        </p>
        <p className="text-meta text-ink-3">Read only: Finance voids and reissues the invoice to change them.</p>
      </div>
      <dl className="grid grid-cols-2 gap-4 px-5 py-4 sm:grid-cols-4">
        {figures.map(([label, value]) => (
          <div key={label}>
            <dt className="text-caps text-ink-3 uppercase">{label}</dt>
            <dd className={`tabular-nums ${label === "Total" ? "font-semibold text-ink" : "text-ink-2"}`}>{value == null ? "—" : label === "Discount" && !value ? "—" : peso(value)}</dd>
          </div>
        ))}
      </dl>
      {lines.length > 0 && (
        <Table head={["Invoice line", " Quantity", " Unit price", " Discount", " VAT", " Amount"]} min="40rem">
          {lines.map((l, i) => (
            <tr key={i}>
              <Td>
                <span className="font-medium">{l.description}</span>
                {l.ref && <span className="block text-meta text-ink-3">{l.ref}</span>}
              </Td>
              <Td num>{count(l.quantity)}</Td>
              <Td num>{peso(l.unitPriceCentavos)}</Td>
              <Td num>{l.discountCentavos ? peso(l.discountCentavos) : "—"}</Td>
              <Td num>{peso(l.taxCentavos)}</Td>
              <Td num>{peso(l.totalCentavos)}</Td>
            </tr>
          ))}
        </Table>
      )}
    </Sheet>
  );
}
