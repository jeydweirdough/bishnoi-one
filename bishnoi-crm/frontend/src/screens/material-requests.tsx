import { PageHeader, Sheet, Empty } from "@/src/platform/ui/sheet";
import { ToggleLinks } from "@/src/platform/ui/toggle-links";
import { canAny } from "@/src/platform/lib/access";
import { getCompanyMe, load } from "@/src/platform/lib/api";
import { makeFormat } from "@/src/platform/lib/format";
import { NoAccess } from "../components/admin/words";
import { RequestDecision } from "../components/materials/request-decision";
import type { MaterialRequest, MaterialRequestStatus } from "../actions/materials";

export const metadata = { title: "Promotional materials" };

type Search = Promise<Record<string, string | string[] | undefined>>;

const VIEWS: Record<MaterialRequestStatus, { label: string; empty: string }> = {
  waiting: { label: "For approval", empty: "No requests waiting for your approval" },
  approved: { label: "Approved", empty: "Nothing approved yet" },
  rejected: { label: "Rejected", empty: "Nothing rejected" },
};

const ADMIN_STATE: Record<MaterialRequest["adminState"], string> = {
  requested: "Not yet given out",
  distributed: "Given out",
  cancelled: "Cancelled in Admin",
};

/**
 * Promotional materials Admin asks to give to the teams this person runs:
 * leaflets, posters and giveaways the pharmacist has already approved. The
 * manager approves or rejects each request; Admin gives out only what's approved.
 */
export default async function MaterialRequestsPage({ searchParams }: { searchParams: Search }) {
  const me = await getCompanyMe();
  if (!canAny(me, ["admin.settings", "department.manage"])) return <NoAccess what="Promotional materials" />;
  const fmt = makeFormat(me.org);
  const params = await searchParams;
  const view = (typeof params.view === "string" && params.view in VIEWS ? params.view : "waiting") as MaterialRequestStatus;
  const { items, counts } = await load<{ items: MaterialRequest[]; counts: Record<MaterialRequestStatus, number> }>(`/material-requests?status=${view}`);

  return (
    <>
      <PageHeader title="Promotional materials">
        Requests from Admin to give promotional materials to your teams. The pharmacist has approved each design; you approve how many go to whom.
      </PageHeader>
      <div className="mb-4">
        <ToggleLinks
          current={view}
          options={(Object.keys(VIEWS) as MaterialRequestStatus[]).map((v) => ({
            value: v,
            label: v === "waiting" && counts.waiting ? `${VIEWS[v].label} · ${counts.waiting}` : VIEWS[v].label,
            href: `/materials?view=${v}`,
          }))}
        />
      </div>
      <Sheet>
        {items.length === 0 ? (
          <Empty icon="approvals" title={VIEWS[view].empty} />
        ) : (
          <ul className="divide-y divide-rule">
            {items.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">
                    {r.quantity.toLocaleString()} × {r.material.title ?? "Promotional material"}
                  </p>
                  <p className="text-meta text-ink-3">
                    {[r.material.kind, r.material.product].filter(Boolean).join(" · ")}
                    {r.material.kind || r.material.product ? " · " : ""}
                    {r.reference}
                  </p>
                  <p className="mt-1 text-sm text-ink-2">
                    For {r.recipient ? `${r.recipient.name}, ${r.team.name}` : `the whole of ${r.team.name}`}
                    {r.purpose ? ` · ${r.purpose}` : ""}
                  </p>
                  <p className="mt-1 text-meta text-ink-3">
                    Requested by {r.requestedBy ?? "Admin"} · {fmt.whenLabel(r.receivedAt)}
                    {r.status !== "waiting" && r.decidedBy ? ` · ${r.status === "approved" ? "approved" : "rejected"} by ${r.decidedBy}${r.decidedAt ? ` ${fmt.whenLabel(r.decidedAt).toLowerCase()}` : ""}` : ""}
                  </p>
                  {r.note && <p className="mt-1 text-sm text-ink-2">Note: {r.note}</p>}
                </div>
                <div className="shrink-0 text-right">
                  {r.status === "waiting" && r.adminState !== "cancelled" ? (
                    <RequestDecision id={r.id} title={`${r.quantity.toLocaleString()} × ${r.material.title ?? "material"}`} />
                  ) : (
                    <span className="text-meta text-ink-3">
                      {r.adminState === "distributed" && r.distributedOn ? `Given out ${fmt.dateLabel(r.distributedOn)}` : ADMIN_STATE[r.adminState]}
                    </span>
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
