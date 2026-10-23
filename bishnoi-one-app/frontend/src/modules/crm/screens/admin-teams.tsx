import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { TeamRow } from "@/src/platform/lib/types";
import { TeamsEditor, type ManagerOption } from "@/src/modules/crm/components/admin/teams-editor";
import { NoAccess } from "@/src/modules/crm/components/admin/words";

export const metadata = { title: "Teams" };

export default async function TeamsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.teams")) return <NoAccess what="managing teams" />;
  const [teams, managers] = await Promise.all([load<TeamRow[]>("/admin/teams"), load<ManagerOption[]>("/admin/teams/managers")]);
  return (
    <>
      <PageHeader title="People and access">
        People work in teams. A team lead reaches their own team&apos;s records; a manager, above the team leads, reaches every team they&apos;re the manager of.
      </PageHeader>
      <TeamsEditor teams={teams} managers={managers} />
    </>
  );
}
