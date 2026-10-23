// Adding a platform user: who they are, their company, and which of its
// applications they get.
import { adminsOnly } from "@/src/modules/console/components/gate";
import { UserForm } from "@/src/modules/console/components/users/user-form";
import { enc, load } from "@/src/modules/console/platform/lib/api";
import { PageHeader, Sheet } from "@/src/modules/console/platform/ui/sheet";
import type { CompanyDetail, Options } from "@/src/modules/console/lib/types";

export const metadata = { title: "Add user" };

export default async function NewUserPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const refused = await adminsOnly();
  if (refused) return refused;
  const { company } = await searchParams;
  const options = await load<Options>("/platform/options");
  const preset = typeof company === "string" && options.companies.some((c) => c.id === company) ? company : "";
  const apps = preset ? (await load<{ company: CompanyDetail }>(`/platform/companies/${enc(preset)}`)).company.applications : [];
  const presetName = options.companies.find((c) => c.id === preset)?.name;
  return (
    <>
      <PageHeader
        title="Add user"
        crumbs={preset && presetName ? [{ href: "/platform/console/companies", label: "Companies" }, { href: `/platform/console/companies/${preset}?tab=users`, label: presetName }] : [{ href: "/platform/console/users", label: "Users" }]}
      >
        One account for the person, with the applications they may use. They still sign in to each application on its own.
      </PageHeader>
      {options.companies.length === 0 ? (
        <Sheet className="max-w-3xl px-5 py-6 text-ink-2">Add a company first: every user belongs to a company.</Sheet>
      ) : (
        <Sheet className="max-w-3xl px-5 py-5 sm:px-6">
          <UserForm companies={options.companies} companyId={preset} initialApps={apps} />
        </Sheet>
      )}
    </>
  );
}
