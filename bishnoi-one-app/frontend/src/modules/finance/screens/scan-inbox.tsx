import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { ScanClient } from "@/src/modules/finance/parity/scan-client";
import type { DocumentScanItem } from "@/src/modules/finance/parity/types";

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

export async function ScanInboxPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{
    items: DocumentScanItem[];
    suppliers: { id: string; name: string; tin: string | null }[];
    accounts: { id: string; code: string; name: string }[];
    vatKinds: { key: string; label: string }[];
  }>("/finance/scans");

  return (
    <Sheet>
      <PageHeader title="Document auto-scan inbox">
        <p className="mt-1 text-meta text-ink-2">
          Upload supplier invoices or receipts (JPG, PNG, or PDF), verify extracted supplier &amp; BIR details, and create a Draft bill with the scan attached.
        </p>
      </PageHeader>
      <ScanClient
        today={fmt.todayKey()}
        items={data.items}
        suppliers={data.suppliers}
        accounts={data.accounts}
        vatKinds={data.vatKinds}
        canCreate={may(me, "bills.create")}
      />
    </Sheet>
  );
}
