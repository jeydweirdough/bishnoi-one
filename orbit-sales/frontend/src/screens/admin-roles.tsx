import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { RolesData } from "@/src/platform/lib/types";
import { RolesEditor } from "../components/admin/roles-editor";
import { NoAccess } from "../components/admin/words";
import { PeopleTabs } from "../components/admin/people-tabs";

export const metadata = { title: "Roles & permissions" };

export default async function RolesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.roles")) return <NoAccess what="roles and permissions" />;
  const data = await load<RolesData>("/admin/roles");
  return (
    <>
      <PageHeader title="People & access">
        A role is what someone may do, and whose records it reaches: their own, their team&apos;s, or everyone&apos;s. Each person has one.
      </PageHeader>
      <PeopleTabs me={me} current="/admin/roles" />
      <RolesEditor data={data} />
    </>
  );
}
