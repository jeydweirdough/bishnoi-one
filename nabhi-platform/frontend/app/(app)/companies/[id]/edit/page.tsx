// Changing a company's particulars. Its applications, structure and status
// are changed on its own page.
import type { Metadata } from "next";
import { adminsOnly } from "@/src/components/gate";
import { CompanyForm } from "@/src/components/organizations/company-form";
import { enc, load } from "@/src/platform/lib/api";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import type { CompanyDetail } from "@/src/lib/types";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const { company } = await load<{ company: CompanyDetail }>(`/platform/companies/${enc(id)}`);
  return { title: `Edit ${company.name}` };
}

export default async function EditCompanyPage({ params }: Props) {
  const refused = await adminsOnly();
  if (refused) return refused;
  const { id } = await params;
  const { company } = await load<{ company: CompanyDetail }>(`/platform/companies/${enc(id)}`);
  return (
    <>
      <PageHeader
        title={`Edit ${company.name}`}
        crumbs={[
          { href: "/companies", label: "Companies" },
          { href: `/companies/${company.id}`, label: company.name },
        ]}
      />
      <Sheet className="max-w-3xl px-5 py-5 sm:px-6">
        <CompanyForm company={company} applications={[]} />
      </Sheet>
    </>
  );
}
