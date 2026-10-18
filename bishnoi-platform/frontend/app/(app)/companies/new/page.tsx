// Adding a company: its particulars, which applications it gets, and who runs it.
import { adminsOnly } from "@/src/components/gate";
import { CompanyForm } from "@/src/components/organizations/company-form";
import { load } from "@/src/platform/lib/api";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import type { Options } from "@/src/lib/types";

export const metadata = { title: "Add company" };

export default async function NewCompanyPage() {
  const refused = await adminsOnly();
  if (refused) return refused;
  const options = await load<Options>("/platform/options");
  return (
    <>
      <PageHeader title="Add company" crumbs={[{ href: "/companies", label: "Companies" }]}>
        A company on the platform, with the applications its users can access.
      </PageHeader>
      <Sheet className="max-w-3xl px-5 py-5 sm:px-6">
        <CompanyForm applications={options.applications} />
      </Sheet>
    </>
  );
}
