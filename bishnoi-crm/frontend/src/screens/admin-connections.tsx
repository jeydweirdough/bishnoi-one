import { PageHeader } from "@/src/platform/ui/sheet";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { ConnectionCard } from "../components/settings/connection-card";
import type { ConnectionInfo } from "../actions/settings";

export const metadata = { title: "Connections" };

/** The outside services the CRM may connect to, and the details each one needs. */
export default async function ConnectionsPage() {
  const me = await getCompanyMe();
  if (!can(me, "admin.settings")) return <NoAccess what="Settings" />;
  const [list, fmt] = [await load<ConnectionInfo[]>("/admin/connections"), makeFormat(me.org)];
  return (
    <>
      <PageHeader title="Settings">
        The details the CRM needs to connect to outside services. Secrets are kept encrypted and never shown again once saved.
      </PageHeader>
      <div className="max-w-3xl space-y-5">
        {list.map((c) => (
          <ConnectionCard
            key={c.key}
            connection={c}
            checkedWhen={c.check ? fmt.whenLabel(c.check.at) : null}
            updatedWhen={c.updatedAt ? fmt.whenLabel(c.updatedAt) : null}
          />
        ))}
      </div>
    </>
  );
}
