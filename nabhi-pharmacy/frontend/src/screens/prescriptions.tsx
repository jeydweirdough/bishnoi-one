import { ClipboardPlus } from "lucide-react";
import Link from "next/link";
import { LinkButton } from "@/src/platform/ui/button";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { enc, load } from "@/src/platform/lib/api";
import { DispenseMark, Head, NoAccess, RxStatusMark, SearchBar, Tabs } from "../components/bits";
import { pageFor, param, type Search } from "../lib/page";
import { itemsLine } from "../lib/words";
import type { PrescriptionCounts, PrescriptionSummary } from "../lib/types";

export const metadata = { title: "Prescriptions" };

const VIEWS = {
  inbox: { label: "Inbox", empty: "Nothing waiting to be checked", hint: "Oldest first: the next one to check is at the top." },
  pending: { label: "Pending verification", empty: "Nothing half-checked", hint: "Checking started and saved part-way." },
  verified: { label: "Verified", empty: "Nothing verified yet", hint: "Passed every check. They wait in Dispensing until handed over." },
  attention: { label: "Rejected / Needs clarification", empty: "Nothing held up", hint: "Held for a question to the prescriber or patient, or turned down." },
  history: { label: "History", empty: "No prescriptions yet", hint: "Every prescription taken in, newest first." },
} as const;
type View = keyof typeof VIEWS;

export default async function PrescriptionsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("prescriptions.view");
  if (!allowed) return <NoAccess what="prescriptions" />;
  const search = await searchParams;
  const view = (param(search, "view", "inbox") in VIEWS ? param(search, "view", "inbox") : "inbox") as View;
  const q = param(search, "q");
  const [rows, counts] = await Promise.all([
    load<PrescriptionSummary[]>(`/prescriptions?view=${view}${q ? `&q=${enc(q)}` : ""}`),
    load<PrescriptionCounts>("/prescriptions/counts"),
  ]);
  const checker = may("prescriptions.verify");

  return (
    <>
      <PageHeader
        title="Prescriptions"
        actions={
          may("prescriptions.create") && (
            <LinkButton href="/prescriptions/new" variant="primary" icon={<ClipboardPlus className="size-4" aria-hidden />}>
              Receive prescription
            </LinkButton>
          )
        }
      >
        Every prescription is checked and verified here before anything is dispensed on it.
      </PageHeader>
      <Tabs
        label="Prescriptions"
        current={view}
        tabs={(Object.keys(VIEWS) as View[]).map((v) => ({
          value: v,
          label: VIEWS[v].label,
          href: `/prescriptions?view=${v}`,
          count: v === "history" || v === "verified" ? undefined : counts[v],
        }))}
      />
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <SearchBar q={q} placeholder="RX number, patient or prescriber" keep={{ view }} />
        <p className="text-meta text-ink-3">{VIEWS[view].hint}</p>
      </div>

      <Sheet>
        {rows.length === 0 ? (
          <Empty icon="prescriptions" title={q ? "No prescriptions match" : VIEWS[view].empty} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <Head columns={["Prescription", "Patient", "Medicines", view === "verified" ? "Dispensing" : "Status", { label: "Received", right: true }]} />
              <tbody className="divide-y divide-rule">
                {rows.map((rx) => (
                  <tr key={rx.id} className="relative hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5 align-top">
                      <Link href={`/prescriptions/${rx.id}`} className="font-semibold whitespace-nowrap text-hema after:absolute after:inset-0 hover:underline">
                        {rx.number}
                      </Link>
                      <span className="block text-meta text-ink-3">{rx.prescriberName}</span>
                    </td>
                    <td className="px-3 py-3 align-top">
                      {rx.patient.fullName}
                      {rx.patient.allergies && <span className="block text-meta font-semibold text-eosin">Allergy: {rx.patient.allergies}</span>}
                    </td>
                    <td className="max-w-[18rem] px-3 py-3 align-top text-ink-2">{itemsLine(rx.items)}</td>
                    <td className="px-3 py-3 align-top">
                      {view === "verified" ? <DispenseMark state={rx.dispensed} /> : <RxStatusMark status={rx.status} />}
                      {rx.checkedBy && rx.status !== "received" && <span className="mt-1 block text-meta text-ink-3">by {rx.checkedBy.name}</span>}
                    </td>
                    <td className="py-3 pr-5 pl-3 text-right align-top text-meta whitespace-nowrap text-ink-2">
                      {fmt.whenLabel(rx.receivedAt)}
                      {(view === "inbox" || view === "pending") && checker && (
                        <span className="relative z-10 mt-1 block">
                          <Link href={`/prescriptions/${rx.id}`} className="font-semibold text-hema hover:underline">
                            {view === "inbox" ? "Check" : "Continue checking"}
                          </Link>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Sheet>
    </>
  );
}
