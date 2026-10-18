import { FirstStep } from "../components/setup";
import { Plus } from "lucide-react";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { FilterSelect, Filters, NoAccess, RowLink, StateMark, Table, Td } from "../components/ui";
import { Pager } from "@/src/platform/ui/pager";
import { PRODUCT_STATUSES, param, query } from "../lib/labels";
import { context, keepInRange, paging, type Search } from "../lib/page";
import { given, referenceOf } from "../lib/reference";
import type { Paged, ProductRow, Reference } from "../lib/types";

export const metadata = { title: "Products" };

export default async function ProductsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, may, me } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), category: param(s, "category"), brand: param(s, "brand"), supplier: param(s, "supplier"), status: param(s, "status") || "active", stock: param(s, "stock"), missing: param(s, "missing") };
  const { page, size, vars } = paging(s);
  const base = `/products${query(f)}`;
  const { products: list, reference: ref } = await loadQuery<{ products: Paged<ProductRow>; reference: Pick<Reference, "categories" | "brands" | "suppliers"> }>(
    `query Products($q: String, $category: String, $brand: String, $supplier: String, $status: String, $stock: String, $missing: Boolean, $limit: Int, $offset: Int) {
      products(q: $q, category: $category, brand: $brand, supplier: $supplier, status: $status, stock: $stock, missing: $missing, limit: $limit, offset: $offset)
      ${referenceOf("categories", "brands", "suppliers")}
    }`,
    { ...given({ ...f, missing: Boolean(f.missing) }), ...vars },
    ["products", "reference"],
  );
  keepInRange(list.items.length, list.total, page, base);
  const products = list.items;
  // Variants sit under their product, so the catalogue reads Product → 1 mL, 3 mL, 5 mL.
  const ids = new Set(products.map((p) => p.id));
  const tops = products.filter((p) => !p.parentId || !ids.has(p.parentId));
  const under = (id: string) => products.filter((p) => p.parentId === id);

  const row = (p: ProductRow, nested = false) => (
    <tr key={p.id} className="relative hover:bg-bench/40">
      <Td>
        <div className={nested ? "pl-5" : ""}>
          <RowLink href={`/products/${p.id}`} sub={[p.sku, p.category?.path, p.brand?.name].filter(Boolean).join(" · ")}>
            {nested && p.variantLabel ? `↳ ${p.variantLabel}` : p.name}
          </RowLink>
        </div>
      </Td>
      <Td num>{p.variantCount ? <span className="text-ink-3">{p.variantCount} variants</span> : `${fmt.count(p.level.onHand)} ${p.unit}`}</Td>
      <Td num>{p.variantCount ? "" : fmt.count(p.level.available)}</Td>
      <Td num>{p.variantCount ? "" : fmt.count(p.reorderPoint)}</Td>
      <Td num>{fmt.peso(p.costPrice)}</Td>
      <Td num>{fmt.peso(p.sellingPrice)}</Td>
      <Td>{p.status === "active" ? <StateMark state={p.state} /> : <span className="text-meta text-ink-3">{PRODUCT_STATUSES[p.status]}</span>}</Td>
    </tr>
  );

  return (
    <>
      <PageHeader
        title="Products"
        actions={
          may("products.create") && (
            <LinkButton href="/products/new" variant="primary" icon={<Plus className="size-4" aria-hidden />}>
              Add product
            </LinkButton>
          )
        }
      >
        Product catalog with costs, selling prices and reorder levels.
      </PageHeader>
      <Filters q={f.q} placeholder="Name, SKU or barcode">
        <FilterSelect name="category" label="Category" value={f.category} options={[{ value: "", label: "All categories" }, ...ref.categories.map((c) => ({ value: c.id, label: c.path }))]} />
        <FilterSelect name="brand" label="Brand" value={f.brand} options={[{ value: "", label: "All brands" }, ...ref.brands.map((b) => ({ value: b.id, label: b.name }))]} />
        <FilterSelect name="supplier" label="Supplier" value={f.supplier} options={[{ value: "", label: "All suppliers" }, ...ref.suppliers.map((x) => ({ value: x.id, label: x.name }))]} />
        <FilterSelect name="stock" label="Stock" value={f.stock} options={[{ value: "", label: "Any" }, { value: "low", label: "Low" }, { value: "out", label: "Out of stock" }, { value: "over", label: "Over maximum" }]} />
        {/* The same list as the sidebar's red count on Products. */}
        <FilterSelect name="missing" label="Prices" value={f.missing} options={[{ value: "", label: "Any" }, { value: "true", label: "Missing price" }]} />
        <FilterSelect name="status" label="Status" value={f.status} options={[{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }, { value: "discontinued", label: "Discontinued" }, { value: "all", label: "All" }]} />
      </Filters>
      <Sheet>
        {products.length === 0 ? (
          <FirstStep icon="products" title="No products" body="Add stocked items with their SKU, unit and reorder level." href="/products/new" action="Add product" permission="products.create" filtered={Boolean(f.q || f.category || f.brand || f.supplier || f.stock || f.missing || f.status !== "active")} clear="/products" may={may} />
        ) : (
          <Table head={["Product", " On hand", " Available", " Reorder level", " Unit cost", " Selling price", "Stock"]} min="52rem">
            {tops.flatMap((p) => [row(p), ...under(p.id).map((v) => row(v, true))])}
          </Table>
        )}
      </Sheet>
      <Pager total={list.total} page={page} size={size} base={base} noun={`product${list.total === 1 ? "" : "s"}${f.q ? ` matching “${f.q}”` : ""}`} />
    </>
  );
}
