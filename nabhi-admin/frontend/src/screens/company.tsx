import { ownersOnly } from "../components/gate";
import { CompanySettings } from "../components/company-settings";
import { PageHeader } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import type { Company } from "@/src/platform/lib/types";

export const metadata = { title: "Company" };

export default async function CompanyPage() {
  const stop = await ownersOnly();
  if (stop) return stop;
  const data = await load<Company>("/admin/company");
  return (
    <>
      <PageHeader title="Company">
        Who this company is: the name on its letters, the short name every screen shows, and what its order numbers start with. How
        it writes money, dates and times is under Money &amp; formats.
      </PageHeader>
      {/* Keyed on what's stored, so a save starts the form from the saved record. */}
      <CompanySettings key={JSON.stringify(data)} data={data} />
    </>
  );
}
