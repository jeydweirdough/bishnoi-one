import { NoAccess } from "@/src/modules/inventory/components/ui";
import { ScanLookup } from "@/src/modules/inventory/components/scan";
import { context } from "@/src/modules/inventory/lib/page";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";

// Scanning (feature plan step 14c): look up whatever is in front of you.

export async function ScanPage() {
  const { may } = await context();
  if (!may("stock.view")) return <NoAccess what="scanning" />;
  return (
    <>
      <PageHeader title="Scan">
        Scan an item&apos;s barcode, a batch or serial number, or a document&apos;s number, with a handheld scanner or the camera. Documents open straight away.
      </PageHeader>
      <Sheet className="max-w-3xl px-5 py-4">
        <ScanLookup />
      </Sheet>
    </>
  );
}
