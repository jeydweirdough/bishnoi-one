import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { loadQuery } from "@/src/platform/lib/api";
import { CatalogList, type CatalogItem } from "../components/catalog-list";
import { NoAccess } from "../components/ui";
import { context } from "../lib/page";
import type { BrandRow, CategoryRow, UnitRow } from "../lib/types";

// The catalog's short lists: categories, brands, units of measure.

async function page(kind: "categories" | "brands" | "units", title: string, blurb: string, items: (raw: unknown) => CatalogItem[]) {
  const { me, may } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const raw = (await loadQuery<Record<string, unknown>>(`query Catalog { ${kind} }`, {}, [kind]))[kind];
  return (
    <>
      <PageHeader title={title}>{blurb}</PageHeader>
      <Sheet className="max-w-3xl">
        <CatalogList kind={kind} items={items(raw)} canEdit={may("products.edit") && may("products.create")} canDelete={may("products.delete")} />
      </Sheet>
    </>
  );
}

export const CategoriesPage = () =>
  page("categories", "Categories", "Product groupings in the catalog.", (raw) =>
    (raw as CategoryRow[]).map((c) => ({ key: c.id, name: c.name, path: c.path, parentId: c.parentId, isActive: c.isActive, count: c.productCount, childCount: c.childCount })),
  );

export const BrandsPage = () =>
  page("brands", "Brands", "Manufacturers and brands of stocked products.", (raw) => (raw as BrandRow[]).map((b) => ({ key: b.id, name: b.name, isActive: b.isActive, count: b.productCount })));

export const UnitsPage = () =>
  page("units", "Units of measure", "Units used to count products.", (raw) =>
    (raw as UnitRow[]).map((u) => ({ key: u.code, code: u.code, name: u.name, isActive: u.isActive, count: u.productCount })),
  );
