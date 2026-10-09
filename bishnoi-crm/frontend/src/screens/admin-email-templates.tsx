import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { EmailTemplates } from "../components/settings/email-templates";
import type { EmailTemplate } from "../actions/mailbox";

export const metadata = { title: "Email templates" };

export default async function EmailTemplatesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const [items, teams] = await Promise.all([load<EmailTemplate[]>("/email-templates?all=true"), load<{ id: string; name: string; isActive: boolean }[]>("/team-names")]);
  return (
    <>
      <PageHeader title="Settings">The emails reps may send from a customer&apos;s page, worded as written. Reps add a personal note; they can&apos;t change the wording.</PageHeader>
      <EmailTemplates items={items} teams={teams.filter((t) => t.isActive).map((t) => ({ value: t.id, label: t.name }))} />
    </>
  );
}
