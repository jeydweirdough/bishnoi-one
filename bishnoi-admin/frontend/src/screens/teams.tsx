import { managersOnly } from "../components/gate";
import { TeamsEditor } from "../components/teams-editor";
import { PageHeader } from "@/src/platform/ui/sheet";
import { getCompanyMe } from "@/src/platform/lib/api";
import { loadOrg } from "@/src/platform/lib/org";

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
