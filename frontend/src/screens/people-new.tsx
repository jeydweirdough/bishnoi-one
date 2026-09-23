import { NewPersonForm } from "../components/new-person-form";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { loadOrg } from "@/src/platform/lib/org";
import type { RolesPayload } from "@/src/platform/lib/types";

export const metadata = { title: "Add person" };

export default async function NewPersonPage() {
  const [{ roles, modules }, divisions] = await Promise.all([load<RolesPayload>("/admin/roles"), loadOrg()]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/settings/people", label: "People" }]} title="Add person" />
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <NewPersonForm roles={roles} divisions={divisions} apps={modules.filter((m) => m.kind === "app")} />
      </Sheet>
    </>
  );
}
