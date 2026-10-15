import Link from "next/link";
import { Empty, PageHeader, Sheet } from "@/src/platform/ui/sheet";
import { load } from "@/src/platform/lib/api";
import { Head, MaterialReviewMark, NoAccess, Tabs } from "../components/bits";
import { pageFor, param, type Search } from "../lib/page";
import type { MaterialReview, MaterialReviewStatus } from "../lib/types";

export const metadata = { title: "Promotional materials" };

const VIEWS = {
  waiting: { label: "For review", empty: "No designs waiting for review", hint: "Oldest first: the next one to review is at the top." },
  returned: { label: "Returned", empty: "Nothing returned for changes", hint: "Sent back with comments. A corrected version comes in as a new review." },
  approved: { label: "Approved", empty: "Nothing approved yet", hint: "Cleared for production in Admin." },
  rejected: { label: "Rejected", empty: "Nothing rejected", hint: "Turned down: these won't be produced." },
} as const;
type View = keyof typeof VIEWS;

/**
 * Promotional materials: designs the marketing assistant sends from Admin for
 * the pharmacist's approval before anything is printed or given to doctors.
 */
export default async function MaterialReviewsPage({ searchParams }: { searchParams: Search }) {
  const { fmt, allowed, may } = await pageFor("materials.view");
  if (!allowed) return <NoAccess what="promotional materials" />;
  const search = await searchParams;
  const view = (param(search, "view", "waiting") in VIEWS ? param(search, "view", "waiting") : "waiting") as View;
  const { items, counts } = await load<{ items: MaterialReview[]; counts: Record<MaterialReviewStatus, number> }>(`/material-reviews?status=${view}`);
  const reviewer = may("materials.review");

  return (
    <>
      <PageHeader title="Promotional materials">
        Every leaflet, poster and giveaway is approved here before Admin produces it.
      </PageHeader>
      <Tabs
        label="Promotional materials"
        current={view}
        tabs={(Object.keys(VIEWS) as View[]).map((v) => ({
          value: v,
          label: VIEWS[v].label,
          href: `/material-reviews?view=${v}`,
          count: v === "waiting" ? counts.waiting : undefined,
        }))}
      />
      <p className="mb-3 text-meta text-ink-3">{VIEWS[view].hint}</p>

      <Sheet>
        {items.length === 0 ? (
          <Empty icon="approvals" title={VIEWS[view].empty} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <Head columns={["Material", "Product", "Status", "Sent by", { label: view === "waiting" ? "Date submitted" : "Date reviewed", right: true }]} />
              <tbody className="divide-y divide-rule">
                {items.map((r) => (
                  <tr key={r.id} className="relative hover:bg-bench/40">
                    <td className="py-3 pr-3 pl-5 align-top">
                      <Link href={`/material-reviews/${r.id}`} className="font-semibold text-hema after:absolute after:inset-0 hover:underline">
                        {r.title}
                      </Link>
                      <span className="block text-meta text-ink-3">
                        {r.kind} · version {r.version} · {r.number}
                      </span>
                    </td>
                    <td className="px-3 py-3 align-top text-ink-2">{r.product ?? "—"}</td>
                    <td className="px-3 py-3 align-top">
                      <MaterialReviewMark status={r.status} />
                      {r.reviewedBy && <span className="mt-1 block text-meta text-ink-3">by {r.reviewedBy}</span>}
                    </td>
                    <td className="px-3 py-3 align-top text-ink-2">{r.sentBy}</td>
                    <td className="py-3 pr-5 pl-3 text-right align-top text-meta whitespace-nowrap text-ink-2">
                      {fmt.whenLabel(view === "waiting" ? r.receivedAt : (r.reviewedAt ?? r.receivedAt))}
                      {view === "waiting" && reviewer && (
                        <span className="relative z-10 mt-1 block">
                          <Link href={`/material-reviews/${r.id}`} className="font-semibold text-hema hover:underline">
                            Review
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
