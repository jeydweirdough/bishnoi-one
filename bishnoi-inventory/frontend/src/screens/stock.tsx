import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { Chips, ExpiryMark, FilterSelect, Filters, NoAccess, RowLink, StateMark, Table, Td } from "../components/ui";
import { MOVEMENT_FILTERS, MOVEMENT_KINDS, param, query, referenceHref, signed } from "../lib/labels";
import { context, type Search } from "../lib/page";
import { given, referenceOf } from "../lib/reference";
import type { BatchRow, Movement, Page, Reference, SerialRow, StockOverview } from "../lib/types";

const warehouseOptions = (ref: Pick<Reference, "warehouses">) => [{ value: "", label: "Every warehouse" }, ...ref.warehouses.map((w) => ({ value: w.id, label: w.name }))];

export async function StockPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may } = await context();
  if (!may("stock.view")) return <NoAccess what="stock levels" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), warehouse: param(s, "warehouse"), category: param(s, "category"), state: param(s, "state") };
  const { stock: data, reference: ref } = await loadQuery<{ stock: StockOverview; reference: Pick<Reference, "warehouses" | "categories"> }>(
    `query Stock($q: String, $warehouse: String, $category: String, $state: String) { stock(q: $q, warehouse: $warehouse, category: $category, state: $state) ${referenceOf("warehouses", "categories")} }`,
    given(f),
    ["stock", "reference"],
  );
  const t = data.total;
  const chip = (state: string, label: string) => ({ value: state, label, href: `/stock${query({ ...f, state })}` });

  return (
    <>
      <PageHeader
        title="Stock"
        actions={may("counts.create") && <LinkButton href="/counts">Count stock</LinkButton>}
      >
        How much you have, where. Available is what&apos;s on hand, less damaged stock and what orders hold.
      </PageHeader>
      <Chips label="Stock" current={f.state} options={[chip("", "Everything"), chip("low", "Low"), chip("out", "Out of stock"), chip("over", "Over maximum")]} />
      <Filters q={f.q} placeholder="Product, SKU or barcode" keep={{ state: f.state }}>
        <FilterSelect name="warehouse" label="Warehouse" value={f.warehouse} options={warehouseOptions(ref)} />
        <FilterSelect name="category" label="Category" value={f.category} options={[{ value: "", label: "Every category" }, ...ref.categories.map((c) => ({ value: c.id, label: c.path }))]} />
      </Filters>
      <Sheet>
        {data.items.length === 0 ? (
          <Empty icon="stock" title="Nothing here">
            Stock shows up once it&apos;s received into a warehouse.
          </Empty>
        ) : (
          <Table head={["Item", "Warehouse", " On hand", " Damaged", " Reserved", " Picking", " Available", " In transit", " Reorder at", "Stock"]} min="64rem">
            {data.items.map((r) => (
              <tr key={`${r.product.id}-${r.warehouse.id}`} className="relative hover:bg-bench/40">
                <Td><RowLink href={`/products/${r.product.id}`} sub={r.product.sku}>{r.product.name}</RowLink></Td>
                <Td>{r.warehouse.name}</Td>
                <Td num>{fmt.count(r.onHand)}</Td>
                <Td num className="text-ink-3">{r.damaged ? fmt.count(r.damaged) : "—"}</Td>
                <Td num className="text-ink-3">{r.reserved ? fmt.count(r.reserved) : "—"}</Td>
                <Td num className="text-ink-3">{r.allocated ? fmt.count(r.allocated) : "—"}</Td>
                <Td num className="font-semibold">{fmt.count(r.available)}</Td>
                <Td num className="text-ink-3">{r.inTransit ? fmt.count(r.inTransit) : "—"}</Td>
                <Td num className="text-ink-3">{fmt.count(r.reorderPoint)}</Td>
                <Td><StateMark state={r.state} /></Td>
              </tr>
            ))}
            <tr className="border-t-2 border-rule-strong font-semibold">
              <Td>Total</Td>
              <Td className="text-meta font-normal text-ink-3">{fmt.peso(t.value)} at cost</Td>
              <Td num>{fmt.count(t.onHand)}</Td>
              <Td num>{fmt.count(t.damaged)}</Td>
              <Td num>{fmt.count(t.reserved)}</Td>
              <Td num>{fmt.count(t.allocated)}</Td>
              <Td num>{fmt.count(t.available)}</Td>
              <Td num>{fmt.count(t.inTransit)}</Td>
              <Td>{""}</Td>
              <Td>{""}</Td>
            </tr>
          </Table>
        )}
      </Sheet>
      <p className="mt-3 text-meta text-ink-3">Low is judged on a product as a whole, against its reorder point; a row is out when nothing is free in that warehouse.</p>
    </>
  );
}

