import { PageHeader } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { ProductForm } from "../components/product-form";
import { NoAccess } from "../components/ui";
import { context, type Params, type Search } from "../lib/page";
import type { Product, ProductRow, Reference } from "../lib/types";

// Adding a product, and changing one: the same form.

async function parentsAndReference() {
  const [ref, all] = await Promise.all([load<Reference>("/inventory/reference"), load<ProductRow[]>("/inventory/products?status=all")]);
  // Only a product that isn't itself a variant can have variants.
  const parents = all.filter((p) => !p.parentId).map((p) => ({ id: p.id, name: p.name, sku: p.sku }));
  return { ref, parents };
}

export async function NewProductPage({ searchParams }: { searchParams: Search }) {
  const { me, may } = await context();
  if (!may("products.create")) return <NoAccess what="adding products" />;
  const { parent } = await searchParams;
  const { ref, parents } = await parentsAndReference();
  return (
    <>
      <PageHeader crumbs={[{ href: "/products", label: "Products" }]} title="Add a product">
        Its code and name, what it costs, when to reorder, and how it&apos;s tracked. Stock comes in by receiving it.
      </PageHeader>
      <ProductForm org={me.org} reference={ref} parents={parents} locked={false} preset={{ parentId: typeof parent === "string" ? parent : undefined }} />
    </>
  );
}

export async function EditProductPage({ params }: { params: Params<{ id: string }> }) {
  const { id } = await params;
  const { me, may } = await context();
  if (!may("products.edit")) return <NoAccess what="changing products" />;
  const [product, { ref, parents }] = await Promise.all([load<Product>(`/inventory/products/${enc(id)}`), parentsAndReference()]);
  // Tracking and unit are fixed once stock has moved (the API says so too).
  const locked = product.recentMovements.length > 0;
  return (
    <>
      <PageHeader crumbs={[{ href: "/products", label: "Products" }, { href: `/products/${product.id}`, label: product.name }]} title={`Edit ${product.name}`} />
      <ProductForm key={product.updatedAt} org={me.org} reference={ref} product={product} parents={parents} locked={locked} />
    </>
  );
}
