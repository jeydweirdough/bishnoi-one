import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { AdvancesClient } from "@/src/modules/finance/parity/advances-client";
import type { AdvanceItem } from "@/src/modules/finance/parity/types";

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

export async function AdvancesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{
    items: AdvanceItem[];
    banks: { id: string; name: string; kind: string }[];
    suppliers: { id: string; name: string }[];
    bills: { id: string; no: number | null; billNumber: string; supplierId: string; supplierName: string; owedCentavos: number }[];
    invoices: { id: string; number: string; customerName: string; owedCentavos: number }[];
  }>("/finance/advances");

  return (
    <Sheet>
      <PageHeader title="Advances & deposits">
        <p className="mt-1 text-meta text-ink-2">
          Track supplier prepayments (1401-000) and customer deposits / retainers (2205-000) cleanly without double-counting VAT, then apply them to bills or invoices.
        </p>
      </PageHeader>
      <AdvancesClient
        org={me.org}
        today={fmt.todayKey()}
        items={data.items}
        banks={data.banks}
        suppliers={data.suppliers}
        bills={data.bills}
        invoices={data.invoices}
        canPrepare={may(me, "vouchers.prepare")}
        canVoid={may(me, "bills.void")}
      />
    </Sheet>
  );
}
