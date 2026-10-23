import { LinkButton } from "@/src/modules/inventory/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { CatalogAddButton, CatalogTable, type CatalogItem, type CatalogKind } from "@/src/modules/inventory/components/catalog-list";
import { FilterSelect, Filters, NoAccess } from "@/src/modules/inventory/components/ui";
import { param } from "@/src/modules/inventory/lib/labels";
import { context, type Search } from "@/src/modules/inventory/lib/page";
import type { BrandRow, CategoryRow, UnitRow } from "@/src/modules/inventory/lib/types";

// The catalog's short lists: categories, brands, units of measure. Laid out as
// Products is: Add at the top, search, then the table; a row opens to edit.

async function page(kind: CatalogKind, title: string, blurb: string, searchParams: Search, items: (raw: unknown) => CatalogItem[]) {
  const { may } = await context();
  if (!may("products.view")) return <NoAccess what="the product catalog" />;
  const s = await searchParams;
  const f = { q: param(s, "q"), status: param(s, "status") };
  const raw = (await loadQuery<Record<string, unknown>>(`query Catalog { ${kind} }`, {}, [kind]))[kind];
  const all = items(raw);
  const q = f.q.trim().toLowerCase();
  const shown = all.filter(
    (i) =>
      (!q || [i.name, i.path, i.code].some((v) => v?.toLowerCase().includes(q))) &&
      (f.status === "active" ? i.isActive : f.status === "inactive" ? !i.isActive : true),
  );
  const canEdit = may("products.edit") && may("products.create");
  const base = `/inventory/catalog/${kind}`;
  return (
    <>
      <PageHeader title={title} actions={canEdit && <CatalogAddButton kind={kind} items={all} />}>
        {blurb}
      </PageHeader>
      <Filters q={f.q} placeholder={kind === "units" ? "Code or name" : "Name"}>
        <FilterSelect name="status" label="Status" value={f.status} options={[{ value: "", label: "All" }, { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }]} />
      </Filters>
      <Sheet>
        {shown.length === 0 ? (
          <Empty title={all.length === 0 ? `No ${kind}` : `No ${kind} match`} icon="lists" actions={all.length > 0 && <LinkButton href={base}>Clear filters</LinkButton>} />
        ) : (
          <CatalogTable kind={kind} items={shown} all={all} canEdit={canEdit} canDelete={may("products.delete")} />
        )}
      </Sheet>
      <p className="mt-3 text-meta text-ink-3">
        {shown.length === all.length ? `${all.length} in total` : `Showing ${shown.length} of ${all.length}`}
      </p>
    </>
  );
}

export const CategoriesPage = ({ searchParams }: { searchParams: Search }) =>
  page("categories", "Categories", "Product groupings in the catalog. Nest them to build a hierarchy, for example Medical Supplies › Syringes.", searchParams, (raw) =>
    (raw as CategoryRow[]).map((c) => ({ key: c.id, name: c.name, path: c.path, parentId: c.parentId, isActive: c.isActive, count: c.productCount, childCount: c.childCount })),
  );

export const BrandsPage = ({ searchParams }: { searchParams: Search }) =>
  page("brands", "Brands", "Manufacturers and brands of stocked products.", searchParams, (raw) => (raw as BrandRow[]).map((b) => ({ key: b.id, name: b.name, isActive: b.isActive, count: b.productCount })));

export const UnitsPage = ({ searchParams }: { searchParams: Search }) =>
  page("units", "Units of measure", "Units used to count products. Quantities are recorded in whole units.", searchParams, (raw) =>
    (raw as UnitRow[]).map((u) => ({ key: u.code, code: u.code, name: u.name, isActive: u.isActive, count: u.productCount })),
  );
