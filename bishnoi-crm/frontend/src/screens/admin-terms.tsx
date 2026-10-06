import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import type { TermsSettings } from "../actions/settings";
import { NoAccess } from "../components/admin/words";
import { TermsEditor } from "../components/terms/terms-editor";

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
