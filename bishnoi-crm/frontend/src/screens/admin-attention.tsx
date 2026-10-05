import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { AttentionRulesEditor } from "../components/settings/attention-rules";
import type { AttentionRules } from "../actions/settings";

export const metadata = { title: "Attention" };

export default async function AttentionSettingsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const rules = await load<AttentionRules>("/admin/attention-rules");
  return (
    <>
      <PageHeader title="Settings">When something is worth a prompt in &quot;Needs your attention&quot; on people&apos;s home pages. A division can have its own.</PageHeader>
      <AttentionRulesEditor initial={rules} />
    </>
  );
}
