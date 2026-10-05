import Link from "next/link";
import { Particulars, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { NoAccess } from "../components/bits";
import { ReturnForm } from "../components/return-form";
import { SaleForm } from "../components/sale-form";
import { pageFor } from "../lib/page";
import { PAYMENT_METHODS } from "../lib/words";
import type { Medicine, PatientRow, SaleDetail } from "../lib/types";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return { title: (await load<SaleDetail>(`/sales/${enc(id)}`)).number };
}

/** One sale, as a receipt, with anything returned on it. */
export default async function SalePage({ params }: { params: Promise<{ id: string }> }) {
  const { me, fmt, allowed, may } = await pageFor("sales.view");
  if (!allowed) return <NoAccess what="sales" />;
  const { id } = await params;
  const s = await load<SaleDetail>(`/sales/${enc(id)}`);

  return (
    <>
      <PageHeader crumbs={[{ href: "/sales?view=history", label: "Sales" }]} title={`Sale ${s.number}`}>
        {s.source === "dispensing" ? "Made by dispensing" : "Over the counter"} · {fmt.whenLabel(s.soldAt)}
        {s.soldBy ? ` by ${s.soldBy.name}` : ""}
      </PageHeader>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,20rem)]">
        <div className="space-y-4">
          <Sheet>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-rule text-caps text-ink-3 uppercase">
                  <th scope="col" className="py-3 pr-3 pl-5 font-semibold">Medicine</th>
                  <th scope="col" className="px-3 py-3 text-right font-semibold">Qty</th>
                  <th scope="col" className="px-3 py-3 text-right font-semibold">Each</th>
                  <th scope="col" className="py-3 pr-5 pl-3 text-right font-semibold">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {s.lines.map((l) => (
                  <tr key={l.id}>
                    <td className="py-3 pr-3 pl-5">
                      <Link href={`/medicines/${l.medicineId}`} className="font-semibold text-hema hover:underline">
                        {l.medicine}
                      </Link>
                      <span className="block text-meta text-ink-3">
                        Lot {l.lotNo}
                        {l.qtyReturned > 0 ? ` · ${l.qtyReturned} returned` : ""}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">{l.quantity}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{fmt.peso(l.unitPriceCentavos)}</td>
                    <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(l.lineTotalCentavos)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-rule text-sm">
                {s.discountCentavos > 0 && (
                  <tr>
                    <td colSpan={3} className="py-2 pr-3 pl-5 text-right text-ink-2">Discount</td>
                    <td className="py-2 pr-5 pl-3 text-right tabular-nums">−{fmt.peso(s.discountCentavos)}</td>
                  </tr>
                )}
                <tr>
                  <td colSpan={3} className="py-2 pr-3 pl-5 text-right font-semibold">Total</td>
                  <td className="py-2 pr-5 pl-3 text-right font-semibold tabular-nums">{fmt.peso(s.totalCentavos)}</td>
                </tr>
                {s.refundedCentavos > 0 && (
                  <tr>
                    <td colSpan={3} className="py-2 pr-3 pl-5 text-right text-ink-2">Refunded</td>
                    <td className="py-2 pr-5 pl-3 text-right tabular-nums">−{fmt.peso(s.refundedCentavos)}</td>
                  </tr>
                )}
              </tfoot>
            </table>
          </Sheet>

          {(s.returns.length > 0 || may("sales.refund")) && (
            <Sheet className="px-5 py-5">
              <SectionTitle icon="returns">Returns &amp; refunds</SectionTitle>
              {s.returns.length > 0 && (
                <ul className="-mx-5 mt-3 mb-4 divide-y divide-rule border-y border-rule">
                  {s.returns.map((r) => (
                    <li key={r.id} className="flex flex-wrap justify-between gap-3 px-5 py-2.5 text-sm">
                      <span>
                        <span className="font-semibold">{r.number}</span> · {r.units} unit{r.units === 1 ? "" : "s"} · {r.reason}
                        <span className="block text-meta text-ink-3">{r.restocked ? "Back on the shelf" : "Not restocked"}</span>
                      </span>
                      <span className="text-right text-meta text-ink-2">
                        {r.refundCentavos ? `${fmt.peso(r.refundCentavos)} refunded` : "No refund"}
                        <span className="block">{fmt.whenLabel(r.at)}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {may("sales.refund") && (
                <div className="mt-3">
                  <ReturnForm sale={s} org={me.org} />
                </div>
              )}
            </Sheet>
          )}
        </div>
        <Sheet className="h-fit px-5 py-5">
          <Particulars
            items={[
              ["Customer", s.patient ? <Link key="c" href={`/patients/${s.patient.id}`} className="text-hema hover:underline">{s.patient.fullName}</Link> : "Walk-in"],
              ["Paid by", PAYMENT_METHODS[s.paymentMethod]],
              ["Dispensing", s.dispensing ? <Link key="d" href={`/dispensing/${s.dispensing.id}`} className="text-hema hover:underline">{s.dispensing.number}</Link> : null],
              ["Notes", s.notes],
            ]}
          />
        </Sheet>
      </div>
    </>
  );
}

export async function SaleNewPage() {
  const { me, allowed } = await pageFor("sales.create");
  if (!allowed) return <NoAccess what="selling" />;
  const [medicines, customers] = await Promise.all([load<Medicine[]>("/medicines?state=active&rxClass=otc"), load<PatientRow[]>("/patients?limit=500")]);
  return (
    <>
      <PageHeader crumbs={[{ href: "/sales", label: "Sales" }]} title="Counter sale">
        Over-the-counter medicines only. For a prescription medicine, receive the prescription: it&apos;s checked, then dispensed.
      </PageHeader>
      <Sheet className="max-w-[50rem] px-5 py-6 sm:px-8">
        <SaleForm
          org={me.org}
          medicines={medicines.map((m) => ({ id: m.id, label: m.label, unit: m.unit, priceCentavos: m.priceCentavos, available: m.available ?? 0 }))}
          customers={customers.map((c) => ({ id: c.id, fullName: c.fullName }))}
        />
      </Sheet>
    </>
  );
}
