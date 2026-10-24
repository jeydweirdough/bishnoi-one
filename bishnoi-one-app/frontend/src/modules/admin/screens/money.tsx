import { managersOnly } from "@/src/modules/admin/components/gate";
import { MoneySettings } from "@/src/modules/admin/components/money-settings";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { load } from "@/src/modules/admin/platform/lib/api";
import type { Company } from "@/src/modules/admin/platform/lib/types";

export const metadata = { title: "Money and formats" };

export default async function MoneyFormatsPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const data = await load<Company>("/admin/company");
  // One instant, settled on the server, so the preview's clock reads the same
  // the moment the page arrives as it did when it was drawn.
  const now = new Date().toISOString();
  return (
    <>
      <PageHeader title="Money and formats">
        How this company writes money, dates and times. Every screen reads them from here, so a change shows up everywhere at once.
      </PageHeader>
      {/* Keyed on what's stored, so a save starts the form from the saved record. */}
      <MoneySettings key={JSON.stringify(data)} data={data} now={now} />
    </>
  );
}
