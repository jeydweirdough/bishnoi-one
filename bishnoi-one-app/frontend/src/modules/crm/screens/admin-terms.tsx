import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/modules/crm/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { TermsSettings } from "@/src/modules/crm/actions/settings";
import { NoAccess } from "@/src/modules/crm/components/admin/words";
import { TermsEditor } from "@/src/modules/crm/components/terms/terms-editor";

export const metadata = { title: "Terms" };

/** Settings → Terms: the few words the company names its own way. */
export default async function TermsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="changing the CRM's terms" />;
  const data = await load<TermsSettings>("/admin/terms");
  return (
    <>
      <PageHeader title="Settings">
        Terms: the words the CRM uses for your field work, in your company&apos;s own language. Everything else the CRM says stays general; customer types, form
        fields and price types are already yours to name.
      </PageHeader>
      <TermsEditor data={data} />
    </>
  );
}
