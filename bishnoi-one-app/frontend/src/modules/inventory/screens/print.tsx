import type { ReactNode } from "react";
import { LetterheadBlock, LetterheadFooter, loadLetterhead } from "@/src/platform/print/letterhead";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { load, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { PrintButton } from "@/src/modules/inventory/components/print-button";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { kindOf } from "@/src/modules/inventory/lib/order-kinds";
import { context, type Params, type Search } from "@/src/modules/inventory/lib/page";
import type { Order, Packing, PO, Receipt, SupplierRow, Transfer, Wave, WarehouseRow } from "@/src/modules/inventory/lib/types";

// Each document on paper, to keep or send as proof: the purchase order to the
// supplier, the goods receipt for a delivery, the issue slip for an order and
// the transfer slip that travels with the stock. Outside the app's frame, so
// only the document prints; the browser's print dialog also saves it as PDF.
// Laid out as the CRM's quotation is: A4, black on white, signatures at the foot.

const caption = "text-[8.5pt] font-semibold tracking-wide text-neutral-600 uppercase";
const paper =
  "mx-auto my-8 max-w-[210mm] bg-white px-[16mm] py-[14mm] text-[10.5pt] leading-snug text-black shadow-sm print:my-0 print:max-w-none print:p-0 print:shadow-none";
const th = "py-1.5 px-2 font-semibold first:pl-0 last:pr-0";
const td = "py-1.5 px-2 first:pl-0 last:pr-0";

type Ctx = Awaited<ReturnType<typeof context>>;

/** The page around a document: back to the record and Print above, the sheet below. */
function Frame({ back, backLabel, auto, children }: { back: string; backLabel: string; auto: boolean; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bench print:bg-white">
      <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-rule bg-sheet px-6 py-3 print:hidden">
        <LinkButton href={back} variant="quiet">
          {backLabel}
        </LinkButton>
        <PrintButton auto={auto} />
      </div>
      <article className={paper}>{children}</article>
    </div>
  );
}

/** The company (its letterhead, from the Platform: step 10), the document's name and number, and its dates. */
async function Head({ ctx, title, number, facts, status }: { ctx: Ctx; title: string; number: string; facts: [string, string][]; status?: string }) {
  const org = ctx.me.org;
  const head = await loadLetterhead();
  return (
    <header className="flex items-start justify-between gap-8 border-b-2 border-black pb-4">
      <LetterheadBlock head={head} fallbackName={org?.brandName || org?.name || ""} />
      <div className="text-right">
        <p className="text-[18pt] font-bold tracking-wide uppercase">{title}</p>
        <p className="font-semibold">No. {number}</p>
        {facts.map(([label, value]) => (
          <p key={label}>
            {label}: {value}
          </p>
        ))}
        {status && <p className="mt-1 inline-block border-2 border-black px-2 text-[9pt] font-bold tracking-wide uppercase">{status}</p>}
      </div>
    </header>
  );
}

/** Who and where, side by side: supplier and delivery address, from and to. */
function Parties({ items }: { items: { label: string; lines: (string | null | undefined)[] }[] }) {
  return (
    <section className={`mt-4 grid gap-8 ${items.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
      {items.map((p) => (
        <div key={p.label}>
          <p className={caption}>{p.label}</p>
          {p.lines.filter(Boolean).map((line, i) => (
            <p key={i} className={i === 0 ? "font-semibold" : "whitespace-pre-line"}>
              {line}
            </p>
          ))}
        </div>
      ))}
    </section>
  );
}

function Notes({ notes }: { notes: string | null }) {
  if (!notes) return null;
  return (
    <section className="mt-6 break-inside-avoid">
      <p className={caption}>Remarks</p>
      <p className="whitespace-pre-line">{notes}</p>
    </section>
  );
}

/** Signature lines: the name printed when the step was taken in the app, and the signature where one was
 *  given in the app (a customer signing for a delivery: step 10). */
function Signatures({ items }: { items: [string, string | null | undefined, ({ image: string; at: string } | null)?][] }) {
  return (
    <section className={`mt-12 grid break-inside-avoid gap-8 ${items.length === 4 ? "grid-cols-4" : "grid-cols-3"}`}>
      {items.map(([role, name, signed]) => (
        <div key={role}>
          <p className="text-[9pt] text-neutral-600">{role}</p>
          <div className="flex h-10 items-end justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {signed && <img src={signed.image} alt={`${name ?? role}'s signature`} className="max-h-10 max-w-full object-contain" />}
          </div>
          <p className="border-t border-black pt-1 text-center font-medium">{name || " "}</p>
          <p className="text-center text-[8.5pt] text-neutral-600">{signed ? `Signed in the app, ${signed.at}` : "Signature over printed name and date"}</p>
        </div>
      ))}
    </section>
  );
}

