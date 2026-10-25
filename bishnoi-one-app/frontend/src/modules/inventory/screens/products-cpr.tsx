import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { CprImport } from "@/src/modules/inventory/components/cpr-import";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { context } from "@/src/modules/inventory/lib/page";
import type { CprState } from "@/src/modules/inventory/lib/types";

export const metadata = { title: "Update CPR numbers" };

type Summary = { counts: Record<CprState, number>; attention: number; warningDays: number };

/** Products' FDA registrations, many at once, with how many still need someone. */
export default async function ProductsCprPage() {
  const { may } = await context();
  if (!may("products.edit")) return <NoAccess what="updating products" />;
  const { cprSummary: s } = await loadQuery<{ cprSummary: Summary }>("query { cprSummary }", {}, ["cprSummary"]);
  const c = s.counts;
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/products", label: "Products" }]} title="Update CPR numbers">
        Each product&apos;s FDA Certificate of Product Registration, by SKU, from a spreadsheet. Nothing is saved until you have checked the rows.{" "}
        {s.attention > 0 ? (
          <a href="/inventory/products?cpr=attention" className="text-ink hover:underline">
            {s.attention} product{s.attention === 1 ? "" : "s"} need attention: {c.missing} without a CPR, {c.no_date} without a validity date, {c.expired} expired, {c.expiring} expiring within {s.warningDays} days.
          </a>
        ) : (
          <>Every product that needs a CPR has a valid one.</>
        )}
      </PageHeader>
      <CprImport />
    </>
  );
}
