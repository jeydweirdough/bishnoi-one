import { Plus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { deleteProduct } from "../actions/inventory";
import { ProductImages, SupplierPrices } from "../components/product-extras";
import { RecordTools } from "../components/record-tools";
import { ExpiryMark, Figures, NoAccess, StateMark, Table, Td } from "../components/ui";
import { MOVEMENT_KINDS, PRODUCT_STATUSES, PRODUCT_TYPES, referenceHref, signed } from "../lib/labels";
import { context, type Params } from "../lib/page";
import type { Product, Reference } from "../lib/types";

export async function generateMetadata({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  return { title: (await load<Product>(`/inventory/products/${enc(id)}`)).name };
}

export default async function ProductPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, fmt, may, at, day } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const [p, ref] = await Promise.all([load<Product>(`/inventory/products/${enc(id)}`), load<Reference>("/inventory/reference")]);
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
            removeNote="Only a product nothing has happened to can be deleted. One with stock history is marked discontinued instead."
          />
        }
        actions={
          <>
            {may("stock.view") && <LinkButton href={`/movements?product=${p.id}`}>Movements</LinkButton>}
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
        <span className="font-mono text-meta">{p.sku}</span>
        {p.category && <> · {p.category.path}</>}
        {p.brand && <> · {p.brand.name}</>}
        {p.status !== "active" && <> · <strong>{PRODUCT_STATUSES[p.status]}</strong></>}
        <span className="ml-2 align-middle">{p.status === "active" && <StateMark state={p.state} />}</span>
      </PageHeader>

      {!groups && (
        <Figures
          items={[
            { label: "On hand", value: `${fmt.count(lv.onHand)} ${p.unit}` },
            { label: "Available", value: fmt.count(lv.available), flag: p.state === "out" || p.state === "low" },
            { label: "Reserved / picking", value: `${fmt.count(lv.reserved)} / ${fmt.count(lv.allocated)}` },
            { label: "Damaged", value: fmt.count(lv.damaged) },
            { label: "In transit", value: fmt.count(lv.inTransit) },
            { label: "Value at cost", value: fmt.peso(p.value) },
          ]}
        />
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="min-w-0 space-y-5">
          {groups && (
            <Sheet>
              <div className="px-5 pt-4">
                <SectionTitle icon="products">Variants</SectionTitle>
              </div>
              <Table head={["Variant", " On hand", " Available", " Cost", " Selling", "Stock"]}>
                {p.variants.map((v) => (
                  <tr key={v.id} className="relative hover:bg-bench/40">
                    <Td>
                      <Link href={`/products/${v.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">{v.variantLabel ?? v.name}</Link>
                      <span className="block text-meta text-ink-3">{v.sku}</span>
                    </Td>
                    <Td num>{fmt.count(v.level.onHand)}</Td>
                    <Td num>{fmt.count(v.level.available)}</Td>
                    <Td num>{fmt.peso(v.costPrice)}</Td>
                    <Td num>{fmt.peso(v.sellingPrice)}</Td>
                    <Td><StateMark state={v.state} /></Td>
                  </tr>
                ))}
              </Table>
            </Sheet>
          )}

          {!groups && (
            <Sheet>
              <div className="px-5 pt-4">
                <SectionTitle icon="warehouses">By warehouse</SectionTitle>
              </div>
              {p.warehouses.length === 0 ? (
                <p className="px-5 pb-4 text-meta text-ink-3">None anywhere yet.</p>
              ) : (
                <Table head={["Warehouse", " On hand", " Damaged", " Reserved", " Picking", " Available", " In transit"]} min="36rem">
                  {p.warehouses.map((w) => (
                    <tr key={w.warehouse.id}>
                      <Td><Link href={`/warehouses/${w.warehouse.id}`} className="font-semibold hover:text-hema hover:underline">{w.warehouse.name}</Link></Td>
                      <Td num>{fmt.count(w.onHand)}</Td>
                      <Td num>{fmt.count(w.damaged)}</Td>
                      <Td num>{fmt.count(w.reserved)}</Td>
                      <Td num>{fmt.count(w.allocated)}</Td>
                      <Td num className="font-semibold">{fmt.count(w.available)}</Td>
                      <Td num>{fmt.count(w.inTransit)}</Td>
                    </tr>
                  ))}
                </Table>
              )}
            </Sheet>
          )}

          {!groups && p.balances.length > 0 && (
            <Sheet>
              <div className="px-5 pt-4">
                <SectionTitle icon="headquarters">Where it is{p.trackBatches ? ", by batch" : ""}</SectionTitle>
                {p.trackExpiry && <p className="text-meta text-ink-3">Soonest to expire first: the order it goes out in.</p>}
              </div>
              <Table head={["Warehouse · location", ...(p.trackBatches ? ["Batch", "Expires"] : []), " On hand", " Damaged"]} min="32rem">
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
            <Sheet>
              <div className="px-5 pt-4">
                <SectionTitle icon="history" action={<Link href={`/movements?product=${p.id}`} className="text-meta text-hema hover:underline">All of them</Link>}>
                  Recent movements
                </SectionTitle>
              </div>
              <Table head={["When", "Action", "Warehouse", "Reference", " Quantity"]} min="36rem">
                {p.recentMovements.map((m) => {
                  const href = referenceHref(m.referenceType, m.referenceId);
                  return (
                    <tr key={m.id}>
                      <Td className="text-meta text-ink-3 whitespace-nowrap">{at(m.at)}</Td>
                      <Td>{MOVEMENT_KINDS[m.kind]}{m.batchNo && <span className="text-meta text-ink-3"> · {m.batchNo}</span>}</Td>
                      <Td>{m.warehouse.code}</Td>
                      <Td>{href ? <Link href={href} className="hover:text-hema hover:underline">{m.reference}</Link> : (m.reference ?? "—")}<span className="block text-meta text-ink-3">{m.user}</span></Td>
                      <Td num className="font-semibold">{signed(m.quantity, fmt.count)}</Td>
                    </tr>
                  );
                })}
              </Table>
            </Sheet>
          )}
        </div>

        <div className="min-w-0 space-y-5">
          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="particulars">Particulars</SectionTitle>
            <div className="mt-3">
              <Particulars
                items={[
                  ["Type", PRODUCT_TYPES[p.productType]],
                  ["Unit", `${p.unitName} (${p.unit})`],
                  ["Barcode", p.barcode],
                  ["Cost price", fmt.peso(p.costPrice)],
                  ["Selling price", fmt.peso(p.sellingPrice)],
                  ["Tax", `${p.taxRateBp / 100}%${p.taxInclusive ? ", included" : ", added"}`],
                  ["Usual supplier", p.supplier ? <Link href={`/suppliers/${p.supplier.id}`} className="hover:text-hema hover:underline">{p.supplier.name}</Link> : null],
                  ["Min · reorder · max", `${fmt.count(p.minStock)} · ${fmt.count(p.reorderPoint)} · ${p.maxStock == null ? "—" : fmt.count(p.maxStock)}`],
                  ["Reorder quantity", fmt.count(p.reorderQty)],
                  ["Tracked by", [p.trackBatches && "batch", p.trackExpiry && "expiry", p.trackSerials && "serial number"].filter(Boolean).join(", ") || "quantity only"],
                  ...(p.variantLabel ? [["Variant", p.variantLabel] as [string, string]] : []),
                  ...Object.entries(p.attributes),
                ]}
              />
            </div>
            {p.description && <p className="mt-4 text-sm whitespace-pre-line text-ink-2">{p.description}</p>}
            <p className="mt-4 text-meta text-ink-3">Last changed {fmt.whenLabel(p.updatedAt).toLowerCase()}.</p>
          </Sheet>

          <Sheet className="px-5 pt-4 pb-5">
            <SectionTitle icon="company">Pictures</SectionTitle>
            <div className="mt-3">
              <ProductImages productId={p.id} images={p.images} canEdit={may("products.edit")} />
            </div>
          </Sheet>

          <Sheet className="px-5 pt-4 pb-4">
            <SectionTitle icon="suppliers">Supplier prices</SectionTitle>
            <div className="mt-2">
              <SupplierPrices org={me.org} product={p} suppliers={ref.suppliers} canEdit={may("products.edit")} canAddSupplier={may("suppliers.create")} />
            </div>
          </Sheet>
        </div>
      </div>
    </>
  );
}
