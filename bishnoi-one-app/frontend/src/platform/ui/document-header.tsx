import type { ReactNode } from "react";

// One document header (feature plan step 8): the same few facts in the same place on every stock
// document (receipts, orders, transfers, adjustments, counts), in every module that has them.

export type DocumentHeader = {
  operationType: { id: string; code: string; name: string; kind: string } | null;
  scheduledOn: string | null;
  doneAt: string | null;
  sourceDocument: string | null;
  responsible: { id: string; name: string } | null;
  timing: "late" | "on_time" | "overdue" | "due" | null;
};

const TIMING: Record<NonNullable<DocumentHeader["timing"]>, { label: string; tone: string }> = {
  late: { label: "Done late", tone: "border-danger text-danger" },
  on_time: { label: "On time", tone: "border-hema text-hema" },
  overdue: { label: "Overdue", tone: "border-danger text-danger" },
  due: { label: "Scheduled", tone: "border-ink-2 text-ink-2" },
};

export const TIMING_OPTIONS = [
  { value: "", label: "Any time" },
  { value: "overdue", label: "Overdue" },
  { value: "due", label: "Scheduled, not done" },
  { value: "late", label: "Done late" },
  { value: "on_time", label: "Done on time" },
];

const day = (iso: string) => new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeZone: "Asia/Manila" }).format(new Date(iso.length === 10 ? `${iso}T00:00:00+08:00` : iso));
const moment = (iso: string) => new Intl.DateTimeFormat("en-PH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Manila" }).format(new Date(iso));

export function TimingMark({ timing }: { timing: DocumentHeader["timing"] }) {
  if (!timing) return null;
  const t = TIMING[timing];
  return <span className={`inline-flex h-5 items-center rounded-full border px-2 text-stamp whitespace-nowrap uppercase ${t.tone}`}>{t.label}</span>;
}

/** The header as a strip of labelled facts, under a document's title. `source` may link the source document. */
export function DocumentHeaderStrip({ header, source }: { header: DocumentHeader | null | undefined; source?: ReactNode }) {
  if (!header) return null;
  const facts: [string, ReactNode][] = [
    ["Operation", header.operationType?.name ?? "—"],
    ["Scheduled", header.scheduledOn ? day(header.scheduledOn) : "—"],
    ["Done", header.doneAt ? moment(header.doneAt) : "Not yet"],
    ["Source document", source ?? header.sourceDocument ?? "—"],
    ["Responsible", header.responsible?.name ?? "—"],
  ];
  return (
    <dl className="mb-4 grid grid-cols-2 gap-x-6 gap-y-2 rounded-xl border border-rule bg-sheet px-5 py-3 sm:grid-cols-3 lg:grid-cols-[repeat(5,minmax(0,1fr))_auto]">
      {facts.map(([label, value]) => (
        <div key={label} className="min-w-0">
          <dt className="text-meta text-ink-3">{label}</dt>
          <dd className="truncate text-sm font-medium text-ink">{value}</dd>
        </div>
      ))}
      <div className="flex items-center">
        <TimingMark timing={header.timing} />
      </div>
    </dl>
  );
}
