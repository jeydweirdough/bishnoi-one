import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/admin/words";
import { PurposesEditor } from "../components/funds/purposes-editor";
import type { FundPurpose } from "../components/funds/types";

export const metadata = { title: "Fund purposes" };

export default async function FundPurposesPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="settings" />;
  const purposes = await load<{ items: FundPurpose[] }>("/funds/purposes?every=true");
  return (
    <>
      <PageHeader title="Fund purposes">
        The purposes salespeople and field agents can request funds for. A purpose subject to liquidation requires official receipts and a refund of any
        excess; the Team Lead can still change that on a
        request. Expense categories are managed by Finance in Nabhi Finance.
      </PageHeader>
      <Sheet className="px-5 py-4">
        <PurposesEditor purposes={purposes.items} />
      </Sheet>
    </>
  );
}
