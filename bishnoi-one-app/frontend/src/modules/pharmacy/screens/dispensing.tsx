import Link from "next/link";
import { Flag } from "@/src/modules/pharmacy/platform/ui/marks";
import { Empty, PageHeader, Sheet } from "@/src/modules/pharmacy/platform/ui/sheet";
import { enc, load } from "@/src/modules/pharmacy/platform/lib/api";
import { Head, NoAccess, SearchBar, Tabs } from "@/src/modules/pharmacy/components/bits";
import { pageFor, param, type Search } from "@/src/modules/pharmacy/lib/page";
import type { Dispensing, PrescriptionSummary } from "@/src/modules/pharmacy/lib/types";

export const metadata = { title: "Dispensing" };

const VIEWS = {
  queue: { label: "Dispensing queue", empty: "Nothing waiting to be dispensed", hint: "Verified prescriptions, first verified first." },
  partial: { label: "Partially dispensed", empty: "Nothing part-way", hint: "Some handed over; the rest waits, usually for stock." },
  dispensed: { label: "Dispensed", empty: "Nothing fully dispensed yet", hint: "Everything on them has been handed over." },
  history: { label: "Dispensing history", empty: "Nothing dispensed yet", hint: "Every hand-over, newest first." },
} as const;
type View = keyof typeof VIEWS;

/** Only verified prescriptions reach this page: checking happens in Prescriptions, first. */
export default async function DispensingPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("dispensing.view");
  if (!allowed) return <NoAccess what="dispensing" />;
  const search = await searchParams;
  const view = (param(search, "view", "queue") in VIEWS ? param(search, "view", "queue") : "queue") as View;
  const q = param(search, "q");
  const query = q ? `&q=${enc(q)}` : "";
  const [queue, partial] = await Promise.all([
    load<PrescriptionSummary[]>(`/dispensing/queue?view=queue${view === "queue" ? query : ""}`),
    load<PrescriptionSummary[]>(`/dispensing/queue?view=partial${view === "partial" ? query : ""}`),
  ]);
  const rows =
    view === "queue" ? queue : view === "partial" ? partial : view === "dispensed" ? await load<PrescriptionSummary[]>(`/dispensing/queue?view=dispensed${query}`) : [];
  const history = view === "history" ? await load<Dispensing[]>(`/dispensing?limit=200${query}`) : [];
  const canDispense = may("dispensing.create");

  return (
    <>
      <PageHeader title="Dispensing">
        Verified prescriptions wait here. Dispensing picks the batch each medicine comes from and records the sale.
      </PageHeader>
      <Tabs
        label="Dispensing"
        current={view}
        tabs={(Object.keys(VIEWS) as View[]).map((v) => ({
          value: v,
          label: VIEWS[v].label,
          href: `/pharmacy/dispensing?view=${v}`,
          count: v === "queue" ? queue.length : v === "partial" ? partial.length : undefined,
        }))}
      />
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SearchBar q={q} placeholder={view === "history" ? "DS or RX number, or patient" : "RX number or patient"} keep={{ view }} />
        <p className="text-meta text-ink-3">{VIEWS[view].hint}</p>
      </div>

      <Sheet>
        {view === "history" ? (
          history.length === 0 ? (
            <Empty icon="dispensing" title={q ? "Nothing matches" : VIEWS.history.empty} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[46rem] text-left text-sm">
                <Head columns={["Dispensing", "Patient", "Medicines", "By", { label: "When", right: true }]} />
                <tbody className="divide-y divide-rule">
                  {history.map((d) => (
                    <tr key={d.id} className="relative hover:bg-bench/40">
                      <td className="py-3 pr-3 pl-5 align-top">
                        <Link href={`/pharmacy/dispensing/${d.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                          {d.number}
                        </Link>
                        <span className="block text-meta text-ink-3">on {d.prescription.number}</span>
                      </td>
                      <td className="px-3 py-3 align-top">{d.patient.fullName}</td>
                      <td className="max-w-[20rem] px-3 py-3 align-top text-ink-2">
                        {d.lines.map((l) => `${l.medicine} × ${l.quantity} (lot ${l.lotNo})`).join(" · ")}
                      </td>
                      <td className="px-3 py-3 align-top text-ink-2">{d.dispensedBy?.name ?? "—"}</td>
                      <td className="py-3 pr-5 pl-3 text-right align-top text-meta whitespace-nowrap text-ink-2">{fmt.whenLabel(d.dispensedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : rows.length === 0 ? (
          <Empty icon="dispensing" title={q ? "Nothing matches" : VIEWS[view].empty}>
            {view === "queue" && !q ? "A prescription lands here once a pharmacist verifies it." : null}
          </Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {rows.map((rx) => (
              <li key={rx.id} className="grid gap-2 px-5 py-3.5 md:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_auto] md:items-center md:gap-5">
                <div className="min-w-0">
                  <Link href={`/pharmacy/prescriptions/${rx.id}`} className="font-semibold text-hema hover:underline">
                    {rx.number}
                  </Link>
                  <span className="block truncate text-sm">{rx.patient.fullName}</span>
                  {rx.patient.allergies && <span className="block text-meta font-semibold text-eosin">Allergy: {rx.patient.allergies}</span>}
                </div>
                <div className="min-w-0 text-sm text-ink-2">
                  {rx.items.map((i) => (
                    <span key={i.writtenAs} className="block truncate">
                      {i.writtenAs} · {view === "dispensed" ? `${i.quantity} given` : `${i.remaining} of ${i.quantity} still owed`}
                    </span>
                  ))}
                  <span className="mt-0.5 block text-meta text-ink-3">
                    Verified {rx.checkedAt ? fmt.whenLabel(rx.checkedAt).toLowerCase() : ""}
                    {rx.checkedBy ? ` by ${rx.checkedBy.name}` : ""}
                  </span>
                </div>
                <div className="flex items-center gap-3 md:justify-end">
                  {view !== "dispensed" && rx.ready === false && <Flag letter="!">Short on stock</Flag>}
                  {view !== "dispensed" && canDispense && (
                    <Link href={`/pharmacy/dispensing/new?rx=${rx.id}`} className="inline-flex h-8 items-center rounded-[3px] bg-hema px-3 text-meta font-semibold text-white hover:bg-hema-hover">
                      {view === "partial" ? "Dispense the rest" : "Dispense"}
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}
