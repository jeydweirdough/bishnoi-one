import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { RecurringClient } from "@/src/modules/finance/parity/recurring-client";
import type { RecurringItem } from "@/src/modules/finance/parity/types";

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

export async function RecurringPage() {
  const me = await getCompanyMe();
  const data = await load<{
    items: RecurringItem[];
    dueCount: number;
    today: string;
    suppliers: { id: string; name: string }[];
    accounts: { id: string; code: string; name: string }[];
    incomeAccounts: { id: string; code: string; name: string }[];
  }>("/finance/recurring");

  return (
    <Sheet>
      <PageHeader title="Recurring bills & invoices">
        <p className="mt-1 text-meta text-ink-2">
          Automate repeating schedules (rent, utilities, retainers). Schedules always generate Drafts so VAT, EWT, and approvals are still checked by staff.
        </p>
      </PageHeader>
      <RecurringClient
        today={data.today}
        items={data.items}
        dueCount={data.dueCount}
        suppliers={data.suppliers}
        accounts={data.accounts}
        incomeAccounts={data.incomeAccounts ?? []}
        canCreate={may(me, "bills.create")}
      />
    </Sheet>
  );
}