async function Foot({ ctx, children }: { ctx: Ctx; children?: ReactNode }) {
  const head = await loadLetterhead();
  return (
    <footer className="mt-8 border-t border-neutral-300 pt-2 text-center text-[8.5pt] text-neutral-600">
      <LetterheadFooter head={head} />
      {children}
      {children ? " " : ""}Printed {ctx.at(new Date().toISOString())} by {ctx.me.user.fullName}.
    </footer>
  );
}

/** The product cell: name, then code and unit under it. */
function Product({ name, sku, unit, extra }: { name: string; sku: string; unit: string; extra?: ReactNode }) {
  return (
    <>
      <span className="font-medium">{name}</span>
      <span className="block text-[9pt] text-neutral-600">
        {sku} · {unit}
      </span>
      {extra}
    </>
  );
}

const STATUS: Record<string, string | undefined> = { draft: "Draft, not approved", cancelled: "Cancelled", partial: "Partially received", requested: "Pending approval", confirmed: "Reserved", picking: "Picking", in_transit: "In transit" };

/** The supplier and the warehouse in full, for their addresses; either may be out of this person's reach. */
async function partiesOf(supplierId: string | null | undefined, warehouseIds: string[]) {
  const vars: Record<string, string> = {};
  const fields: string[] = [];
  const types: string[] = [];
  if (supplierId) {
    vars.s = supplierId;
    types.push("$s: String!");
    fields.push("supplier(id: $s)");
  }
  warehouseIds.forEach((id, i) => {
    vars[`w${i}`] = id;
    types.push(`$w${i}: String!`);
    fields.push(`w${i}: warehouse(id: $w${i})`);
  });
  const data = await loadQuery<Record<string, unknown>>(`query Parties(${types.join(", ")}) { ${fields.join(" ")} }`, vars);
  return { supplier: (data.supplier ?? null) as SupplierRow | null, warehouses: warehouseIds.map((_, i) => (data[`w${i}`] ?? null) as WarehouseRow | null) };
}

const contactOf = (s: SupplierRow | null) => (s ? [s.contactPerson && `Attention: ${s.contactPerson}`, [s.phone, s.email].filter(Boolean).join(" · ") || null] : []);

