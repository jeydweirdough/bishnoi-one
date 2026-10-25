import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { PageHeader, SectionTitle, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { cache } from "react";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { deleteProduct } from "@/src/modules/inventory/actions/inventory";
import { ProductGallery, SupplierPrices } from "@/src/modules/inventory/components/product-extras";
import { RecordTools } from "@/src/modules/inventory/components/record-tools";
import { CprMark, ExpiryMark, NoAccess, Stamp, StateMark, Table, Td } from "@/src/modules/inventory/components/ui";
import { Barcode, BarList, Card, DetailPanel, InfoCard, InfoSection, Pill, StatCards } from "@/src/modules/inventory/components/detail";
import { Icon } from "@/src/modules/inventory/platform/ui/icons";
import { MOVEMENT_KINDS, PRODUCT_STATUSES, PRODUCT_TYPES, referenceHref, signed } from "@/src/modules/inventory/lib/labels";
import { context, type Params } from "@/src/modules/inventory/lib/page";
import type { Product, Reference } from "@/src/modules/inventory/lib/types";

/** A variant's stock, as a pill. */
function StockPill({ state }: { state: Product["state"] }) {
  if (state === "out") return <Stamp tone="attention">Out of stock</Stamp>;
  if (state === "low") return <Stamp tone="attention">Low</Stamp>;
  return state ? <Stamp tone="done">In stock</Stamp> : null;
}

// The page and its title share one request.
const productPage = cache((id: string) =>
  loadQuery<{ product: Product; reference: Pick<Reference, "suppliers"> }>(
    `query Product($id: String!) { product(id: $id) reference { suppliers { id code name isActive } } }`,
    { id },
    ["product", "reference"],
  ),
);

export async function generateMetadata({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  return { title: (await productPage(id)).product.name };
}

// The extra attributes a product came with (from the product list): its details
// in plain labels, and its prices per unit and per pack as a table. Kept as
// written, so a key we don't know still shows, its label made readable.
const DETAIL_LABELS: Record<string, string> = {
  generic_name: "Generic name",
  dosage_strength: "Strength",
  dosage_form: "Dosage form",
  pack_size: "Pack size",
  count: "Count per pack",
  shelf_life: "Shelf life",
};
const PRICE_LABELS: Record<string, string> = {
  srp: "SRP",
  patient_price: "Patient price",
  doctor_price: "Doctor's price",
  distributor_price: "Distributor price",
  trade_price: "Trade price",
};
/** "dosage_form" → "Dosage form". */
const readable = (key: string) => key.replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase());

function attributesOf(attributes: Record<string, string>, brand?: string, category?: string) {
  const details: [string, string][] = [];
  const prices = new Map<string, { label: string; unit: number | null; pack: number | null }>();
  for (const [key, raw] of Object.entries(attributes ?? {})) {
    const value = String(raw ?? "").trim();
    if (!value) continue;
    // The same as the product's own brand and category: not said twice.
    if ((key === "account" && value === brand) || (key === "category" && category?.toUpperCase().includes(value.toUpperCase()))) continue;
    const price = key.match(/^(.*)_(unit|pack)$/);
    if (price && (PRICE_LABELS[price[1]] || /price|srp/.test(price[1])) && /^-?\d+(\.\d+)?$/.test(value)) {
      // Kept in centavos, as the list gave them.
      const row = prices.get(price[1]) ?? { label: PRICE_LABELS[price[1]] ?? readable(price[1]), unit: null, pack: null };
      row[price[2] as "unit" | "pack"] = Math.round(Number(value));
      prices.set(price[1], row);
      continue;
    }
    details.push([DETAIL_LABELS[key] ?? readable(key), value]);
  }
  const order = Object.keys(DETAIL_LABELS).map((k) => DETAIL_LABELS[k]);
  details.sort((a, b) => (order.indexOf(a[0]) + 1 || 99) - (order.indexOf(b[0]) + 1 || 99));
  const priceOrder = Object.keys(PRICE_LABELS);
  const priceRows = [...prices.entries()].sort((a, b) => (priceOrder.indexOf(a[0]) + 1 || 99) - (priceOrder.indexOf(b[0]) + 1 || 99)).map(([, r]) => r);
  return { details, priceRows };
}

/** Whether a description only says what the fields already do ("Abiraterone 250 mg Tablet"). */
function restates(description: string, said: string[]): boolean {
  const words = (t: string) => t.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  const known = new Set(said.flatMap(words));
  const own = words(description);
  return own.length > 0 && own.every((w) => known.has(w));
}

export default async function ProductPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, fmt, may, at, day } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const { product: p, reference: ref } = await productPage(id);
  const groups = p.variantCount > 0;
  const lv = p.level;
  const { details, priceRows } = attributesOf(p.attributes, p.brand?.name, p.category?.path);

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/inventory/products", label: "Products" }, ...(p.parent ? [{ href: `/inventory/products/${p.parent.id}`, label: p.parent.name }] : [])]}
        title={p.name}
        tools={
          <RecordTools
            what="product"
            name={p.name}
            editHref={may("products.edit") ? `/inventory/products/${p.id}/edit` : undefined}
            remove={may("products.delete") ? deleteProduct.bind(null, p.id) : undefined}
            after="/inventory/products"
            removeNote="Only a product with no transactions can be deleted. A product with stock history is marked discontinued instead."
          />
        }
        actions={
          <>
            {may("stock.view") && <LinkButton href={`/inventory/movements?product=${p.id}`}>Stock movements</LinkButton>}
            {groups && may("products.create") && (
              <LinkButton href={`/inventory/products/new?parent=${p.id}`} icon={<Plus className="size-4" aria-hidden />}>
                Add variant
              </LinkButton>
            )}
            {!groups && may("purchasing.create") && (p.state === "low" || p.state === "out") && p.suggestedOrder > 0 && (
              <LinkButton href={`/inventory/purchase-orders/new?product=${p.id}&quantity=${p.suggestedOrder}`} variant="primary">
                Order {fmt.count(p.suggestedOrder)} more
              </LinkButton>
            )}
          </>
        }
      >
        <span className="mr-2 inline-flex h-6 items-center rounded-md border border-rule-strong px-2.5 align-middle text-meta text-ink-2">
          Code: <span className="ml-1 font-mono">{p.sku}</span>
        </span>
        {[p.category?.path, p.brand?.name].filter(Boolean).join(" · ")}
        {p.status !== "active" && <> · <strong>{PRODUCT_STATUSES[p.status]}</strong></>}
        <span className="ml-2 align-middle">{p.status === "active" && !groups && <StateMark state={p.state} />}</span>
      </PageHeader>

      <DetailPanel
        side={
          <>
            <Card className="p-4">
              <ProductGallery productId={p.id} name={p.name} images={p.images} canEdit={may("products.edit")} />
            </Card>
            <Card className="px-5 py-4">
              <h2 className="mb-3 text-center text-sm font-semibold text-ink">Barcode</h2>
              {p.barcode ? (
                <Barcode value={p.barcode} />
              ) : (
                <p className="text-center text-meta text-ink-3">
                  No barcode.
                  {may("products.edit") && (
                    <>
                      {" "}
                      <Link href={`/inventory/products/${p.id}/edit`} className="text-ink hover:underline">Add barcode</Link>
                    </>
                  )}
                </p>
              )}
            </Card>
          </>
        }
      >
        {groups ? (
          <StatCards
            items={[
              { label: "Variants", value: fmt.count(p.variants.length) },
              { label: "On hand, all variants", value: `${fmt.count(p.variants.reduce((n, v) => n + v.level.onHand, 0))} ${p.unit}` },
              { label: "Value at cost", value: fmt.peso(p.variants.reduce((n, v) => n + v.value, 0)) },
            ]}
          />
        ) : (
          <StatCards
            items={[
              { label: "On hand", value: `${fmt.count(lv.onHand)} ${p.unit}`, note: lv.inTransit ? `${fmt.count(lv.inTransit)} in transit` : undefined },
              { label: "Available", value: fmt.count(lv.available), flag: p.state === "out" || p.state === "low", note: p.state === "out" || p.state === "low" ? `Reorder level ${fmt.count(p.reorderPoint)}` : undefined },
              { label: "Reserved for orders", value: fmt.count(lv.reserved + lv.allocated), note: lv.allocated ? `${fmt.count(lv.allocated)} allocated` : undefined },
            ]}
          />
        )}

        <InfoCard>
          {/* The name, code, category, brand and barcode are in the header and beside it: not said again here. */}
          <InfoSection
            icon="products"
            title="Product details"
            items={[
              ["Type", PRODUCT_TYPES[p.productType]],
              ["Unit", `${p.unitName} (${p.unit})`],
              ["Preferred supplier", p.supplier ? <Link key="supplier" href={`/inventory/suppliers/${p.supplier.id}`} className="hover:text-ink hover:underline">{p.supplier.name}</Link> : null],
              ...(p.variantLabel ? [["Variant", p.variantLabel] as [string, string]] : []),
              ...details,
            ]}
          >
            {p.description && !restates(p.description, [p.name, ...details.map(([, v]) => v)]) && (
              <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{p.description}</p>
            )}
          </InfoSection>
          {(p.cpr.state !== "not_needed" || p.cpr.number) && (
            <InfoSection
              icon="letters"
              title="Product registration"
              action={<CprMark cpr={p.cpr} />}
              items={[
                ["CPR number", p.cpr.number ?? (may("products.edit") ? <Link key="add-cpr" href={`/inventory/products/${p.id}/edit`} className="text-ink hover:underline">Add the CPR number</Link> : "None")],
                ["Valid until", p.cpr.validUntil ? `${day(p.cpr.validUntil)}${p.cpr.daysLeft != null && p.cpr.daysLeft >= 0 ? ` · ${fmt.count(p.cpr.daysLeft)} days left` : ""}` : "Not given"],
              ]}
            />
          )}
          {priceRows.length > 0 && (
            <InfoSection icon="pricing" title="Price list" items={[]}>
              <p className="mt-1 text-meta text-ink-3">As given with the product list, per unit and per pack. Selling and cost prices are below.</p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[22rem] text-sm">
                  <thead>
                    <tr className="border-b border-rule text-left text-meta text-ink-3">
                      <th scope="col" className="py-2 pr-3 font-medium">Price</th>
                      <th scope="col" className="px-3 py-2 text-right font-medium">Per unit ({p.unitName.toLowerCase()})</th>
                      <th scope="col" className="py-2 pl-3 text-right font-medium">Per pack</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-rule">
                    {priceRows.map((r) => (
                      <tr key={r.label}>
                        <th scope="row" className="py-2 pr-3 text-left font-semibold text-ink">{r.label}</th>
                        <td className="px-3 py-2 text-right text-ink-2 tabular-nums">{r.unit === null ? "—" : fmt.peso(r.unit)}</td>
                        <td className="py-2 pl-3 text-right text-ink-2 tabular-nums">{r.pack === null ? "—" : fmt.peso(r.pack)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </InfoSection>
          )}
          <InfoSection
            icon="pricing"
            title="Sales information"
            items={[
              ["Selling price", fmt.peso(p.sellingPrice)],
              ["Cost price", fmt.peso(p.costPrice)],
              [
                "Profit",
                p.sellingPrice > 0 ? (
                  <span key="profit">
                    {fmt.peso(p.sellingPrice - p.costPrice)}
                    <Pill>Margin {Math.round(((p.sellingPrice - p.costPrice) / p.sellingPrice) * 100)}%</Pill>
                  </span>
                ) : null,
              ],
              ["Tax", `${p.taxRateBp / 100}%${p.taxInclusive ? ", included" : ", added"}`],
            ]}
          />
          {!groups && (
            <InfoSection
              icon="stock"
              title="Inventory"
              action={
                may("stock.view") && (
                  <Link href={`/inventory/movements?product=${p.id}`} className="inline-flex items-center gap-1.5 text-meta text-ink hover:underline">
                    <Icon name="history" className="size-3.5" />
                    Movement history
                  </Link>
                )
              }
              items={[
                ["Value at cost", fmt.peso(p.value)],
                ["Damaged", fmt.count(lv.damaged)],
                ["In transit", fmt.count(lv.inTransit)],
                ["Minimum · reorder level · maximum", `${fmt.count(p.minStock)} · ${fmt.count(p.reorderPoint)} · ${p.maxStock == null ? "—" : fmt.count(p.maxStock)}`],
                ["Reorder quantity", fmt.count(p.reorderQty)],
                ["Tracking", [p.trackBatches && "batch", p.trackExpiry && "expiry", p.trackSerials && "serial number"].filter(Boolean).join(", ") || "quantity only"],
                ["Last updated", fmt.whenLabel(p.updatedAt)],
              ]}
            />
          )}
        </InfoCard>

        {/* What each supplier charges: the full width, a row each, and a row to add one. */}
        <Card className="mt-5 px-5 pt-4 pb-4">
          <SectionTitle icon="suppliers">Supplier prices</SectionTitle>
          <SupplierPrices org={me.org} product={p} suppliers={ref.suppliers} canEdit={may("products.edit")} canAddSupplier={may("suppliers.create")} />
        </Card>

        {groups ? (
          <BarList
            title="Variants"
            icon="products"
            action={may("products.create") && <Link href={`/inventory/products/new?parent=${p.id}`} className="text-meta text-ink hover:underline">Add variant</Link>}
            rows={p.variants.map((v) => ({
              key: v.id,
              href: `/inventory/products/${v.id}`,
              name: v.variantLabel ?? v.name,
              sub: `${v.sku} · ${fmt.count(v.level.onHand)} on hand · sells at ${fmt.peso(v.sellingPrice)}`,
              pill: <StockPill state={v.state} />,
              share: v.level.onHand / Math.max(1, ...p.variants.map((x) => x.level.onHand)),
            }))}
            empty="No variants."
          />
        ) : (
          <BarList
            title="Stock by warehouse"
            icon="warehouses"
            rows={p.warehouses.map((w) => ({
              key: w.warehouse.id,
              href: `/inventory/warehouses/${w.warehouse.id}`,
              name: w.warehouse.name,
              sub: [
                `${fmt.count(w.onHand)} on hand`,
                `${fmt.count(w.available)} available`,
                w.reserved + w.allocated ? `${fmt.count(w.reserved + w.allocated)} held` : null,
                w.damaged ? `${fmt.count(w.damaged)} damaged` : null,
                w.inTransit ? `${fmt.count(w.inTransit)} on the way` : null,
              ]
                .filter(Boolean)
                .join(" · "),
              pill: w.onHand > 0 ? <Stamp tone="done">In stock</Stamp> : w.inTransit > 0 ? <Stamp tone="active">In transit</Stamp> : <Stamp tone="muted">Empty</Stamp>,
              share: w.onHand / Math.max(1, lv.onHand),
            }))}
            empty="No stock in any warehouse."
          />
        )}
      </DetailPanel>

      {/* Tracked by batch but nothing received yet: say so, and where batches come from. */}
      {!groups && p.balances.length === 0 && (p.trackBatches || p.trackExpiry) && (
        <Sheet className="mt-5 px-5 pt-4 pb-5">
          <SectionTitle icon="headquarters">Batches and expiry</SectionTitle>
          <p className="text-sm text-ink-2">
            This product is tracked by {[p.trackBatches && "batch number", p.trackExpiry && "expiry date"].filter(Boolean).join(" and ")}, but none is in stock yet.
            Each batch is recorded when stock is received, with its batch number and expiry date, and is issued first-expired, first-out.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <LinkButton href="/inventory/receipts/new" variant="primary" size="sm">
              Receive stock
            </LinkButton>
            <LinkButton href="/inventory/batches" size="sm">
              All batches and expiry
            </LinkButton>
          </div>
        </Sheet>
      )}

      {!groups && p.balances.length > 0 && (
        <Sheet className="mt-5">
          <div className="px-5 pt-4">
            <SectionTitle icon="headquarters">Where it is{p.trackBatches ? ", by batch" : ""}</SectionTitle>
            {p.trackExpiry && <p className="text-meta text-ink-3">Sorted by expiry date, the order stock is issued in (first-expired, first-out).</p>}
          </div>
          <Table head={["Warehouse · location", ...(p.trackBatches ? ["Batch", "Expiry date"] : []), " On hand", " Damaged"]} min="32rem">
            {p.balances.map((b, i) => (
              <tr key={i}>
                <Td>{b.warehouse.code} · {b.location.code} <span className="text-meta text-ink-3">{b.location.name}</span></Td>
                {p.trackBatches && <Td>{b.batch?.batchNo ?? "—"}</Td>}
                {p.trackBatches && <Td>{b.batch?.expiresOn ? <ExpiryMark expiry={b.batch.expiry} label={day(b.batch.expiresOn)} /> : "—"}</Td>}
                <Td num>{fmt.count(b.onHand)}</Td>
                <Td num>{b.damaged ? fmt.count(b.damaged) : "—"}</Td>
              </tr>
            ))}
          </Table>
        </Sheet>
      )}

      {p.recentMovements.length > 0 && (
        <Sheet className="mt-5">
          <div className="px-5 pt-4">
            <SectionTitle icon="history" action={<Link href={`/inventory/movements?product=${p.id}`} className="text-meta text-ink hover:underline">View all</Link>}>
              Recent movements
            </SectionTitle>
          </div>
          <Table head={["Date and time", "Movement type", "Warehouse", "Reference", " Quantity"]} min="36rem">
            {p.recentMovements.map((m) => {
              const href = referenceHref(m.referenceType, m.referenceId);
              return (
                <tr key={m.id}>
                  <Td className="text-meta text-ink-3 whitespace-nowrap">{at(m.at)}</Td>
                  <Td>{MOVEMENT_KINDS[m.kind]}{m.batchNo && <span className="text-meta text-ink-3"> · {m.batchNo}</span>}</Td>
                  <Td>{m.warehouse.code}</Td>
                  <Td>{href ? <Link href={href} className="hover:text-ink hover:underline">{m.reference}</Link> : (m.reference ?? "—")}<span className="block text-meta text-ink-3">{m.user}</span></Td>
                  <Td num className="font-semibold">{signed(m.quantity, fmt.count)}</Td>
                </tr>
              );
            })}
          </Table>
        </Sheet>
      )}
    </>
  );
}
