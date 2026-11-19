import type { Metadata } from "next";
import Link from "next/link";
import { accountSend } from "@/src/platform/lib/account";
import { Empty, Sheet } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { OneFrame } from "@/src/one/menu/one-frame";
import { fmtOf, SlipStamp } from "@/src/one/approvals/slip-view";
import type { SlipBrief } from "@/src/one/approvals/types";

export const metadata: Metadata = { title: "Approvals" };

type Box = "waiting" | "mine" | "done" | "all";
const BOXES: { value: Box; label: string }[] = [
  { value: "waiting", label: "Waiting on me" },
  { value: "mine", label: "My requests" },
  { value: "done", label: "Finished" },
];
const EMPTY: Record<Box, { title: string; says: string }> = {
  waiting: { title: "Nothing waits on you", says: "When someone you approve for sends a request, it shows here." },
  mine: { title: "No requests yet", says: "A sales order sent for approval opens its slip here." },
  done: { title: "Nothing finished yet", says: "Approved, returned and cancelled slips you took part in show here." },
  all: { title: "Nothing waiting at the company", says: "Every waiting slip shows here for administrators." },
};

/**
 * One approvals inbox (Step 4C): every approval slip, whatever app its record is in. Waiting on me, my requests,
 * finished; administrators also see everything waiting at the company.
 */
export default async function Approvals({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const s = await searchParams;
  const box: Box = (["waiting", "mine", "done", "all"] as const).find((b) => b === s.box) ?? "waiting";
  let data: { items: SlipBrief[]; isAdmin: boolean } | null = null;
  try {
    data = await accountSend("GET", `/identity/approvals?box=${box}`);
  } catch {
    data = null;
  }
  const boxes = data?.isAdmin ? [...BOXES, { value: "all" as Box, label: "All waiting" }] : BOXES;
  return (
    <OneFrame>
      <h1 className="text-[2rem] leading-tight font-semibold tracking-[-0.02em] text-ink">Approvals</h1>
      <div className="mt-5 mb-4">
        <ToggleLinks current={box} options={boxes.map((b) => ({ value: b.value, label: b.label, href: `/approvals?box=${b.value}` }))} />
      </div>
      <Sheet>
        {data === null ? (
          <p className="px-5 py-6 text-sm text-ink-2">Bishnoi One can&apos;t be reached right now. Try again in a moment.</p>
        ) : data.items.length === 0 ? (
          <Empty title={EMPTY[box].title} icon="approvals">{EMPTY[box].says}</Empty>
        ) : (
          <ul className="divide-y divide-rule">
            {data.items.map((a) => {
              const fmt = fmtOf(a);
              return (
                <li key={a.id}>
                  <Link href={`/approvals/${a.id}`} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 px-5 py-3 hover:bg-bench">
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-ink">
                        {a.number} <span className="font-normal text-ink-2">· {a.title}</span>
                      </span>
                      <span className="block text-meta text-ink-3">
                        {a.kindLabel} · requested by {a.requestedBy.name}, {fmt.whenLabel(a.createdAt)}
                      </span>
                    </span>
                    <span className="flex items-center gap-3">
                      {a.summary.totalCentavos != null && <span className="text-sm font-medium tabular-nums">{fmt.peso(a.summary.totalCentavos)}</span>}
                      <SlipStamp slip={a} />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </Sheet>
    </OneFrame>
  );
}