export async function PurchaseOrderPrint({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  const { fmt, may, day } = ctx;
  if (!may("purchasing.view")) return <NoAccess what="purchase orders" />;
  const { po } = await loadQuery<{ po: PO }>(`query PurchaseOrder($id: String!) { po: purchaseOrder(id: $id) }`, { id }, ["po"]);
  const { supplier, warehouses: [warehouse] } = await partiesOf(po.supplier.id, [po.warehouse.id]);
  return (
    <Frame back={`/inventory/purchase-orders/${po.id}`} backLabel="Back to purchase order" auto={s.auto === "1"}>
      <Head
        ctx={ctx}
        title="Purchase order"
        number={po.number}
        facts={[["Order date", day(po.orderedOn ?? po.createdAt.slice(0, 10))], ...(po.expectedOn ? [["Delivery date", day(po.expectedOn)] as [string, string]] : [])]}
        status={STATUS[po.status]}
      />
      <Parties
        items={[
          { label: "Vendor", lines: [po.supplier.name, supplier?.address, ...contactOf(supplier)] },
          { label: "Deliver to", lines: [po.warehouse.name, warehouse?.address] },
          { label: "Terms", lines: [supplier?.paymentTerms ? `Payment: ${supplier.paymentTerms}` : "Payment: as agreed", supplier?.code ? `Vendor code: ${supplier.code}` : null] },
        ]}
      />
      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className={`${th} w-8`}>No.</th>
            <th scope="col" className={th}>Product</th>
            <th scope="col" className={`${th} text-right`}>Quantity</th>
            <th scope="col" className={`${th} text-right`}>Unit cost</th>
            <th scope="col" className={`${th} text-right`}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {po.lines.map((l, i) => (
            <tr key={l.id} className="break-inside-avoid border-b border-neutral-300 align-top">
              <td className={`${td} tabular-nums`}>{i + 1}</td>
              <td className={td}><Product name={l.product.name} sku={l.product.sku} unit={l.product.unit} /></td>
              <td className={`${td} text-right tabular-nums`}>{fmt.count(l.quantity)} {l.product.unit}</td>
              <td className={`${td} text-right tabular-nums`}>{fmt.peso(l.unitCost)}</td>
              <td className={`${td} text-right font-medium tabular-nums`}>{fmt.peso(l.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="mt-3 ml-auto w-[95mm] break-inside-avoid space-y-0.5">
        <p className="flex justify-between">
          <span>Total quantity</span>
          <span className="tabular-nums">{fmt.count(po.ordered)}</span>
        </p>
        <p className="flex justify-between border-t border-black pt-1 text-[12pt] font-bold">
          <span>Total amount</span>
          <span className="tabular-nums">{fmt.peso(po.total)}</span>
        </p>
      </section>
      <Notes notes={po.notes} />
      <Signatures items={[["Prepared by", po.createdBy?.name], ["Approved by", po.orderedBy?.name], ["Conforme (vendor)", ""]]} />
      <Foot ctx={ctx}>Please quote {po.number} on the delivery receipt and invoice.</Foot>
    </Frame>
  );
}

export async function ReceiptPrint({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  const { fmt, may, day, at } = ctx;
  if (!may("receiving.view")) return <NoAccess what="receiving" />;
  const { receipt: r } = await loadQuery<{ receipt: Receipt }>(`query Receipt($id: String!) { receipt(id: $id) }`, { id }, ["receipt"]);
  const { supplier, warehouses: [warehouse] } = await partiesOf(r.supplier?.id, [r.warehouse.id]);
  return (
    <Frame back={`/inventory/receipts/${r.id}`} backLabel="Back to goods receipt" auto={s.auto === "1"}>
      <Head
        ctx={ctx}
        title="Goods receipt"
        number={r.number}
        facts={[["Received", at(r.receivedAt)], ...(r.order ? [["Purchase order", r.order.number] as [string, string]] : []), ...(r.deliveryRef ? [["Delivery ref.", r.deliveryRef] as [string, string]] : [])]}
      />
      <Parties
        items={[
          { label: "Received from", lines: r.supplier ? [r.supplier.name, supplier?.address, ...contactOf(supplier)] : ["No supplier (stock received without a purchase order)"] },
          { label: "Received into", lines: [r.warehouse.name, `Location ${r.location.code} · ${r.location.name}`, warehouse?.address] },
        ]}
      />
      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className={`${th} w-8`}>No.</th>
            <th scope="col" className={th}>Product</th>
            <th scope="col" className={th}>Batch and expiry</th>
            <th scope="col" className={`${th} text-right`}>Quantity</th>
            <th scope="col" className={`${th} text-right`}>Unit cost</th>
            <th scope="col" className={`${th} text-right`}>Amount</th>
          </tr>
        </thead>
        <tbody>
          {r.lines.map((l, i) => (
            <tr key={l.id} className="break-inside-avoid border-b border-neutral-300 align-top">
              <td className={`${td} tabular-nums`}>{i + 1}</td>
              <td className={td}>
                <Product name={l.product.name} sku={l.product.sku} unit={l.product.unit} extra={l.serials.length > 0 && <span className="block font-mono text-[8.5pt]">Serial: {l.serials.join(", ")}</span>} />
              </td>
              <td className={td}>
                {l.batch ? (
                  <>
                    <span className="font-mono">{l.batch.batchNo}</span>
                    {l.batch.expiresOn && <span className="block text-[9pt] text-neutral-600">Expires {day(l.batch.expiresOn)}</span>}
                  </>
                ) : (
                  "—"
                )}
              </td>
              <td className={`${td} text-right tabular-nums`}>{fmt.count(l.quantity)} {l.product.unit}</td>
              <td className={`${td} text-right tabular-nums`}>{fmt.peso(l.unitCost)}</td>
              <td className={`${td} text-right font-medium tabular-nums`}>{fmt.peso(l.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="mt-3 ml-auto w-[95mm] break-inside-avoid space-y-0.5">
        <p className="flex justify-between">
          <span>Total quantity received</span>
          <span className="tabular-nums">{fmt.count(r.units)}</span>
        </p>
        <p className="flex justify-between border-t border-black pt-1 text-[12pt] font-bold">
          <span>Total value</span>
          <span className="tabular-nums">{fmt.peso(r.total)}</span>
        </p>
      </section>
      <Notes notes={r.notes} />
      <Signatures items={[["Delivered by (vendor)", ""], ["Received by", r.receivedBy?.name], ["Checked by", ""]]} />
      <Foot ctx={ctx}>Received in good order and condition unless noted above.</Foot>
    </Frame>
  );
}

export async function OrderPrint({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  const { fmt, may, day, at } = ctx;
  if (!may("orders.view")) return <NoAccess what="orders" />;
  const { order: o } = await loadQuery<{ order: Order }>(`query Order($id: String!) { order(id: $id) }`, { id }, ["order"]);
  const { warehouses: [warehouse] } = await partiesOf(null, [o.warehouse.id]);
  const enclosed = await load<{ name: string; product: { name: string } }[]>(`/inventory/orders/${o.id}/documents`).catch(() => []);
  const info = kindOf(o.kind);
  const priced = Boolean(info?.priced);
  const issued = o.status === "issued";
  return (
    <Frame back={`/inventory/orders/${o.id}`} backLabel="Back to order" auto={s.auto === "1"}>
      <Head
        ctx={ctx}
        title={issued ? "Issue slip" : "Order"}
        number={o.number}
        facts={[
          ["Date", issued && o.issuedAt ? at(o.issuedAt) : day(o.createdAt.slice(0, 10))],
          ...(o.neededOn ? [["Required by", day(o.neededOn)] as [string, string]] : []),
          // Shipping (step 12): how it goes, the courier and its tracking number.
          ...(o.shipping?.method ? [["Ships by", o.shipping.courier?.name ?? o.shipping.methodLabel ?? ""] as [string, string]] : []),
          ...(o.shipping?.trackingNumber ? [["Tracking no.", o.shipping.trackingNumber] as [string, string]] : []),
        ]}
        status={STATUS[o.status]}
      />
      <Parties
        items={[
          { label: info?.recipient.label ?? "Issued to", lines: [o.recipient, info ? `${info.one[0].toUpperCase()}${info.one.slice(1)}` : null] },
          { label: "Issued from", lines: [o.warehouse.name, warehouse?.address] },
        ]}
      />
      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className={`${th} w-8`}>No.</th>
            <th scope="col" className={th}>Product</th>
            {issued && <th scope="col" className={th}>Batch and location</th>}
            <th scope="col" className={`${th} text-right`}>Quantity</th>
            {priced && <th scope="col" className={`${th} text-right`}>Unit price</th>}
            {priced && <th scope="col" className={`${th} text-right`}>Amount</th>}
          </tr>
        </thead>
        <tbody>
          {o.lines.map((l, i) => (
            <tr key={l.id} className="break-inside-avoid border-b border-neutral-300 align-top">
              <td className={`${td} tabular-nums`}>{i + 1}</td>
              <td className={td}>
                <Product name={l.product.name} sku={l.product.sku} unit={l.product.unit} extra={l.serials.length > 0 && <span className="block font-mono text-[8.5pt]">Serial: {l.serials.join(", ")}</span>} />
              </td>
              {issued && (
                <td className={`${td} text-[9pt]`}>
                  {l.picks.map((p, k) => (
                    <span key={k} className="block">
                      {fmt.count(p.quantity)} from {p.locationCode}
                      {p.batchNo && ` · ${p.batchNo}`}
                      {p.expiresOn && ` (exp. ${day(p.expiresOn)})`}
                    </span>
                  ))}
                </td>
              )}
              <td className={`${td} text-right tabular-nums`}>{fmt.count(l.quantity)} {l.product.unit}</td>
              {priced && <td className={`${td} text-right tabular-nums`}>{l.unitPrice ? fmt.peso(l.unitPrice) : "—"}</td>}
              {priced && <td className={`${td} text-right font-medium tabular-nums`}>{l.total ? fmt.peso(l.total) : "—"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      <section className="mt-3 ml-auto w-[95mm] break-inside-avoid space-y-0.5">
        <p className={`flex justify-between ${priced ? "" : "border-t border-black pt-1 font-bold"}`}>
          <span>Total quantity</span>
          <span className="tabular-nums">{fmt.count(o.units)}</span>
        </p>
        {priced && (
          <p className="flex justify-between border-t border-black pt-1 text-[12pt] font-bold">
            <span>Total amount</span>
            <span className="tabular-nums">{fmt.peso(o.total)}</span>
          </p>
        )}
      </section>
      <Notes notes={o.notes} />
      {/* The documents sent with it (step 15e). */}
      {enclosed.length > 0 && <p className="mt-4 text-[9pt]">Enclosed: {enclosed.map((d) => `${d.name} (${d.product.name})`).join("; ")}</p>}
      <Signatures items={[["Prepared by", o.createdBy?.name, null], ["Approved by", o.confirmedBy?.name, null], ["Issued by", o.issuedBy?.name, null], ["Received by", o.received?.name ?? "", o.received?.signature ? { image: o.received.signature, at: ctx.at(o.received.signedAt) } : null]]} />
      <Foot ctx={ctx}>{priced ? "This is not an official receipt or sales invoice." : undefined}</Foot>
    </Frame>
  );
}

export async function TransferPrint({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  const { fmt, may, day, at } = ctx;
  if (!may("transfers.view")) return <NoAccess what="transfers" />;
  const { transfer: t } = await loadQuery<{ transfer: Transfer }>(`query Transfer($id: String!) { transfer(id: $id) }`, { id }, ["transfer"]);
  const { warehouses: [from, to] } = await partiesOf(null, [t.from.id, t.to.id]);
  const sent = t.status === "in_transit" || t.status === "received";
  return (
    <Frame back={`/inventory/transfers/${t.id}`} backLabel="Back to transfer" auto={s.auto === "1"}>
      <Head
        ctx={ctx}
        title="Stock transfer slip"
        number={t.number}
        facts={[
          ["Requested", at(t.requestedAt ?? t.createdAt)],
          ...(t.dispatchedAt ? [["Dispatched", at(t.dispatchedAt)] as [string, string]] : []),
          ...(t.receivedAt ? [["Received", at(t.receivedAt)] as [string, string]] : []),
        ]}
        status={STATUS[t.status]}
      />
      <Parties
        items={[
          { label: "From", lines: [t.from.name, from?.address] },
          { label: "To", lines: [t.to.name, to?.address] },
        ]}
      />
      <table className="mt-5 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className={`${th} w-8`}>No.</th>
            <th scope="col" className={th}>Product</th>
            {sent && <th scope="col" className={th}>Batches dispatched</th>}
            <th scope="col" className={`${th} text-right`}>Quantity</th>
          </tr>
        </thead>
        <tbody>
          {t.lines.map((l, i) => (
            <tr key={l.id} className="break-inside-avoid border-b border-neutral-300 align-top">
              <td className={`${td} tabular-nums`}>{i + 1}</td>
              <td className={td}>
                <Product name={l.product.name} sku={l.product.sku} unit={l.product.unit} extra={l.serials.length > 0 && <span className="block font-mono text-[8.5pt]">Serial: {l.serials.join(", ")}</span>} />
              </td>
              {sent && (
                <td className={`${td} text-[9pt]`}>
                  {l.picks.map((p, k) => (
                    <span key={k} className="block">
                      {fmt.count(p.quantity)}
                      {p.batchNo ? ` · ${p.batchNo}` : ""}
                      {p.expiresOn ? ` (exp. ${day(p.expiresOn)})` : ""}
                    </span>
                  ))}
                </td>
              )}
              <td className={`${td} text-right tabular-nums`}>{fmt.count(l.quantity)} {l.product.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <section className="mt-3 ml-auto w-[95mm] break-inside-avoid">
        <p className="flex justify-between border-t border-black pt-1 font-bold">
          <span>Total quantity</span>
          <span className="tabular-nums">{fmt.count(t.units)}</span>
        </p>
      </section>
      <Notes notes={t.notes} />
      <Signatures items={[["Requested by", (t.requestedBy ?? t.createdBy)?.name], ["Approved by", t.approvedBy?.name], ["Dispatched by", t.dispatchedBy?.name], ["Received by", t.receivedBy?.name]]} />
      <Foot ctx={ctx} />
    </Frame>
  );
}

// --- packages and waves (step 14d) ----------------------------------------------------------

/** A delivery's box labels, one to a page: box number, which of how many, who it's for, the courier and what's inside. */
export async function PackageLabels({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  if (!ctx.may("orders.view")) return <NoAccess what="orders" />;
  const { order: o } = await loadQuery<{ order: Order }>(`query Order($id: String!) { order(id: $id) }`, { id }, ["order"]);
  const packing = await load<Packing>(`/inventory/orders/${encodeURIComponent(id)}/packages`);
  return (
    <Frame back={`/inventory/orders/${o.id}`} backLabel="Back to delivery" auto={s.auto === "1"}>
      {packing.packages.length === 0 && <p className="text-sm">Nothing packed yet.</p>}
      {packing.packages.map((p) => (
        <section key={p.id} className="break-after-page border-2 border-black p-6 last:break-after-auto">
          <p className="text-[10pt] uppercase">Deliver to</p>
          <p className="text-[20pt] leading-tight font-bold">{o.recipient}</p>
          <div className="mt-4 flex items-end justify-between gap-6 border-t border-black pt-3">
            <div>
              <p className="font-mono text-[26pt] font-bold">{p.number}</p>
              <p className="text-[14pt]">Box {p.index} of {p.of}{p.weightGrams ? ` · ${(p.weightGrams / 1000).toLocaleString()} kg` : ""}</p>
            </div>
            <div className="text-right text-[10pt]">
              <p>Delivery <span className="font-mono font-semibold">{o.number}</span></p>
              {o.shipping?.courier && <p>{o.shipping.courier.name}</p>}
              {o.shipping?.trackingNumber && <p className="font-mono font-semibold">{o.shipping.trackingNumber}</p>}
              <p>From {o.warehouse.name}</p>
            </div>
          </div>
          <ul className="mt-4 border-t border-black pt-2 text-[10pt]">
            {p.lines.map((l) => <li key={l.lineId}>{l.quantity} × {l.product.name} <span className="text-neutral-600">({l.product.sku})</span></li>)}
          </ul>
        </section>
      ))}
    </Frame>
  );
}

/** A wave's pick list: each product once, where to take it, and which delivery each part goes to. */
export async function WavePickList({ params, searchParams }: { params: Params<{ id: string }>; searchParams: Search }) {
  const [{ id }, s] = await Promise.all([params, searchParams]);
  const ctx = await context();
  if (!ctx.may("orders.view")) return <NoAccess what="waves" />;
  const w = await load<Wave>(`/inventory/waves/${encodeURIComponent(id)}`);
  return (
    <Frame back={`/inventory/waves/${w.id}`} backLabel="Back to wave" auto={s.auto === "1"}>
      <h1 className="text-[16pt] font-bold">Pick list {w.number}</h1>
      <p className="text-[10pt]">{w.warehouse.name} · {w.orders.length} deliveries ({w.orders.map((o) => o.number).join(", ")}) · {w.units} units</p>
      <table className="mt-4 w-full border-collapse">
        <thead>
          <tr className="border-y border-black text-left text-[9pt]">
            <th scope="col" className={th}>✓</th>
            <th scope="col" className={th}>Take from</th>
            <th scope="col" className={th}>Product</th>
            <th scope="col" className={`${th} text-right`}>Total</th>
            <th scope="col" className={th}>For</th>
          </tr>
        </thead>
        <tbody>
          {w.pickList.map((r) => (
            <tr key={r.product.id} className="break-inside-avoid border-b border-neutral-300 align-top text-[10pt]">
              <td className={td}>☐</td>
              <td className={td}>{r.short > 0 ? "Not enough on hand" : r.from.map((f, i) => <span key={i} className="block font-mono">{f.quantity} · {f.location.code}{f.batch ? ` · ${f.batch.batchNo}` : ""}</span>)}</td>
              <td className={td}>{r.product.name}<span className="block text-[8.5pt] text-neutral-600">{r.product.sku}</span></td>
              <td className={`${td} text-right font-semibold tabular-nums`}>{r.total}</td>
              <td className={td}>{r.orders.map((o) => <span key={o.orderId} className="block">{o.quantity} → {o.number} {o.recipient}</span>)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Frame>
  );
}
