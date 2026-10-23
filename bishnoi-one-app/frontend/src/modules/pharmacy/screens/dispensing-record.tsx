import Link from "next/link";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { NoAccess } from "@/src/modules/pharmacy/components/bits";
import { pageFor } from "@/src/modules/pharmacy/lib/page";
import type { Dispensing } from "@/src/modules/pharmacy/lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: (await load<Dispensing>(`/dispensing/${enc(id)}`)).number };
}

/** One hand-over: what went out, from which batch, and the sale it made. */
export default async function DispensingRecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { fmt, allowed, may } = await pageFor("dispensing.view");
  if (!allowed) return <NoAccess what="dispensing" />;
  const { id } = await params;
  const d = await load<Dispensing>(`/dispensing/${enc(id)}`);

  return (
    <>
      <PageHeader crumbs={[{ href: "/pharmacy/dispensing?view=history", label: "Dispensing history" }]} title={`Dispensing ${d.number}`}>
        {fmt.whenLabel(d.dispensedAt)}
        {d.dispensedBy ? ` by ${d.dispensedBy.name}${d.dispensedBy.licenseNo ? ` (${d.dispensedBy.licenseNo})` : ""}` : ""}
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <Sheet>
          <div className="px-5 pt-5">
            <SectionTitle icon="dispensing">Handed over</SectionTitle>
          </div>
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-y border-rule text-caps text-ink-3 uppercase">
                <th scope="col" className="py-2.5 pr-3 pl-5 font-semibold">Medicine</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Batch</th>
                <th scope="col" className="py-2.5 pr-5 pl-3 text-right font-semibold">Quantity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {d.lines.map((l, n) => (
                <tr key={n}>
                  <td className="py-3 pr-3 pl-5">
                    <Link href={`/pharmacy/medicines/${l.medicineId}`} className="font-semibold text-hema hover:underline">
                      {l.medicine}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-ink-2">
                    Lot {l.lotNo} · expires {fmt.dateLabel(l.expiresOn)}
                  </td>
                  <td className="py-3 pr-5 pl-3 text-right tabular-nums">
                    {l.quantity} <span className="text-meta text-ink-3">{l.unit}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Sheet>
        <Sheet className="h-fit px-5 py-5">
          <Particulars
            items={[
              ["Patient", <Link key="p" href={`/pharmacy/patients/${d.patient.id}`} className="text-hema hover:underline">{d.patient.fullName}</Link>],
              ["Prescription", <Link key="r" href={`/pharmacy/prescriptions/${d.prescription.id}`} className="text-hema hover:underline">{d.prescription.number}</Link>],
              ["Sale", d.saleId && may("sales.view") ? <Link key="s" href={`/pharmacy/sales/${d.saleId}`} className="text-hema hover:underline">Open the sale</Link> : null],
              ["Notes", d.notes],
            ]}
          />
        </Sheet>
      </div>
    </>
  );
}
