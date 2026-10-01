import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { RequestForm } from "../components/funds/request-form";
import type { FundPurpose } from "../components/funds/types";

export const metadata = { title: "New marketing request" };

export default async function NewFundRequest() {
  const me = await getCompanyMe();
  if (!can(me, "funds.create")) return <NoAccess what="marketing requests" />;
  const purposes = await load<{ items: FundPurpose[] }>("/funds/purposes");
  return (
    <>
      <PageHeader crumbs={[{ href: "/funds", label: "My marketing requests" }]} title="New marketing request">
        Submitted to your Team Lead for approval, then to Finance for release.
      </PageHeader>
      <Sheet className="max-w-[48rem] px-5 py-6 sm:px-8">
        {purposes.items.length === 0 ? (
          <Empty title="No purposes set up yet" icon="payments">
            An administrator sets them under Settings → Marketing request purposes.
          </Empty>
        ) : (
          <RequestForm purposes={purposes.items} org={me.org} today={makeFormat(me.org).todayKey()} />
        )}
      </Sheet>
    </>
  );
}
