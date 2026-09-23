import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { TeamRow } from "@/src/platform/lib/types";
import { TeamsEditor } from "../components/admin/teams-editor";
import { NoAccess } from "../components/admin/words";
import { PeopleTabs } from "../components/admin/people-tabs";

export const metadata = { title: "Teams" };

export default async function TeamsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.teams")) return <NoAccess what="managing teams" />;
  const teams = await load<TeamRow[]>("/admin/teams");
  return (
    <>
      <PageHeader title="People & access">
        People work in teams. A role that reaches &ldquo;their team&apos;s records&rdquo; means the records of everyone in the same team.
      </PageHeader>
      <PeopleTabs me={me} current="/admin/teams" />
      <TeamsEditor teams={teams} />
    </>
  );
}
