import { PageHeader } from "@/src/modules/finance/platform/ui/sheet";
import { load } from "@/src/modules/finance/platform/lib/api";
import { SalesDatScreen } from "@/src/modules/finance/bir/sales-dat/screen";
import type { Company } from "@/src/modules/finance/bir/sales-dat";

export const metadata = { title: "BIR sales DAT" };

/** The BIR Summary List of Sales (RELIEF) DAT, from Oojeema's exports. Asking the API for
 *  the companies' details is also what keeps this page to a role that prepares BIR files. */
export default async function SalesDatPage() {
  const { companies } = await load<{ companies: Company[] }>("/finance/bir/sales-dat");
  return (
    <>
      <PageHeader title="BIR sales DAT">
        Builds the Summary List of Sales (RELIEF) DAT from Oojeema&apos;s exports, applies the rules Sir Rommel confirmed, and checks it against the Income Statement.
      </PageHeader>
      <SalesDatScreen companies={companies} />
    </>
  );
}
