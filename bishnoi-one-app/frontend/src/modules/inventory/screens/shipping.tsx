import { load } from "@/src/modules/inventory/platform/lib/api";
import { NoAccess } from "@/src/modules/inventory/components/ui";
import { CouriersEditor } from "@/src/modules/inventory/components/shipping";
import { context } from "@/src/modules/inventory/lib/page";
import type { Courier } from "@/src/modules/inventory/lib/types";
import { PageHeader, Sheet } from "@/src/platform/ui/sheet";

// Shipping with couriers (feature plan step 12): the delivery companies the warehouse hands parcels to.

export async function CouriersPage() {
  const { may } = await context();
  if (!may("warehouses.view")) return <NoAccess what="couriers" />;
  const couriers = await load<Courier[]>("/inventory/couriers");
  return (
    <>
      <PageHeader title="Couriers">
        The delivery companies your warehouse hands parcels to. Each delivery names its courier and tracking number; its tracking page opens from there.
      </PageHeader>
      <Sheet className="max-w-3xl px-5 py-4">
        <CouriersEditor couriers={couriers} mayManage={may("warehouses.manage")} />
      </Sheet>
    </>
  );
}
