import { managersOnly } from "@/src/modules/admin/components/gate";
import { TeamsEditor } from "@/src/modules/admin/components/teams-editor";
import { PageHeader } from "@/src/modules/admin/platform/ui/sheet";
import { getCompanyMe } from "@/src/modules/admin/platform/lib/api";
import { loadOrg } from "@/src/modules/admin/platform/lib/org";

export const metadata = { title: "Teams" };

export default async function TeamsPage() {
  const stop = await managersOnly();
  if (stop) return stop;
  const [divisions, me] = await Promise.all([loadOrg(), getCompanyMe()]);
  return (
    <>
      <PageHeader title="Teams">
        Every record belongs to a division and a team together. The same team name in two divisions (MD Telesales in B&amp;B
        and in B2C) is two separate teams. Teams are switched off, never deleted, so their records keep a home.
      </PageHeader>
      <TeamsEditor company={me.org.name} divisions={divisions} />
    </>
  );
}
