import { getCompanyMe, load } from "@/src/modules/finance/platform/lib/api";
import { makeFormat } from "@/src/modules/finance/platform/lib/format";
import { PageHeader, Sheet } from "@/src/modules/finance/platform/ui/sheet";
import { CreditNotesClient, VendorCreditsClient } from "@/src/modules/finance/parity/credits-client";
import type { CreditNoteItem, VendorCreditItem } from "@/src/modules/finance/parity/types";

const may = (me: { permissions?: string[] }, p: string) => me.permissions?.includes(p) ?? false;

export async function CreditNotesPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{
    items: CreditNoteItem[];
    invoices: { id: string; number: string; customerName: string; customerTin: string | null; balanceCentavos: number }[];
    incomeAccounts: { id: string; code: string; name: string }[];
  }>("/finance/credit-notes");

  return (
    <Sheet>
      <PageHeader title="Customer credit notes">
        <p className="mt-1 text-meta text-ink-2">
          Issue sales returns &amp; credit adjustments, apply them to open invoices, and reflect them automatically in BIR Sales Journal, 2550Q, and SLS.
        </p>
      </PageHeader>
      <CreditNotesClient
        org={me.org}
        today={fmt.todayKey()}
        items={data.items}
        invoices={data.invoices}
        incomeAccounts={data.incomeAccounts ?? []}
        canCreate={may(me, "invoices.create")}
        canIssue={may(me, "invoices.issue")}
        canCollect={may(me, "invoices.collect")}
        canVoid={may(me, "invoices.void")}
      />
    </Sheet>
  );
}

export async function VendorCreditsPage() {
  const me = await getCompanyMe();
  const fmt = makeFormat(me.org);
  const data = await load<{
    items: VendorCreditItem[];
    bills: { id: string; no: number | null; billNumber: string; supplierId: string; supplierName: string; owedCentavos: number }[];
    suppliers: { id: string; name: string }[];
    accounts: { id: string; code: string; name: string }[];
  }>("/finance/vendor-credits");

  return (
    <Sheet>
      <PageHeader title="Supplier vendor credits">
        <p className="mt-1 text-meta text-ink-2">
          Record supplier credit memos, apply them against unpaid bills before payment vouchers, and keep BIR Input VAT, EWT, SLP &amp; QAP reconciled.
        </p>
      </PageHeader>
      <VendorCreditsClient
        org={me.org}
        today={fmt.todayKey()}
        items={data.items}
        bills={data.bills}
        suppliers={data.suppliers ?? []}
        accounts={data.accounts ?? []}
        canCreate={may(me, "bills.create")}
        canApprove={may(me, "bills.approve")}
        canApply={may(me, "vouchers.prepare")}
        canVoid={may(me, "bills.void")}
      />
    </Sheet>
  );
}
