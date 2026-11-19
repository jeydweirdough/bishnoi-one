import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Printer } from "lucide-react";
import { accountSend } from "@/src/platform/lib/account";
import { LinkButton } from "@/src/platform/ui/button";
import { Sheet } from "@/src/platform/ui/sheet";
import { OneFrame } from "@/src/one/menu/one-frame";
import { SlipActions } from "@/src/one/approvals/slip-actions";
import { SlipAttachments, SlipStamp, SlipSteps, SlipSummary } from "@/src/one/approvals/slip-view";
import type { Slip } from "@/src/one/approvals/types";

export const metadata: Metadata = { title: "Approval slip" };

/** One approval slip (Step 4C): what is asked, its steps, what proves it, and Sign or Return for whoever's turn it is. */
export default async function ApprovalSlip({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let slip: Slip;
  try {
    slip = await accountSend<Slip>("GET", `/identity/approvals/${encodeURIComponent(id)}`);
  } catch {
    notFound();
  }
  return (
    <OneFrame>
      <nav aria-label="Breadcrumb" className="mb-1 text-meta">
        <Link href="/approvals" className="text-ink-2 hover:text-ink hover:underline">Approvals</Link>
      </nav>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-title text-ink">{slip.number}</h1>
          <p className="mt-1 text-ink-2">
            <SlipStamp slip={slip} /> <span className="ml-1">{slip.title}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {slip.record.url && <LinkButton href={slip.record.url}>Open {slip.kindLabel.toLowerCase()}</LinkButton>}
          <LinkButton href={`/approvals/${slip.id}/print`} prefetch={false} icon={<Printer className="size-4" aria-hidden />}>
            Print
          </LinkButton>
        </div>
      </div>
      {slip.replaces && (
        <p className="mb-4 rounded-[3px] bg-bench px-4 py-2 text-sm text-ink">
          Sent again after <Link href={`/approvals/${slip.replaces.id}`} className="font-semibold text-hema hover:underline">{slip.replaces.number}</Link> was returned
          {slip.replaces.note ? `: ${slip.replaces.note}` : "."}
        </p>
      )}
      {slip.status === "returned" && slip.note && <p className="mb-4 rounded-[3px] bg-danger-tint px-4 py-2 text-sm text-ink">Returned: {slip.note}</p>}
      {slip.status === "cancelled" && <p className="mb-4 rounded-[3px] bg-bench px-4 py-2 text-sm text-ink">Cancelled{slip.note ? `: ${slip.note}` : "."}</p>}
      <div className="grid gap-5 lg:grid-cols-3">
        <Sheet className="px-5 py-4 lg:col-span-2">
          <p className="mb-2 text-caps text-ink-3 uppercase">The request</p>
          <SlipSummary slip={slip} />
          <SlipActions id={slip.id} number={slip.number} canSign={slip.canSign} actingAs={slip.actingAs} canAddFiles={slip.canAddFiles} />
        </Sheet>
        <div className="space-y-5">
          <Sheet className="px-5 py-4">
            <p className="mb-3 text-caps text-ink-3 uppercase">Steps</p>
            <SlipSteps slip={slip} />
          </Sheet>
          <Sheet className="px-5 py-4">
            <p className="mb-2 text-caps text-ink-3 uppercase">Attached</p>
            <SlipAttachments slip={slip} />
          </Sheet>
        </div>
      </div>
    </OneFrame>
  );
}