export async function MovementsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, at } = await context();
  if (!may("stock.view")) return <NoAccess what="the movement trail" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), product: param(s, "product"), warehouse: param(s, "warehouse"), kind: param(s, "kind"), from: param(s, "from"), to: param(s, "to") };
  const before = param(s, "before");
  // The product named in the filter comes with the page; the whole product list doesn't.
  const { page, reference: ref, product } = await loadQuery<{ page: Page<Movement>; reference: Pick<Reference, "warehouses">; product?: { id: string; name: string; sku: string } | null }>(
    `query Movements($q: String, $product: String, $warehouse: String, $kind: String, $from: String, $to: String, $before: Int, $productId: String!, $named: Boolean!) {
      page: movements(q: $q, product: $product, warehouse: $warehouse, kind: $kind, from: $from, to: $to, before: $before, limit: 50)
      ${referenceOf("warehouses")}
      product(id: $productId) @include(if: $named)
    }`,
    { ...given(f), ...(before ? { before: Number(before) } : {}), productId: f.product, named: Boolean(f.product) },
    ["page", "reference"],
  );
  const last = page.items.at(-1);

  return (
    <>
      <PageHeader title="Stock movements">
        The trail: every change to stock, who made it, and the document behind it. Newest first.
      </PageHeader>
      <Chips label="Kind" current={f.kind} options={MOVEMENT_FILTERS.map((k) => ({ value: k.key, label: k.label, href: `/movements${query({ ...f, kind: k.key })}` }))} />
      <Filters q={f.q} placeholder="Product, SKU or reference" keep={{ kind: f.kind, product: f.product }}>
        <FilterSelect name="warehouse" label="Warehouse" value={f.warehouse} options={warehouseOptions(ref)} />
        <label className="block">
          <span className="mb-1 block text-meta font-medium text-ink-2">From</span>
          <input type="date" name="from" defaultValue={f.from} className="h-9 border-0 border-b border-control bg-transparent text-sm" />
        </label>
        <label className="block">
          <span className="mb-1 block text-meta font-medium text-ink-2">To</span>
          <input type="date" name="to" defaultValue={f.to} className="h-9 border-0 border-b border-control bg-transparent text-sm" />
        </label>
      </Filters>
      {product && (
        <p className="mb-3 text-sm text-ink-2">
          Only <Link href={`/products/${product.id}`} className="font-semibold text-hema hover:underline">{product.name}</Link>.{" "}
          <Link href={`/movements${query({ ...f, product: "" })}`} className="text-meta text-hema hover:underline">Show every product</Link>
        </p>
      )}
      <Sheet>
        {page.items.length === 0 ? (
          <Empty icon="history" title={before ? "Nothing older" : "No movements match"} />
        ) : (
          <Table head={["When", "Item", "Action", "Warehouse", "Reference", "By", " Quantity", " On hand after"]} min="60rem">
            {page.items.map((m) => {
              const href = referenceHref(m.referenceType, m.referenceId);
              return (
                <tr key={m.id}>
                  <Td className="text-meta whitespace-nowrap text-ink-3 tabular-nums">{at(m.at)}</Td>
                  <Td>
                    <Link href={`/products/${m.product.id}`} className="font-semibold hover:text-hema hover:underline">{m.product.name}</Link>
                    <span className="block text-meta text-ink-3">
                      {m.product.sku}
                      {m.batch && <> · batch {m.batch.batchNo}</>}
                      {m.serials.length > 0 && <> · {m.serials.join(", ")}</>}
                    </span>
                  </Td>
                  <Td>
                    {MOVEMENT_KINDS[m.kind]}
                    {m.note && <span className="block text-meta text-ink-3">{m.note}</span>}
                  </Td>
                  <Td>{m.warehouse.code}{m.location && <span className="text-meta text-ink-3"> · {m.location.code}</span>}</Td>
                  <Td>{href ? <Link href={href} className="text-hema hover:underline">{m.reference}</Link> : (m.reference ?? "—")}</Td>
                  <Td className="text-ink-2">{m.user}</Td>
                  <Td num className={`font-semibold ${m.quantity > 0 ? "text-hema" : ""}`}>{signed(m.quantity, fmt.count)}</Td>
                  <Td num className="text-ink-3">{m.onHandAfter == null ? "—" : fmt.count(m.onHandAfter)}</Td>
                </tr>
              );
            })}
          </Table>
        )}
      </Sheet>
      {(page.more || before) && (
        <div className="mt-4 flex gap-2">
          {before && <LinkButton href={`/movements${query(f)}`} size="sm" variant="quiet">Newest</LinkButton>}
          {page.more && last && <LinkButton href={`/movements${query({ ...f, before: last.id })}`} size="sm">Older</LinkButton>}
        </div>
      )}
    </>
  );
}

