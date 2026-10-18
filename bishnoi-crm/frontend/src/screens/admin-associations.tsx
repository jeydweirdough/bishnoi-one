import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { AssociationLabels } from "../components/settings/association-labels";
import type { AssociationLabel } from "../actions/settings";

export const metadata = { title: "Associations" };

export default async function AssociationsSettingsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const labels = await load<AssociationLabel[]>("/admin/association-labels");
  return (
    <>
      <PageHeader title="Settings">How records can be linked to one another, read from each side: a contact works at an organization, whose page lists the people there.</PageHeader>
      <AssociationLabels initial={labels} />
    </>
  );
}
