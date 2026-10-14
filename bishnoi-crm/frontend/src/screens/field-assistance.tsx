import { PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { can } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { AssistanceBoard } from "../components/field/assistance-board";
import type { AssistanceList, Doctors } from "../components/field/types";

export const metadata = { title: "Patient assistance" };

/**
 * Government assistance applications (PAP, Rx playbook KPI 3): filed for a
 * doctor's patient on a GetMeds product, followed up weekly, and approved with
 * a confirmation receipt. Each approval is a point for the month it came in.
 */
export default async function FieldAssistancePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const me = await getCompanyMe();
  if (!can(me, "visits.view")) return <NoAccess what="patient assistance" />;
  const { status } = await searchParams;
  const shown = ["pending", "approved", "denied"].includes(String(status)) ? String(status) : "";
  const [data, doctors] = await Promise.all([
    load<AssistanceList>(`/assistance${shown ? `?status=${shown}` : ""}`),
    can(me, "visits.create") ? load<Doctors>("/field/doctors?limit=500&sort=plan") : Promise.resolve({ items: [], total: 0, owedCentavos: 0 } as Doctors),
  ]);
  const fmt = makeFormat(me.org);
  const month = `${fmt.monthLabel(data.month)} ${data.month.slice(0, 4)}`;
  const days = new Set(data.items.flatMap((a) => [a.submittedOn, a.decidedOn].filter((d): d is string => !!d)));
  const dateLabel = Object.fromEntries([...days].map((d) => [d, fmt.dateLabel(d)]));
  const figures = [
    { value: data.counts.approved, label: "Approved", note: `${month}: 1 point each`, tone: "text-filed" },
    { value: data.counts.pending, label: "Pending", note: "Follow up weekly", tone: data.counts.pending ? "text-[#8a5a00]" : "text-ink" },
    { value: data.counts.denied, label: "Denied", note: `${month}: count if resubmitted and approved`, tone: "text-ink" },
    { value: data.counts.submitted, label: "Submitted", note: month, tone: "text-ink" },
  ];
  return (
    <>
      <PageHeader title="Patient assistance">
        Government help for a doctor&apos;s patients on GetMeds products: DSWD, PCSO, the Office of the Vice President and YAKAP. Every approved application is a point for the month.
      </PageHeader>
      <Sheet className="mb-5 grid grid-cols-2 gap-px overflow-hidden bg-rule sm:grid-cols-4 [&>*]:bg-sheet">
        {figures.map((f) => (
          <div key={f.label} className="px-5 py-4">
            <span className={`block text-figure tabular-nums ${f.tone}`}>{f.value}</span>
            <span className="block text-sm text-ink">{f.label}</span>
            <span className="block text-meta text-ink-3">{f.note}</span>
          </div>
        ))}
      </Sheet>
      <div className="mb-4">
        <ToggleLinks
          current={shown}
          options={[
            { value: "", label: "All", href: "/field/assistance" },
            { value: "pending", label: "Pending", href: "/field/assistance?status=pending" },
            { value: "approved", label: "Approved", href: "/field/assistance?status=approved" },
            { value: "denied", label: "Denied", href: "/field/assistance?status=denied" },
          ]}
        />
      </div>
      <AssistanceBoard data={data} doctors={doctors.items.map((d) => ({ id: d.id, name: d.name }))} today={fmt.todayKey()} dateLabel={dateLabel} />
    </>
  );
}
