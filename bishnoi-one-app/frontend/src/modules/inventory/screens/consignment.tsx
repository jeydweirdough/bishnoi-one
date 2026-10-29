import { load } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess, Table, Td } from "@/src/modules/inventory/components/ui";
import { SettleConsignment } from "@/src/modules/inventory/components/supply";
import { context } from "@/src/modules/inventory/lib/page";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";

// Consignment (feature plan step 15d): each vendor's consignment sold since its last settlement, settled once and
// sent to Finance as a draft vendor bill.

type Vendor = {
  supplier: { id: string; code: string; name: string };
  since: string | null;
  lines: { productId: string; sku: string; name: string; quantity: number; unitCost: number; total: number }[];
  toPay: number;
  settlements: { id: string; number: string; from: string | null; to: string; total: number; lines: number }[];
};

export async function ConsignmentPage() {
  const { fmt, may, at } = await context();
  if (!may("purchasing.view")) return <NoAccess what="consignment" />;
  const { vendors } = await load<{ vendors: Vendor[] }>("/inventory/consignment");
  return (
    <>
      <PageHeader title="Consignment">
        Vendors&apos; stock kept with us and paid for as it sells. Settle a vendor to bill what sold since the last time: Finance gets it as a draft vendor bill.
      </PageHeader>
      {vendors.length === 0 ? (
        <Sheet><Empty icon="suppliers" title="No consignment stock" source="Purchase receives ticked On consignment." /></Sheet>
      ) : (
        vendors.map((v) => (
          <Sheet key={v.supplier.id} className="mb-5 px-5 py-4">
            <SectionTitle icon="suppliers" action={may("purchasing.approve") && <SettleConsignment supplierId={v.supplier.id} name={v.supplier.name} disabled={v.toPay === 0} />}>
              {v.supplier.name}
            </SectionTitle>
            <p className="mb-2 text-meta text-ink-3">Sold {v.since ? `since ${at(v.since)}` : "since it began"}: {fmt.peso(v.toPay)} to pay.</p>
            {v.lines.length > 0 && (
              <Table head={["Item", " Sold", " Vendor price", " To pay"]} min="32rem">
                {v.lines.map((l) => (
                  <tr key={l.productId}>
                    <Td><span className="font-medium">{l.name}</span><span className="block text-meta text-ink-3">{l.sku}</span></Td>
                    <Td num>{fmt.count(l.quantity)}</Td>
                    <Td num>{fmt.peso(l.unitCost)}</Td>
                    <Td num className="font-semibold">{fmt.peso(l.total)}</Td>
                  </tr>
                ))}
              </Table>
            )}
            {v.settlements.length > 0 && (
              <p className="mt-3 text-meta text-ink-3">
                Settled: {v.settlements.map((x) => `${x.number} (${fmt.peso(x.total)}, ${at(x.to)})`).join(" · ")}
              </p>
            )}
          </Sheet>
        ))
      )}
    </>
  );
}
