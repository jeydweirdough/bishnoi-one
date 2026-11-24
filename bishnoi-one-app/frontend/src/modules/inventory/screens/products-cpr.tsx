import { FileText } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/src/modules/inventory/platform/ui/sheet";
import { load, loadQuery } from "@/src/modules/inventory/platform/lib/api";
import { CprImport } from "@/src/modules/inventory/components/cpr-import";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { context } from "@/src/modules/inventory/lib/page";
import type { CprState, ProductDocument } from "@/src/modules/inventory/lib/types";
import { Pill, type Tone } from "@/src/platform/ui/figures";

export const metadata = { title: "Item registrations (CPR)" };

type Summary = { counts: Record<CprState, number>; attention: number; warningDays: number };
type Inspection = {
  items: { product: { id: string; sku: string; name: string }; cprNumber: string | null; validUntil: string | null; state: CprState; stateLabel: string; file: ProductDocument | null }[];
  withFile: number;
  total: number;
};

const TONE: Record<CprState, Tone> = { valid: "good", expiring: "warn", no_date: "warn", expired: "bad", missing: "bad", not_needed: "plain" };
const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-PH", { day: "numeric", month: "short", year: "numeric" });

/**
 * Products' FDA registrations: the FDA inspection list (2026-11-18: every item that needs a CPR, its number, how long
 * it's valid and its CPR file to open, the ones needing attention first), and updating many at once from a spreadsheet.
 */
export default async function ProductsCprPage() {
  const { may } = await context();
  if (!may("products.view")) return <NoAccess what="items" />;
  const [{ cprSummary: s }, inspection] = await Promise.all([
    loadQuery<{ cprSummary: Summary }>("query { cprSummary }", {}, ["cprSummary"]),
    load<Inspection>("/inventory/cpr-files"),
  ]);
  const c = s.counts;
  return (
    <>
      <PageHeader crumbs={[{ href: "/inventory/products", label: "Items" }]} title="Item registrations (CPR)">
        For an FDA inspection: every item that needs a Certificate of Product Registration, with its CPR file to open.{" "}
        {s.attention > 0 ? (
          <a href="/inventory/products?cpr=attention" className="text-ink hover:underline">
            {s.attention} need attention: {c.missing} without a CPR, {c.no_date} without a validity date, {c.expired} expired, {c.expiring} expiring within {s.warningDays} days.
          </a>
        ) : (
          <>Every item that needs a CPR has a valid one.</>
        )}
      </PageHeader>

      <section aria-labelledby="fda" className="rounded-2xl border border-rule bg-card">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule px-5 py-3">
          <h2 id="fda" className="text-base font-semibold text-ink">FDA inspection</h2>
          <p className="text-meta text-ink-3">
            {inspection.withFile} of {inspection.total} with their CPR file. Add one on the item&apos;s page, under Documents: a file named with &ldquo;CPR&rdquo; is taken as one.
          </p>
        </div>
        {inspection.items.length === 0 ? (
          <p className="px-5 py-6 text-sm text-ink-2">No item needs a CPR yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-meta text-ink-3">
                  <th scope="col" className="px-5 py-2 font-medium">Item</th>
                  <th scope="col" className="px-3 py-2 font-medium">CPR number</th>
                  <th scope="col" className="px-3 py-2 font-medium">Valid until</th>
                  <th scope="col" className="px-3 py-2 font-medium">State</th>
                  <th scope="col" className="px-5 py-2 font-medium">CPR file</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {inspection.items.map((x) => (
                  <tr key={x.product.id} className="hover:bg-bench/40">
                    <td className="px-5 py-2">
                      <Link href={`/inventory/products/${x.product.id}`} className="font-medium text-ink hover:underline">{x.product.name}</Link>
                      <span className="block text-meta text-ink-3">{x.product.sku}</span>
                    </td>
                    <td className="px-3 py-2 tabular-nums">{x.cprNumber ?? <span className="text-ink-3">None</span>}</td>
                    <td className="px-3 py-2 tabular-nums">{x.validUntil ? day(x.validUntil) : <span className="text-ink-3">Not given</span>}</td>
                    <td className="px-3 py-2"><Pill tone={TONE[x.state]}>{x.stateLabel}</Pill></td>
                    <td className="px-5 py-2">
                      {x.file ? (
                        <a href={x.file.href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-hema hover:underline">
                          <FileText className="size-4" aria-hidden /> Open
                        </a>
                      ) : (
                        <Link href={`/inventory/products/${x.product.id}`} className="text-ink-3 hover:text-ink hover:underline">Add the file</Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {may("products.edit") && (
        <section aria-labelledby="many" className="mt-6">
          <h2 id="many" className="mb-2 text-base font-semibold text-ink">Update many from a spreadsheet</h2>
          <p className="mb-3 text-sm text-ink-2">CPR numbers and validity dates by SKU. Nothing is saved until you have checked the rows.</p>
          <CprImport />
        </section>
      )}
    </>
  );
}
