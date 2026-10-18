import { PageHeader } from "@/src/platform/ui/sheet";
import { canAny } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { AttentionRulesEditor } from "../components/settings/attention-rules";
import type { AttentionRules } from "../actions/settings";

export const metadata = { title: "Attention" };

export default async function AttentionSettingsPage() {
  const me = await getCompanyMe();
  if (!canAny(me, ["admin.settings", "department.manage"])) return <NoAccess what="Settings" />;
  const rules = await load<AttentionRules>("/admin/attention-rules");
  return (
    <>
      <PageHeader title={rules.canSetEveryone === false ? "Department settings" : "Settings"}>
        When something is worth a prompt in &quot;Needs your attention&quot; on people&apos;s home pages. A division can have its own
        {rules.canSetEveryone === false ? "; yours are below, starting from everyone's." : "."}
      </PageHeader>
      <AttentionRulesEditor initial={rules} />
    </>
  );
}
