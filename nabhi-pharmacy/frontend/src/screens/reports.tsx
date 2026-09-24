import Link from "next/link";
import type { ReactNode } from "react";
import { Bars } from "@/src/platform/ui/bars";
import { Button } from "@/src/platform/ui/button";
import { Flag } from "@/src/platform/ui/marks";
import { Empty, PageHeader, SectionTitle, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import type { Format } from "@/src/platform/lib/format";
import { BatchStatusMark, FilterInput, Head, NoAccess, Tabs } from "../components/bits";
import { pageFor, param, type Search } from "../lib/page";
import { PAYMENT_METHODS, PRESCRIPTION_STATUSES } from "../lib/words";
import type { BatchStatus, PaymentMethod, PrescriptionStatus } from "../lib/types";

export const metadata = { title: "Reports" };

const REPORTS = {
  prescriptions: "Prescription reports",
  dispensing: "Dispensing reports",
  sales: "Sales reports",
  usage: "Medicine usage",
  expiry: "Expiry reports",
  stock: "Stock reports",
} as const;
type Name = keyof typeof REPORTS;

// Each report's answer, as the API sends it.
type PerDay = { day: string; count: number; units?: number; totalCentavos?: number };
type Report = { name: Name; from: string; to: string } & Record<string, unknown>;

/** A day-by-day column chart: one hue, the count printed on hover and in the table below it. */
function Days({ rows, value, fmt, money }: { rows: PerDay[]; value: (r: PerDay) => number; fmt: Format; money?: boolean }) {
  const max = Math.max(...rows.map(value), 1);
  return (
    <div className="mt-3" role="img" aria-label="Per day, oldest on the left">
      <div className="flex h-28 items-end gap-px">
        {rows.map((r) => {
          const v = value(r);
          return (
            <div
              key={r.day}
              title={`${fmt.dateLabel(r.day)}: ${money ? fmt.peso(v) : v}`}
              className="min-w-0 flex-1 rounded-t-[2px] bg-hema"
              style={{ height: `${v <= 0 ? 0 : Math.max(3, (v / max) * 100)}%` }}
            />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-meta text-ink-3">
        <span>{fmt.dateLabel(rows[0]?.day ?? "")}</span>
        <span>{fmt.dateLabel(rows[rows.length - 1]?.day ?? "")}</span>
      </div>
    </div>
  );
}

function Numbers({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="grid grid-cols-2 divide-rule sm:grid-cols-4 sm:divide-x">
      {items.map(([label, value]) => (
        <div key={label} className="px-5 py-4">
          <span className="block text-figure text-ink">{value}</span>
          <span className="mt-0.5 block text-meta text-ink-3">{label}</span>
        </div>
      ))}
    </div>
  );
}

export default async function ReportsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed } = await pageFor("reports.view");
  if (!allowed) return <NoAccess what="reports" />;
  const search = await searchParams;
  const name = (param(search, "r", "prescriptions") in REPORTS ? param(search, "r", "prescriptions") : "prescriptions") as Name;
  const today = fmt.todayKey();
  const from = param(search, "from");
  const to = param(search, "to");
  const r = await load<Report>(`/reports/${name}?${from ? `from=${enc(from)}&` : ""}${to ? `to=${enc(to)}` : ""}`);
  const range = name === "expiry" ? `On the shelf and expired, or expiring by ${fmt.dateLabel(r.to)}` : `${fmt.dateLabel(r.from)} – ${fmt.dateLabel(r.to)}`;
  const keep = `${from ? `&from=${enc(from)}` : ""}${to ? `&to=${enc(to)}` : ""}`;

  return (
    <>
      <PageHeader title="Reports">Every report covers the days chosen below, the pharmacy&apos;s own days. The last 30 days unless you pick others.</PageHeader>
      <Tabs label="Reports" current={name} tabs={(Object.keys(REPORTS) as Name[]).map((n) => ({ value: n, label: REPORTS[n], href: `/reports?r=${n}${keep}` }))} />
      <form className="mb-4 flex flex-wrap items-end gap-3">
        <input type="hidden" name="r" value={name} />
        {name !== "expiry" && <FilterInput label="From" type="date" name="from" defaultValue={from || r.from} />}
        <FilterInput label={name === "expiry" ? "Expired or expiring by" : "To"} type="date" name="to" defaultValue={to || r.to} max={name === "expiry" ? undefined : today} />
        <Button type="submit" size="sm">
          Show
        </Button>
        <p className="pb-2 text-meta text-ink-3">{range}</p>
      </form>

      {name === "prescriptions" && <PrescriptionsReport r={r} fmt={fmt} />}
      {name === "dispensing" && <DispensingReport r={r} fmt={fmt} />}
      {name === "sales" && <SalesReport r={r} fmt={fmt} />}
      {name === "usage" && <UsageReport r={r} fmt={fmt} />}
      {name === "expiry" && <ExpiryReport r={r} fmt={fmt} />}
      {name === "stock" && <StockReport r={r} fmt={fmt} />}
    </>
  );
}

function PrescriptionsReport({ r, fmt }: { r: Report; fmt: Format }) {
  const by = r.byStatus as Partial<Record<PrescriptionStatus, number>>;
  const checkers = r.byChecker as ({ name: string } & Partial<Record<PrescriptionStatus, number>>)[];
  const prescribers = r.topPrescribers as { name: string; count: number }[];
  return (
    <div className="space-y-4">
      <Sheet>
        <Numbers
          items={[
            ["Received", r.received as number],
            ["Verified", by.verified ?? 0],
            ["Held / rejected", (by.needs_clarification ?? 0) + (by.rejected ?? 0)],
            ["Hours to verify, on average", (r.averageHoursToVerify as number | null) ?? "—"],
          ]}
        />
        <div className="border-t border-rule px-5 pt-4 pb-5">
          <SectionTitle>Received per day</SectionTitle>
          <Days rows={r.perDay as PerDay[]} value={(d) => d.count} fmt={fmt} />
        </div>
      </Sheet>
      <div className="grid gap-4 lg:grid-cols-2">
        <Sheet className="px-5 py-5">
          <SectionTitle>Where they stand now</SectionTitle>
          <Bars rows={(Object.keys(PRESCRIPTION_STATUSES) as PrescriptionStatus[]).map((s) => ({ label: PRESCRIPTION_STATUSES[s], value: by[s] ?? 0, flag: s === "needs_clarification" }))} />
        </Sheet>
        <Sheet className="px-5 py-5">
          <SectionTitle>Top prescribers</SectionTitle>
          {prescribers.length ? <Bars rows={prescribers.map((p) => ({ label: p.name, value: p.count }))} unit="Rx" /> : <p className="mt-2 text-meta text-ink-3">None in these days.</p>}
        </Sheet>
      </div>
      <Sheet>
        <div className="px-5 pt-5">
          <SectionTitle icon="people">Checked, by pharmacist</SectionTitle>
        </div>
        {checkers.length === 0 ? (
          <p className="px-5 py-4 text-meta text-ink-3">Nothing checked in these days.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <Head columns={["Pharmacist", { label: "Verified", right: true }, { label: "Clarification", right: true }, { label: "Rejected", right: true }, { label: "Pending", right: true }]} />
            <tbody className="divide-y divide-rule">
              {checkers.map((c) => (
                <tr key={c.name}>
                  <td className="py-2.5 pr-3 pl-5">{c.name}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{c.verified ?? 0}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{c.needs_clarification ?? 0}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{c.rejected ?? 0}</td>
                  <td className="py-2.5 pr-5 pl-3 text-right tabular-nums">{c.pending ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Sheet>
    </div>
  );
}

function DispensingReport({ r, fmt }: { r: Report; fmt: Format }) {
  const people = r.byPharmacist as { name: string; count: number; units: number }[];
  return (
    <div className="space-y-4">
      <Sheet>
        <Numbers items={[["Dispensings", r.dispensings as number], ["Units handed over", r.units as number], ["Prescriptions served", r.prescriptions as number], ["Days", (r.perDay as PerDay[]).length]]} />
        <div className="border-t border-rule px-5 pt-4 pb-5">
          <SectionTitle>Units dispensed per day</SectionTitle>
          <Days rows={r.perDay as PerDay[]} value={(d) => d.units ?? 0} fmt={fmt} />
        </div>
      </Sheet>
      <Sheet className="px-5 py-5">
        <SectionTitle icon="people">By pharmacist</SectionTitle>
        {people.length ? <Bars rows={people.map((p) => ({ label: `${p.name} · ${p.count} dispensings`, value: p.units }))} unit="units" /> : <p className="mt-2 text-meta text-ink-3">Nothing dispensed in these days.</p>}
      </Sheet>
    </div>
  );
}

function SalesReport({ r, fmt }: { r: Report; fmt: Format }) {
  const methods = r.byPaymentMethod as Partial<Record<PaymentMethod, number>>;
  const sources = r.bySource as Partial<Record<"counter" | "dispensing", number>>;
  return (
    <div className="space-y-4">
      <Sheet>
        <Numbers
          items={[
            ["Sales", r.count as number],
            ["Gross", fmt.peso(r.grossCentavos as number)],
            ["Discounts and refunds", fmt.peso((r.discountCentavos as number) + (r.refundCentavos as number))],
            ["Net", fmt.peso(r.netCentavos as number)],
          ]}
        />
        <div className="border-t border-rule px-5 pt-4 pb-5">
          <SectionTitle>Sales per day</SectionTitle>
          <Days rows={r.perDay as PerDay[]} value={(d) => d.totalCentavos ?? 0} fmt={fmt} money />
        </div>
      </Sheet>
      <div className="grid gap-4 lg:grid-cols-2">
        <Sheet className="px-5 py-5">
          <SectionTitle>By payment</SectionTitle>
          <ul className="mt-2 divide-y divide-rule text-sm">
            {(Object.keys(PAYMENT_METHODS) as PaymentMethod[]).map((m) => (
              <li key={m} className="flex justify-between py-2">
                <span className="text-ink-2">{PAYMENT_METHODS[m]}</span>
                <span className="tabular-nums">{fmt.peso(methods[m] ?? 0)}</span>
              </li>
            ))}
          </ul>
        </Sheet>
        <Sheet className="px-5 py-5">
          <SectionTitle>Counter and dispensing</SectionTitle>
          <ul className="mt-2 divide-y divide-rule text-sm">
            <li className="flex justify-between py-2">
              <span className="text-ink-2">Over the counter</span>
              <span className="tabular-nums">{fmt.peso(sources.counter ?? 0)}</span>
            </li>
            <li className="flex justify-between py-2">
              <span className="text-ink-2">Through dispensing</span>
              <span className="tabular-nums">{fmt.peso(sources.dispensing ?? 0)}</span>
            </li>
          </ul>
        </Sheet>
      </div>
    </div>
  );
}

function UsageReport({ r, fmt }: { r: Report; fmt: Format }) {
  const items = r.items as { medicine: { id: string; label: string; unit: string }; dispensed: number; counter: number; units: number; valueCentavos: number }[];
  return (
    <Sheet>
      {items.length === 0 ? (
        <Empty icon="medicines" title="Nothing went out in these days" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <Head columns={["Medicine", { label: "Dispensed", right: true }, { label: "Counter", right: true }, { label: "Total", right: true }, { label: "Value", right: true }]} />
            <tbody className="divide-y divide-rule">
              {items.map((i) => (
                <tr key={i.medicine.id}>
                  <td className="py-3 pr-3 pl-5">
                    <Link href={`/medicines/${i.medicine.id}`} className="font-semibold text-hema hover:underline">
                      {i.medicine.label}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{i.dispensed}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{i.counter}</td>
                  <td className="px-3 py-3 text-right font-semibold tabular-nums">
                    {i.units} <span className="font-normal text-meta text-ink-3">{i.medicine.unit}</span>
                  </td>
                  <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(i.valueCentavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Sheet>
  );
}

function ExpiryReport({ r, fmt }: { r: Report; fmt: Format }) {
  const items = r.items as { batchId: string; medicine: { id: string; label: string; unit: string }; lotNo: string; expiresOn: string; expired: boolean; qtyOnHand: number; valueCentavos: number; status: BatchStatus }[];
  return (
    <div className="space-y-4">
      <Sheet>
        <Numbers
          items={[
            ["Batches", items.length],
            ["Already expired", items.filter((i) => i.expired).length],
            ["Expired, at cost", fmt.peso(r.expiredValueCentavos as number)],
            ["Expiring, at cost", fmt.peso(r.expiringValueCentavos as number)],
          ]}
        />
      </Sheet>
      <Sheet>
        {items.length === 0 ? (
          <Empty icon="batches" title="Nothing expires in these days" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <Head columns={["Medicine & lot", "Expires", "Status", { label: "On hand", right: true }, { label: "Value", right: true }]} />
              <tbody className="divide-y divide-rule">
                {items.map((i) => (
                  <tr key={i.batchId}>
                    <td className="py-3 pr-3 pl-5">
                      <Link href={`/medicines/${i.medicine.id}`} className="font-semibold text-hema hover:underline">
                        {i.medicine.label}
                      </Link>
                      <span className="block text-meta text-ink-3">Lot {i.lotNo}</span>
                    </td>
                    <td className="px-3 py-3">{i.expired ? <Flag letter="!">{fmt.dateLabel(i.expiresOn)}</Flag> : fmt.dateLabel(i.expiresOn)}</td>
                    <td className="px-3 py-3">
                      <BatchStatusMark status={i.status} expired={i.expired} />
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">{i.qtyOnHand}</td>
                    <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(i.valueCentavos)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </div>
  );
}

function StockReport({ r, fmt }: { r: Report; fmt: Format }) {
  const items = r.items as { medicine: { id: string; label: string; unit: string; code: string }; onHand: number; available: number; reorderLevel: number; low: boolean; valueCentavos: number; unitsOut: number }[];
  return (
    <div className="space-y-4">
      <Sheet>
        <Numbers items={[["Medicines", items.length], ["Low on stock", r.lowCount as number], ["Stock value, at cost", fmt.peso(r.valueCentavos as number)], ["Units out in these days", items.reduce((s, i) => s + i.unitsOut, 0)]]} />
      </Sheet>
      <Sheet>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <Head columns={["Medicine", { label: "On hand", right: true }, { label: "Available", right: true }, { label: "Reorder at", right: true }, { label: "Out in period", right: true }, { label: "Value", right: true }]} />
            <tbody className="divide-y divide-rule">
              {items.map((i) => (
                <tr key={i.medicine.id}>
                  <td className="py-3 pr-3 pl-5">
                    <Link href={`/medicines/${i.medicine.id}`} className="font-semibold text-hema hover:underline">
                      {i.medicine.label}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{i.onHand}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{i.low ? <Flag letter="!">{i.available}</Flag> : i.available}</td>
                  <td className="px-3 py-3 text-right text-ink-2 tabular-nums">{i.reorderLevel}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{i.unitsOut}</td>
                  <td className="py-3 pr-5 pl-3 text-right tabular-nums">{fmt.peso(i.valueCentavos)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Sheet>
    </div>
  );
}
