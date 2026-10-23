import Link from "next/link";
import { PageHeader, SectionTitle, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { BatchStatusMark, MedicineStatusMark, NoAccess, Qty, RxClassMark } from "@/src/modules/pharmacy/components/bits";
import { DeleteRecord } from "@/src/modules/pharmacy/components/delete-record";
import { MedicineForm } from "@/src/modules/pharmacy/components/medicine-form";
import { pageFor } from "@/src/modules/pharmacy/lib/page";
import type { MedicineDetail, MedicineReference } from "@/src/modules/pharmacy/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: (await load<MedicineDetail>(`/medicines/${enc(id)}`)).label };
}

/** Medicine details: what it is, how it's given out, its status, and the batches on the shelf. */
export default async function MedicinePage({ params }: { params: Promise<{ id: string }> }) {
  const { me, fmt, allowed, may } = await pageFor("medicines.view");
  if (!allowed) return <NoAccess what="medicines" />;
  const { id } = await params;
  const [m, reference] = await Promise.all([load<MedicineDetail>(`/medicines/${enc(id)}`), load<MedicineReference>("/medicines/reference")]);
  const canEdit = may("medicines.edit");

  return (
    <>
      <PageHeader
        crumbs={[{ href: "/pharmacy/medicines", label: "Medicines" }]}
        title={
          <span className="inline-flex flex-wrap items-center gap-3">
            {m.label}
            <RxClassMark rxClass={m.rxClass} />
            <MedicineStatusMark status={m.status} />
          </span>
        }
        tools={
          may("medicines.delete") && (
            <DeleteRecord
              what="medicine"
              name={m.label}
              kind="medicine"
              id={m.id}
              after="/pharmacy/medicines"
              body="Only a medicine nothing refers to can be deleted. Once it has stock, prescriptions or sales, mark it discontinued instead."
            />
          )
        }
      >
        {m.code} · {m.onHand ?? 0} on hand, {m.available ?? 0} can be given out today · last changed {fmt.whenLabel(m.updatedAt).toLowerCase()}
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <Sheet className="px-5 py-6 sm:px-8">
          <MedicineForm key={m.updatedAt} medicine={m} reference={reference} org={me.org} canEdit={canEdit} />
        </Sheet>
        <Sheet className="h-fit">
          <div className="px-5 pt-5">
            <SectionTitle icon="batches" action={may("batches.view") && <Link href={`/pharmacy/batches?medicine=${m.id}`} className="text-meta font-semibold text-hema hover:underline">All batches</Link>}>
              Batches
            </SectionTitle>
          </div>
          {m.batches.length === 0 ? (
            <p className="px-5 py-4 text-meta text-ink-3">None received yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-rule border-t border-rule">
              {m.batches.map((b) => (
                <li key={b.id} className="flex items-center justify-between gap-3 px-5 py-2.5 text-sm">
                  <span className="min-w-0">
                    <span className="block font-medium">Lot {b.lotNo}</span>
                    <span className="block text-meta text-ink-3">
                      Expires {fmt.dateLabel(b.expiresOn)}
                      {b.supplier ? ` · ${b.supplier}` : ""}
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1">
                    <Qty n={b.qtyOnHand} />
                    {(b.status !== "available" || b.expired) && <BatchStatusMark status={b.status} expired={b.expired} />}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Sheet>
      </div>
    </>
  );
}
