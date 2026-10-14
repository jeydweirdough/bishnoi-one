import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { cache } from "react";
import { loadQuery } from "@/src/platform/lib/api";
import { deleteProduct } from "../actions/inventory";
import { ProductImages, SupplierPrices } from "../components/product-extras";
import { RecordTools } from "../components/record-tools";
import { ExpiryMark, NoAccess, Stamp, StateMark, Table, Td } from "../components/ui";
import { Barcode, BarList, Card, DetailPanel, InfoCard, InfoSection, Pill, StatCards } from "../components/detail";
import { Icon } from "@/src/platform/ui/icons";
import { MOVEMENT_KINDS, PRODUCT_STATUSES, PRODUCT_TYPES, referenceHref, signed } from "../lib/labels";
import { context, type Params } from "../lib/page";
import type { Product, Reference } from "../lib/types";

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

export default async function ProductPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, fmt, may, at, day } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const { product: p, reference: ref } = await productPage(id);
  const groups = p.variantCount > 0;
  const lv = p.level;

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/products", label: "Products" }, ...(p.parent ? [{ href: `/products/${p.parent.id}`, label: p.parent.name }] : [])]}
        title={p.name}
        tools={
          <RecordTools
            what="product"
            name={p.name}
            editHref={may("products.edit") ? `/products/${p.id}/edit` : undefined}
            remove={may("products.delete") ? deleteProduct.bind(null, p.id) : undefined}
            after="/products"
            removeNote="Only a product with no transactions can be deleted. A product with stock history is marked discontinued instead."
          />
        }
        actions={
          <>
            {may("stock.view") && <LinkButton href={`/movements?product=${p.id}`}>Stock movements</LinkButton>}
            {groups && may("products.create") && (
              <LinkButton href={`/products/new?parent=${p.id}`} icon={<Plus className="size-4" aria-hidden />}>
                Add variant
              </LinkButton>
            )}
            {!groups && may("purchasing.create") && (p.state === "low" || p.state === "out") && p.suggestedOrder > 0 && (
              <LinkButton href={`/purchase-orders/new?product=${p.id}&quantity=${p.suggestedOrder}`} variant="primary">
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
              <div className="grid aspect-square place-items-center overflow-hidden rounded-xl bg-bench">
                {p.images[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element -- served through our own route, sized by the box
                  <img src={`/products/${p.id}/images/${p.images[0]}`} alt={p.name} className="size-full object-contain" />
                ) : (
                  <span className="flex flex-col items-center gap-2 text-ink-3">
                    <Icon name="picture" className="size-12" />
                    <span className="text-meta">No image</span>
                  </span>
                )}
              </div>
              <div className="mt-3">
                <ProductImages productId={p.id} images={p.images} canEdit={may("products.edit")} />
              </div>
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
                      <Link href={`/products/${p.id}/edit`} className="text-ink hover:underline">Add barcode</Link>
                    </>
                  )}
                </p>
              )}
            </Card>
            <Card className="px-5 pt-4 pb-4">
              <SectionTitle icon="suppliers">Supplier prices</SectionTitle>
              <div className="mt-2">
                <SupplierPrices org={me.org} product={p} suppliers={ref.suppliers} canEdit={may("products.edit")} canAddSupplier={may("suppliers.create")} />
              </div>
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
          <InfoSection
            icon="info"
            title="Basic information"
            items={[
              ["Product name", p.name],
              ["Type", PRODUCT_TYPES[p.productType]],
              ["SKU", <span key="sku" className="font-mono">{p.sku}</span>],
              ["Barcode", p.barcode],
              ["Category", p.category?.path],
              ["Brand", p.brand?.name],
              ["Preferred supplier", p.supplier ? <Link key="supplier" href={`/suppliers/${p.supplier.id}`} className="hover:text-ink hover:underline">{p.supplier.name}</Link> : null],
              ["Unit", `${p.unitName} (${p.unit})`],
              ...(p.variantLabel ? [["Variant", p.variantLabel] as [string, string]] : []),
              ...Object.entries(p.attributes),
            ]}
          >
            {p.description && <p className="mt-3 text-sm whitespace-pre-line text-ink-2">{p.description}</p>}
          </InfoSection>
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
                  <Link href={`/movements?product=${p.id}`} className="inline-flex items-center gap-1.5 text-meta text-ink hover:underline">
                    <Icon name="history" className="size-3.5" />
                    Movement history
                  </Link>
                )
              }
              items={[
                ["On hand", `${fmt.count(lv.onHand)} ${p.unit}`],
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

        {groups ? (
          <BarList
            title="Variants"
            icon="products"
            action={may("products.create") && <Link href={`/products/new?parent=${p.id}`} className="text-meta text-ink hover:underline">Add variant</Link>}
            rows={p.variants.map((v) => ({
              key: v.id,
              href: `/products/${v.id}`,
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
              href: `/warehouses/${w.warehouse.id}`,
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
            <SectionTitle icon="history" action={<Link href={`/movements?product=${p.id}`} className="text-meta text-ink hover:underline">View all</Link>}>
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
