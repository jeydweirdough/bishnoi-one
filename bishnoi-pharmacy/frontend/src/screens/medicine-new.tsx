import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/bits";
import { MedicineForm } from "../components/medicine-form";
import { pageFor } from "../lib/page";
import type { MedicineReference } from "../lib/types";

export const metadata = { title: "Add medicine" };

export default async function MedicineNewPage() {
  const { me, allowed } = await pageFor("medicines.create");
  if (!allowed) return <NoAccess what="adding medicines" />;
  const reference = await load<MedicineReference>("/medicines/reference");
  return (
    <>
      <PageHeader crumbs={[{ href: "/medicines", label: "Medicines" }]} title="Add medicine">
        Stock comes in through Stock → Receiving, batch by batch.
      </PageHeader>
      <Sheet className="max-w-[55rem] px-5 py-6 sm:px-8">
        <MedicineForm reference={reference} org={me.org} canEdit />
      </Sheet>
    </>
  );
}