export async function BatchesPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, day } = await context();
  if (!may("stock.view")) return <NoAccess what="batches" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), warehouse: param(s, "warehouse"), expiry: param(s, "expiry"), empty: param(s, "empty") };
  const { batches, reference: ref } = await loadQuery<{ batches: BatchRow[]; reference: Pick<Reference, "warehouses"> }>(
    `query Batches($q: String, $warehouse: String, $expiry: String, $empty: Boolean) { batches(q: $q, warehouse: $warehouse, expiry: $expiry, empty: $empty) ${referenceOf("warehouses")} }`,
    given({ ...f, empty: Boolean(f.empty) }),
    ["batches", "reference"],
  );
  const chip = (expiry: string, label: string) => ({ value: expiry, label, href: `/batches${query({ ...f, expiry })}` });

  return (
    <>
      <PageHeader
        title="Batches & expiry"
        actions={may("adjustments.create") && <LinkButton href="/adjustments/new?reason=expired">Write off expired stock</LinkButton>}
      >
        Every lot on hand, soonest to expire first: the order stock goes out in (first expired, first out).
      </PageHeader>
      <Chips label="Expiry" current={f.expiry} options={[chip("", "Everything"), chip("expired", "Expired"), chip("expiring", "Expiring soon"), chip("ok", "Good")]} />
      <Filters q={f.q} placeholder="Batch number or product" keep={{ expiry: f.expiry }}>
        <FilterSelect name="warehouse" label="Warehouse" value={f.warehouse} options={warehouseOptions(ref)} />
        <FilterSelect name="empty" label="Show" value={f.empty} options={[{ value: "", label: "Batches with stock" }, { value: "true", label: "Used-up batches too" }]} />
      </Filters>
      <Sheet>
        {batches.length === 0 ? (
          <Empty icon="calendar" title="No batches match">Batches are recorded as stock of batch-tracked products is received.</Empty>
        ) : (
          <Table head={["Batch", "Item", "Expires", " Days left", "Where", " On hand", " Value"]} min="52rem">
            {batches.map((b) => (
              <tr key={b.id} className="relative hover:bg-bench/40">
                <Td><span className="font-mono font-semibold">{b.batchNo}</span>{b.manufacturedOn && <span className="block text-meta text-ink-3">Made {day(b.manufacturedOn)}</span>}</Td>
                <Td><RowLink href={`/products/${b.product.id}`} sub={b.product.sku}>{b.product.name}</RowLink></Td>
                <Td>{b.expiresOn ? <ExpiryMark expiry={b.expiry} label={day(b.expiresOn)} /> : <span className="text-ink-3">Doesn&apos;t expire</span>}</Td>
                <Td num className={b.daysLeft != null && b.daysLeft < 0 ? "font-semibold text-eosin" : "text-ink-2"}>{b.daysLeft == null ? "—" : fmt.count(b.daysLeft)}</Td>
                <Td className="text-meta text-ink-2">{b.warehouses.map((w) => `${w.code} ${fmt.count(w.onHand)}`).join(" · ") || "—"}</Td>
                <Td num className="font-semibold">{fmt.count(b.onHand)}{b.damaged > 0 && <span className="block text-meta font-normal text-ink-3">{fmt.count(b.damaged)} damaged</span>}</Td>
                <Td num>{fmt.peso(b.value)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Sheet>
    </>
  );
}

const SERIAL_STATUS = { in_stock: "In stock", in_transit: "In transit", issued: "Issued", written_off: "Written off" } as const;

export async function SerialsPage({ searchParams }: { searchParams: Search }) {
  const { may, at } = await context();
  if (!may("stock.view")) return <NoAccess what="serial numbers" />;
  const q = param(await searchParams, "q");
  const units = q ? (await loadQuery<{ serials: SerialRow[] }>(`query Serials($q: String!) { serials(q: $q) }`, { q }, ["serials"])).serials : [];
  return (
    <>
      <PageHeader title="Serial numbers">Find a serial-numbered unit: where it is now, and everywhere it has been.</PageHeader>
      <Filters q={q} placeholder="Serial number, or part of one" />
      {!q ? (
        <Sheet><Empty icon="stock" title="Type a serial number to find it" /></Sheet>
      ) : units.length === 0 ? (
        <Sheet><Empty icon="stock" title="No unit has that serial number" /></Sheet>
      ) : (
        <div className="space-y-4">
          {units.map((u) => (
            <Sheet key={u.id} className="px-5 pt-4 pb-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-heading"><span className="font-mono">{u.serialNo}</span> <span className="text-ink-2">· {u.product.name}</span></h2>
                <span className="text-sm font-semibold">{SERIAL_STATUS[u.status]}{u.warehouse && ` · ${u.warehouse.name}${u.location ? `, ${u.location.code}` : ""}`}</span>
              </div>
              <ul className="mt-2 divide-y divide-rule text-sm">
                {u.history.map((m) => {
                  const href = referenceHref(m.referenceType, m.referenceId);
                  return (
                    <li key={m.id} className="flex flex-wrap justify-between gap-2 py-2">
                      <span>{MOVEMENT_KINDS[m.kind]} · {m.warehouse.code} · {href ? <Link href={href} className="text-hema hover:underline">{m.reference}</Link> : m.reference}</span>
                      <span className="text-meta text-ink-3">{at(m.at)} · {m.user}</span>
                    </li>
                  );
                })}
              </ul>
            </Sheet>
          ))}
        </div>
      )}
    </>
  );
}
